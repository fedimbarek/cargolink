from time import perf_counter
from django.core.management.base import BaseCommand
from chauffeurs.recommandation import classer_profils


class Command(BaseCommand):
    help = "Évaluer la recommandation sur de petits exemples fictifs."

    def handle(self, *args, **options):
        profils = [
            "Tunis Sfax meubles mobilier cartons",
            "Bizerte Nabeul fruits legumes frais",
            "Sousse Gabes materiaux ciment construction",
        ]
        exemples = [
            ("Tunis Sfax livraison de meubles", 0),
            ("Transport de mobilier en cartons", 0),
            ("Livraison de fruits et legumes", 1),
            ("Produits frais Bizerte Nabeul", 1),
            ("Transport ciment construction", 2),
            ("Materiaux Sousse Gabes", 2),
            ("Ordinateurs batteries electronique", None),
        ]
        debut = perf_counter()
        corrects = 0
        for texte, attendu in exemples:
            resultat = classer_profils(profils, texte)
            obtenu = resultat[0][0] if resultat else None
            corrects += obtenu == attendu
            self.stdout.write(f"{texte} : attendu={attendu}, obtenu={obtenu}")
        duree = (perf_counter() - debut) * 1000
        self.stdout.write(f"Réponses conformes : {corrects}/{len(exemples)}")
        self.stdout.write(f"Temps moyen : {duree / len(exemples):.2f} ms")
        self.stdout.write("Données fictives : ce résultat ne mesure pas la qualité réelle.")