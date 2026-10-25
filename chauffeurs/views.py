from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from users.decorators import role_required
from users.models import Transporteur

from .forms import AffectationForm, ChauffeurForm, PermisForm
from .models import Affectation, Chauffeur, Permis


# Afficher et rechercher les chauffeurs
@role_required("TRANSPORTEUR")
@require_http_methods(["GET"])
def liste(request):
    chauffeurs = (
        Chauffeur.objects
        .filter(transporteur__user=request.user)
        .select_related("permis")
        .order_by("nom", "prenom")
    )

    recherche = request.GET.get("q", "").strip()

    if recherche:
        chauffeurs = chauffeurs.filter(
            Q(nom__icontains=recherche)
            | Q(prenom__icontains=recherche)
        )

    return render(request, "chauffeurs/liste.html", {
        "chauffeurs": chauffeurs,
        "recherche": recherche,
    })


# Ajouter un chauffeur avec son permis
@role_required("TRANSPORTEUR")
@require_http_methods(["GET", "POST"])
def ajouter(request):
    transporteur = get_object_or_404(
        Transporteur,
        user=request.user,
    )

    donnees = request.POST if request.method == "POST" else None

    form = ChauffeurForm(donnees)
    permis_form = PermisForm(donnees)

    if request.method == "POST":
        chauffeur_valide = form.is_valid()
        permis_valide = permis_form.is_valid()

        if chauffeur_valide and permis_valide:
            with transaction.atomic():
                chauffeur = form.save(commit=False)
                chauffeur.transporteur = transporteur
                chauffeur.save()

                permis = permis_form.save(commit=False)
                permis.chauffeur = chauffeur
                permis.save()

            messages.success(
                request,
                "Le chauffeur et son permis ont été ajoutés."
            )
            return redirect("chauffeurs:liste")

    return render(request, "chauffeurs/form.html", {
        "form": form,
        "permis_form": permis_form,
        "titre": "Ajouter un chauffeur",
    })


# Modifier un chauffeur et son permis
@role_required("TRANSPORTEUR")
@require_http_methods(["GET", "POST"])
def modifier(request, pk):
    chauffeur = get_object_or_404(
        Chauffeur,
        pk=pk,
        transporteur__user=request.user,
    )

    permis = Permis.objects.filter(chauffeur=chauffeur).first()
    donnees = request.POST if request.method == "POST" else None

    form = ChauffeurForm(
        donnees,
        instance=chauffeur,
    )
    permis_form = PermisForm(
        donnees,
        instance=permis,
    )

    if request.method == "POST":
        chauffeur_valide = form.is_valid()
        permis_valide = permis_form.is_valid()

        if chauffeur_valide and permis_valide:
            with transaction.atomic():
                chauffeur = form.save()

                permis = permis_form.save(commit=False)
                permis.chauffeur = chauffeur
                permis.save()

            messages.success(
                request,
                "Le chauffeur et son permis ont été enregistrés."
            )
            return redirect("chauffeurs:liste")

    return render(request, "chauffeurs/form.html", {
        "form": form,
        "permis_form": permis_form,
        "titre": "Modifier un chauffeur",
    })


# Supprimer un chauffeur uniquement s'il n'a aucune affectation
@role_required("TRANSPORTEUR")
@require_http_methods(["GET", "POST"])
def supprimer(request, pk):
    chauffeur = get_object_or_404(
        Chauffeur,
        pk=pk,
        transporteur__user=request.user,
    )

    if request.method == "POST":
        if chauffeur.affectations.exists():
            messages.error(
                request,
                "Ce chauffeur possède des affectations. "
                "Il ne peut pas être supprimé."
            )
            return redirect("chauffeurs:liste")

        chauffeur.delete()

        messages.success(
            request,
            "Le chauffeur et son permis associé ont été supprimés."
        )
        return redirect("chauffeurs:liste")

    return render(
        request,
        "chauffeurs/confirmer_suppression.html",
        {"chauffeur": chauffeur},
    )


# Affecter un chauffeur disponible à une mission acceptée
@role_required("TRANSPORTEUR")
@require_http_methods(["GET", "POST"])
def affecter(request):
    transporteur = get_object_or_404(
        Transporteur,
        user=request.user,
    )

    donnees = request.POST if request.method == "POST" else None

    form = AffectationForm(
        donnees,
        transporteur=transporteur,
    )

    if request.method == "POST" and form.is_valid():
        chauffeur = form.cleaned_data["chauffeur"]

        try:
            with transaction.atomic():
                nombre_modifie = Chauffeur.objects.filter(
                    pk=chauffeur.pk,
                    transporteur=transporteur,
                    disponible=True,
                ).update(disponible=False)

                if nombre_modifie == 1:
                    form.save()

        except IntegrityError:
            form.add_error(
                None,
                "L’affectation n’a pas pu être enregistrée. "
                "Cette mission a peut-être déjà été affectée. "
                "Actualisez la page."
            )

        else:
            if nombre_modifie == 1:
                messages.success(
                    request,
                    "Chauffeur affecté à la mission."
                )
                return redirect("chauffeurs:affecter")

            form.add_error(
                "chauffeur",
                "Ce chauffeur n’est plus disponible."
            )

    affectations = (
        Affectation.objects
        .filter(proposition__transporteur=transporteur)
        .select_related(
            "chauffeur",
            "proposition__demande",
        )
        .order_by("-date_creation")
    )

    return render(request, "chauffeurs/affecter.html", {
        "form": form,
        "affectations": affectations,
    })