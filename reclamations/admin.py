from django.contrib import admin
from .models import Reclamation
from .services import predire_priorite
from django.utils.translation import gettext_lazy as _

class PrioriteIAFilter(admin.SimpleListFilter):
    title = _('Priorité suggérée par IA')
    parameter_name = 'priorite_ia'

    def lookups(self, request, model_admin):
        return (
            ('BASSE', _('Basse')),
            ('MOYENNE', _('Moyenne')),
            ('HAUTE', _('Haute')),
        )

    def queryset(self, request, queryset):
        if self.value():
            ids = [
                r.id for r in queryset
                if predire_priorite(r.description or '') == self.value()
            ]
            return queryset.filter(id__in=ids)
        return queryset

@admin.register(Reclamation)
class ReclamationAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'sujet', 'utilisateur', 'statut',
        'priorite', 'priorite_ia', 'date_creation',
    )
    list_filter = ('statut', 'priorite', 'date_creation', PrioriteIAFilter)
    search_fields = ('sujet', 'description', 'utilisateur__username')
    readonly_fields = ('date_creation', 'date_mise_a_jour', 'priorite_ia_detail')
    ordering = ('-date_creation',)
    
    fieldsets = (
        ('Informations', {
            'fields': ('utilisateur', 'sujet', 'description', 'piece_jointe')
        }),
        ('Suivi', {
            'fields': ('statut', 'priorite')
        }),
        ('🤖 Analyse IA', {
            'fields': ('priorite_ia_detail',),
            'classes': ('collapse',),
        }),
        ('Dates', {
            'fields': ('date_creation', 'date_mise_a_jour')
        }),
    )

    def priorite_ia(self, obj):
        """Colonne 'Priorité IA' dans la liste."""
        if not obj.description:
            return "—"
        try:
            pred = predire_priorite(obj.description)
            couleurs = {
                'BASSE': '#6c757d',
                'MOYENNE': '#0d6efd',
                'HAUTE': '#dc3545',
            }
            color = couleurs.get(pred, '#212529')
            return f'<span style="color:{color};font-weight:bold">{pred}</span>'
        except Exception as e:
            return f'<span style="color:red">Erreur</span>'
    priorite_ia.short_description = "🤖 Priorité IA"
    priorite_ia.allow_tags = True

    def priorite_ia_detail(self, obj):
        """Bloc détaillé dans la fiche (probabilités par classe)."""
        if not obj.description:
            return "Pas de description à analyser."
        try:
            from .services import predire_priorite_avec_proba
            probas = predire_priorite_avec_proba(obj.description)
            pred = max(probas, key=probas.get)
            lignes = [f"<p><strong>Prédiction :</strong> {pred}</p>", "<ul>"]
            for classe in ['BASSE', 'MOYENNE', 'HAUTE']:
                p = probas.get(classe, 0)
                pct = round(p * 100, 1)
                lignes.append(
                    f"<li><strong>{classe}</strong> : {pct}%</li>"
                )
            lignes.append("</ul>")
            return "".join(lignes)
        except Exception as e:
            return f"Erreur IA : {e}"
    priorite_ia_detail.short_description = "Détails de la prédiction IA"
    priorite_ia_detail.allow_tags = True