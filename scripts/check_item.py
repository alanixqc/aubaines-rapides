import json

with open('web/data/deals.json') as f:
    data = json.load(f)

cats = {}
for key in ['deals_with_kg', 'deals_wo_kg']:
    for item in data['deals'].get(key, []):
        c = item.get('category', '?')
        cats[c] = cats.get(c, 0) + 1
        
print("Categories:", json.dumps(cats, indent=2))
print(f"Total: {sum(cats.values())}")

# Show all yogurt items sorted by price
yogurts = []
for key in ['deals_with_kg', 'deals_wo_kg']:
    for item in data['deals'].get(key, []):
        if item.get('category') == 'yogourt':
            yogurts.append(item)

yogurts.sort(key=lambda x: (x.get('price') or 0))
print(f"\n🥛 Yogourt deals: {len(yogurts)}")
for y in yogurts:
    store = y.get('store', '?')
    price = y.get('price', 0)
    per_kg = y.get('per_kg')
    protein = y.get('protein_per_dollar')
    ptype = y.get('product_type', '?')
    name = y.get('name', '?')
    ppkg = f"{per_kg:.2f}$/kg" if per_kg else "—"
    pp = f"💪{protein}g/$" if protein else ""
    print(f"  {store:20s} | {name[:50]:50s} | {price:>6.2f}$ | {ppkg:12s} | {ptype} {pp}")
