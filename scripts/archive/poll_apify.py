#!/usr/bin/env python3
"""Poll Apify run status and fetch results."""
import json, urllib.request, time, sys, os

KEY = os.environ.get("APIFY_API_KEY", "")
RUN_ID = "kTj6Bnts8mDZL7TVP"

def api_get(path):
    req = urllib.request.Request(
        f"https://api.apify.com/v2{path}",
        headers={"Authorization": f"Bearer {KEY}"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())

# Poll for completion
for i in range(12):
    time.sleep(10)
    data = api_get(f"/acts/aitorsm~pcexpress-product-scraper/runs/{RUN_ID}")
    status = data['data']['status']
    stats = data['data']['stats']
    cost = data['data'].get('usageTotalUsd', 0)
    results = stats.get('results', 0)
    print(f"[{i+1}] Status: {status}, Items: {results}, Cost: ${cost:.4f}")
    sys.stdout.flush()
    
    if status in ('SUCCEEDED', 'FAILED', 'ABORTED', 'TIMEOUT'):
        break

# Get results
if status == 'SUCCEEDED':
    dataset_id = data['data']['defaultDatasetId']
    result_data = api_get(f"/datasets/{dataset_id}/items")
    print(f"\n=== Got {len(result_data)} items ===")
    for item in result_data[:5]:  # Show first 5
        name = item.get('name', ['N/A'])[0] if isinstance(item.get('name'), list) else item.get('name', 'N/A')
        price = item.get('price', ['N/A'])
        if isinstance(price, list):
            price = price[0]
        image = item.get('image', [''])
        if isinstance(image, list):
            image = image[0] if image else ''
        was_price = item.get('price_old', [None])
        if isinstance(was_price, list):
            was_price = was_price[0]
        
        print(f"\n📦 {name}")
        print(f"   Prix: {price}$" + (f" (était {was_price}$)" if was_price else ""))
        print(f"   Image: {image[:80]}...")
        print(f"   URL: {item.get('url', [''])[0]}")
    
    # Print summary
    print(f"\n=== Coût total: ${cost:.4f} ===")
    print(f"Prix par item: ${cost/max(len(result_data),1):.4f}")
else:
    print(f"\nRun failed with status: {status}")
    # Get error details
    try:
        log = api_get(f"/acts/aitorsm~pcexpress-product-scraper/runs/{RUN_ID}/log")
        print(json.dumps(log, indent=2)[:2000])
    except:
        pass
