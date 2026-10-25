from celery import shared_task

from .services import ErreurIA, calculer_estimation


@shared_task
def estimer_trajet_task(origin, destination, weight, volume, cargo_type, urgent):
    """Tâche Celery : on retourne toujours un dict (jamais d'exception) pour que le front affiche un message."""
    try:
        return {"ok": True, "estimation": calculer_estimation(origin, destination, weight, volume, cargo_type, urgent)}
    except ErreurIA as e:
        return {"ok": False, "erreur": str(e)}
