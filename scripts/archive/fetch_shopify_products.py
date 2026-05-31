"""Extrait les produits Tigre Géant via l'API Shopify + images."""
import json
import urllib.request
import urllib.parse
import re
import os
import sys
from difflib import SequenceMatcher

PROJECT_ROOT = r'C:\Users\Mark France\aubaines-rapides'

# 1. Récupérer TOUS les produits de la collection flyers-and-deals via l'API paginée
def fetch_all_products():
    all_products = []
    page = 1
    while True:
        url = f"https://www.gianttiger.com/fr/collections/flyers-and-deals/products.json?limit=250&page={page}"
        print(f"  Page {page}...", end=" ", flush=True)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                products = data.get("products", [])
                if not products:
                    break
                all_products.extend(products)
                print(f"{len(products)} produits")
                page += 1
        except Exception as e:
            print(f"Erreur: {e}")
            break
    return all_products

print("Récupération des produits Tigre Géant...")
products = fetch_all_products()
print(f"\nTotal: {len(products)} produits")

# 2. Filtrer par catégorie alimentaire/épicerie
# Les tags contiennent des infos de catégorie
GROCERY_TAGS = ['grocery', 'épicerie', 'food', 'alimentation', 'meat', 'viande', 
                'pantry', 'garde-manger', 'produce', 'fruits', 'légumes',
                'dairy', 'laitier', 'beverage', 'boisson', 'snack',
                'frozen', 'surgelé', 'bread', 'pain', 'condiment',
                'breakfast', 'déjeuner', 'meals', 'repas']

# Filtrer par tags
grocery_products = []
for p in products:
    tags_lower = [t.lower() for t in p.get("tags", [])]
    if any(grocery_tag in ' '.join(tags_lower) for grocery_tag in GROCERY_TAGS):
        grocery_products.append(p)

print(f"Produits épicerie (tags): {len(grocery_products)}")

# 3. Sauvegarder les données complètes
out_path = os.path.join(PROJECT_ROOT, 'cache', 'tigregeant', 'shopify_products.json')
with open(out_path, 'w') as f:
    json.dump({
        "total": len(products),
        "grocery_count": len(grocery_products),
        "products": products
    }, f, indent=2, ensure_ascii=False)
print(f"Données sauvegardées: {out_path}")

# 4. Afficher les 30 premiers produits épicerie
print(f"\n{'='*80}")
print(f"ÉCHANTILLON PRODUITS ÉPICERIE (30 premiers)")
print(f"{'='*80}")
for p in grocery_products[:30]:
    title = p["title"]
    variants = p.get("variants", [])
    if variants:
        price = float(variants[0]["price"])
        img = variants[0].get("featured_image", {})
        img_url = img.get("src", "") if img else ""
        
        # Trouver les tags épicerie
        relevant_tags = [t for t in p.get("tags", []) if any(k in t.lower() for k in ['grocery','épicerie','food','alimentation','meat','viande'])]
        
        print(f"  ${price:.2f} | {title[:60]}")
        if img_url:
            print(f"       📷 {img_url[:80]}")
        if relevant_tags:
            print(f"       🏷️ {', '.join(relevant_tags[:3])}")

print(f"\n✅ {len(grocery_products)} produits épicerie avec images Shopify disponibles")
print(f"   Ces images peuvent remplacer les {23} items TG sans image actuellement")
