import sqlite3

import os
# Use Windows native path for Python (sqlite3 doesn't understand MSYS /c/ paths)
db = os.path.join(os.environ.get('USERPROFILE', 'C:/Users/Mark France'), 
                  "aubaines-rapides/data/aubaines.db")
print(f"DB path: {db}")
print(f"File exists: {os.path.isfile(db)}")
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
rows = conn.execute("""
    SELECT item_id, nom, marchand, categorie, prix_courant, poids_estime
    FROM items 
    WHERE marchand LIKE '%IGA%'
      AND poids_g IS NULL
    ORDER BY categorie
""").fetchall()
print(f"Total IGA items without weight: {len(rows)}")
for r in rows:
    print(f"  {r['item_id']:>10} | {r['categorie']:<8} | ${r['prix_courant']:<6} | estime={r['poids_estime']} | {r['nom']}")

# Also check the IGA items that DO have weight
rows2 = conn.execute("""
    SELECT item_id, nom, categorie, prix_courant, poids_g
    FROM items 
    WHERE marchand LIKE '%IGA%'
      AND poids_g IS NOT NULL
    ORDER BY categorie
""").fetchall()
print(f"\nIGA items WITH weight: {len(rows2)}")
for r in rows2[:15]:
    print(f"  {r['item_id']:>10} | {r['categorie']:<8} | ${r['prix_courant']:<6} | {r['poids_g']:>5}g | {r['nom']}")

# Total items per marchand
print("\n--- Items per marchand ---")
for r in conn.execute("SELECT marchand, COUNT(*), SUM(CASE WHEN poids_g IS NULL THEN 1 ELSE 0 END) as sans_poids FROM items GROUP BY marchand ORDER BY COUNT(*) DESC").fetchall():
    total = r['COUNT(*)']
    sans = r['sans_poids']
    pct = sans * 100 / total if total > 0 else 0
    print(f"  {r['marchand']:<25} {total:>5} items, {sans:>4} sans poids ({pct:.0f}%)")

conn.close()
