import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from users.testing import RAPIDE, make_demande, make_pme, make_proposition, make_transporteur, make_vehicle

from . import ml, views
from .services import ErreurIA, calculer_estimation
from .tasks import estimer_trajet_task

TRAJET = {"distance_km": 270.0, "duration_hours": 3.2, "origin_lat": 1, "origin_lon": 1,
          "destination_lat": 2, "destination_lon": 2}


class FeaturesTests(TestCase):
    def test_categories(self):
        self.assertEqual(ml.categorie("Produits laitiers frais"), "FRIGO")
        self.assertEqual(ml.categorie("Produits chimiques"), "DANGEREUX")
        self.assertEqual(ml.categorie("Verre fragile"), "FRAGILE")
        self.assertEqual(ml.categorie("Palettes"), "GENERAL")
        self.assertEqual(ml.categorie(None), "GENERAL")

    def test_vecteur_longueur_et_volume_par_defaut(self):
        v = ml.vecteur(100, 500, None, "Palettes")
        self.assertEqual(len(v), len(ml.FEATURES))
        self.assertEqual(v[2], 2.0)                      # 500 kg / 250 kg/m³

    def test_donnees_synthetiques_reproductibles(self):
        X1, y1 = ml.generer_donnees(200, seed=1)
        X2, y2 = ml.generer_donnees(200, seed=1)
        self.assertTrue(np.array_equal(y1, y2))
        self.assertEqual(X1.shape, (200, len(ml.FEATURES)))
        self.assertTrue((y1 > 0).all())


class ModeleTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.override = override_settings(IA_ARTIFACTS_DIR=Path(cls.tmp.name))
        cls.override.enable()
        ml.charger_modele.cache_clear()
        cls.metriques = ml.entrainer(n_synthetiques=1200, avec_reelles=False)

    @classmethod
    def tearDownClass(cls):
        cls.override.disable()
        ml.charger_modele.cache_clear()
        cls.tmp.cleanup()
        super().tearDownClass()

    def test_le_modele_bat_largement_la_baseline(self):
        par_nom = {m["nom"]: m for m in self.metriques["modeles"]}
        self.assertGreater(self.metriques["test_retenu"]["r2"], 0.9)
        self.assertLess(self.metriques["test_retenu"]["mape"], 15)
        self.assertLess(self.metriques["test_retenu"]["mae"], par_nom["Baseline (moyenne)"]["test_mae"] / 3)

    def test_intervalle_calibre(self):
        self.assertGreater(self.metriques["intervalle"]["couverture_test"], 0.8)

    def test_metriques_sauvegardees(self):
        lues = ml.lire_metriques()
        self.assertEqual(lues["retenu"], self.metriques["retenu"])
        self.assertIn("latence", lues)

    def test_estimation_coherente(self):
        e = ml.estimer(250, 1000, 5, "Palettes")
        self.assertLess(e["bas"], e["prix"])
        self.assertLess(e["prix"], e["haut"])
        self.assertGreater(e["prix"], 100)
        self.assertLess(e["temps_ms"], 200)

    def test_plus_loin_et_plus_lourd_coute_plus_cher(self):
        self.assertGreater(ml.estimer(600, 1000, 5, "x")["prix"], ml.estimer(100, 1000, 5, "x")["prix"])
        self.assertGreater(ml.estimer(300, 15000, 40, "x")["prix"], ml.estimer(300, 500, 2, "x")["prix"])

    def test_frigorifique_et_urgence_majorent_le_prix(self):
        base = ml.estimer(300, 2000, 8, "palettes")["prix"]
        self.assertGreater(ml.estimer(300, 2000, 8, "viande surgelée")["prix"], base)
        self.assertGreater(ml.estimer(300, 2000, 8, "palettes", urgent=True)["prix"], base)

    def test_entrees_invalides(self):
        for args in [(0, 100), (100, 0), (None, 100), (-5, 100)]:
            with self.assertRaises(ValueError):
                ml.estimer(*args)

    def test_modele_absent_est_reentraine_automatiquement(self):
        with tempfile.TemporaryDirectory() as vide, override_settings(IA_ARTIFACTS_DIR=Path(vide)):
            ml.charger_modele.cache_clear()
            self.assertGreater(ml.estimer(200, 800)["prix"], 0)
            self.assertTrue((Path(vide) / "price_model.joblib").exists())
        ml.charger_modele.cache_clear()

    def test_verdict(self):
        est = {"prix": 100.0}
        self.assertEqual(ml.verdict(70, est)[0], "BAS")
        self.assertEqual(ml.verdict(100, est)[0], "OK")
        self.assertEqual(ml.verdict(130, est)[0], "HAUT")
        self.assertIsNone(ml.verdict(100, None))


class CommandeTests(TestCase):
    def test_commande_train_price_model(self):
        from io import StringIO
        from django.core.management import call_command
        with tempfile.TemporaryDirectory() as d, override_settings(IA_ARTIFACTS_DIR=Path(d)):
            out = StringIO()
            call_command("train_price_model", "--n", "600", "--sans-reelles", stdout=out)
            self.assertIn("Modèle retenu", out.getvalue())
            self.assertTrue((Path(d) / "metrics.json").exists())
        ml.charger_modele.cache_clear()


@RAPIDE
class ApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.u_pme, self.pme = make_pme()
        self.u_t, self.t = make_transporteur()
        from users.testing import make_user
        self.u_admin = make_user("adm", "ADMIN")
        self.url = reverse("ia:estimer")
        self.payload = {"origin": "Tunis", "destination": "Sfax", "weight": 1500, "volume": 8,
                        "cargo_type": "Palettes", "urgent": False}

    def post(self, data=None, **kw):
        return self.client.post(self.url, json.dumps(data or self.payload), content_type="application/json", **kw)

    def test_visiteur_redirige_vers_login(self):
        self.assertEqual(self.post().status_code, 302)

    def test_get_interdit(self):
        self.client.force_login(self.u_pme)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_admin_refuse(self):
        self.client.force_login(self.u_admin)
        self.assertEqual(self.post().status_code, 403)

    @patch("ia.services.calculer_trajet", return_value=TRAJET)
    def test_estimation_synchrone(self, _):
        self.client.force_login(self.u_pme)
        r = self.post()
        self.assertEqual(r.status_code, 200)
        e = r.json()["estimation"]
        self.assertEqual(r.json()["etat"], "TERMINE")
        self.assertEqual(e["distance_km"], 270.0)
        self.assertLess(e["bas"], e["haut"])

    @patch("ia.services.calculer_trajet", return_value=TRAJET)
    def test_transporteur_aussi(self, _):
        self.client.force_login(self.u_t)
        self.assertEqual(self.post().status_code, 200)

    @patch("ia.services.calculer_trajet", return_value=None)
    def test_api_distance_indisponible_message_explicite(self, _):
        self.client.force_login(self.u_pme)
        r = self.post()
        self.assertEqual(r.status_code, 502)
        self.assertIn("distance", r.json()["erreur"])

    def test_donnees_invalides(self):
        self.client.force_login(self.u_pme)
        for mauvais in ({"origin": "", "destination": "Sfax", "weight": 5},
                        {"origin": "Tunis", "destination": "tunis", "weight": 5},
                        {"origin": "Tunis", "destination": "Sfax", "weight": -3},
                        {"origin": "Tunis", "destination": "Sfax", "weight": "abc"}):
            r = self.post(mauvais)
            self.assertEqual(r.status_code, 400, mauvais)
            self.assertIn("erreur", r.json())

    def test_json_invalide(self):
        self.client.force_login(self.u_pme)
        r = self.client.post(self.url, "{pas du json", content_type="application/json")
        self.assertEqual(r.status_code, 400)

    @patch("ia.services.calculer_trajet", return_value=TRAJET)
    def test_limitation_de_debit(self, _):
        self.client.force_login(self.u_pme)
        with patch.object(views, "LIMITE_REQUETES", 3):
            codes = [self.post().status_code for _ in range(5)]
        self.assertEqual(codes, [200, 200, 200, 429, 429])

    @override_settings(CELERY_BROKER_URL="redis://localhost:6379/0")
    def test_mode_asynchrone_retourne_202(self):
        self.client.force_login(self.u_pme)
        with patch.object(views.estimer_trajet_task, "delay", return_value=MagicMock(id="abc-123")) as d:
            r = self.post()
        self.assertEqual((r.status_code, r.json()["task_id"]), (202, "abc-123"))
        self.assertTrue(d.called)

    @override_settings(CELERY_BROKER_URL="redis://localhost:6379/0")
    def test_mode_asynchrone_broker_en_panne(self):
        self.client.force_login(self.u_pme)
        with patch.object(views.estimer_trajet_task, "delay", side_effect=OSError("redis down")):
            self.assertEqual(self.post().status_code, 503)

    @override_settings(CELERY_BROKER_URL="redis://localhost:6379/0")
    def test_suivi_de_tache(self):
        self.client.force_login(self.u_pme)
        url = reverse("ia:tache", args=["xyz"])
        cas = [(MagicMock(state="PENDING"), 200, "EN_COURS"),
               (MagicMock(state="SUCCESS", result={"ok": True, "estimation": {"prix": 1}}), 200, "TERMINE"),
               (MagicMock(state="SUCCESS", result={"ok": False, "erreur": "x"}), 502, "ECHEC"),
               (MagicMock(state="FAILURE"), 500, "ECHEC")]
        for res, code, etat in cas:
            with patch.object(views, "AsyncResult", return_value=res):
                r = self.client.get(url)
            self.assertEqual((r.status_code, r.json()["etat"]), (code, etat))

    def test_suivi_de_tache_inactif_sans_redis(self):
        self.client.force_login(self.u_pme)
        self.assertEqual(self.client.get(reverse("ia:tache", args=["xyz"])).status_code, 404)

    @patch("ia.services.calculer_trajet", return_value=TRAJET)
    def test_tache_celery_en_mode_eager(self, _):
        res = estimer_trajet_task.apply(args=("Tunis", "Sfax", 1000, None, "Palettes", False)).get()
        self.assertTrue(res["ok"])
        with patch("ia.services.calculer_trajet", return_value=None):
            self.assertFalse(estimer_trajet_task.apply(args=("A", "B", 1, None, "", False)).get()["ok"])

    @patch("ia.services.calculer_trajet", return_value=TRAJET)
    def test_service_validation(self, _):
        with self.assertRaises(ErreurIA):
            calculer_estimation("Tunis", "Sfax", 0)


@RAPIDE
class IntegrationEcransTests(TestCase):
    def setUp(self):
        self.u_pme, self.pme = make_pme()
        self.u_t, self.t = make_transporteur()
        self.v = make_vehicle(self.t)
        self.d = make_demande(self.pme)

    def test_page_modele(self):
        self.client.force_login(self.u_pme)
        r = self.client.get(reverse("ia:modele"))
        self.assertContains(r, "Comparaison des modèles")

    def test_page_modele_exige_connexion(self):
        self.assertEqual(self.client.get(reverse("ia:modele")).status_code, 302)

    def test_detail_demande_affiche_l_estimation(self):
        self.client.force_login(self.u_pme)
        self.assertContains(self.client.get(reverse("annonces:detail", args=[self.d.pk])), "Estimation IA du prix")

    def test_detail_sans_distance_pas_d_estimation(self):
        d = make_demande(self.pme, distance_km=None, duration_hours=None)
        self.client.force_login(self.u_pme)
        self.assertNotContains(self.client.get(reverse("annonces:detail", args=[d.pk])), "Estimation IA du prix")

    def test_formulaire_de_proposition_affiche_le_prix_conseille(self):
        self.client.force_login(self.u_t)
        self.assertContains(self.client.get(reverse("propositions:proposer", args=[self.d.pk])), "Prix conseillé par l'IA")

    def test_une_panne_du_modele_ne_casse_pas_la_page(self):
        self.client.force_login(self.u_pme)
        with patch("ia.ml.estimer", side_effect=RuntimeError("modèle corrompu")):
            r = self.client.get(reverse("annonces:detail", args=[self.d.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "Estimation IA du prix")
