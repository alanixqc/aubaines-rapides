"""
Recettes — Schema DB + fonctions
Stocke les recettes québécoises structurées
"""
import sqlite3
import os
import json
from datetime import date

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "recipes.db")

SCHEMA_SQL = """
-- Recettes individuelles
CREATE TABLE IF NOT EXISTS recipes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id       TEXT    UNIQUE,        -- ID du site source (ex: "rq-21849")
    title           TEXT    NOT NULL,
    category        TEXT,                   -- Pain de viande, Pâté chinois, etc.
    subcategory     TEXT,                   -- sous-catégorie
    meat_type       TEXT,                   -- boeuf, porc, poulet, veau, mixte
    source_name     TEXT,                   -- nom du site source
    source_url      TEXT,                   -- URL originale
    image_url       TEXT,                   -- photo du plat
    prep_time       TEXT,                   -- "15 min"
    cook_time       TEXT,                   -- "70 min"
    total_time      TEXT,                   -- "1h25"
    servings        TEXT,                   -- "3 à 4 portions"
    difficulty      TEXT,                   -- Facile, Moyen, Difficile
    rating          REAL,                   -- note moyenne
    ingredients_raw TEXT,                   -- JSON: liste des ingrédients
    steps_raw       TEXT,                   -- JSON: liste des étapes
    metadata        TEXT,                   -- JSON flexible (tags, notes, etc.)
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Ingrédients individuels (pour recherche par produit)
CREATE TABLE IF NOT EXISTS recipe_ingredients (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id       INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    ingredient      TEXT    NOT NULL,       -- nom normalisé
    quantity        REAL,                   -- quantité numérique
    unit            TEXT,                   -- tasse, lb, g, ml, c.thé, etc.
    original_text   TEXT,                   -- texte original ("1/2 tasse gruau")
    section         TEXT,                   -- groupe (vide, "sauce", etc.)
    sort_order      INTEGER
);

-- Relation: deals → recettes (générée chaque semaine)
CREATE TABLE IF NOT EXISTS weekly_recipes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start      TEXT    NOT NULL,
    recipe_id       INTEGER NOT NULL REFERENCES recipes(id),
    deal_product_id INTEGER REFERENCES products(id),
    match_type      TEXT,                   -- exacte, substitution, créative
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_recipe_ingredient ON recipe_ingredients(ingredient);
CREATE INDEX IF NOT EXISTS idx_recipes_meat ON recipes(meat_type);
CREATE INDEX IF NOT EXISTS idx_recipes_category ON recipes(category);
CREATE INDEX IF NOT EXISTS idx_weekly_recipes_week ON weekly_recipes(week_start);
"""

MEAT_TYPES = {
    "boeuf": ["boeuf", "bœuf", "beef", "hamburger"],
    "porc": ["porc", "pork"],
    "poulet": ["poulet", "poulets", "chicken"],
    "veau": ["veau", "veal"],
    "dinde": ["dinde", "turkey", "dindon"],
    "mixte": ["mixte", "mélangé"],
}

CATEGORIES = {
    "pain de viande": ["pain de viande", "roulé de viande", "roule de viande", "meatloaf", "pain à' viande"],
    "pâté chinois": ["pâté chinois", "pate chinois", "shepherd's pie", "hachis parmentier"],
    "tourtière": ["tourtière", "tourtiere", "pâté à la viande", "pate a la viande"],
    "boulettes": ["boulettes", "boulette", "meatballs", "rissoles"],
    "chili": ["chili", "chili con carne"],
    "sauce à spaghetti": ["sauce à spaghetti", "sauce a spaghetti", "sauce à viande", "bolognaise", "bolognese"],
    "cigares au chou": ["cigare au chou", "chou farci", "choux farcis", "cabbage roll"],
    "hamburger": ["hamburger", "burger", "galette", "steak haché", "bifteck haché"],
    "casserole": ["casserole", "gratin", "lasagne", "macaroni"],
    "tacos": ["taco", "enchilada", "fajita", "burrito"],
    "pâté": ["pâté", "pate"],
    "sauté": ["sauté", "sauté", "poêlé", "poele"],
    "soupe": ["soupe", "potage", "ragoût", "ragout"],
}

MEAT_EMOJI = {"boeuf": "🥩", "porc": "🥓", "poulet": "🍗", "veau": "🥩", "dinde": "🦃", "mixte": "🥩🥓"}


def get_db():
    """Ouvre et retourne une connexion à la base de données recettes."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Crée les tables si elles n'existent pas."""
    conn = get_db()
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    print(f"✅ Base recettes initialisée : {DB_PATH}")


def detect_meat_type(title, category):
    """Détecte le type de viande à partir du titre et de la catégorie."""
    text = (title + " " + (category or "")).lower()
    found = []
    for meat, keywords in MEAT_TYPES.items():
        for kw in keywords:
            if kw in text:
                found.append(meat)
                break
    if len(found) == 0:
        return "mixte"
    return found[0] if len(found) == 1 else "mixte"


def detect_category(title, category):
    """Trouve la catégorie la plus proche."""
    text = (title + " " + (category or "")).lower()
    for cat, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw in text:
                return cat
    return category or "autre"


def parse_ingredient(text):
    """Parse un ingrédient: '1 1/2 livre boeuf haché' → (qty, unit, name)"""
    import re
    text = text.strip().strip("-").strip()

    # Patterns pour les quantités
    # "1 1/2 livre" ou "1/2 tasse" ou "1 lb" ou "2"
    qty = None
    unit = ""
    name = text

    # Fraction: "1 1/2", "1/2", "3/4"
    frac_match = re.match(r'^(\d+\s+)?(\d+)/(\d+)\s+(.+?)$', text)
    if frac_match:
        whole = int(frac_match.group(1)) if frac_match.group(1) else 0
        num = int(frac_match.group(2))
        den = int(frac_match.group(3))
        qty = whole + num / den
        name = frac_match.group(4)
    else:
        # Nombre simple: "2 lbs", "500 g", "1 c. thé"
        simple_match = re.match(r'^(\d+(?:[,.]\d+)?)\s+(.+?)$', text)
        if simple_match:
            try:
                qty = float(simple_match.group(1).replace(",", "."))
            except ValueError:
                qty = None
            name = simple_match.group(2)

    # Extraire l'unité
    unit_patterns = [
        r'^(lb|lbs|livre|livres)\s+(.+?)$', r'^(oz|once|onces)\s+(.+?)$',
        r'^(g|gr|gramme|grammes)\s+(.+?)$', r'^(kg|kilo|kilos)\s+(.+?)$',
        r'^(ml|millilitre|millilitres)\s+(.+?)$',
        r'^(tasse|tasses|t)\s+(.+?)$', r'^(c[. ]?[àa] soupe|c[. ]?[àa] table|c\. à s\.?|c\. à table|\\btablespoon)\s+(.+?)$',
        r'^(c[. ]?[àa] thé|c[. ]?[àa] café|c\. à t\.?|\\bteaspoon)\s+(.+?)$',
    ]
    for pat in unit_patterns:
        m = re.match(pat, name, re.IGNORECASE)
        if m:
            unit = m.group(1)
            name = m.group(2)
            break

    return qty, unit, name.strip().strip(",")


def format_ingredient_line(text, qty, unit):
    """Formate un ingrédient pour l'affichage."""
    if qty:
        qty_str = f"{qty:.1f}".rstrip("0").rstrip(".") if qty != int(qty) else str(int(qty))
        if unit:
            return f"  • {qty_str} {unit} {text}"
        return f"  • {qty_str} {text}"
    return f"  • {text}"


if __name__ == "__main__":
    init_db()
    print("✅ Base recettes prête")
