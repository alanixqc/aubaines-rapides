# 🚀 Aubaines Rapides — Mission & Roadmap

---

## 🎯 Mission

**Aubaines Rapides** est un outil web gratuit qui compare les spéciaux d'épicerie de la semaine au Québec — viande, poisson, fruits, légumes et paniers — pour trouver les meilleurs prix en 30 secondes, pas 30 minutes.

L'objectif ultime : créer un **écosystème autonome** qui scrappe les circulaires → génère des recettes liées → informe la communauté → monétise via affiliation et abonnements → réinvestit dans l'outil.

---

## 📖 Ce qui a été accompli

### Phase 1 — Fondations (scraping & données)
- Pipeline de scraping automatisé (Flipp API + Tigre Géant Shopify)
- Base de données SQLite de 431 deals/semaine avec prix, $/kg, $/lb
- Classification Frais / Transformé pour chaque produit
- Enrichissement automatique des images produits (Shopify API)
- Base de recettes (429 recettes liées aux deals)
- Calcul des protéines par dollar (références FCÉN Canada)
- Tri intelligent : meilleur achat par $/kg

### Phase 2 — Site web (frontend)
- Site statique hébergé sur GitHub Pages
- Design "circulaire papier" : crème #f3ede3, terracotta #b8492e, mustard #c9942e
- Polices Fraunces (titres) + Caveat (accent manuscrit) + Source Serif 4
- 5 catégories avec onglets : Viande, Poisson, Fruits, Légumes, Panier
- Filtre 🌿 Frais / 🏭 Transformé par catégorie
- Top 3 deals avec ⭐ TOP, classement #1, #2, #3…
- Navigation entre les semaines (précédent/suivant)
- Barre de statistiques (offres, viandes, légumes, fruits, magasins)
- Badges de commerce colorés (17 épiceries avec couleurs distinctives)

### Phase 3 — Expérience utilisateur
- ✅ **Grille responsive** : 1 col (mobile) → 2 cols (tablette 600px) → 3 cols (desktop 1200px) → 4 cols (1600px+)
- ✅ **Modale détail produit** avec prix, protéines, poids, validité, image plein écran
- ✅ **Recherche** dans produit, magasin ET catégorie
- ✅ **Toast** notifications (remplace les alert())
- ✅ **État vide** quand aucun résultat trouvé
- ✅ **Escape** ferme modale et plein écran

### Phase 4 — Accessibilité & SEO
- ✅ 29 boutons HTML avec `type="button"` + `aria-label`
- ✅ `role="tablist"` / `role="tab"` / `aria-selected` pour les onglets
- ✅ Navigation clavier (Enter/Space sur les cartes deals)
- ✅ `rel="noopener"` sur les liens externes
- ✅ `.sr-only` pour les labels cachés
- ✅ Meta description, canonical, Open Graph, Twitter Card, favicon, theme-color
- ✅ `escapeHTML()` pour toutes les données injectées

### Phase 5 — Corrections & stabilité
- ✅ Bug modale vide au chargement — cachée par défaut avec classe `.open`
- ✅ Bug filtre "Transformé" — remplacé par `data-type` attributs
- ✅ Bug grille desktop — grille sur `.deals-container` au lieu de `.cat-section`
- ✅ Boutons qui ne restaient pas actifs — reset du filtre au changement de catégorie

---

## 🔮 Ce qui s'en vient

### 🔜 Court terme (prochaines semaines)

| Priorité | Fonctionnalité | Effort |
|----------|---------------|--------|
| 1 | **Newsletter** (MailerLite) — formulaire fonctionnel + cron envoi mardi | ½ journée |
| 2 | **Page recettes** liées aux deals de la semaine | 1 journée |
| 3 | **Groupe Facebook / Communauté** | ½ journée |
| 4 | **Amazon Associates CA** — liens affiliation ustensiles/ingrédients | ½ journée |
| 5 | **Séparation deals.json par semaine** — performance (lazy loading) | ½ journée |

### 📅 Moyen terme (1-3 mois)

- **TikTok automatique** — vidéo des 3 top deals + 1 recette chaque semaine
- **WhatsApp / Messenger** — notifications des deals
- **Scan de facture** → identification des items → liste d'épicerie
- **Page "Abonnement Premium"** (19.95$/mois) — deals exclusifs, alertes SMS, pas de pubs
- **Dashboard utilisateur** — favoris, historique de prix, alertes personnalisées

### 🏆 Long terme (3-6 mois)

- Serveur dédié (sortir de GitHub Pages)
- Application mobile (PWA ou native)
- API publique pour les données de spéciaux
- Livraison Uber-style intégrée
- Programme d'affiliation multi-magasins

### 💰 Modèle d’affaires

| Source | Revenu estimé | Seuil |
|--------|--------------|-------|
| Amazon Associates | 5-15$/mois (départ) | 3-4 liens cliqués/jour |
| Newsletter sponsors | 50-200$/envoi | 500+ abonnés |
| Premium 19.95$/mois | 100$/mois | 5 abonnés = break-even |
| Facebook groupe sponsorisé | 20-50$/mois | 1000+ membres |

**Break-even : 5 abonnés Premium** couvrent tous les frais (domaine, newsletter, serveur).

---

*Document généré le 30 mai 2026 — projet Aubaines Rapides*
