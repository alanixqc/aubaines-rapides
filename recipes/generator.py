#!/usr/bin/env python3
"""
Générateur de recettes — Aubaines Rapides
Usage:  python recipes/generator.py              → toutes les recettes
        python recipes/generator.py boeuf         → recettes boeuf seulement
        python recipes/generator.py poulet        → recettes poulet/dinde
        python recipes/generator.py porc          → recettes porc seulement
Les recettes sont liées aux deals de viande hachée de la semaine.
"""
import sys
import os
import json
import random
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from recipes.schema import get_db as get_recipe_db
from db.schema import get_db as get_deal_db

DEAL_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "aubaines.db")
RECIPE_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "recipes.db")

STORE_EMOJIS = {
    "Super C": "🟡", "Metro": "🔴", "IGA": "🟢", "Maxi": "🟠",
    "Provigo": "🟣", "Walmart": "🔵", "Costco": "⭕",
    "Tigre Géant": "🐯", "Les Marchés Tradition": "🟤",
}
MEAT_EMOJI = {"boeuf": "🥩", "porc": "🥓", "poulet": "🍗", "veau": "🥩", "dinde": "🦃", "mixte": "🥩🥓"}

# Mapping pour trouver la viande dans les noms d'ingrédients
MEAT_KEYWORDS = {
    "boeuf": ["boeuf", "bœuf", "steak haché", "bifteck haché", "hamburger", "ground beef"],
    "porc": ["porc", "porc haché", "pork"],
    "poulet": ["poulet", "poulet haché", "chicken"],
    "dinde": ["dinde", "dindon", "turkey"],
    "veau": ["veau", "veau haché", "veal"],
}

# Types de viande supportés
VALID_MEAT_TYPES = {"boeuf", "porc", "poulet", "dinde", "veau"}
# Alias
MEAT_ALIASES = {
    "bœuf": "boeuf", "beef": "boeuf",
    "pork": "porc",
    "chicken": "poulet", "poul": "poulet",
    "dinde": "dinde", "dindon": "dinde", "turkey": "dinde",
    "veau": "veau", "veal": "veau",
}


def get_weekly_deals():
    """Récupère les deals de viande hachée de la semaine."""
    db = get_deal_db()
    max_week = db.execute("SELECT MAX(week_start) as w FROM price_history").fetchone()["w"]

    rows = db.execute("""
        SELECT p.id, p.name, p.meat_type, p.package_weight_g,
               s.name as store, ph.price, ph.unit_price, ph.unit_type,
               ph.valid_to, ph.merchant_name, ph.image_url
        FROM products p
        JOIN stores s ON s.id = p.store_id
        JOIN price_history ph ON ph.product_id = p.id
        WHERE ph.week_start = ?
          AND p.meat_type IS NOT NULL
          AND ph.price IS NOT NULL
          AND (
               LOWER(p.name) LIKE '%haché%'
            OR LOWER(p.name) LIKE '%hache%'
            OR LOWER(p.name) LIKE '%burger%'
            OR LOWER(p.name) LIKE '%steak haché%'
            OR LOWER(p.name) LIKE '%bifteck haché%'
          )
        ORDER BY ph.price ASC LIMIT 30
    """, (max_week,)).fetchall()
    db.close()

    seen = set()
    deals = []
    for r in rows:
        key = (r["name"], r["merchant_name"])
        if key not in seen:
            seen.add(key)
            deals.append(r)
    return deals


def match_recipes(meat_filter=None):
    """Trouve des recettes. Si meat_filter est donné, filtre par viande."""
    rdb = get_recipe_db()
    meat_filter = normalize_meat(meat_filter)

    if meat_filter:
        # Mapping du type demandé → types dans la DB
        if meat_filter == "boeuf":
            db_types = ("boeuf", "mixte")
        elif meat_filter == "porc":
            db_types = ("porc", "mixte")
        elif meat_filter == "poulet":
            db_types = ("poulet", "mixte")
        elif meat_filter == "dinde":
            db_types = ("dinde", "mixte", "poulet")
        elif meat_filter == "veau":
            db_types = ("veau", "mixte")
        else:
            db_types = (meat_filter, "mixte")

        placeholders = ",".join("?" for _ in db_types)
        rows = rdb.execute(f"""
            SELECT id, title, category, meat_type, source_name, source_url, image_url,
                   prep_time, cook_time, total_time, servings, rating, ingredients_raw, steps_raw
            FROM recipes
            WHERE meat_type IN ({placeholders})
            ORDER BY RANDOM() LIMIT 3
        """, db_types).fetchall()
        recipes = [dict(r) for r in rows]
    else:
        # Pas de filtre: 1 recette de chaque type disponible
        recipes = []
        for mt in ["boeuf", "porc", "poulet"]:
            r = rdb.execute("""
                SELECT id, title, category, meat_type, source_name, source_url, image_url,
                       prep_time, cook_time, total_time, servings, rating, ingredients_raw, steps_raw
                FROM recipes
                WHERE meat_type IN (?, 'mixte')
                ORDER BY RANDOM() LIMIT 1
            """, (mt,)).fetchone()
            if r:
                recipes.append(dict(r))

    rdb.close()
    return recipes


def normalize_meat(meat):
    """Normalise un nom de viande."""
    if not meat:
        return None
    meat = meat.lower().strip()
    return MEAT_ALIASES.get(meat, meat)


def estimate_cost(recipe, deals):
    """Estime le coût de la recette basé sur les deals disponibles."""
    ingredients = json.loads(recipe.get("ingredients_raw", "[]"))
    matched_items = []

    for ing in ingredients:
        ing_name = (ing.get("ingredient") or ing.get("original_text", "")).lower()
        for d in deals:
            deal_name = d["name"].lower()
            for mt, keywords in MEAT_KEYWORDS.items():
                for kw in keywords:
                    if kw in ing_name:
                        price = d["price"] or 0
                        matched_items.append({
                            "deal_name": d["name"],
                            "deal_store": d["merchant_name"],
                            "deal_price": price,
                            "ingredient": ing.get("original_text", ""),
                        })
                        break
                if matched_items and matched_items[-1].get("deal_store"):
                    break
            if matched_items and matched_items[-1].get("deal_store"):
                break

    total_cost = sum(m["deal_price"] for m in matched_items)
    return total_cost, matched_items


def format_recipe_card(recipe, deals, medal="🥇"):
    """Formate une recette complète pour affichage."""
    emoji = MEAT_EMOJI.get(recipe.get("meat_type", ""), "🍳")
    lines = [f"\n{medal} {emoji} **{recipe['title']}**"]

    if recipe.get("category"):
        lines.append(f"   📂 {recipe['category']}")

    times = []
    if recipe.get("prep_time"): times.append(f"Préparation: {recipe['prep_time']}")
    if recipe.get("cook_time"): times.append(f"Cuisson: {recipe['cook_time']}")
    if recipe.get("total_time"): times.append(f"Total: {recipe['total_time']}")
    if times: lines.append(f"   ⏱ {' | '.join(times)}")
    if recipe.get("servings"):
        lines.append(f"   👥 {recipe['servings']}")

    # Ingrédients
    ingredients = json.loads(recipe.get("ingredients_raw", "[]"))
    if ingredients:
        lines.append(f"\n   📋 **Ingrédients:**")
        for ing in ingredients[:8]:
            text = ing.get("original_text", "")
            if ing.get("section") and ing["section"] not in ("ingrédients", "ingredients", ""):
                lines.append(f"   *{ing['section']}*")
            lines.append(f"   • {text}")
        if len(ingredients) > 8:
            lines.append(f"   … et {len(ingredients) - 8} autres ingrédients")

    # Étapes
    steps = json.loads(recipe.get("steps_raw", "[]"))
    if steps:
        lines.append(f"\n   👨‍🍳 **Préparation:**")
        for s in steps[:3]:
            lines.append(f"   {s['step']}. {s['text'][:120]}")
        if len(steps) > 3:
            lines.append(f"   … et {len(steps) - 3} autres étapes")

    # Estimation coût
    cost, matched = estimate_cost(recipe, deals)
    if cost > 0:
        stores = set(m["deal_store"] for m in matched)
        store_str = ", ".join(f"{STORE_EMOJIS.get(s, '')}{s}" for s in stores)
        lines.append(f"\n💰 **Coût estimé:** ~{cost:.2f}$ (viande seulement)")
        if stores:
            lines.append(f"   🏪 Acheter chez: {store_str}")

    if recipe.get("source_url"):
        lines.append(f"\n🔗 [Voir la recette originale]({recipe['source_url']})")

    return "\n".join(lines)


def generate_recipes(meat_filter=None):
    """Pipeline complet: deals → recettes → formatage."""
    if meat_filter:
        normalized = normalize_meat(meat_filter)
        if normalized not in VALID_MEAT_TYPES and normalized != "tout":
            print(f"❌ Type de viande invalide. Choisis parmi: boeuf, porc, poulet, dinde, veau")
            print(f"   Exemple: !recette boeuf, !recette poulet, !recette porc")
            return None
    else:
        normalized = None

    deals = get_weekly_deals()
    if not deals:
        print("😕 Aucun deal de viande hachée cette semaine.")
        return None

    recipes = match_recipes(normalized)
    if not recipes:
        meat_label = f" pour {normalized}" if normalized else ""
        print(f"😕 Aucune recette trouvée{meat_label}.")
        return None

    # Formatage
    medals = ["🥇", "🥈", "🥉"]
    header = "🍳 **RECETTES DE LA SEMAINE**"
    if normalized:
        emoji = MEAT_EMOJI.get(normalized, "")
        header += f" — {emoji} {normalized.capitalize()}"
    header += f"\n📅 Semaine du {date.today().strftime('%d %B %Y')}\n"
    print(header)

    for i, recipe in enumerate(recipes[:3]):
        medal = medals[i] if i < len(medals) else "📋"
        print(format_recipe_card(recipe, deals, medal))

    deals_total = len(deals)
    types = set(d["meat_type"] for d in deals if d["meat_type"])
    print(f"\n📊 {deals_total} offres de viande hachée · Types: {', '.join(sorted(types))}")
    print("💡 !recette boeuf | !recette poulet | !recette porc pour filtrer")

    return recipes[:3]


if __name__ == "__main__":
    filter_meat = sys.argv[1] if len(sys.argv) > 1 else None
    generate_recipes(filter_meat)
