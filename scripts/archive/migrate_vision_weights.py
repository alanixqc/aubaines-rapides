#!/usr/bin/env python3
"""
Migration DB : ajoute colonnes image_url, package_weight_g et
met à jour les poids à partir de nos découvertes via vision.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db.schema import get_db

db = get_db()

# 1. Ajouter colonnes manquantes
print("🔧 Migration schema...")
try:
    db.execute("ALTER TABLE price_history ADD COLUMN image_url TEXT")
    print("   ✅ image_url ajouté à price_history")
except Exception as e:
    print(f"   ℹ️  image_url déjà présent ou erreur: {e}")

try:
    db.execute("ALTER TABLE products ADD COLUMN package_weight_g INTEGER")
    print("   ✅ package_weight_g ajouté à products")
except Exception as e:
    print(f"   ℹ️  package_weight_g déjà présent ou erreur: {e}")

try:
    db.execute("ALTER TABLE price_history ADD COLUMN flipp_item_id INTEGER")
    print("   ✅ flipp_item_id ajouté à price_history")
except Exception as e:
    print(f"   ℹ️  flipp_item_id déjà présent ou erreur: {e}")

db.commit()

# 2. Mettre à jour les poids de produits IGA découverts via vision
updates = {
    # (nom_produit, poids_g) - correspondance par nom partiel
    "BŒUF HACHÉ MAIGRE 8 ACRES": 400,
    "BŒUF HACHÉ MAIGRE": 400,  # fallback
    "BISON HACHÉ MAIGRE NORTHFORK": 224,
    "BACON LAFLEUR": 500,
    "BACON DOUBLE FUMÉ FUMOIRS GOSSELIN": 375,
    "POITRINES DE POULET FRAIS DÉSOSSÉES": 1500,
    "BOUCHÉES DE POITRINE DE POULET FRAIS MARCANGELO": 200,
    "HAUTS DE CUISSE DE POULET FRAIS DÉSOSSÉES": 1100,
    "VIANDE FUMÉE DE PORC FUMOIRS GOSSELIN": 500,
}

# Mise à jour des produits IGA
store = db.execute("SELECT id FROM stores WHERE name = 'IGA'").fetchone()
if store:
    store_id = store['id']
    for name_part, weight in updates.items():
        products = db.execute(
            "SELECT id, name FROM products WHERE store_id = ? AND name LIKE ?",
            (store_id, f"%{name_part}%")
        ).fetchall()
        for p in products:
            db.execute(
                "UPDATE products SET package_weight_g = ? WHERE id = ?",
                (weight, p['id'])
            )
            print(f"   ✅ {p['name'][:50]:50s} → {weight}g")

db.commit()

# 3. Vérification
print("\n📊 RÉSUMÉ DES PRODUITS IGA AVEC POIDS:")
rows = db.execute("""
    SELECT p.name, p.meat_type, p.package_weight_g, ph.price, ph.unit_price, ph.unit_type
    FROM products p
    JOIN stores s ON p.store_id = s.id
    LEFT JOIN price_history ph ON ph.product_id = p.id
    WHERE s.name = 'IGA' AND p.meat_type IS NOT NULL
    ORDER BY p.name
""").fetchall()

seen = set()
for r in rows:
    if r['name'] not in seen:
        seen.add(r['name'])
        w = f"{r['package_weight_g']}g" if r['package_weight_g'] else "au poids"
        up = f"${r['unit_price']:.2f}{r['unit_type']}" if r['unit_price'] else "-"
        print(f"  {r['name'][:55]:55s} | poids={w:>8s} | ${r['price'] or 0:<6} | unitaire={up}")

db.close()
