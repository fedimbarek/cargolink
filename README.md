# CargoLink (StackUnity)

## Lancer le projet
    uv sync
    uv run python manage.py migrate
    uv run python manage.py createsuperuser
    uv run python manage.py runserver

Les notifications sont envoyées automatiquement via l'API Transactional Email de Brevo après validation de la transaction. Configurer `BREVO_API_KEY`, `BREVO_SENDER_EMAIL` (adresse d'expédition vérifiée dans Brevo), `BREVO_SENDER_NAME` (optionnel) et `SITE_URL` dans les variables d'environnement. Sans clé API et adresse d'expédition, l'email ne peut pas être envoyé ; la notification reste enregistrée dans CargoLink.

## Endpoints users
POST /api/auth/register/ | POST /api/auth/login/ | POST /api/auth/refresh/ | GET/PATCH /api/auth/me/
