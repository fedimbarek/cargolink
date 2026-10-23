from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

from .models import PME, Transporteur, User


class BootstrapMixin:
    """Ajoute la classe CSS Bootstrap à tous les champs."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class LoginForm(BootstrapMixin, AuthenticationForm):
    username = forms.EmailField(label="Email")     # on se connecte avec l'email


class RegisterForm(BootstrapMixin, forms.Form):
    ROLE_CHOICES = [(User.Role.PME, "PME"), (User.Role.TRANSPORTEUR, "Transporteur")]

    username = forms.CharField(max_length=150, label="Nom d'utilisateur")
    email = forms.EmailField(label="Email")
    password = forms.CharField(widget=forms.PasswordInput, label="Mot de passe")
    role = forms.ChoiceField(choices=ROLE_CHOICES, label="Je suis")
    company_name = forms.CharField(max_length=150, label="Nom de la société")
    phone = forms.CharField(max_length=20, required=False, label="Téléphone")

    def clean_username(self):
        value = self.cleaned_data["username"]
        if User.objects.filter(username__iexact=value).exists():
            raise forms.ValidationError("Ce nom d'utilisateur existe déjà.")
        return value

    def clean_email(self):
        value = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=value).exists():
            raise forms.ValidationError("Cet email est déjà utilisé.")
        return value

    def clean_password(self):
        value = self.cleaned_data["password"]
        validate_password(value)          # règles de sécurité de Django
        return value

    @transaction.atomic
    def save(self):
        d = self.cleaned_data
        user = User(username=d["username"], email=d["email"], role=d["role"])
        user.set_password(d["password"])
        if d["role"] == User.Role.TRANSPORTEUR:
            user.status = User.Status.PENDING       # l'admin doit valider
        user.save()
        if d["role"] == User.Role.PME:
            PME.objects.create(user=user, company_name=d["company_name"], phone=d["phone"])
        else:
            Transporteur.objects.create(user=user, company_name=d["company_name"], phone=d["phone"])
        return user