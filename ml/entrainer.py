from pathlib import Path
from time import perf_counter

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.feature_selection import SelectPercentile, chi2
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import FeatureUnion, Pipeline


DOSSIER = Path(__file__).resolve().parent
CHEMIN_DONNEES = DOSSIER / "donnees.csv"
CHEMIN_MODELE = DOSSIER / "modele_priorite.joblib"
CLASSES = ["urgent", "normal", "info"]

EXEMPLES_MANUELS = [
    ("Alerte : la cargaison est endommagée et le camion ne peut plus rouler.", "urgent"),
    ("Suivi Sousse vers Gabès : incident / retard pour la réservation #41 - le véhicule est en panne.", "urgent"),
    ("Le colis de la réservation #19 sur Tunis vers Nabeul est perdu.", "urgent"),
    ("Un problème bloque le transport de la commande #27 de Sfax vers Tunis.", "urgent"),
    ("Nouvelle offre pour votre demande #41 sur le trajet Sousse vers Gabès, comparez les prix.", "normal"),
    ("Veuillez vérifier la nouvelle proposition liée à la demande #63 de Tunis vers Nabeul.", "normal"),
    ("Le transporteur demande une nouvelle date pour la réservation #19 de Sfax vers Tunis.", "normal"),
    ("Un justificatif est nécessaire pour finaliser la mission #27 de Monastir à Tunis.", "normal"),
    ("La réservation #41 pour Sousse vers Gabès vient d’être confirmée.", "info"),
    ("Le véhicule a démarré et transporte votre commande de Tunis à Nabeul.", "info"),
    ("Votre chargement est arrivé à destination, la mission est terminée.", "info"),
    ("Le suivi du transport #19 de Sfax vers Tunis indique que le camion est en route.", "info"),
]


def main():
    if not CHEMIN_DONNEES.is_file():
        raise FileNotFoundError(
            f"{CHEMIN_DONNEES} est introuvable. "
            "Lancez d'abord `uv run python -m ml.generer_donnees`."
        )

    donnees = pd.read_csv(CHEMIN_DONNEES)
    if not {"texte", "statut", "groupe"}.issubset(donnees.columns) or donnees.empty:
        raise ValueError("Le CSV doit contenir des colonnes texte, statut et groupe non vides.")
    if donnees[["texte", "statut", "groupe"]].isna().any().any():
        raise ValueError("Les colonnes texte, statut et groupe ne doivent pas contenir de valeurs vides.")
    if set(donnees["statut"]) != set(CLASSES):
        raise ValueError(f"Les étiquettes attendues sont : {', '.join(CLASSES)}.")

    indices_test = set()
    repartition_groupes = []
    for statut in CLASSES:
        indices_classe = donnees.index[donnees["statut"] == statut]
        groupes_classe = donnees.loc[indices_classe, "groupe"]
        separation = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)
        indices_train, indices_validation = next(
            separation.split(donnees.loc[indices_classe, "texte"], donnees.loc[indices_classe, "statut"],
                             groups=groupes_classe)
        )
        indices_test.update(donnees.loc[indices_classe].iloc[indices_validation].index)
        repartition_groupes.append(
            (statut, len(set(groupes_classe.iloc[indices_train])),
             len(set(groupes_classe.iloc[indices_validation])))
        )

    masque_test = donnees.index.isin(indices_test)
    entrainement = donnees.loc[~masque_test]
    validation = donnees.loc[masque_test]

    modele = Pipeline([
        ("caracteristiques", FeatureUnion([
            ("mots", TfidfVectorizer(
                analyzer="word",
                ngram_range=(1, 2),
                strip_accents="unicode",
                sublinear_tf=True,
            )),
            ("caracteres", TfidfVectorizer(
                analyzer="char_wb",
                ngram_range=(3, 5),
                min_df=2,
                sublinear_tf=True,
            )),
        ])),
        ("selection", SelectPercentile(chi2, percentile=80)),
        ("classification", LogisticRegression(
            C=2.0,
            class_weight="balanced",
            max_iter=2000,
            random_state=42,
        )),
    ])
    modele.fit(entrainement["texte"], entrainement["statut"])

    predictions_test = modele.predict(validation["texte"])
    print("Évaluation par scénarios tenus à l'écart de l'entraînement :")
    print("Groupes entraînement/validation par priorité :", repartition_groupes)
    print(classification_report(
        validation["statut"],
        predictions_test,
        labels=CLASSES,
        zero_division=0,
    ))
    print("Matrice de confusion (lignes = réalité, colonnes = prédiction) :")
    print(confusion_matrix(validation["statut"], predictions_test, labels=CLASSES))

    textes_manuels, statuts_manuels = zip(*EXEMPLES_MANUELS)
    debut = perf_counter()
    predictions_manuelles = modele.predict(list(textes_manuels))
    probabilites_manuelles = modele.predict_proba(list(textes_manuels)).max(axis=1)
    duree_ms = (perf_counter() - debut) * 1000
    print("\nContrôle séparé sur des phrases rédigées manuellement :")
    print(classification_report(
        statuts_manuels,
        predictions_manuelles,
        labels=CLASSES,
        zero_division=0,
    ))
    print(
        f"Prédiction des {len(textes_manuels)} exemples manuels : "
        f"{duree_ms:.2f} ms au total."
    )
    print(
        "Confiance moyenne sur ces exemples manuels : "
        f"{probabilites_manuelles.mean() * 100:.1f} %."
    )

    modele.fit(donnees["texte"], donnees["statut"])
    joblib.dump(modele, CHEMIN_MODELE)
    print(f"Modèle sauvegardé dans {CHEMIN_MODELE}.")


if __name__ == "__main__":
    main()
