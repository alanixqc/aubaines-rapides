#!/usr/bin/env python3
"""Super C preview scraper with pickup-service confirmation (fix for '0 results').
Reuses scrapers.scraper_superc parsing, adds the fulfillment-mode step the site now requires.
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from scrapers.scraper_superc import SuperCScraper

CAT_URL = 'https://www.superc.ca/en/aisles/meat-poultry/beef-veal'


def confirm_service(page):
    """Confirm Pick-up service + timeslot if the site shows the 'Select Pick-up or Delivery' gate."""
    page.goto(CAT_URL, wait_until='domcontentloaded', timeout=90000)
    page.wait_for_timeout(5000)
    body = page.inner_text('body')
    if 'found 0 results' not in body:
        print('   ℹ️ gate not detected, products already visible', flush=True)
        return True

    # open the service modal from the banner (JS click: element can sit outside viewport)
    opened = page.evaluate("""() => {
      const b = document.querySelector('button.choose-new-service-pickup');
      if (!b) return 'no button';
      b.click();
      return 'clicked';
    }""")
    print(f'   → banner click: {opened}', flush=True)
    if opened != 'clicked':
        try:
            page.get_by_text('Pick-up or Delivery', exact=False).first.evaluate('(el) => el.click()')
            print('   → modal opened (text JS)', flush=True)
        except Exception as e:
            print('   ❌ cannot open modal:', type(e).__name__, str(e)[:120], flush=True)
            return False
    page.wait_for_timeout(3500)

    # choose Pickup inside the modal
    for how, sel in (('role', 'Pickup'), ('text', 'Pickup'), ('css', 'button:has-text("Pickup")')):
        try:
            if how == 'role':
                loc = page.get_by_role('button', name='Pickup', exact=True)
            elif how == 'text':
                loc = page.get_by_text('Pickup', exact=True)
            else:
                loc = page.locator(sel)
            if loc.count():
                loc.first.click(timeout=6000)
                print(f'   → Pickup selected ({how}, n={loc.count()})', flush=True)
                break
        except Exception as e:
            print(f'   pickup {how} fail {type(e).__name__} {str(e)[:80]}', flush=True)
    page.wait_for_timeout(2500)

    # confirm
    for sel in ('button:has-text("Confirm")', 'button:has-text("Confirmer")'):
        try:
            loc = page.locator(sel)
            if loc.count():
                loc.first.click(timeout=6000)
                print('   → Confirm clicked', flush=True)
                break
        except Exception as e:
            print('   confirm fail', type(e).__name__, str(e)[:80], flush=True)
    page.wait_for_timeout(6000)

    page.goto(CAT_URL, wait_until='domcontentloaded', timeout=90000)
    page.wait_for_timeout(6000)
    body = page.inner_text('body')
    ok = 'found 0 results' not in body
    print(f'   → after confirm: products_visible={ok}', flush=True)
    return ok


def main():
    with SuperCScraper(headless=True) as s:
        page = s._page
        print('=== STEP: confirm fulfillment service ===', flush=True)
        if not confirm_service(page):
            print('❌ Super C still shows 0 results after service confirmation', flush=True)
            page.screenshot(path='run_logs/superc_after_confirm.png', full_page=False)
            return 1

        print('=== STEP: scrape all categories ===', flush=True)
        products = s.scrape_flat(None)
        print(f'📦 Super C products parsed: {len(products)}', flush=True)
        if not products:
            return 1
        s.store_products(products)
        print('💾 stored', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
