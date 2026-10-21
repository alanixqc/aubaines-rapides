from playwright.sync_api import sync_playwright

URL = 'https://www.superc.ca/en/aisles/meat-poultry/beef-veal'
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(locale='fr-CA', user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36', viewport={'width':1440,'height':900})
    pg = ctx.new_page()
    pg.goto(URL, wait_until='domcontentloaded', timeout=90000)
    pg.wait_for_timeout(5000)
    print('banner click:', pg.evaluate("()=>{const b=document.querySelector('button.choose-new-service-pickup'); if(!b)return 'no'; b.click(); return 'ok'}"), flush=True)
    pg.wait_for_timeout(4000)

    html = pg.evaluate("""() => {
      // find deepest element containing 'Select your timeslot'
      const all = [...document.querySelectorAll('div,section,aside,dialog')];
      const hit = all.filter(e => e.innerText && e.innerText.includes('Select your timeslot') && e.innerText.length < 600);
      const el = hit.sort((a,b)=>a.innerText.length-b.innerText.length)[0];
      if (!el) return 'no modal';
      let box = el;
      for (let i=0;i<3 && box.parentElement;i++) box = box.parentElement;
      return box.outerHTML.slice(0, 4000);
    }""")
    print('--- MODAL HTML ---', flush=True)
    print(html, flush=True)
    pg.screenshot(path='run_logs/superc_modal.png', full_page=False)
    b.close()
