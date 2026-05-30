#!/usr/bin/env python3
"""
Pipeline Aubanes Rapides — version robuste avec statut
Exécuté par cron chaque mardi 8h30
"""
import sys
import os
import json
import logging
from datetime import datetime, date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scraper.flipp_scraper import FlippScraper
from scripts.generate_report import generate_html
from db.schema import get_db

# ─── Configuration ───────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
STATUS_FILE = os.path.join(PROJECT_ROOT, "data", "pipeline_status.json")
LOG_FILE = os.path.join(PROJECT_ROOT, "data", "pipeline.log")


def setup_logging():
    """Configure logging to file and stdout."""
    log_format = "%(asctime)s [%(levelname)s] %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger(__name__)


def save_status(status_data):
    """Saves pipeline run status to JSON file for monitoring."""
    status_data["last_run"] = datetime.now().isoformat()
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status_data, f, indent=2, ensure_ascii=False)
    logging.info(f"📝 Statut sauvegardé dans {STATUS_FILE}")


def get_weekly_summary():
    """Récupère les top deals pour les afficher dans le résumé."""
    from scripts.deal import enrich, is_excluded, format_price_line, format_protein_line

    db = get_db()
    max_week = db.execute("SELECT MAX(week_start) as w FROM price_history").fetchone()["w"]

    rows = db.execute(
        """SELECT p.id, p.name, p.meat_type, p.package_weight_g,
                  s.name as store, ph.price, ph.unit_price, ph.unit_type,
                  ph.valid_to, ph.merchant_name, ph.image_url
           FROM products p
           JOIN stores s ON s.id = p.store_id
           JOIN price_history ph ON ph.product_id = p.id
           WHERE ph.week_start = ? AND ph.price IS NOT NULL AND p.meat_type IS NOT NULL
           ORDER BY ph.price ASC LIMIT 3000""",
        (max_week,),
    ).fetchall()
    db.close()

    # Enrich + dedup + exclude
    enriched = []
    seen = set()
    for r in rows:
        if is_excluded(r["name"]):
            continue
        key = (r["name"], r["merchant_name"])
        if key in seen:
            continue
        seen.add(key)
        per_kg, source, is_est, weight_kg = enrich(r)
        if per_kg:
            enriched.append({"r": r, "per_kg": per_kg, "source": source, "weight_kg": weight_kg})

    if not enriched:
        return None

    enriched.sort(key=lambda x: x["per_kg"] if x["per_kg"] and x["per_kg"] > 0 else 99999)

    # Take top 3
    top3 = enriched[:3]
    summary_lines = ["🏆  TOP 3 DEALS DE LA SEMAINE  🏆"]
    medals = ["🥇", "🥈", "🥉"]
    for i, e in enumerate(top3):
        r = e["r"]
        store_emoji = {"Super C": "🟡", "Metro": "🔴", "IGA": "🟢", "Maxi": "🟠",
                       "Provigo": "🟣", "Walmart": "🔵", "Costco": "⭕",
                       "Tigre Géant": "🐯", "Les Marchés Tradition": "🟤"}.get(r["merchant_name"], "🏪")
        meat_emoji = {"boeuf": "🥩", "poulet": "🍗", "porc": "🥓"}.get(r["meat_type"], "")
        per_lb = round(e["per_kg"] / 2.20462, 2)
        line = f"\n{medals[i]} {store_emoji} **{r['merchant_name']}** {meat_emoji}"
        line += f"\n   {r['name'][:40]}"
        line += f"\n   💰 {r['price']:.2f}$  ·  {e['per_kg']:.2f}$/kg  ·  {per_lb:.2f}$/lb"
        summary_lines.append(line)

    # Stats
    total_meat = len(enriched)
    stores = set(e["r"]["merchant_name"] for e in enriched)
    summary_lines.append(f"\n📊 {total_meat} offres · {len(stores)} épiceries")
    summary_lines.append("📍 Saint-Jérôme · !deal [codepostal] pour filtrer")

    return "\n".join(summary_lines)


def run_pipeline():
    logger = setup_logging()
    start_time = datetime.now()

    logger.info("=" * 60)
    logger.info("🔄 PIPELINE AUBANES RAPIDES")
    logger.info("=" * 60)

    status = {"success": False, "error": None, "stats": {}, "started_at": start_time.isoformat()}

    try:
        # ── Phase 1: Scraper ──
        logger.info("\n📡 Phase 1: Scraping Flipp...")
        scraper = FlippScraper()
        stats = scraper.run()

        logger.info(f"   Items scrapés:   {stats.get('items_scraped', 0)}")
        logger.info(f"   Items viande:    {stats.get('meat_items', 0)}")
        logger.info(f"   Nouvelles entrées: {stats.get('new_entries', 0)}")
        status["stats"]["scrape"] = stats

        # ── Phase 2: Déduplication ──
        logger.info("\n🧹 Phase 2: Nettoyage des doublons...")
        db = get_db()
        db.execute("""
            DELETE FROM price_history WHERE id NOT IN (
                SELECT MAX(id) FROM price_history
                GROUP BY product_id, week_start, merchant_name
            )
        """)
        dedup_count = db.total_changes
        db.commit()
        db.close()
        logger.info(f"   ✅ {dedup_count} doublons nettoyés")

        # ── Phase 3: Rapport HTML ──
        logger.info("\n📊 Phase 3: Génération du rapport...")
        html_content = generate_html()
        logger.info("   ✅ Rapport généré")

        # ── Phase 4: Statut des données ──
        db = get_db()
        total_products = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        total_prices = db.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
        weeks = [r["week_start"] for r in
                 db.execute("SELECT DISTINCT week_start FROM price_history ORDER BY week_start").fetchall()]
        db.close()

        logger.info(f"\n📈 Base de données:")
        logger.info(f"   Produits: {total_products}")
        logger.info(f"   Prix historiques: {total_prices}")
        logger.info(f"   Semaines: {', '.join(weeks) if weeks else 'aucune'}")

        # ── Résumé ──
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"\n✅ Pipeline terminé en {elapsed:.1f}s")
        logger.info(f"   Items scrapés:   {stats.get('items_scraped', 0)}")
        logger.info(f"   Items viande:    {stats.get('meat_items', 0)}")

        status["success"] = True
        status["stats"]["total_products"] = total_products
        status["stats"]["total_prices"] = total_prices
        status["stats"]["weeks"] = weeks
        status["stats"]["elapsed_seconds"] = round(elapsed, 1)
        save_status(status)

        # ── Summary for Discord ──
        summary = get_weekly_summary()
        if summary:
            print(f"\n{'=' * 60}")
            print(summary)
            print(f"\n{'=' * 60}")

        return status

    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.error(f"\n❌ Pipeline ÉCHOUÉ après {elapsed:.1f}s: {e}")
        import traceback
        logger.error(traceback.format_exc())

        status["success"] = False
        status["error"] = str(e)
        status["stats"]["elapsed_seconds"] = round(elapsed, 1)
        save_status(status)
        return status


if __name__ == "__main__":
    result = run_pipeline()
    sys.exit(0 if result["success"] else 1)
