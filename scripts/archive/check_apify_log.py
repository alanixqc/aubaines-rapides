#!/usr/bin/env python3
"""Check Apify run log."""
import json, urllib.request, os

KEY = os.environ.get("APIFY_API_KEY", "")
RUN_ID = "kTj6Bnts8mDZL7TVP"

def api_get(path):
    req = urllib.request.Request(
        f"https://api.apify.com/v2{path}",
        headers={"Authorization": f"Bearer {KEY}"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())

# Get run log
log = api_get(f"/acts/aitorsm~pcexpress-product-scraper/runs/{RUN_ID}/log")
print("=== LOG ===")
if isinstance(log, dict):
    print(json.dumps(log, indent=2)[:3000])
elif isinstance(log, list):
    for line in log[-50:]:
        print(line.get('message', str(line)) if isinstance(line, dict) else str(line))
else:
    print(str(log)[:3000])

# Also check the key-value store for any saved input/output
try:
    kv_store = api_get("/acts/aitorsm~pcexpress-product-scraper/runs/{RUN_ID}/key-value-store")
    print(f"\nKV Store: {json.dumps(kv_store, indent=2)[:1000]}")
except:
    pass
