from django.db import models
from django.utils import timezone

from users.models import Transporteur


class Chauffeur(models.Model):
    transporteur = models.ForeignKey(
        Transporteur,
        on_delete=models.PROTECT,
        related_name="chauffeurs",
    )
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    telephone = models.CharField(max_length=20)
    disponible = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.prenom} {self.nom}"


class Permis(models.Model):
    class Categorie(models.TextChoices):
        B = "B", "B"
        C = "C", "C"
        CE = "CE", "CE"

    chauffeur = models.OneToOneField(
        Chauffeur,
        on_delete=models.CASCADE,
        related_name="permis",
    )
    numero = models.CharField(max_length=50, unique=True)
    categorie = models.CharField(
        max_length=2,
        choices=Categorie.choices,
    )
    date_expiration = models.DateField()

    @property
    def est_expire(self):
        return self.date_expiration < timezone.localdate()

    def __str__(self):
        return f"{self.numero} - {self.chauffeur}"

class Affectation(models.Model):
    proposition = models.OneToOneField(
        "propositions.Proposition",
        on_delete=models.PROTECT,
        related_name="affectation",
    )
    chauffeur = models.ForeignKey(
        Chauffeur,
        on_delete=models.PROTECT,
        related_name="affectations",
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Mission {self.proposition_id} - {self.chauffeur}"