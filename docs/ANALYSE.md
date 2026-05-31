# 🔍 Analyse constructive — Aubaines Rapides

> **À lire par l'assistant IA avant toute modification du projet.**
> Ce document décrit l'état réel du projet, ses forces, ses faiblesses, et un plan d'action priorisé.
> Objectif : passer d'un bon prototype solo à un produit fiable et monétisable, sans tout réécrire.

---

## 1. Contexte du projet (résumé pour l'IA)

- **Quoi** : outil web gratuit qui compare les spéciaux d'épicerie de la semaine au Québec (viande, poisson, fruits, légumes, paniers).
- **Stack** : site statique (HTML/CSS/JS vanilla) hébergé sur **GitHub Pages**, données dans un **`deals.json`** généré à partir d'une base **SQLite** (~431 deals/semaine). Pipeline de scraping **Flipp API + Tigre Géant (Shopify)**. ~429 recettes liées, calcul protéines/$ (références FCÉN).
- **Auteur** : développeur débutant mais autonome, solo, conscient des coûts.
- **But final** : écosystème autonome → scraping → recettes → communauté → monétisation (affiliation + abonnement Premium 19.95 $/mois).

**Règle pour l'IA** : ce projet est solo et débutant. On privilégie des solutions **simples, robustes et peu coûteuses**. Pas de refonte framework non demandée, pas de dépendances lourdes sans raison claire. Chaque suggestion doit pouvoir être livrée en quelques heures à une journée.

---

## 2. Forces actuelles (à NE PAS casser)

Ce qui est déjà bien fait et qui doit rester :

- Pipeline de données fonctionnel avec normalisation $/kg et $/lb — c'est le cœur de valeur.
- Frontend statique = quasi gratuit, rapide, simple à déployer.
- Accessibilité déjà sérieuse (aria-label, rôles tablist, navigation clavier, `escapeHTML`).
- SEO de base présent (meta description, Open Graph, Twitter Card).
- Design cohérent et identitaire (palette circulaire papier, polices Fraunces/Caveat).
- Calcul protéines/$ = vrai différenciateur vs les autres comparateurs.

---

## 3. Problèmes observés et dette technique (priorisés)

### 🔴 P0 — Critique ou correctif rapide à fort impact

| # | Problème | Pourquoi ça compte |
|---|----------|--------------------|
| P0-1 | **Incohérence d'URL** : la page est servie sur `/aubaines-rapides/web/`, mais `canonical` pointe vers `/aubaines-rapides/`, et les liens de partage mentionnent `aubainesrapides.ca`. | Trois URL pour un même produit = SEO dilué, balise canonical fausse, partages qui pointent vers une page potentiellement inexistante. |
| P0-2 | **Aucun état d'erreur si `deals.json` ne charge pas** : le site reste bloqué sur « On fouille les circulaires... ». | Si le scraping échoue ou que le fichier est corrompu, l'utilisateur voit un site cassé sans message. |
| P0-3 | **Pas de monitoring du scraping** : rien n'avertit si une semaine retourne 0 deal ou si Flipp/Shopify change son format. | Le produit peut se vider silencieusement pendant des semaines. |
| P0-4 | **Conformité légale Québec absente** (voir §5) : pas de politique de confidentialité, pas de mécanisme de consentement courriel conforme à la LCAP, droits d'image/scraping non clarifiés. | Bloque toute monétisation propre et expose à des risques réels (CASL/LCAP, Loi 25). |

### 🟠 P1 — Important pour la fiabilité et la croissance

| # | Problème | Note |
|---|----------|------|
| P1-1 | **Qualité de parsing des prix** : les circulaires affichent « 2/5 $ », « 3,99 $/lb », « achetez-en 2 » — formats variés et casse-gueule. Pas de couche de validation/détection d'anomalies visible. | C'est LA difficulté technique d'un comparateur de circulaires. Un prix mal parsé détruit la confiance. |
| P1-2 | **`deals.json` monolithique** qui grossit avec les semaines. | Déjà identifié dans la roadmap (séparation par semaine + lazy loading). À prioriser avant que ça devienne lourd. |
| P1-3 | **Classification Frais/Transformé** : si c'est par mots-clés, taux d'erreur élevé. | À auditer : combien d'erreurs sur un échantillon de 50 items ? |
| P1-4 | **Pas de tests automatisés** sur le pipeline (parsing, conversions $/kg, classification). | Un test sur 20 cas réels de prix éviterait des régressions silencieuses. |
| P1-5 | **Données structurées SEO (JSON-LD) absentes** : Schema.org `Product`/`Offer` aideraient énormément un site de deals à ressortir dans Google. | Effort faible, gain SEO réel. |

### 🟡 P2 — Amélioration continue

- Lazy loading des images produits + `loading="lazy"` + dimensions explicites (évite le layout shift).
- Historique de prix par produit (utile pour le futur dashboard + argument Premium).
- Détection de doublons inter-magasins (même produit, prix différents).
- Pages SEO par catégorie/magasin (longue traîne : « spéciaux viande Maxi cette semaine »).

---

## 4. Plan d'action priorisé (tâches concrètes pour l'IA)

> Chaque tâche a un **critère d'acceptation** (« Fini quand... »). L'IA doit le respecter et ne pas dépasser le périmètre demandé.

### Sprint 1 — Stabiliser (P0)

1. **Unifier l'URL.**
   - Décider d'une URL canonique unique. Recommandation : configurer le domaine custom `aubainesrapides.ca` (fichier `CNAME` dans le repo) OU, à défaut, servir le site à la racine `/aubaines-rapides/`.
   - Corriger `canonical`, Open Graph `url`, et les liens de partage pour qu'ils pointent tous au même endroit.
   - *Fini quand* : les 3 références (URL réelle, canonical, partages) sont identiques.

2. **Ajouter un état d'erreur + timeout sur le chargement de `deals.json`.**
   - Si le `fetch` échoue ou dépasse ~8 s, afficher un message clair (« Données temporairement indisponibles, réessaie plus tard ») plutôt que le spinner infini.
   - *Fini quand* : couper le réseau ou renommer `deals.json` affiche un message propre, pas un site figé.

3. **Mettre une alerte sur le scraping.**
   - À la fin du script Python : si le nombre de deals < seuil (ex. 50) ou si une exception survient, envoyer une notification (courriel via SMTP, ou simple log horodaté + statut dans un fichier `last_run.json`).
   - *Fini quand* : une exécution vide ou en erreur produit une alerte visible sans avoir à ouvrir les logs.

### Sprint 2 — Fiabiliser les données (P1)

4. **Couche de validation des prix.**
   - Normaliser les formats (« 2/5 $ » → 2,50 $/unité, « 3,99/lb » → conversion $/kg).
   - Marquer (flag) tout deal dont le $/kg est aberrant (ex. < 0,50 $ ou > 100 $) pour révision manuelle plutôt que de l'afficher tel quel.
   - *Fini quand* : un fichier `flagged.json` liste les deals douteux et ils n'apparaissent pas (ou sont marqués) sur le site.

5. **Tests sur le parsing.**
   - Créer un petit jeu de ~20 cas réels de prix de circulaires avec le résultat attendu. Lancer ces tests à chaque génération.
   - *Fini quand* : `python test_parsing.py` passe et casse si on introduit une régression.

6. **Découper `deals.json` par semaine + lazy loading.**
   - Un fichier par semaine (`deals-2026-W22.json`) + un index léger. Charger seulement la semaine demandée.
   - *Fini quand* : le chargement initial ne télécharge qu'une semaine, pas tout l'historique.

7. **Ajouter le JSON-LD Schema.org.**
   - Pour chaque deal affiché : balisage `Product` + `Offer` (nom, prix, devise, magasin, validité).
   - *Fini quand* : le test Rich Results de Google valide la page sans erreur.

### Sprint 3 — Croissance (aligné avec ta roadmap)

8. Newsletter **conforme LCAP** (voir §5) avant le cron du mardi.
9. Page recettes liées aux deals.
10. Liens d'affiliation Amazon Associates **avec divulgation claire**.

---

## 5. ⚖️ Risques légaux à régler avant de monétiser (Québec/Canada)

> Ce n'est pas un avis juridique, mais ces points sont concrets et propres au Québec. À traiter **avant** de vendre un abonnement ou d'envoyer une newsletter.

- **LCAP / CASL (loi anti-pourriel canadienne)** : un envoi courriel commercial exige un **consentement explicite**, l'**identification de l'expéditeur** et un lien de **désabonnement** fonctionnel. Le formulaire actuel doit capturer et journaliser le consentement.
- **Loi 25 (protection des renseignements personnels, Québec)** : si tu collectes des courriels, il faut une **politique de confidentialité** accessible et un responsable de la protection des données identifié.
- **Scraping & droits** : Flipp et les détaillants ont des conditions d'utilisation. Réutiliser les **images produits** (Shopify Tigre Géant, etc.) dans un produit payant peut poser un problème de droits. À clarifier — au minimum, citer la source et vérifier les ToS.
- **Divulgation d'affiliation** : les liens Amazon Associates doivent afficher une mention claire (« lien affilié »).

**Action minimale** : créer une page `confidentialite.html` + `conditions.html` et brancher le consentement sur le formulaire newsletter. Effort : ~½ journée.

---

## 6. Comment travailler avec moi (l'IA)

Pour que je sois réellement utile sur ce projet à long terme :

1. **Crée un fichier `CLAUDE.md`** (ou `CONTEXT.md`) à la racine du repo contenant : la stack, les conventions de nommage, la structure des dossiers, et la règle « solutions simples et peu coûteuses, pas de refonte non demandée ». Je le lirai à chaque session.
2. **Travaille par petites tâches** avec un critère d'acceptation, comme au §4. Évite « améliore le site » — préfère « ajoute un état d'erreur au fetch de deals.json ».
3. **Donne-moi des exemples réels** quand c'est de la donnée (vrais textes de circulaires, vrai `deals.json`) plutôt que des cas inventés.
4. **Demande-moi de t'expliquer** ce que je change et pourquoi, en une phrase par modification — utile pour apprendre et pour repérer si je pars dans le champ.
5. **Une chose à la fois** : valide une tâche avant de passer à la suivante, surtout sur le pipeline de données.

---

## 7. Résumé en une phrase

Le produit a de bonnes fondations ; les prochaines priorités sont **unifier l'URL**, **rendre le chargement et le scraping robustes**, **fiabiliser le parsing des prix**, et **mettre en place la conformité légale** avant d'activer la monétisation.

*Document d'analyse — projet Aubaines Rapides — 30 mai 2026*
