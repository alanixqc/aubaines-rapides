"""build_site.py — Exporte la DB → JSON pour le site Aubaines Rapides
Version 4: tout en français, zéro lien externe, image plein écran
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

# ─── Traductions anglais→français pour noms de produits ───
# Appliquées aux noms des circulaires qui n'ont pas de version française
EN_TO_FR_TRANSLATIONS = {
    # Marques / marqueurs de marque
    "great value": "Grande Valeur",
    "giant value": "Géant Valeur",
    "gold label": "Étiquette Or",
    "smokehouse": "Fumoir",
    "smoke house": "Fumoir",
    "maple lodge farms": "Fermes Maple Lodge",
    "la cage": "La Cage",
    "legacy": "Patrimoine",
    "levitt's": "Levitt",
    "old fashioned": "À l'Ancienne",
    "boston market": "Marché Boston",
    "high liner": "High Liner",
    "aqua star": "Aqua Star",
    "compliments": "Compliments",
    "janes": "Janes",
    "marcangelo": "Marcangelo",
    "le petit charcutier": "Le Petit Charcutier",

    # Viandes génériques
    "beef": "bœuf",
    "pork": "porc",
    "chicken": "poulet",
    "turkey": "dinde",
    "veal": "veau",
    "lamb": "agneau",
    "ham": "jambon",
    "bacon": "bacon",
    "sausage": "saucisse",
    "sausages": "saucisses",
    "sausage strips": "lanières de saucisses",
    "meat": "viande",
    "meatballs": "boulettes",
    "burgers": "burgers",
    "burger": "burger",
    "nuggets": "nuggets",
    "strips": "lanières",
    "fillets": "filets",
    "fillet": "filet",
    "cutlettes": "escalopes",
    "cutlet": "escalope",
    "tenderloin": "filet mignon",
    "tenderloins": "filets mignons",
    "loin chop": "côtelette de longe",
    "loin": "longe",
    "chops": "côtelettes",
    "steak": "steak",
    "steaks": "steaks",
    "roast": "rôti",
    "stew": "ragoût",
    "stewing": "à ragoût",
    "ground": "haché",
    "whole": "entier",
    "fresh": "frais",
    "boneless": "désossé",
    "skinless": "sans peau",
    "breast": "poitrine",
    "thigh": "cuisse",
    "thighs": "cuisses",
    "wings": "ailes",
    "drumstick": "pilons",
    "drumsticks": "pilons",
    "back": "dos",
    "side ribs": "côtes levées",
    "spare ribs": "côtes levées",
    "ribs": "côtes",
    "smoked": "fumé",
    "smoke": "fumé",
    "roasted": "rôti",
    "grilled": "grillé",
    "breaded": "pané",
    "frozen": "surgelé",
    "quick-peel": "décorticage rapide",
    "easy peel": "facile à décortiquer",
    "peeled": "décortiqué",
    "tail": "queue",
    "raw": "cru",
    "cooked": "cuit",
    "wild": "sauvage",
    "pacific": "du Pacifique",
    "white shrimp": "crevettes blanches",
    "shrimp": "crevettes",
    "salmon": "saumon",
    "boned": "désossé",
    "frenched": "parée",
    "barbecue style": "style barbecue",
    "bbq style": "style BBQ",
    "korean bbq style": "style BBQ coréen",
    "maple bourbon flavour": "saveur érable bourbon",
    "maple chipotle": "érable chipotle",
    "angus & cheddar beef burger": "burger bœuf Angus et cheddar",
    "beef & cheddar smashed burger": "burger bœuf et cheddar écrasé",
    "beef burger": "burger de bœuf",
    "beef burgers": "burgers de bœuf",
    "cheese": "fromage",
    "cheddar": "cheddar",
    "original": "original",
    "regular": "régulier",
    "lean": "maigre",
    "medium": "moyen",
    "smoked meat": "viande fumée",
    "montreal smoked": "fumé à Montréal",
    "english style": "style anglais",
    "market cuts": "morceaux du marché",
    "wild pacific salmon": "saumon sauvage du Pacifique",
    "boneless ham steak": "tranche de jambon désossée",
    "smokehouse boneless ham steak": "tranche de jambon désossée fumée",
    "pork loin chop": "côtelette de longe de porc",
    "pork tenderloins": "filets mignons de porc",
    "pork roast": "rôti de porc",
    "chicken strips": "lanières de poulet",
    "chicken nuggets": "nuggets de poulet",
    "chicken breast": "poitrine de poulet",
    "chicken thighs": "cuisses de poulet",
    "chicken wings": "ailes de poulet",
    "whole chicken": "poulet entier",
    "sweet & sour chicken": "poulet aigre-doux",
    "turkey breast": "poitrine de dinde",
    "beef pot roast": "rôti de bœuf braisé",
    "beef for chinese fondue": "bœuf pour fondue chinoise",
    "bag": "sac",
    "box": "boîte",
    "pack": "paquet",
    "tray": "plateau",
    "each": "chaque",
    "value": "valeur",
    "size": "format",
    "family size": "format familial",
    "party size": "format party",
    "twin pack": "double paquet",
    "2-pack": "double",
    "6-pack": "6 unités",
    "8-pack": "8 unités",
    "10-pack": "10 unités",
    "12-pack": "12 unités",
    "smashhouse": "Smashhouse",
    "angus": "Angus",
    "gsm": "GSM",
    "beef": "bœuf",
    "shrimp": "crevettes",
    "sausage": "saucisse",
    "sausages": "saucisses",
    "fillets": "filets",
    "nuggets": "nuggets",
    "smoked": "fumé",
    "steak": "steak",
    "burger": "burger",
    "burgers": "burgers",
    "bacon": "bacon",
    "frozen": "surgelé",
    "whole": "entier",
    "juice": "jus",
    "sweet": "sucré",
    "white": "blanc",
    "pacific": "du Pacifique",
    "wild": "sauvage",
}

# Recettes — traduction français + URL française
RECIPE_FRENCH = {
    "Classic Beef Chili": {
        "title_fr": "Chili classique au bœuf",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/5762-chili-classique-au-boeuf"
    },
    "Chicken Chili Verde": {
        "title_fr": "Chili vert au poulet",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/5764-chili-vert-au-poulet"
    },
    "Three-Bean and Pork Chili": {
        "title_fr": "Chili au porc et trois haricots",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/6037-chili-au-porc-et-trois-haricots"
    },
    "Classic Chili": {
        "title_fr": "Chili classique",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Cheddar Cheese Meatloaf": {
        "title_fr": "Pain de viande au cheddar",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Swedish Meatballs": {
        "title_fr": "Boulettes suédoises",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Meatball and Pigs' Feet Stew": {
        "title_fr": "Ragoût de boulettes et pieds de porc",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Clemence's Meatloaf": {
        "title_fr": "Pain de viande de Clémence",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Meatballs in Tomato Sauce (The Best)": {
        "title_fr": "Meilleures boulettes à la sauce tomate",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Childhood Meatballs": {
        "title_fr": "Boulettes d'enfance",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Braised Beef and Oka Cheese Shepherd's Pie": {
        "title_fr": "Pâté chinois au bœuf braisé et fromage Oka",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Pâté Chinois (Shepherd's Pie)": {
        "title_fr": "Pâté chinois",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Shepherd's Pie with Cheese Curd (Pâté Chinois)": {
        "title_fr": "Pâté chinois au fromage en grains",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Sausage Shepherd's Pie": {
        "title_fr": "Pâté chinois aux saucisses",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "White Meatloaf with Mushroom Sauce": {
        "title_fr": "Pain de viande blanc à la sauce aux champignons",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Veal and Parmesan-Stuffed Zucchini": {
        "title_fr": "Courgettes farcies au veau et parmesan",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Texan-Style Shepherd's Pie": {
        "title_fr": "Pâté chinois texan",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Veal Meatballs": {
        "title_fr": "Boulettes de veau",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Meatball and Spaghetti Squash Soup": {
        "title_fr": "Soupe de boulettes et courge spaghetti",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Extra-Tender Pork Meatballs": {
        "title_fr": "Boulettes de porc extra-tendres",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Hamburger Steak with Onions and Balsamic Vine": {
        "title_fr": "Steak Hamburg aux oignons et vinaigre balsamique",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Hamburger-Flavoured Soup": {
        "title_fr": "Soupe saveur hamburger",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Sweet and Sour Chicken Meatballs": {
        "title_fr": "Boulettes de poulet aigre-douces",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Stuffed Zucchini Au Gratin": {
        "title_fr": "Courgettes farcies au gratin",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Slow Cooker Bolognese Sauce": {
        "title_fr": "Sauce bolognaise à la mijoteuse",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Pork Meatballs with Roasted Peppers and Barbe": {
        "title_fr": "Boulettes de porc aux poivrons rôtis et BBQ",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Pork Meatballs with Squash in a Cream Sauce": {
        "title_fr": "Boulettes de porc à la courge et sauce crème",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Tofu and Veal Meatloaves with Barbecue Sauce": {
        "title_fr": "Pains de viande au tofu et veau, sauce BBQ",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Bolognese Sauce (The Best)": {
        "title_fr": "Meilleure sauce bolognaise",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Mushroom Bolognese Lasagna": {
        "title_fr": "Lasagne bolognaise aux champignons",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Beer Chili": {
        "title_fr": "Chili à la bière",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Maple Lodge Farms Originale Saucisses Fumées De Poulet": {
        "title_fr": "Saucisses fumées de poulet originales Maple Lodge Farms",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
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


def translate_product_name(name):
    """Traduit un nom de produit anglais vers français.
    Utilise la table EN_TO_FR pour remplacer les termes anglais par leur équivalent français.
    """
    name_lower = name.lower().strip()
    original = name
    
    # Appliquer les traductions de la plus longue à la plus courte
    # pour éviter les substitutions partielles (ex: "beef" dans "beef burgers" vs "beef")
    sorted_terms = sorted(EN_TO_FR_TRANSLATIONS.keys(), key=len, reverse=True)
    
    for term in sorted_terms:
        if term in name_lower:
            replacement = EN_TO_FR_TRANSLATIONS[term]
            # Case-insensitive replacement preserving original's case pattern
            name_lower = name_lower.replace(term, replacement)
    
    # Capitaliser la première lettre
    if name_lower:
        name_lower = name_lower[0].upper() + name_lower[1:]
    
    # Nettoyer les espaces multiples
    name_lower = re.sub(r'\s+', ' ', name_lower).strip()
    
    return name_lower


def clean_french_name(name):
    """Nettoie le nom pour garder seulement le français.
    Gère: 'FRENCH | ENGLISH', 'FRENCH │ ENGLISH', et les noms 100% anglais.
    """
    # Split sur | ou │ (Unicode BOX DRAWINGS)
    name = re.split(r'\s*[│|]\s*', name)[0]
    # Enlever les parenthèses anglaises
    name = re.sub(r'\s*\([a-zA-Z\s]+\)', '', name)
    name = name.strip()
    
    if not name:
        return ""
    
    # Mettre le nom en minuscules sauf première lettre
    # pour éviter les noms en MAJUSCULES des circulaires
    name = name.lower()
    name = name[0].upper() + name[1:] if len(name) > 1 else name
    
    # Vérifier si le nom contient encore des mots anglais
    name_lower = name.lower()
    english_terms = {'beef','pork','chicken','turkey','ham','bacon','sausage','steak','roast',
                     'grill','fried','frozen','fresh','boneless','breast','thigh','wings',
                     'ground','whole','smoked','loin','chops','strips','nuggets','fillets',
                     'shrimp','salmon','value','original','regular','smokehouse','tenderloin',
                     'burger','burgers','boston','market','gold','label','smoke','house',
                     'giant','pack','butcher','strip','recipe','dinner','meal','kit','house',
                     'style','bbq','grill','aged','lean'}
    
    words = set(re.findall(r'[a-zA-Z]+', name_lower))
    eng_word_count = sum(1 for w in words if w in english_terms)
    
    if eng_word_count >= 2:
        name = translate_product_name(name)
    
    # Nettoyage final: enlever les mots anglais redondants après du français
    # ex: "MERGUEZ DE BOEUF BEEF" → "Merguez de bœuf"
    # ex: "Jambon fumé Le Petit Charcutier smoked" → "Jambon fumé Le Petit Charcutier"
    name_lower2 = name.lower()
    french_before_english = [
        (r'\bboeuf\b\s+beef\b', 'bœuf'),
        (r'\bbœuf\b\s+beef\b', 'bœuf'),
        (r'\bpoulet\b\s+chicken\b', 'poulet'),
        (r'\bporc\b\s+pork\b', 'porc'),
        (r'\bfumé\b\s+smoked\b', 'fumé'),
        (r'\bfume\b\s+smoked\b', 'fumé'),
        (r'\bjambon\b\s+ham\b', 'jambon'),
        (r'\bsaucisse\b\s+sausage\b', 'saucisse'),
        (r'\bsteak\b\s+steak\b', 'steak'),
        (r'\bdinde\b\s+turkey\b', 'dinde'),
    ]
    for pattern, replacement in french_before_english:
        if re.search(pattern, name_lower2, re.IGNORECASE):
            name = re.sub(pattern, replacement, name, flags=re.IGNORECASE)
    
    # Nettoyage: si "smoked" est présent et que "fumé" est aussi présent (pas adjacent),
    # enlever "smoked" (redondant)
    for eng_word, fr_word in [('smoked','fumé'), ('smoked','fume'), ('beef','boeuf'), ('beef','bœuf'),
                               ('pork','porc'), ('chicken','poulet'), ('ham','jambon'),
                               ('sausage','saucisse'), ('turkey','dinde')]:
        if eng_word in name_lower2 and fr_word in name_lower2:
            # Enlever le mot anglais redondant
            name = re.sub(r'\s*' + re.escape(eng_word) + r'\b', '', name, flags=re.IGNORECASE).strip()
    
    # Capitaliser proprement: première lettre en maj, le reste en min (sauf acronymes)
    # Sauf si c'est un nom de marque connu en majuscules
    name = name[0].upper() + name[1:] if len(name) > 1 else name
    
    return name


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


def translate_recipe(recipe):
    """Traduit une recette en français si elle est dans la table."""
    if not recipe:
        return recipe
    
    title = recipe.get("title", "")
    if title in RECIPE_FRENCH:
        fr = RECIPE_FRENCH[title]
        return {
            **recipe,
            "title": fr["title_fr"],
            "url": fr["url_fr"],
        }
    
    # Si titre anglais non trouvé dans la table, tenter de franciser l'URL
    url = recipe.get("url", "")
    if "/en/" in url:
        recipe["url"] = url.replace("/en/recipes/", "/fr/recettes/")
        # Traduire quelques titres courants par pattern
        recipe["title"] = recipe["title"].replace("Chicken", "Poulet").replace("Beef", "Bœuf").replace("Pork", "Porc").replace("Veal", "Veau")
    
    return recipe


def get_recipe_link(meat_type, all_recipes):
    """Trouve une recette qui correspond au type de viande et la traduit."""
    if meat_type not in all_recipes:
        return None
    mt_recipes = all_recipes[meat_type]
    if not mt_recipes:
        return None
    # Traduire la recette en français
    return translate_recipe(mt_recipes[0])


def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def load_recipes():
    """Charge les recettes de la DB et les groupe par type de viande.
    Traduit les titres et URLs en français.
    """
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
        
        recipe = {
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
        }
        
        # Traduire la recette en français
        recipe = translate_recipe(recipe)
        
        by_meat[mt].append(recipe)
    
    # Limiter à top 5 par type
    for mt in by_meat:
        by_meat[mt] = sorted(by_meat[mt], key=lambda x: -x["rating_count"])[:5]
    
    return dict(by_meat)


def export_deals():
    """Exporte tous les deals avec classification enrichie + recettes traduites."""
    db = get_db()
    max_week = db.execute("SELECT MAX(week_start) as w FROM price_history").fetchone()["w"]
    
    recipes_by_meat = load_recipes()
    
    rows = db.execute("""
        SELECT p.id, p.name, p.meat_type, p.package_weight_g,
               s.name as store, s.id as store_id,
               ph.price, ph.unit_price, ph.unit_type,
               ph.valid_to, ph.merchant_name, ph.image_url
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
        
        # Recette liée (traduite en français)
        recipe = None
        if mt in recipes_by_meat:
            recipe = get_recipe_link(mt, recipes_by_meat)
        
        # Nom du produit nettoyé et traduit
        store_name = r["merchant_name"]
        clean_name = clean_french_name(r["name"])
        
        deals.append({
            "id": r["id"],
            "name": clean_name,
            "name_short": short_name(clean_name, 40),
            "category": mt,
            "store": store_name,
            "store_id": r["store_id"],
            "store_emoji": store_emoji(store_name),
            "price": round(r["price"], 2) if r["price"] else None,
            "per_kg": per_kg,
            "per_lb": per_lb,
            "weight_kg": weight_kg,
            "source": source,
            "valid_to": r["valid_to"],
            "image_url": r["image_url"],
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
        clean_name = clean_french_name(r["name"])
        products.append({
            "name": clean_name,
            "name_short": short_name(clean_name, 50),
            "category": mt,
            "store": store_name,
            "store_emoji": store_emoji(store_name),
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
    } for r in rows]


def export_recipes_top():
    """Exporte les meilleures recettes pour les afficher sur le site (traduites)."""
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
        
        recipe = {
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
        }
        
        # Traduire
        recipe = translate_recipe(recipe)
        
        recipes.append(recipe)
    return recipes


def main():
    print("🔨 Génération des données du site...")
    
    print("  📦 Deals (traduction française)...")
    deals = export_deals()
    with open(os.path.join(WEB_DIR, "deals.json"), "w", encoding="utf-8") as f:
        json.dump(deals, f, ensure_ascii=False, indent=2)
    print(f"    ✅ {deals['stats']['total']} deals exportés, noms en français")
    
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
    
    print("  🍳 Recettes (traduction française)...")
    recipes = export_recipes_top()
    with open(os.path.join(WEB_DIR, "recipes.json"), "w", encoding="utf-8") as f:
        json.dump(recipes, f, ensure_ascii=False, indent=2)
    print(f"    ✅ {len(recipes)} recettes en français")
    
    print(f"\n✅ Données générées dans {WEB_DIR}")


if __name__ == "__main__":
    main()
