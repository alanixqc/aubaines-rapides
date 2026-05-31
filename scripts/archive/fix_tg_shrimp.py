"""Fix les 2 shrimp items TG restants + vérifie les matchs."""
import json, sqlite3, os

DB_PATH = r'C:\Users\Mark France\aubaines-rapides\data\aubaines.db'

db = sqlite3.connect(DB_PATH)
db.row_factory = sqlite3.Row

# Trouver les items TG sans image
rows = db.execute("""
    SELECT ph.id, p.name, ph.price
    FROM price_history ph
    JOIN products p ON ph.product_id = p.id
    JOIN stores s ON p.store_id = s.id
    WHERE s.name = 'Tigre Géant'
      AND (ph.image_url IS NULL OR ph.image_url = '')
      AND ph.week_start = (
          SELECT MAX(week_start) FROM price_history 
          JOIN products ON price_history.product_id = products.id
          JOIN stores ON products.store_id = stores.id
          WHERE stores.name = 'Tigre Géant'
      )
""").fetchall()

print(f"Items TG encore sans image: {len(rows)}")
for r in rows:
    print(f"  ID={r['id']} | {r['name']} (${r['price']:.2f})")

# Chercher les produits shrimp dans Shopify
with open(r'C:\Users\Mark France\aubaines-rapides\cache\tigregeant\shopify_products.json') as f:
    shopify = json.load(f)

print(f"\nProduits Aqua Star / crevettes dans Shopify:")
for p in shopify['products']:
    title = p['title']
    if 'aqua' in title.lower() or 'crevette' in title.lower() or 'shrimp' in title.lower():
        for v in p['variants']:
            price = float(v['price'])
            img = v.get('featured_image', {}) or {}
            img_url = img.get('src', '') if img else ''
            print(f"  ${price:.2f} | {title[:70]}")
            if img_url:
                print(f"       📷 {img_url[:70]}")

# Vérifier si on peut trouver par prix exact
print(f"\nRecherche par prix $6.98 dans Shopify:")
for p in shopify['products']:
    for v in p['variants']:
        if float(v['price']) == 6.98:
            img = v.get('featured_image', {}) or {}
            img_url = img.get('src', '') if img else ''
            if img_url and ('aqua' in p['title'].lower() or 'crevette' in p['title'].lower()):
                print(f"  {p['title'][:60]} (${v['price']})")
                print(f"       📷 {img_url[:70]}")

db.close()
