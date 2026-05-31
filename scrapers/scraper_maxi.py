#!/usr/bin/env python3
"""scraper_maxi.py — Scraper PC Express (Maxi/Provigo/Loblaws) avec DB
Usage: python scraper_maxi.py --store maxi --db
"""
import urllib.request, re, json, sys, os, argparse
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scripts.db_saver import save_products_to_db, save_deals_json

STORES = {
    "maxi": {"domain": "www.maxi.ca", "banner": "maxi", "name": "Maxi",
             "color": "#2563eb", "category_url": "https://www.maxi.ca/fr/alimentation/viande/c/27998"},
    "provigo": {"domain": "www.provigo.ca", "banner": "provigo", "name": "Provigo",
                "color": "#dc2626", "category_url": "https://www.provigo.ca/fr/alimentation/viande/c/27998"},
    "loblaws": {"domain": "www.loblaws.ca", "banner": "loblaw", "name": "Loblaws",
                "color": "#1d4ed8", "category_url": "https://www.loblaws.ca/fr/alimentation/viande/c/27998"},
}

def fetch_page(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "fr-CA,fr;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8')

def extract_products(html):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*type="application/json"[^>]*>({.*?})</script>', html, re.DOTALL)
    if not m: return []
    data = json.loads(m.group(1))
    try:
        comps = data['props']['pageProps']['initialData']['layout']['sections']['mainContentCollection']['components']
    except: return []
    
    seen, products = set(), []
    for c in comps:
        for tile in c.get('data', {}).get('productTiles', []):
            pid = tile.get('productId', '')
            if pid and pid not in seen:
                seen.add(pid)
                products.append(tile)
    return products

def normalize(tile, store):
    pricing = tile.get('pricing', {})
    price = 0.0
    try: price = float(pricing.get('price', '0').replace(',', '.'))
    except: pass
    
    was = None
    if pricing.get('wasPrice'):
        try: was = float(pricing['wasPrice'].replace('\xa0',' ').replace('$','').replace(',','.').strip())
        except: pass
    
    img = tile.get('productImage', [{}])[0].get('mediumUrl', '') if tile.get('productImage') else ''
    link = tile.get('link', '')
    if link and not link.startswith('http'):
        link = f"https://{store['domain']}{link}"
    
    return {
        "name": tile.get('title', ''),
        "brand": tile.get('brand', ''),
        "price": price,
        "was_price": was,
        "on_sale": was is not None and was > price,
        "image": img,
        "url": link,
        "sizing": tile.get('packageSizing', ''),
        "store": store['name'],
        "category": "Viande",
        "meat_type": None,
        "scraped_at": datetime.now().isoformat(),
    }

def scrape(store_key):
    store = STORES.get(store_key)
    if not store: return []
    print(f"🔄 {store['name']}... ", end='', flush=True)
    try:
        html = fetch_page(store['category_url'])
        tiles = extract_products(html)
        products = [normalize(t, store) for t in tiles]
        sales = sum(1 for p in products if p.get('on_sale'))
        print(f"✅ {len(products)} produits ({sales} spéciaux)")
        return products
    except Exception as e:
        print(f"❌ {e}")
        return []

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", choices=list(STORES.keys()), default="maxi")
    ap.add_argument("--db", action="store_true", help="Écrire dans la DB")
    args = ap.parse_args()
    
    products = scrape(args.store)
    
    if args.db and products:
        save_products_to_db(products, STORES[args.store]['name'])
    
    # Toujours sauvegarder le JSON pour le site
    if products:
        p = save_deals_json(products, args.store)
        print(f"   📄 JSON: {p}")
    
    # Output for pipeline
    print(f"\n---JSON_OUTPUT---")
    print(json.dumps(products, ensure_ascii=False))
