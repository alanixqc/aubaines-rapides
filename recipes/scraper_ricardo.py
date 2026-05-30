#!/usr/bin/env python3
"""
Scraper Ricardo — ricardocuisine.com
Scrape les recettes de viande hachée depuis la page listing boeuf
Utilise JSON-LD + HTML pour extraire les données structurées
"""
import sys
import os
import re
import json
import time
import random
import requests
from datetime import datetime
from html import unescape

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from recipes.schema import (
    get_db, init_db, detect_category, parse_ingredient
)

BASE_URL = "https://www.ricardocuisine.com"
REQUEST_DELAY = 2.0  # soyez polis avec Ricardo


def get_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
        "Accept-Language": "fr-CA,fr;q=0.9",
    }


def get_recipe_urls(max_pages=20):
    """Récupère les URLs des recettes depuis la page boeuf."""
    urls = []
    for page in range(1, max_pages + 1):
        if page == 1:
            url = f"{BASE_URL}/recettes/ingredients/boeuf"
        else:
            url = f"{BASE_URL}/recettes/ingredients/boeuf/page/{page}"

        try:
            resp = requests.get(url, headers=get_headers(), timeout=15)
            resp.raise_for_status()
        except Exception as e:
            print(f"   ❌ Page {page}: {e}")
            break

        # Trouver les liens de recettes
        links = re.findall(r'href="(/recettes/\d+-[^"]+)"', resp.text)
        links = list(set(links))  # déduplication
        urls.extend(links)
        print(f"📄 Page {page}: {len(links)} recettes (total: {len(urls)})")

        # Vérifier s'il y a une page suivante
        if '<link rel="next"' not in resp.text:
            print("   → Dernière page atteinte")
            break

        time.sleep(REQUEST_DELAY)

    return [f"{BASE_URL}{u}" for u in urls]


def scrape_recipe(url):
    """Scrape une recette Ricardo depuis son URL."""
    try:
        resp = requests.get(url, headers=get_headers(), timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"   ❌ Requête: {e}")
        return None

    html = resp.text
    data = {"source_url": url}

    try:
        # ── JSON-LD ──
        json_ld_match = re.search(
            r"<script type='application/ld\+json'>({.*?})</script>",
            html, re.DOTALL
        )
        if not json_ld_match:
            json_ld_match = re.search(
                r'<script type="application/ld\+json">({.*?})</script>',
                html, re.DOTALL
            )
        ld = {}
        if json_ld_match:
            try:
                ld = json.loads(json_ld_match.group(1))
            except:
                pass

        # ── Titre ──
        title = ld.get("name", "")
        if not title:
            tm = re.search(r'<h1[^>]*>(.*?)</h1>', html)
            if tm: title = re.sub(r'<[^>]+>', '', tm.group(1)).strip()
        data["title"] = title
        source_id_match = re.search(r'/recettes/(\d+)-', url)
        data["id"] = f"rc-{source_id_match.group(1)}" if source_id_match else f"rc-{hash(url)}"

        # ── Image ──
        if ld.get("image"):
            img = ld["image"]
            data["image_url"] = img[0] if isinstance(img, list) else img

        # ── Temps ──
        prep = ld.get("prepTime", "")
        cook = ld.get("cookTime", "")
        data["prep_time"] = prep.replace("PT", "").replace("M", " min").replace("H", "h ") if prep else None
        data["cook_time"] = cook.replace("PT", "").replace("M", " min").replace("H", "h ") if cook else None

        # Calculate total
        total_min = 0
        if prep:
            m = re.search(r'PT?(?:(\d+)H)?(?:(\d+)M)?', prep)
            if m: total_min += (int(m.group(1) or 0) * 60) + (int(m.group(2) or 0))
        if cook:
            m = re.search(r'PT?(?:(\d+)H)?(?:(\d+)M)?', cook)
            if m: total_min += (int(m.group(1) or 0) * 60) + (int(m.group(2) or 0))
        if total_min:
            h, m = divmod(total_min, 60)
            data["total_time"] = f"{h}h{m} min" if h else f"{m} min"

        # ── Portions ──
        yield_match = re.search(r'Rendement[^<]*</span>\s*[^<]*?<[^>]*>([^<]+)', html, re.DOTALL)
        if yield_match:
            data["servings"] = yield_match.group(1).strip()
        elif ld.get("recipeYield"):
            data["servings"] = ld["recipeYield"]

        # ── Source ──
        data["source_name"] = "Ricardo"

        # ── Catégorie ──
        cat_match = re.search(r'Catégories?\s*</[^>]+>\s*(.+?)</section>', html, re.DOTALL)
        category = ""
        if cat_match:
            categories = re.findall(r'>([^<]+)</a>', cat_match.group(1))
            category = ", ".join(categories) if categories else ""
        data["category"] = detect_category(title, category)

        # ── Ingrédients (JSON-LD) ──
        ingredients = []
        if ld.get("recipeIngredient"):
            for ing_text in ld["recipeIngredient"]:
                ing_text = ing_text.strip()
                qty, unit, name = parse_ingredient(ing_text)
                ingredients.append({
                    "original_text": ing_text, "quantity": qty, "unit": unit,
                    "ingredient": name, "section": "", "sort_order": len(ingredients),
                })

        # Fallback: HTML ingredients
        if not ingredients:
            sections = re.findall(
                r'c-recipe-instructions--ingredients.*?<ul[^>]*>(.*?)</ul>',
                html, re.DOTALL
            )
            for section_html in sections:
                items = re.findall(r'<li[^>]*>(.*?)</li>', section_html, re.DOTALL)
                for li in items:
                    text = re.sub(r'<[^>]+>', '', li).strip()
                    if text and 'for=' not in li:
                        qty, unit, name = parse_ingredient(text)
                        ingredients.append({
                            "original_text": text, "quantity": qty, "unit": unit,
                            "ingredient": name, "section": "", "sort_order": len(ingredients),
                        })

        data["ingredients_raw"] = json.dumps(ingredients, ensure_ascii=False)

        # ── Étapes (JSON-LD) ──
        steps = []
        if ld.get("recipeInstructions"):
            for inst in ld["recipeInstructions"]:
                if isinstance(inst, dict) and inst.get("text"):
                    steps.append({"step": len(steps) + 1, "text": inst["text"]})

        # Fallback: HTML steps
        if not steps:
            prep_section = re.search(
                r'c-recipe-instructions--preparation.*?<ol[^>]*>(.*?)</ol>',
                html, re.DOTALL
            )
            if prep_section:
                items = re.findall(r'<li[^>]*>(.*?)</li>', prep_section.group(1), re.DOTALL)
                for li in items:
                    text = re.sub(r'<[^>]+>', '', li).strip()
                    if text:
                        steps.append({"step": len(steps) + 1, "text": text})

        data["steps_raw"] = json.dumps(steps, ensure_ascii=False)

        # ── Rating ──
        rating_match = re.search(r'c-recipe-rating__value[^>]*>([\d.,]+)', html)
        if rating_match:
            data["rating"] = float(rating_match.group(1).replace(",", "."))

        # ── Meat type ──
        title_lower = title.lower() if title else ""
        if any(w in title_lower for w in ["boeuf", "bœuf", "beef", "steak haché"]):
            data["meat_type"] = "boeuf"
        elif any(w in title_lower for w in ["porc", "pork"]):
            data["meat_type"] = "porc"
        elif any(w in title_lower for w in ["poulet", "poulets", "chicken"]):
            data["meat_type"] = "poulet"
        elif any(w in title_lower for w in ["veau", "veal"]):
            data["meat_type"] = "veau"
        elif any(w in title_lower for w in ["dinde", "dindon", "turkey"]):
            data["meat_type"] = "dinde"
        elif "haché" in title_lower or "hache" in title_lower:
            data["meat_type"] = "mixte"
        else:
            data["meat_type"] = "mixte"

        return data

    except Exception as e:
        print(f"   ❌ Parse: {e}")
        import traceback
        traceback.print_exc()
        return None


def save_recipe(db, data):
    """Sauvegarde une recette dans la base."""
    if not data or not data.get("title"):
        return None

    db.execute("""
        INSERT OR REPLACE INTO recipes
        (source_id, title, category, meat_type, source_name,
         source_url, image_url, prep_time, cook_time, total_time,
         servings, rating, ingredients_raw, steps_raw, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("id"), data.get("title", ""), data.get("category"),
        data.get("meat_type"), data.get("source_name"), data.get("source_url"),
        data.get("image_url"), data.get("prep_time"), data.get("cook_time"),
        data.get("total_time"), data.get("servings"), data.get("rating"),
        data.get("ingredients_raw", "[]"), data.get("steps_raw", "[]"),
        json.dumps({"scraped_at": datetime.now().isoformat()}, ensure_ascii=False),
    ))

    recipe_id = db.execute("SELECT id FROM recipes WHERE source_id = ?", (data.get("id"),)).fetchone()
    if not recipe_id:
        return None
    recipe_id = recipe_id["id"]

    db.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
    for ing in json.loads(data.get("ingredients_raw", "[]")):
        db.execute("""
            INSERT INTO recipe_ingredients (recipe_id, ingredient, quantity, unit, original_text, section, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (recipe_id, ing.get("ingredient", ""), ing.get("quantity"),
              ing.get("unit", ""), ing.get("original_text", ""),
              ing.get("section", ""), ing.get("sort_order", 0)))
    return recipe_id


def is_hachee(data):
    """Vérifie si une recette est à la viande hachée."""
    text = (data.get("title", "") + " " + data.get("category", "")).lower()
    if "haché" in text or "hache" in text or "burger" in text or "steak haché" in text:
        return True
    ingredients = json.loads(data.get("ingredients_raw", "[]"))
    for ing in ingredients:
        ing_text = ing.get("original_text", "").lower()
        if "haché" in ing_text or "hache" in ing_text or "steak haché" in ing_text:
            return True
    return False


def run_scraper(max_recipes=None):
    """Scrape Ricardo recettes de boeuf."""
    print("=" * 60)
    print("🍳 SCRAPER RICARDO — ricardocuisine.com")
    print("   Focus: viande hachée (à partir des pages boeuf)")
    print("=" * 60)

    init_db()
    db = get_db()

    # Récupérer les URLs
    urls = get_recipe_urls()
    print(f"\n📊 {len(urls)} URLs de recettes trouvées")

    if max_recipes:
        urls = urls[:max_recipes]
        print(f"   (limité à {max_recipes})")

    # Filtrer les déjà scrappées
    existing = set(r["source_id"] for r in db.execute("SELECT source_id FROM recipes WHERE source_name='Ricardo'").fetchall())

    saved = 0
    skipped = 0
    errors = 0
    for i, url in enumerate(urls, 1):
        # Extraire l'ID
        id_match = re.search(r'/recettes/(\d+)-', url)
        rid = f"rc-{id_match.group(1)}" if id_match else None

        if rid and rid in existing:
            skipped += 1
            print(f"[{i}/{len(urls)}] ⏭️  Déjà scrapé")
            continue

        print(f"[{i}/{len(urls)}] {url.split('/')[-1][:50]}...")

        data = scrape_recipe(url)
        if data and data.get("title"):
            if is_hachee(data):
                rid = save_recipe(db, data)
                if rid:
                    saved += 1
                    print(f"   ✅ Sauvegardé (ID {rid})")
                else:
                    errors += 1
                    print(f"   ❌ Échec sauvegarde")
            else:
                skipped += 1
                print(f"   ⏭️  Pas de viande hachée")
        else:
            errors += 1
            print(f"   ❌ Échec scraping")

        db.commit()
        time.sleep(REQUEST_DELAY + random.uniform(0, 1))

    db.close()
    print(f"\n{'=' * 60}")
    print(f"✅ Terminé: {saved} sauvegardées, {skipped} ignorées, {errors} erreurs")
    print(f"{'=' * 60}")
    return {"saved": saved, "skipped": skipped, "errors": errors}


if __name__ == "__main__":
    max_rec = None
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        max_rec = int(sys.argv[idx + 1])
    run_scraper(max_recipes=max_rec)
