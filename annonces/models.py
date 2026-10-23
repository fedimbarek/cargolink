from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone

from users.models import PME


class DemandeTransport(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Ouverte"
        ASSIGNED = "ASSIGNED", "Transporteur choisi"
        IN_PROGRESS = "IN_PROGRESS", "En cours"
        DELIVERED = "DELIVERED", "Livrée"
        CANCELLED = "CANCELLED", "Annulée"
        EXPIRED = "EXPIRED", "Expirée"

    pme = models.ForeignKey(PME, on_delete=models.CASCADE, related_name="demandes")
    origin = models.CharField("Origine", max_length=150)
    destination = models.CharField("Destination", max_length=150)
    pickup_date = models.DateTimeField("Date de chargement")
    delivery_date = models.DateTimeField("Date de livraison souhaitée")
    weight = models.DecimalField("Poids (kg)", max_digits=10, decimal_places=2,
                                 validators=[MinValueValidator(0.01)])
    volume = models.DecimalField("Volume (m³)", max_digits=10, decimal_places=2,
                                 null=True, blank=True)
    cargo_type = models.CharField("Type de marchandise", max_length=100)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    # Calculés grâce aux API externes (Nominatim + OSRM), voir services.py
    distance_km = models.DecimalField(max_digits=8, decimal_places=1, null=True, blank=True)
    duration_hours = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    origin_lat = models.FloatField(null=True, blank=True)
    origin_lon = models.FloatField(null=True, blank=True)
    destination_lat = models.FloatField(null=True, blank=True)
    destination_lon = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.origin} → {self.destination} ({self.weight} kg)"

    # ---------- règles métier ----------
    def clean(self):
        if self.pickup_date and self.delivery_date and self.delivery_date <= self.pickup_date:
            raise ValidationError("La date de livraison doit être après la date de chargement.")
        if (self.status == self.Status.OPEN and self.pickup_date
                and self.pickup_date < timezone.now()):
            raise ValidationError("La date de chargement doit être dans le futur.")
        if self.origin and self.destination and self.origin.strip().lower() == self.destination.strip().lower():
            raise ValidationError("L'origine et la destination doivent être différentes.")

    @property
    def est_modifiable(self):
        """Modifiable seulement si ouverte et sans aucune proposition (sinon les offres deviennent fausses)."""
        return self.status == self.Status.OPEN and not self.propositions.exists()

    @property
    def peut_etre_annulee(self):
        return self.status in (self.Status.OPEN, self.Status.ASSIGNED)

    # Les statuts de Proposition ("PENDING", "ACCEPTED", "REJECTED") sont définis dans propositions/models.py
    def _rejeter_propositions_actives(self):
        self.propositions.filter(status__in=["PENDING", "ACCEPTED"]).update(status="REJECTED")

    @transaction.atomic
    def annuler(self):
        self.status = self.Status.CANCELLED
        self.save(update_fields=["status"])
        self._rejeter_propositions_actives()

    @transaction.atomic
    def expirer(self):
        self.status = self.Status.EXPIRED
        self.save(update_fields=["status"])
        self._rejeter_propositions_actives()

    @property
    def lien_itineraire(self):
        if None in (self.origin_lat, self.origin_lon, self.destination_lat, self.destination_lon):
            return None
        return ("https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route="
                f"{self.origin_lat}%2C{self.origin_lon}%3B{self.destination_lat}%2C{self.destination_lon}")

    @property
    def badge_class(self):
        return {
            "OPEN": "bg-success", "ASSIGNED": "bg-primary", "IN_PROGRESS": "bg-info text-dark",
            "DELIVERED": "bg-dark", "CANCELLED": "bg-danger", "EXPIRED": "bg-secondary",
        }.get(self.status, "bg-secondary")