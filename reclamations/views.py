from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Q
from .models import Reclamation
from .forms import ReclamationForm
from .services import predire_priorite


def _est_admin(user):
    """Admin = superuser, staff, ou rôle différent de PME/TRANSPORTEUR."""
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

        if _est_admin(user):
            return qs  # Admin voit tout
        if _est_pme(user):
            return qs  # PME voit tout (selon votre demande)
        if _est_transporteur(user):
            # Transporteur ne voit QUE les réclamations qui lui sont adressées
            # OU qu'il a lui-même créées
            return qs.filter(Q(destinataire=user) | Q(utilisateur=user))
        return qs.none()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['est_support'] = _est_admin(self.request.user)
        ctx['est_pme'] = _est_pme(self.request.user)
        ctx['est_transporteur'] = _est_transporteur(self.request.user)
        ctx['mode_toutes'] = _est_admin(self.request.user) or _est_pme(self.request.user)
        return ctx


class ReclamationCreateView(LoginRequiredMixin, CreateView):
    model = Reclamation
    form_class = ReclamationForm
    template_name = 'reclamations/form.html'
    success_url = reverse_lazy('reclamations:liste')

    def form_valid(self, form):
        form.instance.utilisateur = self.request.user
        try:
            suggestion = predire_priorite(form.cleaned_data.get('description', ''))
            messages.info(self.request, f"🤖 Priorité suggérée par l'IA : {suggestion}")
        except Exception:
            pass
        return super().form_valid(form)


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