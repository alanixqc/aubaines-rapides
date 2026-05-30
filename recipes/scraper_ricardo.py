#!/usr/bin/env python3
"""
Scraper Ricardo — ricardocuisine.com
Scrape les recettes de viande hachée
Le listing page contient les URLs dans le JSON-LD ItemList, même pour page 2+
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
from recipes.schema import get_db, init_db, detect_category, parse_ingredient

BASE_URL = "https://www.ricardocuisine.com"
REQUEST_DELAY = 1.2

INGREDIENTS = [
    ("boeuf", 19),
    ("porc", 33),
    ("poulet", 25),
    ("veau", 6),
]


def get_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
        "Accept-Language": "fr-CA,fr;q=0.9",
    }


def get_all_recipe_urls():
    """Récupère toutes les URLs de recettes pour chaque type de viande."""
    all_urls = []
    for ingredient, max_pages in INGREDIENTS:
        for page in range(1, max_pages + 1):
            url = f"{BASE_URL}/recettes/ingredients/{ingredient}?page={page}"
            try:
                resp = requests.get(url, headers=get_headers(), timeout=15)
                scripts = re.findall(r'<script[^>]*>(.*?)</script>', resp.text, re.DOTALL)

                for s in scripts:
                    if 'ItemList' in s:
                        try:
                            data = json.loads(s.strip())
                            if isinstance(data, dict) and data.get('@type') == 'ItemList':
                                items = data.get('itemListElement', [])
                                for item in items:
                                    u = item.get('url', '')
                                    if '/recettes/' in u and '/ingredients/' not in u and '/plats-principaux/' not in u:
                                        if u not in all_urls:
                                            all_urls.append(u)
                        except:
                            pass

                print(f"📄 {ingredient} page {page}/{max_pages}: {len(all_urls)} URLs uniques")
                time.sleep(REQUEST_DELAY)
            except Exception as e:
                print(f"   ❌ {ingredient} page {page}: {e}")
                time.sleep(2)

    return all_urls


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
        # JSON-LD
        ld_match = re.search(r"<script type='application/ld\+json'>({.*?})</script>", html, re.DOTALL)
        ld = {}
        if ld_match:
            try:
                ld = json.loads(ld_match.group(1))
            except:
                pass

        # Titre
        data["title"] = ld.get("name", "")
        if not data["title"]:
            tm = re.search(r'<h1[^>]*>(.*?)</h1>', html)
            if tm: data["title"] = re.sub(r'<[^>]+>', '', tm.group(1)).strip()

        id_match = re.search(r'/recettes/(\d+)-', url)
        data["id"] = f"rc-{id_match.group(1)}" if id_match else f"rc-{hash(url)}"
        data["source_name"] = "Ricardo"

        # Image
        if ld.get("image"):
            img = ld["image"]
            data["image_url"] = img[0] if isinstance(img, list) else img

        # Temps
        prep, cook = ld.get("prepTime", ""), ld.get("cookTime", "")
        data["prep_time"] = prep.replace("PT", "").replace("M", " min").replace("H", "h ") if prep else None
        data["cook_time"] = cook.replace("PT", "").replace("M", " min").replace("H", "h ") if cook else None

        total_min = 0
        for t in [prep, cook]:
            m = re.search(r'PT?(?:(\d+)H)?(?:(\d+)M)?', t)
            if m: total_min += (int(m.group(1) or 0) * 60) + (int(m.group(2) or 0))
        if total_min:
            h, m = divmod(total_min, 60)
            data["total_time"] = f"{h}h{m} min" if h else f"{m} min"

        # Portions
        yield_match = re.search(r'Rendement[^<]*</span>\s*[^<]*?<[^>]*>([^<]+)', html, re.DOTALL)
        data["servings"] = yield_match.group(1).strip() if yield_match else ld.get("recipeYield")

        # Catégorie
        cat_match = re.search(r'Catégories?\s*</[^>]+>\s*(.+?)</section>', html, re.DOTALL)
        category = ""
        if cat_match:
            cats = re.findall(r'>([^<]+)</a>', cat_match.group(1))
            category = ", ".join(cats) if cats else ""
        data["category"] = detect_category(data["title"], category)

        # Ingrédients
        ingredients = []
        if ld.get("recipeIngredient"):
            for ing_text in ld["recipeIngredient"]:
                ing_text = ing_text.strip()
                qty, unit, name = parse_ingredient(ing_text)
                ingredients.append({
                    "original_text": ing_text, "quantity": qty, "unit": unit,
                    "ingredient": name, "section": "", "sort_order": len(ingredients),
                })

        # Fallback HTML
        if not ingredients:
            sections = re.findall(r'c-recipe-instructions--ingredients.*?<ul[^>]*>(.*?)</ul>', html, re.DOTALL)
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

        # Étapes
        steps = []
        if ld.get("recipeInstructions"):
            for inst in ld["recipeInstructions"]:
                if isinstance(inst, dict) and inst.get("text"):
                    steps.append({"step": len(steps) + 1, "text": inst["text"]})

        if not steps:
            prep_section = re.search(r'c-recipe-instructions--preparation.*?<ol[^>]*>(.*?)</ol>', html, re.DOTALL)
            if prep_section:
                items = re.findall(r'<li[^>]*>(.*?)</li>', prep_section.group(1), re.DOTALL)
                for li in items:
                    text = re.sub(r'<[^>]+>', '', li).strip()
                    if text: steps.append({"step": len(steps) + 1, "text": text})

        data["steps_raw"] = json.dumps(steps, ensure_ascii=False)

        # Rating
        rating_match = re.search(r'c-recipe-rating__value[^>]*>([\d.,]+)', html)
        data["rating"] = float(rating_match.group(1).replace(",", ".")) if rating_match else None

        # Meat type
        text = (data["title"] + " " + category + " " + data.get("category", "")).lower()
        for ing in ingredients:
            text += " " + (ing.get("original_text") or "").lower()

        if any(w in text for w in ["boeuf", "bœuf", "beef", "steak haché"]):
            data["meat_type"] = "boeuf"
        elif any(w in text for w in ["porc", "pork"]):
            data["meat_type"] = "porc"
        elif any(w in text for w in ["poulet", "poulets", "chicken"]):
            data["meat_type"] = "poulet"
        elif any(w in text for w in ["veau", "veal"]):
            data["meat_type"] = "veau"
        elif any(w in text for w in ["dinde", "dindon", "turkey"]):
            data["meat_type"] = "dinde"
        elif "haché" in text or "hache" in text:
            data["meat_type"] = "mixte"
        else:
            data["meat_type"] = "mixte"

        return data

    except Exception as e:
        print(f"   ❌ Parse: {e}")
        return None


def is_hachee(data):
    """Vérifie si une recette utilise de la viande hachée."""
    text = (data.get("title", "") + " " + data.get("category", "")).lower()
    if "haché" in text or "hache" in text or "burger" in text or "steak haché" in text:
        return True
    for ing in json.loads(data.get("ingredients_raw", "[]")):
        it = ing.get("original_text", "").lower()
        if "haché" in it or "hache" in it:
            return True
    return False


def save_recipe(db, data):
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
    rid = db.execute("SELECT id FROM recipes WHERE source_id = ?", (data.get("id"),)).fetchone()
    if not rid: return None
    rid = rid["id"]
    db.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (rid,))
    for ing in json.loads(data.get("ingredients_raw", "[]")):
        db.execute("""
            INSERT INTO recipe_ingredients (recipe_id, ingredient, quantity, unit, original_text, section, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (rid, ing.get("ingredient", ""), ing.get("quantity"),
              ing.get("unit", ""), ing.get("original_text", ""),
              ing.get("section", ""), ing.get("sort_order", 0)))
    return rid


def run_scraper(max_recipes=None):
    print("=" * 60)
    print("🍳 SCRAPER RICARDO — ricardocuisine.com")
    print("   ~1 943 recettes totales (boeuf+porc+poulet+veau)")
    print("=" * 60)

    init_db()
    db = get_db()

    # Étape 1: Récupérer toutes les URLs
    print("\n📡 Étape 1: Récupération des URLs...")
    urls = get_all_recipe_urls()
    print(f"\n📊 {len(urls)} URLs de recettes uniques trouvées")

    if max_recipes:
        urls = urls[:max_recipes]

    # Filtrer les déjà scrappées
    existing = set(r["source_id"] for r in db.execute("SELECT source_id FROM recipes WHERE source_name='Ricardo'").fetchall())

    # Étape 2: Scraper chaque recette
    print(f"\n📡 Étape 2: Scraping des recettes...")
    saved = 0
    skipped = 0
    errors = 0
    for i, url in enumerate(urls, 1):
        id_match = re.search(r'/recettes/(\d+)-', url)
        rid = f"rc-{id_match.group(1)}" if id_match else None
        if rid and rid in existing:
            skipped += 1
            continue

        data = scrape_recipe(url)
        if data and data.get("title"):
            if is_hachee(data):
                rid = save_recipe(db, data)
                if rid:
                    saved += 1
                    print(f"[{i}/{len(urls)}] ✅ {data['title'][:45]}")
                else:
                    errors += 1
                    print(f"[{i}/{len(urls)}] ❌ Sauvegarde")
            else:
                skipped += 1
        else:
            errors += 1

        db.commit()
        if i % 5 == 0:
            print(f"   → {saved} sauvegardées, {skipped} skip, {errors} erreurs")
        time.sleep(REQUEST_DELAY + random.uniform(0, 0.5))

    db.close()
    print(f"\n{'=' * 60}")
    print(f"✅ Terminé: {saved} sauvegardées, {skipped} skip, {errors} erreurs")
    print(f"{'=' * 60}")
    return {"saved": saved, "skipped": skipped, "errors": errors}


if __name__ == "__main__":
    max_rec = None
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        max_rec = int(sys.argv[idx + 1])
    run_scraper(max_recipes=max_rec)
