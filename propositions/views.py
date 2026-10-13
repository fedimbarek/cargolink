from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from annonces.models import DemandeTransport
from users.decorators import role_required

from .forms import PropositionForm, VehicleForm
from .models import Proposition, Vehicle
from .services import ErreurMetier, accepter_proposition, comparer, demandes_compatibles


# ---------------------------------------------------------------- véhicules
@role_required("TRANSPORTEUR")
def vehicules(request):
    transporteur = request.user.transporteur
    form = VehicleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        vehicule = form.save(commit=False)
        vehicule.transporteur = transporteur
        vehicule.save()
        messages.success(request, "Véhicule ajouté.")
        return redirect("propositions:vehicules")
    return render(request, "propositions/vehicules.html", {
        "form": form, "vehicules": transporteur.vehicles.all().order_by("registration_number")})


@role_required("TRANSPORTEUR")
@require_POST
def vehicule_toggle(request, pk):
    v = get_object_or_404(Vehicle, pk=pk, transporteur__user=request.user)
    v.availability = not v.availability
    v.save(update_fields=["availability"])
    return redirect("propositions:vehicules")


@role_required("TRANSPORTEUR")
@require_POST
def vehicule_supprimer(request, pk):
    v = get_object_or_404(Vehicle, pk=pk, transporteur__user=request.user)
    if v.propositions.exists():          # FK PROTECT: on garde l'historique
        messages.error(request, "Ce véhicule est lié à des propositions : rendez-le indisponible au lieu de le supprimer.")
    else:
        v.delete()
        messages.success(request, "Véhicule supprimé.")
    return redirect("propositions:vehicules")


# ------------------------------------------------------------- propositions
@role_required("TRANSPORTEUR")
def proposer(request, demande_id):
    transporteur = request.user.transporteur
    demande = get_object_or_404(DemandeTransport, pk=demande_id)
    if not transporteur.verified:
        messages.error(request, "Votre compte doit être validé par l'administrateur avant de proposer.")
        return redirect("annonces:detail", pk=demande.pk)
    if demande.status != DemandeTransport.Status.OPEN:
        messages.error(request, "Cette demande n'est plus ouverte.")
        return redirect("annonces:liste")
    if demande.propositions.filter(transporteur=transporteur, status__in=Proposition.ACTIVES).exists():
        messages.warning(request, "Vous avez déjà une proposition active sur cette demande.")
        return redirect("annonces:detail", pk=demande.pk)
    if not transporteur.vehicles.filter(availability=True).exists():
        messages.warning(request, "Ajoutez d'abord un véhicule disponible.")
        return redirect("propositions:vehicules")

    form = PropositionForm(request.POST or None, transporteur=transporteur, demande=demande)
    if request.method == "POST" and form.is_valid():
        p = form.save(commit=False)
        p.demande, p.transporteur = demande, transporteur
        try:
            p.save()
        except IntegrityError:
            messages.warning(request, "Vous avez déjà une proposition active sur cette demande.")
        else:
            messages.success(request, "Proposition envoyée.")
        return redirect("annonces:detail", pk=demande.pk)
    return render(request, "propositions/proposer.html", {"form": form, "d": demande})


@role_required("TRANSPORTEUR")
def mes_propositions(request):
    props = (Proposition.objects.filter(transporteur__user=request.user)
             .select_related("demande", "vehicle").order_by("-created_at"))
    return render(request, "propositions/mes_propositions.html", {"propositions": props})


@role_required("TRANSPORTEUR")
@require_POST
def retirer(request, pk):
    p = get_object_or_404(Proposition, pk=pk, transporteur__user=request.user)
    if p.status != Proposition.Status.PENDING:
        messages.error(request, "Seule une proposition en attente peut être retirée.")
    else:
        p.status = Proposition.Status.WITHDRAWN
        p.save(update_fields=["status"])
        messages.success(request, "Proposition retirée.")
    return redirect("propositions:mes_propositions")


@role_required("TRANSPORTEUR")
def matching(request):
    return render(request, "propositions/matching.html",
                  {"resultats": demandes_compatibles(request.user.transporteur)})


# --------------------------------------------------- côté PME: comparer/accepter
@role_required("PME")
def propositions_recues(request):
    """Toutes les offres reçues sur les demandes de la PME connectée."""
    props = (Proposition.objects.filter(demande__pme__user=request.user)
             .select_related("demande", "transporteur", "vehicle").order_by("-created_at"))
    return render(request, "propositions/recues.html", {"propositions": props})


@role_required("PME")
def comparer_propositions(request, demande_id):
    demande = get_object_or_404(DemandeTransport, pk=demande_id, pme__user=request.user)
    return render(request, "propositions/comparer.html", {"d": demande, "lignes": comparer(demande)})


@role_required("PME")
@require_POST
def accepter(request, pk):
    p = get_object_or_404(Proposition, pk=pk, demande__pme__user=request.user)
    try:
        accepter_proposition(p)
    except ErreurMetier as e:
        messages.error(request, str(e))
    else:
        messages.success(request, "Proposition acceptée. Les autres offres ont été refusées.")
    return redirect("annonces:detail", pk=p.demande_id)