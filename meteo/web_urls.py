from django.urls import path

from . import views

app_name = "meteo"

urlpatterns = [
    path("alertes/", views.alertes, name="alertes"),
    path("alertes/lues/", views.alertes_lues, name="alertes_lues"),
    path("alertes/actualiser/", views.alertes_actualiser, name="alertes_actualiser"),
    path("demande/<int:demande_id>/", views.detail, name="detail"),
    path("demande/<int:demande_id>/actualiser/", views.actualiser, name="actualiser"),
]