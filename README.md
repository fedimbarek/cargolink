# CargoLink (StackUnity)

Plateforme Django de mise en relation PME / transporteurs : demandes de transport, propositions, comparaison des
offres, factures et paiements, alertes météo, et estimation de prix par machine learning.

## Lancer le projet
    cp .env.example .env
    uv sync                      # ou: pip install -r requirements-dev.txt
    uv lock                      # (une fois) régénère uv.lock après l'ajout des dépendances IA / déploiement
    python manage.py migrate
    python manage.py createsuperuser
    python manage.py runserver

Le modèle IA est fourni (`ia/artifacts/`). Pour le ré-entraîner : `python manage.py train_price_model`.

## Tests, couverture, qualité
    python manage.py test
    coverage run manage.py test && coverage report
    DEBUG=False SECRET_KEY=x ALLOWED_HOSTS=localhost python manage.py check --deploy

## Documentation
- `docs/RAPPORT_IA.md` : cas d'usage, données, métriques, asynchronisme
- `docs/ACCESSIBILITE.md` : mesures WCAG et audit
- `docs/DEPLOIEMENT_RENDER.md` : déploiement + CI
- `docs/CHECKLIST_GRILLE.md` : correspondance avec la grille d'évaluation
- `docs/QCM_CargoLink.md` : QCM de révision (cours + code)

En développement, `DJANGO_DEBUG` vaut `True` par défaut et une clé temporaire est générée si `DJANGO_SECRET_KEY` est absent. En production, définir `DJANGO_DEBUG=False`, `DJANGO_SECRET_KEY` avec une clé secrète forte et `DJANGO_ALLOWED_HOSTS` avec les noms d’hôte autorisés, séparés par des virgules.

Les notifications sont envoyées automatiquement via l'API Transactional Email de Brevo après validation de la transaction. Configurer `BREVO_API_KEY`, `BREVO_SENDER_EMAIL` (adresse d'expédition vérifiée dans Brevo), `BREVO_SENDER_NAME` (optionnel) et `SITE_URL` dans les variables d'environnement. Sans clé API et adresse d'expédition, l'email ne peut pas être envoyé ; la notification reste enregistrée dans CargoLink.

## Assistant IA des notifications
L'assistant local classe le texte des notifications lues en priorité `urgent`, `normal` ou `info`, puis affiche un conseil prédéfini à côté de chaque notification. Il ne génère pas de texte libre. Le modèle TF-IDF / régression logistique est entraîné sur des exemples synthétiques et répétitifs : les scores peuvent être artificiellement élevés et ne prouvent pas la qualité sur des messages réels. Le petit jeu manuel de contrôle ne remplace pas une validation réelle ; les conseils doivent être vérifiés par l'utilisateur.

Régénérer les données et entraîner le modèle après `uv sync` :

    uv run python -m ml.generer_donnees
    uv run python -m ml.entrainer

L'entraînement affiche les métriques sur un jeu synthétique séparé et sur des phrases manuelles, ainsi qu'un temps de prédiction indicatif. Le modèle local sauvegardé est `ml/modele_priorite.joblib`. Aucun message de notification n'est envoyé à un service IA externe.

## Endpoints users
POST /api/auth/register/ | POST /api/auth/login/ | POST /api/auth/refresh/ | GET/PATCH /api/auth/me/
POST /ia/estimer/ (estimation de prix) | GET /ia/tache/<id>/ (suivi asynchrone) | GET /ia/modele/ (métriques)
