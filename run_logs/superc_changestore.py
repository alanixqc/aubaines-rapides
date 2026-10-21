from playwright.sync_api import sync_playwright
import re

URL = 'https://www.superc.ca/en/aisles/meat-poultry/beef-veal'
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(locale='fr-CA', user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36', viewport={'width':1440,'height':900})
    pg = ctx.new_page()
    pg.goto(URL, wait_until='domcontentloaded', timeout=90000)
    pg.wait_for_timeout(5000)

    # open store locator via 'Change store'
    r = pg.evaluate("""() => {
      const els = [...document.querySelectorAll('a,button')].filter(e => /Change store|Changer de magasin/i.test(e.innerText||''));
      if (!els.length) return 'no change-store';
      els[0].click(); return 'clicked';
    }""")
    print('change store:', r, flush=True)
    pg.wait_for_timeout(5000)
    print('--- body head ---', flush=True)
    print(pg.inner_text('body')[:600].replace('\n',' | '), flush=True)

    # fill postal in locator
    for sel in ('#storeLocatorPostalCode', 'input[name="postalCode"]', 'input#postalCode', '#deliveryPostalCode'):
        loc = pg.locator(sel)
        if loc.count() and loc.first.is_visible():
            loc.first.fill('J7C 1A1')
            print('filled', sel, flush=True)
            pg.keyboard.press('Enter')
            pg.wait_for_timeout(6000)
            break
    body = pg.inner_text('body')[:1200]
    print('--- after postal ---', flush=True)
    print(body.replace('\n',' | '), flush=True)

    # list store results
    stores = pg.evaluate("""() => [...document.querySelectorAll('[class*="store"]')]
        .map(e => (e.innerText||'').trim()).filter(t => t.length>10 && t.length<160).slice(0,10)""")
    print('STORES:', stores, flush=True)
    pg.screenshot(path='run_logs/superc_storeloc.png', full_page=False)
    b.close()
