"""
API externes utilisées par le module annonces :
  - Nominatim (OpenStreetMap) : transformer une ville en coordonnées GPS
  - OSRM (routage)            : distance et durée routière entre 2 points
Aucune clé API n'est nécessaire. En cas de panne, on retourne None (l'application continue de marcher).
"""
import hashlib
import time

import requests
from django.conf import settings
from django.core.cache import cache

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OSRM_URL = "https://router.project-osrm.org/route/v1/driving"
HEADERS = {"User-Agent": "CargoLink-StackUnity/1.0 (projet universitaire Django)"}  # obligatoire pour Nominatim
TIMEOUT = 5


def geocoder(ville):
    """Retourne ((lat, lon) ou None, appel_reseau_effectue)."""
    cle = "geo:" + hashlib.md5(ville.strip().lower().encode()).hexdigest()
    en_cache = cache.get(cle)
    if en_cache:
        return en_cache, False

    params = {"q": ville, "format": "json", "limit": 1}
    pays = getattr(settings, "NOMINATIM_COUNTRY_CODES", "")
    if pays:
        params["countrycodes"] = pays
    try:
        r = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        coords = (float(data[0]["lat"]), float(data[0]["lon"]))
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return None, True
    cache.set(cle, coords, 60 * 60 * 24)      # 24h
    return coords, True


def calculer_trajet(origine, destination):
    """Retourne un dict (distance, durée, coordonnées) ou None si une API est indisponible."""
    o, appel = geocoder(origine)
    if appel:
        time.sleep(1)          # Nominatim: maximum 1 requête par seconde
    d, _ = geocoder(destination)
    if not o or not d:
        return None
    try:
        r = requests.get(f"{OSRM_URL}/{o[1]},{o[0]};{d[1]},{d[0]}",
                         params={"overview": "false"}, timeout=TIMEOUT)
        r.raise_for_status()
        route = r.json()["routes"][0]
        return {
            "origin_lat": o[0], "origin_lon": o[1],
            "destination_lat": d[0], "destination_lon": d[1],
            "distance_km": round(route["distance"] / 1000, 1),
            "duration_hours": round(route["duration"] / 3600, 1),
        }
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return None