from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from users.decorators import role_required

from . import services
from .models import EtapeSuivi, Notification, Reservation
from .services import ErreurReservation


def reservations_de(user):
    """Réservations visibles par l'utilisateur (PME propriétaire ou transporteur de la mission)."""
    qs = Reservation.objects.select_related(
        "proposition__demande__pme", "proposition__transporteur", "proposition__vehicle")
    if user.role == "ADMIN":
        return qs
    return qs.filter(Q(proposition__demande__pme__user=user) | Q(proposition__transporteur__user=user))


@role_required("PME", "TRANSPORTEUR", "ADMIN")
def liste(request):
    qs = reservations_de(request.user)
    statut = request.GET.get("status")
    if statut in Reservation.Status.values:
        qs = qs.filter(status=statut)
    return render(request, "reservations/liste.html",
                  {"reservations": qs, "statuts": Reservation.Status.choices, "statut": statut})


@role_required("PME", "TRANSPORTEUR", "ADMIN")
def detail(request, pk):
    r = get_object_or_404(reservations_de(request.user), pk=pk)
    return render(request, "reservations/detail.html", {
        "r": r,
        "etapes": r.etapes.all(),
        "est_transporteur": r.transporteur.user_id == request.user.id,
        "est_pme": r.pme.user_id == request.user.id,
        "types_etape": [(t, EtapeSuivi.Type(t).label) for t in services.ETAPES_INTERMEDIAIRES],
        "evaluation": getattr(r, "evaluation", None),
    })


def _action(request, pk, fonction, message, *, transporteur_seul=True):
    r = get_object_or_404(reservations_de(request.user), pk=pk)
    if transporteur_seul and r.transporteur.user_id != request.user.id:
        raise PermissionDenied
    try:
        fonction(r)
    except ErreurReservation as e:
        messages.error(request, str(e))
    else:
        messages.success(request, message)
    return redirect("reservations:detail", pk=r.pk)


@role_required("TRANSPORTEUR")
@require_POST
def demarrer(request, pk):
    p = request.POST
    return _action(request, pk, lambda r: services.demarrer(
        r, p.get("commentaire", "")[:255], p.get("localisation", "")[:150]), "Mission démarrée.")


@role_required("TRANSPORTEUR")
@require_POST
def etape(request, pk):
    p = request.POST
    return _action(request, pk, lambda r: services.ajouter_etape(
        r, p.get("type"), p.get("commentaire", "")[:255], p.get("localisation", "")[:150]), "Étape ajoutée.")


@role_required("TRANSPORTEUR")
@require_POST
def livrer(request, pk):
    return _action(request, pk, lambda r: services.livrer(r, request.POST.get("commentaire", "")[:255]),
                   "Livraison confirmée.")


@role_required("PME", "TRANSPORTEUR")
@require_POST
def annuler(request, pk):
    return _action(request, pk, lambda r: services.annuler(r, request.user, request.POST.get("motif", "")[:255]),
                   "Réservation annulée.", transporteur_seul=False)


# ------------------------------------------------------------ notifications
@login_required
def notifications(request):
    notifs = request.user.notifications_suivi.all()[:100]
    return render(request, "reservations/notifications.html", {"notifications": notifs})


@login_required
@require_POST
def notification_ouvrir(request, pk):
    n = get_object_or_404(Notification, pk=pk, user=request.user)
    n.lue = True
    n.save(update_fields=["lue"])
    if url_has_allowed_host_and_scheme(
        n.lien,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(n.lien)
    return redirect("reservations:notifications")


@login_required
@require_POST
def notification_supprimer(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.delete()
    return redirect("reservations:notifications")


@login_required
@require_POST
def notifications_tout_lire(request):
    request.user.notifications_suivi.filter(lue=False).update(lue=True)
    return redirect("reservations:notifications")
