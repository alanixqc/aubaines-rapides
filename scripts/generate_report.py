#!/usr/bin/env python3
"""
Rapport HTML — Meilleurs deals viande de la semaine
"""
import sys
import os
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db.schema import get_db, DB_PATH

OUTPUT_PATH = os.path.join(os.path.dirname(DB_PATH), "..", "web", "index.html")

MEAT_EMOJI = {"boeuf": "🥩", "poulet": "🍗", "porc": "🥓"}
MEAT_COLORS = {"boeuf": "#e74c3c", "poulet": "#f39c12", "porc": "#e67e22"}


def format_price(price):
    if price is None:
        return "—"
    return f"${price:.2f}"


def get_best_deals(meat_type, limit=15):
    """Récupère les meilleurs deals pour un type de viande."""
    db = get_db()
    rows = db.execute(
        """SELECT p.name, s.name as store, ph.price, ph.sale_text,
                  ph.valid_from, ph.valid_to, ph.merchant_name,
                  (SELECT AVG(ph2.price) FROM price_history ph2
                   JOIN products p2 ON p2.id = ph2.product_id
                   WHERE p2.meat_type = p.meat_type
                   AND p2.name = p.name
                   AND ph2.price IS NOT NULL) as avg_price
           FROM price_history ph
           JOIN products p ON p.id = ph.product_id
           JOIN stores s ON s.id = p.store_id
           WHERE p.meat_type = ?
             AND ph.week_start = date('now')
             AND ph.price IS NOT NULL
           GROUP BY p.name, s.name
           ORDER BY ph.price ASC
           LIMIT ?""",
        (meat_type, limit),
    ).fetchall()
    db.close()
    return rows


def get_price_history(product_name, store_name):
    """Récupère l'historique des prix pour un produit."""
    db = get_db()
    rows = db.execute(
        """SELECT ph.price, ph.week_start
           FROM price_history ph
           JOIN products p ON p.id = ph.product_id
           JOIN stores s ON s.id = p.store_id
           WHERE p.name = ? AND s.name = ?
           ORDER BY ph.week_start DESC
           LIMIT 52""",
        (product_name, store_name),
    ).fetchall()
    db.close()
    return rows


def count_meat_items():
    """Compte les items viande cette semaine."""
    db = get_db()
    rows = db.execute(
        """SELECT p.meat_type, COUNT(DISTINCT p.name || s.name) as cnt
           FROM price_history ph
           JOIN products p ON p.id = ph.product_id
           JOIN stores s ON s.id = p.store_id
           WHERE p.meat_type IS NOT NULL
             AND ph.week_start = date('now')
           GROUP BY p.meat_type
           ORDER BY cnt DESC"""
    ).fetchall()
    db.close()
    return rows


def count_by_store():
    """Compte les items viande par magasin."""
    db = get_db()
    rows = db.execute(
        """SELECT s.name, COUNT(DISTINCT p.name || s.name) as cnt
           FROM price_history ph
           JOIN products p ON p.id = ph.product_id
           JOIN stores s ON s.id = p.store_id
           WHERE p.meat_type IS NOT NULL
             AND ph.week_start = date('now')
           GROUP BY s.name
           ORDER BY cnt DESC"""
    ).fetchall()
    db.close()
    return rows


def generate_html():
    today = date.today()
    week_start = today.strftime("%Y-%m-%d")

    counts = count_meat_items()
    total_items = sum(r["cnt"] for r in counts)
    store_counts = count_by_store()

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Aubaines Rapides — Meilleurs Deals Viande</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          background: #0f0f0f; color: #e0e0e0; line-height: 1.6; }}
  .container {{ max-width: 1100px; margin: 0 auto; padding: 20px; }}
  header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            padding: 30px 0; text-align: center; border-bottom: 3px solid #e94560; margin-bottom: 30px; }}
  header h1 {{ font-size: 2em; color: #fff; }}
  header p {{ color: #aaa; font-size: 1.1em; }}
  .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px; margin-bottom: 30px; }}
  .stat-card {{ background: #1a1a2e; border-radius: 10px; padding: 20px; text-align: center; }}
  .stat-card .num {{ font-size: 2em; font-weight: bold; }}
  .stat-card .label {{ color: #888; font-size: 0.9em; }}
  .stat-card.boeuf .num {{ color: #e74c3c; }}
  .stat-card.poulet .num {{ color: #f39c12; }}
  .stat-card.porc .num {{ color: #e67e22; }}
  .store-list {{ background: #1a1a2e; border-radius: 10px; padding: 20px; margin-bottom: 30px; }}
  .store-list h3 {{ margin-bottom: 10px; color: #ccc; }}
  .store-list .tag {{ display: inline-block; background: #16213e; padding: 5px 12px;
                     border-radius: 15px; margin: 3px; font-size: 0.85em; }}
  .deals-section {{ margin-bottom: 30px; }}
  .deals-section h2 {{ margin-bottom: 15px; padding-bottom: 8px; border-bottom: 2px solid #333; }}
  .deal-card {{ background: #1a1a2e; border-radius: 8px; padding: 15px; margin-bottom: 8px;
               display: flex; justify-content: space-between; align-items: center;
               transition: transform 0.2s; }}
  .deal-card:hover {{ transform: translateX(5px); background: #1f1f3e; }}
  .deal-card .info {{ flex: 1; }}
  .deal-card .store-name {{ font-size: 0.8em; color: #888; }}
  .deal-card .product-name {{ font-size: 1em; color: #fff; }}
  .deal-card .price {{ font-size: 1.3em; font-weight: bold; text-align: right; }}
  .deal-card .price.sale {{ color: #2ecc71; }}
  .deal-card .dates {{ font-size: 0.75em; color: #666; text-align: right; }}
  footer {{ text-align: center; color: #555; padding: 20px; font-size: 0.85em; }}
  .update-badge {{ background: #e94560; color: #fff; font-size: 0.7em;
                   padding: 2px 8px; border-radius: 10px; }}
</style>
</head>
<body>
<header>
  <div class="container">
    <h1>🥩 Aubaines Rapides</h1>
    <p>Meilleurs deals viande de la semaine — {today.strftime('%d %B %Y').lower()}</p>
    <span class="update-badge">Mise à jour hebdomadaire</span>
  </div>
</header>
<div class="container">

<div class="stats">
  <div class="stat-card">
    <div class="num" style="color:#2ecc71;">{total_items}</div>
    <div class="label">Items viande en rabais</div>
  </div>
"""

    for c in counts:
        mt = c["meat_type"]
        emoji = MEAT_EMOJI.get(mt, "")
        html += f"""  <div class="stat-card {mt}">
    <div class="num">{c["cnt"]}</div>
    <div class="label">{emoji} {mt.capitalize()}</div>
  </div>
"""

    html += """</div>
<div class="store-list">
  <h3>🏪 Magasins scannés</h3>
"""
    for sc in store_counts:
        html += f'  <span class="tag">{sc["name"]} ({sc["cnt"]})</span>\n'

    html += """</div>
"""

    # Deals par type de viande
    for mt in ["boeuf", "poulet", "porc"]:
        emoji = MEAT_EMOJI.get(mt, "")
        deals = get_best_deals(mt)
        if not deals:
            continue

        html += f"""<div class="deals-section">
  <h2 style="border-color:{MEAT_COLORS.get(mt, '#333')};">{emoji} Meilleurs deals — {mt.capitalize()}</h2>
"""
        for d in deals:
            p = d["price"]
            is_good = p is not None and d["avg_price"] is not None and p < d["avg_price"]
            price_class = "sale" if is_good else ""
            savings = f" -{(1 - p/d['avg_price'])*100:.0f}%" if is_good and p and d['avg_price'] else ""
            dates = f"du {d['valid_from']}" if d["valid_from"] else ""
            if d["valid_to"]:
                dates += f" au {d['valid_to']}"

            html += f"""  <div class="deal-card">
    <div class="info">
      <div class="store-name">[{d["store"]}]</div>
      <div class="product-name">{d["name"][:55]}</div>
    </div>
    <div>
      <div class="price {price_class}">{format_price(p)}{savings}</div>
      <div class="dates">{dates}</div>
    </div>
  </div>
"""

        html += "</div>\n"

    scraped_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    html += f"""
<footer>
  <p>Scrapé automatiquement via Flipp API · Dernière mise à jour : {scraped_at}</p>
  <p style="margin-top:5px;">📍 Saint-Jérôme, QC · Code postal J7Y4A2</p>
</footer>
</div>
</body>
</html>"""

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ Rapport généré : {OUTPUT_PATH}")
    return html


if __name__ == "__main__":
    generate_html()
