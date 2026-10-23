from django import forms

from .models import Proposition, Vehicle


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ["registration_number", "type", "capacity_weight", "capacity_volume", "availability"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field, forms.ChoiceField):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"


class PropositionForm(forms.ModelForm):
    class Meta:
        model = Proposition
        fields = ["vehicle", "price", "estimated_duration", "message"]
        widgets = {"message": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, transporteur=None, demande=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.demande = demande
        self.transporteur = transporteur
        # seulement les véhicules disponibles de ce transporteur
        self.fields["vehicle"].queryset = Vehicle.objects.filter(transporteur=transporteur, availability=True)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field, forms.ModelChoiceField) else "form-control"

    def clean_vehicle(self):
        vehicle = self.cleaned_data["vehicle"]
        if self.demande and not vehicle.peut_transporter(self.demande):
            raise forms.ValidationError(
                "Ce véhicule n'a pas la capacité nécessaire (poids/volume) pour cette demande.")
        return vehicle