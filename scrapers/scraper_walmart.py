#!/usr/bin/env python3
"""Scraper Walmart Canada — via l'API Flipp (flyers-ng.flippback.com)
   Remplacent l'approche Playwright bloquée par PerimeterX."""

import sys, os, json, random, argparse, re
from datetime import datetime, date, timedelta

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db.schema import get_db

FLIPP_API = "https://flyers-ng.flippback.com/api/flipp"
LOCALE = "fr"
POSTAL = "J7Y4A2"
MERCHANT_NAME = "Walmart"

MEAT_KW = [
    "boeuf", "bœuf", "poulet", "porc", "bacon", "jambon", "steak",
    "haché", "hache", "côtelette", "cotelette", "saucisse", "viande",
    "poitrine", "cuisse", "filet", "rôti", "roti", "dinde", "veau",
    "agneau", "burger", "boulette", "bifteck", "surlonge", "aile",
    "pilons", "drumstick", "brochette", "souvlaki", "côte", "cote",
    "longe",
]

EXCLUDE = [
    "chien", "chat", "purina", "whiskas", "friskies", "pedigree",
    "bouillon", "gâterie", "gaterie", "treat", "nourriture sèche",
    "dog", "cat", "pet",
]


def classify_meat(name):
    n = name.lower()
    for ex in EXCLUDE:
        if ex in n:
            return None
    for kw in ["bœuf", "boeuf", "veau"]:
        if kw in n:
            return "boeuf"
    for kw in ["poulet", "dinde", "volaille"]:
        if kw in n:
            return "poulet"
    for kw in ["porc", "bacon", "jambon", "côtelette", "cotelette",
               "saucisse", "longe", "côte", "cote"]:
        if kw in n:
            return "porc"
    return None


def short_name(name, maxlen=40):
    if len(name) > maxlen:
        return name[:maxlen] + "…"
    return name


def main():
    parser = argparse.ArgumentParser(description="Walmart Meat Scraper (Flipp API)")
    parser.add_argument("--save", action="store_true", help="Save to JSON")
    parser.add_argument("--output", help="Custom output path")
    parser.add_argument("--db", action="store_true", help="Insert into DB")
    parser.add_argument("--json", action="store_true", help="Print JSON to stdout")
    args = parser.parse_args()

    sid = "".join(random.choices("0123456789", k=16))
    session = requests.Session()

    # 1. Get all flyers
    resp = session.get(
        f"{FLIPP_API}/data?locale={LOCALE}&postal_code={POSTAL}&sid={sid}",
        timeout=30,
    )
    data = resp.json()
    flyers = [f for f in data.get("flyers", []) if f.get("merchant") == MERCHANT_NAME]

    print(f"📡 {len(flyers)} circulaires pour {MERCHANT_NAME}", file=sys.stderr)

    all_meat = []
    for flyer in flyers:
        fid = flyer["id"]
        items = session.get(
            f"{FLIPP_API}/flyers/{fid}/flyer_items?locale={LOCALE}&sid={sid}",
            timeout=30,
        ).json()

        for item in items:
            name = (item.get("name") or "").strip()
            price_text = str(item.get("price") or "")
            meat_type = classify_meat(name)
            if not meat_type:
                continue

            try:
                price = float(price_text)
            except (ValueError, TypeError):
                continue

            all_meat.append({
                "name": name,
                "price": price,
                "merchant_name": MERCHANT_NAME,
                "meat_type": meat_type,
                "image_url": item.get("cutout_image_url", ""),
                "valid_from": item.get("valid_from", ""),
                "valid_to": item.get("valid_to", ""),
                "flipp_item_id": item.get("id"),
                "flyer_id": fid,
            })

    print(f"🥩 {len(all_meat)} items viande extraits", file=sys.stderr)
    for m in all_meat[:10]:
        print(f"   {m['meat_type']:6s} | {short_name(m['name'], 45)} | {m['price']:.2f}$", file=sys.stderr)

    output = {
        "store": MERCHANT_NAME,
        "scraped_at": datetime.now().isoformat(),
        "total_meat": len(all_meat),
        "products": all_meat,
    }

    # Save file
    if args.save or args.output:
        out_path = args.output or os.path.join(
            os.path.dirname(__file__), "..", "data", "walmart_products.json"
        )
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"💾 Saved: {out_path}", file=sys.stderr)

    # DB insert
    if args.db:
        db = get_db()
        row = db.execute("SELECT id FROM stores WHERE slug = ? OR name = ?",
                          ("walmart", MERCHANT_NAME)).fetchone()
        if row:
            store_id = row["id"]
        else:
            db.execute("INSERT INTO stores (name, slug) VALUES (?, ?)", (MERCHANT_NAME, "walmart"))
            db.commit()
            store_id = db.execute("SELECT id FROM stores ORDER BY id DESC LIMIT 1").fetchone()["id"]

        max_week = db.execute("SELECT MAX(week_start) as w FROM price_history").fetchone()["w"]
        week_start = max_week or (date.today() - timedelta(days=date.today().weekday())).isoformat()

        inserted = 0
        for mp in all_meat:
            row = db.execute(
                "SELECT id FROM products WHERE name = ? AND store_id = ?",
                (mp["name"], store_id),
            ).fetchone()
            if row:
                pid = row["id"]
            else:
                db.execute(
                    "INSERT INTO products (name, store_id, meat_type) VALUES (?, ?, ?)",
                    (mp["name"], store_id, mp["meat_type"]),
                )
                db.commit()
                pid = db.execute("SELECT id FROM products ORDER BY id DESC LIMIT 1").fetchone()["id"]

            valid_to_d = mp["valid_to"][:10] if mp["valid_to"] else None
            db.execute(
                """INSERT INTO price_history
                   (product_id, price, week_start, merchant_name, image_url,
                    valid_to, flipp_item_id, scanned_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                (pid, mp["price"], week_start, MERCHANT_NAME,
                 mp["image_url"], valid_to_d, mp["flipp_item_id"]),
            )
            inserted += 1

        db.commit()
        db.close()
        print(f"💾 DB: {inserted} produits Walmart insérés", file=sys.stderr)

    if args.json:
        print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
