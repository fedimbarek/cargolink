"""
API externe utilisée par le module meteo : Open-Meteo (gratuite, aucune clé API).
  - geocoding-api.open-meteo.com : ville -> coordonnées GPS (si la demande n'en a pas)
  - api.open-meteo.com           : prévision météo journalière (jusqu'à 16 jours)
En cas de panne, on retourne un message d'erreur et l'application continue de marcher.
"""
import hashlib
from datetime import timedelta

import requests
from django.core.cache import cache
from django.utils import timezone

from annonces.models import DemandeTransport

from .models import AlerteMeteo, PrevisionMeteo

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 5
HORIZON_JOURS = 16                       # l'API prévoit au maximum 16 jours

# seuils de risque pour un transport routier
PLUIE_MOYEN, PLUIE_ELEVE = 5, 20         # mm / jour
VENT_MOYEN, VENT_ELEVE = 40, 60          # km/h
CHAUD_MOYEN, CHAUD_ELEVE = 35, 40        # °C
CODES_ORAGE = {95, 96, 99}
CODES_NEIGE_VERGLAS = {56, 57, 66, 67, 71, 73, 75, 77, 85, 86}

LIBELLES = {
    0: "Ciel dégagé", 1: "Plutôt dégagé", 2: "Partiellement nuageux", 3: "Couvert",
    45: "Brouillard", 48: "Brouillard givrant",
    51: "Bruine légère", 53: "Bruine", 55: "Bruine forte",
    56: "Bruine verglaçante", 57: "Bruine verglaçante forte",
    61: "Pluie légère", 63: "Pluie", 65: "Pluie forte",
    66: "Pluie verglaçante", 67: "Pluie verglaçante forte",
    71: "Neige légère", 73: "Neige", 75: "Neige forte", 77: "Grains de neige",
    80: "Averses légères", 81: "Averses", 82: "Averses violentes",
    85: "Averses de neige", 86: "Fortes averses de neige",
    95: "Orage", 96: "Orage avec grêle", 99: "Orage avec forte grêle",
}


class ErreurMeteo(Exception):
    """Problème avec l'API météo (message affichable à l'utilisateur)."""


# ---------------- appels à l'API ----------------
def geocoder(ville):
    """Retourne (lat, lon) ou None si la ville est introuvable. Lève ErreurMeteo si l'API est en panne."""
    cle = "meteo:geo:" + hashlib.md5(ville.strip().lower().encode()).hexdigest()
    coords = cache.get(cle)
    if coords:
        return coords
    try:
        r = requests.get(GEOCODING_URL, params={"name": ville, "count": 1, "language": "fr", "format": "json"},
                         timeout=TIMEOUT)
        r.raise_for_status()
        resultats = r.json().get("results") or []
    except (requests.RequestException, ValueError):
        raise ErreurMeteo("API météo indisponible (géocodage). Réessayez plus tard.")
    if not resultats:
        return None
    coords = (float(resultats[0]["latitude"]), float(resultats[0]["longitude"]))
    cache.set(cle, coords, 60 * 60 * 24)
    return coords


def prevision_jour(lat, lon, jour):
    """Prévision d'un jour donné: dict (temp_min, temp_max, pluie, vent, code)."""
    cle = f"meteo:prev:{round(lat, 2)}:{round(lon, 2)}:{jour.isoformat()}"
    data = cache.get(cle)
    if data:
        return data
    params = {
        "latitude": lat, "longitude": lon, "timezone": "auto",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
        "start_date": jour.isoformat(), "end_date": jour.isoformat(),
    }
    try:
        r = requests.get(FORECAST_URL, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        d = r.json()["daily"]
        data = {
            "temp_min": float(d["temperature_2m_min"][0]),
            "temp_max": float(d["temperature_2m_max"][0]),
            "pluie": float(d["precipitation_sum"][0] or 0),
            "vent": float(d["wind_speed_10m_max"][0] or 0),
            "code": int(d["weather_code"][0] or 0),
        }
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
        raise ErreurMeteo("API météo indisponible (prévision). Réessayez plus tard.")
    cache.set(cle, data, 60 * 60)            # 1h
    return data


# ---------------- règles métier ----------------
def evaluer_risque(temp_min, temp_max, pluie, vent, code):
    """Retourne (niveau, [raisons]) pour un transport routier."""
    eleve, moyen = [], []
    if code in CODES_ORAGE:
        eleve.append("orage")
    if pluie >= PLUIE_ELEVE:
        eleve.append(f"pluie forte ({pluie:g} mm)")
    elif pluie >= PLUIE_MOYEN:
        moyen.append(f"pluie ({pluie:g} mm)")
    if vent >= VENT_ELEVE:
        eleve.append(f"vent violent ({vent:g} km/h)")
    elif vent >= VENT_MOYEN:
        moyen.append(f"vent fort ({vent:g} km/h)")
    if temp_max >= CHAUD_ELEVE:
        eleve.append(f"canicule ({temp_max:g} °C)")
    elif temp_max >= CHAUD_MOYEN:
        moyen.append(f"forte chaleur ({temp_max:g} °C)")
    if code in CODES_NEIGE_VERGLAS or temp_min <= 0:
        moyen.append("risque de neige ou de verglas")
    if code in (45, 48):
        moyen.append("brouillard")
    if eleve:
        return PrevisionMeteo.Risque.ELEVE, eleve + moyen
    if moyen:
        return PrevisionMeteo.Risque.MOYEN, moyen
    return PrevisionMeteo.Risque.FAIBLE, []


def _synchroniser_alerte(prevision):
    if prevision.risque == PrevisionMeteo.Risque.FAIBLE:
        AlerteMeteo.objects.filter(prevision=prevision).delete()
        return
    message = (f"{prevision.get_point_display()} à {prevision.ville} le "
               f"{prevision.date_prevue:%d/%m/%Y} : {prevision.raisons}")
    alerte, cree = AlerteMeteo.objects.get_or_create(
        prevision=prevision, defaults={"niveau": prevision.risque, "message": message})
    if not cree and (alerte.niveau != prevision.risque or alerte.message != message):
        alerte.niveau, alerte.message, alerte.lue = prevision.risque, message, False
        alerte.save()


def mettre_a_jour(demande):
    """Récupère la météo du chargement et de la livraison, crée/met à jour prévisions et alertes.
    Retourne la liste des messages d'erreur (vide si tout s'est bien passé)."""
    P = PrevisionMeteo.Point
    points = [
        (P.ORIGINE, "chargement", demande.origin, demande.origin_lat, demande.origin_lon, demande.pickup_date),
        (P.DESTINATION, "livraison", demande.destination, demande.destination_lat,
         demande.destination_lon, demande.delivery_date),
    ]
    aujourdhui = timezone.localdate()
    erreurs = []
    for point, nom, ville, lat, lon, quand in points:
        jour = timezone.localtime(quand).date()
        if not (aujourdhui <= jour <= aujourdhui + timedelta(days=HORIZON_JOURS - 1)):
            erreurs.append(f"Pas de prévision pour le {nom} ({jour:%d/%m/%Y}) : "
                           f"l'API couvre seulement les {HORIZON_JOURS} prochains jours.")
            continue
        try:
            if lat is None or lon is None:
                coords = geocoder(ville)
                if not coords:
                    erreurs.append(f"Ville introuvable pour le {nom} : « {ville} ».")
                    continue
                lat, lon = coords
            m = prevision_jour(lat, lon, jour)
        except ErreurMeteo as e:
            erreurs.append(str(e))
            continue
        risque, raisons = evaluer_risque(m["temp_min"], m["temp_max"], m["pluie"], m["vent"], m["code"])
        prevision, _ = PrevisionMeteo.objects.update_or_create(
            demande=demande, point=point,
            defaults=dict(
                ville=ville, date_prevue=jour, code_meteo=m["code"],
                resume=LIBELLES.get(m["code"], "Conditions variables"),
                temp_min=m["temp_min"], temp_max=m["temp_max"],
                precipitation_mm=m["pluie"], vent_kmh=m["vent"],
                risque=risque, raisons=", ".join(raisons),
            ))
        _synchroniser_alerte(prevision)
    return erreurs


        

# ---------------- qui voit quoi ----------------
MAX_DEMANDES_PAR_ACTUALISATION = 10      # évite de bloquer la page (chaque demande = 2 appels API)


def demandes_du_user(user):
    """PME: ses demandes. Transporteur: les demandes où il a une proposition en attente ou acceptée. Admin: toutes."""
    D = DemandeTransport
    if user.is_superuser or user.role == "ADMIN":
        return D.objects.all()
    if user.role == "PME":
        return D.objects.filter(pme__user=user)
    if user.role == "TRANSPORTEUR":
        return D.objects.filter(propositions__transporteur__user=user,
                                propositions__status__in=["PENDING", "ACCEPTED"]).distinct()
    return D.objects.none()


def alertes_visibles(user):
    return (AlerteMeteo.objects.filter(prevision__demande__in=demandes_du_user(user))
            .select_related("prevision__demande"))


def demandes_a_actualiser(user):
    D = DemandeTransport
    return demandes_du_user(user).filter(
        status__in=[D.Status.OPEN, D.Status.ASSIGNED, D.Status.IN_PROGRESS]).order_by("pickup_date")


def actualiser_tout(user):
    """Met à jour la météo des demandes actives de l'utilisateur.
    Retourne (nombre de demandes traitées, liste d'erreurs lisibles)."""
    demandes = list(demandes_a_actualiser(user)[:MAX_DEMANDES_PAR_ACTUALISATION])
    erreurs = []
    for d in demandes:
        erreurs += [f"Demande #{d.pk} : {e}" for e in mettre_a_jour(d)]
    return len(demandes), erreurs