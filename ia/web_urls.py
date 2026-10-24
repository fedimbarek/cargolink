from django.urls import path

from . import views

app_name = "ia"

urlpatterns = [
    path("estimer/", views.estimer, name="estimer"),
    path("tache/<str:task_id>/", views.tache, name="tache"),
    path("modele/", views.modele, name="modele"),
]
