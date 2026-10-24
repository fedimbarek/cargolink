from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from users.testing import RAPIDE, make_demande, make_pme, make_proposition, make_transporteur, make_vehicle

from . import services
from .models import AlerteMeteo, PrevisionMeteo

BEAU = {"temp_min": 15, "temp_max": 25, "pluie": 0, "vent": 10, "code": 0}
ORAGE = {"temp_min": 15, "temp_max": 25, "pluie": 25, "vent": 70, "code": 95}


class RisqueTests(TestCase):
    def test_faible(self):
        self.assertEqual(services.evaluer_risque(15, 25, 0, 10, 0), ("FAIBLE", []))

    def test_pluie_moyenne_et_forte(self):
        self.assertEqual(services.evaluer_risque(15, 25, 5, 10, 61)[0], "MOYEN")
        self.assertEqual(services.evaluer_risque(15, 25, 20, 10, 65)[0], "ELEVE")

    def test_vent_et_chaleur(self):
        self.assertEqual(services.evaluer_risque(15, 25, 0, 40, 0)[0], "MOYEN")
        self.assertEqual(services.evaluer_risque(15, 25, 0, 60, 0)[0], "ELEVE")
        self.assertEqual(services.evaluer_risque(25, 36, 0, 0, 0)[0], "MOYEN")
        self.assertEqual(services.evaluer_risque(25, 41, 0, 0, 0)[0], "ELEVE")

    def test_orage_toujours_eleve(self):
        niveau, raisons = services.evaluer_risque(15, 25, 0, 0, 95)
        self.assertEqual(niveau, "ELEVE")
        self.assertIn("orage", raisons)

    def test_gel_donne_risque_moyen(self):
        self.assertEqual(services.evaluer_risque(-2, 5, 0, 0, 0)[0], "MOYEN")


@RAPIDE
class ServiceTests(TestCase):
    def setUp(self):
        self.u_pme, self.pme = make_pme()
        self.d = make_demande(self.pme, origin_lat=36.8, origin_lon=10.1, destination_lat=34.7, destination_lon=10.7)

    @patch("meteo.services.prevision_jour", return_value=ORAGE)
    def test_mise_a_jour_cree_previsions_et_alertes(self, _):
        self.assertEqual(services.mettre_a_jour(self.d), [])
        self.assertEqual(PrevisionMeteo.objects.filter(demande=self.d).count(), 2)
        self.assertEqual(AlerteMeteo.objects.filter(niveau="ELEVE").count(), 2)

    @patch("meteo.services.prevision_jour")
    def test_alerte_supprimee_quand_le_risque_disparait(self, prev):
        prev.return_value = ORAGE
        services.mettre_a_jour(self.d)
        prev.return_value = BEAU
        services.mettre_a_jour(self.d)
        self.assertEqual(AlerteMeteo.objects.count(), 0)

    def test_date_hors_horizon(self):
        d = make_demande(self.pme, pickup_date=timezone.now() + timedelta(days=40),
                         delivery_date=timezone.now() + timedelta(days=41),
                         origin_lat=1, origin_lon=1, destination_lat=1, destination_lon=1)
        erreurs = services.mettre_a_jour(d)
        self.assertEqual(len(erreurs), 2)
        self.assertEqual(PrevisionMeteo.objects.filter(demande=d).count(), 0)

    @patch("meteo.services.prevision_jour", side_effect=services.ErreurMeteo("API météo indisponible"))
    def test_api_en_panne_ne_plante_pas(self, _):
        self.assertEqual(len(services.mettre_a_jour(self.d)), 2)

    @patch("meteo.services.requests.get")
    def test_geocodage_api_en_panne(self, get):
        import requests
        from django.core.cache import cache
        cache.clear()
        get.side_effect = requests.RequestException("boom")
        with self.assertRaises(services.ErreurMeteo):
            services.geocoder("Gabès")

    def test_visibilite_des_demandes(self):
        _, t = make_transporteur()
        make_proposition(self.d, t, make_vehicle(t))
        autre = make_demande(self.pme)
        self.assertEqual(set(services.demandes_du_user(t.user)), {self.d})
        self.assertEqual(set(services.demandes_du_user(self.u_pme)), {self.d, autre})


@RAPIDE
class VuesTests(TestCase):
    def setUp(self):
        self.u_pme, self.pme = make_pme()
        self.u_pme2, _ = make_pme("pme2")
        self.u_t, self.t = make_transporteur()
        self.d = make_demande(self.pme, origin_lat=1, origin_lon=1, destination_lat=2, destination_lon=2)

    @patch("meteo.services.prevision_jour", return_value=BEAU)
    def test_detail_proprietaire(self, _):
        self.client.force_login(self.u_pme)
        self.assertEqual(self.client.get(reverse("meteo:detail", args=[self.d.pk])).status_code, 200)

    def test_detail_autre_pme_interdit(self):
        self.client.force_login(self.u_pme2)
        self.assertEqual(self.client.get(reverse("meteo:detail", args=[self.d.pk])).status_code, 403)

    def test_actualiser_exige_post(self):
        self.client.force_login(self.u_pme)
        self.assertEqual(self.client.get(reverse("meteo:actualiser", args=[self.d.pk])).status_code, 405)

    def test_transporteur_ne_peut_pas_marquer_les_alertes_lues(self):
        self.client.force_login(self.u_t)
        self.assertEqual(self.client.post(reverse("meteo:alertes_lues")).status_code, 403)

    @patch("meteo.services.prevision_jour", return_value=ORAGE)
    def test_pme_marque_les_alertes_lues(self, _):
        services.mettre_a_jour(self.d)
        self.client.force_login(self.u_pme)
        self.client.post(reverse("meteo:alertes_lues"))
        self.assertFalse(AlerteMeteo.objects.filter(lue=False).exists())
