from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from annonces.models import DemandeTransport
from evaluations.services import ErreurEvaluation, evaluer
from propositions.models import Proposition, Vehicle
from propositions.services import accepter_proposition
from users.models import PME, Transporteur, User

from . import services
from .models import EtapeSuivi, Notification, Reservation

RAPIDE = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])


def _user(name, role):
    return User.objects.create_user(username=name, email=f"{name}@test.tn", password="pass12345", role=role)


class Base:
    """1 PME, 2 transporteurs qui proposent sur la même demande ; la PME accepte l'offre de `tr`."""

    def setUp(self):
        self.u_pme = _user("pme", "PME")
        self.pme = PME.objects.create(user=self.u_pme, company_name="Pme SA")
        self.u_tr = _user("tr", "TRANSPORTEUR")
        self.tr = Transporteur.objects.create(user=self.u_tr, company_name="Trans SARL", verified=True)
        self.u_tr2 = _user("tr2", "TRANSPORTEUR")
        self.tr2 = Transporteur.objects.create(user=self.u_tr2, company_name="Autre SARL", verified=True)
        now = timezone.now()
        self.demande = DemandeTransport.objects.create(
            pme=self.pme, origin="Tunis", destination="Sfax", weight=1000, cargo_type="Palettes",
            pickup_date=now + timedelta(days=2), delivery_date=now + timedelta(days=3))
        self.p1 = self._proposer(self.tr, "123 TUN 1")
        self.p2 = self._proposer(self.tr2, "456 TUN 2")
        accepter_proposition(self.p1)
        self.r = Reservation.objects.get(proposition=self.p1)

    def _proposer(self, t, immat):
        v = Vehicle.objects.create(transporteur=t, registration_number=immat, capacity_weight=5000, capacity_volume=30)
        return Proposition.objects.create(demande=self.demande, transporteur=t, vehicle=v,
                                          price=Decimal("400"), estimated_duration=6)

    def statut_demande(self):
        self.demande.refresh_from_db()
        return self.demande.status


@RAPIDE
class ServicesTests(Base, TestCase):
    def test_notifier_envoie_un_email_apres_creation(self):
        reponse_api = Mock()
        with self.settings(
            BREVO_API_KEY="cle-test",
            BREVO_SENDER_EMAIL="notifications@example.com",
            BREVO_SENDER_NAME="CargoLink",
            SITE_URL="https://cargolink.example",
        ), patch("reservations.services.requests.post", return_value=reponse_api) as envoyer:
            with self.captureOnCommitCallbacks(execute=True):
                services.notifier(
                    self.u_pme,
                    "Votre réservation a été mise à jour.",
                    "/reservations/1/",
                )

        reponse_api.raise_for_status.assert_called_once_with()
        envoyer.assert_called_once()
        self.assertEqual(envoyer.call_args.args[0], "https://api.brevo.com/v3/smtp/email")
        self.assertEqual(envoyer.call_args.kwargs["headers"]["api-key"], "cle-test")
        self.assertEqual(envoyer.call_args.kwargs["json"]["to"], [
            {"email": self.u_pme.email, "name": self.u_pme.username}
        ])
        self.assertIn(
            "https://cargolink.example/reservations/1/",
            envoyer.call_args.kwargs["json"]["textContent"],
        )

    def test_acceptation_cree_reservation_et_notifie(self):
        self.assertEqual(self.r.status, Reservation.Status.CONFIRMEE)
        self.assertEqual(self.r.etapes.count(), 1)
        self.assertTrue(self.u_tr.notifications_suivi.exists())
        self.assertFalse(Reservation.objects.filter(proposition=self.p2).exists())

    def test_cycle_complet_et_evaluation(self):
        services.demarrer(self.r, localisation="Tunis")
        self.assertEqual(self.statut_demande(), DemandeTransport.Status.IN_PROGRESS)
        services.ajouter_etape(self.r, EtapeSuivi.Type.EN_ROUTE, localisation="Sousse")
        services.livrer(self.r)
        self.assertEqual(self.statut_demande(), DemandeTransport.Status.DELIVERED)
        self.assertEqual(self.r.etapes.count(), 4)
        evaluer(self.r, 4, "Bien")
        self.tr.refresh_from_db()
        self.assertEqual(self.tr.rating, Decimal("4.00"))
        with self.assertRaises(ErreurEvaluation):
            evaluer(self.r, 5)

    def test_regles_de_transition(self):
        with self.assertRaises(services.ErreurReservation):
            services.livrer(self.r)                      # pas encore démarrée
        with self.assertRaises(ErreurEvaluation):
            evaluer(self.r, 5)                           # pas encore livrée
        services.demarrer(self.r)
        with self.assertRaises(services.ErreurReservation):
            services.annuler(self.r, self.u_pme)         # trop tard pour annuler
        with self.assertRaises(services.ErreurReservation):
            services.ajouter_etape(self.r, EtapeSuivi.Type.LIVRAISON)

    def test_annulation_avant_depart(self):
        services.annuler(self.r, self.u_pme, "Plus besoin")
        self.assertEqual(self.statut_demande(), DemandeTransport.Status.CANCELLED)
        self.assertTrue(self.u_tr.notifications_suivi.filter(message__contains="annulée").exists())


@RAPIDE
class WebTests(Base, TestCase):
    def test_compteur_et_tout_marquer_comme_lu(self):
        notification = self.u_tr.notifications_suivi.get()
        self.client.force_login(self.u_tr)

        reponse = self.client.get(reverse("reservations:notifications"))
        self.assertContains(reponse, ">1</span>")

        notification_pme = Notification.objects.create(user=self.u_pme, message="Notification PME")
        url = reverse("reservations:notifications_tout_lire")
        reponse = self.client.post(url)

        self.assertRedirects(reponse, reverse("reservations:notifications"))
        notification.refresh_from_db()
        notification_pme.refresh_from_db()
        self.assertTrue(notification.lue)
        self.assertFalse(notification_pme.lue)
        self.assertNotContains(self.client.get(reverse("reservations:notifications")), ">1</span>")

    def test_supprimer_notification_et_interdire_celle_d_un_autre_user(self):
        notification = self.u_tr.notifications_suivi.get()
        notification_pme = Notification.objects.create(user=self.u_pme, message="Notification PME")
        self.client.force_login(self.u_tr)

        url = reverse("reservations:notification_supprimer", args=[notification.pk])
        reponse = self.client.post(url)

        self.assertRedirects(reponse, reverse("reservations:notifications"))
        self.assertFalse(Notification.objects.filter(pk=notification.pk).exists())

        url_autre_user = reverse("reservations:notification_supprimer", args=[notification_pme.pk])
        self.assertEqual(self.client.post(url_autre_user).status_code, 404)
        self.assertTrue(Notification.objects.filter(pk=notification_pme.pk).exists())

    def test_seul_le_transporteur_demarre(self):
        url = reverse("reservations:demarrer", args=[self.r.pk])
        self.client.force_login(self.u_pme)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.client.force_login(self.u_tr2)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_login(self.u_tr)
        self.client.post(url)
        self.r.refresh_from_db()
        self.assertEqual(self.r.status, Reservation.Status.EN_COURS)

    def test_pages_et_evaluation_web(self):
        services.demarrer(self.r)
        services.livrer(self.r)
        self.client.force_login(self.u_pme)
        self.assertContains(self.client.get(reverse("reservations:detail", args=[self.r.pk])), "Envoyer la note")
        self.assertEqual(self.client.get(reverse("reservations:liste")).status_code, 200)
        self.assertEqual(self.client.get(reverse("reservations:notifications")).status_code, 200)
        self.client.post(reverse("evaluations:evaluer", args=[self.r.pk]), {"note": "5"})
        self.assertTrue(hasattr(Reservation.objects.get(pk=self.r.pk), "evaluation"))
        self.assertEqual(self.client.get(reverse("evaluations:avis", args=[self.tr.pk])).status_code, 200)


@RAPIDE
class ApiTests(Base, APITestCase):
    def test_api_suivi_et_evaluation(self):
        self.client.force_authenticate(self.u_tr)
        self.assertEqual(len(self.client.get("/api/reservations/").data), 1)
        self.assertEqual(self.client.post(f"/api/reservations/{self.r.pk}/demarrer/").status_code, 200)
        self.assertEqual(self.client.post(f"/api/reservations/{self.r.pk}/livrer/").status_code, 200)
        self.client.force_authenticate(self.u_pme)
        self.assertEqual(self.client.post(f"/api/reservations/{self.r.pk}/livrer/").status_code, 403)
        rep = self.client.post(f"/api/evaluations/reservation/{self.r.pk}/", {"note": 3}, format="json")
        self.assertEqual(rep.status_code, 201)
        self.assertGreater(len(self.client.get("/api/reservations/notifications/").data), 0)
