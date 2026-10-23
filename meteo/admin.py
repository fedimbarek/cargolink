from django.contrib import admin

from .models import AlerteMeteo, PrevisionMeteo


@admin.register(PrevisionMeteo)
class PrevisionMeteoAdmin(admin.ModelAdmin):
    list_display = ("demande", "point", "ville", "date_prevue", "resume", "risque", "maj_le")
    list_filter = ("point", "risque")


@admin.register(AlerteMeteo)
class AlerteMeteoAdmin(admin.ModelAdmin):
    list_display = ("message", "niveau", "lue", "created_at")
    list_filter = ("niveau", "lue")
