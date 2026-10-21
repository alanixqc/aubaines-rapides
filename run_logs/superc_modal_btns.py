from playwright.sync_api import sync_playwright

URL = 'https://www.superc.ca/en/aisles/meat-poultry/beef-veal'
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(locale='fr-CA', user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36', viewport={'width':1440,'height':900})
    pg = ctx.new_page()
    pg.goto(URL, wait_until='domcontentloaded', timeout=90000)
    pg.wait_for_timeout(5000)
    pg.evaluate("()=>{const b=document.querySelector('button.choose-new-service-pickup'); if(b) b.click();}")
    pg.wait_for_timeout(4000)

    out = pg.evaluate("""() => {
      const m = document.querySelector('#modal-service-and-timeslot');
      if (!m) return 'no modal';
      const btns = [...m.querySelectorAll('button')].map(b => ({
        text: (b.innerText||'').trim().slice(0,40),
        cls: (b.className||'').toString().slice(0,70),
        hidden: b.offsetParent === null
      })).filter(b => b.text || b.cls.includes('service'));
      const tabs = [...m.querySelectorAll('[data-service-type],[class*="service-type"],.st__service a, .service_tab')].map(e => ({tag:e.tagName, cls:(e.className||'').toString().slice(0,60), text:(e.innerText||'').trim().slice(0,30)}));
      return JSON.stringify({btns, tabs, footer: (m.querySelector('.st--footer')||{}).innerText || ''}, null, 1);
    }""")
    print(out, flush=True)
    b.close()
