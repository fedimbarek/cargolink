"""
Logique métier du module reservations (réservation + suivi de livraison + notifications).
  - creer_reservation()   : appelée par propositions.services.accepter_proposition()
  - demarrer()            : le transporteur charge la marchandise -> demande EN COURS
  - ajouter_etape()       : étape intermédiaire (en route, incident...)
  - livrer()              : livraison terminée -> demande LIVRÉE, la PME peut évaluer
  - annuler()             : seulement avant le départ, la demande est annulée
  - notifier()            : crée une notification interne pour un utilisateur
Chaque changement d'état ajoute une EtapeSuivi et notifie l'autre partie.
"""
import logging
from urllib.parse import urljoin

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

import requests

from annonces.models import DemandeTransport

from .models import EtapeSuivi, Notification, Reservation

logger = logging.getLogger(__name__)


class ErreurReservation(Exception):
    """Règle métier non respectée (message affichable à l'utilisateur)."""


def _envoyer_email_notification(email, nom, message, lien, sujet):
    if not settings.BREVO_API_KEY or not settings.BREVO_SENDER_EMAIL:
        logger.warning("Email de notification non envoyé : configuration Brevo manquante.")
        return

    url_notifications = urljoin(
        f"{settings.SITE_URL.rstrip('/')}/",
        (lien or reverse("reservations:notifications")).lstrip("/"),
    )
    try:
        reponse = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "accept": "application/json",
                "api-key": settings.BREVO_API_KEY,
                "content-type": "application/json",
            },
            json={
                "sender": {
                    "name": settings.BREVO_SENDER_NAME,
                    "email": settings.BREVO_SENDER_EMAIL,
                },
                "to": [{"email": email, "name": nom}],
                "subject": sujet,
                "textContent": (
                    f"Bonjour {nom},\n\n"
                    f"Vous avez une nouvelle notification :\n\n{message}\n\n"
                    f"Consultez-la ici : {url_notifications}"
                ),
            },
            timeout=10,
        )
        reponse.raise_for_status()
    except requests.RequestException:
        logger.exception("Échec de l'envoi de l'email de notification via Brevo.")


def notifier(user, message, lien="", transporteur=None, *, sujet="Nouvelle notification CargoLink"):
    notification = Notification.objects.create(
        user=user, transporteur=transporteur, message=message[:255], lien=lien
    )
    if user.role == "PME":
        transaction.on_commit(
            lambda: _envoyer_email_notification(
                user.email,
                user.get_full_name() or user.username,
                notification.message,
                notification.lien,
                sujet,
            ),
            robust=True,
        )
    return notification


def _lien(reservation):
    return reverse("reservations:detail", args=[reservation.pk])


@transaction.atomic
def creer_reservation(proposition):
    reservation, cree = Reservation.objects.get_or_create(
        proposition=proposition,
        defaults={
            "user": proposition.demande.pme.user,
            "transporteur": proposition.transporteur,
            "nom_contact": proposition.demande.pme.user.username,
            "email_contact": proposition.demande.pme.user.email,
            "nom_societe": proposition.demande.pme.company_name,
            "telephone": proposition.demande.pme.phone,
        },
    )
    if cree:
        if proposition.status == proposition.Status.ACCEPTED:
            from factures.services import creer_facture, echeance_par_defaut

            creer_facture(proposition, echeance_par_defaut())
        EtapeSuivi.objects.create(reservation=reservation, type=EtapeSuivi.Type.CONFIRMATION)
        notifier(
            reservation.user,
            f"Votre réservation #{reservation.pk} pour {proposition.demande} est confirmée.",
            _lien(reservation),
            sujet="Confirmation de votre réservation CargoLink",
        )
        notifier(
            proposition.transporteur.user,
            f"Statut : proposition confirmée pour {proposition.demande}.",
            _lien(reservation),
            transporteur=proposition.transporteur,
        )
    return reservation


@transaction.atomic
def demarrer(reservation, commentaire="", localisation=""):
    if reservation.status != Reservation.Status.CONFIRMEE:
        raise ErreurReservation("Seule une réservation confirmée peut démarrer.")
    reservation.status = Reservation.Status.EN_COURS
    reservation.demarree_le = timezone.now()
    reservation.save(update_fields=["status", "demarree_le"])
    DemandeTransport.objects.filter(pk=reservation.demande.pk).update(
        status=DemandeTransport.Status.IN_PROGRESS)
    EtapeSuivi.objects.create(reservation=reservation, type=EtapeSuivi.Type.CHARGEMENT,
                              commentaire=commentaire, localisation=localisation)
    notifier(reservation.pme.user, f"Votre marchandise ({reservation.demande}) est en route.",
             _lien(reservation))
    return reservation


ETAPES_INTERMEDIAIRES = (EtapeSuivi.Type.EN_ROUTE, EtapeSuivi.Type.INCIDENT)


def ajouter_etape(reservation, type_etape, commentaire="", localisation=""):
    if reservation.status != Reservation.Status.EN_COURS:
        raise ErreurReservation("Les étapes ne peuvent être ajoutées que pendant la livraison.")
    if type_etape not in ETAPES_INTERMEDIAIRES:
        raise ErreurReservation("Type d'étape invalide.")
    etape = EtapeSuivi.objects.create(reservation=reservation, type=type_etape,
                                      commentaire=commentaire, localisation=localisation)
    notifier(reservation.pme.user, f"Suivi {reservation.demande} : {etape.get_type_display()}"
             + (f" - {commentaire}" if commentaire else ""), _lien(reservation))
    return etape


@transaction.atomic
def livrer(reservation, commentaire=""):
    if reservation.status != Reservation.Status.EN_COURS:
        raise ErreurReservation("Seule une réservation en cours peut être livrée.")
    reservation.status = Reservation.Status.LIVREE
    reservation.livree_le = timezone.now()
    reservation.save(update_fields=["status", "livree_le"])
    DemandeTransport.objects.filter(pk=reservation.demande.pk).update(
        status=DemandeTransport.Status.DELIVERED)
    EtapeSuivi.objects.create(reservation=reservation, type=EtapeSuivi.Type.LIVRAISON,
                              commentaire=commentaire)
    notifier(reservation.pme.user,
             f"{reservation.demande} a été livrée. Pensez à évaluer le transporteur.", _lien(reservation))
    return reservation


@transaction.atomic
def annuler(reservation, par_user, motif=""):
    if reservation.status != Reservation.Status.CONFIRMEE:
        raise ErreurReservation("Une réservation ne peut être annulée qu'avant le départ.")
    reservation.status = Reservation.Status.ANNULEE
    reservation.save(update_fields=["status"])
    reservation.demande.annuler()       # demande annulée + proposition acceptée refusée
    EtapeSuivi.objects.create(reservation=reservation, type=EtapeSuivi.Type.ANNULATION, commentaire=motif)
    autre = reservation.transporteur.user if par_user == reservation.pme.user else reservation.pme.user
    notifier(autre, f"La réservation {reservation.demande} a été annulée.", _lien(reservation))
    return reservation
