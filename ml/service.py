import logging
from functools import lru_cache
from pathlib import Path

import joblib


logger = logging.getLogger(__name__)
CHEMIN_MODELE = Path(__file__).resolve().with_name("modele_priorite.joblib")


CONSEILS = {
    "urgent": (
        "À traiter rapidement : consultez le détail de la réservation et "
        "contactez l’autre partie si le problème persiste."
    ),
    "normal": (
        "Action recommandée : consultez le détail de la réservation pour "
        "vérifier l’étape ou la demande indiquée."
    ),
    "info": (
        "Aucune action urgente détectée. Consultez les détails si vous "
        "souhaitez davantage d’informations."
    ),
}

LIBELLES_PRIORITE = {
    "urgent": "Urgente",
    "normal": "Normale",
    "info": "Information",
}


class ErreurAssistantIA(Exception):
    """Le modèle local ne peut pas fournir de conseil."""


@lru_cache(maxsize=2)
def _charger_modele(modifie_le):
    try:
        return joblib.load(CHEMIN_MODELE)
    except (OSError, EOFError, ValueError) as erreur:
        logger.exception("Impossible de charger le modèle local de priorité.")
        raise ErreurAssistantIA("Le modèle local de priorité est indisponible.") from erreur


def _obtenir_modele():
    try:
        modifie_le = CHEMIN_MODELE.stat().st_mtime_ns
    except OSError as erreur:
        logger.exception("Impossible de lire le fichier du modèle local de priorité.")
        raise ErreurAssistantIA("Le modèle local de priorité est indisponible.") from erreur
    return _charger_modele(modifie_le)


def analyser_notifications(notifications):
    notifications_lues = [notification for notification in notifications if notification.lue]
    if not notifications_lues:
        return

    modele = _obtenir_modele()
    textes = [notification.message for notification in notifications_lues]
    predictions = modele.predict(textes)
    probabilites = modele.predict_proba(textes)

    for notification, priorite, scores in zip(notifications_lues, predictions, probabilites, strict=True):
        indice = list(modele.classes_).index(priorite)
        confiance = float(scores[indice])
        notification.priorite_ia = priorite
        notification.libelle_priorite_ia = LIBELLES_PRIORITE[priorite]
        notification.confiance_ia = confiance
        notification.confiance_pourcentage_ia = round(confiance * 100)
        if confiance < 0.45:
            notification.conseil_ia = (
                "L’assistant hésite sur la catégorie. Vérifiez le message et "
                "les détails de la réservation manuellement."
            )
        else:
            notification.conseil_ia = CONSEILS[priorite]
