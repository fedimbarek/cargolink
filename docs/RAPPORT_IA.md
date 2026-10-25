# Rapport IA : estimation du prix d'un transport

## 1. Cas d'usage
CargoLink met en relation des PME et des transporteurs. Le prix est le point de friction :
la PME ne sait pas si une offre est correcte, le transporteur ne sait pas quoi proposer.
Le modèle (régression, scikit-learn) estime un prix à partir de la distance, du poids, du volume,
du type de marchandise (4 catégories) et de l'urgence.

| Écran | Apport |
|---|---|
| Création d'une demande (PME) | bouton « Estimer le prix » : budget probable + fourchette |
| Détail d'une demande | carte « Estimation IA du prix » |
| Proposer (transporteur) | prix conseillé + bouton « Utiliser ce prix » |
| Comparer les offres (PME) | colonne « Vs marché » : sous le marché / prix du marché / au-dessus |
| `/ia/modele/` | métriques, comparaison des modèles, importance des variables |

## 2. Données (point d'honnêteté)
La base ne contient aucun historique de transactions exploitable. Le jeu d'entraînement est donc **synthétique**
(3000 lignes, `ia/ml.py::generer_donnees`) : tarif non linéaire (rendements décroissants sur la distance,
suppléments frigorifique ×1,35 / fragile ×1,12 / dangereux ×1,5 / urgent ×1,18) avec un bruit multiplicatif de ±10 %.
Les propositions réellement acceptées sont ajoutées automatiquement dès qu'elles existent.

**Conséquence :** les métriques ci-dessous mesurent la capacité du modèle à retrouver la loi de prix
simulée, pas sa précision sur le vrai marché tunisien. À dire clairement au jury ; la parade est le
ré-entraînement sur données réelles (`python manage.py train_price_model`).

## 3. Méthode
1. Découpage 70 % entraînement / 15 % calibration / 15 % test (jamais vu).
2. Cible = log(prix) (erreurs relatives, prix toujours positifs).
3. Quatre modèles comparés par validation croisée à 5 plis : baseline (moyenne), régression linéaire (log-features),
   Random Forest, Gradient Boosting. Le meilleur RMSE de validation croisée est retenu.
4. Intervalle de prédiction à 90 % par « split conformal » sur le jeu de calibration.

## 4. Résultats (jeu de test, 450 lignes)
| Modèle | CV RMSE (log) | MAE (TND) | RMSE (TND) | R² | MAPE |
|---|---|---|---|---|---|
| Baseline (moyenne) | 0,624 | 132,6 | 210,9 | -0,09 | 49,9 % |
| Régression linéaire | 0,138 | 30,9 | 51,1 | 0,936 | 11,0 % |
| Random Forest | 0,129 | 28,6 | 46,2 | 0,948 | 9,9 % |
| **Gradient Boosting (retenu)** | **0,111** | **23,1** | **34,5** | **0,971** | **8,4 %** |

- Le modèle retenu se trompe en moyenne de 23 TND (8 %), contre 133 TND pour la baseline.
- Fourchette à 90 % : couverture réelle mesurée sur le test = **91,8 %** (objectif 90 %) : l'intervalle est bien calibré.
- La baseline a un R² négatif car elle prédit la moyenne géométrique (entraînement sur le log).
- Graphique prix réel vs prédit : `ia/static/ia/pred_vs_reel.png`.

## 5. Performance et asynchronisme
- Inférence : **~0,3 ms** par prédiction (modèle chargé une fois par processus, `lru_cache`).
- Le point lent est le calcul de distance (Nominatim + OSRM, quelques secondes) :
  - sans `REDIS_URL` : traitement synchrone (aucune dépendance en local) ;
  - avec `REDIS_URL` : `/ia/estimer/` répond **202 + task_id** et une tâche Celery (`ia/tasks.py`) calcule en arrière-plan ;
    le navigateur interroge `/ia/tache/<id>/` (voir `static/js/estimation.js`). Worker : `celery -A config worker -l info`.
- Sur les pages de détail / proposition / comparaison, la distance est déjà en base : aucun appel réseau.

## 6. Robustesse, sécurité, UX
- Clés et URLs en variables d'environnement ; aucune clé tierce dans le code (le modèle est local, pas d'API payante).
- Limitation de débit : 20 estimations/minute/utilisateur (HTTP 429) ; accès réservé aux rôles PME et transporteur.
- Entrées validées (`EstimationForm`) ; erreurs explicites (400 / 502 / 503) affichées dans une zone `role="alert"`.
- Chargement signalé (spinner + texte `role="status"` + `aria-busy`).
- Une panne du modèle ne casse jamais une page : l'estimation disparaît et l'erreur est journalisée.
- Modèle absent ou incompatible avec la version de scikit-learn : ré-entraîné automatiquement au premier appel.
- Le fichier `.joblib` est produit par notre propre commande (ne jamais charger un `.joblib` d'origine inconnue).

## 7. Limites
Données synthétiques ; pas de prise en compte de la saison, du carburant ni du retour à vide ; catégories de
marchandise déduites de mots-clés (texte libre). Pistes : ré-entraînement mensuel sur les propositions acceptées,
liste de catégories dans le formulaire.
