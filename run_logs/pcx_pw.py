#!/usr/bin/env python3
"""Fetch PC Express store category pages with Playwright (headless) and write to DB.
Fallback for scraper_maxi.py when urllib gets 403 / empty layout.
Usage: python run_logs/pcx_pw.py maxi|provigo|loblaws
"""
import sys, os, json, re
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from scripts.db_saver import save_products_to_db, save_deals_json
from scrapers.scraper_maxi import STORES, normalize

from playwright.sync_api import sync_playwright


def find_tiles(obj, out, seen):
    """Recursively collect product tile dicts (layout-agnostic)."""
    if isinstance(obj, dict):
        pid = obj.get('productId')
        if pid and obj.get('title') and ('pricing' in obj or 'packageSizing' in obj):
            if pid not in seen:
                seen.add(pid)
                out.append(obj)
        for v in obj.values():
            find_tiles(v, out, seen)
    elif isinstance(obj, list):
        for v in obj:
            find_tiles(v, out, seen)


def fetch_html(page, url):
    page.goto(url, wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(6000)
    try:
        page.wait_for_selector('script#__NEXT_DATA__', timeout=15000)
    except Exception:
        pass
    return page.content()


def extract(html):
    m = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        return []
    data = json.loads(m.group(1))
    tiles = []
    find_tiles(data, tiles, set())
    return tiles


def main():
    key = sys.argv[1]
    store = STORES[key]
    all_products = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(
            locale="fr-CA",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
        )
        page = ctx.new_page()
        for label, url, dairy in (("viande", store['category_url'], False),
                                  ("laitages", store.get('dairy_url'), True)):
            if not url:
                continue
            try:
                html = fetch_html(page, url)
                tiles = extract(html)
                prods = [normalize(t, store, is_dairy=dairy) for t in tiles]
                sales = sum(1 for x in prods if x.get('on_sale'))
                print(f"🔄 {store['name']} {label}: ✅ {len(prods)} produits ({sales} spéciaux) [html {len(html)}]")
                all_products.extend(prods)
            except Exception as e:
                print(f"🔄 {store['name']} {label}: ❌ {type(e).__name__}: {e}")
        browser.close()

    # dedupe by url/name+size
    seen, clean = set(), []
    for p in all_products:
        k = (p['name'], p.get('sizing'))
        if k in seen:
            continue
        seen.add(k)
        clean.append(p)

    print(f"TOTAL {store['name']}: {len(clean)}")
    if clean:
        save_products_to_db(clean, store['name'])
        path = save_deals_json(clean, key)
        print(f"💾 DB + JSON: {path}")


if __name__ == "__main__":
    main()
