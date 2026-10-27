from decimal import Decimal

from django.db import transaction
from django.db.models import Avg

from reservations.models import Reservation

from .models import Evaluation


class ErreurEvaluation(Exception):
    """Erreur métier liée à une évaluation."""


@transaction.atomic
def evaluer(reservation, note, commentaire=""):
    if reservation.status != Reservation.Status.LIVREE:
        raise ErreurEvaluation("La réservation doit être livrée avant son évaluation.")
    try:
        note = int(note)
    except (TypeError, ValueError):
        raise ErreurEvaluation("La note doit être comprise entre 1 et 5.") from None
    if not 1 <= note <= 5:
        raise ErreurEvaluation("La note doit être comprise entre 1 et 5.")
    if Evaluation.objects.filter(reservation=reservation).exists():
        raise ErreurEvaluation("Cette réservation a déjà été évaluée.")

    evaluation = Evaluation.objects.create(
        reservation=reservation,
        note=note,
        commentaire=commentaire[:2000],
    )
    moyenne = Evaluation.objects.filter(
        reservation__transporteur=reservation.transporteur
    ).aggregate(moyenne=Avg("note"))["moyenne"]
    reservation.transporteur.rating = Decimal(str(moyenne)).quantize(Decimal("0.01"))
    reservation.transporteur.save(update_fields=["rating"])
    return evaluation
