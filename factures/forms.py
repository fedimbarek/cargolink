from decimal import Decimal

from django import forms
from django.utils import timezone

from . import services
from .models import Facture, Paiement


def _bootstrap(form):
    for field in form.fields.values():
        field.widget.attrs["class"] = "form-select" if isinstance(field, forms.ChoiceField) else "form-control"


class FactureForm(forms.ModelForm):
    class Meta:
        model = Facture
        fields = ["montant_ht", "taux_tva", "date_echeance", "notes"]
        widgets = {
            "date_echeance": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrap(self)

    def clean_date_echeance(self):
        d = self.cleaned_data["date_echeance"]
        inchangee = self.instance.pk and d == self.instance.date_echeance
        if d < timezone.localdate() and not inchangee:
            raise forms.ValidationError("L'échéance ne peut pas être dans le passé.")
        return d


class FactureCreationForm(forms.Form):
    """Création d'une facture: le transporteur choisit une de ses missions acceptées non encore facturées."""
    proposition = forms.ModelChoiceField(queryset=None, label="Mission à facturer",
                                         empty_label="— Choisir une mission —")
    montant_ht = forms.DecimalField(label="Montant HT (TND) — vide = prix de la proposition", required=False,
                                    max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    taux_tva = forms.DecimalField(label="TVA (%)", max_digits=5, decimal_places=2,
                                  min_value=Decimal("0"), max_value=Decimal("100"))
    date_echeance = forms.DateField(label="Date d'échéance",
                                    widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    notes = forms.CharField(label="Notes", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["proposition"].queryset = services.propositions_a_facturer(user)
        self.fields["proposition"].label_from_instance = lambda p: (
            f"Demande #{p.demande_id} · {p.demande.origin} → {p.demande.destination} · {p.price} TND")
        _bootstrap(self)

    def clean_date_echeance(self):
        d = self.cleaned_data["date_echeance"]
        if d < timezone.localdate():
            raise forms.ValidationError("L'échéance ne peut pas être dans le passé.")
        return d


class PaiementForm(forms.ModelForm):
    class Meta:
        model = Paiement
        fields = ["montant", "date_paiement", "mode", "reference"]
        widgets = {"date_paiement": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrap(self)

    def clean_date_paiement(self):
        d = self.cleaned_data["date_paiement"]
        if d > timezone.localdate():
            raise forms.ValidationError("La date du paiement ne peut pas être dans le futur.")
        return d


class FactureFilterForm(forms.Form):
    status = forms.ChoiceField(required=False, label="Statut",
                               choices=[("", "Tous")] + list(Facture.Status.choices))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].widget.attrs["class"] = "form-select form-select-sm"

class BilanFilterForm(forms.Form):
    MOIS = [("", "Toute l'année")] + [
        (str(i), nom) for i, nom in enumerate(
            ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet",
             "Août", "Septembre", "Octobre", "Novembre", "Décembre"], 1)]

    annee = forms.IntegerField(label="Année", required=False, min_value=2000, max_value=2100)
    mois = forms.ChoiceField(label="Mois", required=False, choices=MOIS)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["annee"].widget.attrs["class"] = "form-control form-control-sm"
        self.fields["mois"].widget.attrs["class"] = "form-select form-select-sm"        