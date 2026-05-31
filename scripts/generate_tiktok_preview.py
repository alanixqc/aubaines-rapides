#!/usr/bin/env python3
"""Generate TikTok data JSON for preview page"""
import json, urllib.request, time, os

APIFY_KEY = os.environ.get("APIFY_API_KEY", "")
if not APIFY_KEY:
    env = r"C:\Users\Mark France\aubaines-rapides\.env"
    if os.path.exists(env):
        with open(env) as f:
            for line in f:
                line = line.strip()
                if line.startswith("APIFY_API_KEY="):
                    APIFY_KEY = line.split("=", 1)[1].strip()
                    break


def scrape(query, limit=20):
    payload = {
        "searchQueries": [query],
        "resultsPerPage": limit,
        "searchSection": "",
        "proxyCountryCode": "None",
        "maxFollowersPerProfile": 0, "maxFollowingPerProfile": 0,
        "commentsPerPost": 0, "topLevelCommentsPerPost": 0, "maxRepliesPerComment": 0,
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        "https://api.apify.com/v2/acts/clockworks~tiktok-scraper/runs",
        data=data, method="POST",
        headers={"Authorization": f"Bearer {APIFY_KEY}", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        run = json.loads(r.read())
    rid = run["data"]["id"]

    for i in range(30):
        time.sleep(5)
        r2 = urllib.request.Request(
            f"https://api.apify.com/v2/actor-runs/{rid}",
            headers={"Authorization": f"Bearer {APIFY_KEY}"}
        )
        with urllib.request.urlopen(r2, timeout=15) as resp:
            st = json.loads(resp.read())
        s = st["data"]["status"]
        print(f"  [{i+1}] {s}")
        if s in ("SUCCEEDED", "FAILED", "TIMEOUT", "ABORTED"):
            break
    if s != "SUCCEEDED":
        return []
    ds = st["data"]["defaultDatasetId"]
    r3 = urllib.request.Request(
        f"https://api.apify.com/v2/datasets/{ds}/items",
        headers={"Authorization": f"Bearer {APIFY_KEY}"}
    )
    with urllib.request.urlopen(r3) as resp:
        return json.loads(resp.read())


def clean(v):
    author = v.get("authorMeta", {})
    return {
        "author": author.get("name", "?"),
        "nickname": author.get("nickName", ""),
        "avatar": author.get("avatar", ""),
        "text": v.get("text", "")[:200],
        "plays": v.get("playCount", 0),
        "likes": v.get("diggCount", 0),
        "url": v.get("webVideoUrl", ""),
        "hashtags": [h.get("name","") for h in v.get("hashtags", [])],
        "duration": v.get("videoMeta", {}).get("duration", 0),
        "created": v.get("createTimeISO", ""),
        "fans": author.get("fans", 0),
    }


queries = {"poulet": "recette poulet pas cher", "boeuf": "recette boeuf pas cher", "economie": "aubaine epicerie"}
all_data = {}
for cat, q in queries.items():
    print(f"{cat}: {q}")
    raw = scrape(q, 20)
    all_data[cat] = [clean(v) for v in raw]
    print(f"  -> {len(all_data[cat])} videos")

output = {
    "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "categories": all_data,
}
path = r"C:\Users\Mark France\aubaines-rapides\web\data\tiktok_preview.json"
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"\nSaved: {path}")
print(f"  poulet: {len(all_data['poulet'])}")
print(f"  boeuf:  {len(all_data['boeuf'])}")
print(f"  economie: {len(all_data['economie'])}")
