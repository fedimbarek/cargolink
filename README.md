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

## Endpoints API
POST /api/auth/register/ | POST /api/auth/login/ | POST /api/auth/refresh/ | GET/PATCH /api/auth/me/
POST /ia/estimer/ (estimation de prix) | GET /ia/tache/<id>/ (suivi asynchrone) | GET /ia/modele/ (métriques)
