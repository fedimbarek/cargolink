from django import forms
from .models import Reclamation


class ReclamationForm(forms.ModelForm):
    class Meta:
        model = Reclamation
        fields = ['sujet', 'description', 'priorite', 'destinataire', 'piece_jointe']
        widgets = {
            'sujet': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Décrivez brièvement le problème',
                'aria-label': 'Sujet de la réclamation',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Expliquez en détail...',
                'aria-describedby': 'description-help',
            }),
            'priorite': forms.Select(attrs={
                'class': 'form-select',
                'aria-label': 'Niveau de priorité',
            }),
            'destinataire': forms.Select(attrs={
                'class': 'form-select',
                'aria-label': 'Transporteur concerné',
            }),
            'piece_jointe': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'aria-label': 'Pièce jointe',
            }),
        }
        labels = {
            'sujet': 'Sujet',
            'description': 'Description',
            'priorite': 'Priorité',
            'destinataire': 'Transporteur concerné',
            'piece_jointe': 'Pièce jointe (optionnel)',
        }
        help_texts = {
            'destinataire': "Laissez vide si la réclamation ne concerne pas un transporteur précis.",
        }