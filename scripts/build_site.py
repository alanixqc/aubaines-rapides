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
    # Plus de termes manquants (Super C)
    "marrow": "moelle",
    "soup": "soupe",
    "bones": "os",
    "grain fed": "nourri au grain",
    "grain-fed": "nourri au grain",
    "fed": "nourri au grain",
    "liver": "foie",
    "slices": "tranches",
    "quarter": "quartier",
    "quarters": "quartiers",
    "hocks": "jarrets",
    "belly": "poitrine",
    "rack of": "râble de",
    "shank": "jarret",
    "tenderized": "attendri",
    "tenderized": "attendri",
    "seasonned": "assaisonné",
    "seasoned": "assaisonné",
    "french steak": "steak français",
    "french": "français",
    "inside round": "intérieur de ronde",
    "sandwich": "sandwich",
    "setwich": "sandwich",
    "osso buco": "osso buco",
    "giant value": "Géant Valeur",
    "lean": "maigre",
    "medium": "moyen",
    "diced": "en dés",
    "cubes": "cubes",
    "prepared": "préparé",
    "strips": "lanières",
    "frenched": "paré",
    "marinated": "mariné",
    "seasoned": "assaisonné",
    "seasoning": "assaisonnement",
    "garlic": "ail",
    "herb": "herbes",
    "herbs": "herbes",
    "spices": "épices",
    "pepper": "poivre",
    "butter": "beurre",
    "cream": "crème",
    "onion": "oignon",
    "hot dog": "hot dog",
    "weiners": "saucisses",
    "smokies": "saucisses fumées",
    "kolbassa": "kolbassa",
    "kielbassa": "kielbassa",
    "pepperoni": "pepperoni",
    "salami": "salami",
    "prosciutto": "prosciutto",
    "curd": "grains",
    "cheese curds": "fromage en grains",
    "3-pepper": "3 poivres",
    "three-pepper": "3 poivres",
    "peppered": "aux poivres",
    "portuguese": "portugais",
    "bbq": "BBQ",
    "bbq cut": "coupe BBQ",
    "bbq style": "style BBQ",
    "bone-in": "avec os",
    "boneless": "désossé",
    "skinless": "sans peau",
    "without skin": "sans peau",
    "loin": "longe",
    "sirloin": "surlonge",
    "rib": "côte",
    "ribeye": "entre-côte",
    "picanha": "picanha",
    "t-bone": "T-bone",
    "porterhouse": "porterhouse",
    "chuck": "paleron",
    "flank": "flanc",
    "round": "rondelle",
    "rump": "cuisse",
    "blade": "palette",
    "shoulder": "épaule",
    "knuckle": "gîte",
    "cutlet": "escalope",
    "stewing": "à ragoût",
    "stir fry": "pour sauté",
    "saute": "pour sauté",
    "stir": "pour sauté",
    "ground": "haché",
    "mince": "haché",
    "sausage": "saucisse",
    "sausages": "saucisses",
    "stew": "ragoût",
    "roast": "rôti",
    "basted": "brossé",
    "crispy": "croustillant",
    "breaded": "pané",
    "battered": "enrobe",
    "broiled": "grillé au four",
    "grilled": "grillé",
    "pan": "à la poêle",
    "deep": "frite",
    "shallow": "frite légère",
    "charcoal": "au charbon",
    "stovetop": "sur la cuisinière",
    "baked": "au four",
    "roasted": "rôti",
    "cooked": "cuit",
    "raw": "cru",
    "fresh": "frais",
    "frozen": "surgelé",
    "smoked": "fumé",
    "boneless": "désossé",
    "boneless": "désossé",
    "regular": "régulier",
    "original": "original",
    "gold label": "Étiquette Or",
    "giant value": "Géant Valeur",
    "great value": "Grande Valeur",
    "value pack": "paquet de valeur",
    "combo pack": "combo",
    "family size": "format familial",
    "party size": "format fête",
    "twin pack": "double paquet",
    "3-pack": "3 unités",
    "4-pack": "4 unités",
    "5-pack": "5 unités",
    "6-pack": "6 unités",
    "8-pack": "8 unités",
    "10-pack": "10 unités",
    "12-pack": "12 unités",
    "with": "avec",
    "without": "sans",
    # NOTE: "for", "and", "in", "of", "at" etc. (mots ≤3 lettres) NE DOIVENT PAS être ici —
    # ils matchent à l'intérieur de mots plus longs ("for" dans "forêt" → "pouret", "in" dans "grain" → "graen")
    # Utiliser le word-boundary post-processing dans translate_product_name() à la place
    # Termes manquants (juin 2026) — ajoutés après avoir trouvé 81 noms encore en anglais sur le site
    "kidneys": "rognons",
    "kidney": "rognon",
    "hearts": "cœurs",
    "heart": "cœur",
    "tongue": "langue",
    "tripe": "tripes",
    "gizzards": "gésiers",
    "gizzard": "gésier",
    "sliced": "tranché",
    "slice": "tranche",
    "chops": "côtelettes",
    "chop": "côtelette",
    "hotel cut": "coupe hôtel",
    "hotel style": "style hôtel",
    "honey": "miel",
    "honey garlic": "miel et ail",
    "lemon pepper": "citron poivre",
    "lemon herb": "citron et herbes",
    "knife cut": "coupe au couteau",
    "cook from": "à cuire",
    "legs": "cuisses",
    "leg": "cuisse",
    "back attached": "dos attaché",
    "tip": "pointe",
    "spice": "épices",
    "montreal spice": "épices Montréal",
    "montreal steak spice": "épices à steak Montréal",
    "montreal smoked meat": "viande fumée Montréal",
    "smoked meat": "viande fumée",
    "corned beef": "bœuf salé",
    "pastrami": "pastrami",
    "kielbasa": "kielbasa",
    "smokies": "saucisses fumées",
    "bangers": "bangers",
    "maple": "érable",
    "apple": "pomme",
    "cherry": "cerise",
    "peach": "pêche",
    "mango": "mangue",
    "pineapple": "ananas",
    "orange": "orange",
    "lemon": "citron",
    "lime": "lime",
    "veal liver": "foie de veau",
    "beef liver": "foie de bœuf",
    "pork liver": "foie de porc",
    "chicken liver": "foie de poulet",
    "attached": "attaché",
    "seared": "saisi",
    "sautéed": "sauté",
    "sauté": "sauté",
    "glazed": "glaçé",
    "marinated": "mariné",
    "stuffed": "farcie",
    "organic": "bio",
    "halal": "halal",
    "kosher": "kasher",
    "free range": "plein air",
    "free-range": "plein air",
    "grain fed": "nourri au grain",
    "grain-fed": "nourri au grain",
    "grass fed": "nourri à l'herbe",
    "grass-fed": "nourri à l'herbe",
    "air chilled": "refroidi à l'air",
    "air-chilled": "refroidi à l'air",
    "never frozen": "jamais surgelé",
    "fresh never frozen": "frais jamais surgelé",
    "hotel-style": "style hôtel",
    "hotel cut": "coupe hôtel",
    "bbq sauce": "sauce BBQ",
    "blood pudding": "boudin",
    "shaved": "émincé",
    "shaved steak": "steak émincé",
    "top sirloin": "haut de surlonge",
    "three pepper": "3 poivres",
    "three-pepper": "3 poivres",
    "wine": "vin",
    "shallots": "échalotes",
    "steakhouse": "steakhouse",
    "striploin": "contre-filet",
    "striplonge": "contre-filet",
    "inside": "intérieur",
    # Corrections de traductions erronées
    "nourri au grain": "nourri au grain",  # verrou: empêche le re-remplacement par erreur

    # ─── Traductions de phrases complètes (AVANT les mots atomiques) ───
    # L'ordre des mots anglais (adj+adj+noun) diffère du français (noun+adj+adj)
    # Ces phrases doivent matcher AVANT les mots individuels pour éviter
    # "Moyen haché boeuf" au lieu de "Boeuf haché mi-maigre"
    "extra lean ground beef, value pack": "boeuf haché extra maigre, paquet de valeur",
    "extra lean ground beef": "boeuf haché extra maigre",
    "lean ground beef, value pack": "boeuf haché maigre, paquet de valeur",
    "lean ground beef": "boeuf haché maigre",
    "medium ground beef, value pack": "boeuf haché mi-maigre, paquet de valeur",
    "medium ground beef": "boeuf haché mi-maigre",
    # Porc: même problème d'ordre des mots
    "extra lean ground pork, value pack": "porc haché extra maigre, paquet de valeur",
    "extra lean ground pork": "porc haché extra maigre",
    "lean ground pork, value pack": "porc haché maigre, paquet de valeur",
    "lean ground pork": "porc haché maigre",
    "medium ground pork": "porc haché mi-maigre",
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
    "Hamburger Steak with Onions": {
        "title_fr": "Steak hamburger aux oignons",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Hamburger Steak with Onions and Balsamic Vinegar": {
        "title_fr": "Steak hamburger aux oignons",
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
    "Braised Beef and Oka Cheese Shepherd's Pie": {
        "title_fr": "Pâté chinois au bœuf braisé et fromage Oka",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Shepherd's Pie with Cheese Curd (Pâté Chinois)": {
        "title_fr": "Pâté chinois au fromage en grains",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Pork Meatballs with Roasted Peppers and Barbecue Sauce": {
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
    "Ground Pork and Shrimp Ramen Soup": {
        "title_fr": "Soupe ramen au porc haché et crevettes",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Two-Bean Chili": {
        "title_fr": "Chili aux deux haricots",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Risotto with Ground Veal, Spinach and Roasted Tomatoes": {
        "title_fr": "Risotto au veau haché, épinards et tomates rôties",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Spaghetti Bolognese Sauce": {
        "title_fr": "Sauce bolognaise pour spaghetti",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Indian-Spiced Chili": {
        "title_fr": "Chili aux épices indiennes",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Bolognese Sauce": {
        "title_fr": "Sauce bolognaise",
        "url_fr": "https://www.ricardocuisine.com/fr/recettes/"
    },
    "Veal Cocktail Meatballs": {
        "title_fr": "Boulettes cocktail de veau",
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
               'thon en','maïs en','crevette en','compote',
               'vinaigre','bouillon','cubes','épices','sel','poivre','gruau','céréale',
               'lait','beurre','œuf','oeuf','fromage','crème','pain']

SAUCE_KW = ['ketchup','moutarde','mayonnaise','mayo',
            'sauce barbecue','sauce bbq','sauce algérienne',
            'sauce cocktail','sauce soya','sauce soja','sauce chili',
            'sauce hoisin','sauce teriyaki','sauce st-hubert',
            'sauce à','sauce pour',
            'mélange à sauce','mélange sauce',
            'vinaigrette','salsa','guacamole',
            'sriracha','tabasco','worcestershire',
            'tartare']

YOGOURT_KW = ['yogourt','yaourt','yogurt','kéfir','kefir','skyr',
              'yogourt grec','yaourt grec','greek yogurt','yogourt grecque']

PROTEIN_PER_100G = {
    "boeuf": {"haché maigre": 20, "haché": 17, "steak": 23, "rôti": 22, "cube": 20, "generic": 20},
    "poulet": {"poitrine": 25, "cuisse": 20, "aile": 18, "entier": 20, "haché": 20, "generic": 20},
    "porc": {"longe": 22, "côtelette": 20, "haché": 17, "rôti": 22, "generic": 20},
    "veau": {"haché": 18, "generic": 18},
    "poisson": {"saumon": 20, "thon": 23, "crevette": 20, "morue": 18, "generic": 18},
    "yogourt": {"grec": 9, "grecque": 9, "nature": 4, "generic": 5},
}

# ─── URLs des épiceries ───
STORE_URLS = {
    "Super C": "https://www.superc.ca/",
    "Tigre Géant": "https://www.tigregeant.ca/",
    "Maxi": "https://www.maxi.ca/",
    "Provigo": "https://www.provigo.ca/",
    "Loblaws": "https://www.loblaws.ca/",
    "IGA": "https://www.iga.net/",
    "Metro": "https://www.metro.ca/",
    "Walmart": "https://www.walmart.ca/",
    "Costco": "https://www.costco.ca/",
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
    for kw in YOGOURT_KW:
        if kw in name_lower:
            return "yogourt"
    for kw in SAUCE_KW:
        if kw in name_lower:
            return "sauce"
    for kw in CONSERVE_KW:
        if kw in name_lower:
            return "panier"
    if current_mt in ("legume", "légume"):
        return "legume"
    return current_mt or "autre"


def classify_product_type(name):
    """Classifie un produit comme 'frais' ou 'transformé' selon son nom.
    'frais' = viande crue, fruits/légumes frais, poisson frais, ingrédients bruts
    'transformé' = surgelé, préparé, en conserve, transformé, pané, etc.
    """
    name_lower = name.lower()
    
    # Mots-clés de produits TRANSFORMÉS (surgelés, préparés, transformés)
    TRANSFORMED_KW = [
        # Surgelé
        r'\bsurgelé', r'\bcongelé', r'\bfrozen', r'\bglacé',
        # Préparé / prêt-à-manger
        r'\bpréparé', r'\brepas\b', r'\bplat\b', r'\bdîner\b', r'\bsouper\b',
        r'\bentrée\b', r'\bportion\b',
        # Pané / frit
        r'\bpané', r'\bfrit', r'\bbreaded', r'\bfried',
        # Nuggets / lanières / burgers (préparés)
        r'\bnuggets?\b', r'\blanières?\b', r'\bstrips?\b', r'\bburger', r'\bpépites?\b',
        # Charcuterie / transformé
        r'\bjambon\b', r'\bbacon\b', r'\bsaucisse\b', r'\bsaucisson\b',
        r'\bviande fumée\b', r'\bsmoked meat\b', r'\bdeli\b', r'\bcharcuterie\b',
        # Conserves
        r'\bconserve\b', r'\ben conserve\b', r'\bbte\b', r'\bbocal\b',
        r'\bsoupe\b', r'\bbouillon\b',
        # Sauce / condiment
        r'\bsauce\b', r'\bmayonnaise\b', r'\bketchup\b', r'\bmoutarde\b',
        r'\bvinaigre\b', r'\bhuile\b',
        # Boisson
        r'\bboisson\b', r'\bjus\b', r'\bsoda\b', r'\bpepsi\b', r'\bcoca\b',
        # Snack
        r'\bcroustille\b', r'\bchips\b', r'\bnoix\b', r'\barachide\b',
        r'\bbiscuit\b', r'\bgâteau\b', r'\btartinade\b', r'\bconfiture\b',
        # Produits laitiers transformés
        r'\bfromage\b', r'\byogourt\b', r'\byaourt\b', r'\bcrème\b',
        r'\blait\b', r'\bbeurre\b', r'\boeuf\b',
        # Pâtes / riz / féculents
        r'\bpâtes\b', r'\briz\b', r'\bfarine\b', r'\bsucre\b', r'\bpain\b',
        r'\bcéréale\b', r'\bgaufre\b', r'\bpizza\b',
        # Autres transformés
        r'\bmélangé\b', r'\bassaisonné\b', r'\bmariné\b', r'\btrempette\b',
        r'\bcafé\b', r'\bthé\b', r'\bpapier\b', r'\bsavon\b', r'\bdétergent\b',
        r'\bassiette\b', r'\bgobelet\b', r'\bsac\b', r'\bpoubelle\b',
    ]
    
    for pattern in TRANSFORMED_KW:
        if re.search(pattern, name_lower):
            return "transformé"
    
    # Par défaut, si c'est de la viande/légume/fruit/poisson, c'est frais
    # (sauf si déjà détecté comme transformé ci-dessus)
    if any(mt in name_lower for mt in ['boeuf','bœuf','poulet','porc','veau','dinde',
                                         'agneau','steak','rôti','côtelette',
                                         'poitrine','cuisse','aile','pilons',
                                         'longe','filet','haché',
                                         'saumon','crevette','poisson','morue',
                                         'tilapia','truite','aiglefin','éperlan',
                                         'pomme','banane','orange','raisin',
                                         'bleuet','fraise','framboise','mûre','mure',
                                         'légume','legume','carotte','brocoli',
                                         'laitue','tomate','concombre','oignon',
                                         'patate','pomme de terre','salade',
                                         'chou','maïs','poivron','haricot',
                                         'melon','ananas','mangue','kiwi',
                                         'pêche','poire','cerise','abricot',
                                         'prune','nectarine','citron','lime',
                                         'pamplemousse','canneberge','airelle',
                                         'asperge','céleri','celeri','radis',
                                         'épinard','avocat','courgette',
                                         'aubergine','champignon','fève',
                                         'pois','navet','betterave',
                                         'persil','basilic','coriandre',
                                         'lime','limon','clémentine','mandarine']):
        return "frais"
    
    # Pour les catégories 'legume'/'fruit' sans indication, frais
    # Pour le reste, panier par défaut
    return "transformé"


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
    
    # Post-processing: mots courts avec word-boundary (trop risqués en substring)
    # Ces mots sont SÉCURITAIRES en \b car ils n'apparaissent pas à l'intérieur 
    # de mots français dans le contexte des produits d'épicerie
    name_lower = re.sub(r'\band\b', 'et', name_lower, flags=re.IGNORECASE)
    name_lower = re.sub(r'\bfor\b', 'pour', name_lower, flags=re.IGNORECASE)
    name_lower = re.sub(r'\bwine\b', 'vin', name_lower, flags=re.IGNORECASE)
    name_lower = re.sub(r'\bshallots\b', 'échalotes', name_lower, flags=re.IGNORECASE)
    name_lower = re.sub(r'\bshallot\b', 'échalote', name_lower, flags=re.IGNORECASE)
    
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
    # On traduit TOUJOURS — la fonction translate_product_name est idempotente
    # pour le texte déjà en français (aucun terme EN→FR ne matchera).
    # L'ancien gate `eng_word_count >= 1` manquait des mots absents du set
    # (ex: 'sliced', 'blood', 'pudding', 'hotel' — pas dans english_terms → pas traduit)
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
    # Normaliser les apostrophes courbes → droites pour matcher RECIPE_FRENCH
    norm_title = title.replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    if norm_title in RECIPE_FRENCH:
        fr = RECIPE_FRENCH[norm_title]
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


def format_duration_french(duration_str):
    """Parse ISO 8601 duration (format PT15M, PT1H30M) depuis la DB vers français.
    Exemples: PT15M → '15 min', PT1H → '1 h', PT1H30M → '1 h 30 min'
    """
    if not duration_str:
        return ""
    # Extraire la durée ISO du texte brut (ex: 'Time": "PT15M",')
    m = re.search(r'PT(\d+H)?(\d+M)?', duration_str)
    if not m:
        return ""
    h = int(m.group(1).replace('H', '')) if m.group(1) else 0
    m_val = int(m.group(2).replace('M', '')) if m.group(2) else 0

    if h > 0 and m_val > 0:
        return f"{h} h {m_val} min"
    elif h > 0:
        return f"{h} h"
    else:
        return f"{m_val} min"


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
            "prep_time": format_duration_french(r["prep_time"]),
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
    """Exporte tous les deals avec classification enrichie + recettes traduites.
    Nouveau: exporte TOUTES les semaines disponibles pour navigation dans le temps."""
    db = get_db()
    
    recipes_by_meat = load_recipes()
    
    # Récupérer toutes les semaines disponibles
    all_weeks = [r["w"] for r in db.execute("SELECT DISTINCT week_start as w FROM price_history ORDER BY w DESC").fetchall()]
    
    if not all_weeks:
        db.close()
        return {"weeks": [], "deals": {}, "stats": {}}
    
    current_week = all_weeks[0]
    
    deals_by_week = {}
    week_stats = {}
    
    for week in all_weeks:
        rows = db.execute("""\
            SELECT p.id, p.name, p.meat_type, p.package_weight_g,
                   s.name as store, s.id as store_id,
                   ph.price, ph.unit_price, ph.unit_type,
                   ph.valid_to, ph.merchant_name, ph.image_url,
                   ph.sale_text
            FROM products p
            JOIN stores s ON s.id = p.store_id
            JOIN price_history ph ON ph.product_id = p.id
            WHERE ph.week_start = ? AND ph.price IS NOT NULL AND p.meat_type IS NOT NULL
            ORDER BY ph.price ASC
        """, (week,)).fetchall()
        
        seen_products = {}  # dict: pk -> row (pour préférer les entrées avec image)
        category_counts = defaultdict(int)
        store_set = set()
        deals = []
        
        # Première passe: garder la meilleure entrée par produit (avec image prioritaire)
        for r in rows:
            if is_excluded(r["name"]):
                continue
            pk = (r["name"], r["merchant_name"])
            if pk in seen_products:
                existing = seen_products[pk]
                # Remplacer si l'entrée courante a une image et pas l'existante
                if r["image_url"] and not existing["image_url"]:
                    seen_products[pk] = r
                continue
            seen_products[pk] = r
        
        # Deuxième passe: traiter les entrées retenues
        for r in seen_products.values():

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
            protein_per_100g = estimate_protein_per_100g(r["name"], mt) if mt in ["boeuf","porc","poulet","veau","poisson","yogourt"] else None
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
            
            # URL du site de l'épicerie
            store_url = STORE_URLS.get(store_name, "")
            
            deals.append({
                "id": r["id"],
                "name": clean_name,
                "name_short": short_name(clean_name, 40),
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
                "protein_per_100g": protein_per_100g,
                "protein_per_dollar": protein_per_dollar,
                "product_type": classify_product_type(clean_name),
                "recipe": recipe,
                "detail": r["sale_text"].strip() if r["sale_text"] else None,
            })
        
        deals_with_kg = [d for d in deals if d["per_kg"]]
        deals_with_kg.sort(key=lambda x: (x["per_kg"] if x["per_kg"] and x["per_kg"] > 0 else 99999, x["price"] or 0))
        deals_wo_kg = [d for d in deals if not d["per_kg"]]
        deals_wo_kg.sort(key=lambda x: x["price"] or 0)
        
        deals_by_week[week] = {
            "deals_with_kg": deals_with_kg,
            "deals_wo_kg": deals_wo_kg,
        }
        
        week_stats[week] = {
            "total": len(deals),
            "by_category": dict(category_counts),
            "stores": sorted(store_set),
        }
    
    db.close()
    
    # Fusionner tous les deals de la semaine courante en un seul tableau pour backward compat
    cw = deals_by_week.get(current_week, {"deals_with_kg": [], "deals_wo_kg": []})
    all_deals_current = cw["deals_with_kg"] + cw["deals_wo_kg"]
    
    return {
        "weeks": all_weeks,  # Liste des semaines dispo
        "current_week": current_week,
        "deals": {
            "deals_with_kg": all_deals_current,
            "deals_wo_kg": cw["deals_wo_kg"],
        },
        "deals_by_week": deals_by_week,  # Toutes les semaines
        "stats": {
            "total": week_stats.get(current_week, {}).get("total", 0),
            "by_category": week_stats.get(current_week, {}).get("by_category", {}),
            "stores": week_stats.get(current_week, {}).get("stores", []),
            "week": current_week,
            "weeks": all_weeks,
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
    rows = db.execute("""\
        SELECT p.id, p.name, p.meat_type, p.package_weight_g,
               s.name as store, s.id as store_id,
               ph.price, ph.unit_price, ph.unit_type,
               ph.valid_to, ph.merchant_name, ph.image_url
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
        
        # Nettoyer les caractères de contrôle unicode (\\u2028 etc.) sans toucher la ponctuation
        clean_title = re.sub(r'[\u0000-\u001f\u2028-\u202f\ufff0-\uffff]', '', r["title"]).strip()
        
        recipe = {
            "title": clean_title,
            "meat_type": r["meat_type"],
            "source": r["source_name"],
            "url": r["source_url"],
            "image_url": r["image_url"],
            "rating": r["rating"],
            "rating_count": r["rating_count"] or 0,
            "prep_time": format_duration_french(r["prep_time"]),
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
