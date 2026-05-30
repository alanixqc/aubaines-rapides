"""Match les items TG sans image aux produits Shopify pour récupérer les images."""
import json
import re
import os
from difflib import SequenceMatcher
from collections import defaultdict

PROJECT_ROOT = r'C:\Users\Mark France\aubaines-rapides'
DEALS_PATH = os.path.join(PROJECT_ROOT, 'web', 'data', 'deals.json')
SHOPIFY_PATH = os.path.join(PROJECT_ROOT, 'cache', 'tigregeant', 'shopify_products.json')

# Charger les deals
with open(DEALS_PATH) as f:
    deals_data = json.load(f)

deals = deals_data.get('deals_with_kg', [])
tg_deals = [d for d in deals if d.get('store') == 'Tigre Géant' and not d.get('image_url')]
print(f"Items TG sans image: {len(tg_deals)}")

# Charger les produits Shopify
with open(SHOPIFY_PATH) as f:
    shopify_data = json.load(f)

shopify_products = shopify_data.get('products', [])
print(f"Produits Shopify: {len(shopify_products)}")

def normalize_name(name):
    """Normalise un nom pour comparaison."""
    name = name.lower()
    # Enlever les accents
    name = name.replace('é','e').replace('è','e').replace('ê','e').replace('ë','e')
    name = name.replace('à','a').replace('â','a').replace('ä','a')
    name = name.replace('ô','o').replace('ö','o').replace('ò','o')
    name = name.replace('û','u').replace('ü','u')
    name = name.replace('î','i').replace('ï','i')
    name = name.replace('ç','c')
    # Enlever caractères non-alphanumériques
    name = re.sub(r'[^a-z0-9\s]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def extract_keywords(name):
    """Extrait les mots-clés importants d'un nom."""
    name = normalize_name(name)
    words = name.split()
    # Enlever les mots trop courts et génériques
    stopwords = {'le','la','les','de','du','des','un','une','et','au','aux','en','sur',
                 'par','pour','avec','sans','dans','a','est','ou','pas','plus','tres',
                 'chez','chez','cest','c\'est','format','chaque','pack','paquet','sac',
                 'boite','boîte','bte','sachet','emb','ml','g','kg','lb','oz'}
    return [w for w in words if len(w) > 2 and w not in stopwords]

def name_similarity(deal_name, shopify_name):
    """Calcule la similarité entre deux noms de produits."""
    deal_norm = normalize_name(deal_name)
    shop_norm = normalize_name(shopify_name)
    
    # Exact match
    if deal_norm == shop_norm:
        return 1.0
    
    # Sequence matcher
    seq_sim = SequenceMatcher(None, deal_norm, shop_norm).ratio()
    
    # Vérifier les mots-clés
    deal_kw = set(extract_keywords(deal_name))
    shop_kw = set(extract_keywords(shopify_name))
    
    if not deal_kw or not shop_kw:
        return 0.0
    
    overlap = len(deal_kw & shop_kw)
    jaccard = overlap / len(deal_kw | shop_kw) if deal_kw | shop_kw else 0
    
    # Score composite: 60% séquence, 40% mots-clés
    return 0.6 * seq_sim + 0.4 * jaccard

# Pour chaque TG deal, trouver le meilleur match
print(f"\n{'='*80}")
print(f"RECHERCHE DE MATCHS")
print(f"{'='*80}")

matches = []
unmatched = []

for deal in tg_deals:
    deal_name = deal.get('name', '')
    deal_price = deal.get('price', 0)
    
    best_match = None
    best_score = 0
    
    for p in shopify_products:
        title = p.get('title', '')
        variants = p.get('variants', [])
        
        if not variants:
            continue
        
        price = float(variants[0].get('price', 0))
        img = variants[0].get('featured_image', {})
        img_url = img.get('src', '') if img else ''
        
        if not img_url:
            continue
        
        score = name_similarity(deal_name, title)
        
        # Bonus si le prix est proche (±$2)
        if abs(price - deal_price) < 2.0:
            score += 0.1
        # Malus si le prix est trop différent (±$5+)
        elif abs(price - deal_price) > 5.0:
            score *= 0.5
        
        if score > best_score:
            best_score = score
            best_match = {
                'shopify_title': title,
                'shopify_price': price,
                'image_url': img_url,
            }
    
    match_info = {
        'deal_name': deal_name,
        'deal_price': deal_price,
        'deal_id': deal.get('id'),
        'best_score': round(best_score, 3),
        'best_match': best_match
    }
    
    if best_score > 0.35 and best_match:
        matches.append(match_info)
        print(f"\n✅ [{best_score:.2f}] {deal_name[:50]}")
        print(f"   → {best_match['shopify_title'][:50]}")
        print(f"   💰 ${deal_price:.2f} → ${best_match['shopify_price']:.2f}")
        print(f"   📷 {best_match['image_url'][:80]}")
    else:
        unmatched.append(match_info)
        print(f"\n❌ [{best_score:.2f}] {deal_name[:50]}")

print(f"\n{'='*80}")
print(f"RÉSULTATS")
print(f"{'='*80}")
print(f"Matchs réussis: {len(matches)}/{len(tg_deals)}")
print(f"Sans match: {len(unmatched)}")

if unmatched:
    print(f"\nItems sans match:")
    for u in unmatched:
        print(f"  - {u['deal_name']} (${u['deal_price']:.2f})")
