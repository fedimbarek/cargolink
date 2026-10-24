#!/usr/bin/env bash
# Script de build exécuté par Render à chaque déploiement (exit on error)
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate --no-input

# (ré)entraîne le modèle IA avec la version de scikit-learn installée sur le serveur (quelques secondes)
python manage.py train_price_model --sans-reelles

# crée le super-utilisateur à partir des variables DJANGO_SUPERUSER_* (ignoré s'il existe déjà)
if [[ -n "${DJANGO_SUPERUSER_EMAIL}" ]]; then
  python manage.py createsuperuser --no-input || true
fi
