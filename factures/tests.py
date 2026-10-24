from datetime import timedelta
from decimal import Decimal

from django.db.models import ProtectedError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from annonces.models import DemandeTransport
from propositions.models import Proposition, Vehicle
from users.models import PME, Transporteur, User

from . import services
from .models import Facture, Paiement

RAPIDE = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])


def _user(name, role):
    return User.objects.create_user(username=name, email=f"{name}@test.tn", password="pass12345", role=role)


class Base:
    """1 PME, 2 transporteurs, 1 mission livrée (proposition acceptée, 450 TND HT) du transporteur `tr`."""

    def setUp(self):
        self.u_pme = _user("pme", "PME")
        self.pme = PME.objects.create(user=self.u_pme, company_name="Pme SA")
        self.u_tr = _user("tr", "TRANSPORTEUR")
        self.tr = Transporteur.objects.create(user=self.u_tr, company_name="Trans SARL", verified=True)
        self.u_tr2 = _user("tr2", "TRANSPORTEUR")
        self.tr2 = Transporteur.objects.create(user=self.u_tr2, company_name="Autre SARL", verified=True)
        self.u_admin = _user("adm", "ADMIN")
        self.vehicle = Vehicle.objects.create(transporteur=self.tr, registration_number="123 TUN 4567",
                                              capacity_weight=5000, capacity_volume=30)
        self.res = self._proposition(livree=True)

    def _proposition(self, livree=True, prix="450.00"):
        """Proposition ACCEPTÉE du transporteur `tr`; la demande est LIVRÉE si livree=True, sinon ANNULÉE
        (donc non facturable: seules les demandes assignées / en cours / livrées le sont, cf. STATUTS_FACTURABLES)."""
        now = timezone.now()
        demande = DemandeTransport.objects.create(
            pme=self.pme, origin="Tunis", destination="Sfax", weight=1000, cargo_type="Palettes",
            pickup_date=now + timedelta(days=2), delivery_date=now + timedelta(days=3),
            status=DemandeTransport.Status.DELIVERED if livree else DemandeTransport.Status.CANCELLED)
        return Proposition.objects.create(demande=demande, transporteur=self.tr, vehicle=self.vehicle,
                                          price=Decimal(prix), estimated_duration=6,
                                          status=Proposition.Status.ACCEPTED)

    def echeance(self, jours=30):
        return timezone.localdate() + timedelta(days=jours)

    def facture(self, emise=False):
        f = services.creer_facture(self.res, self.echeance())
        return services.emettre(f) if emise else f


@RAPIDE
class ModelEtServicesTests(Base, TestCase):
    def test_montants_tva_19(self):
        f = self.facture()
        self.assertEqual((f.montant_ht, f.montant_tva, f.total_ttc), (Decimal("450.00"), Decimal("85.50"), Decimal("535.50")))
        self.assertEqual(f.numero, f"FAC-{f.created_at.year}-{f.pk:05d}")
        self.assertEqual(f.reste_a_payer, Decimal("535.50"))

    def test_arrondi_au_centime(self):
        f = services.creer_facture(self._proposition(prix="100.03"), self.echeance(), taux_tva=Decimal("7"))
        self.assertEqual(f.montant_tva, Decimal("7.00"))      # 7.0021 -> 7.00
        self.assertEqual(f.total_ttc, Decimal("107.03"))

    def test_refus_mission_non_livree(self):
        r = self._proposition(livree=False)
        with self.assertRaises(services.ErreurFacture):
            services.creer_facture(r, self.echeance())
        r2 = self._proposition()                                             # livrée mais proposition non acceptée
        Proposition.objects.filter(pk=r2.pk).update(status=Proposition.Status.PENDING)
        r2.refresh_from_db()
        with self.assertRaises(services.ErreurFacture):
            services.creer_facture(r2, self.echeance())

    def test_une_seule_facture_par_proposition(self):
        self.facture()
        with self.assertRaises(services.ErreurFacture):
            services.creer_facture(self.res, self.echeance())

    def test_cycle_complet_statuts(self):
        f = self.facture()
        self.assertEqual(f.status, "BROUILLON")
        with self.assertRaises(services.ErreurFacture):                      # pas de paiement sur un brouillon
            services.enregistrer_paiement(f, Decimal("10"))
        f = services.emettre(f)
        self.assertEqual((f.status, f.emise_le is not None), ("EMISE", True))
        p1 = services.enregistrer_paiement(f, Decimal("200"))
        f.refresh_from_db(); self.assertEqual(f.status, "PARTIELLE")
        p2 = services.enregistrer_paiement(f, Decimal("335.50"))
        f.refresh_from_db(); self.assertEqual((f.status, f.reste_a_payer), ("PAYEE", Decimal("0.00")))
        services.supprimer_paiement(p2)
        f.refresh_from_db(); self.assertEqual(f.status, "PARTIELLE")
        services.supprimer_paiement(p1)
        f.refresh_from_db(); self.assertEqual(f.status, "EMISE")

    def test_paiement_ne_peut_pas_depasser_le_reste(self):
        f = self.facture(emise=True)
        with self.assertRaises(services.ErreurFacture):
            services.enregistrer_paiement(f, Decimal("535.51"))
        with self.assertRaises(services.ErreurFacture):
            services.enregistrer_paiement(f, Decimal("0"))
        self.assertEqual(f.paiements.count(), 0)

    def test_modifier_paiement_revalide_et_recalcule(self):
        f = self.facture(emise=True)
        p = services.enregistrer_paiement(f, Decimal("100"))
        services.modifier_paiement(p, montant=Decimal("535.50"))
        f.refresh_from_db(); self.assertEqual(f.status, "PAYEE")
        with self.assertRaises(services.ErreurFacture):
            services.modifier_paiement(p, montant=Decimal("600"))

    def test_annulation_et_suppression(self):
        f = self.facture(emise=True)
        services.enregistrer_paiement(f, Decimal("50"))
        with self.assertRaises(services.ErreurFacture):
            services.annuler(f)                                              # déjà un paiement
        with self.assertRaises(services.ErreurFacture):
            services.supprimer_facture(f)
        f2 = self._proposition()
        f2 = services.creer_facture(f2, self.echeance())
        services.annuler(f2)
        services.supprimer_facture(f2)
        self.assertFalse(Facture.objects.filter(pk=f2.pk).exists())

    def test_en_retard(self):
        f = self.facture(emise=True)
        self.assertFalse(f.en_retard)
        Facture.objects.filter(pk=f.pk).update(date_echeance=self.echeance(-1))
        f.refresh_from_db(); self.assertTrue(f.en_retard)


@RAPIDE
class FactureApiTests(Base, APITestCase):
    URL = "/api/factures/"

    def _creer(self, **extra):
        data = {"proposition": self.res.pk, "date_echeance": str(self.echeance())}
        data.update(extra)
        return self.client.post(self.URL, data, format="json")

    def test_crud_transporteur(self):
        self.client.force_authenticate(self.u_tr)
        rep = self._creer(notes="Merci")
        self.assertEqual(rep.status_code, 201, rep.data)
        self.assertEqual((rep.data["status"], rep.data["montant_ht"], rep.data["total_ttc"]), ("BROUILLON", "450.00", "535.50"))
        fid = rep.data["id"]
        rep = self.client.patch(f"{self.URL}{fid}/", {"montant_ht": "500.00", "taux_tva": "7"}, format="json")
        self.assertEqual((rep.status_code, rep.data["total_ttc"]), (200, "535.00"))
        self.assertEqual(self.client.get(f"{self.URL}{fid}/").status_code, 200)
        self.assertEqual(self.client.delete(f"{self.URL}{fid}/").status_code, 204)

    def test_creation_refusee(self):
        self.client.force_authenticate(self.u_pme)
        self.assertEqual(self._creer().status_code, 403)                     # rôle PME
        self.client.force_authenticate(self.u_tr2)
        self.assertEqual(self._creer().status_code, 400)                     # pas sa proposition
        self.client.force_authenticate(self.u_tr)
        self.assertEqual(self._creer(proposition=self._proposition(livree=False).pk).status_code, 400)
        self.assertEqual(self._creer(date_echeance=str(self.echeance(-3))).status_code, 400)
        self.assertEqual(self._creer(taux_tva="150").status_code, 400)
        self.assertEqual(self._creer().status_code, 201)
        self.assertEqual(self._creer().status_code, 400)                     # doublon

    def test_sans_authentification(self):
        self.assertEqual(self.client.get(self.URL).status_code, 401)

    def test_pme_ne_voit_pas_les_brouillons(self):
        f = self.facture()
        self.client.force_authenticate(self.u_pme)
        self.assertEqual(len(self.client.get(self.URL).data), 0)
        self.assertEqual(self.client.get(f"{self.URL}{f.pk}/").status_code, 404)
        services.emettre(f)
        self.assertEqual(len(self.client.get(self.URL).data), 1)
        self.assertEqual(self.client.get(f"{self.URL}{f.pk}/").data["transporteur"], "Trans SARL")

    def test_visibilite_par_role(self):
        f = self.facture(emise=True)
        for user, attendu in [(self.u_tr, 1), (self.u_tr2, 0), (self.u_admin, 1), (self.u_pme, 1)]:
            self.client.force_authenticate(user)
            self.assertEqual(len(self.client.get(self.URL).data), attendu, user.username)
        self.client.force_authenticate(self.u_tr2)
        self.assertEqual(self.client.get(f"{self.URL}{f.pk}/").status_code, 404)
        self.client.force_authenticate(self.u_tr)
        self.assertEqual(len(self.client.get(self.URL, {"status": "PAYEE"}).data), 0)

    def test_modification_interdite_apres_emission(self):
        f = self.facture(emise=True)
        self.client.force_authenticate(self.u_tr)
        self.assertEqual(self.client.patch(f"{self.URL}{f.pk}/", {"notes": "x"}, format="json").status_code, 400)
        self.assertEqual(self.client.delete(f"{self.URL}{f.pk}/").status_code, 400)
        self.client.force_authenticate(self.u_pme)
        self.assertEqual(self.client.patch(f"{self.URL}{f.pk}/", {"notes": "x"}, format="json").status_code, 403)

    def test_actions_emettre_annuler(self):
        f = self.facture()
        self.client.force_authenticate(self.u_pme)
        self.assertEqual(self.client.post(f"{self.URL}{f.pk}/emettre/").status_code, 403)
        self.client.force_authenticate(self.u_tr2)
        self.assertEqual(self.client.post(f"{self.URL}{f.pk}/emettre/").status_code, 404)
        self.client.force_authenticate(self.u_tr)
        rep = self.client.post(f"{self.URL}{f.pk}/emettre/")
        self.assertEqual((rep.status_code, rep.data["status"]), (200, "EMISE"))
        self.assertEqual(self.client.post(f"{self.URL}{f.pk}/emettre/").status_code, 400)
        rep = self.client.post(f"{self.URL}{f.pk}/annuler/")
        self.assertEqual((rep.status_code, rep.data["status"]), (200, "ANNULEE"))
        self.assertEqual(self.client.delete(f"{self.URL}{f.pk}/").status_code, 204)

    def test_proposition_facturee_est_protegee(self):
        self.facture()
        with self.assertRaises(ProtectedError):
            self.res.delete()


@RAPIDE
class PaiementApiTests(Base, APITestCase):
    URL = "/api/factures/paiements/"

    def setUp(self):
        super().setUp()
        self.f = self.facture(emise=True)

    def _payer(self, montant="100.00", **extra):
        data = {"facture": self.f.pk, "montant": montant, "mode": "CHEQUE", "reference": "CH-1"}
        data.update(extra)
        return self.client.post(self.URL, data, format="json")

    def test_crud_complet_et_statut_recalcule(self):
        self.client.force_authenticate(self.u_tr)
        rep = self._payer("100.00")
        self.assertEqual(rep.status_code, 201, rep.data)
        pid = rep.data["id"]
        self.f.refresh_from_db(); self.assertEqual(self.f.status, "PARTIELLE")
        rep = self.client.patch(f"{self.URL}{pid}/", {"montant": "535.50"}, format="json")
        self.assertEqual(rep.status_code, 200, rep.data)
        self.f.refresh_from_db(); self.assertEqual(self.f.status, "PAYEE")
        self.assertEqual(len(self.client.get(self.URL, {"facture": self.f.pk}).data), 1)
        self.assertEqual(self.client.delete(f"{self.URL}{pid}/").status_code, 204)
        self.f.refresh_from_db(); self.assertEqual(self.f.status, "EMISE")

    def test_validations(self):
        self.client.force_authenticate(self.u_tr)
        self.assertEqual(self._payer("999").status_code, 400)                # dépasse le reste
        self.assertEqual(self._payer("0").status_code, 400)
        self.assertEqual(self._payer(date_paiement=str(self.echeance(5))).status_code, 400)   # futur
        self.assertEqual(self.client.get(f"{self.URL}?facture=abc").status_code, 200)

    def test_droits(self):
        self.client.force_authenticate(self.u_pme)
        self.assertEqual(self._payer().status_code, 403)                     # la PME ne peut pas écrire
        self.client.force_authenticate(self.u_tr2)
        self.assertEqual(self._payer().status_code, 400)                     # pas sa facture
        self.client.force_authenticate(self.u_tr)
        pid = self._payer().data["id"]
        self.client.force_authenticate(self.u_pme)
        self.assertEqual(len(self.client.get(self.URL).data), 1)             # mais peut lire
        self.assertEqual(self.client.delete(f"{self.URL}{pid}/").status_code, 403)
        self.client.force_authenticate(self.u_tr2)
        self.assertEqual(self.client.get(f"{self.URL}{pid}/").status_code, 404)

    def test_paiement_refuse_sur_facture_annulee_ou_brouillon(self):
        brouillon = services.creer_facture(self._proposition(), self.echeance())
        self.client.force_authenticate(self.u_tr)
        self.assertEqual(self._payer(facture=brouillon.pk).status_code, 400)
        services.annuler(self.f)
        self.assertEqual(self._payer().status_code, 400)

    def test_deplacer_un_paiement_refuse(self):
        self.client.force_authenticate(self.u_tr)
        pid = self._payer().data["id"]
        autre = services.creer_facture(self._proposition(), self.echeance())
        self.assertEqual(self.client.patch(f"{self.URL}{pid}/", {"facture": autre.pk}, format="json").status_code, 400)


@RAPIDE
class WebTests(Base, TestCase):
    def test_liste_a_facturer_et_creation(self):
        self.client.force_login(self.u_tr)
        self.assertContains(self.client.get(reverse("factures:liste")), f"Demande #{self.res.demande_id}")
        self.assertEqual(self.client.get(reverse("factures:creer", args=[self.res.pk])).status_code, 200)
        rep = self.client.post(reverse("factures:creer", args=[self.res.pk]), {
            "montant_ht": "450.00", "taux_tva": "19", "date_echeance": str(self.echeance()), "notes": ""})
        f = Facture.objects.get()
        self.assertRedirects(rep, reverse("factures:detail", args=[f.pk]))
        self.assertContains(self.client.get(reverse("factures:detail", args=[f.pk])), "535,50")

    def test_creation_refusee_si_pas_livree_ou_pas_a_soi(self):
        self.client.force_login(self.u_tr)
        non_livree = self._proposition(livree=False)
        self.assertEqual(self.client.get(reverse("factures:creer", args=[non_livree.pk])).status_code, 302)
        self.assertFalse(Facture.objects.exists())
        self.client.force_login(self.u_tr2)
        self.assertEqual(self.client.get(reverse("factures:creer", args=[self.res.pk])).status_code, 404)
        self.client.force_login(self.u_pme)
        self.assertEqual(self.client.get(reverse("factures:creer", args=[self.res.pk])).status_code, 403)

    def test_parcours_complet_transporteur(self):
        self.client.force_login(self.u_tr)
        f = self.facture()
        self.client.post(reverse("factures:modifier", args=[f.pk]), {
            "montant_ht": "500.00", "taux_tva": "19", "date_echeance": str(self.echeance()), "notes": "ok"})
        f.refresh_from_db(); self.assertEqual(f.montant_ht, Decimal("500.00"))
        self.client.post(reverse("factures:emettre", args=[f.pk]))
        f.refresh_from_db(); self.assertEqual(f.status, "EMISE")
        self.assertEqual(self.client.get(reverse("factures:modifier", args=[f.pk])).status_code, 302)   # plus modifiable
        self.client.post(reverse("factures:paiement_ajouter", args=[f.pk]), {
            "montant": "100", "date_paiement": str(timezone.localdate()), "mode": "ESPECES", "reference": ""})
        p = Paiement.objects.get()
        f.refresh_from_db(); self.assertEqual(f.status, "PARTIELLE")
        self.assertEqual(self.client.get(reverse("factures:paiement_modifier", args=[p.pk])).status_code, 200)
        self.client.post(reverse("factures:paiement_modifier", args=[p.pk]), {
            "montant": "595.00", "date_paiement": str(timezone.localdate()), "mode": "VIREMENT", "reference": "V1"})
        f.refresh_from_db(); self.assertEqual(f.status, "PAYEE")
        self.client.post(reverse("factures:paiement_supprimer", args=[p.pk]))
        f.refresh_from_db(); self.assertEqual(f.status, "EMISE")
        self.client.post(reverse("factures:annuler", args=[f.pk]))
        self.client.post(reverse("factures:supprimer", args=[f.pk]))
        self.assertFalse(Facture.objects.exists())

    def test_paiement_trop_eleve_refuse(self):
        f = self.facture(emise=True)
        self.client.force_login(self.u_tr)
        self.client.post(reverse("factures:paiement_ajouter", args=[f.pk]), {
            "montant": "9999", "date_paiement": str(timezone.localdate()), "mode": "ESPECES", "reference": ""})
        self.assertFalse(Paiement.objects.exists())

    def test_la_pme_voit_la_facture_emise_pas_le_brouillon(self):
        f = self.facture()
        self.client.force_login(self.u_pme)
        self.assertEqual(self.client.get(reverse("factures:detail", args=[f.pk])).status_code, 404)
        services.emettre(f)
        rep = self.client.get(reverse("factures:detail", args=[f.pk]))
        self.assertContains(rep, f.numero)
        self.assertNotContains(rep, "Émettre la facture")                    # pas d'actions pour la PME
        self.assertContains(self.client.get(reverse("factures:liste")), f.numero)
        self.assertEqual(self.client.post(reverse("factures:emettre", args=[f.pk])).status_code, 403)

    def test_autre_transporteur_et_anonyme(self):
        f = self.facture(emise=True)
        self.client.force_login(self.u_tr2)
        self.assertEqual(self.client.get(reverse("factures:detail", args=[f.pk])).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("factures:liste")).status_code, 302)
        self.client.force_login(self.u_tr)
        self.assertContains(self.client.get(reverse("dashboard")), "Facturation")
