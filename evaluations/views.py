from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from reservations.models import Reservation
from users.decorators import role_required
from users.models import Transporteur

from .models import Evaluation
from .services import ErreurEvaluation, evaluer as creer_evaluation


@role_required("PME")
@require_POST
def evaluer(request, pk):
    reservation = get_object_or_404(Reservation, pk=pk)
    if reservation.pme.user_id != request.user.pk:
        raise PermissionDenied
    try:
        creer_evaluation(
            reservation,
            request.POST.get("note"),
            request.POST.get("commentaire", ""),
        )
    except ErreurEvaluation as erreur:
        messages.error(request, str(erreur))
    else:
        messages.success(request, "Votre évaluation a été enregistrée.")
    return redirect("reservations:detail", pk=reservation.pk)


def avis(request, pk):
    transporteur = get_object_or_404(Transporteur, pk=pk)
    evaluations = Evaluation.objects.filter(
        reservation__transporteur=transporteur
    ).select_related("reservation__proposition__demande__pme__user")
    return render(request, "evaluations/avis.html", {
        "transporteur": transporteur,
        "evaluations": evaluations,
    })