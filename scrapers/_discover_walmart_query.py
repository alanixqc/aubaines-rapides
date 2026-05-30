#!/usr/bin/env python3
"""Extract Walmart products from fully-rendered page."""
import json, sys, os
from playwright.sync_api import sync_playwright

TARGET_URL = "https://www.walmart.ca/en/browse/grocery/meat-seafood/10019_10086"
OUTPUT = os.path.join(os.path.dirname(__file__), "..", "data", "walmart_products.json")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        locale="en-CA",
    )
    page = context.new_page()
    
    # Intercept the Browse API response
    products_data = []
    
    def on_response(response):
        url = response.url
        if "orchestra/snb/graphql/Browse" in url or "preso.intl" in url:
            try:
                body = response.text()
                data = json.loads(body)
                products_data.append({"url": url, "data": data})
                print(f"\n=== CAPTURED Browse API Response ===", file=sys.stderr)
                print(f"URL: {url[:200]}", file=sys.stderr)
                # Explore structure
                s = json.dumps(data, indent=2, ensure_ascii=False)
                print(f"Response: {s[:3000]}", file=sys.stderr)
            except:
                pass
    
    page.on("response", on_response)
    
    page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=120000)
    
    # Scroll down to trigger lazy loading
    for i in range(5):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(2000)
    page.wait_for_timeout(5000)
    
    # Extract products from DOM
    products = page.evaluate("""() => {
        // Look for product tiles in the rendered page
        const tiles = document.querySelectorAll(
            '[class*="product-tile"], [class*="productTile"], [data-testid*="product"], ' +
            'a[class*="product"], article[class*="product"], div[class*="product"]'
        );
        
        const results = [];
        const seen = new Set();
        
        tiles.forEach(tile => {
            // Get product name
            const titleEl = tile.querySelector('[class*="title"], [class*="name"], [class*="Name"], h3, h2, a');
            const name = titleEl ? titleEl.textContent.trim() : '';
            
            if (!name || seen.has(name)) return;
            seen.add(name);
            
            // Get price
            const priceEl = tile.querySelector('[class*="price"], [class*="Price"], [data-automation*="price"]');
            const price = priceEl ? priceEl.textContent.trim() : '';
            
            // Get image
            const img = tile.querySelector('img');
            const imgUrl = img ? img.src : '';
            
            // Get link
            const link = tile.closest('a') || tile.querySelector('a');
            const href = link ? link.href : '';
            
            if (name && price) {
                results.push({
                    name: name,
                    price: price,
                    image_url: imgUrl,
                    link: href,
                    html: tile.outerHTML.substring(0, 300),
                });
            }
        });
        
        return results;
    }""")
    
    # Also try to extract from the main content area
    main_content = page.evaluate("""() => {
        const main = document.querySelector('main') || document.querySelector('[role="main"]') || document.getElementById('main');
        if (!main) return {text: document.body.textContent.substring(0, 2000)};
        
        return {
            html: main.innerHTML.substring(0, 3000),
            text: main.textContent.substring(0, 2000),
            children: main.children.length,
        };
    }""")
    
    result = {
        "products": products,
        "main_content": main_content,
        "browse_api_responses": products_data,
        "title": page.title(),
    }
    
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n=== Products Found: {len(products)} ===", file=sys.stderr)
    for p in products[:10]:
        print(f"  {json.dumps(p, indent=2)[:200]}", file=sys.stderr)
    
    print(f"\n=== Main Content ===", file=sys.stderr)
    if isinstance(main_content, dict):
        print(f"  HTML first 500: {main_content.get('html', '')[:500]}", file=sys.stderr)
        print(f"  Text: {main_content.get('text', '')[:500]}", file=sys.stderr)
    
    print(f"\nSaved to {OUTPUT}", file=sys.stderr)
    browser.close()
