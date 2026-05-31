#!/usr/bin/env python3
"""Mini test: scrape 1 flyer IGA, vérifie que image_url est sauvé"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db.schema import get_db
from scraper.flipp_scraper import FlippScraper

s = FlippScraper()
flyers = s.get_flyers()
iga = [f for f in flyers if f.get("merchant") == "IGA"]

if not iga:
    print("❌ Aucun flyer IGA")
    sys.exit(1)

flyer = iga[0]
print(f"📄 Scraping IGA flyer #{flyer['id']}...")
items = s.get_flyer_items(flyer['id'], default_merchant="IGA")

print(f"   {len(items)} items dans la circulaire")

# Vérifier le premier item parsé
parsed = s.parse_item(items[0])
print(f"\n🔍 Premier item parsé:")
print(f"   name: {parsed['name']}")
print(f"   image_url: {parsed['image_url']}")
print(f"   flipp_item_id: {parsed['flipp_item_id']}")

# Sauvegarder 3 items pour tester
count = 0
for item in items[:3]:
    parsed = s.parse_item(item)
    if parsed:
        s.store_item(parsed)
        count += 1

print(f"\n✅ {count} item(s) sauvegardé(s)")

# Vérifier dans la DB
db = get_db()
row = db.execute(
    "SELECT image_url, flipp_item_id FROM price_history ORDER BY id DESC LIMIT 1"
).fetchone()
if row and row['image_url']:
    print(f"\n✅ DB contient image_url: {row['image_url'][:60]}...")
    print(f"✅ DB contient flipp_item_id: {row['flipp_item_id']}")
else:
    print(f"❌ image_url toujours NULL dans la DB!")
db.close()
