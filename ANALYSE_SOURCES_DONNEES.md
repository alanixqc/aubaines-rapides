# Analyse des Sources de Données — Remplacement de Flipp
## Projet Aubaines-Rapides  
**Date :** 30 mai 2026  
**Objectif :** Trouver LA source de données idéale pour chaque épicerie (viande/spéciaux)

---

## Résumé Exécutif

| # | Épicerie | Source Idéale | Format | Facilité Scraping | Section Viande |
|---|----------|--------------|--------|-------------------|----------------|
| 1 | **IGA** | Voila.ca API (Sobeys) | API REST JSON | ✅ Facile | ✅ Oui |
| 2 | **Provigo** | PC Express API (Loblaws) | API REST JSON | ✅ Facile | ✅ Oui |
| 3 | **Maxi** | PC Express API (Loblaws) | API REST JSON | ✅ Facile | ✅ Oui |
| 4 | **Walmart** | Flipp API (flyers-ng) + Walmart GraphQL | API GraphQL/REST | ⚠️ Moyen (PX) | ✅ Oui |
| 5 | **Costco** | Site Web (Playwright) + PDF coupons | HTML/PDF | ⚠️ Difficile | ✅ Oui |
| 6 | **Marchés Tradition** | Flipp API (flyers-ng) | API REST JSON | ✅ Facile | ✅ Oui |
| 7 | **Mayrand** | PDF circulaire (PDF parsing) | PDF | ⚠️ Difficile | ✅ Oui |
| 8 | **Rachelle Béry** | Voila.ca API (via Sobeys-IGA) | API REST JSON | ✅ Facile | ✅ Oui |
| 9 | **M&M Food Market** | Site Web (list view) | HTML/JS | ⚠️ Moyen | ⚠️ Partiel |
| 10 | **L'Inter-Marché** | PC Express API (Loblaws) | API REST JSON | ✅ Facile | ✅ Oui |
| 11 | **Fruiterie Potager** | Circulaires.com (image) + Flipp API | Images/API | ⚠️ Difficile | ⚠️ Partiel |
| 12 | **Supermarché Aurès** | Flipp API (déjà sur Flipp!) | API REST JSON | ✅ Facile | ✅ Oui |
| 13 | **5 Saveurs** | Image JPG (WordPress) | Image | ❌ Très difficile | ✅ Oui |
| 14 | **Chois du Président** | PC Express API (Loblaws) | API REST JSON | ✅ Facile | ✅ Oui |

---

## Analyse Détaillée par Épicerie

### 1. IGA (iga.net) — Groupe Sobeys

**Source idéale :** Voila.ca API (`https://voila.ca/api/v2/...` ou v5)

**Détails :**
- ✅ IGA fait partie du groupe Sobeys. La plateforme d'épicerie en ligne est **Voila.ca** (voilà par IGA)
- ✅ L'API de Voila.ca est bien documentée et accessible sans authentification complexe
- ✅ Endpoint : `https://voila.ca/api/v5/...` (API versionnée REST)
- ✅ Retourne des données JSON structurées : nom, prix, prix unitaire, image, catégorie
- ✅ Section viande disponible : catégories "Meat & Poultry", "Beef", "Chicken", "Pork"
- ✅ L'Apify scraper `ocrad/voila-product-scraper` confirme le fonctionnement pour IGA.net, Sobeys.com, Safeway.ca, FarmBoy.ca
- ❌ La circulaire sur iga.net est une image (AEM platform), NE PAS utiliser

**URLs clés :**
- API : `https://voila.ca/api/v5/search?q=meat&location=H2X1Y4`
- Flyer (image) : `https://www.iga.net/fr/circulaire`
- Épicerie en ligne : `https://voila.ca/`

**Recommandation :** Scraper via Voila.ca API avec code postal QC. Filtrer par catégories viande.

---

### 2. Provigo (provigo.ca) — Groupe Loblaws

**Source idéale :** PC Express API (`https://api.pcexpress.ca/...`)

**Détails :**
- ✅ Provigo fait partie du groupe Loblaws. Utilise la plateforme **PC Express**
- ✅ API bien documentée : `api.pcexpress.ca` avec `X-Apikey` (pas d'authentification complexe)
- ✅ Banner ID : `provigo`
- ✅ Retourne JSON structuré : prix, nom, image, disponibilité
- ✅ Section viande disponible via les catégories PC Express
- ✅ Apify scraper `aitorsm/pcexpress-product-scraper` supporte Provigo
- ❌ La circulaire sur provigo.ca est une image/PDF, NE PAS utiliser

**URLs clés :**
- API : `https://api.pcexpress.ca/...` (via l'app PC Express)
- Flyer (image) : `https://www.provigo.ca/fr/print-flyer`
- Épicerie en ligne : `https://www.provigo.ca/fr/`

**Recommandation :** Utiliser PC Express API comme pour Maxi (déjà implémenté partiellement).

---

### 3. Maxi (maxi.ca) — Groupe Loblaws

**Source idéale :** PC Express API + Flipp API (déjà implémenté)

**Détails :**
- ✅ Déjà partiellement implémenté dans `scraper_maxi.py`
- ✅ Utilise la **Flipp flyers-ng API** (actuelle) — fonctionne bien
- ✅ **PC Express API** comme alternative plus stable : banner ID `maxi`
- ✅ JSON structuré avec prix, noms, images
- ✅ Section viande dédiée (beef, chicken, pork, etc.)

**URLs clés :**
- API Flipp : `https://flyers-ng.flippback.com/api/flipp/data`
- API PC Express : `https://api.pcexpress.ca/...`
- Site : `https://www.maxi.ca/fr/`

**Recommandation :** Migrer vers PC Express API (plus fiable que Flipp à long terme).

---

### 4. Walmart (walmart.ca)

**Sources disponibles :**
- **Flipp API** ✅ (déjà implémenté dans `scraper_walmart.py`)
- **Walmart GraphQL API** ⚠️ (complexe, protégé par PerimeterX)

**Détails :**
- ✅ La **Flipp API** fonctionne actuellement pour Walmart (via flyers-ng.flippback.com)
- ✅ Données en JSON, incluant noms, prix, images, dates de validité
- ⚠️ Walmart utilise **PerimeterX** anti-bot sur son site direct — très difficile à scraper directement
- ⚠️ L'API GraphQL de Walmart nécessite des tokens et résout des challenges PerimeterX
- ✅ Section viande : walmart.ca a une section "Meat & Seafood" dédiée

**URLs clés :**
- API Flipp : `https://flyers-ng.flippback.com/api/flipp/data` (avec `merchant=Walmart`)
- Site viande : `https://www.walmart.ca/en/browse/grocery/meat-seafood/10019_10086`
- GraphQL : `walmart.ca/orchestra/snb/graphql/search` (protégé)

**Recommandation :** Continuer avec Flipp API. Si Flipp devient indisponible, investiguer l'API GraphQL avec solver PerimeterX.

---

### 5. Costco (costco.ca)

**Source idéale (relative) :** Site Web (Playwright) + PDF coupons

**Détails :**
- ❌ **Pas d'API publique documentée** pour Costco Canada
- ❌ Site web protégé (bloque les requêtes automatisées)
- ⚠️ Les coupons spéciaux sont disponibles sur `costco.ca/coupons.html` avec sélection de province
- ⚠️ Les coupons mensuels étaient disponibles en PDF à des URLs prévisibles (format potentiellement obsolète)
- ✅ Section viande : `costco.ca/meat.html` — catégories Beef, Poultry, Pork, Fish & Seafood
- ✅ Prix en ligne disponibles pour les membres

**URLs clés :**
- Viande : `https://www.costco.ca/meat.html` / `https://www.costco.ca/meat.html?langId=-25`
- Coupons : `https://www.costco.ca/coupons.html?lang=fr-CA`
- Épicerie : `https://www.costco.ca/grocery-household.html`

**Recommandation :** Approche Playwright pour scraper les pages catégories avec sélection de province QC. Alternative : scraper les coupons PDF mensuels si le pattern URL est encore actif.

---

### 6. Les Marchés Tradition (marchestradition.com)

**Source idéale :** Flipp API (déjà implémenté)

**Détails :**
- ✅ Déjà implémenté dans `scraper_marchestradition.py`
- ✅ Utilise la **Flipp flyers-ng API** — fonctionne parfaitement
- ✅ Nom du marchand : `Les Marchés Tradition`
- ✅ JSON structuré avec prix, images, dates
- ✅ Section viande : boucherie traditionnelle, bonne sélection

**URLs clés :**
- API Flipp : `https://flyers-ng.flippback.com/api/flipp/data` (merchant=`Les Marchés Tradition`)
- Site : `https://www.marchestradition.com/`

**Recommandation :** Continuer avec Flipp API. Source fiable et stable.

---

### 7. Mayrand (mayrand.ca)

**Source idéale (relative) :** PDF parsing de la circulaire

**Détails :**
- ❌ **Circulaire en PDF uniquement** (format difficile à scraper)
- ✅ PDF disponible à URLs prévisibles : `mayrand.ca/hubfs/Circulaire_du_[DATE]_FR_VFFF.pdf`
- ✅ PDF contient les prix et descriptions texte (extractible avec PyPDF2/pdfplumber)
- ❌ Pas d'API publique, pas de site e-commerce
- ✅ Section viande : oui, Mayrand a une boucherie réputée
- ✅ HubSpot héberge les PDF, pas de protection particulière

**URLs clés :**
- Circulaire PDF : `https://mayrand.ca/hubfs/Circulaire%20du%2027%20mai%20au%202%20juin%202026%20FR%20VFFF.pdf`
- Page circulaire : `https://mayrand.ca/fr/nos-prix-rabais/issuu/`
- Page principale : `https://mayrand.ca/fr/notre-circulaire`

**Recommandation :** Scraper le PDF avec PyPDF2/pdfplumber. Chercher les mots-clés viande, extraire les prix. Approche OCR si le PDF est une image scannée.

---

### 8. Rachelle Béry (rachellebery.com) — Groupe Sobeys

**Source idéale :** Voila.ca API (via Sobeys/IGA)

**Détails :**
- ✅ Rachelle Béry appartient au groupe **Sobeys** (acquis en 2005)
- ✅ Utilise la même plateforme que IGA → données accessibles via **Voila.ca API**
- ✅ Boutiques santé intégrées dans les IGA également
- ✅ Circulaire sur le site WordPress mais les produits sont dans le catalogue Voila
- ✅ Section viande : oui (épicerie santé avec viande biologique/naturelle)
- ❌ La circulaire sur rachellebery.ca est un lien de téléchargement, format inconnu

**URLs clés :**
- API Voila : `https://voila.ca/api/v5/search?q=rachelle+bery`
- Circulaire : `https://www.rachellebery.ca/fr/circulaires/epicerie`
- Site : `https://www.rachellebery.ca/`

**Recommandation :** Utiliser la même API Voila.ca que IGA. Filtrer par marque Rachelle Béry ou localisation.

---

### 9. Les Aliments M&M (mmfoods.ca / mmfoodmarket.com)

**Source idéale (relative) :** Site Web (list view avec Playwright)

**Détails :**
- ✅ A une page **"list view"** avec produits et prix : `/en/categories/on-sale-now`
- ✅ 107+ produits en spécial chaque semaine
- ✅ Catégories viande : "Butcher", "Beef", "Chicken", "Pork", "Wings & chunks", "Burgers"
- ⚠️ **Prix cachés** — nécessite la sélection d'un magasin (store locator)
- ❌ Plateforme **Workarea Ecommerce** personnalisée, pas d'API JSON standard
- ❌ Pas de section viande fraîche (M&M = surgelé principalement)
- ⚠️ Les "meat items" sont des produits surgelés préparés, pas de la viande fraîche

**URLs clés :**
- Liste des spéciaux : `https://www.mmfoodmarket.com/en/categories/on-sale-now`
- Flyer : `https://www.mmfoodmarket.com/pages/flyer`
- Section viande surgelée : `/en/categories/butcher`

**Recommandation :** Approche Playwright : sélectionner un magasin, puis scraper la page "on-sale-now". Filtrer par catégories "Butcher", "Chicken", "Beef", "Pork". Effort moyen.

---

### 10. L'Inter-Marché (intermarche.com / lintermarche.ca) — Groupe Loblaws

**Source idéale :** PC Express API (Loblaws)

**Détails :**
- ✅ **Bannière Loblaws** (Independents group) — Freshmart, Apex, SuperValu
- ✅ Utilise la même plateforme Loblaws → **PC Express API**
- ✅ Banner ID : `independent` ou similaire
- ✅ Circulaire liée à Loblaws : `lintermarche.ca/circulaire/`
- ✅ Section viande : oui
- ❌ Site lintermarche.ca basique, peu de fonctionnalités e-commerce

**URLs clés :**
- API PC Express : `https://api.pcexpress.ca/...`
- Circulaire : `https://lintermarche.ca/circulaire/`
- Site : `https://lintermarche.ca/`

**Recommandation :** Même approche que Provogi/Maxi — PC Express API. Filtrer par bannière indépendante ou par code postal QC.

---

### 11. Fruiterie Potager (fruiteriepotager.com)

**Source idéale (relative) :** Circulaires.com (images) + Flipp API (si présent)

**Détails :**
- ❌ Site WordPress avec peu de données produits
- ❌ Circulaire en iframe (viewer de flyer image) — format image uniquement
- ⚠️ Présent sur **Circulaires.com** (aggrégateur de circulaires en images)
- ✅ Deux emplacements : Saint-Eustache et Blainville
- ⚠️ Section viande : limitée (fruiterie = fruits/légumes, mais ont charcuterie/fromage)

**URLs clés :**
- Circulaire : `https://fruiteriepotager.com/circulaire/` (iframe)
- Circulaires.com : `https://www.circulaires.com/fruiterie-potager/`
- Site : `https://fruiteriepotager.com/`
- Épicerie en ligne : `https://fruiteriepotager.com/boutique/`

**Recommandation :** OCR sur les images de circulaires.com, OU approche Playwright pour capturer les données de l'épicerie en ligne. Source difficile.

---

### 12. Supermarché Aurès (supermarcheaures.com)

**Source idéale :** Flipp API ✅ (déjà sur Flipp!)

**Détails :**
- ✅ **Déjà sur Flipp!** — "Généré par Flipp" sur leur page circulaire
- ✅ Instagram confirme : "Sur Flipp et Reebee!"
- ✅ Les spéciaux sont directement disponibles via la **Flipp flyers-ng API**
- ✅ Nouveau magasin (2025) à Laval, viande halal
- ✅ Section viande : boucherie halal, spécialités maghrébines

**URLs clés :**
- Circulaire (Flipp embed) : `https://supermarcheaures.com/circulaire`
- API Flipp : `https://flyers-ng.flippback.com/api/flipp/data` (tester avec `merchant=Supermarché Aurès` ou `Aurès`)
- Site : `https://supermarcheaures.com/`

**Recommandation :** Utiliser Flipp API. Trouver le nom exact du marchand dans la réponse Flipp. Meilleure source possible.

---

### 13. Marché 5 Saveurs (5saveurs.com)

**Source idéale (relative) :** Image JPG (WordPress) + OCR

**Détails :**
- ❌ **Circulaire en image JPG uniquement** sur WordPress
- ❌ `5saveurs.com/circulaire-du-28-mai-au-3-juin-2026/` → une seule image JPG
- ❌ Pas d'API, pas de données structurées
- ✅ Section viande : boucherie, poissonnerie, charcuterie
- ✅ Aussi sur `circulaires.com` (images) et `rabaischocs.com`
- ⚠️ Petit indépendant à Saint-Jérôme
- ⚠️ Page Facebook active

**URLs clés :**
- Circulaire : `https://5saveurs.com/speciaux/circulaire-de-la-semaine`
- Image URL : `https://5saveurs.com/wp-content/uploads/2026/05/20260528-975x1024.jpg`
- Circulaires.com : `https://www.circulaires.com/marche-5-saveurs/`

**Recommandation :** OCR (Tesseract) sur l'image JPG. Les URLs d'images suivent un pattern basé sur la date. Source très difficile, envisager OCR automatisé.

---

### 14. Le Choix du Président / President's Choice (PC) — Groupe Loblaws

**Source idéale :** PC Express API (Loblaws)

**Détails :**
- ✅ **Marque maison de Loblaws** — les produits PC sont disponibles via **PC Express API**
- ✅ API `api.pcexpress.ca` avec banner ID variés (superstore, loblaw, provigo, maxi, etc.)
- ✅ Les produits PC sont dans TOUTES les bannières Loblaws
- ✅ Sections dédiées : "PC", "PC Blue Menu", "PC Black Label", "PC Free From", "sans nom"
- ✅ Section viande : PC Blue Menu Chicken Breast, PC Beef, etc.
- ❌ Pas de site dédié pour la circulaire PC (les spéciaux sont dans les circulaires des bannières)

**URLs clés :**
- API PC Express : `https://api.pcexpress.ca/...`
- Marque : `https://www.lechoixdupresident.ca/`
- Circulaire Loblaws : `https://www.loblaws.ca/print-flyer`

**Recommandation :** Utiliser PC Express API. Filtrer par marque `"President's Choice"` ou `"PC"` dans les résultats. Idéal car les spéciaux PC sont disponibles dans TOUTES les bannières Loblaws.

---

## Recommandations Techniques Globales

### Priorité d'implémentation

| Priorité | Épicerie | Source | Effort | Impact |
|----------|----------|--------|--------|--------|
| 🔴 P0 | Maxi, Provigo, IGA, Walmart, Marchés Tradition, Aurès | Déjà implémenté (Flipp/Voila/PC Express) | Faible | Élevé |
| 🟡 P1 | Rachelle Béry, L'Inter-Marché, Choix du Président | API existante (Voila/PC Express) | Faible | Moyen |
| 🟠 P2 | M&M Food Market | Playwright (list view) | Moyen | Moyen |
| 🔵 P3 | Costco | Playwright (site) | Moyen-Élevé | Élevé |
| 🟤 P4 | Mayrand | PDF parsing | Élevé | Moyen |
| ⚪ P5 | Fruiterie Potager, 5 Saveurs | OCR/Images | Très élevé | Faible |

### Architecture des APIs

```
┌─────────────────────────────────────────────────────┐
│                  Aubaines-Rapides                    │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Loblaws Group          Sobeys Group   Indépendants │
│  ─────────────          ────────────   ──────────── │
│  • PC Express API       • Voila API    • Flipp API  │
│  │                      │              │            │
│  ├─ Provigo             ├─ IGA         ├─ Marchés   │
│  ├─ Maxi                ├─ Rachelle    │  Tradition │
│  ├─ L'Inter-Marché       │  Béry       ├─ Aurès     │
│  └─ PC (marque)         └─ Sobeys      └─ Walmart   │
│                                                     │
│  Playwright (HTML)         PDF / OCR                 │
│  ─────────────────         ────────                  │
│  • Costco                  • Mayrand                 │
│  • M&M Food Market         • 5 Saveurs               │
│                           • Fruiterie Potager        │
└─────────────────────────────────────────────────────┘
```

### Schéma de données unifié (recommandé)

```python
{
    "store": "string",          # Nom de l'épicerie
    "name": "string",           # Nom du produit
    "price": float,             # Prix courant
    "compare_at_price": float,  # Prix régulier (si en spécial)
    "unit_price": float,        # Prix unitaire (e.g., $/100g)
    "unit_type": "string",      # /kg, /lb, /100g, /ea
    "sale_text": "string",      # Texte brut du spécial
    "valid_from": "date",       # Début de l'offre
    "valid_to": "date",         # Fin de l'offre
    "image_url": "string",      # URL de l'image
    "meat_type": "string",      # boeuf, poulet, porc, etc.
    "category": "string",       # steak, haché, poitrine, etc.
    "product_code": "string",   # Code produit (si disponible)
    "scraped_at": "datetime"    # Timestamp
}
```

---

## Ce qui existe déjà

Fichiers déjà créés dans `scrapers/` :

| Fichier | Épiceries | Source |
|---------|-----------|--------|
| `scraper_maxi.py` | Maxi + Provigo | Flipp API + PC Express |
| `scraper_walmart.py` | Walmart | Flipp API |
| `scraper_marchestradition.py` | Les Marchés Tradition | Flipp API |
| `scraper_metro.py` | Metro (hors scope) | Playwright (HTML) |
| `scraper_superc.py` | Super C (hors scope) | Playwright (HTML) |
| `scraper_tigregeant.py` | Tigre Géant (hors scope) | Playwright (HTML) |

---

## Prochaines Actions Recommandées

1. **Migrer Maxi/Provigo** de Flipp API → PC Express API (plus stable)
2. **Créer scraper IGA** via Voila.ca API
3. **Créer scraper Rachelle Béry** via Voila.ca API (même code qu'IGA)
4. **Créer scraper L'Inter-Marché** via PC Express API
5. **Créer scraper PC** via PC Express API (filtrer marque Président's Choice)
6. **Créer scraper Aurès** via Flipp API (trouver le bon merchant name)
7. **Créer scraper Costco** via Playwright
8. **Créer scraper M&M** via Playwright (list view)
9. **Créer scraper Mayrand** via PDF parsing (pdfplumber)
10. **Créer scrapers 5 Saveurs et Fruiterie Potager** via OCR (en dernier)
