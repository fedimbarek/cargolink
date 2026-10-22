from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from annonces.models import DemandeTransport
from reservations.models import Reservation
from users.models import PME, Transporteur, User

from .models import Proposition, Vehicle


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AccepterPropositionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="pme", email="pme@example.test", password="password", role=User.Role.PME,
        )
        self.pme = PME.objects.create(
            user=self.user, company_name="Entreprise initiale", registration_number="REG-1",
            address="Tunis", phone="11111111",
        )
        self.carrier_user = User.objects.create_user(
            username="transporteur", email="transporteur@example.test", password="password",
            role=User.Role.TRANSPORTEUR,
        )
        self.transporteur = Transporteur.objects.create(
            user=self.carrier_user, company_name="Transport SARL", verified=True,
        )
        self.demande = DemandeTransport.objects.create(
            pme=self.pme, origin="Tunis", destination="Sfax",
            pickup_date=timezone.now() + timedelta(days=2),
            delivery_date=timezone.now() + timedelta(days=3),
            weight=1000, cargo_type="Palettes",
        )
        self.vehicle = Vehicle.objects.create(
            transporteur=self.transporteur, registration_number="123 TUN 1",
            capacity_weight=5000, capacity_volume=30,
        )
        self.proposition = Proposition.objects.create(
            demande=self.demande, transporteur=self.transporteur, vehicle=self.vehicle,
            price=400, estimated_duration=6,
        )
        self.client.force_login(self.user)

    def test_acceptation_affiche_et_enregistre_les_coordonnees_modifiees(self):
        url = reverse("propositions:accepter", args=[self.proposition.pk])
        response = self.client.get(url)

        self.assertContains(response, "Entreprise initiale")
        self.assertContains(response, "pme@example.test")

        response = self.client.post(url, {
            "nom_contact": "Nouveau contact",
            "email_contact": "contact@example.test",
            "nom_societe": "Nouvelle entreprise",
            "matricule": "REG-2",
            "adresse": "Sousse",
            "telephone": "22222222",
        })

        self.assertRedirects(response, reverse("annonces:detail", args=[self.proposition.demande_id]))
        reservation = Reservation.objects.get(proposition=self.proposition)
        self.assertEqual(reservation.user_id, self.user.pk)
        self.assertEqual(reservation.transporteur_id, self.transporteur.pk)
        self.assertEqual(reservation.proposition_id, self.proposition.pk)
        self.assertEqual(reservation.nom_contact, "Nouveau contact")
        self.assertEqual(reservation.email_contact, "contact@example.test")
        self.assertEqual(reservation.nom_societe, "Nouvelle entreprise")
        self.assertEqual(reservation.adresse, "Sousse")
        self.assertEqual(reservation.telephone, "22222222")
        notification = self.carrier_user.notifications_suivi.get()
        self.assertIn("Statut : proposition confirmée", notification.message)
        self.assertEqual(notification.transporteur_id, self.transporteur.pk)

        self.client.force_login(self.carrier_user)
        self.assertContains(
            self.client.get(reverse("reservations:notifications")),
            f"Transporteur #{self.transporteur.pk}",
        )

    def test_creation_proposition_notifie_la_pme(self):
        demande = DemandeTransport.objects.create(
            pme=self.pme, origin="Sousse", destination="Tunis",
            pickup_date=timezone.now() + timedelta(days=4),
            delivery_date=timezone.now() + timedelta(days=5),
            weight=1000, cargo_type="Palettes",
        )
        self.client.force_login(self.carrier_user)

        response = self.client.post(reverse("propositions:proposer", args=[demande.pk]), {
            "vehicle": self.vehicle.pk,
            "price": "500",
            "estimated_duration": "8",
            "message": "Offre de transport",
        })

        self.assertRedirects(response, reverse("annonces:detail", args=[demande.pk]))
        notification = self.user.notifications_suivi.get()
        self.assertEqual(
            notification.message,
            f"Nouvelle proposition reçue pour votre demande #{demande.pk}.",
        )
        self.assertEqual(
            notification.lien,
            reverse("propositions:comparer", args=[demande.pk]),
        )
