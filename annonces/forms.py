from django import forms
from django.utils import timezone

from .models import DemandeTransport


class DemandeForm(forms.ModelForm):
    class Meta:
        model = DemandeTransport
        fields = ["origin", "destination", "pickup_date", "delivery_date",
                  "weight", "volume", "cargo_type", "description"]
        widgets = {
            "pickup_date": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "delivery_date": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"
        for name in ("pickup_date", "delivery_date"):
            self.fields[name].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]

    def clean(self):
        cleaned = super().clean()
        pickup, delivery = cleaned.get("pickup_date"), cleaned.get("delivery_date")
        origin, destination = cleaned.get("origin"), cleaned.get("destination")
        if pickup and pickup < timezone.now():
            self.add_error("pickup_date", "La date de chargement doit être dans le futur.")
        if pickup and delivery and delivery <= pickup:
            self.add_error("delivery_date", "La date de livraison doit être après la date de chargement.")
        if origin and destination and origin.strip().lower() == destination.strip().lower():
            self.add_error("destination", "L'origine et la destination doivent être différentes.")
        return cleaned


class DemandeFilterForm(forms.Form):
    TRI_CHOICES = [
        ("-created_at", "Plus récentes"),
        ("pickup_date", "Date de chargement"),
        ("-weight", "Poids décroissant"),
        ("weight", "Poids croissant"),
        ("distance_km", "Distance croissante"),
    ]

    origin = forms.CharField(required=False, label="Origine")
    destination = forms.CharField(required=False, label="Destination")
    cargo_type = forms.CharField(required=False, label="Marchandise")
    poids_min = forms.DecimalField(required=False, min_value=0, label="Poids min (kg)")
    poids_max = forms.DecimalField(required=False, min_value=0, label="Poids max (kg)")
    date_min = forms.DateField(required=False, label="Chargement à partir du",
                               widget=forms.DateInput(attrs={"type": "date"}))
    status = forms.ChoiceField(required=False, label="Statut",
                               choices=[("", "Tous")] + list(DemandeTransport.Status.choices))
    tri = forms.ChoiceField(required=False, label="Trier par", choices=TRI_CHOICES)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field, forms.ChoiceField):
                field.widget.attrs["class"] = "form-select form-select-sm"
            else:
                field.widget.attrs["class"] = "form-control form-control-sm"

    def clean(self):
        cleaned = super().clean()
        mini, maxi = cleaned.get("poids_min"), cleaned.get("poids_max")
        if mini is not None and maxi is not None and mini > maxi:
            raise forms.ValidationError("Le poids minimum dépasse le poids maximum.")
        return cleaned