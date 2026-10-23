from django.db import models

from annonces.models import DemandeTransport


class PrevisionMeteo(models.Model):
    """Météo prévue pour le chargement (origine) ou la livraison (destination) d'une demande."""

    class Point(models.TextChoices):
        ORIGINE = "ORIGINE", "Chargement"
        DESTINATION = "DESTINATION", "Livraison"

    class Risque(models.TextChoices):
        FAIBLE = "FAIBLE", "Faible"
        MOYEN = "MOYEN", "Moyen"
        ELEVE = "ELEVE", "Élevé"

    demande = models.ForeignKey(DemandeTransport, on_delete=models.CASCADE, related_name="previsions")
    point = models.CharField(max_length=12, choices=Point.choices)
    ville = models.CharField(max_length=150)
    date_prevue = models.DateField("Jour prévu")
    resume = models.CharField("Conditions", max_length=60)
    code_meteo = models.PositiveIntegerField("Code WMO", default=0)
    temp_min = models.DecimalField("Température min (°C)", max_digits=5, decimal_places=1)
    temp_max = models.DecimalField("Température max (°C)", max_digits=5, decimal_places=1)
    precipitation_mm = models.DecimalField("Pluie (mm)", max_digits=6, decimal_places=1, default=0)
    vent_kmh = models.DecimalField("Vent max (km/h)", max_digits=5, decimal_places=1, default=0)
    risque = models.CharField(max_length=6, choices=Risque.choices, default=Risque.FAIBLE)
    raisons = models.CharField("Raisons du risque", max_length=255, blank=True)
    maj_le = models.DateTimeField("Mise à jour", auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["demande", "point"], name="une_prevision_par_point")
        ]
        ordering = ["demande_id", "point"]

    def __str__(self):
        return f"{self.get_point_display()} {self.ville} {self.date_prevue}: {self.resume}"

    @property
    def badge_class(self):
        return {"FAIBLE": "bg-success", "MOYEN": "bg-warning text-dark",
                "ELEVE": "bg-danger"}.get(self.risque, "bg-secondary")


class AlerteMeteo(models.Model):
    """Alerte créée automatiquement quand une prévision présente un risque moyen ou élevé."""

    prevision = models.OneToOneField(PrevisionMeteo, on_delete=models.CASCADE, related_name="alerte")
    niveau = models.CharField(max_length=6, choices=PrevisionMeteo.Risque.choices)
    message = models.CharField(max_length=300)
    lue = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["lue", "-created_at"]

    def __str__(self):
        return f"[{self.get_niveau_display()}] {self.message}"

    @property
    def demande(self):
        return self.prevision.demande

    @property
    def badge_class(self):
        return self.prevision.badge_class
