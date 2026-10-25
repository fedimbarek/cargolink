# QCM CargoLink – cours + code de l'application

35 questions à choix unique. Les réponses détaillées sont à la fin du document.

**1. [Cours – Templates] Quelle syntaxe affiche la valeur d'une variable du contexte dans un gabarit Django ?**

- A) <% book_title %>
- B) ${book_title}
- C) {{ book_title }}
- D) {% book_title %}

**2. [Cours – Templates] Pourquoi préférer {% url 'book_details' b.id %} à un lien écrit en dur (/books/12) ?**

- A) C'est plus rapide à l'exécution
- B) Pour activer la protection CSRF
- C) Parce que les liens en dur sont interdits par Django
- D) Respecter le principe DRY : l'URL n'est définie qu'à un seul endroit (urls.py)

**3. [Cours – Templates] Quelle paire de balises permet à index.html de réutiliser la structure de base.html ?**

- A) {% include %} / {% endinclude %}
- B) {% extends "base.html" %} et {% block %}
- C) {% load base %}
- D) {% import base %}

**4. [Cours – Views] Que fait la fonction render(request, 'app/list_books.html', context) ?**

- A) Retourne du JSON
- B) Enregistre le contexte en base
- C) Redirige vers une URL
- D) Charge le gabarit, le remplit avec le contexte et renvoie un HttpResponse

**5. [Cours – Views] Quelle est la différence entre raise Http404(...) et return HttpResponseNotFound(...) ?**

- A) HttpResponseNotFound lève une exception
- B) Http404 renvoie le code 500
- C) Http404 est une exception interceptée par Django qui affiche la page 404 ; HttpResponseNotFound est une réponse retournée
- D) Aucune, ce sont deux noms du même objet

**6. [Cours – URLs] Que signifie path('book_detail/<int:id_book>', book_detail) ?**

- A) La vue doit s'appeler id_book
- B) Le segment doit être un entier et est transmis à la vue comme int nommé id_book
- C) id_book est transmis à la vue sous forme de chaîne
- D) L'URL accepte n'importe quel texte

**7. [Cours – Vues génériques] Avec class BookList(ListView): model = Book, quel est le nom de template et de variable de contexte par défaut ?**

- A) book_list.html et items
- B) app/book_list.html et object_list
- C) book.html et books
- D) app/list.html et list

**8. [Cours – Vues génériques] Quels attributs minimum configure-t-on dans une CreateView ?**

- A) model (ou form_class), template_name et success_url
- B) context_object_name
- C) uniquement queryset
- D) get_absolute_url

**9. [Cours – Forms] Quel est l'avantage de ModelForm par rapport à Form ?**

- A) Il génère les champs à partir du modèle (pas de redéfinition) et fournit form.save()
- B) Il est plus rapide
- C) Il remplace la validation
- D) Il fonctionne sans CSRF

**10. [Cours – Forms] À quoi sert {% csrf_token %} dans un formulaire POST ?**

- A) À remplir automatiquement le formulaire
- B) À protéger contre les requêtes forgées depuis un autre site (CSRF) : sans jeton, Django rejette la requête (403)
- C) À chiffrer le mot de passe
- D) À afficher les erreurs

**11. [Cours – Authentification] Quelle est la différence entre authentification et autorisation ?**

- A) L'authentification ne concerne que l'admin
- B) Aucune
- C) Authentification : vérifier QUI est l'utilisateur ; autorisation : vérifier CE QU'IL a le droit de faire
- D) L'inverse

**12. [Cours – Authentification] Dans une vue de connexion écrite à la main, quel est l'ordre correct ?**

- A) create_user() puis login()
- B) authenticate(request, username, password) puis, si user n'est pas None, login(request, user)
- C) login(request, user) puis authenticate()
- D) set_password() puis save()

**13. [Cours – Authentification] Comment Django stocke-t-il les mots de passe, et quel est l'algorithme par défaut ?**

- A) En clair, protégés par la base
- B) En MD5 salé
- C) Hachés ; PBKDF2 avec SHA-256 par défaut
- D) Chiffrés en AES réversible

**14. [Cours – Authentification] Quelle est la bonne façon de protéger une vue basée sur une classe contre les visiteurs anonymes ?**

- A) Impossible sans middleware
- B) if request.user == None
- C) class MaVue(LoginRequiredMixin, DetailView)
- D) @login_required au-dessus de la classe

**15. [Cours – Authentification] À quoi sert LoginRequiredMiddleware (Django 5.1+) ?**

- A) Remplacer AUTH_USER_MODEL
- B) Limiter les tentatives de connexion
- C) Protéger tout le site par défaut ; on rend une vue publique avec @login_not_required
- D) Chiffrer les sessions

**16. [Cours – Authentification] Pourquoi la documentation recommande-t-elle un modèle User personnalisé dès le début du projet ?**

- A) Car le User par défaut est obsolète
- B) Car changer de modèle User en cours de projet est très difficile (migrations, clés étrangères)
- C) Pour accélérer la base
- D) C'est obligatoire pour utiliser l'admin

**17. [Cours – Django REST Framework] Que fait serializer = EventSerializer(data=request.data) suivi de serializer.is_valid() ?**

- A) Enregistre directement en base
- B) Désérialise et valide les données entrantes ; save() n'est appelé qu'ensuite
- C) Convertit un objet en JSON
- D) Supprime l'événement

**18. [Cours – Django REST Framework] Quel code HTTP convient à une création réussie via l'API, et à des données invalides ?**

- A) 201 Created et 400 Bad Request
- B) 302 et 403
- C) 204 et 404
- D) 200 et 500

**19. [Cours – IA (Gemini)] Où doit-on placer la clé de l'API Gemini ?**

- A) Dans le JavaScript
- B) Dans le template HTML
- C) Directement dans views.py
- D) Dans un fichier .env non versionné, lu avec os.getenv après python-dotenv

**20. [Cours – Déploiement Render] Quel est le rôle de WhiteNoise et de build.sh dans le déploiement sur Render ?**

- A) WhiteNoise chiffre les statiques ; build.sh crée le dépôt GitHub
- B) WhiteNoise sert les fichiers statiques ; build.sh installe les dépendances, lance collectstatic et migrate
- C) WhiteNoise remplace PostgreSQL ; build.sh démarre le serveur
- D) Ils ne servent qu'en local

**21. [Cours – Déploiement Render] Pourquoi lit-on DATABASE_URL, SECRET_KEY et DEBUG depuis l'environnement en production ?**

- A) Pour ne jamais versionner de secrets et adapter la configuration à chaque environnement (DEBUG=False en prod)
- B) Car Render l'impose techniquement
- C) Pour aller plus vite
- D) Pour désactiver CSRF

**22. [Code CargoLink – Utilisateurs] Que signifie USERNAME_FIELD = "email" dans users/models.py ?**

- A) Le champ email n'est plus obligatoire
- B) On se connecte avec l'email ; username reste dans REQUIRED_FIELDS pour createsuperuser
- C) L'email devient la clé primaire
- D) Le username est supprimé

**23. [Code CargoLink – Utilisateurs] Pourquoi un transporteur fraîchement inscrit ne peut-il pas faire de proposition ?**

- A) Il n'a pas de véhicule
- B) Son statut est PENDING et transporteur.verified est False tant que l'admin ne l'a pas validé (permission IsTransporteur, vérifications dans les vues)
- C) Seules les PME peuvent proposer
- D) Il doit payer

**24. [Code CargoLink – Utilisateurs] Que fait le décorateur role_required("PME") de users/decorators.py pour un transporteur connecté ?**

- A) Le redirige vers le login
- B) Lève PermissionDenied → page 403 personnalisée
- C) Affiche une page blanche
- D) Le déconnecte

**25. [Code CargoLink – Propositions] À quoi sert la UniqueConstraint(condition=Q(status__in=[PENDING, ACCEPTED])) sur Proposition ?**

- A) Limiter à 2 propositions par demande
- B) Interdire les prix identiques
- C) Un transporteur ne peut avoir qu'UNE proposition active par demande, mais peut re-proposer après un retrait/refus
- D) Rendre le prix unique

**26. [Code CargoLink – Propositions] Pourquoi accepter_proposition utilise-t-elle @transaction.atomic et select_for_update() ?**

- A) Pour verrouiller la table user
- B) Pour accélérer la requête
- C) Pour qu'acceptation, refus des autres offres et passage en ASSIGNED soient tout-ou-rien et sans course entre deux acceptations simultanées
- D) Pour envoyer un e-mail

**27. [Code CargoLink – Propositions] Comment est calculé le score de comparaison des offres (comparer) ?**

- A) Moyenne simple des trois
- B) 50 % prix + 30 % note du transporteur + 20 % durée (normalisés), la meilleure est « recommandée »
- C) 33 % chacun
- D) 100 % le prix

**28. [Code CargoLink – Factures] Pourquoi les vues annuler, accepter, emettre sont-elles décorées avec @require_POST ?**

- A) Pour afficher un formulaire
- B) Pour la rapidité
- C) Une action qui modifie des données ne doit pas être déclenchée par un simple GET (lien, préchargement, CSRF)
- D) Django l'exige pour tous les décorateurs

**29. [Code CargoLink – Factures] Une facture de 450 TND HT avec TVA 19 % donne quel total TTC, et quelle règle d'arrondi est utilisée ?**

- A) 535,50 TND ; arrondi au centime (ROUND_HALF_UP) avec Decimal
- B) 531,00 TND ; troncature
- C) 450 TND ; la TVA est facultative
- D) 535,5 ; float

**30. [Code CargoLink – IA] Pourquoi le modèle d'estimation de prix est-il entraîné sur log(prix) et pas sur le prix brut ?**

- A) Pour réduire la taille du fichier
- B) Car l'erreur sur un prix est relative (multiplicative) : le log stabilise la variance et garantit des prix positifs
- C) Car scikit-learn l'exige
- D) Pour éviter l'overfitting à 100 %

**31. [Code CargoLink – IA] Quelle métrique mesure l'erreur moyenne en dinars, et laquelle l'erreur relative en % ?**

- A) MAE (TND) et MAPE (%)
- B) R² et MAE
- C) Précision et Recall
- D) F1 et matrice de confusion

**32. [Code CargoLink – IA] À quoi sert le jeu de calibration dans ia/ml.py ?**

- A) À entraîner le modèle
- B) À augmenter les données
- C) À calculer l'intervalle de prédiction à 90 % (split conformal) ; la couverture est ensuite vérifiée sur le jeu de test
- D) À choisir le meilleur algorithme

**33. [Code CargoLink – IA] Que se passe-t-il si REDIS_URL n'est pas défini ?**

- A) Le modèle est ré-entraîné à chaque requête
- B) L'IA est désactivée
- C) Celery passe en mode « eager » : l'estimation s'exécute de façon synchrone (aucune dépendance à Redis)
- D) L'application plante

**34. [Code CargoLink – IA] Pourquoi l'appel au modèle ML est-il rapide alors que l'estimation depuis le formulaire peut être lente ?**

- A) Le formulaire utilise Gemini
- B) Le modèle est chargé une fois en mémoire (~0,3 ms/prédiction) ; c'est le calcul de distance (Nominatim + OSRM, réseau) qui est lent et peut être déporté dans Celery
- C) Le modèle tourne sur GPU
- D) Le modèle est ré-entraîné à chaque appel

**35. [Code CargoLink – Sécurité] Quelles protections de production sont activées quand DEBUG=False dans settings.py ?**

- A) Uniquement WhiteNoise
- B) SECRET_KEY obligatoire, redirection HTTPS, cookies Secure, HSTS, WhiteNoise + statiques hachés
- C) Aucune
- D) Uniquement ALLOWED_HOSTS


---

## Corrigé

| N° | Réponse | Explication |
|---|---|---|
| 1 | **C** | Les variables s'écrivent {{ }} ; les balises (if, for, url…) s'écrivent {% %}. |
| 2 | **D** | Avec {% url %} (et le name= du path), changer une URL ne casse aucun gabarit. |
| 3 | **B** | extends déclare l'héritage ; les {% block %} sont les zones que l'enfant redéfinit. include insère un fragment. |
| 4 | **D** | render = charger le template + remplir le contexte + renvoyer un HttpResponse. |
| 5 | **C** | Django intercepte l'exception Http404 et rend la page d'erreur (handler404) ; l'autre est une réponse normale de statut 404. |
| 6 | **B** | Le convertisseur int valide le segment et le convertit ; str, slug et uuid existent aussi. Avec re_path, tout arrive en chaîne. |
| 7 | **B** | ListView déduit <app>/<modèle>_list.html et expose object_list (modifiable avec template_name / context_object_name). |
| 8 | **A** | CreateView a besoin du modèle/formulaire, du gabarit et de l'URL de redirection après succès. |
| 9 | **A** | ModelForm reprend les champs et validateurs du modèle ; Meta.fields choisit les champs et save() enregistre l'objet. |
| 10 | **B** | Le jeton prouve que le formulaire vient bien de notre site. Sur un fetch JS, il est envoyé dans l'en-tête X-CSRFToken. |
| 11 | **C** | Les deux sont gérés par django.contrib.auth (login/mot de passe d'un côté, permissions/groupes de l'autre). |
| 12 | **B** | authenticate vérifie les identifiants et retourne un User ou None ; login attache l'utilisateur à la session. |
| 13 | **C** | Jamais en clair. PBKDF2 par défaut (870 000 itérations depuis Django 5.1) ; Argon2 et BCrypt sont supportés via PASSWORD_HASHERS. |
| 14 | **C** | Le mixin est l'équivalent de @login_required pour les vues classes (il doit être placé en premier dans l'héritage). |
| 15 | **C** | Cela réduit le risque d'oublier @login_required sur une nouvelle vue sensible. |
| 16 | **B** | On hérite d'AbstractUser (garder les champs) ou AbstractBaseUser (repartir de zéro) et on déclare AUTH_USER_MODEL avant la première migration. |
| 17 | **B** | Un serializer fait les deux sens : objet → JSON (serializer.data) et JSON → objet validé (is_valid + save). |
| 18 | **A** | Response(serializer.data, status=201) si valide ; Response(serializer.errors, status=400) sinon. |
| 19 | **D** | Une clé commitée sur GitHub est compromise ; on utilise des variables d'environnement (.env ignoré par Git). |
| 20 | **B** | Gunicorn/Uvicorn ne servent pas les statiques en production : WhiteNoise s'en charge après collectstatic. |
| 21 | **A** | Principe des 12 facteurs : la configuration sensible vit dans l'environnement, pas dans le code. |
| 22 | **B** | C'est pourquoi le formulaire de connexion déclare username = forms.EmailField et que l'API de login reçoit {email, password}. |
| 23 | **B** | RegisterForm/RegisterSerializer mettent status=PENDING ; l'action admin « Valider les transporteurs » passe verified=True et status=ACTIVE. |
| 24 | **B** | Il empile @login_required (visiteur → login) puis compare request.user.role ; sinon PermissionDenied (403). |
| 25 | **C** | Contrainte partielle garantie par la base (même en cas de double clic / requêtes concurrentes) ; la vue capture IntegrityError. |
| 26 | **C** | Sans verrou, deux PME/onglets pourraient accepter deux offres sur la même demande. |
| 27 | **B** | _moins_c_est_mieux normalise prix et durée entre min et max ; la note est divisée par 5. |
| 28 | **C** | GET doit rester sans effet de bord ; le POST est protégé par le jeton CSRF. Un GET renvoie 405. |
| 29 | **A** | On utilise Decimal (jamais float pour l'argent) : TVA = 85,50 puis total = 535,50. |
| 30 | **B** | Le bruit du marché est proportionnel au prix ; la prédiction est ramenée en TND avec exp(). |
| 31 | **A** | Précision/Recall/F1 sont des métriques de classification ; ici c'est une régression : MAE, RMSE, R² et MAPE. |
| 32 | **C** | Découpage 70 % train / 15 % calibration / 15 % test : le test reste intact pour une évaluation honnête. |
| 33 | **C** | settings : CELERY_TASK_ALWAYS_EAGER = not CELERY_BROKER_URL. Avec Redis, /ia/estimer/ répond 202 + task_id et le front interroge /ia/tache/<id>/. |
| 34 | **B** | C'est la justification de la tâche asynchrone : ne pas bloquer la requête HTTP sur des API externes. |
| 35 | **B** | Vérifié par python manage.py check --deploy (exécuté dans la CI GitHub Actions). |

## Barème indicatif

8 points sur 20 : une bonne réponse = 8 / nombre de questions posées.
