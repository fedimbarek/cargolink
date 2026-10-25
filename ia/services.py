"""Orchestration d'une estimation : distance (API externe, lente) puis modèle ML (rapide)."""
from annonces.services import calculer_trajet

from . import ml


class ErreurIA(Exception):
    """Erreur affichable à l'utilisateur."""


def calculer_estimation(origin, destination, weight, volume=None, cargo_type="", urgent=False):
    """Retourne un dict JSON-sérialisable. Lève ErreurIA si la distance est introuvable ou si les entrées
    sont invalides. C'est cette fonction (lente à cause du réseau) qui peut être déportée dans Celery."""
    trajet = calculer_trajet(origin, destination)
    if not trajet:
        raise ErreurIA("Impossible de calculer la distance (ville introuvable ou service de cartographie "
                       "indisponible). Réessayez dans un instant.")
    try:
        est = ml.estimer(trajet["distance_km"], weight, volume, cargo_type, urgent)
    except ValueError as e:
        raise ErreurIA(str(e))
    est["distance_km"] = float(trajet["distance_km"])
    est["duree_h"] = float(trajet["duration_hours"])
    return est
