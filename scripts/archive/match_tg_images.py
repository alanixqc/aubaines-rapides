"""Match items TG → images Shopify + mise à jour du scraper.
Version finale: fuzzy matching + validation par prix + fallback."""
import json
import re
import os
import sys
from difflib import SequenceMatcher
from collections import defaultdict

PROJECT_ROOT = r'C:\Users\Mark France\aubaines-rapides'
SHOPIFY_PATH = os.path.join(PROJECT_ROOT, 'cache', 'tigregeant', 'shopify_products.json')

# ─── Normalisation ───
def normalize(name):
    name = name.lower()
    accent_map = str.maketrans('éèêëàâäôöòûüùîïç', 'eeeeaaaooouuuiic')
    name = name.translate(accent_map)
    name = re.sub(r'[^a-z0-9\s]', ' ', name)
    return re.sub(r'\s+', ' ', name).strip()

def keywords(name):
    words = normalize(name).split()
    stopwords = {'le','la','les','de','du','des','un','une','et','au','aux','en',
                 'sur','par','pour','avec','sans','dans','est','ou','pas','plus',
                 'format','chaque','pack','paquet','sac','boite','boîte','sachet',
                 'ml','g','kg','lb','oz','x','environ','emb','bte','lanières',
                 'laniere','régulier','regulier','original','originale','fumé',
                 'fume','frais','entier','surgelé','surgele','congelé','congele',
                 'désossé','desosse','sans',' peau','cuit','cru'}
    return [w for w in words if len(w) > 2 and w not in stopwords]

def name_similarity(a, b):
    a_norm, b_norm = normalize(a), normalize(b)
    if a_norm == b_norm:
        return 1.0
    seq = SequenceMatcher(None, a_norm, b_norm).ratio()
    akw, bkw = set(keywords(a)), set(keywords(b))
    if not akw or not bkw:
        return seq * 0.5
    jaccard = len(akw & bkw) / len(akw | bkw)
    return 0.5 * seq + 0.5 * jaccard

# ─── Charger les données Shopify ───
with open(SHOPIFY_PATH) as f:
    shopify_data = json.load(f)

products = shopify_data.get('products', [])

# Indexer les produits Shopify par nom + prix pour recherche rapide
# Struct: dict de nom_normalisé → liste de {title, price, img_url}
shopify_index = defaultdict(list)
for p in products:
    title = p.get('title', '')
    for v in p.get('variants', []):
        price = float(v.get('price', 0))
        img = v.get('featured_image', {})
        img_url = img.get('src', '') if img else ''
        if img_url:
            shopify_index[normalize(title)].append({
                'title': title,
                'price': price,
                'img_url': img_url
            })

def find_best_match(deal_name, deal_price):
    """Trouve le meilleur match Shopify pour un deal TG."""
    best = None
    best_score = 0
    
    # Chercher dans tous les produits
    for p in products:
        title = p.get('title', '')
        for v in p.get('variants', []):
            price = float(v.get('price', 0))
            img = v.get('featured_image', {})
            img_url = img.get('src', '') if img else ''
            if not img_url:
                continue
            
            score = name_similarity(deal_name, title)
            
            # Bonus/penalty sur le prix
            price_diff = abs(price - deal_price)
            if price_diff < 0.5:
                score += 0.15
            elif price_diff > 3.0:
                score -= 0.2
            elif price_diff > 5.0:
                score -= 0.5
            
            if score > best_score:
                best_score = score
                best = {
                    'title': title,
                    'price': price,
                    'img_url': img_url,
                    'score': round(score, 3)
                }
    
    # Seuil: 0.4 (minimal), avec validation de prix
    if best_score >= 0.4:
        return best
    return None

# ─── TEST avec les deals TG ───
DEALS_PATH = os.path.join(PROJECT_ROOT, 'web', 'data', 'deals.json')
with open(DEALS_PATH) as f:
    deals_data = json.load(f)

tg_deals = [d for d in deals_data.get('deals_with_kg', []) 
            if d.get('store') == 'Tigre Géant' and not d.get('image_url')]

print(f"Recherche d'images pour {len(tg_deals)} items TG sans image...")
print()

results = []
for d in tg_deals:
    match = find_best_match(d['name'], d['price'])
    if match:
        results.append((d, match))
        icon = '✅' if match['score'] > 0.6 else '⚠️'
        print(f"{icon} [{match['score']:.2f}] {d['name'][:55]}")
        print(f"   → {match['title'][:55]}")
        print(f"   💰 ${d['price']:.2f} → ${match['price']:.2f} | 📷 {match['img_url'][:60]}")
    else:
        results.append((d, None))
        print(f"❌ [NOPE] {d['name'][:55]} (${d['price']:.2f})")

good = sum(1 for _, m in results if m and m['score'] > 0.6)
ok = sum(1 for _, m in results if m and 0.4 <= m['score'] <= 0.6)
nope = sum(1 for _, m in results if m is None)

print(f"\n{'='*60}")
print(f"RÉSULTATS: {good} bons ✅, {ok} moyens ⚠️, {nope} sans match ❌")
print(f"{'='*60}")

# Afficher les cas problématiques
if ok > 0:
    print(f"\n⚠️ MATCHS DOUTEUX (score 0.4-0.6) — à vérifier:")
    for d, m in results:
        if m and 0.4 <= m['score'] <= 0.6:
            print(f"  {d['name'][:50]} (${d['price']:.2f})")
            print(f"  → {m['title'][:50]} (${m['price']:.2f}) score={m['score']:.2f}")
            print()

if nope > 0:
    print(f"\n❌ SANS MATCH:")
    for d, m in results:
        if m is None:
            print(f"  - {d['name'][:50]} (${d['price']:.2f})")
