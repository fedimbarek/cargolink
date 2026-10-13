from django.urls import path

from . import views

app_name = "propositions"

urlpatterns = [
    path("vehicules/", views.vehicules, name="vehicules"),
    path("vehicules/<int:pk>/toggle/", views.vehicule_toggle, name="vehicule_toggle"),
    path("vehicules/<int:pk>/supprimer/", views.vehicule_supprimer, name="vehicule_supprimer"),
    path("proposer/<int:demande_id>/", views.proposer, name="proposer"),
    path("mes-propositions/", views.mes_propositions, name="mes_propositions"),
    path("retirer/<int:pk>/", views.retirer, name="retirer"),
    path("matching/", views.matching, name="matching"),
    path("recues/", views.propositions_recues, name="recues"),
    path("comparer/<int:demande_id>/", views.comparer_propositions, name="comparer"),
    path("accepter/<int:pk>/", views.accepter, name="accepter"),
]