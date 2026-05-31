"""Vérifie la qualité des images TG dans le DB."""
import json, sqlite3, os

DB_PATH = r'C:\Users\Mark France\aubaines-rapides\data\aubaines.db'
DEALS_PATH = r'C:\Users\Mark France\aubaines-rapides\web\data\deals.json'

# Vérifier le JSON
with open(DEALS_PATH) as f:
    data = json.load(f)

tg_deals = [d for d in data['deals_with_kg'] if d.get('store') == 'Tigre Géant']
with_img = [d for d in tg_deals if d.get('image_url')]
without = [d for d in tg_deals if not d.get('image_url')]

print(f"=== DANS LE JSON ===")
print(f"TG deals: {len(tg_deals)}")
print(f"Avec image: {len(with_img)}")
print(f"Sans image: {len(without)}")

if without:
    print(f"\nSans image:")
    for d in without:
        print(f"  - {d['name'][:60]} (${d['price']:.2f})")

# Vérifier dans la DB
print(f"\n=== DANS LA DB ===")
db = sqlite3.connect(DB_PATH)
db.row_factory = sqlite3.Row
rows = db.execute("""
    SELECT ph.id, p.name, ph.price, ph.image_url
    FROM price_history ph
    JOIN products p ON ph.product_id = p.id
    JOIN stores s ON p.store_id = s.id
    WHERE s.name = 'Tigre Géant'
      AND ph.week_start = (
          SELECT MAX(week_start) FROM price_history 
          JOIN products ON price_history.product_id = products.id
          JOIN stores ON products.store_id = stores.id
          WHERE stores.name = 'Tigre Géant'
      )
      AND ph.image_url IS NOT NULL AND ph.image_url != ''
    LIMIT 30
""").fetchall()

print(f"Items TG avec image (DB): {len(rows)}")
for r in rows:
    print(f"  ✅ {r['image_url'][:60]}")
    print(f"     {r['name'][:55]} (${r['price']:.2f})")

db.close()
