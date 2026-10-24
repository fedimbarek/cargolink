# Ce qui a été ajouté / modifié

## Nouveau
- `ia/` : app d'estimation de prix (ml.py, services, tâche Celery, vues, commande `train_price_model`, page `/ia/modele/`, modèle entraîné dans `ia/artifacts/`)
- `config/celery.py`, `config/error_views.py`, `templates/errors/` (403, 404, 500), `templates/includes/field.html`
- `static/css/cargolink.css`, `static/js/estimation.js`, `static/js/prix-conseille.js`
- Tests : `annonces/tests.py`, `propositions/tests.py`, `meteo/tests.py`, `ia/tests.py`, `config/test_accessibilite.py`, `users/testing.py` (fabriques)
- Déploiement / CI : `requirements*.txt`, `build.sh`, `render.yaml`, `.env.example`, `.github/workflows/ci.yml`, `.coveragerc`
- `docs/` (rapport IA, accessibilité, déploiement, grille, QCM)

## Modifié
- `config/settings.py` : variables d'environnement (SECRET_KEY, DEBUG, ALLOWED_HOSTS, DATABASE_URL), WhiteNoise, PostgreSQL via `dj_database_url`, sécurité de production, throttling DRF, Celery, langue `fr` / fuseau `Africa/Tunis`, e-mail SMTP en production, journalisation
- `config/urls.py` : route `ia/` + handlers 403/404/500
- `templates/base.html` et tous les templates : accessibilité (titres, tableaux, champs, ARIA)
- `annonces/views.py`, `propositions/views.py` : estimation IA dans le détail, la proposition et la comparaison
- Templates annonces / propositions : panneau IA, colonne « Vs marché »
- `factures/tests.py` : 3 tests corrigés (ils supposaient que seule une demande LIVRÉE est facturable alors que le service accepte aussi ASSIGNÉE / EN COURS) et format décimal français (`535,50`)
- `pyproject.toml`, `README.md`, `.gitignore`

## Comportements à connaître
- La langue est passée en français : les nombres s'affichent avec une virgule.
- `DEBUG` vaut True par défaut en local ; sur Render la variable `DEBUG=False` est fournie par `render.yaml`.
- `uv.lock` doit être régénéré : `uv lock`.
