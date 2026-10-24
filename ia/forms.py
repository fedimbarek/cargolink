from django import forms


class EstimationForm(forms.Form):
    origin = forms.CharField(max_length=150)
    destination = forms.CharField(max_length=150)
    weight = forms.DecimalField(min_value=0.01, max_digits=10, decimal_places=2)
    volume = forms.DecimalField(min_value=0, max_digits=10, decimal_places=2, required=False)
    cargo_type = forms.CharField(max_length=100, required=False)
    urgent = forms.BooleanField(required=False)

    def clean(self):
        c = super().clean()
        o, d = c.get("origin"), c.get("destination")
        if o and d and o.strip().lower() == d.strip().lower():
            raise forms.ValidationError("L'origine et la destination doivent être différentes.")
        return c
