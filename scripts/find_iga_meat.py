#!/usr/bin/env python3
"""Va chercher TOUS les items viande IGA avec leurs URLs d'images"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scraper.flipp_scraper import FlippScraper, MEAT_KEYWORDS
import re

def is_meat(name):
    """Simple check si c'est de la viande"""
    name_lower = name.lower()
    exclude = [r'\bshampoo', r'\bchampignon', r'\bcantaloup', r'\btomate', r'\bburger bun',
               r'\bhot.dog', r'\bhamburger', r'\bmuffin', r'\bgâteau', r'\bmaïs\b',
               r'\bnourriture.*chien', r'\bbière', r'\bcafé', r'\bjus\b', r'\byogourt',
               r'\bcoca.cola', r'\bfromage', r'\bcrème glacée', r'\bbiscuit',
               r'\bchocolat', r'\bfriandise', r'\bbouffe congelée', r'\bplant',
               r'\bmélange.*crêpe', r'\bmélange.*gauffre', r'\bmélange.*gâteau',
               r'\btomate', r'\bmelon', r'\bkiwi', r'\bananas', r'\bfraise',
               r'\bboisson', r'\blaitue', r'\bpâte', r'\briz\b', r'\bvin\b',
               r'\bconserve', r'\bsauce', r'\bcrackers', r'\bsalade', r'\bcéréales',
               r'\bsoupe', r'\bjus\b', r'\bcafé\b', r'\bthé\b', r'\beau\b',
               r'\blotion', r'\bsavon', r'\bdétergent', r'\bnettoyant',
               r'\dcarton de lait\b', r'\bœufs?\b', r'\blait\b', r'\bcrème\b',
               r'\byogourt', r'\bfarce', r'\bcompote', r'\bpurée', r'\bpatate',
               r'\bpomme de terre', r'\boignon', r'\bail\b', r'\blégume',
               r'\bfruit', r'\blime', r'\bcitron', r'\borange', r'\bpamplemousse',
               r'\braisin', r'\bcoco', r'\bnoix', r'\bamande', r'\bcajou',
               r'\bpistache', r'\bgraine', r'\bharicot', r'\blentille',
               r'\bpois\b', r'\bmaïs\b', r'\bépinard', r'\bbrocoli',
               r'\bchou-fleur', r'\bchou\b', r'\bcarotte', r'\bcéleri',
               r'\bconcombre', r'\bpoivron', r'\bcourgette', r'\bcourge',
               r'\bavocat', r'\bpatate douce',]
    for pat in exclude:
        if re.search(pat, name_lower):
            return False, None
    
    for meat_type in ['boeuf', 'poulet', 'porc']:
        for kw in MEAT_KEYWORDS[meat_type]['fr'] + MEAT_KEYWORDS[meat_type]['en']:
            if len(kw.split()) >= 2:
                if kw in name_lower:
                    return True, meat_type
            else:
                if re.search(r'\b' + re.escape(kw) + r'\b', name_lower):
                    # Exceptions
                    if kw == 'haché' and not any(x in name_lower for x in ['boeuf', 'poulet', 'porc', 'beef', 'chicken', 'pork', 'veau', 'bison']):
                        if 'salade' in name_lower or 'tomate' in name_lower:
                            continue
                    return True, meat_type
    return False, None

s = FlippScraper()
flyers = s.get_flyers()
iga_flyers = [f for f in flyers if f.get("merchant") == "IGA"]

meat_items = []
for flyer in iga_flyers:
    items = s.get_flyer_items(flyer['id'], default_merchant="IGA")
    for item in items:
        name = item.get('name', '')
        is_m, m_type = is_meat(name)
        if is_m:
            meat_items.append({
                'flipp_id': item.get('id'),
                'name': name,
                'price': item.get('price'),
                'image_url': item.get('cutout_image_url'),
                'valid_from': item.get('valid_from', '')[:10],
                'valid_to': item.get('valid_to', '')[:10],
                'meat_type': m_type,
                'merchant': 'IGA'
            })

print(f"\n{'='*60}")
print(f"🥩 Items VIANDE IGA trouvés: {len(meat_items)}")
print(f"{'='*60}")
for i, item in enumerate(meat_items):
    print(f"\n[{i+1}] {item['name']}")
    print(f"    Type: {item['meat_type']} | Prix: ${item['price']} | ID: {item['flipp_id']}")
    print(f"    Image: {item['image_url']}")
    print(f"    Dates: {item['valid_from']} → {item['valid_to']}")

# Sauvegarder la liste pour usage
with open('/c/Users/Mark France/aubaines-rapides/data/iga_meat_items.json', 'w') as f:
    json.dump(meat_items, f, indent=2, ensure_ascii=False)
print(f"\n✅ Sauvegardé dans data/iga_meat_items.json")
