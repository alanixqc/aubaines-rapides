import json

with open('web/data/deals.json') as f:
    data = json.load(f)

cats = set()
for key in ['deals_with_kg', 'deals_wo_kg']:
    for item in data['deals'].get(key, []):
        cats.add(item.get('category'))
        
print("Categories:", sorted(cats))

for key in ['deals_with_kg', 'deals_wo_kg']:
    for item in data['deals'].get(key, []):
        if item.get('category') == 'yogourt':
            print(f"✅ YOGOURT: {item['name']} — {item.get('store')} — {item.get('price')}$")
        else:
            name = item.get('name','').lower()
            if any(kw in name for kw in ['yogourt','yaourt','yogurt','kéfir','kefir','skyr']):
                print(f"❌ MANQUÉ: {item['name']} — cat={item.get('category')}")
