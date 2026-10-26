import os
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'ia_model.pkl')


def entrainer_modele():
    """Entraîne un classifieur de priorité sur un jeu équilibré (30 exemples)."""
    texts = [
        # ----- BASSE (10) -----
        "petit retard de livraison, rien de grave",
        "je voudrais juste avoir un suivi de mon colis",
        "question sur les horaires de livraison",
        "petite erreur de libellé sur l'adresse",
        "demande d'information sur ma facture",
        "le colis est arrivé un peu en retard mais tout va bien",
        "simple question sur le délai de traitement",
        "comment modifier mon adresse de livraison",
        "petit retard sans conséquence",
        "je souhaite recevoir un duplicata de facture",
        # ----- MOYENNE (10) -----
        "problème de facturation, montant incorrect",
        "erreur sur la facture, doublon",
        "retard de plusieurs jours",
        "le transporteur a livré à la mauvaise adresse",
        "marchandise partiellement endommagée",
        "problème avec un paiement non reçu",
        "colis livré dans un autre point relais",
        "facture non reçue après livraison",
        "transporteur en retard sans information",
        "erreur de poids sur le bon de livraison",
        # ----- HAUTE (10) -----
        "colis complètement écrasé, contenu cassé",
        "marchandise détruite, perte financière importante",
        "retard critique, client mécontent, pénalités",
        "le transporteur ne répond plus du tout",
        "colis perdu depuis une semaine",
        "colis volé ou disparu pendant le transport",
        "marchandise avariée, produit périssable perdu",
        "le colis est introuvable, client furieux",
        "livraison urgente non effectuée, blocage total",
        "colis endommagé et transporteur injoignable",
    ]
    labels = ['BASSE'] * 10 + ['MOYENNE'] * 10 + ['HAUTE'] * 10

    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
        ('clf', LogisticRegression(max_iter=2000, class_weight='balanced')),
    ])
    pipeline.fit(texts, labels)
    joblib.dump(pipeline, MODEL_PATH)
    return pipeline


def predire_priorite(description):
    """Prédit la priorité. Retourne MOYENNE si le modèle est incertain."""
    if not description:
        return 'MOYENNE'
    if not os.path.exists(MODEL_PATH):
        entrainer_modele()
    model = joblib.load(MODEL_PATH)
    proba = model.predict_proba([description])[0]
    classes = model.classes_
    max_proba = max(proba)
    prediction = classes[proba.argmax()]
    if max_proba < 0.35:
        return 'MOYENNE'
    return str(prediction)


def predire_priorite_avec_proba(description):
    """Retourne un dict {classe: probabilité}."""
    if not description:
        return {}
    if not os.path.exists(MODEL_PATH):
        entrainer_modele()
    model = joblib.load(MODEL_PATH)
    proba = model.predict_proba([description])[0]
    classes = model.classes_
    return dict(zip([str(c) for c in classes], [float(p) for p in proba]))


def suggerer_et_appliquer(reclamation):
    """Calcule la priorité IA et l'APPLIQUE au champ `priorite`.
    Retourne {priorite, probabilites, applique}.
    """
    if not reclamation.description:
        return {'priorite': reclamation.priorite, 'probabilites': {}, 'applique': False}
    suggestion = predire_priorite(reclamation.description)
    probabilites = predire_priorite_avec_proba(reclamation.description)
    reclamation.priorite = suggestion  # ← l'IA change la priorité automatiquement
    return {'priorite': suggestion, 'probabilites': probabilites, 'applique': True}