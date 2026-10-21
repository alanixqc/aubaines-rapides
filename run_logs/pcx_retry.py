#!/usr/bin/env python3
"""PC Express (Maxi/Provigo/Loblaws) via urllib with retry/backoff + layout-agnostic tile extraction.
Usage: python3 run_logs/pcx_retry.py provigo [attempts]
"""
import os, sys, json, re, time, random, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from scripts.db_saver import save_products_to_db, save_deals_json
from scrapers.scraper_maxi import STORES, normalize

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
H = {"User-Agent": UA, "Accept-Language": "fr-CA,fr;q=0.9",
     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}


def fetch(url):
    req = urllib.request.Request(url, headers=H)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8', 'replace')


def extract_tiles(html):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        return None, None
    data = json.loads(m.group(1))
    out, seen = [], set()

    def walk(o):
        if isinstance(o, dict):
            pid = o.get('productId')
            if pid and o.get('title') and ('pricing' in o or 'packageSizing' in o):
                if pid not in seen:
                    seen.add(pid)
                    out.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(data)
    # also classic path, if present
    try:
        comps = data['props']['pageProps']['initialData']['layout']['sections']['mainContentCollection']['components']
        for c in comps:
            for t in c.get('data', {}).get('productTiles', []):
                pid = t.get('productId')
                if pid and pid not in seen:
                    seen.add(pid)
                    out.append(t)
    except Exception:
        pass
    return out, data


def main():
    key = sys.argv[1]
    attempts = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    store = STORES[key]
    products = []
    for label, url, dairy in (("viande", store['category_url'], False),
                              ("laitages", store.get('dairy_url'), True)):
        if not url:
            continue
        tiles = None
        for a in range(attempts):
            try:
                html = fetch(url)
                tiles, data = extract_tiles(html)
                print(f"{store['name']} {label} try{a+1}: len={len(html)} tiles={len(tiles) if tiles is not None else 'no-nextdata'}", flush=True)
                if tiles:
                    break
            except Exception as e:
                print(f"{store['name']} {label} try{a+1}: {type(e).__name__} {str(e)[:60]}", flush=True)
                tiles = None
            time.sleep(random.uniform(12, 18))
        if tiles:
            prods = [normalize(t, store, is_dairy=dairy) for t in tiles]
            products.extend(prods)

    # dedupe
    seen, clean = set(), []
    for p in products:
        k = (p['name'], p.get('sizing'))
        if k in seen:
            continue
        seen.add(k)
        clean.append(p)

    print(f"TOTAL {store['name']}: {len(clean)}", flush=True)
    if clean:
        save_products_to_db(clean, store['name'])
        print('💾 DB written', flush=True)
        print('📄 JSON:', save_deals_json(clean, key), flush=True)
    return 0 if clean else 1


if __name__ == '__main__':
    sys.exit(main())
