from django.contrib import admin

from .models import EtapeSuivi, Notification, Reservation


class EtapeInline(admin.TabularInline):
    model = EtapeSuivi
    extra = 0


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("id", "proposition", "status", "created_at", "livree_le")
    list_filter = ("status",)
    inlines = [EtapeInline]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "message", "lue", "created_at")
    list_filter = ("lue",)
