from rest_framework.routers import SimpleRouter

from .api_views import FactureViewSet, PaiementViewSet

router = SimpleRouter()
router.register("paiements", PaiementViewSet, basename="paiement")   # avant "" pour ne pas être pris pour {id}
router.register("", FactureViewSet, basename="facture")

urlpatterns = router.urls