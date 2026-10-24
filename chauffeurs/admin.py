from django.contrib import admin

from .models import Chauffeur, Permis


@admin.register(Chauffeur)
class ChauffeurAdmin(admin.ModelAdmin):
    list_display = (
        "prenom",
        "nom",
        "telephone",
        "transporteur",
        "disponible",
    )
    search_fields = ("nom", "prenom", "telephone")
    list_filter = ("disponible",)


@admin.register(Permis)
class PermisAdmin(admin.ModelAdmin):
    list_display = (
        "numero",
        "chauffeur",
        "categorie",
        "date_expiration",
        "est_expire",
    )
    search_fields = (
        "numero",
        "chauffeur__nom",
        "chauffeur__prenom",
    )
    list_filter = ("categorie",)

    @admin.display(boolean=True, description="Expiré")
    def est_expire(self, obj):
        return obj.est_expire