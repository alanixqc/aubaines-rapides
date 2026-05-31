"""Analyse quels items Tigre Géant ont des images vs pas."""
import json

with open(r'C:\Users\Mark France\aubaines-rapides\web\data\deals.json') as f:
    data = json.load(f)

deals = data.get('deals_with_kg', [])
tg_deals = [d for d in deals if d.get('store') == 'Tigre Géant']
with_image = [d for d in tg_deals if d.get('image_url')]
without_image = [d for d in tg_deals if not d.get('image_url')]

print(f'Total deals: {len(deals)}')
print(f'Tigre Géant deals: {len(tg_deals)}')
print(f'  Avec image: {len(with_image)}')
print(f'  Sans image: {len(without_image)}')
print()
print('Items sans image:')
for d in without_image:
    print(f'  - {d["name"]} (${d["price"]:.2f})')
