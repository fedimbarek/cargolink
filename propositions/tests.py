from decimal import Decimal
from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from annonces.models import DemandeTransport
from users.testing import (RAPIDE, make_demande, make_pme, make_proposition, make_transporteur, make_vehicle)

from . import services
from .forms import PropositionForm
from .models import Proposition


class VehiculeTests(TestCase):
    def setUp(self):
        _, self.pme = make_pme()
        _, self.t = make_transporteur()
        self.v = make_vehicle(self.t, weight=2000, volume=10)

    def test_capacite_poids(self):
        self.assertTrue(self.v.peut_transporter(make_demande(self.pme, weight=2000)))
        self.assertFalse(self.v.peut_transporter(make_demande(self.pme, weight=2001)))

    def test_capacite_volume(self):
        self.assertFalse(self.v.peut_transporter(make_demande(self.pme, weight=100, volume=11)))

    def test_taux_remplissage(self):
        self.assertEqual(self.v.taux_remplissage(make_demande(self.pme, weight=500)), 25.0)


class ContrainteTests(TestCase):
    def test_une_seule_proposition_active_par_transporteur(self):
        _, pme = make_pme()
        _, t = make_transporteur()
        d, v = make_demande(pme), make_vehicle(t)
        make_proposition(d, t, v)
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_proposition(d, t, v, price="300")

    def test_nouvelle_proposition_possible_apres_retrait(self):
        _, pme = make_pme()
        _, t = make_transporteur()
        d, v = make_demande(pme), make_vehicle(t)
        make_proposition(d, t, v, status="WITHDRAWN")
        make_proposition(d, t, v, price="300")
        self.assertEqual(d.propositions.count(), 2)

    def test_formulaire_refuse_vehicule_trop_petit(self):
        _, pme = make_pme()
        _, t = make_transporteur()
        petit = make_vehicle(t, weight=100, volume=1)
        d = make_demande(pme, weight=1000)
        f = PropositionForm({"vehicle": petit.pk, "price": "200", "estimated_duration": 3},
                            transporteur=t, demande=d)
        self.assertFalse(f.is_valid())
        self.assertIn("vehicle", f.errors)


@RAPIDE
class ServicesTests(TestCase):
    def setUp(self):
        _, self.pme = make_pme()
        _, self.t1 = make_transporteur("t1", rating="5.00")
        _, self.t2 = make_transporteur("t2", rating="2.00")
        self.v1, self.v2 = make_vehicle(self.t1, "A 1"), make_vehicle(self.t2, "B 2")
        self.d = make_demande(self.pme)
        self.p1 = make_proposition(self.d, self.t1, self.v1, price="500", duration=6)
        self.p2 = make_proposition(self.d, self.t2, self.v2, price="300", duration=4)

    def test_accepter_refuse_les_autres_et_assigne(self):
        services.accepter_proposition(self.p1)
        for p in (self.p1, self.p2, self.d):
            p.refresh_from_db()
        self.assertEqual((self.p1.status, self.p2.status, self.d.status), ("ACCEPTED", "REJECTED", "ASSIGNED"))

    def test_accepter_demande_non_ouverte(self):
        DemandeTransport.objects.filter(pk=self.d.pk).update(status="CANCELLED")
        with self.assertRaises(services.ErreurMetier):
            services.accepter_proposition(self.p1)

    def test_accepter_deux_fois_impossible(self):
        services.accepter_proposition(self.p1)
        with self.assertRaises(services.ErreurMetier):
            services.accepter_proposition(self.p1)

    @patch("propositions.services.taux_change", return_value=0.3)
    def test_comparaison_score_et_recommandation(self, _):
        lignes = services.comparer(self.d)
        self.assertEqual(len(lignes), 2)
        self.assertEqual([l["recommandee"] for l in lignes], [True, False])
        self.assertTrue(all(0 <= l["score"] <= 100 for l in lignes))
        self.assertEqual(lignes[0]["prix_eur"], Decimal("90.00") if lignes[0]["proposition"] == self.p2 else Decimal("150.00"))

    @patch("propositions.services.taux_change", return_value=None)
    def test_comparaison_sans_api_de_change(self, _):
        self.assertIsNone(services.comparer(self.d)[0]["prix_eur"])

    def test_comparaison_vide(self):
        self.assertEqual(services.comparer(make_demande(self.pme)), [])

    def test_matching_trie_par_taux_de_remplissage(self):
        gros = make_demande(self.pme, weight=4000)
        petit = make_demande(self.pme, weight=500)
        res = services.demandes_compatibles(self.t1)
        pks = [r["demande"].pk for r in res]
        self.assertLess(pks.index(gros.pk), pks.index(petit.pk))
        self.assertNotIn(self.d.pk, pks)                 # déjà une proposition active dessus

    @patch("propositions.services.requests.get")
    def test_taux_change_api_en_panne(self, get):
        import requests
        from django.core.cache import cache
        cache.clear()
        get.side_effect = requests.RequestException("boom")
        self.assertIsNone(services.taux_change("TND", "EUR"))


@RAPIDE
class VuesTests(TestCase):
    def setUp(self):
        self.u_pme, self.pme = make_pme()
        self.u_t, self.t = make_transporteur("t")
        self.u_nv, self.nv = make_transporteur("nv", verified=False)
        self.v = make_vehicle(self.t)
        self.d = make_demande(self.pme)

    def donnees(self, **kw):
        d = {"vehicle": self.v.pk, "price": "420", "estimated_duration": 5, "message": ""}
        d.update(kw)
        return d

    def test_transporteur_propose(self):
        self.client.force_login(self.u_t)
        r = self.client.post(reverse("propositions:proposer", args=[self.d.pk]), self.donnees())
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Proposition.objects.get().price, Decimal("420"))

    def test_proposition_double_refusee(self):
        make_proposition(self.d, self.t, self.v)
        self.client.force_login(self.u_t)
        self.client.post(reverse("propositions:proposer", args=[self.d.pk]), self.donnees())
        self.assertEqual(Proposition.objects.count(), 1)

    def test_transporteur_non_valide_ne_peut_pas_proposer(self):
        self.client.force_login(self.u_nv)
        self.client.post(reverse("propositions:proposer", args=[self.d.pk]), self.donnees())
        self.assertEqual(Proposition.objects.count(), 0)

    def test_pme_ne_peut_pas_proposer(self):
        self.client.force_login(self.u_pme)
        self.assertEqual(self.client.get(reverse("propositions:proposer", args=[self.d.pk])).status_code, 403)

    def test_pme_accepte_via_post(self):
        p = make_proposition(self.d, self.t, self.v)
        self.client.force_login(self.u_pme)
        self.assertEqual(self.client.get(reverse("propositions:accepter", args=[p.pk])).status_code, 405)
        self.client.post(reverse("propositions:accepter", args=[p.pk]))
        p.refresh_from_db()
        self.assertEqual(p.status, "ACCEPTED")

    def test_autre_pme_ne_peut_pas_accepter(self):
        p = make_proposition(self.d, self.t, self.v)
        autre, _ = make_pme("autre")
        self.client.force_login(autre)
        self.assertEqual(self.client.post(reverse("propositions:accepter", args=[p.pk])).status_code, 404)

    def test_retrait_proposition(self):
        p = make_proposition(self.d, self.t, self.v)
        self.client.force_login(self.u_t)
        self.client.post(reverse("propositions:retirer", args=[p.pk]))
        p.refresh_from_db()
        self.assertEqual(p.status, "WITHDRAWN")

    def test_suppression_vehicule_lie_a_une_proposition_interdite(self):
        make_proposition(self.d, self.t, self.v)
        self.client.force_login(self.u_t)
        self.client.post(reverse("propositions:vehicule_supprimer", args=[self.v.pk]))
        self.assertTrue(type(self.v).objects.filter(pk=self.v.pk).exists())

    def test_page_comparer_affiche_le_verdict_ia(self):
        make_proposition(self.d, self.t, self.v, price="100")
        self.client.force_login(self.u_pme)
        with patch("propositions.services.taux_change", return_value=0.3):
            r = self.client.get(reverse("propositions:comparer", args=[self.d.pk]))
        self.assertContains(r, "Vs marché")
        self.assertContains(r, "Sous le marché")
