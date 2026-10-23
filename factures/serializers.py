from django.utils import timezone
from rest_framework import serializers

from . import services
from .models import Facture, Paiement


class PaiementSerializer(serializers.ModelSerializer):
    mode_display = serializers.CharField(source="get_mode_display", read_only=True)
    enregistre_par_email = serializers.SerializerMethodField()

    class Meta:
        model = Paiement
        fields = ["id", "facture", "montant", "date_paiement", "mode", "mode_display",
                  "reference", "enregistre_par_email", "created_at"]
        read_only_fields = ["created_at"]

    def get_enregistre_par_email(self, obj):
        return obj.enregistre_par.email if obj.enregistre_par else None

    def validate_facture(self, facture):
        if self.instance is not None and facture != self.instance.facture:
            raise serializers.ValidationError("On ne peut pas déplacer un paiement vers une autre facture.")
        if facture.transporteur.user_id != self.context["request"].user.id:
            raise serializers.ValidationError("Cette facture n'est pas la vôtre.")
        return facture

    def validate_date_paiement(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError("La date du paiement ne peut pas être dans le futur.")
        return value

    def create(self, validated_data):
        try:
            return services.enregistrer_paiement(
                validated_data["facture"], validated_data["montant"],
                validated_data.get("date_paiement"), validated_data.get("mode", Paiement.Mode.VIREMENT),
                validated_data.get("reference", ""), validated_data.get("enregistre_par"))
        except services.ErreurFacture as e:
            raise serializers.ValidationError(str(e))

    def update(self, instance, validated_data):
        validated_data.pop("facture", None)
        try:
            return services.modifier_paiement(instance, **validated_data)
        except services.ErreurFacture as e:
            raise serializers.ValidationError(str(e))


class FactureSerializer(serializers.ModelSerializer):
    """`proposition` n'est demandée qu'à la création. Une facture n'est modifiable qu'en brouillon;
    ensuite le statut évolue via les actions emettre/annuler et les paiements."""
    numero = serializers.CharField(read_only=True)
    demande = serializers.IntegerField(source="proposition.demande_id", read_only=True)
    pme = serializers.CharField(source="pme.company_name", read_only=True)
    transporteur = serializers.CharField(source="transporteur.company_name", read_only=True)
    trajet = serializers.CharField(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    montant_tva = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_ttc = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_paye = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    reste_a_payer = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    en_retard = serializers.BooleanField(read_only=True)
    paiements = PaiementSerializer(many=True, read_only=True)

    class Meta:
        model = Facture
        fields = ["id", "numero", "proposition", "demande", "pme", "transporteur", "trajet",
                  "montant_ht", "taux_tva", "montant_tva", "total_ttc", "total_paye", "reste_a_payer",
                  "status", "status_display", "date_echeance", "en_retard", "notes",
                  "created_at", "emise_le", "paiements"]
        read_only_fields = ["status", "created_at", "emise_le"]
        extra_kwargs = {"montant_ht": {"required": False}}     # par défaut: prix de la proposition acceptée

    def validate_proposition(self, proposition):
        if self.instance is not None:
            if proposition != self.instance.proposition:
                raise serializers.ValidationError("On ne peut pas changer la proposition d'une facture.")
            return proposition
        if proposition.transporteur.user_id != self.context["request"].user.id:
            raise serializers.ValidationError("Cette proposition n'est pas la vôtre.")
        if not services.est_facturable(proposition):
            raise serializers.ValidationError("Cette mission n'est pas facturable (la proposition doit être acceptée).")
        return proposition

    def validate_date_echeance(self, value):
        inchangee = self.instance is not None and value == self.instance.date_echeance
        if value < timezone.localdate() and not inchangee:
            raise serializers.ValidationError("L'échéance ne peut pas être dans le passé.")
        return value

    def validate(self, attrs):
        if self.instance is not None and not self.instance.est_modifiable:
            raise serializers.ValidationError("Seule une facture en brouillon est modifiable.")
        return attrs

    def create(self, validated_data):
        try:
            return services.creer_facture(
                validated_data["proposition"], validated_data["date_echeance"],
                validated_data.get("taux_tva", services.TVA_DEFAUT), validated_data.get("notes", ""),
                validated_data.get("montant_ht"))
        except services.ErreurFacture as e:
            raise serializers.ValidationError({"proposition": str(e)})