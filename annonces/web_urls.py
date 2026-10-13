from django.urls import path

from . import views

app_name = "annonces"

urlpatterns = [
    path("", views.liste, name="liste"),
    path("nouvelle/", views.creer, name="creer"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/modifier/", views.modifier, name="modifier"),
    path("<int:pk>/annuler/", views.annuler, name="annuler"),
]