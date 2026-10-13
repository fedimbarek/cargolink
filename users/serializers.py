from django.db import IntegrityError, transaction
from rest_framework import serializers

from .models import PME, Transporteur, User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(choices=[User.Role.PME, User.Role.TRANSPORTEUR])
    company_name = serializers.CharField(write_only=True)
    phone = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "role", "company_name", "phone"]

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Cet email est déjà utilisé.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        company_name = validated_data.pop("company_name")
        phone = validated_data.pop("phone", "")
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)            # hash du mot de passe
        if user.role == User.Role.TRANSPORTEUR:
            user.status = User.Status.PENDING  # l'admin doit valider
        try:
            user.save()
        except IntegrityError:
            raise serializers.ValidationError({"email": "Cet email est déjà utilisé."})
        if user.role == User.Role.PME:
            PME.objects.create(user=user, company_name=company_name, phone=phone)
        else:
            Transporteur.objects.create(user=user, company_name=company_name, phone=phone)
        return user


class PMESerializer(serializers.ModelSerializer):
    class Meta:
        model = PME
        fields = ["company_name", "registration_number", "address", "phone"]


class TransporteurSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transporteur
        fields = ["company_name", "license_number", "phone", "rating", "verified"]
        read_only_fields = ["rating", "verified"]


class MeSerializer(serializers.ModelSerializer):
    pme = PMESerializer(required=False)
    transporteur = TransporteurSerializer(required=False)

    class Meta:
        model = User
        fields = ["id", "username", "email", "role", "status", "pme", "transporteur"]
        read_only_fields = ["email", "role", "status"]

    def update(self, instance, validated_data):
        pme_data = validated_data.pop("pme", None)
        transp_data = validated_data.pop("transporteur", None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()
        if pme_data and hasattr(instance, "pme"):
            for k, v in pme_data.items():
                setattr(instance.pme, k, v)
            instance.pme.save()
        if transp_data and hasattr(instance, "transporteur"):
            for k, v in transp_data.items():
                setattr(instance.transporteur, k, v)
            instance.transporteur.save()
        return instance