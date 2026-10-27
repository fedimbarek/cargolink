from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from propositions.models import Proposition
from users.decorators import role_required

from . import bilan as bilan_calc, services
from .forms import (BilanFilterForm, FactureCreationForm, FactureFilterForm, FactureForm,
                    PaiementForm)
from .models import Facture, Paiement

S = Facture.Status


def _visibles(user):
    return services.factures_visibles(user)


def _facture(request, pk):
    return get_object_or_404(_visibles(request.user), pk=pk)


def _erreurs(form):
    return " ".join(e for errs in form.errors.values() for e in errs)


@login_required
def liste(request):
    toutes = list(_visibles(request.user))
    factures = toutes
    form = FactureFilterForm(request.GET or None)
    if form.is_bound and form.is_valid() and form.cleaned_data.get("status"):
        factures = [f for f in toutes if f.status == form.cleaned_data["status"]]
    comptees = [f for f in toutes if f.status in (S.EMISE, S.PARTIELLE, S.PAYEE)]
    stats = {
        "total": sum((f.total_ttc for f in comptees), Decimal("0")),
        "paye": sum((f.total_paye for f in comptees), Decimal("0")),
        "retard": sum(1 for f in comptees if f.en_retard),
    }
    stats["reste"] = stats["total"] - stats["paye"]
    a_facturer = []
    if request.user.role == "TRANSPORTEUR":
        a_facturer = services.propositions_a_facturer(request.user)
    return render(request, "factures/liste.html",
                  {"factures": factures, "form": form, "stats": stats, "a_facturer": a_facturer})


# ----------------------------------------------------------- bilan
@login_required
def bilan(request):
    """Bilan de facturation (transporteur: CA / créances ; PME: dépenses / dettes ; admin: tout)."""
    annee, mois = timezone.localdate().year, None
    form = BilanFilterForm(request.GET or None, initial={"annee": annee})
    if form.is_bound and form.is_valid():
        annee = form.cleaned_data.get("annee") or annee
        mois = int(form.cleaned_data["mois"]) if form.cleaned_data.get("mois") else None
    b = bilan_calc.calculer_bilan(request.user, annee, mois)

    analyse_ia = None
    if request.GET.get("ia"):
        analyse_ia = bilan_calc.analyse_ia(b)
        if analyse_ia is None:
            messages.warning(request, "Analyse IA indisponible (clé API absente ou service injoignable). "
                                      "L'analyse automatique reste affichée.")
    return render(request, "factures/bilan.html", {
        "b": b, "form": form, "analyse": bilan_calc.analyse_regles(b), "analyse_ia": analyse_ia,
        "graph": bilan_calc.donnees_graphique(b), "est_pme": request.user.role == "PME"})


@login_required
def detail(request, pk):
    f = _facture(request, pk)
    est_transporteur = f.transporteur.user_id == request.user.id
    return render(request, "factures/detail.html", {
        "f": f, "paiements": f.paiements.all(), "est_transporteur": est_transporteur,
        "paiement_form": PaiementForm(initial={"montant": f.reste_a_payer, "date_paiement": timezone.localdate()})
                         if est_transporteur and f.accepte_paiements else None,
    })


# ----------------------------------------------------------- CRUD facture (transporteur)
@role_required("TRANSPORTEUR")
def nouvelle(request):
    """Bouton « + Nouvelle facture »: choisir une mission acceptée puis saisir la facture."""
    if not services.propositions_a_facturer(request.user).exists():
        messages.info(request, "Aucune mission à facturer pour le moment: "
                               "une PME doit d'abord accepter une de vos propositions.")
        return redirect("factures:liste")
    form = FactureCreationForm(request.POST or None, user=request.user, initial={
        "taux_tva": services.TVA_DEFAUT, "date_echeance": services.echeance_par_defaut()})
    if request.method == "POST" and form.is_valid():
        c = form.cleaned_data
        try:
            f = services.creer_facture(c["proposition"], c["date_echeance"], c["taux_tva"],
                                       c["notes"], c["montant_ht"])
        except services.ErreurFacture as e:
            messages.error(request, str(e))
            return redirect("factures:liste")
        messages.success(request, "Facture créée en brouillon. Vérifiez-la puis émettez-la.")
        return redirect("factures:detail", pk=f.pk)
    return render(request, "factures/form.html", {
        "form": form, "titre": "Nouvelle facture", "retour": reverse("factures:liste")})


@role_required("TRANSPORTEUR")
def creer(request, proposition_id):
    p = get_object_or_404(Proposition.objects.select_related("demande"),
                          pk=proposition_id, transporteur__user=request.user)
    existante = Facture.objects.filter(proposition=p).first()
    if existante:
        messages.info(request, "Cette mission a déjà une facture.")
        return redirect("factures:detail", pk=existante.pk)
    if not services.est_facturable(p):
        messages.error(request, "Cette mission n'est pas facturable (la proposition doit être acceptée).")
        return redirect("factures:liste")
    form = FactureForm(request.POST or None, initial={
        "montant_ht": p.price, "taux_tva": services.TVA_DEFAUT, "date_echeance": services.echeance_par_defaut()})
    if request.method == "POST" and form.is_valid():
        c = form.cleaned_data
        try:
            f = services.creer_facture(p, c["date_echeance"], c["taux_tva"], c["notes"], c["montant_ht"])
        except services.ErreurFacture as e:
            messages.error(request, str(e))
            return redirect("factures:liste")
        messages.success(request, "Facture créée en brouillon. Vérifiez-la puis émettez-la.")
        return redirect("factures:detail", pk=f.pk)
    return render(request, "factures/form.html", {
        "form": form, "titre": f"Facturer la demande #{p.demande_id} ({p.demande})",
        "retour": reverse("factures:liste")})


@role_required("TRANSPORTEUR")
def modifier(request, pk):
    f = _facture(request, pk)
    if not f.est_modifiable:
        messages.error(request, "Seule une facture en brouillon est modifiable.")
        return redirect("factures:detail", pk=pk)
    form = FactureForm(request.POST or None, instance=f)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Facture modifiée.")
        return redirect("factures:detail", pk=pk)
    return render(request, "factures/form.html", {
        "form": form, "titre": f"Modifier {f.numero}", "retour": reverse("factures:detail", args=[pk])})


def _transition(request, pk, fonction, message_ok):
    f = _facture(request, pk)
    try:
        fonction(f)
    except services.ErreurFacture as e:
        messages.error(request, str(e))
    else:
        messages.success(request, message_ok)
    return redirect("factures:detail", pk=pk)


@role_required("TRANSPORTEUR")
@require_POST
def emettre(request, pk):
    return _transition(request, pk, services.emettre, "Facture émise: la PME peut maintenant la consulter.")


@role_required("TRANSPORTEUR")
@require_POST
def annuler(request, pk):
    return _transition(request, pk, services.annuler, "Facture annulée.")


@role_required("TRANSPORTEUR")
@require_POST
def supprimer(request, pk):
    f = _facture(request, pk)
    try:
        services.supprimer_facture(f)
    except services.ErreurFacture as e:
        messages.error(request, str(e))
        return redirect("factures:detail", pk=pk)
    messages.success(request, "Facture supprimée.")
    return redirect("factures:liste")


# ----------------------------------------------------------- CRUD paiements (transporteur)
@role_required("TRANSPORTEUR")
@require_POST
def paiement_ajouter(request, pk):
    f = _facture(request, pk)
    form = PaiementForm(request.POST)
    if form.is_valid():
        c = form.cleaned_data
        try:
            services.enregistrer_paiement(f, c["montant"], c["date_paiement"], c["mode"], c["reference"], request.user)
        except services.ErreurFacture as e:
            messages.error(request, str(e))
        else:
            messages.success(request, "Paiement enregistré.")
    else:
        messages.error(request, "Paiement invalide: " + _erreurs(form))
    return redirect("factures:detail", pk=pk)


def _paiement(request, pk):
    return get_object_or_404(Paiement.objects.select_related("facture"), pk=pk,
                             facture__proposition__transporteur__user=request.user)


@role_required("TRANSPORTEUR")
def paiement_modifier(request, pk):
    p = _paiement(request, pk)
    form = PaiementForm(request.POST or None, instance=p)
    if request.method == "POST" and form.is_valid():
        c = form.cleaned_data
        try:
            services.modifier_paiement(p, montant=c["montant"], date_paiement=c["date_paiement"],
                                       mode=c["mode"], reference=c["reference"])
        except services.ErreurFacture as e:
            messages.error(request, str(e))
        else:
            messages.success(request, "Paiement modifié.")
            return redirect("factures:detail", pk=p.facture_id)
    return render(request, "factures/form.html", {
        "form": form, "titre": "Modifier le paiement", "retour": reverse("factures:detail", args=[p.facture_id])})


@role_required("TRANSPORTEUR")
@require_POST
def paiement_supprimer(request, pk):
    p = _paiement(request, pk)
    facture_id = p.facture_id
    try:
        services.supprimer_paiement(p)
    except services.ErreurFacture as e:
        messages.error(request, str(e))
    else:
        messages.success(request, "Paiement supprimé.")
    return redirect("factures:detail", pk=facture_id)