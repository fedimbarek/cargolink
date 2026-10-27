from django.urls import path

from . import api_views

urlpatterns = [
    path("reservation/<int:pk>/", api_views.evaluer_reservation, name="api_evaluer"),
]