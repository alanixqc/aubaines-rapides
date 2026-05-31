#!/usr/bin/env python3
"""
scraper_maxi.py — Scraper gratuit pour Maxi, Provigo, Loblaws (PC Express)
Extrait les données des produits depuis le __NEXT_DATA__ du HTML.
Pas besoin d'API payante — un simple fetch HTTP.

Usage:
    python scraper_maxi.py                  # Maxi (défaut)
    python scraper_maxi.py --store provigo  # Provigo
    python scraper_maxi.py --store loblaws  # Loblaws
    python scraper_maxi.py --all            # Tous les stores
"""

import urllib.request
import re
import json
import sys
import os
from datetime import datetime

# Configuration des stores PC Express
STORES = {
    "maxi": {
        "domain": "www.maxi.ca",
        "banner": "maxi",
        "name": "Maxi",
        "color": "#2563eb",
        "category_url": "https://www.maxi.ca/fr/alimentation/viande/c/27998",
    },
    "provigo": {
        "domain": "www.provigo.ca",
        "banner": "provigo",
        "name": "Provigo",
        "color": "#dc2626",
        "category_url": "https://www.provigo.ca/fr/alimentation/viande/c/27998",
    },
    "loblaws": {
        "domain": "www.loblaws.ca",
        "banner": "loblaw",
        "name": "Loblaws",
        "color": "#1d4ed8",
        "category_url": "https://www.loblaws.ca/fr/alimentation/viande/c/27998",
    },
}

def fetch_page(url):
    """Fetch a page with proper headers."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-CA,fr;q=0.9,en;q=0.8",
        }
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode('utf-8')

def extract_products_from_html(html):
    """Extract product tiles from server-rendered HTML."""
    match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*type="application/json"[^>]*>({.*?})</script>',
        html, re.DOTALL
    )
    if not match:
        return []
    
    data = json.loads(match.group(1))
    
    try:
        comps = data['props']['pageProps']['initialData']['layout']['sections']['mainContentCollection']['components']
    except (KeyError, TypeError):
        return []
    
    all_products = []
    seen_ids = set()
    for comp in comps:
        tiles = comp.get('data', {}).get('productTiles', [])
        for tile in tiles:
            pid = tile.get('productId', '')
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                all_products.append(tile)
    
    return all_products

def normalize_product(tile, store_info):
    """Convert a PC Express product tile to our standard format."""
    pricing = tile.get('pricing', {})
    price_str = pricing.get('price', '0')
    was_price_str = pricing.get('wasPrice')
    
    # Clean price strings (remove non-numeric chars)
    try:
        price = float(price_str.replace(',', '.'))
    except (ValueError, AttributeError):
        price = 0.0
    
    # Parse wasPrice (format like "15,50 $")
    was_price = None
    if was_price_str:
        try:
            clean = was_price_str.replace('\xa0', ' ').replace('$', '').replace(',', '.').strip()
            was_price = float(clean)
        except (ValueError, AttributeError):
            was_price = None
    
    # Determine if on sale
    on_sale = price > 0 and was_price is not None and was_price > price
    
    # Image URL (use medium size)
    img_url = ''
    if tile.get('productImage'):
        img_url = tile['productImage'][0].get('mediumUrl', '')
    
    # Full product URL
    link = tile.get('link', '')
    if link and not link.startswith('http'):
        link = f"https://{store_info['domain']}{link}"
    
    # Brand
    brand = tile.get('brand', '')
    
    # Product name
    name = tile.get('title', '')
    
    # Package size
    sizing = tile.get('packageSizing', '')
    
    return {
        "store": store_info['name'],
        "store_banner": store_info['banner'],
        "store_color": store_info['color'],
        "product_id": tile.get('productId', ''),
        "name": name,
        "brand": brand,
        "price": price,
        "was_price": was_price,
        "on_sale": on_sale,
        "savings": round(was_price - price, 2) if on_sale else 0,
        "image": img_url,
        "url": link,
        "sizing": sizing,
        "category": "Viande",
        "scraped_at": datetime.now().isoformat(),
    }

def scrape_store(store_key):
    """Scrape one PC Express store for meat deals."""
    store = STORES.get(store_key)
    if not store:
        print(f"❌ Store inconnu: {store_key}")
        return []
    
    print(f"🔄 Scraping {store['name']}... ", end='', flush=True)
    
    try:
        html = fetch_page(store['category_url'])
        tiles = extract_products_from_html(html)
        
        if not tiles:
            print(f"❌ 0 produits")
            return []
        
        products = [normalize_product(t, store) for t in tiles]
        
        # Count stats
        on_sale = sum(1 for p in products if p['on_sale'])
        print(f"✅ {len(products)} produits, {on_sale} en spécial")
        
        return products
    
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return []

def scrape_all():
    """Scrape all PC Express stores."""
    all_products = []
    for store_key in STORES:
        products = scrape_store(store_key)
        all_products.extend(products)
    return all_products

def print_summary(products):
    """Print a summary of scraped products."""
    if not products:
        print("\n📭 Aucun produit trouvé")
        return
    
    stores = set(p['store'] for p in products)
    on_sale = sum(1 for p in products if p['on_sale'])
    
    print(f"\n{'='*50}")
    print(f"📊 RÉSUMÉ ({len(products)} produits, {len(stores)} magasins)")
    print(f"{'='*50}")
    
    for store_name in sorted(stores):
        store_products = [p for p in products if p['store'] == store_name]
        store_sale = sum(1 for p in store_products if p['on_sale'])
        print(f"\n🏪 {store_name}: {len(store_products)} produits ({store_sale} spéciaux)")
        
        for p in store_products[:5]:  # Show first 5
            sale_tag = "🔴 SPÉCIAL! " if p['on_sale'] else ""
            was = f" (était {p['was_price']}$)" if p['on_sale'] else ""
            print(f"  {sale_tag}{p['brand']} {p['name']} — {p['price']}${was}")
            if p['image']:
                print(f"     🖼️  {p['image'][:60]}...")
    
    print(f"\n💰 Total en spécial: {on_sale}/{len(products)}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Scraper PC Express (Maxi, Provigo, Loblaws)")
    parser.add_argument("--store", choices=list(STORES.keys()) + ["all"], default="maxi",
                        help="Store à scraper (défaut: maxi)")
    parser.add_argument("--output", help="Fichier de sortie JSON")
    parser.add_argument("--summary", action="store_true", default=True,
                        help="Afficher le résumé")
    
    args = parser.parse_args()
    
    if args.store == "all":
        products = scrape_all()
    else:
        products = scrape_store(args.store)
    
    if args.summary:
        print_summary(products)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Sauvegardé: {args.output} ({len(products)} produits)")
    
    # Always output to stdout for pipeline consumption
    print(f"\n---JSON_OUTPUT---")
    print(json.dumps(products, ensure_ascii=False))
