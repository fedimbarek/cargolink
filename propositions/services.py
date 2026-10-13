"""
Logique métier avancée du module propositions + API externe de taux de change.
  - taux_change()              : API externe open.er-api.com (sans clé, cache 1h)
  - demandes_compatibles()     : MATCHING PME <-> transporteur (capacité + taux de remplissage)
  - comparer()                 : COMPARAISON des offres avec un score pondéré
  - accepter_proposition()     : acceptation atomique (les autres offres sont refusées)
"""
from decimal import Decimal

import requests
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from annonces.models import DemandeTransport

from .models import Proposition


class ErreurMetier(Exception):
    """Règle métier non respectée (message affichable à l'utilisateur)."""


# ---------------- API externe: taux de change ----------------
def taux_change(source="TND", cible="EUR"):
    """Retourne le taux (float) ou None si l'API est indisponible. Données: exchangerate-api.com"""
    cle = f"fx:{source}:{cible}"
    taux = cache.get(cle)
    if taux is not None:
        return taux
    try:
        r = requests.get(f"https://open.er-api.com/v6/latest/{source}", timeout=5)
        r.raise_for_status()
        taux = float(r.json()["rates"][cible])
    except (requests.RequestException, ValueError, KeyError):
        return None
    cache.set(cle, taux, 60 * 60)            # 1h (l'API limite les appels)
    return taux


# ---------------- Matching ----------------
def demandes_compatibles(transporteur):
    """Demandes ouvertes que le transporteur peut assurer, triées par taux de remplissage décroissant."""
    vehicules = list(transporteur.vehicles.filter(availability=True))
    deja = Proposition.objects.filter(
        transporteur=transporteur, status__in=Proposition.ACTIVES).values_list("demande_id", flat=True)
    demandes = (DemandeTransport.objects
                .filter(status=DemandeTransport.Status.OPEN, pickup_date__gt=timezone.now())
                .exclude(pk__in=list(deja)).select_related("pme"))
    resultats = []
    for d in demandes:
        candidats = [(v.taux_remplissage(d), v) for v in vehicules if v.peut_transporter(d)]
        if candidats:
            taux, v = max(candidats, key=lambda c: c[0])
            resultats.append({"demande": d, "vehicle": v, "taux": round(taux)})
    resultats.sort(key=lambda r: -r["taux"])
    return resultats


# ---------------- Comparaison ----------------
def _moins_c_est_mieux(valeur, mini, maxi):
    return 1.0 if maxi == mini else float((maxi - valeur) / (maxi - mini))


def comparer(demande):
    """Score /100 = 50% prix + 30% note du transporteur + 20% durée. La meilleure offre est recommandée."""
    props = list(demande.propositions.filter(status__in=Proposition.ACTIVES)
                 .select_related("transporteur", "vehicle"))
    if not props:
        return []
    prix = [p.price for p in props]
    durees = [p.estimated_duration for p in props]
    taux = taux_change("TND", "EUR")
    lignes = []
    for p in props:
        score = 100 * (0.5 * _moins_c_est_mieux(p.price, min(prix), max(prix))
                       + 0.3 * float(p.transporteur.rating) / 5
                       + 0.2 * _moins_c_est_mieux(p.estimated_duration, min(durees), max(durees)))
        lignes.append({
            "proposition": p,
            "score": round(score),
            "prix_eur": round(p.price * Decimal(str(taux)), 2) if taux else None,
            "prix_km": round(p.price / demande.distance_km, 2) if demande.distance_km else None,
            "recommandee": False,
        })
    lignes.sort(key=lambda l: -l["score"])
    lignes[0]["recommandee"] = True
    return lignes


# ---------------- Acceptation ----------------
@transaction.atomic
def accepter_proposition(proposition):
    demande = DemandeTransport.objects.select_for_update().get(pk=proposition.demande_id)
    proposition = Proposition.objects.select_for_update().get(pk=proposition.pk)
    if demande.status != DemandeTransport.Status.OPEN:
        raise ErreurMetier("Cette demande n'est plus ouverte.")
    if proposition.status != Proposition.Status.PENDING:
        raise ErreurMetier("Cette proposition n'est plus disponible.")
    proposition.status = Proposition.Status.ACCEPTED
    proposition.save(update_fields=["status"])
    demande.propositions.exclude(pk=proposition.pk).filter(
        status=Proposition.Status.PENDING).update(status=Proposition.Status.REJECTED)
    demande.status = DemandeTransport.Status.ASSIGNED
    demande.save(update_fields=["status"])
    # TODO module reservations: créer ici la Reservation liée à cette proposition
    return proposition