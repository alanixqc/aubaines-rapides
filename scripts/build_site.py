"""build_site.py — Exporte la DB → JSON pour le site Aubaines Rapides
Exécuté après chaque scrape (cron) pour mettre à jour le site statique.
"""

import json
import sqlite3
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scripts.query import strip_accents, is_excluded, extract_weight_kg, find_default_weight, store_emoji, short_name

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "aubaines.db")
WEB_DIR = os.path.join(os.path.dirname(__file__), "..", "web", "data")

os.makedirs(WEB_DIR, exist_ok=True)


def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def export_deals():
    """Exporte tous les deals de la semaine courante."""
    db = get_db()
    max_week = db.execute("SELECT MAX(week_start) as w FROM price_history").fetchone()["w"]

    rows = db.execute("""
        SELECT p.id, p.name, p.meat_type, p.package_weight_g,
               s.name as store, s.id as store_id,
               ph.price, ph.unit_price, ph.unit_type,
               ph.valid_to, ph.merchant_name, ph.image_url, ph.flipp_item_id
        FROM products p
        JOIN stores s ON s.id = p.store_id
        JOIN price_history ph ON ph.product_id = p.id
        WHERE ph.week_start = ? AND ph.price IS NOT NULL AND p.meat_type IS NOT NULL
        ORDER BY ph.price ASC
    """, (max_week,)).fetchall()

    # Stats
    seen_products = set()
    meat_counts = defaultdict(int)
    store_set = set()
    deals = []

    for r in rows:
        if is_excluded(r["name"]):
            continue
        pk = (r["name"], r["merchant_name"])
        if pk in seen_products:
            continue
        seen_products.add(pk)

        mt = r["meat_type"] or "autre"
        store_set.add(r["merchant_name"])
        meat_counts[mt] += 1

        # Calculer $/kg
        per_kg = None
        source = None
        weight_kg = None

        if r["package_weight_g"] and r["price"]:
            weight_kg = r["package_weight_g"] / 1000
            per_kg = round(r["price"] / weight_kg, 2)
            source = "reel"
        elif r["unit_price"]:
            ut = r["unit_type"] or ""
            if "/kg" in ut:
                per_kg = round(r["unit_price"], 2)
                source = "image"
            elif "/100g" in ut:
                per_kg = round(r["unit_price"] * 10, 2)
                source = "image"
        if per_kg is None:
            w = extract_weight_kg(r["name"])
            if w and r["price"]:
                per_kg = round(r["price"] / w, 2)
                weight_kg = w
                source = "nom"
        if per_kg is None:
            w = find_default_weight(r["name"])
            if w and r["price"]:
                per_kg = round(r["price"] / w, 2)
                weight_kg = w
                source = "estime"

        per_lb = round(per_kg / 2.20462, 2) if per_kg else None

        deals.append({
            "id": r["id"],
            "name": r["name"],
            "name_short": short_name(r["name"], 40),
            "meat_type": mt,
            "store": r["merchant_name"],
            "store_id": r["store_id"],
            "store_emoji": store_emoji(r["merchant_name"]),
            "price": round(r["price"], 2) if r["price"] else None,
            "per_kg": per_kg,
            "per_lb": per_lb,
            "weight_kg": weight_kg,
            "source": source,
            "valid_to": r["valid_to"],
            "image_url": r["image_url"],
            "flipp_item_id": r["flipp_item_id"],
        })

    db.close()

    # Trier par $/kg
    deals_with_kg = [d for d in deals if d["per_kg"]]
    deals_with_kg.sort(key=lambda x: (x["per_kg"] if x["per_kg"] and x["per_kg"] > 0 else 99999, x["price"] or 0))

    deals_wo_kg = [d for d in deals if not d["per_kg"]]
    deals_wo_kg.sort(key=lambda x: x["price"] or 0)

    return {
        "deals_with_kg": deals_with_kg,
        "deals_wo_kg": deals_wo_kg,
        "stats": {
            "total": len(deals),
            "by_type": dict(meat_counts),
            "stores": sorted(store_set),
            "week": max_week,
            "generated_at": datetime.now().isoformat(),
        }
    }


def export_trends():
    """Exporte les tendances historiques StatCan."""
    db = get_db()
    rows = db.execute("""
        SELECT product, ref_date, value, uom
        FROM statcan_prices
        ORDER BY product, ref_date ASC
    """).fetchall()
    db.close()

    trends = defaultdict(list)
    for r in rows:
        trends[r["product"]].append({
            "date": r["ref_date"],
            "price": round(r["value"], 2),
            "unit": r["uom"],
        })

    return [{"product": p, "data": d} for p, d in sorted(trends.items())]


def export_products():
    """Exporte la liste de tous les produits pour la recherche."""
    db = get_db()
    max_week = db.execute("SELECT MAX(week_start) as w FROM price_history").fetchone()["w"]

    rows = db.execute("""
        SELECT DISTINCT p.name, p.meat_type, s.name as store,
               ph.price, ph.merchant_name, ph.valid_to, ph.image_url
        FROM products p
        JOIN stores s ON s.id = p.store_id
        JOIN price_history ph ON ph.product_id = p.id
        WHERE ph.week_start = ? AND ph.price IS NOT NULL AND p.meat_type IS NOT NULL
        ORDER BY p.name ASC
    """, (max_week,)).fetchall()
    db.close()

    products = []
    seen = set()
    for r in rows:
        if is_excluded(r["name"]):
            continue
        k = (r["name"], r["merchant_name"])
        if k in seen:
            continue
        seen.add(k)
        products.append({
            "name": r["name"],
            "name_short": short_name(r["name"], 50),
            "meat_type": r["meat_type"] or "autre",
            "store": r["merchant_name"],
            "store_emoji": store_emoji(r["merchant_name"]),
            "price": round(r["price"], 2) if r["price"] else None,
            "valid_to": r["valid_to"],
            "image_url": r["image_url"],
        })

    return products


def export_stores():
    """Exporte la liste des magasins."""
    db = get_db()
    rows = db.execute("SELECT id, name, slug FROM stores ORDER BY name").fetchall()
    db.close()
    return [{
        "id": r["id"],
        "name": r["name"],
        "emoji": store_emoji(r["name"]),
        "slug": r["slug"],
    } for r in rows]


def main():
    print("📦 Exportation des données pour le site...")

    deals = export_deals()
    with open(os.path.join(WEB_DIR, "deals.json"), "w", encoding="utf-8") as f:
        json.dump(deals, f, ensure_ascii=False, indent=2)
    print(f"  ✅ deals.json — {deals['stats']['total']} deals, {len(deals['deals_with_kg'])} avec $/kg")

    trends = export_trends()
    with open(os.path.join(WEB_DIR, "trends.json"), "w", encoding="utf-8") as f:
        json.dump(trends, f, ensure_ascii=False, indent=2)
    print(f"  ✅ trends.json — {len(trends)} produits")

    products = export_products()
    with open(os.path.join(WEB_DIR, "products.json"), "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    print(f"  ✅ products.json — {len(products)} produits")

    stores = export_stores()
    with open(os.path.join(WEB_DIR, "stores.json"), "w", encoding="utf-8") as f:
        json.dump(stores, f, ensure_ascii=False, indent=2)
    print(f"  ✅ stores.json — {len(stores)} magasins")

    # Stats pour affichage rapide
    stats = deals["stats"]
    stats["stores_count"] = len(stores)
    stats["trends_count"] = len(trends)
    with open(os.path.join(WEB_DIR, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"  ✅ stats.json")

    print(f"\n📊 Résumé : {stats['total']} offres · {stats['stores_count']} magasins · {len(trends)} tendances historiques")


if __name__ == "__main__":
    main()
