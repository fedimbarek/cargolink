from rest_framework import generics, serializers, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from . import services
from .models import EtapeSuivi, Notification, Reservation
from .views import reservations_de


class EtapeSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = EtapeSuivi
        fields = ["id", "type", "type_display", "commentaire", "localisation", "created_at"]


class ReservationSerializer(serializers.ModelSerializer):
    demande = serializers.IntegerField(source="proposition.demande_id", read_only=True)
    trajet = serializers.CharField(source="demande", read_only=True)
    transporteur = serializers.CharField(source="proposition.transporteur", read_only=True)
    prix = serializers.DecimalField(source="proposition.price", max_digits=10, decimal_places=2, read_only=True)
    etapes = EtapeSerializer(many=True, read_only=True)

    class Meta:
        model = Reservation
        fields = ["id", "proposition", "demande", "trajet", "transporteur", "prix", "status",
                  "created_at", "demarree_le", "livree_le", "etapes"]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "message", "lien", "lue", "created_at"]


class ReservationActionSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=services.ETAPES_INTERMEDIAIRES, required=False)
    commentaire = serializers.CharField(required=False, allow_blank=True, max_length=255)
    localisation = serializers.CharField(required=False, allow_blank=True, max_length=150)
    motif = serializers.CharField(required=False, allow_blank=True, max_length=255)


class ReservationListe(generics.ListAPIView):
    serializer_class = ReservationSerializer

    def get_queryset(self):
        return reservations_de(self.request.user).prefetch_related("etapes")


class ReservationDetail(generics.RetrieveAPIView):
    serializer_class = ReservationSerializer

    def get_queryset(self):
        return reservations_de(self.request.user).prefetch_related("etapes")


ACTIONS = {
    "demarrer": lambda r, d, u: services.demarrer(r, d.get("commentaire", ""), d.get("localisation", "")),
    "etape": lambda r, d, u: services.ajouter_etape(r, d.get("type"), d.get("commentaire", ""),
                                                    d.get("localisation", "")),
    "livrer": lambda r, d, u: services.livrer(r, d.get("commentaire", "")),
    "annuler": lambda r, d, u: services.annuler(r, u, d.get("motif", "")),
}


@api_view(["POST"])
def reservation_action(request, pk, action):
    r = reservations_de(request.user).filter(pk=pk).first()
    if r is None or action not in ACTIONS:
        return Response(status=status.HTTP_404_NOT_FOUND)
    est_transporteur = r.transporteur.user_id == request.user.id
    if not est_transporteur and not (action == "annuler" and r.pme.user_id == request.user.id):
        return Response({"detail": "Action réservée au transporteur."}, status=status.HTTP_403_FORBIDDEN)
    donnees = ReservationActionSerializer(data=request.data)
    if not donnees.is_valid():
        return Response(donnees.errors, status=status.HTTP_400_BAD_REQUEST)
    try:
        ACTIONS[action](r, donnees.validated_data, request.user)
    except services.ErreurReservation as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    r.refresh_from_db()
    return Response(ReservationSerializer(r).data)


class NotificationListe(generics.ListAPIView):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return self.request.user.notifications_suivi.all()
