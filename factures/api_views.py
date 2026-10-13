from rest_framework import status as http, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.response import Response

from users.permissions import IsTransporteur

from . import services
from .models import Facture, Paiement
from .serializers import FactureSerializer, PaiementSerializer


class LectureTousEcritureTransporteur(BasePermission):
    """Lecture: tout utilisateur connecté (le queryset filtre ce qu'il a le droit de voir).
    Écriture: uniquement un transporteur validé par l'admin."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return IsTransporteur().has_permission(request, view)


def _erreur(e):
    return ValidationError({"detail": str(e)})


class FactureViewSet(viewsets.ModelViewSet):
    """
    GET    /api/factures/?status=      liste (filtrable par statut)
    POST   /api/factures/              créer un brouillon  {proposition, date_echeance, [montant_ht, taux_tva, notes]}
    GET    /api/factures/{id}/         détail (avec paiements)
    PATCH  /api/factures/{id}/         modifier (brouillon seulement)
    DELETE /api/factures/{id}/         supprimer (brouillon ou annulée)
    POST   /api/factures/{id}/emettre/ | /annuler/
    """
    serializer_class = FactureSerializer
    permission_classes = [LectureTousEcritureTransporteur]

    def get_queryset(self):
        qs = services.factures_visibles(self.request.user)
        statut = self.request.query_params.get("status")
        if statut in Facture.Status.values:
            qs = qs.filter(status=statut)
        return qs

    def destroy(self, request, *args, **kwargs):
        try:
            services.supprimer_facture(self.get_object())
        except services.ErreurFacture as e:
            raise _erreur(e)
        return Response(status=http.HTTP_204_NO_CONTENT)

    def _transition(self, fonction):
        try:
            facture = fonction(self.get_object())
        except services.ErreurFacture as e:
            raise _erreur(e)
        return Response(self.get_serializer(facture).data)

    @action(detail=True, methods=["post"])
    def emettre(self, request, pk=None):
        return self._transition(services.emettre)

    @action(detail=True, methods=["post"])
    def annuler(self, request, pk=None):
        return self._transition(services.annuler)


class PaiementViewSet(viewsets.ModelViewSet):
    """
    GET    /api/factures/paiements/?facture=   liste
    POST   /api/factures/paiements/            {facture, montant, [date_paiement, mode, reference]}
    PATCH  /api/factures/paiements/{id}/       modifier
    DELETE /api/factures/paiements/{id}/       supprimer
    Le statut de la facture (EMISE / PARTIELLE / PAYEE) est recalculé à chaque opération.
    """
    serializer_class = PaiementSerializer
    permission_classes = [LectureTousEcritureTransporteur]

    def get_queryset(self):
        qs = (Paiement.objects.filter(facture__in=services.factures_visibles(self.request.user))
              .select_related("facture__proposition__transporteur", "enregistre_par"))
        facture_id = self.request.query_params.get("facture")
        if facture_id and facture_id.isdigit():
            qs = qs.filter(facture_id=int(facture_id))
        return qs

    def perform_create(self, serializer):
        serializer.save(enregistre_par=self.request.user)

    def destroy(self, request, *args, **kwargs):
        try:
            services.supprimer_paiement(self.get_object())
        except services.ErreurFacture as e:
            raise _erreur(e)
        return Response(status=http.HTTP_204_NO_CONTENT)