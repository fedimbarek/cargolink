from django.test import SimpleTestCase
from .recommandation import classer_profils


class TestsIA(SimpleTestCase):
    def test_recommande_le_profil_similaire(self):
        profils = ["Tunis Sfax meubles", "Bizerte Nabeul fruits"]
        resultat = classer_profils(profils, "Tunis Sfax meubles fragiles")
        self.assertEqual(resultat[0][0], 0)

    def test_sans_historique(self):
        self.assertEqual(classer_profils(["", ""], "Tunis meubles"), [])

    def test_sans_candidats(self):
        self.assertEqual(classer_profils([], "Tunis meubles"), [])

    def test_sans_similarite(self):
        self.assertEqual(classer_profils(["meubles"], "bananes"), [])

    def test_aucune_requete(self):
        self.assertEqual(classer_profils(["meubles"], ""), [])