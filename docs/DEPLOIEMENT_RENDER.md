# Déploiement sur Render (suivi du guide du cours)

## Fichiers fournis
`requirements.txt`, `build.sh`, `render.yaml` (blueprint), `.env.example`, `.github/workflows/ci.yml` (intégration continue).

## Étapes
1. Pousser le projet sur GitHub (`git add . && git commit -m "..." && git push`) : **un commit par membre de l'équipe** (la grille note Git individuellement).
2. Render > **New > Blueprint** > choisir le dépôt : crée la base PostgreSQL `cargolink-db` et le service web.
   (Sans blueprint : New > Web Service, Build `./build.sh`, Start `python -m gunicorn config.asgi:application -k uvicorn_worker.UvicornWorker`.)
3. Dans le dashboard, renseigner `DJANGO_SUPERUSER_PASSWORD` (jamais dans Git). `SECRET_KEY` est générée, `DATABASE_URL` est injectée.
4. Déployer. `build.sh` exécute : `pip install`, `collectstatic`, `migrate`, entraînement du modèle IA, création de l'admin.
5. Vérifier : `https://<service>.onrender.com/login/`, puis `/admin/` et `/ia/modele/`.

## IA asynchrone (facultatif)
Créer un **Key Value** Render, copier son URL dans `REDIS_URL`, ajouter un *Background Worker* :
`celery -A config worker -l info`. Sans `REDIS_URL`, tout reste synchrone et fonctionnel.

## Intégration continue
À chaque push / pull request GitHub Actions lance : `check`, `makemigrations --check`, les tests avec couverture
(seuil 75 %), puis `check --deploy` avec `DEBUG=False`.

## Points d'attention
- Offre gratuite : le service s'endort après inactivité (premier chargement lent) ; la base gratuite expire.
- `db.sqlite3` n'est pas versionné (.gitignore) : les données de démo se créent via l'admin.
- Les fichiers téléversés ne persistent pas sur le disque éphémère de Render ; le projet n'en utilise pas.
