from django.urls import path

from . import views
from .vue_recommandation import recommandation

app_name = "chauffeurs"

urlpatterns = [
    path("", views.liste, name="liste"),
    path("recommandation/", recommandation, name="recommandation"),
    path("ajouter/", views.ajouter, name="ajouter"),
    path("<int:pk>/modifier/", views.modifier, name="modifier"),
    path("<int:pk>/supprimer/", views.supprimer, name="supprimer"),
        path("affecter/", views.affecter, name="affecter"),
]