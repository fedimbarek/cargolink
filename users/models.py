from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        PME = "PME", "PME"
        TRANSPORTEUR = "TRANSPORTEUR", "Transporteur"
        ADMIN = "ADMIN", "Administrateur"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Actif"
        PENDING = "PENDING", "En attente"
        BLOCKED = "BLOCKED", "Bloqué"

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PME)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)

    USERNAME_FIELD = "email"      # on se connecte avec l'email
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return f"{self.email} ({self.role})"


class PME(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="pme")
    company_name = models.CharField(max_length=150)
    registration_number = models.CharField(max_length=50, blank=True)
    address = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.company_name


class Transporteur(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="transporteur")
    company_name = models.CharField(max_length=150)
    license_number = models.CharField(max_length=50, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    verified = models.BooleanField(default=False)   # validé par l'admin

    def __str__(self):
        return self.company_name
