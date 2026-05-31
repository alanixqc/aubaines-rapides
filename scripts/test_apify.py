#!/usr/bin/env python3
import json, urllib.request, sys, time, os

KEY = os.environ.get("APIFY_API_KEY", "")

payload = {
    "address": "Maxi Boulevard Grignon,  900 Saint-Jérôme J7Y 3S7",
    "bannerId": "maxi",
    "startUrls": [{"url": "https://www.maxi.ca/fr/alimentation/viande/c/27998"}],
    "maxItems": 30
}

req = urllib.request.Request(
    "https://api.apify.com/v2/acts/aitorsm~pcexpress-product-scraper/runs",
    data=json.dumps(payload).encode(),
    headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    method="POST"
)

try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
        print(json.dumps(data, indent=2))
except Exception as e:
    print(f"Error: {e}")
    if hasattr(e, 'read'):
        print(e.read().decode()[:2000])
