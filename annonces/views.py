from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from users.decorators import role_required
from users.models import PME

from .forms import DemandeFilterForm, DemandeForm
from .models import DemandeTransport
from .services import calculer_trajet

Status = DemandeTransport.Status


def _appliquer_trajet(demande):
    """Appelle les API externes; si elles sont en panne, on prévient mais on enregistre quand même."""
    trajet = calculer_trajet(demande.origin, demande.destination)
    if trajet:
        for champ, valeur in trajet.items():
            setattr(demande, champ, valeur)
        return True
    demande.distance_km = demande.duration_hours = None
    return False


@login_required
def liste(request):
    user = request.user
    qs = DemandeTransport.objects.select_related("pme").annotate(nb_propositions=Count("propositions"))
    if user.role == "PME":
        qs = qs.filter(pme__user=user)
    elif user.role == "TRANSPORTEUR":
        qs = qs.filter(status=Status.OPEN)

    form = DemandeFilterForm(request.GET or None)
    if user.role == "TRANSPORTEUR":
        del form.fields["status"]
    ordre = "-created_at"
    if form.is_bound and form.is_valid():
        c = form.cleaned_data
        if c.get("origin"):
            qs = qs.filter(origin__icontains=c["origin"])
        if c.get("destination"):
            qs = qs.filter(destination__icontains=c["destination"])
        if c.get("cargo_type"):
            qs = qs.filter(cargo_type__icontains=c["cargo_type"])
        if c.get("poids_min") is not None:
            qs = qs.filter(weight__gte=c["poids_min"])
        if c.get("poids_max") is not None:
            qs = qs.filter(weight__lte=c["poids_max"])
        if c.get("date_min"):
            qs = qs.filter(pickup_date__date__gte=c["date_min"])
        if c.get("status"):
            qs = qs.filter(status=c["status"])
        ordre = c.get("tri") or ordre

    stats = None
    if user.role == "PME":                       # tableau de bord statistique de la PME
        mes = DemandeTransport.objects.filter(pme__user=user)
        stats = mes.aggregate(total=Count("id"), poids=Sum("weight"), distance_moy=Avg("distance_km"))
        par_statut = {r["status"]: r["n"] for r in mes.values("status").annotate(n=Count("id"))}
        stats["ouvertes"] = par_statut.get(Status.OPEN, 0)
        stats["attribuees"] = par_statut.get(Status.ASSIGNED, 0)

    return render(request, "annonces/liste.html",
                  {"demandes": qs.order_by(ordre), "form": form, "stats": stats})


@role_required("PME")
def creer(request):
    pme = get_object_or_404(PME, user=request.user)
    form = DemandeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        demande = form.save(commit=False)
        demande.pme = pme
        if not _appliquer_trajet(demande):
            messages.warning(request, "Demande enregistrée, mais la distance n'a pas pu être calculée (API externe indisponible ou ville introuvable).")
        else:
            messages.success(request, f"Demande publiée. Distance estimée: {demande.distance_km} km.")
        demande.save()
        return redirect("annonces:detail", pk=demande.pk)
    return render(request, "annonces/form.html", {"form": form, "titre": "Nouvelle demande de transport"})


@login_required
def detail(request, pk):
    demande = get_object_or_404(DemandeTransport.objects.select_related("pme"), pk=pk)
    user = request.user
    est_proprietaire = demande.pme.user_id == user.id
    ma_proposition = None
    if user.role == "PME" and not est_proprietaire:
        raise PermissionDenied
    if user.role == "TRANSPORTEUR":
        ma_proposition = demande.propositions.filter(
            transporteur__user=user, status__in=["PENDING", "ACCEPTED"]).first()
        if demande.status != Status.OPEN and not demande.propositions.filter(transporteur__user=user).exists():
            raise PermissionDenied
    t = getattr(user, "transporteur", None)
    peut_proposer = bool(t and t.verified and demande.status == Status.OPEN and not ma_proposition)
    return render(request, "annonces/detail.html", {
        "d": demande, "est_proprietaire": est_proprietaire, "ma_proposition": ma_proposition,
        "peut_proposer": peut_proposer,
        "nb_propositions": demande.propositions.filter(status__in=["PENDING", "ACCEPTED"]).count(),
    })


@role_required("PME")
def modifier(request, pk):
    demande = get_object_or_404(DemandeTransport, pk=pk, pme__user=request.user)
    if not demande.est_modifiable:
        messages.error(request, "Cette demande ne peut plus être modifiée (déjà des propositions ou plus ouverte).")
        return redirect("annonces:detail", pk=pk)
    form = DemandeForm(request.POST or None, instance=demande)
    if request.method == "POST" and form.is_valid():
        demande = form.save(commit=False)
        if {"origin", "destination"} & set(form.changed_data):
            _appliquer_trajet(demande)           # recalcul seulement si le trajet a changé
        demande.save()
        messages.success(request, "Demande modifiée.")
        return redirect("annonces:detail", pk=pk)
    return render(request, "annonces/form.html", {"form": form, "titre": "Modifier la demande"})


@role_required("PME")
@require_POST
def annuler(request, pk):
    demande = get_object_or_404(DemandeTransport, pk=pk, pme__user=request.user)
    if not demande.peut_etre_annulee:
        messages.error(request, "Cette demande ne peut plus être annulée.")
    else:
        demande.annuler()
        messages.success(request, "Demande annulée. Les propositions en cours ont été refusées.")
    return redirect("annonces:detail", pk=pk)