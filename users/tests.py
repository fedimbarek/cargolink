from rest_framework.test import APITestCase


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
        from users.models import User
        self.assertEqual(User.objects.get(email="tr@t.tn").status, "PENDING")

    def test_me_requires_login(self):
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
