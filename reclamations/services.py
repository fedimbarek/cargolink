"""
Adaptateur de compatibilité.
Toute la logique IA vit dans `MLReclamations.py`.
"""
from .MLReclamations import (
    MODEL_PATH,
    entrainer_modele,
    predire_priorite,
    predire_priorite_avec_proba,
    suggerer_et_appliquer,
)