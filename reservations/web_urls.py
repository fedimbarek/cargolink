from django.urls import path

from . import views

app_name = "reservations"

urlpatterns = [
    path("", views.liste, name="liste"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/demarrer/", views.demarrer, name="demarrer"),
    path("<int:pk>/etape/", views.etape, name="etape"),
    path("<int:pk>/livrer/", views.livrer, name="livrer"),
    path("<int:pk>/annuler/", views.annuler, name="annuler"),
    path("notifications/", views.notifications, name="notifications"),
    path("notifications/<int:pk>/", views.notification_ouvrir, name="notification_ouvrir"),
    path("notifications/tout-lire/", views.notifications_tout_lire, name="notifications_tout_lire"),
]
