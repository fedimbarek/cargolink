import logging
from time import perf_counter

from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from propositions.models import Proposition
from users.decorators import role_required
from .recommandation import recommander

logger = logging.getLogger(__name__)


@role_required("TRANSPORTEUR")
@require_http_methods(["GET"])
def recommandation(request):
    missions = Proposition.objects.filter(
        transporteur__user=request.user,
        status="ACCEPTED",
        affectation__isnull=True,
    ).select_related("demande", "transporteur").order_by("-pk")

    resultats = []
    selection = request.GET.get("mission", "")
    temps_ms = None
    erreur = ""

    if selection:
        if not selection.isdecimal():
            erreur = "Sélectionnez une mission dans la liste."
        else:
            mission = get_object_or_404(missions, pk=int(selection))
            debut = perf_counter()
            try:
                resultats = recommander(mission.transporteur, mission)
            except Exception:
                logger.exception("Recommandation chauffeur indisponible")
                erreur = "La recommandation est indisponible. Réessayez plus tard."
            temps_ms = round((perf_counter() - debut) * 1000, 2)

    return render(request, "chauffeurs/recommandation.html", {
        "missions": missions, "selection": selection,
        "resultats": resultats, "temps_ms": temps_ms, "erreur": erreur,
    })