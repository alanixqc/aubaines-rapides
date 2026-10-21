from playwright.sync_api import sync_playwright

URL = 'https://www.superc.ca/en/aisles/meat-poultry/beef-veal'

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(locale='fr-CA',
                        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                        viewport={'width': 1440, 'height': 900})
    pg = ctx.new_page()
    pg.goto(URL, wait_until='domcontentloaded', timeout=90000)
    pg.wait_for_timeout(5000)

    # Inspect the banner structure around 'Pick-up or Delivery'
    info = pg.evaluate("""() => {
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
      let el = null;
      while (walker.nextNode()) {
        const n = walker.currentNode;
        if (n.children.length === 0 && n.textContent.trim() === 'Pick-up or Delivery') { el = n; break; }
      }
      if (!el) return 'not found';
      let box = el;
      for (let i = 0; i < 5 && box.parentElement; i++) box = box.parentElement;
      const btns = [...box.querySelectorAll('button,a,[role="button"]')].map(b => ({
        tag: b.tagName, text: (b.textContent||'').trim().slice(0,40), cls: (b.className||'').toString().slice(0,60)
      }));
      return JSON.stringify({bannerText: box.innerText.slice(0,300), buttons: btns.slice(0,12)});
    }""")
    print('BANNER:', info, flush=True)

    # Click the 'Select' button inside that banner
    ok = pg.evaluate("""() => {
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
      let el = null;
      while (walker.nextNode()) {
        const n = walker.currentNode;
        if (n.children.length === 0 && n.textContent.trim() === 'Pick-up or Delivery') { el = n; break; }
      }
      if (!el) return 'no anchor';
      let box = el;
      for (let i = 0; i < 5 && box.parentElement; i++) box = box.parentElement;
      const cand = [...box.querySelectorAll('button,a,[role="button"]')].find(b => (b.textContent||'').trim().toLowerCase().startsWith('select'));
      if (!cand) return 'no select btn';
      cand.click();
      return 'clicked';
    }""")
    print('CLICK:', ok, flush=True)
    pg.wait_for_timeout(4000)
    body = pg.inner_text('body')
    print('--- AFTER CLICK ---', flush=True)
    print(body[:1500].replace('\n', ' | '), flush=True)

    # Look for pickup/delivery options
    for label in ['Pick-up', 'Pickup', 'Delivery', 'Ramassage', 'Livraison']:
        try:
            loc = pg.get_by_role('button', name=label, exact=False)
            print(f'btn {label}: {loc.count()}', flush=True)
        except Exception as e:
            print(f'btn {label} ERR', str(e)[:60], flush=True)

    pg.screenshot(path='run_logs/superc_after_click.png', full_page=False)
    b.close()
