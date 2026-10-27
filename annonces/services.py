"""
API externes utilisées par le module annonces :
  - Dictionnaire local des gouvernorats tunisiens (aucun appel réseau)
  - Nominatim (OpenStreetMap) : repli pour les villes absentes du dictionnaire
  - OSRM (routage)            : distance et durée routières
  - Repli haversine x 1.3     : si OSRM est indisponible
Aucune clé API n'est nécessaire.
"""
import hashlib
import logging
import time
import unicodedata
from math import asin, cos, radians, sin, sqrt

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OSRM_URL = "https://router.project-osrm.org/route/v1/driving"
HEADERS = {"User-Agent": "CargoLink-StackUnity/1.0 (projet universitaire Django)"}
TIMEOUT = 5
VITESSE_MOYENNE_KMH = 62      # même moyenne que l'estimation OSRM (471 km ≈ 7,6 h)
COEFF_ROUTE = 1.3             # distance route ≈ distance à vol d'oiseau x 1.3

# --- Gouvernorats tunisiens (lat, lon) ---------------------------------------
GOUVERNORATS = {
    "tunis": (36.8065, 10.1815), "ariana": (36.8625, 10.1956),
    "ben arous": (36.7531, 10.2189), "manouba": (36.8101, 10.0863),
    "la manouba": (36.8101, 10.0863), "nabeul": (36.4561, 10.7376),
    "zaghouan": (36.4029, 10.1429), "bizerte": (37.2744, 9.8739),
    "beja": (36.7256, 9.1817), "jendouba": (36.5012, 8.7802),
    "le kef": (36.1742, 8.7049), "kef": (36.1742, 8.7049),
    "siliana": (36.0849, 9.3708), "sousse": (35.8256, 10.6369),
    "monastir": (35.7643, 10.8113), "mahdia": (35.5047, 11.0622),
    "sfax": (34.7406, 10.7603), "kairouan": (35.6781, 10.0963),
    "kasserine": (35.1676, 8.8365), "sidi bouzid": (35.0382, 9.4849),
    "gabes": (33.8815, 10.0982), "medenine": (33.3549, 10.5055),
    "tataouine": (32.9297, 10.4518), "gafsa": (34.4250, 8.7842),
    "tozeur": (33.9197, 8.1335), "kebili": (33.7044, 8.9690),
}


def _norm(texte):
    """minuscules, sans accents, sans espaces superflus ("Béja " -> "beja")."""
    texte = unicodedata.normalize("NFD", texte.strip().lower())
    return "".join(c for c in texte if unicodedata.category(c) != "Mn")


def _coords_locales(ville):
    nom = _norm(ville)
    if nom in GOUVERNORATS:
        return GOUVERNORATS[nom]
    # "Tunis, Tunisie" ou "Tunis Tunisie" -> on teste la première partie
    premier = nom.split(",")[0].strip()
    return GOUVERNORATS.get(premier)


def _haversine_km(c1, c2):
    lat1, lon1 = c1
    lat2, lon2 = c2
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * 6371 * asin(sqrt(a))


def geocoder(ville):
    """Retourne ((lat, lon) ou None, appel_reseau_effectue)."""
    # 1) dictionnaire local : instantané, jamais bloqué
    locales = _coords_locales(ville)
    if locales:
        return locales, False

    # 2) cache
    cle = "geo:" + hashlib.md5(ville.strip().lower().encode()).hexdigest()
    en_cache = cache.get(cle)
    if en_cache:
        return en_cache, False

    # 3) Nominatim (repli pour les villes hors dictionnaire)
    params = {"q": ville, "format": "json", "limit": 1}
    pays = getattr(settings, "NOMINATIM_COUNTRY_CODES", "")
    if pays:
        params["countrycodes"] = pays
    try:
        r = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=TIMEOUT)
        logger.warning("Nominatim %s -> %s", ville, r.status_code)
        r.raise_for_status()
        data = r.json()
        coords = (float(data[0]["lat"]), float(data[0]["lon"]))
    except (requests.RequestException, ValueError, KeyError, IndexError):
        logger.exception("Nominatim a échoué pour %r", ville)
        return None, True
    cache.set(cle, coords, 60 * 60 * 24)      # 24h
    return coords, True


def calculer_trajet(origine, destination):
    """Retourne un dict (distance, durée, coordonnées) ou None si une ville est introuvable."""
    o, appel = geocoder(origine)
    if appel:
        time.sleep(1)          # Nominatim: maximum 1 requête par seconde
    d, _ = geocoder(destination)
    if not o or not d:
        return None

    resultat = {
        "origin_lat": o[0], "origin_lon": o[1],
        "destination_lat": d[0], "destination_lon": d[1],
    }

    # Distance routière réelle (OSRM)
    try:
        r = requests.get(f"{OSRM_URL}/{o[1]},{o[0]};{d[1]},{d[0]}",
                         params={"overview": "false"}, timeout=TIMEOUT)
        r.raise_for_status()
        route = r.json()["routes"][0]
        resultat["distance_km"] = round(route["distance"] / 1000, 1)
        resultat["duration_hours"] = round(route["duration"] / 3600, 1)
        return resultat
    except (requests.RequestException, ValueError, KeyError, IndexError):
        logger.exception("OSRM indisponible, repli haversine")

    # Repli : distance à vol d'oiseau x 1.3
    km = round(_haversine_km(o, d) * COEFF_ROUTE, 1)
    resultat["distance_km"] = km
    resultat["duration_hours"] = round(km / VITESSE_MOYENNE_KMH, 1)
    return resultat