from django.contrib import admin
from .models import Reclamation
from .MLReclamations import predire_priorite


@admin.register(Reclamation)
class ReclamationAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'sujet', 'utilisateur', 'destinataire',
        'statut', 'priorite', 'priorite_ia', 'date_creation',
    )
    list_filter = ('statut', 'priorite', 'date_creation')
    search_fields = ('sujet', 'description', 'utilisateur__username', 'destinataire__username')
    readonly_fields = ('date_creation', 'date_mise_a_jour')
    ordering = ('-date_creation',)

    def priorite_ia(self, obj):
        if not obj.description:
            return "—"
        try:
            pred = predire_priorite(obj.description)
            couleurs = {'BASSE': '#6c757d', 'MOYENNE': '#0d6efd', 'HAUTE': '#dc3545'}
            return f'<span style="color:{couleurs.get(pred, "#212529")};font-weight:bold">{pred}</span>'
        except Exception:
            return "Erreur"
    priorite_ia.short_description = "🤖 Priorité IA"
    priorite_ia.allow_tags = True