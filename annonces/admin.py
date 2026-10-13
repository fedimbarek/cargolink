from django.contrib import admin

from .models import DemandeTransport


@admin.register(DemandeTransport)
class DemandeTransportAdmin(admin.ModelAdmin):
    list_display = ("id", "origin", "destination", "pme", "weight", "distance_km", "pickup_date", "status")
    list_filter = ("status", "cargo_type")
    search_fields = ("origin", "destination", "pme__company_name")