from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from reservations.models import Reservation


class Evaluation(models.Model):
    reservation = models.OneToOneField(
        Reservation, on_delete=models.CASCADE, related_name="evaluation"
    )
    note = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    commentaire = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Évaluation {self.note}/5 - réservation #{self.reservation_id}"

    @property
    def etoiles(self):
        return "★" * self.note + "☆" * (5 - self.note)
