from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from reservations.models import Reservation

from .services import ErreurEvaluation, evaluer as creer_evaluation


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def evaluer_reservation(request, pk):
    """Une PME évalue la réservation terminée (note de 1 à 5 + commentaire)."""
    reservation = get_object_or_404(Reservation, pk=pk)
    if reservation.pme.user_id != request.user.pk:
        raise PermissionDenied
    try:
        evaluation = creer_evaluation(
            reservation,
            request.data.get("note"),
            request.data.get("commentaire", ""),
        )
    except ErreurEvaluation as erreur:
        return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(
        {
            "detail": "Évaluation enregistrée.",
            "note": getattr(evaluation, "note", request.data.get("note")),
            "commentaire": getattr(evaluation, "commentaire", request.data.get("commentaire", "")),
        },
        status=status.HTTP_201_CREATED,
    )