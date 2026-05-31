import sqlite3, json, sys, re
sys.path.insert(0, 'scripts')
from build_site import RECIPE_FRENCH

conn = sqlite3.connect('data/recipes.db')
conn.row_factory = sqlite3.Row
rows = conn.execute("""
    SELECT title FROM recipes 
    WHERE ingredients_raw IS NOT NULL AND ingredients_raw != '[]' 
    ORDER BY rating_count DESC LIMIT 30
""").fetchall()
conn.close()

for r in rows:
    t = r['title']
    found = t in RECIPE_FRENCH
    print(f"{'✅' if found else '❌'} {repr(t)[:80]}", end="")
    if found:
        print(f" → {RECIPE_FRENCH[t]['title_fr'][:40]}")
    else:
        print(" — MANQUE")
