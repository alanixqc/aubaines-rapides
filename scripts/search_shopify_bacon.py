"""Cherche des produits bacon dans les données Shopify."""
import json, re

with open(r'C:\Users\Mark France\aubaines-rapides\cache\tigregeant\shopify_products.json') as f:
    data = json.load(f)

# Chercher bacon
for p in data['products']:
    title = p['title']
    if 'bacon' in title.lower():
        variants = p.get('variants', [])
        for v in variants:
            price = float(v.get('price', 0))
            img = v.get('featured_image', {})
            img_url = img.get('src', '') if img else ''
            print(f"  ${price:.2f} | {title[:80]}")
            if img_url:
                print(f"       📷 {img_url[:80]}")

print("\n--- Recherche bacon dans tags ---")
for p in data['products']:
    tags = ' '.join(t.lower() for t in p.get('tags', []))
    if 'bacon' in tags and 'bacon' not in p['title'].lower():
        variants = p.get('variants', [])
        for v in variants:
            price = float(v.get('price', 0))
            print(f"  ${price:.2f} | {p['title'][:80]}")

print("\n--- Recherche: Gold Label / Étiquette Or ---")
for p in data['products']:
    title = p['title'].lower()
    if 'gold label' in title or 'étiquette or' in title:
        variants = p.get('variants', [])
        for v in variants:
            price = float(v.get('price', 0))
            img = v.get('featured_image', {})
            img_url = img.get('src', '') if img else ''
            print(f"  ${price:.2f} | {p['title'][:80]}")
            if img_url:
                print(f"       📷 {img_url[:80]}")

print("\n--- Recherche: jambon désossé Smokehouse ---")
for p in data['products']:
    title = p['title'].lower()
    if 'smokehouse' in title and ('jambon' in title or 'ham' in title):
        variants = p.get('variants', [])
        for v in variants:
            price = float(v.get('price', 0))
            img = v.get('featured_image', {})
            img_url = img.get('src', '') if img else ''
            print(f"  ${price:.2f} | {p['title'][:80]}")
            if img_url:
                print(f"       📷 {img_url[:80]}")
