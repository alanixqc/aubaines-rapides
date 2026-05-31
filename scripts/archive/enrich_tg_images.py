#!/usr/bin/env python3
"""
Enrichit les items Tigre Géant avec des images produits via l'API Shopify.
One-time + réutilisable à chaque run du scraper.
"""
import json, re, os, sys, sqlite3
from difflib import SequenceMatcher
from collections import defaultdict
from datetime import datetime

PROJECT_ROOT = r'C:\Users\Mark France\aubaines-rapides'
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'aubaines.db')
SHOPIFY_CACHE = os.path.join(PROJECT_ROOT, 'cache', 'tigregeant', 'shopify_products.json')
CACHE_DIR = os.path.join(PROJECT_ROOT, 'cache', 'tigregeant')

os.makedirs(CACHE_DIR, exist_ok=True)

# ─── Normalisation ───
ACCENT_MAP = str.maketrans('éèêëàâäôöòûüùîïç', 'eeeeaaaooouuuiic')

def normalize(name):
    name = name.lower().translate(ACCENT_MAP)
    name = re.sub(r'[^a-z0-9\s]', ' ', name)
    return re.sub(r'\s+', ' ', name).strip()

STOPWORDS = {'le','la','les','de','du','des','un','une','et','au','aux','en',
             'sur','par','pour','avec','sans','dans','est','ou','pas','plus',
             'format','chaque','pack','paquet','sac','boite','boîte','sachet',
             'ml','g','kg','lb','oz','x','environ','emb','bte'}

def keywords(name):
    words = normalize(name).split()
    return [w for w in words if len(w) > 2 and w not in STOPWORDS]

def name_similarity(a, b):
    a_n, b_n = normalize(a), normalize(b)
    if a_n == b_n:
        return 1.0
    seq = SequenceMatcher(None, a_n, b_n).ratio()
    a_kw, b_kw = set(keywords(a)), set(keywords(b))
    if not a_kw or not b_kw:
        return seq * 0.5
    jaccard = len(a_kw & b_kw) / len(a_kw | b_kw)
    return 0.5 * seq + 0.5 * jaccard

# ─── Corrections manuelles pour les cas connus ───
MANUAL_MATCHES = {
    # "nom dans le deal" → "nom exact dans Shopify (ou assez proche)"
    "Étiquette Or Fumoir bacon - 375g": "Bacon fumée Gold Label - 375 g",
    "Étiquette Or fumoir bacon - 375g": "Bacon fumée Gold Label - 375 g",
    "Étiquette Or original lanières de saucisses, 300 g": "Lanières de saucisse Gold Label Original, 300 g",
    "Tranche de jambon désossé Étiquette Or Fumoir": "Tranche de jambon désossé Smokehouse - 375 g",
}

def load_shopify_products(force_refetch=False):
    """Charge les produits Shopify, avec cache."""
    cache_path = SHOPIFY_CACHE
    
    if os.path.exists(cache_path) and not force_refetch:
        with open(cache_path) as f:
            data = json.load(f)
            print(f"  📦 {len(data.get('products', []))} produits chargés depuis le cache")
            return data['products']
    
    # Fetch from API
    print("  🌐 Téléchargement des produits Shopify...")
    all_products = []
    page = 1
    while True:
        url = f"https://www.gianttiger.com/fr/collections/flyers-and-deals/products.json?limit=250&page={page}"
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                products = data.get("products", [])
                if not products:
                    break
                all_products.extend(products)
                page += 1
        except Exception as e:
            print(f"    ⚠️ Erreur page {page}: {e}")
            break
    
    with open(cache_path, 'w') as f:
        json.dump({"total": len(all_products), "products": all_products}, f, 
                  indent=2, ensure_ascii=False)
    print(f"  ✅ {len(all_products)} produits Shopify sauvegardés")
    return all_products


def find_best_match(deal_name, deal_price, shopify_products):
    """Trouve la meilleure image Shopify pour un deal TG."""
    # 1. Vérifier les matchs manuels
    deal_key = deal_name.strip()
    manual_target = MANUAL_MATCHES.get(deal_key)
    if not manual_target:
        # Essayer sans accents
        deal_norm = normalize(deal_key)
        for k, v in MANUAL_MATCHES.items():
            if normalize(k) == deal_norm:
                manual_target = v
                break
    
    if manual_target:
        for p in shopify_products:
            title = p.get('title', '')
            if name_similarity(manual_target, title) > 0.7:
                for v in p.get('variants', []):
                    img = v.get('featured_image', {})
                    img_url = img.get('src', '') if img else ''
                    if img_url:
                        print(f"      🔗 Match manuel: {title[:50]}")
                        return img_url
    
    # 2. Fuzzy matching
    best = None
    best_score = 0
    
    for p in shopify_products:
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
                best = (img_url, title, price, score)
    
    if best and best[3] >= 0.45:
        print(f"      🔗 Fuzzy: {best[1][:40]} (score={best[3]:.2f}, ${best[2]:.2f})")
        return best[0]
    
    return None


def update_deal_images(shopify_products):
    """Parcourt les deals TG sans image et met à jour la DB."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    
    # Trouver les items Tigre Géant SANS image
    rows = db.execute("""
        SELECT ph.id, p.name, ph.price, ph.image_url
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
    
    print(f"\n🔍 {len(rows)} items TG sans image dans la DB")
    
    updated = 0
    for row in rows:
        deal_name = row['name']
        deal_price = row['price']
        
        print(f"\n  📄 {deal_name[:55]} (${deal_price:.2f})")
        img_url = find_best_match(deal_name, deal_price, shopify_products)
        
        if img_url:
            db.execute("UPDATE price_history SET image_url = ? WHERE id = ?",
                      (img_url, row['id']))
            updated += 1
            print(f"      ✅ Image trouvée")
        else:
            print(f"      ❌ Aucun match")
    
    db.commit()
    db.close()
    
    print(f"\n{'='*50}")
    print(f"✅ {updated}/{len(rows)} images mises à jour dans la DB")
    return updated


def update_json_from_db():
    """Rebuilde le JSON du site après mise à jour de la DB."""
    print("\n🏗️  Rebuild du JSON...")
    sys.path.insert(0, os.path.join(PROJECT_ROOT, 'scripts'))
    from build_site import main as build_main
    try:
        build_main()
        print("✅ JSON mis à jour")
    except Exception as e:
        print(f"⚠️  Erreur rebuild: {e}")


if __name__ == '__main__':
    print(f"{'='*60}")
    print(f"🖼️  ENRICHISSEMENT IMAGES TIGRE GÉANT")
    print(f"{'='*60}")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    shopify_products = load_shopify_products()
    update_deal_images(shopify_products)
    update_json_from_db()
    
    print(f"\n✅ Terminé!")
