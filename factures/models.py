from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from propositions.models import Proposition

CENTIME = Decimal("0.01")
ZERO = Decimal("0.00")


class Facture(models.Model):
    """Facture d'une mission (proposition acceptée), émise par le transporteur à destination de la PME.
    Cycle: BROUILLON -> EMISE -> PARTIELLE -> PAYEE (ou ANNULEE tant qu'aucun paiement n'est enregistré)."""

    class Status(models.TextChoices):
        BROUILLON = "BROUILLON", "Brouillon"
        EMISE = "EMISE", "Émise"
        PARTIELLE = "PARTIELLE", "Partiellement payée"
        PAYEE = "PAYEE", "Payée"
        ANNULEE = "ANNULEE", "Annulée"

    proposition = models.OneToOneField(Proposition, on_delete=models.PROTECT, related_name="facture",
                                       verbose_name="Proposition acceptée")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.BROUILLON)
    montant_ht = models.DecimalField("Montant HT (TND)", max_digits=10, decimal_places=2,
                                     validators=[MinValueValidator(Decimal("0.01"))])
    taux_tva = models.DecimalField("TVA (%)", max_digits=5, decimal_places=2, default=Decimal("19"),
                                   validators=[MinValueValidator(0), MaxValueValidator(100)])
    date_echeance = models.DateField("Date d'échéance")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    emise_le = models.DateTimeField("Émise le", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.numero} - {self.total_ttc} TND"

    # ---------- raccourcis vers la mission ----------
    @property
    def demande(self):
        return self.proposition.demande

    @property
    def transporteur(self):
        return self.proposition.transporteur

    @property
    def pme(self):
        return self.proposition.demande.pme

    @property
    def trajet(self):
        return f"{self.demande.origin} → {self.demande.destination}"

    # ---------- montants ----------
    @property
    def numero(self):
        return f"FAC-{self.created_at.year}-{self.pk:05d}" if self.pk and self.created_at else "FAC-?"

    @property
    def montant_tva(self):
        return (Decimal(self.montant_ht) * Decimal(self.taux_tva) / 100).quantize(CENTIME, ROUND_HALF_UP)

    @property
    def total_ttc(self):
        return Decimal(self.montant_ht).quantize(CENTIME, ROUND_HALF_UP) + self.montant_tva

    @property
    def total_paye(self):
        return sum((p.montant for p in self.paiements.all()), ZERO)

    @property
    def reste_a_payer(self):
        return self.total_ttc - self.total_paye

    @property
    def en_retard(self):
        return (self.status in (self.Status.EMISE, self.Status.PARTIELLE)
                and self.date_echeance < timezone.localdate())

    # ---------- règles métier ----------
    @property
    def est_modifiable(self):
        return self.status == self.Status.BROUILLON

    @property
    def peut_emettre(self):
        return self.status == self.Status.BROUILLON

    @property
    def peut_annuler(self):
        return self.status in (self.Status.BROUILLON, self.Status.EMISE)    # EMISE => aucun paiement

    @property
    def est_supprimable(self):
        return self.status in (self.Status.BROUILLON, self.Status.ANNULEE)

    @property
    def accepte_paiements(self):
        return self.status in (self.Status.EMISE, self.Status.PARTIELLE)

    @property
    def paiements_modifiables(self):
        return self.status in (self.Status.EMISE, self.Status.PARTIELLE, self.Status.PAYEE)

    @property
    def badge_class(self):
        return {"BROUILLON": "bg-secondary", "EMISE": "bg-primary", "PARTIELLE": "bg-warning text-dark",
                "PAYEE": "bg-success", "ANNULEE": "bg-danger"}.get(self.status, "bg-secondary")


class Paiement(models.Model):
    """Un paiement (total ou partiel) reçu sur une facture."""

    class Mode(models.TextChoices):
        VIREMENT = "VIREMENT", "Virement"
        CHEQUE = "CHEQUE", "Chèque"
        ESPECES = "ESPECES", "Espèces"
        CARTE = "CARTE", "Carte bancaire"

    facture = models.ForeignKey(Facture, on_delete=models.CASCADE, related_name="paiements")
    montant = models.DecimalField("Montant (TND)", max_digits=10, decimal_places=2,
                                  validators=[MinValueValidator(Decimal("0.01"))])
    date_paiement = models.DateField("Date du paiement", default=timezone.localdate)
    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.VIREMENT)
    reference = models.CharField("Référence (n° chèque, virement...)", max_length=100, blank=True)
    enregistre_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                       null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date_paiement", "id"]

    def __str__(self):
        return f"{self.facture.numero}: {self.montant} TND ({self.get_mode_display()})"