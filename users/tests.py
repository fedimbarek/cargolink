from django.core import mail
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import PME, Transporteur, User
from .testing import RAPIDE, make_demande, make_pme, make_transporteur


class AuthTests(APITestCase):
    def test_register_login_me(self):
        r = self.client.post("/api/auth/register/", {
            "username": "ali", "email": "ali@pme.tn", "password": "Motdepasse123",
            "role": "PME", "company_name": "Ali SARL",
        })
        self.assertEqual(r.status_code, 201)

        r = self.client.post("/api/auth/login/", {"email": "ali@pme.tn", "password": "Motdepasse123"})
        self.assertEqual(r.status_code, 200)
        token = r.data["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        r = self.client.get("/api/auth/me/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["pme"]["company_name"], "Ali SARL")

    def test_transporteur_pending(self):
        r = self.client.post("/api/auth/register/", {
            "username": "tr", "email": "tr@t.tn", "password": "Motdepasse123",
            "role": "TRANSPORTEUR", "company_name": "TR Transport",
        })
        self.assertEqual(r.status_code, 201)
        self.assertEqual(User.objects.get(email="tr@t.tn").status, "PENDING")

    def test_me_requires_login(self):
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)

    def test_register_ne_permet_pas_de_devenir_admin(self):
        r = self.client.post("/api/auth/register/", {
            "username": "x", "email": "x@t.tn", "password": "Motdepasse123", "role": "ADMIN", "company_name": "X"})
        self.assertEqual(r.status_code, 400)

    def test_email_unique(self):
        data = {"username": "a", "email": "dup@t.tn", "password": "Motdepasse123", "role": "PME", "company_name": "A"}
        self.client.post("/api/auth/register/", data)
        data["username"] = "b"
        self.assertEqual(self.client.post("/api/auth/register/", data).status_code, 400)

    def test_mot_de_passe_hache(self):
        self.client.post("/api/auth/register/", {
            "username": "h", "email": "h@t.tn", "password": "Motdepasse123", "role": "PME", "company_name": "H"})
        u = User.objects.get(email="h@t.tn")
        self.assertNotEqual(u.password, "Motdepasse123")
        self.assertTrue(u.password.startswith(("pbkdf2_", "argon2", "bcrypt")))

    def test_mot_de_passe_trop_court(self):
        r = self.client.post("/api/auth/register/", {
            "username": "c", "email": "c@t.tn", "password": "abc", "role": "PME", "company_name": "C"})
        self.assertEqual(r.status_code, 400)

    def test_login_mauvais_mot_de_passe(self):
        make_pme("zed")
        r = self.client.post("/api/auth/login/", {"email": "zed@test.tn", "password": "faux"})
        self.assertEqual(r.status_code, 401)


@RAPIDE
class PagesWebTests(TestCase):
    def test_inscription_pme_connecte_automatiquement(self):
        r = self.client.post(reverse("register_page"), {
            "username": "nour", "email": "nour@t.tn", "password": "Motdepasse123", "role": "PME",
            "company_name": "Nour SA", "phone": "123"})
        self.assertRedirects(r, reverse("dashboard"))
        self.assertTrue(PME.objects.filter(user__email="nour@t.tn").exists())
        self.assertEqual(int(self.client.session["_auth_user_id"]), User.objects.get(email="nour@t.tn").pk)

    def test_inscription_transporteur_en_attente(self):
        self.client.post(reverse("register_page"), {
            "username": "trx", "email": "trx@t.tn", "password": "Motdepasse123", "role": "TRANSPORTEUR",
            "company_name": "Trx"})
        u = User.objects.get(email="trx@t.tn")
        self.assertEqual(u.status, "PENDING")
        self.assertFalse(u.transporteur.verified)

    def test_inscription_mot_de_passe_commun_refuse(self):
        r = self.client.post(reverse("register_page"), {
            "username": "w", "email": "w@t.tn", "password": "password", "role": "PME", "company_name": "W"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(email="w@t.tn").exists())

    def test_inscription_email_deja_utilise(self):
        make_pme("dup")
        r = self.client.post(reverse("register_page"), {
            "username": "autre", "email": "dup@test.tn", "password": "Motdepasse123", "role": "PME", "company_name": "A"})
        self.assertContains(r, "déjà utilisé")

    def test_connexion_par_email(self):
        make_pme("sam")
        r = self.client.post(reverse("login_page"), {"username": "sam@test.tn", "password": "pass12345"})
        self.assertRedirects(r, reverse("dashboard"))

    def test_connexion_refusee(self):
        make_pme("sam")
        r = self.client.post(reverse("login_page"), {"username": "sam@test.tn", "password": "x"})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_dashboard_exige_connexion(self):
        r = self.client.get(reverse("dashboard"))
        self.assertRedirects(r, f"{reverse('login_page')}?next={reverse('dashboard')}")

    def test_deconnexion_par_post(self):
        u, _ = make_pme("out")
        self.client.force_login(u)
        self.client.post(reverse("logout"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_dashboard_selon_le_role(self):
        u, _ = make_transporteur("tt", verified=False)
        self.client.force_login(u)
        self.assertContains(self.client.get(reverse("dashboard")), "en attente de validation")


@RAPIDE
class SecuriteEtErreursTests(TestCase):
    def test_csrf_actif_sur_le_login(self):
        make_pme("csrf")
        c = Client(enforce_csrf_checks=True)
        r = c.post(reverse("login_page"), {"username": "csrf@test.tn", "password": "pass12345"})
        self.assertEqual(r.status_code, 403)

    def test_page_404_personnalisee(self):
        r = self.client.get("/cette-page-n-existe-pas/")
        self.assertEqual(r.status_code, 404)
        self.assertContains(r, "Page introuvable", status_code=404)

    def test_page_403_personnalisee(self):
        u, _ = make_transporteur("forb")
        self.client.force_login(u)
        r = self.client.get(reverse("annonces:creer"))
        self.assertContains(r, "Vous n'avez pas le droit", status_code=403)

    def test_page_500_sans_dependance(self):
        from config.error_views import erreur_500
        from django.test import RequestFactory
        r = erreur_500(RequestFactory().get("/"))
        self.assertEqual(r.status_code, 500)
        self.assertIn("Erreur serveur", r.content.decode())

    def test_en_tetes_de_securite(self):
        r = self.client.get(reverse("login_page"))
        self.assertEqual(r["X-Frame-Options"], "DENY")
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")

    def test_acces_direct_par_url_impossible_sans_le_bon_role(self):
        """Contrôle d'accès: ni un PME ni un visiteur ne peuvent contourner les rôles en tapant l'URL."""
        u, pme = make_pme("bypass")
        d = make_demande(pme)
        for url in (reverse("propositions:vehicules"), reverse("propositions:matching"),
                    reverse("propositions:mes_propositions")):
            self.client.logout()
            self.assertEqual(self.client.get(url).status_code, 302, url)         # visiteur -> login
            self.client.force_login(u)
            self.assertEqual(self.client.get(url).status_code, 403, url)         # PME -> interdit
        self.assertEqual(self.client.get(reverse("propositions:proposer", args=[d.pk])).status_code, 403)

    def test_settings_prod_exigent_secret_key(self):
        import importlib
        import os
        from unittest import mock
        import config.settings as cfg
        env = {"DEBUG": "False", "SECRET_KEY": ""}
        with mock.patch.dict(os.environ, env):
            with self.assertRaises(RuntimeError):
                importlib.reload(cfg)
        importlib.reload(cfg)
