from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import Client, TestCase, tag
from django.urls import reverse
from django.utils import timezone

from users.testing import (
    RAPIDE, make_demande, make_pme, make_proposition,
    make_transporteur, make_vehicle,
)
from .models import Affectation, Chauffeur, Permis


@RAPIDE
class TestsIntegration(TestCase):
    def setUp(self):
        self.user, self.transporteur = make_transporteur()
        self.autre_user, self.autre_transporteur = make_transporteur("autre")
        self.pme_user, pme = make_pme()
        demande = make_demande(pme)
        vehicule = make_vehicle(self.transporteur)
        self.offre = make_proposition(
            demande, self.transporteur, vehicule, status="ACCEPTED"
        )
        self.chauffeur = Chauffeur.objects.create(
            transporteur=self.transporteur, nom="Ben Ali",
            prenom="Ahmed", telephone="22123456",
        )
        self.permis = Permis.objects.create(
            chauffeur=self.chauffeur, numero="TEST-001", categorie="C",
            date_expiration=timezone.localdate() + timedelta(days=365),
        )
        self.client.force_login(self.user)

    def donnees_chauffeur(self):
        return {
            "nom": "Nouveau", "prenom": "Sami", "telephone": "22345678",
            "disponible": "on", "numero": "TEST-002", "categorie": "C",
            "date_expiration": str(timezone.localdate() + timedelta(days=365)),
        }

    def affecter(self):
        return self.client.post(reverse("chauffeurs:affecter"), {
            "proposition": self.offre.pk, "chauffeur": self.chauffeur.pk,
        })

    def test_visiteur_redirige(self):
        self.client.logout()
        reponse = self.client.get(reverse("chauffeurs:liste"))
        self.assertEqual(reponse.status_code, 302)
        self.assertIn(reverse("login_page"), reponse.url)

    def test_pme_interdite(self):
        self.client.force_login(self.pme_user)
        reponse = self.client.get(reverse("chauffeurs:liste"))
        self.assertEqual(reponse.status_code, 403)

    def test_liste_limitee_au_proprietaire(self):
        self.client.force_login(self.autre_user)
        reponse = self.client.get(reverse("chauffeurs:liste"))
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(list(reponse.context["chauffeurs"]), [])

    def test_recherche(self):
        reponse = self.client.get(reverse("chauffeurs:liste"), {"q": "Ahmed"})
        self.assertEqual(list(reponse.context["chauffeurs"]), [self.chauffeur])

    def test_ajout_chauffeur_et_permis(self):
        reponse = self.client.post(
            reverse("chauffeurs:ajouter"), self.donnees_chauffeur()
        )
        self.assertRedirects(reponse, reverse("chauffeurs:liste"))
        nouveau = Chauffeur.objects.get(nom="Nouveau")
        self.assertEqual(nouveau.transporteur, self.transporteur)
        self.assertEqual(nouveau.permis.numero, "TEST-002")

    def test_permis_invalide_aucun_ajout(self):
        donnees = self.donnees_chauffeur()
        donnees["numero"] = "TEST-001"
        reponse = self.client.post(reverse("chauffeurs:ajouter"), donnees)
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("numero", reponse.context["permis_form"].errors)
        self.assertEqual(Chauffeur.objects.count(), 1)
        self.assertEqual(Permis.objects.count(), 1)

    def test_modification(self):
        donnees = self.donnees_chauffeur()
        donnees["numero"] = self.permis.numero
        reponse = self.client.post(
            reverse("chauffeurs:modifier", args=[self.chauffeur.pk]), donnees
        )
        self.assertRedirects(reponse, reverse("chauffeurs:liste"))
        self.chauffeur.refresh_from_db()
        self.assertEqual(self.chauffeur.nom, "Nouveau")
        self.assertEqual(Permis.objects.count(), 1)

    def test_modification_autre_transporteur_refusee(self):
        self.client.force_login(self.autre_user)
        reponse = self.client.post(
            reverse("chauffeurs:modifier", args=[self.chauffeur.pk]),
            self.donnees_chauffeur(),
        )
        self.assertEqual(reponse.status_code, 404)
        self.chauffeur.refresh_from_db()
        self.assertEqual(self.chauffeur.nom, "Ben Ali")

    def test_get_ne_supprime_pas(self):
        reponse = self.client.get(
            reverse("chauffeurs:supprimer", args=[self.chauffeur.pk])
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(Chauffeur.objects.filter(pk=self.chauffeur.pk).exists())

    def test_suppression_avec_permis(self):
        reponse = self.client.post(
            reverse("chauffeurs:supprimer", args=[self.chauffeur.pk])
        )
        self.assertRedirects(reponse, reverse("chauffeurs:liste"))
        self.assertEqual(Chauffeur.objects.count(), 0)
        self.assertEqual(Permis.objects.count(), 0)

    def test_affectation_rend_indisponible(self):
        reponse = self.affecter()
        self.assertRedirects(reponse, reverse("chauffeurs:affecter"))
        self.chauffeur.refresh_from_db()
        self.assertFalse(self.chauffeur.disponible)
        self.assertTrue(Affectation.objects.filter(
            chauffeur=self.chauffeur, proposition=self.offre
        ).exists())

    def test_permis_expire_refuse(self):
        self.permis.date_expiration = timezone.localdate() - timedelta(days=1)
        self.permis.save()
        reponse = self.affecter()
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("chauffeur", reponse.context["form"].errors)
        self.assertEqual(Affectation.objects.count(), 0)

    def test_chauffeur_indisponible_refuse(self):
        self.chauffeur.disponible = False
        self.chauffeur.save()
        self.affecter()
        self.assertEqual(Affectation.objects.count(), 0)

    def test_chauffeur_autre_transporteur_refuse(self):
        self.chauffeur.transporteur = self.autre_transporteur
        self.chauffeur.save()
        self.affecter()
        self.assertEqual(Affectation.objects.count(), 0)

    def test_offre_non_acceptee_refusee(self):
        self.offre.status = "PENDING"
        self.offre.save()
        self.affecter()
        self.assertEqual(Affectation.objects.count(), 0)

    def test_suppression_chauffeur_affecte_bloquee(self):
        self.affecter()
        reponse = self.client.post(
            reverse("chauffeurs:supprimer", args=[self.chauffeur.pk])
        )
        self.assertRedirects(reponse, reverse("chauffeurs:liste"))
        self.assertTrue(Chauffeur.objects.filter(pk=self.chauffeur.pk).exists())

    def test_un_seul_permis_par_chauffeur(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Permis.objects.create(
                    chauffeur=self.chauffeur, numero="AUTRE", categorie="C",
                    date_expiration=timezone.localdate(),
                )

    def test_une_seule_affectation_par_offre(self):
        Affectation.objects.create(chauffeur=self.chauffeur, proposition=self.offre)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Affectation.objects.create(
                    chauffeur=self.chauffeur, proposition=self.offre
                )

    def test_csrf_obligatoire(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        reponse = client.post(
            reverse("chauffeurs:ajouter"), self.donnees_chauffeur()
        )
        self.assertEqual(reponse.status_code, 403)

    @tag("ia")
    def test_page_ia_sans_historique(self):
        reponse = self.client.get(reverse("chauffeurs:recommandation"), {
            "mission": self.offre.pk,
        })
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.context["resultats"], [])
        self.assertContains(reponse, "Aucun historique similaire")

    @tag("ia")
    def test_page_ia_autre_transporteur_refusee(self):
        self.client.force_login(self.autre_user)
        reponse = self.client.get(reverse("chauffeurs:recommandation"), {
            "mission": self.offre.pk,
        })
        self.assertEqual(reponse.status_code, 404)

    @tag("ia")
    def test_page_ia_avec_historique_termine(self):
        historique = make_demande(self.offre.demande.pme, status="DELIVERED")
        ancienne_offre = make_proposition(
            historique, self.transporteur, self.offre.vehicle, status="ACCEPTED"
        )
        Affectation.objects.create(
            proposition=ancienne_offre, chauffeur=self.chauffeur
        )
        reponse = self.client.get(reverse("chauffeurs:recommandation"), {
            "mission": self.offre.pk,
        })
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(
            reponse.context["resultats"][0]["chauffeur"], self.chauffeur
        )

    @tag("ia")
    def test_page_ia_ignore_permis_expire(self):
        self.permis.date_expiration = timezone.localdate() - timedelta(days=1)
        self.permis.save()
        reponse = self.client.get(reverse("chauffeurs:recommandation"), {
            "mission": self.offre.pk,
        })
        self.assertEqual(reponse.context["resultats"], [])