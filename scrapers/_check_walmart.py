"""Quick Walmart check - what does the page look like?"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://www.walmart.ca/en/browse/grocery/meat-seafood/10019_10086",
              wait_until="domcontentloaded", timeout=30000)
    import time
    time.sleep(8)
    title = page.title()
    text = page.evaluate("document.body?.innerText || ''")
    html = page.content()
    print(f"Title: '{title}'")
    print(f"HTML: {len(html)} chars")
    print(f"Text[:600]: {text[:600]}")
    # Check for products
    tiles = page.evaluate("document.querySelectorAll('[data-testid*=\"product\"]').length")
    print(f"Product tiles: {tiles}")
    # Check for PerimeterX
    if "block" in text.lower() or "denied" in text.lower():
        print("⚠️ BLOCKED")
    else:
        print("✅ Loaded OK")
    browser.close()
