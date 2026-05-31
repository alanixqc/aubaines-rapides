import json

with open('web/data/deals.json') as f:
    data = json.load(f)

items = data['deals']['deals_with_kg']

# Get item 53389 in full
targets = [38361, 53389, 53391]
for item in items:
    if item.get('id') in targets:
        print(f"=== ID {item['id']} ===")
        print(json.dumps(item, ensure_ascii=False, indent=2))
        print()
