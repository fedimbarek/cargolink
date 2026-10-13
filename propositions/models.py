from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from annonces.models import DemandeTransport
from users.models import Transporteur


class Vehicle(models.Model):
    class Type(models.TextChoices):
        CAMIONNETTE = "CAMIONNETTE", "Camionnette"
        CAMION = "CAMION", "Camion"
        SEMI = "SEMI", "Semi-remorque"
        FRIGO = "FRIGO", "Frigorifique"

    transporteur = models.ForeignKey(Transporteur, on_delete=models.CASCADE, related_name="vehicles")
    registration_number = models.CharField("Immatriculation", max_length=50, unique=True)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.CAMION)
    capacity_weight = models.DecimalField("Capacité (kg)", max_digits=10, decimal_places=2,
                                          validators=[MinValueValidator(1)])
    capacity_volume = models.DecimalField("Volume (m³)", max_digits=10, decimal_places=2,
                                          validators=[MinValueValidator(0.1)])
    availability = models.BooleanField("Disponible", default=True)

    def __str__(self):
        return f"{self.registration_number} ({self.get_type_display()}, {self.capacity_weight} kg)"

    # ---------- règles métier ----------
    def peut_transporter(self, demande):
        if demande.weight > self.capacity_weight:
            return False
        if demande.volume is not None and demande.volume > self.capacity_volume:
            return False
        return True

    def taux_remplissage(self, demande):
        """% de la capacité utilisée: plus c'est haut, moins on gaspille de capacité."""
        return float(demande.weight / self.capacity_weight * 100)


class Proposition(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        ACCEPTED = "ACCEPTED", "Acceptée"
        REJECTED = "REJECTED", "Refusée"
        WITHDRAWN = "WITHDRAWN", "Retirée"

    ACTIVES = [Status.PENDING, Status.ACCEPTED]

    demande = models.ForeignKey(DemandeTransport, on_delete=models.CASCADE, related_name="propositions")
    transporteur = models.ForeignKey(Transporteur, on_delete=models.CASCADE, related_name="propositions")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="propositions",
                                verbose_name="Véhicule")
    price = models.DecimalField("Prix (TND)", max_digits=10, decimal_places=2,
                                validators=[MinValueValidator(1)])
    estimated_duration = models.PositiveIntegerField("Durée estimée (heures)",
                                                     validators=[MinValueValidator(1)])
    message = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # un transporteur ne peut avoir qu'UNE proposition active par demande
            models.UniqueConstraint(
                fields=["demande", "transporteur"],
                condition=Q(status__in=["PENDING", "ACCEPTED"]),
                name="une_proposition_active_par_transporteur",
            )
        ]

    def __str__(self):
        return f"{self.transporteur} → demande #{self.demande_id}: {self.price} TND"

    @property
    def badge_class(self):
        return {"PENDING": "bg-warning text-dark", "ACCEPTED": "bg-success",
                "REJECTED": "bg-danger", "WITHDRAWN": "bg-secondary"}.get(self.status, "bg-secondary")