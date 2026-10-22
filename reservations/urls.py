from django.urls import path

from . import api_views

urlpatterns = [
    path("", api_views.ReservationListe.as_view(), name="api_reservations"),
    path("<int:pk>/", api_views.ReservationDetail.as_view(), name="api_reservation"),
    path("<int:pk>/<str:action>/", api_views.reservation_action, name="api_reservation_action"),
    path("notifications/", api_views.NotificationListe.as_view(), name="api_notifications"),
]
