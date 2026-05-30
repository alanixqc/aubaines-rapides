#!/usr/bin/env python3
"""Test rapide: va chercher les items IGA de Flipp et montre l'URL d'image"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scraper.flipp_scraper import FlippScraper

s = FlippScraper()
flyers = s.get_flyers()

# Trouver IGA
iga_flyers = [f for f in flyers if f.get("merchant") == "IGA"]
print(f"IGA flyers trouvés: {len(iga_flyers)}")
for f in iga_flyers:
    print(f"  Flyer #{f['id']}: {f.get('merchant')} - {f.get('title', 'N/A')}")
    items = s.get_flyer_items(f['id'], default_merchant="IGA")
    print(f"    {len(items)} items au total")
    
    # Montrer les 5 premiers items avec leur structure
    for i, item in enumerate(items[:5]):
        print(f"\n    Item #{i}:")
        # Afficher les champs clés
        for key in ['id', 'name', 'price', 'merchant', 'cutout_image_url', 'valid_from', 'valid_to']:
            val = item.get(key, 'N/A')
            print(f"      {key}: {val}")
    break  # juste un flyer IGA
