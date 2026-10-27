from django.urls import path

from . import views

app_name = "evaluations"

urlpatterns = [
    path("reservation/<int:pk>/", views.evaluer, name="evaluer"),
    path("transporteur/<int:pk>/", views.avis, name="avis"),
]