# Les Aubaines Rapides 🚀🥩

Scraper automatique de circulaires d'épicerie pour trouver les meilleurs deals de viande (bœuf, poulet, porc) au Québec.

## Stack

- **Data source:** API Flipp (non-documentée) — couvre Super C, Metro, IGA, Maxi, Provigo, Walmart, Costco +
- **Database:** SQLite (`data/aubaines.db`)
- **Rapport:** HTML statique (`web/index.html`)
- **Schedule:** Cron job chaque mardi 8h30

## Utilisation

```bash
# Pipeline complet
python scripts/pipeline.py

# Scraper seulement
python scraper/flipp_scraper.py

# Rapport seulement
python scripts/generate_report.py
```

## Stats 29 mai 2026

- 296 items viande uniques en rabais cette semaine
- 76 bœuf | 130 poulet | 90 porc
- 15+ magasins scannés autour de Saint-Jérôme

## À venir

- 🔜 Filtres par prix/kg pour voir les vrais aubaines
- 🔜 Graphiques historique 52 semaines
- 🔜 Alertes Discord quand un prix bat le record
- 🔜 Recettes avec panier le moins cher
