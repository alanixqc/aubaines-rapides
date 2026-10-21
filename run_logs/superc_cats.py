from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(locale='fr-CA', user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36', viewport={'width':1440,'height':900})
    pg = ctx.new_page()
    pg.goto('https://www.superc.ca/en/aisles/meat-poultry/beef-veal', wait_until='domcontentloaded', timeout=90000)
    pg.wait_for_timeout(5000)
    links = pg.evaluate("""() => [...document.querySelectorAll('a[href*="/aisles/"]')]
        .map(a => a.getAttribute('href')).filter((v,i,s)=>s.indexOf(v)===i).slice(0,40)""")
    print('AISLE LINKS:', links, flush=True)
    for href in links[:8]:
        url = 'https://www.superc.ca' + href if href.startswith('/') else href
        try:
            pg.goto(url, wait_until='domcontentloaded', timeout=60000)
            pg.wait_for_timeout(4000)
            body = pg.inner_text('body')
            zero = 'found 0 results' in body
            cards = pg.locator('[data-testid*="product"], article, [class*="product-tile"], [class*="productTile"]').count()
            import re
            m = re.search(r'(\d[\d,\s]*)\s*items?', body)
            print(f'{href[:60]:60s} zero={zero} cards={cards} items_txt={m.group(0) if m else "-"}', flush=True)
        except Exception as e:
            print(href[:60], 'ERR', str(e)[:70], flush=True)
    b.close()
