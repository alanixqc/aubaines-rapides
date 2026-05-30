# Aubaines Rapides 🚀🥩

Scraper automatique de circulaires d'épicerie pour trouver les meilleurs deals de viande au Québec.

**Tagline:** *On fait les maths. Tu fais les économies.*

## Stack

- **Data source:** API Flipp — couvre 18 épiceries du Québec
- **Database:** SQLite (`data/aubaines.db`)
- **Site web:** GitHub Pages → https://alanixqc.github.io/aubaines-rapides/
- **Discord:** Commandes !deal et !produit dans #aubaines-rapides
- **Schedule:** Cron job chaque mardi 8h30 (livré automatiquement dans Discord)

## Stats (30 mai 2026)

- 3 614 produits dans la base
- 7 228 entrées de prix (2 semaines d'historique)
- 338 items viande/semaine (86 bœuf · 157 poulet · 95 porc)
- 18 épiceries scannées autour de Saint-Jérôme

## Commandes Discord

| Commande | Description |
|----------|-------------|
| `!deal` | Top 3 deals à Saint-Jérôme |
| `!deal H2X1Y3` | Top 3 près d'un code postal |
| `!produit haché` | Tous les items "haché" avec $/kg |
| `!produit poitrine` | Tous les items "poitrine" en rabais |
| `!aide` | Aide du bot |

## Utilisation

```bash
# Pipeline complet (scrape + déduplication + rapport)
python scripts/pipeline.py

# Scraper seulement
python scraper/flipp_scraper.py

# Rapport HTML seulement
python scripts/generate_report.py

# Commandes Discord
python scripts/deal.py                # !deal
python scripts/deal.py "H2X1Y3"      # !deal avec code postal
python scripts/query.py "haché"      # !produit haché
```

## Déploiement site web

Le site est hébergé sur GitHub Pages:
1. `git add . && git commit -m "..." && git push`
2. GitHub Pages rebuild automatiquement
3. Accès: https://alanixqc.github.io/aubaines-rapides/

## Bot Discord autonome (optionnel)

Pour un bot Discord qui répond 24/7 sans Hermes:

1. Crée une application sur https://discord.com/developers/applications
2. Copie le token et définis la variable d'environnement:
   ```bash
   export AUBAINES_RAPIDES_BOT_TOKEN="ton_token_ici"
   ```
3. Lance le bot:
   ```bash
   python bot/bot.py
   ```

## Structure du projet

```
aubaines-rapides/
├── data/              # DB SQLite + logs + status
├── db/
│   └── schema.py      # Schema + connexion DB
├── scraper/
│   └── flipp_scraper.py  # Scraper Flipp API
├── scripts/
│   ├── pipeline.py        # Pipeline complet (robuste)
│   ├── deal.py            # !deal — top 3 deals
│   ├── query.py           # !produit — recherche
│   ├── generate_report.py # Rapport HTML
│   └── nearby_stores.py   # OSM géocodage
├── web/
│   ├── index.html         # Site principal
│   └── plan-d-affaires.html
├── bot/
│   └── bot.py             # Bot Discord autonome
├── .gitignore
├── .nojekyll
└── README.md
```

## Roadmap

- ✅ Scraper Flipp — automatisé (cron mardi 8h30)
- ✅ Site web — GitHub Pages
- ✅ Discord commands — !deal, !produit
- ✅ Pipeline robuste — logging, statut, auto-post
- ✅ Analyse concurrentielle en mémoire
- 🔜 Recettes IA liées aux deals de la semaine
- 🔜 Abonnement Premium (alertes, historique 52 sem)
- 🔜 Newsletter email
- 🔜 Bot Discord autonome
