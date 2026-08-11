#!/usr/bin/env python3
"""Capture le screenshot de la circulaire Tigre Geant (etape retiree du scraper)."""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db.schema import get_week_start
from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
CACHE_DIR = os.path.join(PROJECT_ROOT, "cache", "tigregeant")
FLYER_URL = "https://www.gianttiger.com/fr/collections/flyers-and-deals?view=flyers"
os.makedirs(CACHE_DIR, exist_ok=True)

week_start = get_week_start()
out_path = os.path.join(CACHE_DIR, f"circulaire_{week_start}.png")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        locale="fr-CA",
        viewport={"width": 1280, "height": 2000},
    )
    page = context.new_page()
    print("  Chargement de la circulaire...")
    try:
        page.goto(FLYER_URL, timeout=45000, wait_until="networkidle")
    except PwTimeout:
        print("  Timeout sur le chargement initial, on continue...")
    time.sleep(5)
    try:
        accept = page.get_by_role("button", name="Accepter Tout")
        if accept.is_visible(timeout=3000):
            accept.click()
            time.sleep(2)
            print("  Cookies acceptes")
    except Exception:
        pass
    time.sleep(3)
    page.screenshot(path=out_path, full_page=True)
    browser.close()

size_kb = os.path.getsize(out_path) // 1024
print(f"Screenshot OK: {out_path} ({size_kb} KB)")
