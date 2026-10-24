from django.db import models
from django.conf import settings


class Reclamation(models.Model):
    STATUT_CHOICES = [
        ('NOUVELLE', 'Nouvelle'),
        ('EN_COURS', 'En cours de traitement'),
        ('RESOLUE', 'Résolue'),
        ('FERMEE', 'Fermée'),
    ]
    PRIORITE_CHOICES = [
        ('BASSE', 'Basse'),
        ('MOYENNE', 'Moyenne'),
        ('HAUTE', 'Haute'),
        ('CRITIQUE', 'Critique'),
    ]

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reclamations',
        verbose_name="Créateur"
    )
    # ==== NOUVEAU CHAMP ====
    destinataire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reclamations_recues',
        verbose_name="Destinataire (transporteur concerné)",
        limit_choices_to={'role': 'TRANSPORTEUR'},
        help_text="Transporteur concerné par la réclamation (optionnel)"
    )

    sujet = models.CharField(max_length=200, verbose_name="Sujet")
    description = models.TextField(verbose_name="Description détaillée")
    statut = models.CharField(
        max_length=20, choices=STATUT_CHOICES,
        default='NOUVELLE', verbose_name="Statut"
    )
    priorite = models.CharField(
        max_length=10, choices=PRIORITE_CHOICES,
        default='MOYENNE', verbose_name="Priorité"
    )
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    date_mise_a_jour = models.DateTimeField(auto_now=True, verbose_name="Dernière mise à jour")
    piece_jointe = models.FileField(
        upload_to='reclamations/pieces_jointes/',
        blank=True, null=True, verbose_name="Pièce jointe"
    )

    class Meta:
        ordering = ['-date_creation']
        verbose_name = "Réclamation"
        verbose_name_plural = "Réclamations"
        permissions = [
            ("peut_traiter_reclamation", "Peut traiter les réclamations"),
        ]

    def __str__(self):
        return f"#{self.id} - {self.sujet} ({self.get_statut_display()})"