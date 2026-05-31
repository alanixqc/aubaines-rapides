#!/usr/bin/env python3
"""capture_flyers.py — Capture les circulaires des épiceries en screenshots."""
import json, os, sys, time, re
from datetime import date
from playwright.sync_api import sync_playwright

WEB_DIR = os.path.join(os.path.dirname(__file__), "..", "web", "flyers")
os.makedirs(WEB_DIR, exist_ok=True)

FLYERS = {
    "superc": {
        "url": "https://www.superc.ca/fr/circulaire",
        "name": "Super C",
        "headless": False,
    },
    "metro": {
        "url": "https://www.metro.ca/circulaire",
        "name": "Metro",
        "headless": False,
    },
    "maxi": {
        "url": "https://www.maxi.ca/fr/deals/flyer",
        "name": "Maxi",
        "headless": True,
    },
    "provigo": {
        "url": "https://www.provigo.ca/fr/deals/flyer",
        "name": "Provigo",
        "headless": True,
    },
    "iga": {
        "url": "https://www.iga.net/fr/circulaire",
        "name": "IGA",
        "headless": False,
    },
    "tigregeant": {
        "url": "https://www.gianttiger.com/fr/collections/flyers-and-deals?view=flyers",
        "name": "Tigre Géant",
        "headless": True,
    },
}

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"

def capture(store_key, info):
    out_path = os.path.join(WEB_DIR, f"{store_key}-flyer.png")
    print(f"\n📸 {info['name']}... ", end="", flush=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=info["headless"],
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 2000},
            locale="fr-CA",
            extra_http_headers={"Accept-Language": "fr-CA,fr;q=0.9"},
        )
        page = ctx.new_page()

        # Block images/fonts for speed, keep layout
        page.route(re.compile(r"\.(woff|woff2|ttf|eot)(\?|$)"), lambda r: r.abort())

        try:
            page.goto(info["url"], wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(5000)

            # Try to accept cookies
            for sel in ["button:has-text('Accepter')", "button:has-text('Accept')",
                        "#onetrust-accept-btn-handler", ".accept-cookies"]:
                try:
                    btn = page.locator(sel)
                    if btn.count() > 0 and btn.first.is_visible(timeout=2000):
                        btn.first.click(timeout=2000)
                        page.wait_for_timeout(1500)
                        break
                except:
                    pass

            # Try to close modal
            for sel in ["button:has-text('Passer')", "button:has-text('Skip')",
                        ".modal-close", "[aria-label='Close']"]:
                try:
                    btn = page.locator(sel)
                    if btn.count() > 0 and btn.first.is_visible(timeout=1000):
                        btn.first.click(timeout=2000)
                        page.wait_for_timeout(1000)
                        break
                except:
                    pass

            # Scroll to load lazy content
            for _ in range(5):
                page.evaluate("window.scrollBy(0, 800)")
                page.wait_for_timeout(500)

            # Scroll back to top
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(500)

            # Full page screenshot
            page.screenshot(path=out_path, full_page=True)
            size_kb = os.path.getsize(out_path) / 1024
            print(f"✅ ({size_kb:.0f}KB)")

        except Exception as e:
            print(f"❌ {e}")
            # Try partial screenshot anyway
            try:
                page.screenshot(path=out_path)
                size_kb = os.path.getsize(out_path) / 1024
                print(f"   ⚠️ Partial screenshot ({size_kb:.0f}KB)")
            except:
                print(f"   ❌ Failed completely")

        finally:
            browser.close()

    return os.path.exists(out_path)

if __name__ == "__main__":
    print("=" * 50)
    print(f"📰 CAPTURE CIRCULAIRES — {date.today()}")
    print("=" * 50)

    results = {}
    for key, info in FLYERS.items():
        results[key] = capture(key, info)

    print(f"\n{'=' * 50}")
    print("RÉSULTATS:")
    for key, ok in results.items():
        name = FLYERS[key]["name"]
        path = os.path.join(WEB_DIR, f"{key}-flyer.png")
        size = os.path.getsize(path) / 1024 if os.path.exists(path) else 0
        print(f"  {'✅' if ok else '❌'} {name:15s} ({size:.0f}KB)")
    print("=" * 50)
