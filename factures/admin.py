from django.contrib import admin

from .models import Facture, Paiement


class PaiementInline(admin.TabularInline):
    model = Paiement
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Facture)
class FactureAdmin(admin.ModelAdmin):
    list_display = ("id", "numero", "proposition", "montant_ht", "taux_tva", "status", "date_echeance")
    list_filter = ("status",)
    inlines = [PaiementInline]


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = ("facture", "montant", "mode", "date_paiement")
    list_filter = ("mode",)