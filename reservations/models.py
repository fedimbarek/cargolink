from django.conf import settings
from django.db import models

from propositions.models import Proposition
from users.models import Transporteur


class Reservation(models.Model):
    """Mission créée automatiquement quand la PME accepte une proposition.
    Cycle: CONFIRMEE -> EN_COURS -> LIVREE (ou ANNULEE avant le départ)."""

    class Status(models.TextChoices):
        CONFIRMEE = "CONFIRMEE", "Confirmée"
        EN_COURS = "EN_COURS", "En cours de livraison"
        LIVREE = "LIVREE", "Livrée"
        ANNULEE = "ANNULEE", "Annulée"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reservations")
    transporteur = models.ForeignKey(Transporteur, on_delete=models.PROTECT, related_name="reservations")
    proposition = models.OneToOneField(Proposition, on_delete=models.PROTECT, related_name="reservation")
    nom_contact = models.CharField("Nom du contact", max_length=150)
    email_contact = models.EmailField("Email de contact")
    nom_societe = models.CharField("Société", max_length=150)
    matricule = models.CharField("Matricule / registre", max_length=50, blank=True)
    adresse = models.CharField("Adresse", max_length=255, blank=True)
    telephone = models.CharField("Téléphone", max_length=20, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CONFIRMEE)
    created_at = models.DateTimeField(auto_now_add=True)
    demarree_le = models.DateTimeField("Départ", null=True, blank=True)
    livree_le = models.DateTimeField("Livrée le", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Réservation #{self.pk} - {self.demande}"

    # ---------- raccourcis ----------
    @property
    def demande(self):
        return self.proposition.demande

    @property
    def pme(self):
        return self.proposition.demande.pme

    @property
    def badge_class(self):
        return {"CONFIRMEE": "bg-primary", "EN_COURS": "bg-info text-dark",
                "LIVREE": "bg-success", "ANNULEE": "bg-danger"}.get(self.status, "bg-secondary")


class EtapeSuivi(models.Model):
    """Étape du suivi de livraison (journal visible par la PME et le transporteur)."""

    class Type(models.TextChoices):
        CONFIRMATION = "CONFIRMATION", "Réservation confirmée"
        CHARGEMENT = "CHARGEMENT", "Marchandise chargée / départ"
        EN_ROUTE = "EN_ROUTE", "En route"
        INCIDENT = "INCIDENT", "Incident / retard"
        LIVRAISON = "LIVRAISON", "Livrée"
        ANNULATION = "ANNULATION", "Annulée"

    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name="etapes")
    type = models.CharField(max_length=15, choices=Type.choices)
    commentaire = models.CharField(max_length=255, blank=True)
    localisation = models.CharField("Localisation", max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"{self.get_type_display()} ({self.created_at:%d/%m %H:%M})"


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications_suivi")
    transporteur = models.ForeignKey(
        Transporteur, null=True, blank=True, on_delete=models.SET_NULL, related_name="notifications"
    )
    message = models.CharField(max_length=255)
    lien = models.CharField(max_length=255, blank=True)
    lue = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user}: {self.message}"
