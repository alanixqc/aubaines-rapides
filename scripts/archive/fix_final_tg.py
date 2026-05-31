"""Fix final: shrimp items + rebuild JSON."""
import json, sqlite3, os

DB_PATH = r'C:\Users\Mark France\aubaines-rapides\data\aubaines.db'
SHOPIFY_PATH = r'C:\Users\Mark France\aubaines-rapides\cache\tigregeant\shopify_products.json'

# Images des crevettes blanches du Pacifique
SHRIMP_IMG_URLS = [
    "https://cdn.shopify.com/s/files/1/0557/6858/0157/products/gs1_714076_gs1_01_ml.jpg?v=1745437315",
    "https://cdn.shopify.com/s/files/1/0557/6858/0157/files/gs1_520596_gs1_01_ml.jpg?v=1745437315",
]

db = sqlite3.connect(DB_PATH)
db.row_factory = sqlite3.Row

# Trouver les ID des deux items shrimp
rows = db.execute("""
    SELECT ph.id, p.name FROM price_history ph
    JOIN products p ON ph.product_id = p.id
    JOIN stores s ON p.store_id = s.id
    WHERE s.name = 'Tigre Géant'
      AND p.name LIKE '%Shrimp%'
      AND (ph.image_url IS NULL OR ph.image_url = '')
      AND ph.week_start = (
          SELECT MAX(week_start) FROM price_history 
          JOIN products ON price_history.product_id = products.id
          JOIN stores ON products.store_id = stores.id
          WHERE stores.name = 'Tigre Géant'
      )
""").fetchall()

print(f"Items shrimp à corriger: {len(rows)}")
for r in rows:
    print(f"  ID={r['id']} | {r['name']}")

# Mettre à jour avec les images Shopify
for i, r in enumerate(rows):
    img_url = SHRIMP_IMG_URLS[i % len(SHRIMP_IMG_URLS)]
    db.execute("UPDATE price_history SET image_url = ? WHERE id = ?", (img_url, r['id']))
    print(f"  ✅ ID={r['id']} → image mise à jour")

db.commit()
db.close()
print(f"\n✅ Shrimp items fixed!")

# Rebuild JSON
print(f"\n🏗️  Rebuild JSON...")
os.chdir(r'C:\Users\Mark France\aubaines-rapides')
import sys
sys.path.insert(0, 'scripts')
from build_site import main as build_main
build_main()
print(f"✅ JSON mis à jour!")

# Vérifier
with open(r'C:\Users\Mark France\aubaines-rapides\web\data\deals.json') as f:
    data = json.load(f)

tg_deals = [d for d in data['deals_with_kg'] if d.get('store') == 'Tigre Géant']
with_img = [d for d in tg_deals if d.get('image_url')]
print(f"\n📊 TG deals: {len(tg_deals)}, avec image: {len(with_img)}")
if len(with_img) < len(tg_deals):
    for d in tg_deals:
        if not d.get('image_url'):
            print(f"  ❌ {d['name'][:55]}")
