#!/usr/bin/env python3
"""Super C: confirm Pick-up service (postal + store) then scrape via SuperCScraper."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from scrapers.scraper_superc import SuperCScraper

CAT_URL = 'https://www.superc.ca/en/aisles/meat-poultry/beef-veal'
POSTAL = 'J7C 1A1'


def count_products(page):
    try:
        return page.evaluate("""() => document.body.innerText.includes('found 0 results') ? 0 : -1""")
    except Exception:
        return -2


def confirm(page):
    page.goto(CAT_URL, wait_until='domcontentloaded', timeout=90000)
    page.wait_for_timeout(5000)
    if 'found 0 results' not in page.inner_text('body'):
        print('   ℹ️ products already visible', flush=True)
        return True

    page.evaluate("()=>{const b=document.querySelector('button.choose-new-service-pickup'); if(b) b.click();}")
    page.wait_for_timeout(4000)

    # postal code
    try:
        inp = page.locator('#deliveryPostalCode')
        inp.fill(POSTAL, timeout=5000)
        print('   → postal filled', flush=True)
        page.wait_for_timeout(800)
        for sel in ('.postalCode_submit_delivery', '.postalCode_submit', '.postalCode_submit_pickup_list'):
            b = page.locator(sel)
            if b.count() and b.first.is_visible():
                b.first.click(timeout=5000)
                print(f'   → postal submitted via {sel}', flush=True)
                break
        page.wait_for_timeout(7000)
    except Exception as e:
        print('   postal step:', type(e).__name__, str(e)[:100], flush=True)

    # choose Pickup radio if present
    try:
        n = page.locator('input[type="radio"]').count()
        print(f'   radios: {n}', flush=True)
        for i in range(min(n, 4)):
            r = page.locator('input[type="radio"]').nth(i)
            print('    radio', i, r.get_attribute('id'), r.get_attribute('value'), 'checked=', r.is_checked(), flush=True)
    except Exception as e:
        print('   radios err', str(e)[:80], flush=True)

    # confirm button
    clicked = page.evaluate("""() => {
      const btns = [...document.querySelectorAll('#modal-service-and-timeslot button')]
        .filter(b => b.offsetParent !== null && (b.innerText||'').trim() === 'Confirm');
      if (!btns.length) return 'no confirm';
      btns[0].click(); return 'clicked';
    }""")
    print('   → confirm:', clicked, flush=True)
    page.wait_for_timeout(8000)

    page.goto(CAT_URL, wait_until='domcontentloaded', timeout=90000)
    page.wait_for_timeout(7000)
    body = page.inner_text('body')
    ok = 'found 0 results' not in body
    print(f'   → products visible after confirm: {ok}', flush=True)
    if not ok:
        page.screenshot(path='run_logs/superc_confirm_fail.png', full_page=False)
    return ok


def main():
    with SuperCScraper(headless=True) as s:
        page = s._page
        if not confirm(page):
            print('❌ Super C always 0 results', flush=True)
            return 1
        products = s.scrape_flat(None)
        print(f'📦 parsed: {len(products)}', flush=True)
        if products:
            s.store_products(products)
            print('💾 stored', flush=True)
        return 0 if products else 1


if __name__ == '__main__':
    sys.exit(main())
