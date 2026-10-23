from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from users.testing import (RAPIDE, make_demande, make_pme, make_proposition, make_transporteur, make_vehicle)
from io import StringIO
from .forms import DemandeFilterForm, DemandeForm
from .models import DemandeTransport

TRAJET = {"origin_lat": 36.8, "origin_lon": 10.1, "destination_lat": 34.7, "destination_lon": 10.7,
          "distance_km": 270.0, "duration_hours": 3.2}


def donnees(**kw):
    now = timezone.now()
    d = {"origin": "Tunis", "destination": "Sfax", "pickup_date": (now + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
         "delivery_date": (now + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M"), "weight": "1500",
         "volume": "10", "cargo_type": "Palettes", "description": ""}
    d.update(kw)
    return d


@RAPIDE
class ModeleTests(TestCase):
    def setUp(self):
        self.u_pme, self.pme = make_pme()

    def test_livraison_apres_chargement(self):
        d = make_demande(self.pme)
        d.delivery_date = d.pickup_date - timedelta(hours=1)
        with self.assertRaises(ValidationError):
            d.clean()

    def test_chargement_dans_le_futur(self):
        d = make_demande(self.pme)
        d.pickup_date = timezone.now() - timedelta(days=1)
        d.delivery_date = timezone.now() + timedelta(days=1)
        with self.assertRaises(ValidationError):
            d.clean()

    def test_origine_differente_de_destination(self):
        d = make_demande(self.pme, destination="tunis ")
        with self.assertRaises(ValidationError):
            d.clean()

    def test_modifiable_seulement_sans_proposition(self):
        d = make_demande(self.pme)
        self.assertTrue(d.est_modifiable)
        _, t = make_transporteur()
        make_proposition(d, t, make_vehicle(t))
        self.assertFalse(d.est_modifiable)

    def test_annuler_rejette_les_propositions_actives(self):
        d = make_demande(self.pme)
        _, t = make_transporteur()
        p = make_proposition(d, t, make_vehicle(t))
        d.annuler()
        p.refresh_from_db()
        self.assertEqual((d.status, p.status), ("CANCELLED", "REJECTED"))

    def test_commande_expire_demandes(self):
        vieille = make_demande(self.pme, pickup_date=timezone.now() - timedelta(days=1),
                               delivery_date=timezone.now() + timedelta(days=1))
        recente = make_demande(self.pme)
        #call_command("expire_demandes", stdout=open("/dev/null", "w"))
        call_command("expire_demandes", stdout=StringIO())
        vieille.refresh_from_db(); recente.refresh_from_db()
        self.assertEqual((vieille.status, recente.status), ("EXPIRED", "OPEN"))

    def test_lien_itineraire_et_badge(self):
        d = make_demande(self.pme)
        self.assertIsNone(d.lien_itineraire)
        d.origin_lat = d.origin_lon = d.destination_lat = d.destination_lon = 1.0
        self.assertIn("openstreetmap", d.lien_itineraire)
        self.assertEqual(d.badge_class, "bg-success")


class FormulaireTests(TestCase):
    def test_form_valide(self):
        self.assertTrue(DemandeForm(donnees()).is_valid())

    def test_dates_incoherentes(self):
        f = DemandeForm(donnees(delivery_date=(timezone.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")))
        self.assertFalse(f.is_valid())
        self.assertIn("delivery_date", f.errors)

    def test_poids_minimum(self):
        self.assertFalse(DemandeForm(donnees(weight="0")).is_valid())

    def test_filtre_poids_incoherent(self):
        f = DemandeFilterForm({"poids_min": "50", "poids_max": "10"})
        self.assertFalse(f.is_valid())


@RAPIDE
class VuesTests(TestCase):
    def setUp(self):
        self.u_pme, self.pme = make_pme("pme")
        self.u_pme2, self.pme2 = make_pme("pme2")
        self.u_tr, self.tr = make_transporteur("tr")
        self.d = make_demande(self.pme)

    def test_liste_exige_connexion(self):
        r = self.client.get(reverse("annonces:liste"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r.url)

    @patch("annonces.views.calculer_trajet", return_value=TRAJET)
    def test_creation_par_pme(self, _):
        self.client.force_login(self.u_pme)
        r = self.client.post(reverse("annonces:creer"), donnees())
        self.assertEqual(r.status_code, 302)
        d = DemandeTransport.objects.latest("id")
        self.assertEqual((d.pme, float(d.distance_km)), (self.pme, 270.0))

    @patch("annonces.views.calculer_trajet", return_value=None)
    def test_creation_meme_si_api_en_panne(self, _):
        self.client.force_login(self.u_pme)
        self.client.post(reverse("annonces:creer"), donnees())
        self.assertIsNone(DemandeTransport.objects.latest("id").distance_km)

    def test_transporteur_ne_peut_pas_creer(self):
        self.client.force_login(self.u_tr)
        self.assertEqual(self.client.get(reverse("annonces:creer")).status_code, 403)

    def test_pme_ne_voit_pas_la_demande_d_une_autre(self):
        self.client.force_login(self.u_pme2)
        self.assertEqual(self.client.get(reverse("annonces:detail", args=[self.d.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("annonces:liste")).context["demandes"].count(), 0)

    def test_transporteur_voit_seulement_les_ouvertes(self):
        self.client.force_login(self.u_tr)
        make_demande(self.pme, status="CANCELLED")
        self.assertEqual(self.client.get(reverse("annonces:liste")).context["demandes"].count(), 1)

    def test_filtre_par_poids(self):
        make_demande(self.pme, weight=9000)
        self.client.force_login(self.u_pme)
        r = self.client.get(reverse("annonces:liste"), {"poids_min": "5000"})
        self.assertEqual([x.weight for x in r.context["demandes"]], [9000])

    def test_modification_bloquee_apres_proposition(self):
        make_proposition(self.d, self.tr, make_vehicle(self.tr))
        self.client.force_login(self.u_pme)
        r = self.client.get(reverse("annonces:modifier", args=[self.d.pk]))
        self.assertRedirects(r, reverse("annonces:detail", args=[self.d.pk]))

    def test_annulation_exige_post(self):
        self.client.force_login(self.u_pme)
        self.assertEqual(self.client.get(reverse("annonces:annuler", args=[self.d.pk])).status_code, 405)
        self.client.post(reverse("annonces:annuler", args=[self.d.pk]))
        self.d.refresh_from_db()
        self.assertEqual(self.d.status, "CANCELLED")

    def test_autre_pme_ne_peut_pas_annuler(self):
        self.client.force_login(self.u_pme2)
        self.assertEqual(self.client.post(reverse("annonces:annuler", args=[self.d.pk])).status_code, 404)
