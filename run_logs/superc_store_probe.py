from playwright.sync_api import sync_playwright
import re

URL = 'https://www.superc.ca/en/aisles/meat-poultry/beef-veal'
POSTAL = 'J7C 1A1'

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(locale='fr-CA',
                        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                        viewport={'width': 1440, 'height': 900})
    pg = ctx.new_page()
    pg.goto(URL, wait_until='domcontentloaded', timeout=90000)
    pg.wait_for_timeout(6000)

    # 1. Look for store selection entry points
    for txt in ['Select', 'Pick-up or Delivery', 'Choose', 'Choisir']:
        try:
            loc = pg.get_by_text(txt, exact=False)
            print(f'text="{txt}" count={loc.count()}', flush=True)
        except Exception as e:
            print(f'text="{txt}" ERR {e}', flush=True)

    # 2. Try clicking the store selector
    clicked = False
    for label in ['Pick-up or Delivery', 'Select']:
        try:
            loc = pg.get_by_text(label, exact=False).first
            if loc.is_visible():
                loc.click(timeout=5000)
                clicked = True
                print('clicked:', label, flush=True)
                pg.wait_for_timeout(4000)
                break
        except Exception as e:
            print('click fail', label, type(e).__name__, str(e)[:100], flush=True)

    # 3. Dump any inputs on the page
    try:
        n = pg.locator('input').count()
        print('inputs:', n, flush=True)
        for i in range(min(n, 8)):
            el = pg.locator('input').nth(i)
            print('  input', i, el.get_attribute('type'), el.get_attribute('placeholder'), el.get_attribute('name'), flush=True)
    except Exception as e:
        print('inputs ERR', e, flush=True)

    body = pg.inner_text('body')
    print('--- modal/body excerpt ---', flush=True)
    print(body[:1200], flush=True)

    # 4. Try postal entry
    try:
        inp = pg.locator('input[type="text"], input[inputmode="numeric"], input[placeholder*="ostal"], input[placeholder*="ode postal"]').first
        if inp.count() and inp.is_visible():
            inp.fill(POSTAL)
            print('filled postal', flush=True)
            pg.wait_for_timeout(1500)
            pg.keyboard.press('Enter')
            pg.wait_for_timeout(5000)
            print('after postal text:', pg.inner_text('body')[:800].replace('\n', ' | '), flush=True)
    except Exception as e:
        print('postal ERR', type(e).__name__, str(e)[:120], flush=True)

    print('FINAL URL:', pg.url, flush=True)
    b.close()
