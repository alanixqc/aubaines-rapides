#!/usr/bin/env python3
"""
Pipeline Aubanes Rapides — version INDÉPENDANTE (sans Flipp)
=============================================================
Exécute les scrapers directs (Shopify, Playwright) + dédup + build site.
Aucune dépendance à Flipp/flippback/wishabi.
Exécuté par cron chaque mardi 8h30
"""
import sys
import os
import json
import logging
import subprocess
from datetime import datetime, date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.generate_report import generate_html
from db.schema import get_db

# ─── Configuration ───────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
STATUS_FILE = os.path.join(PROJECT_ROOT, "data", "pipeline_status.json")
LOG_FILE = os.path.join(PROJECT_ROOT, "data", "pipeline.log")
SCRIPTERS_DIR = os.path.join(PROJECT_ROOT, "scrapers")
PYTHON = sys.executable


def setup_logging():
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
    total_meat = status_data.get("stats", {}).get("total_meat", 0)
    if status_data["success"] and total_meat < 50:
        status_data["warning"] = f"Seulement {total_meat} items viande (seuil: 50)"
    status_data["last_run"] = datetime.now().isoformat()
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status_data, f, indent=2, ensure_ascii=False)
    logging.info(f"📝 Statut sauvegardé dans {STATUS_FILE}")
    
    # Copie allégée vers web/data/status.json pour le site
    web_status = os.path.join(PROJECT_ROOT, "web", "data", "status.json")
    web_data = {
        "success": status_data["success"],
        "last_run": status_data["last_run"],
        "warning": status_data.get("warning"),
        "total_products": status_data.get("stats", {}).get("total_products"),
        "total_prices": status_data.get("stats", {}).get("total_prices"),
    }
    os.makedirs(os.path.dirname(web_status), exist_ok=True)
    with open(web_status, "w", encoding="utf-8") as f:
        json.dump(web_data, f, indent=2, ensure_ascii=False)


def run_scraper(name, args=None, timeout=120):
    """Run a scraper subprocess and return (success, output)."""
    path = os.path.join(SCRIPTERS_DIR, f"scraper_{name}.py")
    if not os.path.exists(path):
        logging.warning(f"   ⚠️ Scraper {name} introuvable: {path}")
        return False, ""

    cmd = [PYTHON, path, "--db"]
    if args:
        cmd.extend(args)

    logging.info(f"   ▶️ python scraper_{name}.py {' '.join(args or ['--db'])}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        for line in result.stderr.strip().split("\n"):
            if line.strip():
                logging.info(f"   {line.strip()}")
        if result.stdout.strip():
            logging.info(f"   stdout: {result.stdout.strip()[:200]}")
        if result.returncode != 0:
            logging.error(f"   ❌ {name} échec (code {result.returncode})")
            return False, result.stderr
        return True, ""
    except subprocess.TimeoutExpired:
        logging.error(f"   ❌ {name} timeout ({timeout}s)")
        return False, "timeout"
    except Exception as e:
        logging.error(f"   ❌ {name} exception: {e}")
        return False, str(e)


def get_weekly_summary():
    """Récupère le top 3 deals pour le résumé final."""
    from scripts.deal import enrich, is_excluded

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
    top3 = enriched[:3]
    medals = ["🥇", "🥈", "🥉"]

    lines = ["🏆  TOP 3 DEALS DE LA SEMAINE  🏆"]
    for i, e in enumerate(top3):
        r = e["r"]
        store_emoji = {"Super C": "🟡", "Metro": "🔴", "Tigre Géant": "🐯"}.get(r["merchant_name"], "🏪")
        meat_emoji = {"boeuf": "🥩", "poulet": "🍗", "porc": "🥓"}.get(r["meat_type"], "")
        per_lb = round(e["per_kg"] / 2.20462, 2)
        line = f"\n{medals[i]} {store_emoji} **{r['merchant_name']}** {meat_emoji}"
        line += f"\n   {r['name'][:40]}"
        line += f"\n   💰 {r['price']:.2f}$  ·  {e['per_kg']:.2f}$/kg  ·  {per_lb:.2f}$/lb"
        lines.append(line)

    total_meat = len(enriched)
    stores = set(e["r"]["merchant_name"] for e in enriched)
    lines.append(f"\n📊 {total_meat} offres · {len(stores)} épiceries")
    lines.append("📍 Données indépendantes · pas de Flipp")
    return "\n".join(lines)


def run_pipeline():
    logger = setup_logging()
    start_time = datetime.now()

    logger.info("=" * 60)
    logger.info("🔄 PIPELINE AUBANES RAPIDES — INDÉPENDANT")
    logger.info("   Sans Flipp · Scrapers directs uniquement")
    logger.info("=" * 60)

    status = {"success": False, "error": None, "stats": {}, "started_at": start_time.isoformat()}
    scrapers_stats = {}

    try:
        # ── Phase 0: Scrapers API directes (Shopify, etc.) ──
        logger.info("\n🔧 Phase 0: Scrapers API directes...")
        api_scrapers = [
            ("tigregeant", ["--db"], 120),
        ]
        for name, args, tout in api_scrapers:
            ok, err = run_scraper(name, args, timeout=tout)
            scrapers_stats[name] = {"success": ok, "error": err if not ok else None}
            logger.info(f"   {'✅' if ok else '❌'} {name}")

        # ── Phase 0b: Playwright scrapers ──
        logger.info("\n🌐 Phase 0b: Scrapers Playwright...")
        playwright_scrapers = ["superc"]
        for name in playwright_scrapers:
            ok, err = run_scraper(name, ["--db", "--headless", "true"], timeout=180)
            scrapers_stats[name] = {"success": ok, "error": err if not ok else None}
            logger.info(f"   {'✅' if ok else '❌'} {name}")

        # ── Phase 1: Déduplication ──
        logger.info("\n🧹 Phase 1: Nettoyage des doublons...")
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

        # ── Phase 2: Rapport HTML ──
        logger.info("\n📊 Phase 2: Génération du rapport HTML...")
        html_content = generate_html()
        logger.info("   ✅ Rapport généré")

        # ── Phase 3: Stats ──
        db = get_db()
        total_products = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        total_prices = db.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
        weeks = [r["week_start"] for r in
                 db.execute("SELECT DISTINCT week_start FROM price_history ORDER BY week_start").fetchall()]

        meat_by_store = db.execute("""
            SELECT ph.merchant_name, COUNT(DISTINCT ph.product_id) as cnt
            FROM price_history ph
            JOIN products p ON p.id = ph.product_id
            WHERE ph.week_start = (SELECT MAX(week_start) FROM price_history)
              AND p.meat_type IS NOT NULL
            GROUP BY ph.merchant_name ORDER BY cnt DESC
        """).fetchall()
        
        total_meat_current = sum(r["cnt"] for r in meat_by_store)
        db.close()

        logger.info(f"\n📈 Base de données:")
        logger.info(f"   Produits: {total_products}")
        logger.info(f"   Prix: {total_prices}")
        logger.info(f"   Semaines: {', '.join(weeks) if weeks else 'aucune'}")
        for row in meat_by_store:
            logger.info(f"   {row['merchant_name']:25s}  {row['cnt']:3d} items")

        # ── Résumé ──
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"\n✅ Pipeline terminé en {elapsed:.1f}s")
        logger.info(f"   Items viande semaine courante: {total_meat_current}")

        status["success"] = True
        status["stats"] = {
            "scrapers": {k: {"success": v["success"]} for k, v in scrapers_stats.items()},
            "total_meat": total_meat_current,
            "total_products": total_products,
            "total_prices": total_prices,
            "weeks": weeks,
            "meat_by_store": {r["merchant_name"]: r["cnt"] for r in meat_by_store},
            "elapsed_seconds": round(elapsed, 1),
            "source": "indépendant (aucun Flipp)",
        }
        save_status(status)

        # ── Summary ──
        summary = get_weekly_summary()
        if summary:
            print(f"\n{'=' * 60}")
            print(summary)
            print(f"\n{'=' * 60}")

        # ── Build site (JSON data) ──
        logger.info("\n📦 Génération des données pour le site...")
        try:
            subprocess.run(
                [PYTHON, os.path.join(PROJECT_ROOT, "scripts", "build_site.py")],
                check=True, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=60
            )
            logger.info("   ✅ Site data généré")
        except subprocess.CalledProcessError as e:
            logger.error(f"   ⚠️ build_site: {e.stderr}")

        # ── Commit & push site data ──
        logger.info("\n📤 Push vers GitHub Pages...")
        try:
            subprocess.run(
                ["git", "add", "web/data/"],
                check=True, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=30
            )
            result = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=PROJECT_ROOT, capture_output=True, timeout=15
            )
            if result.returncode == 1:
                subprocess.run(
                    ["git", "commit", "-m", f"auto: site data {datetime.now().strftime('%Y-%m-%d')}"],
                    check=True, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=30
                )
                subprocess.run(
                    ["git", "push"],
                    check=True, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=60
                )
                logger.info("   ✅ Pushé sur GitHub")
            else:
                logger.info("   Rien à commit (pas de changements)")
        except subprocess.CalledProcessError as e:
            logger.error(f"   ⚠️ Git push: {e.stderr}")

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
