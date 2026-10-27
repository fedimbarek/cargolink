import random
from itertools import product
from pathlib import Path

import pandas as pd


random.seed(42)

TRAJETS = [
    "Tunis vers Sfax",
    "Sousse vers Monastir",
    "Monastir vers Tunis",
    "Nabeul vers Gabès",
]
IDS = [3, 6, 8, 12, 17]

EXEMPLES = {
    "urgent": [
        ("incident_retard", "Suivi {trajet} : incident / retard pour la réservation #{id} - {probleme}."),
        ("incident_reservation", "Incident signalé pour la réservation #{id} sur {trajet} : {probleme}."),
        ("cargaison_bloquee", "Cargaison bloquée ou endommagée pour la réservation #{id} sur {trajet} : {probleme}."),
        ("accident_chauffeur", "Accident signalé pendant le transport de la réservation #{id} sur {trajet}."),
        ("marchandise_endommagee", "Marchandise endommagée signalée pour la réservation #{id} sur {trajet}."),
        ("colis_perdu", "Colis perdu pendant le transport de la réservation #{id} sur {trajet}."),
        ("retard_important", "Plusieurs jours de retard pour la livraison de la réservation #{id} sur {trajet}."),
        ("transporteur_injoignable", "Transporteur injoignable, livraison bloquée pour la réservation #{id} sur {trajet}."),
    ],
    "normal": [
        ("proposition_recue", "Nouvelle proposition reçue pour votre demande #{id}, trajet {trajet}."),
        ("offre_a_comparer", "Un transporteur a envoyé une offre pour la demande #{id} ({trajet}) : comparez la proposition."),
        ("offre_a_valider", "Une proposition attend votre validation pour la demande #{id} ({trajet})."),
        ("modification_date", "Une modification de date est demandée pour la réservation #{id} ({trajet})."),
        ("modification_adresse", "Un changement d'adresse est demandé pour la réservation #{id} ({trajet})."),
        ("demande_renseignement", "Une réponse sur votre demande #{id} ({trajet}) est disponible, veuillez la consulter."),
        ("document_a_fournir", "Un document manque pour finaliser la réservation #{id} ({trajet})."),
        ("confirmation_requise", "Veuillez confirmer les détails de la réservation #{id} ({trajet}) avant le départ."),
    ],
    "info": [
        ("reservation_confirmee", "Votre réservation #{id} pour {trajet} est confirmée."),
        ("proposition_confirmee", "Statut : proposition confirmée pour la réservation #{id} ({trajet})."),
        ("marchandise_en_route", "Votre marchandise pour la réservation #{id} ({trajet}) est en route."),
        ("etape_en_route", "Suivi de la réservation #{id} ({trajet}) : en route."),
        ("livraison_terminee", "La livraison de votre réservation #{id} ({trajet}) est terminée."),
        ("livraison_recue", "Votre réservation #{id} pour {trajet} a été livrée. Pensez à évaluer le transporteur."),
        ("reservation_annulee", "La réservation #{id} pour {trajet} a été annulée."),
        ("service_remercie", "Merci pour votre confiance, le transport de la réservation #{id} ({trajet}) s'est bien déroulé."),
    ],
}

PROBLEMES = [
    "le camion est immobilisé",
    "le véhicule est bloqué",
    "le chauffeur signale un incident",
    "la marchandise est endommagée",
    "la cargaison est abîmée",
    "la marchandise ne peut pas avancer",
]


def main():
    lignes = []
    for statut, scenarios in EXEMPLES.items():
        for groupe, modele in scenarios:
            for index, (trajet, identifiant) in enumerate(product(TRAJETS, IDS)):
                if "{probleme}" in modele:
                    texte = modele.format(
                        trajet=trajet,
                        id=identifiant,
                        probleme=PROBLEMES[index % len(PROBLEMES)],
                    )
                else:
                    texte = modele.format(trajet=trajet, id=identifiant)
                lignes.append({"texte": texte, "statut": statut, "groupe": groupe})

    chemin = Path(__file__).with_name("donnees.csv")
    donnees = pd.DataFrame(lignes).drop_duplicates(subset="texte")
    donnees.to_csv(chemin, index=False)
    print(f"{len(donnees)} exemples CargoLink enregistrés dans {chemin}.")
    print("Exemples par priorité :", donnees["statut"].value_counts().to_dict())


if __name__ == "__main__":
    main()
