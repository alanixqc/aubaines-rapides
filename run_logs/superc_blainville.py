import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
from playwright.sync_api import sync_playwright

URL = 'https://www.superc.ca/en/aisles/meat-poultry/beef-veal'

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(locale='fr-CA', user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36', viewport={'width':1440,'height':900})
    pg = ctx.new_page()
    pg.goto(URL, wait_until='domcontentloaded', timeout=90000)
    pg.wait_for_timeout(5000)

    pg.evaluate("""() => { const e=[...document.querySelectorAll('a,button')].filter(x=>/Change store/i.test(x.innerText||'')); if(e[0]) e[0].click(); }""")
    pg.wait_for_timeout(4000)

    # city search
    city = None
    for sel in ('input[name="city"]', 'input#city', 'input[placeholder*="ity"]', 'input[placeholder*="ille"]'):
        loc = pg.locator(sel)
        if loc.count():
            city = loc.first
            print('city input:', sel, flush=True)
            break
    if city:
        city.fill('Blainville')
        pg.wait_for_timeout(1000)
        # click Find
        pg.evaluate("""() => { const b=[...document.querySelectorAll('button,a')].filter(x=>/^Find$/i.test((x.innerText||'').trim())); if(b[0]) b[0].click(); }""")
        pg.wait_for_timeout(7000)

    stores = pg.evaluate("""() => [...document.querySelectorAll('[class*="store"]')]
        .map(e => (e.innerText||'').trim()).filter(t => /^Super C -/.test(t) || t.length<80).slice(0,8)""")
    print('STORES after city:', stores, flush=True)

    # click the first store entry that looks like a store name
    clicked = pg.evaluate("""() => {
      const cands = [...document.querySelectorAll('a,button,li,div')]
        .filter(e => (e.innerText||'').trim().startsWith('Super C -') && e.offsetParent !== null);
      const el = cands[cands.length-1] || cands[0];
      if (!el) return 'none';
      el.click(); return el.innerText.trim().slice(0,40);
    }""")
    print('store clicked:', clicked, flush=True)
    pg.wait_for_timeout(4000)

    conf = pg.evaluate("""() => { const b=[...document.querySelectorAll('button,a')].filter(x=>/Confirm my shopping store/i.test(x.innerText||'')); if(!b.length) return 'no confirm btn'; b[0].click(); return 'confirmed'; }""")
    print('confirm store:', conf, flush=True)
    pg.wait_for_timeout(7000)

    pg.goto(URL, wait_until='domcontentloaded', timeout=90000)
    pg.wait_for_timeout(7000)
    body = pg.inner_text('body')
    print('zero results?', 'found 0 results' in body, flush=True)
    print('store label:', [l.strip() for l in body.split('\n') if l.strip().startswith('Super C -')][:2], flush=True)
    cards = pg.locator('[data-testid*="product"],product-tile,[class*="product-tile"]').count()
    print('cards:', cards, flush=True)
    pg.screenshot(path='run_logs/superc_blainville.png', full_page=False)
    b.close()
