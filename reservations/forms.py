from django import forms

from .models import Reservation


class ReservationContactForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = ["nom_contact", "email_contact", "nom_societe", "telephone"]

    def __init__(self, *args, proposition, **kwargs):
        super().__init__(*args, **kwargs)
        pme = proposition.demande.pme
        valeurs = {
            "nom_contact": pme.user.username,
            "email_contact": pme.user.email,
            "nom_societe": pme.company_name,
            "telephone": pme.phone,
        }
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"
            if not self.is_bound:
                field.initial = valeurs[name]
