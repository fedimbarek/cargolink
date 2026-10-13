from django.contrib import admin

from .models import Proposition, Vehicle


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("registration_number", "transporteur", "type", "capacity_weight", "availability")
    list_filter = ("type", "availability")


@admin.register(Proposition)
class PropositionAdmin(admin.ModelAdmin):
    list_display = ("id", "demande", "transporteur", "price", "estimated_duration", "status")
    list_filter = ("status",)