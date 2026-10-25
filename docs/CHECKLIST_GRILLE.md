# Correspondance avec la grille d'évaluation (20 points)

| Module | Pts | État dans le projet | Démonstration |
|---|---|---|---|
| Fonctionnalités & CRUD | 2 | Demandes, propositions, véhicules, factures, paiements : CRUD complet, validations serveur + client | Créer / modifier / annuler une demande |
| Tests & BNF | 3-4 | 151 tests, couverture 85 % (branches), `.coveragerc`, CI avec seuil ; CSRF, hachage, `SECRET_KEY` en env, `check --deploy` propre, rôles testés (URL directe → 403), pages 403/404/500, limitation de débit | `python manage.py test` puis `coverage report` |
| Accessibilité | 2 | Voir `docs/ACCESSIBILITE.md` + audit automatisé | Lighthouse + clavier |
| IA | 4 | Régression de prix, 4 modèles comparés, métriques, intervalle calibré, latence, Celery/Redis optionnel, UX de chargement/erreur | `/ia/modele/` + création d'une demande |
| UX / UI | 1 | Menu responsive, retour utilisateur, messages d'état, cohérence Bootstrap | Parcours complet sur mobile |
| Q/R & QCM | 8 | `docs/QCM_CargoLink.md` (35 questions) | Révision |
| Git | note indiv. | **À faire par l'équipe** : commits individuels | `git shortlog -sn` |
| Intégration & Déploiement | équipe | Fichiers prêts ; **le déploiement reste à lancer par l'équipe** | URL Render |

## Ce que le code ne peut pas faire à votre place
1. Pousser sur GitHub avec le compte de chaque membre.
2. Créer le service Render et saisir le mot de passe admin.
3. Capture Lighthouse / axe pour la soutenance.
4. Remplacer, si possible, les données synthétiques de l'IA par de vraies propositions (voir `docs/RAPPORT_IA.md`).
