"""build_site.py — Exporte la DB → JSON pour le site Aubaines Rapides
Version 3: ajoute store_url pour liens vers circulaire + flipp_item_id
"""
import json
import sqlite3
import os
import sys
import re
from collections import defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scripts.query import strip_accents, is_excluded, extract_weight_kg, find_default_weight, store_emoji, short_name

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "aubaines.db")
RECIPE_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "recipes.db")
WEB_DIR = os.path.join(os.path.dirname(__file__), "..", "web", "data")
os.makedirs(WEB_DIR, exist_ok=True)

# ─── URLs des circulaires par magasin ───
# Donne l'URL de la circulaire en ligne (site officiel ou Flipp)
STORE_URLS = {
    "Super C": "https://www.superc.ca/fr/online-grocery/current-offers/weekly-flyer",
    "Metro": "https://www.metro.ca/fr/circulaire",
    "IGA": "https://www.iga.net/fr/circulaire",
    "Maxi": "https://www.maxi.ca/fr/online-grocery/current-offers/weekly-flyer",
    "Provigo": "https://www.provigo.ca/fr/online-grocery/current-offers/weekly-flyer",
    "Walmart": "https://www.walmart.ca/fr/ads",
    "Costco": "https://www.costco.ca/warehouse-savings.html",
    "Tigre Géant": "https://www.tigregeant.ca/",
    "Adonis": "https://www.adonis.ca/fr/circulaires",
    "Kim Phat": "https://flipp.com/fr-ca/kim-phat-flyer",
    "Marché Tau": "https://flipp.com/fr-ca/marche-tau-flyer",
    "Les Marchés Tradition": "https://flipp.com/fr-ca/marches-tradition-flyer",
    "Mayrand": "https://flipp.com/fr-ca/mayrand-flyer",
    "Rachelle Béry": "https://flipp.com/fr-ca/rachelle-bery-flyer",
    "L'Inter-Marché": "https://flipp.com/fr-ca/inter-marche-flyer",
    "Supermarché Aurès": "https://flipp.com/fr-ca/aures-flyer",
    "Fruiterie Potager": "https://flipp.com/fr-ca/fruiterie-potager-flyer",
    "5 Saveurs": "https://flipp.com/fr-ca/5-saveurs-flyer",
    "Les aliments M&M": "https://flipp.com/fr-ca/m-m-flyer",
    "le Choix du Président": "https://flipp.com/fr-ca/president-s-choice-flyer",
}

POISSON_KW = ['saumon','crevette','poisson','thon','truite','morue','cabillaud','sole','tilapia',
              'espadon','flétan','maquereau','sardine','anchois','hareng','éperlan','dorade',
              'moule','palourde','crabe','homard','calmar','poulpe','crevettes','pétoncle',
              'fruits de mer','fish','shrimp','salmon','cod','tuna','seafood','sushi']
FRUIT_KW = ['pomme','banane','orange','raisin','bleuet','fraise','framboise','mûre','mure',
            'melon','pastèque','ananas','mangue','kiwi','pêche','poire','prune','cerise',
            'abricot','nectarine','clémentine','mandarine','pamplemousse','citron','lime',
            'limon','canneberge','airelle','fruit','apple','banana','orange','grape',
            'blueberry','strawberry','raspberry','mango','pineapple','watermelon']
CONSERVE_KW = ['conserve','canne','boîte','tin','lentille','pois chiche','haricot rouge',
               'haricot noir','soupe','tomate en','sauce tomate','pâtes alimentaires','riz ',
               'farine','sucre','huile','beurre d\'arachide','beurre de peanut','café',
               'thon en','maïs en','crevette en','compote','ketchup','moutarde','mayonnaise',
               'vinaigre','bouillon','cubes','épices','sel','poivre','gruau','céréale',
               'lait','beurre','œuf','oeuf','fromage','yogourt','yaourt','crème','pain']

PROTEIN_PER_100G = {
    "boeuf": {"haché maigre": 20, "haché": 17, "steak": 23, "rôti": 22, "cube": 20, "generic": 20},
    "poulet": {"poitrine": 25, "cuisse": 20, "aile": 18, "entier": 20, "haché": 20, "generic": 20},
    "porc": {"longe": 22, "côtelette": 20, "haché": 17, "rôti": 22, "generic": 20},
    "veau": {"haché": 18, "generic": 18},
    "poisson": {"saumon": 20, "thon": 23, "crevette": 20, "morue": 18, "generic": 18},
}


def classify_meat_type(name, current_mt):
    """Améliore la classification des types de viande/aliments."""
    name_lower = name.lower()
    for kw in POISSON_KW:
        if kw in name_lower:
            return "poisson"
    for kw in FRUIT_KW:
        if kw in name_lower:
            return "fruit"
    for kw in CONSERVE_KW:
        if kw in name_lower:
            return "panier"
    if current_mt in ("legume", "légume"):
        return "legume"
    return current_mt or "autre"


def clean_french_name(name):
    """Nettoie le nom pour garder seulement le français."""
    import re
    name = re.split(r'\s*\|\s*', name)[0]
    name = re.sub(r'\s*\([a-zA-Z]+\)', '', name)
    return name.strip().capitalize()


def estimate_protein_per_100g(name, meat_type):
    """Estime les protéines par 100g pour un produit."""
    name_lower = name.lower()
    if meat_type in PROTEIN_PER_100G:
        variants = PROTEIN_PER_100G[meat_type]
        for kw, val in variants.items():
            if kw in name_lower or kw in meat_type:
                return val
        return variants["generic"]
    return None


def get_store_url(store_name):
    """Retourne l'URL de la circulaire pour un magasin donné."""
    # Cherche correspondance exacte
    if store_name in STORE_URLS:
        return STORE_URLS[store_name]
    # Cherche correspondance partielle
    for key, url in STORE_URLS.items():
        if key.lower() in store_name.lower() or store_name.lower() in key.lower():
            return url
    # Fallback: recherche Flipp
    slug = store_name.lower().replace(" ", "-").replace("'", "-").replace("é","e").replace("è","e").replace("ê","e").replace("ô","o").replace("ç","c")
    return f"https://flipp.com/fr-ca/{slug}-flyer"


def get_recipe_link(meat_type, all_recipes):
    """Trouve une recette qui correspond au type de viande."""
    if meat_type not in all_recipes:
        return None
    mt_recipes = all_recipes[meat_type]
    if not mt_recipes:
        return None
    return mt_recipes[0]


def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def load_recipes():
    """Charge les recettes de la DB et les groupe par type de viande."""
    if not os.path.exists(RECIPE_DB_PATH):
        return {}
    conn = sqlite3.connect(RECIPE_DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT title, meat_type, source_name, source_url, rating_count, 
               rating, prep_time, cook_time, total_time, servings,
               ingredients_raw
        FROM recipes 
        WHERE ingredients_raw IS NOT NULL AND ingredients_raw != '[]'
        ORDER BY rating_count DESC
    """).fetchall()
    conn.close()
    
    by_meat = defaultdict(list)
    for r in rows:
        mt = r["meat_type"] or "mixte"
        try:
            ings = json.loads(r["ingredients_raw"])
            ing_count = len(ings)
        except:
            ings = []
            ing_count = 0
        
        by_meat[mt].append({
            "title": r["title"],
            "source": r["source_name"],
            "url": r["source_url"],
            "rating_count": r["rating_count"] or 0,
            "rating": r["rating"],
            "prep_time": r["prep_time"],
            "cook_time": r["cook_time"],
            "total_time": r["total_time"],
            "servings": r["servings"],
            "ingredient_count": ing_count,
        })
    
    # Limiter à top 5 par type
    for mt in by_meat:
        by_meat[mt] = sorted(by_meat[mt], key=lambda x: -x["rating_count"])[:5]
    
    return dict(by_meat)


def export_deals():
    """Exporte tous les deals avec classification enrichie + recettes + URLs."""
    db = get_db()
    max_week = db.execute("SELECT MAX(week_start) as w FROM price_history").fetchone()["w"]
    
    recipes_by_meat = load_recipes()
    
    rows = db.execute("""
        SELECT p.id, p.name, p.meat_type, p.package_weight_g,
               s.name as store, s.id as store_id,
               ph.price, ph.unit_price, ph.unit_type,
               ph.valid_to, ph.merchant_name, ph.image_url, ph.flipp_item_id
        FROM products p
        JOIN stores s ON s.id = p.store_id
        JOIN price_history ph ON ph.product_id = p.id
        WHERE ph.week_start = ? AND ph.price IS NOT NULL AND p.meat_type IS NOT NULL
        ORDER BY ph.price ASC
    """, (max_week,)).fetchall()
    
    seen_products = set()
    category_counts = defaultdict(int)
    store_set = set()
    deals = []
    
    for r in rows:
        if is_excluded(r["name"]):
            continue
        pk = (r["name"], r["merchant_name"])
        if pk in seen_products:
            continue
        seen_products.add(pk)

        mt = classify_meat_type(r["name"], r["meat_type"] or "autre")
        store_set.add(r["merchant_name"])
        category_counts[mt] += 1

        # $/kg
        per_kg = None
        source = None
        weight_kg = None
        
        if r["package_weight_g"] and r["price"]:
            weight_kg = r["package_weight_g"] / 1000
            per_kg = round(r["price"] / weight_kg, 2)
            source = "reel"
        elif r["unit_price"]:
            ut = r["unit_type"] or ""
            if "/kg" in ut:
                per_kg = round(r["unit_price"], 2)
                source = "image"
            elif "/100g" in ut:
                per_kg = round(r["unit_price"] * 10, 2)
                source = "image"
        if per_kg is None:
            w = extract_weight_kg(r["name"])
            if w and r["price"]:
                per_kg = round(r["price"] / w, 2)
                weight_kg = w
                source = "nom"
        if per_kg is None:
            w = find_default_weight(r["name"])
            if w and r["price"]:
                per_kg = round(r["price"] / w, 2)
                weight_kg = w
                source = "estime"
        
        per_lb = round(per_kg / 2.20462, 2) if per_kg else None
        
        # Protéines
        protein_per_100g = estimate_protein_per_100g(r["name"], mt) if mt in ["boeuf","porc","poulet","veau","poisson"] else None
        protein_per_dollar = None
        if protein_per_100g and per_kg:
            protein_per_dollar = round((protein_per_100g * 10) / per_kg, 1)
        
        # Recette liée
        recipe = None
        if mt in recipes_by_meat:
            recipe = get_recipe_link(mt, recipes_by_meat)
        
        # URL de la circulaire du magasin
        store_name = r["merchant_name"]
        store_url = get_store_url(store_name)
        
        deals.append({
            "id": r["id"],
            "name": clean_french_name(r["name"]),
            "name_short": short_name(clean_french_name(r["name"]), 40),
            "category": mt,
            "store": store_name,
            "store_id": r["store_id"],
            "store_emoji": store_emoji(store_name),
            "store_url": store_url,
            "price": round(r["price"], 2) if r["price"] else None,
            "per_kg": per_kg,
            "per_lb": per_lb,
            "weight_kg": weight_kg,
            "source": source,
            "valid_to": r["valid_to"],
            "image_url": r["image_url"],
            "flipp_item_id": r["flipp_item_id"],
            "protein_per_100g": protein_per_100g,
            "protein_per_dollar": protein_per_dollar,
            "recipe": recipe,
        })
    
    db.close()
    
    deals_with_kg = [d for d in deals if d["per_kg"]]
    deals_with_kg.sort(key=lambda x: (x["per_kg"] if x["per_kg"] and x["per_kg"] > 0 else 99999, x["price"] or 0))
    deals_wo_kg = [d for d in deals if not d["per_kg"]]
    deals_wo_kg.sort(key=lambda x: x["price"] or 0)
    
    return {
        "deals_with_kg": deals_with_kg,
        "deals_wo_kg": deals_wo_kg,
        "stats": {
            "total": len(deals),
            "by_category": dict(category_counts),
            "stores": sorted(store_set),
            "week": max_week,
            "generated_at": datetime.now().isoformat(),
        },
        "recipes_available": {mt: len(recs) for mt, recs in recipes_by_meat.items() if recs},
    }


def export_trends():
    db = get_db()
    rows = db.execute("""
        SELECT product, ref_date, value, uom
        FROM statcan_prices
        ORDER BY product, ref_date ASC
    """).fetchall()
    db.close()
    trends = defaultdict(list)
    for r in rows:
        trends[r["product"]].append({
            "date": r["ref_date"],
            "price": round(r["value"], 2),
            "unit": r["uom"],
        })
    return [{"product": p, "data": d} for p, d in sorted(trends.items())]


def export_products():
    db = get_db()
    max_week = db.execute("SELECT MAX(week_start) as w FROM price_history").fetchone()["w"]
    rows = db.execute("""
        SELECT DISTINCT p.name, p.meat_type, s.name as store,
               ph.price, ph.merchant_name, ph.valid_to, ph.image_url
        FROM products p
        JOIN stores s ON s.id = p.store_id
        JOIN price_history ph ON ph.product_id = p.id
        WHERE ph.week_start = ? AND ph.price IS NOT NULL AND p.meat_type IS NOT NULL
        ORDER BY p.name ASC
    """, (max_week,)).fetchall()
    db.close()
    products = []
    seen = set()
    for r in rows:
        if is_excluded(r["name"]):
            continue
        k = (r["name"], r["merchant_name"])
        if k in seen:
            continue
        seen.add(k)
        mt = classify_meat_type(r["name"], r["meat_type"] or "autre")
        store_name = r["merchant_name"]
        products.append({
            "name": r["name"],
            "name_short": short_name(r["name"], 50),
            "category": mt,
            "store": store_name,
            "store_emoji": store_emoji(store_name),
            "store_url": get_store_url(store_name),
            "price": round(r["price"], 2) if r["price"] else None,
            "valid_to": r["valid_to"],
            "image_url": r["image_url"],
        })
    return products


def export_stores():
    db = get_db()
    rows = db.execute("SELECT id, name, slug FROM stores ORDER BY name").fetchall()
    db.close()
    return [{
        "id": r["id"], "name": r["name"],
        "emoji": store_emoji(r["name"]), "slug": r["slug"],
        "store_url": get_store_url(r["name"])
    } for r in rows]


def export_recipes_top():
    """Exporte les meilleures recettes pour les afficher sur le site."""
    if not os.path.exists(RECIPE_DB_PATH):
        return []
    conn = sqlite3.connect(RECIPE_DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT title, meat_type, source_name, source_url, image_url, 
               rating, rating_count, prep_time, cook_time, total_time,
               servings, ingredients_raw, steps_raw
        FROM recipes 
        WHERE ingredients_raw IS NOT NULL AND ingredients_raw != '[]'
        ORDER BY rating_count DESC
        LIMIT 30
    """).fetchall()
    conn.close()
    recipes = []
    for r in rows:
        try:
            ings = len(json.loads(r["ingredients_raw"]))
        except:
            ings = 0
        try:
            steps = len(json.loads(r["steps_raw"]))
        except:
            steps = 0
        recipes.append({
            "title": r["title"],
            "meat_type": r["meat_type"],
            "source": r["source_name"],
            "url": r["source_url"],
            "image_url": r["image_url"],
            "rating": r["rating"],
            "rating_count": r["rating_count"] or 0,
            "prep_time": r["prep_time"],
            "cook_time": r["cook_time"],
            "total_time": r["total_time"],
            "servings": r["servings"],
            "ingredients_count": ings,
            "steps_count": steps,
        })
    return recipes


def main():
    print("🔨 Génération des données du site...")
    
    print("  📦 Deals...")
    deals = export_deals()
    with open(os.path.join(WEB_DIR, "deals.json"), "w", encoding="utf-8") as f:
        json.dump(deals, f, ensure_ascii=False, indent=2)
    print(f"    ✅ {deals['stats']['total']} deals exportés")
    
    print("  📈 Tendances...")
    trends = export_trends()
    with open(os.path.join(WEB_DIR, "trends.json"), "w", encoding="utf-8") as f:
        json.dump(trends, f, ensure_ascii=False, indent=2)
    print(f"    ✅ {len(trends)} séries temporelles")
    
    print("  🏪 Magasins...")
    stores = export_stores()
    with open(os.path.join(WEB_DIR, "stores.json"), "w", encoding="utf-8") as f:
        json.dump(stores, f, ensure_ascii=False, indent=2)
    print(f"    ✅ {len(stores)} magasins")
    
    print("  🍳 Recettes...")
    recipes = export_recipes_top()
    with open(os.path.join(WEB_DIR, "recipes.json"), "w", encoding="utf-8") as f:
        json.dump(recipes, f, ensure_ascii=False, indent=2)
    print(f"    ✅ {len(recipes)} recettes")
    
    print(f"\n✅ Données générées dans {WEB_DIR}")


if __name__ == "__main__":
    main()
