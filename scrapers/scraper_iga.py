#!/usr/bin/env python3
"""scraper_iga.py — Scraper IGA via Apify Voilà.ca avec DB
Usage: python scraper_iga.py --db
"""
import json, urllib.request, time, os, sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scripts.db_saver import save_products_to_db, save_deals_json

# Lire la clé API
APIFY_KEY = os.environ.get("APIFY_API_KEY", "")
if not APIFY_KEY:
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.strip().startswith("APIFY_API_KEY="):
                    APIFY_KEY = line.strip().split("=", 1)[1].strip()
                    break

STORE_INFO = {"name": "IGA", "banner": "iga", "color": "#009640"}

MEAT_KW = ["beef","pork","chicken","turkey","boeuf","porc","poulet","dinde",
           "steak","ground beef","boeuf haché","bœuf haché","haché","burger",
           "sausage","saucisse","bacon","rib","côte","lanière","poitrine",
           "breast","wing","aile","cuisse","filet","roast","rôti","bœuf",
           "veau","lamb","agneau","ham","jambon","viande","meat","wagyu",
           "smokies","chorizo","sirloin","ground","flank","brisket","steak"]
EXCLUDE = ["drumstick","bouillon","broth","soup","dog","cat","pet","animal",
           "vegetarian","vegan","veggie","plant-based","végé","végétarien",
           "bun","bread","pain","tortilla","pasta filled","ravioli","tortellini"]

def api_get(path):
    req = urllib.request.Request(f"https://api.apify.com/v2{path}",
                                  headers={"Authorization": f"Bearer {APIFY_KEY}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def run_voila(max_items=100):
    payload = {
        "keywords": "", "location": "J7Z 1J6", "maxItems": max_items,
        "scrapeProductDetails": False,
        "proxyConfiguration": {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"]}
    }
    req = urllib.request.Request(
        "https://api.apify.com/v2/acts/ocrad~voila-product-scraper/runs",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {APIFY_KEY}", "Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        run = json.loads(r.read())
    run_id = run["data"]["id"]
    print(f"  Run ID: {run_id}")
    
    for i in range(20):
        time.sleep(10)
        r = api_get(f"/acts/ocrad~voila-product-scraper/runs/{run_id}")
        s = r["data"]["status"]
        c = r["data"].get("usageTotalUsd", 0)
        print(f"    [{i+1}] {s} (${c:.4f})")
        if s in ("SUCCEEDED","FAILED","TIMEOUT"): break
    
    if s != "SUCCEEDED": return []
    items = api_get(f"/datasets/{r['data']['defaultDatasetId']}/items")
    print(f"  ✅ {len(items)} items, ${r['data'].get('usageTotalUsd',0):.4f}")
    return items

def is_meat(item):
    tags = item.get("tags")
    if not isinstance(tags, (list, tuple)):
        tags = [str(tags)] if tags is not None else []
    if isinstance(tags, str): tags = [tags]
    name = (item.get("name","") + " " + " ".join(tags)).lower()
    return any(k in name for k in MEAT_KW) and not any(k in name for k in EXCLUDE)

def normalize(item):
    price_str = item.get("price", "$0").replace("$","").replace(",","")
    try: price = float(price_str)
    except: price = 0.0
    return {
        "name": item.get("name",""),
        "brand": "",
        "price": price,
        "was_price": None,
        "on_sale": False,
        "image": item.get("imageUrl",""),
        "url": item.get("productUrl",""),
        "sizing": item.get("size",""),
        "store": STORE_INFO["name"],
        "category": "Viande",
        "meat_type": None,
        "scraped_at": datetime.now().isoformat(),
    }

def scrape_iga():
    if not APIFY_KEY:
        print("❌ APIFY_API_KEY non trouvée")
        return []
    print(f"\n🔄 IGA (via Voilà.ca)...")
    raw = run_voila(100)
    meat = [i for i in raw if is_meat(i)]
    print(f"  🥩 {len(meat)} produits viande")
    return [normalize(i) for i in meat]

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", action="store_true", help="Écrire dans la DB")
    args = ap.parse_args()
    
    products = scrape_iga()
    
    if args.db and products:
        save_products_to_db(products, "IGA", slug="iga")
    
    if products:
        save_deals_json(products, "iga")
        print(f"\nRÉSULTAT: {len(products)} produits IGA")
    
    print(f"\n---JSON_OUTPUT---")
    print(json.dumps(products, ensure_ascii=False))
