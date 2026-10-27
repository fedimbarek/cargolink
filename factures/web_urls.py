from django.urls import path

from . import views

app_name = "factures"

urlpatterns = [
    path("", views.liste, name="liste"),
    path("bilan/", views.bilan, name="bilan"), 
    path("nouvelle/", views.nouvelle, name="nouvelle"),
    path("creer/<int:proposition_id>/", views.creer, name="creer"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/modifier/", views.modifier, name="modifier"),
    path("<int:pk>/emettre/", views.emettre, name="emettre"),
    path("<int:pk>/annuler/", views.annuler, name="annuler"),
    path("<int:pk>/supprimer/", views.supprimer, name="supprimer"),
    path("<int:pk>/paiements/ajouter/", views.paiement_ajouter, name="paiement_ajouter"),
    path("paiements/<int:pk>/modifier/", views.paiement_modifier, name="paiement_modifier"),
    path("paiements/<int:pk>/supprimer/", views.paiement_supprimer, name="paiement_supprimer"),
]