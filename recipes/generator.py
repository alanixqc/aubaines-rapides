#!/usr/bin/env python3
"""
Générateur de recettes — Aubaines Rapides
Prend les deals de la semaine et génère 3 recettes utilisant la viande hachée
"""
import sys
import os
import json
import random
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from recipes.schema import get_db as get_recipe_db
from db.schema import get_db as get_deal_db

# ─── Configuration ───────────────────────────────────────────────────────────
DEAL_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "aubaines.db")
RECIPE_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "recipes.db")

STORE_EMOJIS = {
    "Super C": "🟡", "Metro": "🔴", "IGA": "🟢", "Maxi": "🟠",
    "Provigo": "🟣", "Walmart": "🔵", "Costco": "⭕",
    "Tigre Géant": "🐯", "Les Marchés Tradition": "🟤",
}
MEAT_EMOJI = {"boeuf": "🥩", "porc": "🥓", "poulet": "🍗", "veau": "🥩", "dinde": "🦃", "mixte": "🥩🥓"}

# Mapping: meat_type → mots-clefs pour matcher dans les ingrédients des recettes
MEAT_INGREDIENT_KEYWORDS = {
    "boeuf": ["boeuf", "bœuf", "steak haché", "bifteck haché", "hamburger", "ground beef"],
    "porc": ["porc", "porc haché", "pork"],
    "poulet": ["poulet", "poulet haché", "dindon", "dinde", "chicken", "turkey"],
    "veau": ["veau", "veau haché", "veal"],
    "dinde": ["dinde", "dindon", "turkey"],
}


def format_qty(qty):
    """Formate une quantité pour l'affichage."""
    if qty is None:
        return ""
    qty_str = f"{qty:.2f}".rstrip("0").rstrip(".")
    if "." in qty_str:
        qty_str = qty_str.rstrip("0").rstrip(".")
    return qty_str


def get_weekly_deals():
    """Récupère les deals de viande hachée de la semaine."""
    db = get_deal_db()
    max_week = db.execute("SELECT MAX(week_start) as w FROM price_history").fetchone()["w"]

    # Items viande hachée
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
        ORDER BY ph.price ASC
        LIMIT 30
    """, (max_week,)).fetchall()
    db.close()

    # Déduplication
    seen = set()
    deals = []
    for r in rows:
        key = (r["name"], r["merchant_name"])
        if key not in seen:
            seen.add(key)
            deals.append(r)

    return deals


def match_recipes(deals):
    """Trouve des recettes qui correspondent aux deals de la semaine."""
    rdb = get_recipe_db()

    # Grouper par type de viande
    meat_types = set()
    for d in deals:
        if d["meat_type"]:
            meat_types.add(d["meat_type"])

    if not meat_types:
        meat_types = {"boeuf"}  # fallback

    recipes = []
    for mt in meat_types:
        best = None
        if mt == "boeuf":
            best = rdb.execute("""
                SELECT id, title, category, meat_type, source_name, source_url, image_url,
                       prep_time, cook_time, total_time, servings, rating, ingredients_raw, steps_raw
                FROM recipes
                WHERE meat_type IN ('boeuf', 'mixte')
                ORDER BY RANDOM() LIMIT 1
            """).fetchone()
        elif mt == "porc":
            best = rdb.execute("""
                SELECT id, title, category, meat_type, source_name, source_url, image_url,
                       prep_time, cook_time, total_time, servings, rating, ingredients_raw, steps_raw
                FROM recipes
                WHERE meat_type IN ('porc', 'mixte')
                ORDER BY RANDOM() LIMIT 1
            """).fetchone()
        elif mt in ("poulet", "dinde", "dindon"):
            best = rdb.execute("""
                SELECT id, title, category, meat_type, source_name, source_url, image_url,
                       prep_time, cook_time, total_time, servings, rating, ingredients_raw, steps_raw
                FROM recipes
                WHERE meat_type IN ('poulet', 'dinde', 'mixte')
                ORDER BY RANDOM() LIMIT 1
            """).fetchone()

        if best:
            recipes.append(dict(best))

    rdb.close()
    return recipes


def estimate_cost(recipe, deals):
    """Estime le coût de la recette basé sur les deals disponibles."""
    ingredients = json.loads(recipe["ingredients_raw"])
    total_est = 0.0
    matched_items = []

    for ing in ingredients:
        ing_name = (ing.get("ingredient") or ing.get("original_text", "")).lower()

        # Chercher si l'ingrédient principal (viande) matche un deal
        for d in deals:
            deal_name = d["name"].lower()
            # Check si la viande du deal correspond
            for mt, keywords in MEAT_INGREDIENT_KEYWORDS.items():
                for kw in keywords:
                    if kw in ing_name:
                        # Deal trouvé pour cet ingrédient
                        price = d["price"] or 0
                        total_est += price
                        matched_items.append({
                            "deal_name": d["name"],
                            "deal_store": d["merchant_name"],
                            "deal_price": price,
                            "ingredient": ing.get("original_text", ""),
                        })
                        break
                if matched_items and matched_items[-1].get("deal_name"):
                    break
            if matched_items and matched_items[-1].get("deal_name"):
                break

    return total_est, matched_items


def format_recipe_card(recipe, deals, medal="🥇"):
    """Formate une recette complète pour affichage."""
    emoji = MEAT_EMOJI.get(recipe.get("meat_type", ""), "🍳")

    lines = []
    lines.append(f"\n{medal} {emoji} **{recipe['title']}**")
    if recipe.get("category"):
        lines.append(f"   📂 {recipe['category']}")

    if recipe.get("prep_time") or recipe.get("cook_time") or recipe.get("total_time"):
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
        # Prendre les 8 premiers ingrédients
        lines.append(f"   \n   📋 **Ingrédients:**")
        for ing in ingredients[:8]:
            text = ing.get("original_text", "")
            if ing.get("section") and ing["section"] not in ("ingrédients", "ingredients", ""):
                lines.append(f"   *{ing['section']}*")
            lines.append(f"   • {text}")
        if len(ingredients) > 8:
            lines.append(f"   … et {len(ingredients) - 8} autres ingrédients")

    # Étapes (premières 3)
    steps = json.loads(recipe.get("steps_raw", "[]"))
    if steps:
        lines.append(f"   \n   👨‍🍳 **Préparation:**")
        for s in steps[:3]:
            lines.append(f"   {s['step']}. {s['text'][:120]}")
        if len(steps) > 3:
            lines.append(f"   … et {len(steps) - 3} autres étapes")

    # Estimation du coût
    cost, matched = estimate_cost(recipe, deals)
    if cost > 0:
        stores = set(m["deal_store"] for m in matched)
        store_str = ", ".join(f"{STORE_EMOJIS.get(s, '')}{s}" for s in stores)
        lines.append(f"   \n💰 **Coût estimé:** ~{cost:.2f}$ (viande seulement)")
        if stores:
            lines.append(f"   🏪 Acheter chez: {store_str}")

    # Lien recette originale
    if recipe.get("source_url"):
        lines.append(f"   \n🔗 [Voir la recette originale]({recipe['source_url']})")

    return "\n".join(lines)


def generate_recipes():
    """Pipeline complet: deals → recettes → formatage."""
    print("🍳 GÉNÉRATEUR DE RECETTES — Aubaines Rapides")
    print("=" * 60)

    # 1. Récupérer les deals de viande hachée
    deals = get_weekly_deals()
    if not deals:
        print("❌ Aucun deal de viande hachée cette semaine.")
        return

    print(f"\n📊 {len(deals)} deals de viande hachée trouvés:")
    for d in deals:
        price = d["price"] or 0
        store_em = STORE_EMOJIS.get(d["merchant_name"], "🏪")
        print(f"   {store_em} {d['merchant_name']} — {d['name'][:45]} — {price:.2f}$")

    # Stats par type
    by_type = {}
    for d in deals:
        mt = d["meat_type"] or "autre"
        by_type[mt] = by_type.get(mt, 0) + 1
    print(f"\n   Types: {', '.join(f'{k}: {v}' for k, v in by_type.items())}")

    # 2. Matcher avec des recettes
    recipes = match_recipes(deals)
    if not recipes:
        print("❌ Aucune recette trouvée.")
        return

    print(f"\n📖 {len(recipes)} recettes sélectionnées:")

    # 3. Formater
    medals = ["🥇", "🥈", "🥉"]
    for i, recipe in enumerate(recipes[:3]):
        medal = medals[i] if i < len(medals) else "📋"
        card = format_recipe_card(recipe, deals, medal)
        print(card)
        print()

    # 4. Résumé
    print("=" * 60)
    print(f"✅ {min(len(recipes), 3)} recettes générées avec les deals de la semaine")
    print(f"📅 Semaine du {date.today()}")
    print("=" * 60)

    return recipes[:3]


def format_for_discord(recipes, deals):
    """Formate les recettes pour un post Discord."""
    medals = ["🥇", "🥈", "🥉"]
    parts = ["🍳 **RECETTES DE LA SEMAINE** — Avec les deals en cours!"]
    parts.append(f"📅 Semaine du {date.today().strftime('%d %B %Y')}\n")

    for i, recipe in enumerate(recipes[:3]):
        medal = medals[i] if i < len(medals) else "📋"
        card = format_recipe_card(recipe, deals, medal)
        parts.append(card)

    parts.append(f"\n---\n💡 Utilise !deal pour voir les deals ou !produit [nom] pour chercher un ingrédient")
    return "\n".join(parts)


if __name__ == "__main__":
    recipes = generate_recipes()

    # Mode Discord
    if "--discord" in sys.argv and recipes:
        from scripts.deal import get_db
        deals = get_weekly_deals()
        msg = format_for_discord(recipes, deals)
        print("\n\n📱 MESSAGE DISCORD:")
        print(msg)
