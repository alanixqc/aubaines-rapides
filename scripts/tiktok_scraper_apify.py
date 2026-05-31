#!/usr/bin/env python3
"""TikTok Scraper via Apify clockworks~tiktok-scraper

Usage:
  python scripts/tiktok_scraper_apify.py search "recette poulet"
  python scripts/tiktok_scraper_apify.py hashtag "recettefacile"
  python scripts/tiktok_scraper_apify.py profile "johndoe"
  python scripts/tiktok_scraper_apify.py video "https://tiktok.com/@user/video/12345"
  python scripts/tiktok_scraper_apify.py followers "johndoe"
  python scripts/tiktok_scraper_apify.py following "johndoe"
"""

import json, urllib.request, time, os, sys

ACTOR_ID = "clockworks~tiktok-scraper"

APIFY_KEY = os.environ.get("APIFY_API_KEY", "")
if not APIFY_KEY:
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("APIFY_API_KEY="):
                    APIFY_KEY = line.split("=", 1)[1].strip()
                    break

if not APIFY_KEY:
    print("APIFY_API_KEY introuvable. Mets-la dans .env ou variable d'env.")
    sys.exit(1)


def api_get(path):
    req = urllib.request.Request(
        f"https://api.apify.com/v2{path}",
        headers={"Authorization": f"Bearer {APIFY_KEY}"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def run_actor(payload, label=""):
    print(f"Lancement {label}...")
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs",
        data=data,
        headers={
            "Authorization": f"Bearer {APIFY_KEY}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        run = json.loads(r.read())

    run_id = run["data"]["id"]

    for i in range(30):
        time.sleep(5)
        r2 = urllib.request.Request(
            f"https://api.apify.com/v2/actor-runs/{run_id}",
            headers={"Authorization": f"Bearer {APIFY_KEY}"}
        )
        with urllib.request.urlopen(r2, timeout=15) as resp:
            st = json.loads(resp.read())
        s = st["data"]["status"]
        c = st["data"].get("usageTotalUsd", 0)
        items = st["data"]["stats"].get("results", 0)
        print(f"  [{i+1}] {s} - {items} items (${c:.4f})")
        if s in ("SUCCEEDED", "FAILED", "TIMEOUT", "ABORTED"):
            break

    if s != "SUCCEEDED":
        print(f"Echec: {s}")
        return []

    dataset_id = st["data"]["defaultDatasetId"]
    results = api_get(f"/datasets/{dataset_id}/items")
    total = st["data"]["stats"].get("results", len(results))
    print(f"OK {total} resultats, ${c:.4f}")
    return results


def build_payload(mode, value):
    base = {
        "resultsPerPage": 30,
        "proxyCountryCode": "None",
        "maxFollowersPerProfile": 0,
        "maxFollowingPerProfile": 0,
        "commentsPerPost": 0,
        "topLevelCommentsPerPost": 0,
        "maxRepliesPerComment": 0,
    }

    if mode == "search":
        base["searchQueries"] = [value]
        base["searchSection"] = ""
    elif mode == "hashtag":
        base["hashtags"] = [value]
    elif mode == "profile":
        base["profiles"] = [value]
        base["profileScrapeSections"] = ["videos"]
    elif mode == "video":
        base["postURLs"] = [value]
    elif mode == "followers":
        base["profiles"] = [value]
        base["profileScrapeSections"] = ["followers"]
        base["maxFollowersPerProfile"] = 50
    elif mode == "following":
        base["profiles"] = [value]
        base["profileScrapeSections"] = ["following"]
        base["maxFollowingPerProfile"] = 50
    else:
        print(f"Mode inconnu: {mode}")
        sys.exit(1)

    return base


def show_results(results, max_show=10):
    if not results:
        print("  (aucun resultat)")
        return

    print(f"\n{len(results)} videos recuperees:\n")
    for i, v in enumerate(results[:max_show]):
        author = v.get("authorMeta", {}).get("name", "?")
        text = v.get("text", "")[:80]
        plays = v.get("playCount", 0)
        likes = v.get("diggCount", 0)
        url = v.get("webVideoUrl", "")
        print(f"  {i+1}. @{author}")
        print(f"     {text}")
        print(f"     plays: {plays:,}  |  likes: {likes:,}")
        print(f"     {url}")
        print()

    if len(results) > max_show:
        print(f"  ... et {len(results) - max_show} de plus")

    cats = set()
    for v in results:
        ht = [h.get("name", "").lower() for h in v.get("hashtags", [])]
        txt = v.get("text", "").lower()
        if any(k in txt or k in ht for k in ["boeuf","beef","steak","burger"]):
            cats.add("Boeuf")
        if any(k in txt or k in ht for k in ["poulet","chicken","wing","breast"]):
            cats.add("Poulet")
        if any(k in txt or k in ht for k in ["porc","pork","bacon","ham"]):
            cats.add("Porc")
        if any(k in txt or k in ht for k in ["recette","recipe","cuisine","cook"]):
            cats.add("Recettes")
    print("\nCategories detectees:")
    for c in sorted(cats):
        print(f"  {c}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    mode = sys.argv[1]
    value = sys.argv[2]

    print(f"TikTok - {mode}: {value}")
    payload = build_payload(mode, value)
    results = run_actor(payload, label=f"TikTok {mode}")
    show_results(results)
