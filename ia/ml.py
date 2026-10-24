"""
Module IA de CargoLink : estimation du prix d'un transport (régression, scikit-learn).

Cas d'usage (besoin réel de l'application) :
  - la PME sait si les offres reçues sont dans le marché (colonne « vs marché » dans la comparaison)
  - le transporteur reçoit un prix conseillé avant de proposer
  - la PME estime son budget avant de publier une demande

Données : l'application n'a pas (encore) d'historique de transactions exploitable, on génère donc un jeu
synthétique réaliste (voir generer_donnees) ; les propositions réellement acceptées sont ajoutées
automatiquement à l'entraînement dès qu'elles existent (charger_donnees_reelles).

Modèle : on compare 4 modèles (baseline, régression linéaire, random forest, gradient boosting) par
validation croisée, on garde le meilleur, et on fournit un intervalle de prédiction (méthode « split
conformal » sur un jeu de calibration) pour dire à l'utilisateur la fourchette de prix plausible.
"""
import json
import logging
import re
import time
from datetime import datetime, timezone as dt_timezone
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import sklearn
from django.conf import settings
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import cross_validate, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer

logger = logging.getLogger(__name__)

CATEGORIES = ["GENERAL", "FRIGO", "FRAGILE", "DANGEREUX"]
MOTS_CLES = {
    "FRIGO": r"frigo|froid|frais|surgel|congel|lait|viande|poisson|fromage|yaourt|legume|fruit",
    "DANGEREUX": r"danger|chimi|gaz|carburant|essence|acide|explosif|toxique|adr|inflammable",
    "FRAGILE": r"fragile|verre|vitre|cerami|porcelaine|electro|ordinateur|miroir|vitrage",
}
FEATURES = ["distance_km", "weight", "volume", "urgent"] + [f"cat_{c}" for c in CATEGORIES]
DENSITE_DEFAUT = 250.0            # kg/m³, utilisée quand le volume n'est pas renseigné
NIVEAU_INTERVALLE = 0.90
SEUIL_BAS, SEUIL_HAUT = 0.85, 1.15   # verdict d'une offre : rapport prix offert / prix estimé


def artifacts_dir():
    return Path(getattr(settings, "IA_ARTIFACTS_DIR", Path(__file__).resolve().parent / "artifacts"))


# ----------------------------------------------------------------- features
def categorie(cargo_type):
    """Le type de marchandise est un texte libre : on le ramène à 4 catégories par mots-clés."""
    texte = (cargo_type or "").lower()
    for cat in ("DANGEREUX", "FRIGO", "FRAGILE"):          # ordre = priorité
        if re.search(MOTS_CLES[cat], texte):
            return cat
    return "GENERAL"


def vecteur(distance_km, weight, volume, cargo_type, urgent=False):
    volume = float(volume) if volume else max(float(weight) / DENSITE_DEFAUT, 0.1)
    cat = categorie(cargo_type)
    return [float(distance_km), float(weight), volume, 1.0 if urgent else 0.0] + \
           [1.0 if cat == c else 0.0 for c in CATEGORIES]


# ----------------------------------------------------------------- données
def generer_donnees(n=3000, seed=42):
    """Jeu synthétique : tarif non linéaire (rendements décroissants sur la distance, supplément selon la
    catégorie et l'urgence) + bruit multiplicatif de ±10 %. Retourne (X, y)."""
    rng = np.random.default_rng(seed)
    distance = np.clip(rng.lognormal(5.0, 0.8, n), 15, 900)
    poids = np.clip(rng.lognormal(7.0, 1.1, n), 50, 24000)
    volume = np.clip(poids / 250 * rng.uniform(0.6, 1.6, n) + 0.5, 0.2, 90)
    cats = rng.choice(len(CATEGORIES), size=n, p=[0.6, 0.15, 0.15, 0.10])
    urgent = (rng.random(n) < 0.2).astype(float)

    par_km = 0.7 + 0.45 * (poids / 1000) ** 0.6 + 0.012 * volume
    tarif = 45 + par_km * distance ** 0.93
    tarif *= np.array([1.0, 1.35, 1.12, 1.5])[cats] * np.where(urgent == 1, 1.18, 1.0)
    prix = tarif * np.exp(rng.normal(0, 0.10, n))

    one_hot = np.eye(len(CATEGORIES))[cats]
    X = np.column_stack([distance, poids, volume, urgent, one_hot])
    return X, prix


def charger_donnees_reelles():
    """Propositions réellement acceptées (vérité terrain) : ajoutées à l'entraînement si disponibles."""
    from propositions.models import Proposition
    lignes, prix = [], []
    qs = Proposition.objects.filter(status=Proposition.Status.ACCEPTED, demande__distance_km__isnull=False
                                    ).select_related("demande")
    for p in qs:
        d = p.demande
        lignes.append(vecteur(d.distance_km, d.weight, d.volume, d.cargo_type, urgent=False))
        prix.append(float(p.price))
    if not lignes:
        return np.empty((0, len(FEATURES))), np.empty(0)
    return np.array(lignes), np.array(prix)


# ----------------------------------------------------------------- modèles
def _log_cols():
    return FunctionTransformer(np.log1p, feature_names_out="one-to-one")


def candidats():
    lineaire = make_pipeline(
        ColumnTransformer([("log", _log_cols(), [0, 1, 2])], remainder="passthrough"),
        LinearRegression())
    return {
        "Baseline (moyenne)": DummyRegressor(strategy="mean"),
        "Régression linéaire": lineaire,
        "Random Forest": RandomForestRegressor(n_estimators=200, min_samples_leaf=2, random_state=0, n_jobs=1),
        "Gradient Boosting": GradientBoostingRegressor(n_estimators=300, max_depth=3, learning_rate=0.05,
                                                       random_state=0),
    }


def _metriques(y_vrai, y_pred):
    return {
        "mae": round(float(mean_absolute_error(y_vrai, y_pred)), 2),
        "rmse": round(float(np.sqrt(mean_squared_error(y_vrai, y_pred))), 2),
        "r2": round(float(r2_score(y_vrai, y_pred)), 4),
        "mape": round(float(np.mean(np.abs(y_vrai - y_pred) / y_vrai) * 100), 2),
    }


def entrainer(n_synthetiques=3000, seed=42, avec_reelles=True, evaluer=True):
    """Entraîne, évalue et sauvegarde le modèle. Retourne le dictionnaire de métriques."""
    X, y = generer_donnees(n_synthetiques, seed)
    n_reel = 0
    if avec_reelles:
        try:
            Xr, yr = charger_donnees_reelles()
            n_reel = len(yr)
            if n_reel:
                X, y = np.vstack([X, Xr]), np.concatenate([y, yr])
        except Exception:                      # base non migrée, etc. : on continue en synthétique
            n_reel = 0

    # 70 % entraînement / 15 % calibration (intervalle) / 15 % test final jamais vu
    X_tr, X_rest, y_tr, y_rest = train_test_split(X, y, test_size=0.30, random_state=seed)
    X_cal, X_te, y_cal, y_te = train_test_split(X_rest, y_rest, test_size=0.50, random_state=seed)
    log_tr = np.log(y_tr)

    modeles, retenu_nom, meilleur_rmse = [], "Gradient Boosting", float("inf")
    if evaluer:
        for nom, modele in candidats().items():
            cv = cross_validate(modele, X_tr, log_tr, cv=5,
                                scoring=("neg_root_mean_squared_error", "r2"))
            cv_rmse = float(-cv["test_neg_root_mean_squared_error"].mean())
            modele.fit(X_tr, log_tr)
            pred = np.exp(modele.predict(X_te))
            ligne = {"nom": nom, "cv_rmse_log": round(cv_rmse, 4), "cv_r2": round(float(cv["test_r2"].mean()), 4)}
            ligne.update({f"test_{k}": v for k, v in _metriques(y_te, pred).items()})
            modeles.append(ligne)
            if nom != "Baseline (moyenne)" and cv_rmse < meilleur_rmse:
                meilleur_rmse, retenu_nom = cv_rmse, nom

    final = candidats()[retenu_nom]
    final.fit(X_tr, log_tr)

    # intervalle de prédiction « split conformal » sur l'échelle log (erreurs relatives)
    residus = np.log(y_cal) - final.predict(X_cal)
    alpha = (1 - NIVEAU_INTERVALLE) / 2
    q_bas, q_haut = float(np.quantile(residus, alpha)), float(np.quantile(residus, 1 - alpha))
    pred_te_log = final.predict(X_te)
    couverture = float(np.mean((np.log(y_te) >= pred_te_log + q_bas) & (np.log(y_te) <= pred_te_log + q_haut)))

    importances = {}
    estimateur = final[-1] if hasattr(final, "steps") else final
    if hasattr(estimateur, "feature_importances_"):
        importances = {f: round(float(v), 4) for f, v in zip(FEATURES, estimateur.feature_importances_)}
        importances = dict(sorted(importances.items(), key=lambda kv: -kv[1]))

    # latence d'inférence (ms) mesurée sur 200 prédictions unitaires
    durees = []
    for ligne in X_te[:200]:
        t0 = time.perf_counter()
        final.predict(ligne.reshape(1, -1))
        durees.append((time.perf_counter() - t0) * 1000)
    latence = {"moyenne_ms": round(float(np.mean(durees)), 2), "p95_ms": round(float(np.percentile(durees, 95)), 2)}

    pred_te = np.exp(pred_te_log)
    metriques = {
        "entraine_le": datetime.now(dt_timezone.utc).isoformat(timespec="seconds"),
        "sklearn": sklearn.__version__,
        "donnees": {"synthetiques": int(n_synthetiques), "reelles": int(n_reel),
                    "train": len(y_tr), "calibration": len(y_cal), "test": len(y_te)},
        "retenu": retenu_nom,
        "test_retenu": _metriques(y_te, pred_te),
        "modeles": modeles,
        "intervalle": {"niveau": NIVEAU_INTERVALLE, "couverture_test": round(couverture, 3),
                       "q_bas": round(q_bas, 4), "q_haut": round(q_haut, 4)},
        "importances": importances,
        "latence": latence,
    }

    dossier = artifacts_dir()
    dossier.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": final, "q_bas": q_bas, "q_haut": q_haut, "features": FEATURES,
                 "sklearn": sklearn.__version__, "retenu": retenu_nom}, dossier / "price_model.joblib")
    (dossier / "metrics.json").write_text(json.dumps(metriques, ensure_ascii=False, indent=2), encoding="utf-8")
    charger_modele.cache_clear()
    _tracer_graphique(y_te, pred_te, dossier)
    return metriques


def _tracer_graphique(y_vrai, y_pred, dossier):
    """Graphique prix réel vs prix prédit (facultatif : seulement si matplotlib est installé)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    fig, ax = plt.subplots(figsize=(5.2, 4.2), dpi=110)
    ax.scatter(y_vrai, y_pred, s=8, alpha=0.45, color="#0d6efd")
    m = float(max(y_vrai.max(), y_pred.max()))
    ax.plot([0, m], [0, m], color="#b02a37", lw=1.2, label="Prédiction parfaite")
    ax.set_xlabel("Prix réel (TND)")
    ax.set_ylabel("Prix prédit (TND)")
    ax.set_title("Jeu de test : prix réel vs prédit")
    ax.legend()
    fig.tight_layout()
    cible = Path(__file__).resolve().parent / "static" / "ia"
    cible.mkdir(parents=True, exist_ok=True)
    fig.savefig(cible / "pred_vs_reel.png")
    plt.close(fig)


# ----------------------------------------------------------------- inférence
@lru_cache(maxsize=1)
def charger_modele():
    """Charge le modèle une seule fois par processus. S'il est absent ou incompatible avec la version de
    scikit-learn installée, on le ré-entraîne rapidement (sans évaluation) au lieu de planter."""
    chemin = artifacts_dir() / "price_model.joblib"
    try:
        paquet = joblib.load(chemin)
        if paquet.get("features") != FEATURES:
            raise ValueError("features différentes")
        return paquet
    except Exception:
        entrainer(n_synthetiques=2000, avec_reelles=False, evaluer=False)
        return joblib.load(chemin)


def estimer(distance_km, weight, volume=None, cargo_type="", urgent=False):
    """Prix estimé (TND) + fourchette à 90 %. Lève ValueError si les entrées sont invalides."""
    if not distance_km or float(distance_km) <= 0 or not weight or float(weight) <= 0:
        raise ValueError("Distance et poids doivent être strictement positifs.")
    t0 = time.perf_counter()
    paquet = charger_modele()
    x = np.array(vecteur(distance_km, weight, volume, cargo_type, urgent)).reshape(1, -1)
    log_prix = float(paquet["model"].predict(x)[0])
    prix = float(np.exp(log_prix))
    return {
        "prix": round(prix, 2),
        "bas": round(float(np.exp(log_prix + paquet["q_bas"])), 2),
        "haut": round(float(np.exp(log_prix + paquet["q_haut"])), 2),
        "prix_km": round(prix / float(distance_km), 2),
        "categorie": categorie(cargo_type),
        "modele": paquet["retenu"],
        "temps_ms": round((time.perf_counter() - t0) * 1000, 2),
    }


def estimer_demande(demande):
    """Estimation pour une DemandeTransport déjà enregistrée (aucun appel réseau). None si pas de distance."""
    if not demande.distance_km:
        return None
    from django.utils import timezone
    urgent = bool(demande.pickup_date and (demande.pickup_date - timezone.now()).total_seconds() < 48 * 3600)
    try:
        return estimer(demande.distance_km, demande.weight, demande.volume, demande.cargo_type, urgent)
    except Exception:           # l'IA est un plus: une panne du modèle ne doit jamais casser la page
        logger.exception("Estimation IA impossible pour la demande %s", getattr(demande, "pk", "?"))
        return None


def verdict(prix_offert, estimation):
    """Compare le prix d'une offre au prix estimé : (code, libellé, classe Bootstrap)."""
    if not estimation or not estimation["prix"]:
        return None
    rapport = float(prix_offert) / estimation["prix"]
    if rapport < SEUIL_BAS:
        return ("BAS", "Sous le marché", "bg-info text-dark")
    if rapport > SEUIL_HAUT:
        return ("HAUT", "Au-dessus du marché", "bg-warning text-dark")
    return ("OK", "Prix du marché", "bg-success")


def lire_metriques():
    """Métriques de la dernière exécution de l'entraînement (None si jamais entraîné)."""
    chemin = artifacts_dir() / "metrics.json"
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
