#!/usr/bin/env python3
"""
Scraper de recettes — RecettesQuébécoises.com
Focus: viande hachée (boeuf, porc, poulet, veau, dinde)
Les recettes de cuisine ne sont pas protégeables par le droit d'auteur (biens communs).
"""
import sys
import os
import re
import json
import time
import random
import requests
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from recipes.schema import (
    get_db, init_db, detect_meat_type, detect_category, parse_ingredient
)

BASE_URL = "https://www.recettesquebecoises.com"
REQUEST_DELAY = 1.5

SECTIONS = [
    ("viande-boeuf-hache", "boeuf"),
    ("viande-porc-hache", "porc"),
    ("viande-poulet-hache-et-dindon-hache", "poulet"),
    ("viande-veau-hache", "veau"),
]


def get_headers():
    return {
        "User-Agent": random.choice([
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0",
        ]),
        "Accept-Language": "fr-CA,fr;q=0.9,en;q=0.8",
    }


def _get_section_between(html, section_name):
    """Trouve le contenu entre <h2>section_name</h2> et le prochain <h2>."""
    pattern = re.compile(
        r'<h[23][^>]*>' + re.escape(section_name) + r'</h[23]>(.*?)(?=<h[23]|$)',
        re.DOTALL | re.IGNORECASE
    )
    m = pattern.search(html)
    return m.group(1) if m else None


def parse_listing_page(html, meat_type):
    """Parse une page de listing pour extraire les infos des recettes."""
    recipes = []
    items = re.findall(r'<li class="q">(.*?)</li>', html, re.DOTALL)
    seen = set()
    for item in items:
        title_m = re.search(r'title="([^"]+)"', item)
        href_m = re.search(r'href="([^"]+)"', item)
        img_m = re.search(r'background-image:url\(([^)]+)\)', item)
        if title_m and href_m:
            rid_m = re.search(r'/recette/(\d+)-', href_m.group(1))
            rid = rid_m.group(1) if rid_m else None
            if rid and rid not in seen:
                seen.add(rid)
                recipes.append({
                    "id": f"rq-{rid}",
                    "source_url": href_m.group(1),
                    "title": title_m.group(1).strip(),
                    "meat_type": meat_type,
                    "source_id": rid,
                    "image_url": img_m.group(1) if img_m else None,
                })
    return recipes


def scrape_category(slug, meat_type, max_pages=7):
    """Scrape toutes les recettes d'une catégorie."""
    recipes = []
    for page in range(1, max_pages + 1):
        url = f"{BASE_URL}/section/{slug}?_par=10&_pgn={page}"
        try:
            resp = requests.get(url, headers=get_headers(), timeout=15)
            resp.raise_for_status()
            page_recipes = parse_listing_page(resp.text, meat_type)
            recipes.extend(page_recipes)
            print(f"   → {len(page_recipes)} recettes (total: {len(recipes)})")
            time.sleep(REQUEST_DELAY + random.uniform(0, 0.5))
            if len(page_recipes) < 10:
                break
        except Exception as e:
            print(f"   ❌ Erreur page {page}: {e}")
            time.sleep(3)
    return recipes


def scrape_recipe_detail(recipe):
    """Scrape une page de recette individuelle."""
    try:
        resp = requests.get(recipe["source_url"], headers=get_headers(), timeout=15)
        resp.raise_for_status()
        return parse_recipe_page(resp.text, recipe)
    except Exception as e:
        print(f"   ❌ Détail: {recipe['source_url'][:60]}... — {e}")
        return None


def parse_recipe_page(html, recipe):
    """Extrait les détails d'une page de recette."""
    data = dict(recipe)

    # ── Catégorie ──
    cat_match = re.search(r'Catégorie</strong>.*?<a[^>]*>([^<]+)</a>', html, re.DOTALL)
    category = cat_match.group(1).strip() if cat_match else ""
    data["category"] = detect_category(recipe["title"], category)

    # ── Source ──
    src_match = re.search(r'Source</strong>\s*([^<]+?)\s*</span>', html, re.DOTALL)
    data["source_name"] = src_match.group(1).strip() if src_match else ""

    # ── Ingrédients ──
    ingredients = []
    ing_section = _get_section_between(html, "Ingrédients")
    if ing_section:
        # Chercher sous-sections (sauce, garniture) avec leurs <ul>
        subsections = re.finditer(
            r'<(?:h2|h3)[^>]*>(.*?)</(?:h2|h3)>\s*<ul[^>]*>(.*?)</ul>',
            ing_section, re.DOTALL | re.IGNORECASE
        )
        found_any = False
        for m in subsections:
            section_title = re.sub(r'<[^>]+>', '', m.group(1)).strip().lower()
            section_title = re.sub(r'\s+', ' ', section_title.strip("*"))

            if any(nis in section_title for nis in (
                "photo", "préparation", "preparation", "commentaire",
                "notes", "actions", "commentaires", "concours", "signaler"
            )):
                continue

            current_section = "" if section_title in ("ingrédients", "ingredients") else section_title
            list_items = re.findall(r'<li[^>]*>(.*?)</li>', m.group(2), re.DOTALL)
            for li in list_items:
                text = re.sub(r'<[^>]+>', '', li).strip()
                if text:
                    found_any = True
                    qty, unit, name = parse_ingredient(text)
                    ingredients.append({
                        "original_text": text, "quantity": qty, "unit": unit,
                        "ingredient": name, "section": current_section,
                        "sort_order": len(ingredients),
                    })

        # Fallback: <ul> direct dans la section
        if not found_any:
            for ul in re.findall(r'<ul[^>]*>(.*?)</ul>', ing_section, re.DOTALL):
                for li in re.findall(r'<li[^>]*>(.*?)</li>', ul, re.DOTALL):
                    text = re.sub(r'<[^>]+>', '', li).strip()
                    if text:
                        qty, unit, name = parse_ingredient(text)
                        ingredients.append({
                            "original_text": text, "quantity": qty, "unit": unit,
                            "ingredient": name, "section": "", "sort_order": len(ingredients),
                        })

    data["ingredients_raw"] = json.dumps(ingredients, ensure_ascii=False)

    # ── Étapes ──
    steps = []
    prep_section = _get_section_between(html, "Préparation")
    if prep_section:
        step_num = 0
        for ol in re.findall(r'<ol[^>]*>(.*?)</ol>', prep_section, re.DOTALL):
            for li in re.findall(r'<li[^>]*>(.*?)</li>', ol, re.DOTALL):
                step_text = re.sub(r'<[^>]+>', '', li).strip()
                if step_text:
                    step_num += 1
                    steps.append({"step": step_num, "text": step_text})
    data["steps_raw"] = json.dumps(steps, ensure_ascii=False)

    # ── Temps et portions ──
    cmt = re.search(r'Commentaire du\s*cuisin(?:er|ier)([\s\S]*?)(?=<h[23]|$)', html, re.DOTALL | re.IGNORECASE)
    if cmt:
        ct = re.sub(r'<[^>]+>', '\n', cmt.group(1))
        pt = re.search(r'Temps de préparation\s*:\s*([^\n]+)', ct, re.IGNORECASE)
        data["prep_time"] = pt.group(1).strip() if pt else None
        ct2 = re.search(r'Temps de cuisson\s*:\s*([^\n]+)', ct, re.IGNORECASE)
        data["cook_time"] = ct2.group(1).strip() if ct2 else None
        tt = re.search(r'Temps de pr[ée]t\s*:\s*([^\n]+)', ct, re.IGNORECASE)
        data["total_time"] = tt.group(1).strip() if tt else None
        sv = re.search(r'(\d+\s*(?:à|–|-)\s*\d+|\d+)\s*(?:Portions?|portions?)', ct, re.IGNORECASE)
        data["servings"] = sv.group(1).strip() + " portions" if sv else None

    # ── Rating ──
    data["rating"] = float(len(re.findall(r'★', html))) if re.search(r'★', html) else None

    return data


def save_recipe(db, data):
    """Sauvegarde une recette dans la base."""
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


def run_scraper(max_recipes=None, skip_first=0):
    """Pipeline complet: scrape listings → détails → sauvegarde."""
    print("=" * 60)
    print("🍳 SCRAPER DE RECETTES — RecettesQuébécoises.com")
    print("   Focus: viande hachée")
    print("=" * 60)

    init_db()
    db = get_db()

    all_recipes = []
    for slug, meat in SECTIONS:
        recipes = scrape_category(slug, meat)
        all_recipes.extend(recipes)
        print(f"   ✅ {len(recipes)} recettes ({meat})")

    print(f"\n📊 Total: {len(all_recipes)} recettes à scraper")
    if max_recipes:
        all_recipes = all_recipes[skip_first:skip_first + max_recipes]
        print(f"   (lot {skip_first}-{skip_first + max_recipes})")

    saved = 0
    errors = 0
    for i, recipe in enumerate(all_recipes, 1):
        print(f"[{skip_first + i}/{len(all_recipes)}] {recipe['title'][:50]}...")
        data = scrape_recipe_detail(recipe)
        if data:
            rid = save_recipe(db, data)
            if rid:
                saved += 1
                print(f"   ✅ ID {rid}")
            else:
                errors += 1
                print(f"   ❌ Sauvegarde")
        else:
            errors += 1
        db.commit()
        time.sleep(REQUEST_DELAY + random.uniform(0, 1))

    db.close()
    print(f"\n{'='*60}")
    print(f"✅ {saved} recettes, {errors} erreurs")
    return {"saved": saved, "errors": errors}


if __name__ == "__main__":
    max_rec = None
    skip = 0
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        max_rec = int(sys.argv[idx + 1])
    if "--skip" in sys.argv:
        idx = sys.argv.index("--skip")
        skip = int(sys.argv[idx + 1])
    run_scraper(max_recipes=max_rec, skip_first=skip)
