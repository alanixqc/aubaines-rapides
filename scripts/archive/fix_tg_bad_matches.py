"""Fix les mauvais matches + intègre dans le scraper."""
import json, sqlite3, os, sys

DB_PATH = r'C:\Users\Mark France\aubaines-rapides\data\aubaines.db'
SHOPIFY_PATH = r'C:\Users\Mark France\aubaines-rapides\cache\tigregeant\shopify_products.json'

# ─── CORRECTIONS MANUELLES ───
# Format: {"nom_dans_DB": "shopify_title_exact"}
MANUAL_CORRECTIONS = {
    "Boston Market Turkey Breast Cutlettes, 369 g": "Escalopes de poitrine de dinde Boston Market, 369 g",
    "High Liner English Style Fillets, 500 g": "High Liner Filets en Pâte à l'Anglaise, 500 g",
    "La Cage Regular Chicken Nuggets, 550 g": "La Cage Pépites de Poulet Régulier, 550 g",
}

# Charger les produits Shopify
with open(SHOPIFY_PATH) as f:
    shopify_data = json.load(f)

def find_img_for_title(target_title):
    """Trouve l'image Shopify pour un titre exact."""
    for p in shopify_data['products']:
        title = p.get('title', '')
        if title.lower().strip() == target_title.lower().strip():
            for v in p.get('variants', []):
                img = v.get('featured_image', {}) or {}
                img_url = img.get('src', '') if img else ''
                if img_url:
                    return img_url
    return None

# Mettre à jour la DB
db = sqlite3.connect(DB_PATH)
db.row_factory = sqlite3.Row

for db_name, shopify_title in MANUAL_CORRECTIONS.items():
    rows = db.execute("""
        SELECT ph.id, p.name FROM price_history ph
        JOIN products p ON ph.product_id = p.id
        JOIN stores s ON p.store_id = s.id
        WHERE s.name = 'Tigre Géant'
          AND p.name = ?
    """, (db_name,)).fetchall()
    
    if not rows:
        print(f"❌ {db_name[:50]} → pas trouvé dans la DB")
        continue
    
    img_url = find_img_for_title(shopify_title)
    if not img_url:
        print(f"❌ {db_name[:50]} → pas d'image pour '{shopify_title}'")
        continue
    
    for r in rows:
        db.execute("UPDATE price_history SET image_url = ? WHERE id = ?", (img_url, r['id']))
        print(f"✅ {db_name[:50]} → image corrigée ({shopify_title[:40]})")

db.commit()
db.close()

# Rebuild
print(f"\n🏗️  Rebuild...")
os.chdir(r'C:\Users\Mark France\aubaines-rapides')
sys.path.insert(0, 'scripts')
from build_site import main as build_main
build_main()
print(f"✅ Terminé!")

# Vérifier
with open(r'C:\Users\Mark France\aubaines-rapides\web\data\deals.json') as f:
    data = json.load(f)

# Les noms sont en français dans le JSON, on cherche par la traduction
checks = ["poitrine de dinde", "style anglais", "nuggets de poulet"]
for d in data['deals_with_kg']:
    for check in checks:
        if check in d['name'].lower() and d.get('store') == 'Tigre Géant':
            status = "✅ IMG" if d.get('image_url') else "❌ PAS D'IMAGE"
            print(f"  VÉRIF: {d['name'][:50]} → {status}")
            break
