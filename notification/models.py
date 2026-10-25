from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Type(models.TextChoices):
        INFO = "info", "Information"
        RESERVATION = "reservation", "Réservation"
        PROPOSITION = "proposition", "Proposition"
        FACTURE = "facture", "Facture"
        EVALUATION = "evaluation", "Évaluation"

    destinataire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.INFO)
    titre = models.CharField(max_length=150)
    message = models.TextField()
    lien = models.CharField(max_length=255, blank=True)
    lue = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_creation"]

    def __str__(self):
        return f"{self.titre} → {self.destinataire}"