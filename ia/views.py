import json

from celery.result import AsyncResult
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from . import ml
from .forms import EstimationForm
from .services import ErreurIA, calculer_estimation
from .tasks import estimer_trajet_task

LIMITE_REQUETES, FENETRE_SECONDES = 20, 60      # 20 estimations / minute / utilisateur (appels API externes coûteux)


def _limite_atteinte(user):
    cle = f"ia:rl:{user.pk}"
    cache.add(cle, 0, FENETRE_SECONDES)
    try:
        return cache.incr(cle) > LIMITE_REQUETES
    except ValueError:
        return False


def _corps(request):
    if request.content_type == "application/json":
        try:
            data = json.loads(request.body or b"{}")
            return data if isinstance(data, dict) else None
        except ValueError:
            return None
    return request.POST


@login_required
@require_POST
def estimer(request):
    """POST /ia/estimer/  {origin, destination, weight, [volume, cargo_type, urgent]}
    - 200 + estimation si le traitement est synchrone (pas de Redis configuré)
    - 202 + task_id si le calcul est délégué à Celery (à interroger via /ia/tache/<id>/)"""
    if request.user.role not in ("PME", "TRANSPORTEUR"):
        return JsonResponse({"erreur": "Réservé aux PME et aux transporteurs."}, status=403)
    if _limite_atteinte(request.user):
        return JsonResponse({"erreur": "Trop de demandes d'estimation, réessayez dans une minute."}, status=429)
    data = _corps(request)
    if data is None:
        return JsonResponse({"erreur": "Corps de requête invalide."}, status=400)
    form = EstimationForm(data)
    if not form.is_valid():
        return JsonResponse({"erreur": "Données invalides.", "champs": form.errors.get_json_data()}, status=400)
    c = form.cleaned_data
    args = (c["origin"], c["destination"], float(c["weight"]), float(c["volume"]) if c["volume"] else None,
            c["cargo_type"], c["urgent"])

    if settings.CELERY_BROKER_URL:                      # mode asynchrone: la requête HTTP n'est pas bloquée
        try:
            tache = estimer_trajet_task.delay(*args)
        except Exception:
            return JsonResponse({"erreur": "File de tâches indisponible, réessayez plus tard."}, status=503)
        return JsonResponse({"etat": "EN_COURS", "task_id": tache.id}, status=202)

    try:
        return JsonResponse({"etat": "TERMINE", "estimation": calculer_estimation(*args)})
    except ErreurIA as e:
        return JsonResponse({"etat": "ECHEC", "erreur": str(e)}, status=502)


@login_required
@require_GET
def tache(request, task_id):
    """GET /ia/tache/<id>/ : état d'une estimation asynchrone."""
    if not settings.CELERY_BROKER_URL:
        return JsonResponse({"erreur": "Mode asynchrone désactivé."}, status=404)
    res = AsyncResult(task_id)
    if res.state in ("PENDING", "STARTED", "RETRY"):
        return JsonResponse({"etat": "EN_COURS"})
    if res.state == "SUCCESS":
        r = res.result
        if r.get("ok"):
            return JsonResponse({"etat": "TERMINE", "estimation": r["estimation"]})
        return JsonResponse({"etat": "ECHEC", "erreur": r["erreur"]}, status=502)
    return JsonResponse({"etat": "ECHEC", "erreur": "Le calcul a échoué."}, status=500)


@login_required
def modele(request):
    """Page de présentation du modèle : métriques, comparaison des algorithmes, importance des variables."""
    metriques = ml.lire_metriques()
    return render(request, "ia/modele.html", {"m": metriques})
