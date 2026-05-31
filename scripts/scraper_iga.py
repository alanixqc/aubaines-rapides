#!/usr/bin/env python3
"""
scraper_iga.py — Scraper IGA via l'API Apify Voilà.ca
Coût: ~0,25-1,00$/run via les crédits gratuits Apify
"""
import json, urllib.request, time, os, sys
from datetime import datetime

APIFY_KEY = os.environ.get("APIFY_API_KEY", "")
# Fallback: lire depuis .env
if not APIFY_KEY:
    try:
        with open(os.path.join(os.path.dirname(__file__), "..", ".env")) as f:
            for line in f:
                if line.strip().startswith("APIFY_API_KEY="):
                    APIFY_KEY = line.strip().split("=", 1)[1].strip()
                    break
    except:
        pass

STORE_INFO = {
    "name": "IGA",
    "banner": "iga",
    "color": "#009640",
}

def api_get(path, key=APIFY_KEY):
    req = urllib.request.Request(
        f"https://api.apify.com/v2{path}",
        headers={"Authorization": f"Bearer {key}"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def run_scraper(max_items=200, key=APIFY_KEY):
    """Run Voilà scraper in browse mode (no keywords, gets all categories)."""
    payload = {
        "keywords": "",
        "location": "J7Z 1J6",
        "maxItems": max_items,
        "scrapeProductDetails": False,
        "proxyConfiguration": {
            "useApifyProxy": True,
            "apifyProxyGroups": ["RESIDENTIAL"]
        }
    }
    
    req = urllib.request.Request(
        "https://api.apify.com/v2/acts/ocrad~voila-product-scraper/runs",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        run = json.loads(r.read())
    
    run_id = run["data"]["id"]
    print(f"  Run ID: {run_id}")
    
    # Wait for completion
    for i in range(20):
        time.sleep(10)
        r = api_get(f"/acts/ocrad~voila-product-scraper/runs/{run_id}")
        status = r["data"]["status"]
        cost = r["data"].get("usageTotalUsd", 0)
        print(f"    [{i+1}] {status} (${cost:.4f})")
        if status in ("SUCCEEDED", "FAILED", "TIMEOUT"):
            break
    
    if status != "SUCCEEDED":
        print(f"  ❌ Run failed: {status}")
        return []
    
    items = api_get(f"/datasets/{r['data']['defaultDatasetId']}/items")
    cost = r["data"].get("usageTotalUsd", 0)
    print(f"  ✅ {len(items)} items, coût: ${cost:.4f}")
    return items

MEAT_KEYWORDS = [
    "beef", "pork", "chicken", "turkey", "boeuf", "porc", "poulet", "dinde",
    "steak", "ground beef", "boeuf haché", "bœuf haché", "haché", "burger",
    "sausage", "saucisse", "bacon", "rib", "côte", "lanière", "poitrine",
    "breast", "wing", "aile", "cuisse", "filet", "roast", "rôti", "bœuf",
    "veau", "lamb", "agneau", "ham", "jambon", "viande", "meat", "wagyu",
    "smokies", "chorizo", "sirloin", "ground", "flank", "brisket",
]

# False positives to exclude
EXCLUDE_KEYWORDS = [
    "drumstick",  # ice cream cones
    "bouillon", "broth", "soup",  # not meat
    "dog", "cat", "pet", "animal",  # pet food
    "vegetarian", "vegan", "veggie", "plant-based", "végé", "végétarien",
    "bun", "bread", "pain",  # hamburger buns, not meat
    "tortilla", "pasta filled", "ravioli", "tortellini",  # filled pasta
]

def is_meat_product(item):
    """Check if a product name is meat-related."""
    tags = item.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]
    name = (item.get("name", "") + " " + " ".join(tags)).lower()
    # Must match a meat keyword
    matched = any(kw in name for kw in MEAT_KEYWORDS)
    # Must NOT match exclusion
    excluded = any(kw in name for kw in EXCLUDE_KEYWORDS)
    return matched and not excluded

def normalize_product(item):
    """Convert Voilà item to our standard format."""
    price_str = item.get("price", "$0").replace("$", "").replace(",", "")
    try:
        price = float(price_str)
    except:
        price = 0.0
    
    return {
        "store": STORE_INFO["name"],
        "store_banner": STORE_INFO["banner"],
        "store_color": STORE_INFO["color"],
        "product_id": "",
        "name": item.get("name", ""),
        "brand": "",
        "price": price,
        "was_price": None,
        "on_sale": False,
        "savings": 0,
        "image": item.get("imageUrl", ""),
        "url": item.get("productUrl", ""),
        "sizing": item.get("size", ""),
        "category": "Viande",
        "scraped_at": datetime.now().isoformat(),
    }

def scrape_iga(key=APIFY_KEY):
    """Scrape IGA for meat products."""
    print(f"\n🔄 Scraping IGA (via Voilà.ca)...")
    
    if not key:
        print("  ❌ APIFY_API_KEY non trouvée")
        return []
    
    raw_items = run_scraper(max_items=100, key=key)
    
    if not raw_items:
        return []
    
    # Filter for meat products
    meat_items = [i for i in raw_items if is_meat_product(i)]
    print(f"  🥩 {len(meat_items)} produits viande sur {len(raw_items)}")
    
    products = [normalize_product(i) for i in meat_items]
    return products

if __name__ == "__main__":
    products = scrape_iga()
    if products:
        print(f"\n{'='*40}")
        print(f"RÉSULTAT: {len(products)} produits IGA")
        print(f"{'='*40}")
        for p in products[:5]:
            print(f"  {p['name']} — {p['price']}$")
            print(f"    🖼️  {p['image'][:60]}...")
    else:
        print("\n❌ Aucun produit IGA")
    
    # JSON output for pipeline
    print(f"\n---JSON_OUTPUT---")
    print(json.dumps(products, ensure_ascii=False))
