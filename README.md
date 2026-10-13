# CargoLink (StackUnity)

## Lancer le projet
    uv sync
    uv run python manage.py migrate
    uv run python manage.py createsuperuser
    uv run python manage.py runserver

## Endpoints users
POST /api/auth/register/ | POST /api/auth/login/ | POST /api/auth/refresh/ | GET/PATCH /api/auth/me/
