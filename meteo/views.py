from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from annonces.models import DemandeTransport
from users.decorators import role_required

from .models import AlerteMeteo, PrevisionMeteo
from .services import actualiser_tout, alertes_visibles, mettre_a_jour


def _peut_voir(user, demande):
    if user.is_superuser or user.role == "ADMIN":
        return True
    if user.role == "PME":
        return demande.pme.user_id == user.id
    if user.role == "TRANSPORTEUR":
        return (demande.status == DemandeTransport.Status.OPEN
                or demande.propositions.filter(transporteur__user=user).exists())
    return False


def _demande_autorisee(request, demande_id):
    demande = get_object_or_404(DemandeTransport.objects.select_related("pme"), pk=demande_id)
    if not _peut_voir(request.user, demande):
        raise PermissionDenied
    return demande


@login_required
def detail(request, demande_id):
    demande = _demande_autorisee(request, demande_id)
    if not demande.previsions.exists():                # 1re visite: on interroge l'API
        for e in mettre_a_jour(demande):
            messages.warning(request, e)
    prevs = {p.point: p for p in demande.previsions.all()}
    cartes = [
        {"titre": "Chargement", "ville": demande.origin, "date": demande.pickup_date,
         "prevision": prevs.get(PrevisionMeteo.Point.ORIGINE)},
        {"titre": "Livraison", "ville": demande.destination, "date": demande.delivery_date,
         "prevision": prevs.get(PrevisionMeteo.Point.DESTINATION)},
    ]
    return render(request, "meteo/detail.html", {"d": demande, "cartes": cartes})


@login_required
@require_POST
def actualiser(request, demande_id):
    demande = _demande_autorisee(request, demande_id)
    erreurs = mettre_a_jour(demande)
    for e in erreurs:
        messages.warning(request, e)
    if not erreurs:
        messages.success(request, "Météo mise à jour.")
    return redirect("meteo:detail", demande_id=demande.pk)


@role_required("PME", "TRANSPORTEUR", "ADMIN")
def alertes(request):
    """PME: alertes de ses demandes. Transporteur: alertes des demandes où il a proposé. Admin: toutes."""
    return render(request, "meteo/alertes.html", {"alertes": alertes_visibles(request.user)})


@role_required("PME", "TRANSPORTEUR", "ADMIN")
@require_POST
def alertes_actualiser(request):
    """Interroge l'API météo pour toutes les demandes actives, puis recrée/met à jour les alertes."""
    nb, erreurs = actualiser_tout(request.user)
    if nb == 0:
        messages.info(request, "Aucune demande active à vérifier.")
    elif not erreurs:
        messages.success(request, f"Météo mise à jour pour {nb} demande(s).")
    else:
        messages.warning(request, f"Météo vérifiée pour {nb} demande(s), avec des avertissements :")
        for e in erreurs[:5]:
            messages.warning(request, e)
        if len(erreurs) > 5:
            messages.warning(request, f"… et {len(erreurs) - 5} autre(s).")
    return redirect("meteo:alertes")


@role_required("PME")      # le drapeau « lue » appartient à la PME: le transporteur ne peut pas le modifier
@require_POST
def alertes_lues(request):
    AlerteMeteo.objects.filter(prevision__demande__pme__user=request.user, lue=False).update(lue=True)
    messages.success(request, "Alertes marquées comme lues.")
    return redirect("meteo:alertes")