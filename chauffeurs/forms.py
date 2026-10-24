from django import forms

from .models import Chauffeur, Permis
from django.utils import timezone

from propositions.models import Proposition
from .models import Affectation


class ChauffeurForm(forms.ModelForm):
    class Meta:
        model = Chauffeur
        fields = ["nom", "prenom", "telephone", "disponible"]

        labels = {
            "nom": "Nom",
            "prenom": "Prénom",
            "telephone": "Téléphone",
            "disponible": "Disponible",
        }

        widgets = {
            "nom": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "prenom": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "telephone": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "disponible": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }


class PermisForm(forms.ModelForm):
    class Meta:
        model = Permis
        fields = ["numero", "categorie", "date_expiration"]

        labels = {
            "numero": "Numéro du permis",
            "categorie": "Catégorie",
            "date_expiration": "Date d’expiration",
        }

        widgets = {
            "numero": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "categorie": forms.Select(
                attrs={"class": "form-select"}
            ),
            "date_expiration": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": "form-control",
                    "type": "date",
                },
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date_expiration"].input_formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
        ]

class AffectationForm(forms.ModelForm):
    class Meta:
        model = Affectation
        fields = ["proposition", "chauffeur"]

        labels = {
            "proposition": "Mission acceptée",
            "chauffeur": "Chauffeur",
        }

        widgets = {
            "proposition": forms.Select(
                attrs={"class": "form-select"}
            ),
            "chauffeur": forms.Select(
                attrs={"class": "form-select"}
            ),
        }

    def __init__(self, *args, transporteur, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["proposition"].queryset = (
            Proposition.objects.filter(
                transporteur=transporteur,
                status=Proposition.Status.ACCEPTED,
                affectation__isnull=True,
            )
        )

        self.fields["chauffeur"].queryset = (
            Chauffeur.objects.filter(
                transporteur=transporteur,
                disponible=True,
                permis__date_expiration__gte=timezone.localdate(),
            ).order_by("nom", "prenom")
        )