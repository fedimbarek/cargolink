# Accessibilité (WCAG 2.1 AA)

## Ce qui est en place
| Critère de la grille | Mise en œuvre |
|---|---|
| Structure sémantique | `<header>`, `<nav aria-label>`, `<main id="contenu">`, `<footer>` ; un seul `<h1>` par page, titres sans saut de niveau ; `lang="fr"` |
| ARIA et alternatives | `aria-label` sur les boutons sans texte, `aria-current="page"` dans le menu, `aria-live`/`role="status"`/`role="alert"` pour messages et erreurs, `aria-busy` pendant le calcul IA, `alt` descriptif sur le graphique du modèle, `<caption>` et `scope` sur tous les tableaux, champs reliés à leur label et aux erreurs (`aria-describedby` / `aria-invalid` natifs de Django) |
| Contraste | `static/css/cargolink.css` : bleu `#0a58ca` (6,4:1), erreurs `#b02a37` (6,5:1), succès `#146c43` ; le bleu Bootstrap par défaut des liens (4,3:1) échouait au seuil AA de 4,5:1 |
| Clavier | lien d'évitement « Aller au contenu principal », focus visible (contour jaune + halo sombre), menu mobile accessible au clavier, aucune action réservée à la souris |
| Responsive | `viewport`, menu repliable, tableaux dans `.table-responsive`, `prefers-reduced-motion` respecté |

## Audit automatisé (dans la suite de tests)
`config/test_accessibilite.py` parcourt toutes les pages principales (PME, transporteur, admin, pages d'erreur) et
vérifie : langue, `<main>`, lien d'évitement, un seul h1, hiérarchie des titres, `alt`, labels, boutons/liens nommés,
`caption`/`scope`, `nav` nommée. Un test de contrôle prouve que l'audit détecte bien les défauts.

## Audit manuel à présenter au jury (5 minutes)
1. Chrome > DevTools > **Lighthouse** > Accessibility sur `/login/`, `/annonces/`, `/annonces/nouvelle/` : faire une capture du score.
2. Extension **axe DevTools** sur la page de création de demande.
3. Souris débranchée : Tab / Maj+Tab / Entrée du login jusqu'à la création d'une demande, puis estimation IA.
4. Zoom navigateur à 200 % : pas de défilement horizontal de la page.
