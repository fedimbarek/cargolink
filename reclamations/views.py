import json
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .models import Reclamation
from .forms import ReclamationForm
from .MLReclamations import (
    predire_priorite,
    predire_priorite_avec_proba,
    suggerer_et_appliquer,
)


def _est_admin(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return hasattr(user, 'role') and user.role not in ['PME', 'TRANSPORTEUR']


def _est_pme(user):
    return getattr(user, 'role', None) == 'PME'


def _est_transporteur(user):
    return getattr(user, 'role', None) == 'TRANSPORTEUR'


class ReclamationListView(LoginRequiredMixin, ListView):
    model = Reclamation
    template_name = 'reclamations/liste.html'
    context_object_name = 'reclamations'

    def get_queryset(self):
        qs = Reclamation.objects.select_related('utilisateur', 'destinataire').all()
        user = self.request.user
        if _est_admin(user) or _est_pme(user):
            return qs
        if _est_transporteur(user):
            return qs.filter(Q(destinataire=user) | Q(utilisateur=user))
        return qs.none()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['est_support'] = _est_admin(self.request.user)
        ctx['est_pme'] = _est_pme(self.request.user)
        ctx['est_transporteur'] = _est_transporteur(self.request.user)
        ctx['mode_toutes'] = _est_admin(self.request.user) or _est_pme(self.request.user)
        # Récupère la suggestion IA laissée par la création, puis la consomme
        ctx['ai_suggestion'] = self.request.session.pop('ai_suggestion', None)
        return ctx


class ReclamationCreateView(LoginRequiredMixin, CreateView):
    model = Reclamation
    form_class = ReclamationForm
    template_name = 'reclamations/form.html'
    success_url = reverse_lazy('reclamations:liste')

    def form_valid(self, form):
        form.instance.utilisateur = self.request.user
        # 🤖 IA : calcule la priorité et l'APPLIQUE (modifie form.instance.priorite)
        try:
            resultat = suggerer_et_appliquer(form.instance)
            ai_data = {
                'priorite': resultat['priorite'],
                'probabilites': resultat['probabilites'],
                'sujet': form.instance.sujet,
                'reclamation_id': None,  # rempli après save
                'erreur': None,
            }
        except Exception as e:
            ai_data = {
                'priorite': form.instance.priorite,
                'probabilites': {},
                'sujet': form.instance.sujet,
                'reclamation_id': None,
                'erreur': str(e),
            }
        response = super().form_valid(form)  # ← sauvegarde la réclamation
        ai_data['reclamation_id'] = form.instance.pk
        self.request.session['ai_suggestion'] = ai_data
        return response


class ReclamationDetailView(LoginRequiredMixin, DetailView):
    model = Reclamation
    template_name = 'reclamations/detail.html'
    context_object_name = 'reclamation'

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if _est_admin(user) or _est_pme(user):
            return qs
        if _est_transporteur(user):
            return qs.filter(Q(destinataire=user) | Q(utilisateur=user))
        return qs.none()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['est_support'] = _est_admin(self.request.user)
        return ctx


class ReclamationUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Reclamation
    form_class = ReclamationForm
    template_name = 'reclamations/form.html'
    permission_required = 'reclamations.change_reclamation'
    raise_exception = True
    success_url = reverse_lazy('reclamations:liste')


class ReclamationDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Reclamation
    template_name = 'reclamations/confirm_delete.html'
    permission_required = 'reclamations.delete_reclamation'
    raise_exception = True
    success_url = reverse_lazy('reclamations:liste')


@login_required
@require_POST
def suggerer_ia_api(request):
    """Endpoint AJAX : prédit la priorité sans sauvegarder."""
    try:
        data = json.loads(request.body)
        description = data.get('description', '').strip()
        if not description:
            return JsonResponse({'error': 'Description vide'}, status=400)
        priorite = predire_priorite(description)
        probabilites = predire_priorite_avec_proba(description)
        return JsonResponse({'priorite': priorite, 'probabilites': probabilites})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)