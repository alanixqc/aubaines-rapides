#!/usr/bin/env python3
"""
Scraper Ricardo v4 — extrait les recettes du JSON embarqué dans renderReactBridge.
Chaque objet recette est en JSON strict (clés avec guillemets).
"""
import sys, os, re, json, time, random, sqlite3, requests
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from recipes.schema import get_db, init_db, detect_meat_type, detect_category, parse_ingredient

BASE = "https://www.ricardocuisine.com"
REQUEST_DELAY = 1.5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
    "Accept-Language": "fr-CA,fr;q=0.9,en;q=0.8",
}

GROUND_MEAT_RE = re.compile(
    r'(hach[ée]|viande\s*hach[ée]|boulettes|pain\s*de\s*viande|pât[ée]\s*chinois|'
    r'hamburger|smash\s*burger|bolognaise|bolognese|'
    r'macaronis.*(?:viande|b[oœ]uf|bœuf|boeuf)|'
    r'tortillas\s*farcies|tacos\s*au\s*b[oœ]uf|'
    r'pizzas?\s*cheeseburger|p.tes\s*[àa]\s*la\s*turque|'
    r'soupe.lasagne|lasagne|chili|'
    r'feuillet[ée]s\s*de\s*pain\s*de\s*viande|'
    r'poivrons?\s*farci|macaroni.*fromage|'
    r'cretons|farce|boulette|'
    r'ground\s*(?:beef|pork|chicken|turkey|veal)|'
    r'meatball|meat\s*loa[fv]|'
    r'shepherd.s\s*pie|cottage\s*pie|'
    r'stuffed\s*(?:pepper|zucchini)|beef\s*and\s*cheese)',
    re.IGNORECASE | re.UNICODE
)

CATEGORIES = [
    ("boeuf", "/en/recipes/ingredients/beef"),
    ("porc", "/en/recipes/ingredients/pork"),
    ("poulet", "/en/recipes/ingredients/chicken"),
    ("veau", "/en/recipes/ingredients/veal"),
]


def extract_recipes_from_page(html):
    """Extract individual recipe JSON objects from the renderReactBridge data."""
    recipes = []
    
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    for s in scripts:
        if 'renderReactBridge' not in s:
            continue
        
        # Match recipe objects: {"id":NNNN,"uniqueId":... "hideFromPersonalRecipes":null}
        # Using lazy .*? with DOTALL to handle nested braces in "times":{...}
        pattern = re.compile(
            r'\{"id":(\d+),"uniqueId":.*?"hideFromPersonalRecipes":(?:null|true|false)\}',
            re.DOTALL
        )
        for m in pattern.finditer(s):
            try:
                obj = json.loads(m.group(0))
                if 'title' in obj and 'ratingTotal' in obj:
                    recipes.append(obj)
            except json.JSONDecodeError:
                continue
        
        if recipes:
            break
    
    return recipes


def scrape_category(cat_key, en_url, min_votes=5, max_pages=20):
    """Scrape all pages of a category, filter by ground meat + votes."""
    all_items = []
    seen_ids = set()
    
    print(f"\n📂 {cat_key} — {BASE}{en_url}")
    
    for page in range(1, max_pages + 1):
        url = f"{BASE}{en_url}?currentPage={page}"
        
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"   ❌ Page {page}: {e}")
            break
        
        recipes = extract_recipes_from_page(resp.text)
        
        if not recipes:
            print(f"   ⏹ Arrêt page {page} (aucune recette)")
            break
        
        page_matches = 0
        for item in recipes:
            rid = str(item.get("id", ""))
            if not rid or rid in seen_ids:
                continue
            seen_ids.add(rid)
            
            title = item.get("title", "")
            rating_total = item.get("ratingTotal", 0) or 0
            
            # Filtrer: viande hachée ET votes >= min_votes
            if not GROUND_MEAT_RE.search(title):
                continue
            if rating_total < min_votes:
                continue
            
            all_items.append({
                "recipe_id": f"rc-{rid}",
                "title": title,
                "id": rid,
                "url": f"{BASE}/en/recipes/{item.get('url', '')}",
                "image_url": item.get("image"),
                "description": item.get("description", ""),
                "rating_avg": item.get("ratingAvg", 0) or 0,
                "rating_total": rating_total,
                "price_per_portion": item.get("pricePerPortion"),
                "price_range": item.get("priceRange", 1),
                "time_preparation": item.get("timePreparation", ""),
                "time_total": item.get("timeTotal", ""),
                "meat_type": cat_key,
                "author": item.get("author"),
                "is_exclusive": item.get("isExclusive", False),
            })
            page_matches += 1
        
        if page_matches:
            plural = "s" if page_matches > 1 else ""
            print(f"   📄 Page {page}: {page_matches} recette{plural}")
        
        if len(recipes) < 24:
            print(f"   ⏹ Dernière page ({len(recipes)} items)")
            break
        
        time.sleep(REQUEST_DELAY)
    
    print(f"   ✅ Total: {len(all_items)} recettes avec viande hachée")
    for item in all_items[:10]:
        print(f"      → {item['title'][:55]:55s} ⭐{item['rating_avg']} ({item['rating_total']} votes)")
    if len(all_items) > 10:
        print(f"      ... + {len(all_items)-10} autres")
    return all_items


def scrape_recipe_detail(url, item):
    """Fetch and parse a recipe detail page."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        html = resp.text
        
        if "Cette page est introuvable" in html or "This page cannot be found" in html:
            return None
        
        data = dict(item)
        
        # Rating from detail page
        rm = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:/5)?\s*\((\d+)\s*votes?\)', html, re.IGNORECASE)
        if rm:
            data["rating_avg"] = float(rm.group(1).replace(",", "."))
            data["rating_total"] = int(rm.group(2))
        
        # Times
        pm = re.search(r'(?:Préparation|Prep)\s*:?\s*([^<|]+?)(?:\s*\||<|\n)', html, re.IGNORECASE)
        data["time_preparation"] = pm.group(1).strip() if pm else data.get("time_preparation")
        
        cm = re.search(r'(?:Cuisson|Cook)\s*:?\s*([^<|]+?)(?:\s*\||<|\n)', html, re.IGNORECASE)
        data["time_cooking"] = cm.group(1).strip() if cm else None
        
        tm = re.search(r'(?:Temps total|Total)\s*:?\s*([^<|]+?)(?:\s*\||<|\n)', html, re.IGNORECASE)
        data["time_total"] = tm.group(1).strip() if tm else data.get("time_total")
        
        # Servings
        sv = re.search(r'(?:Portions?|Servings?|Donne|Yields?)\s*:?\s*([^<]+?)(?:\s*\||<|\n)', html, re.IGNORECASE)
        data["servings"] = sv.group(1).strip() if sv else None
        if not data.get("servings"):
            sv = re.search(r'(\d+)\s*(?:Portions?|servings?|personnes?)', html, re.IGNORECASE)
            data["servings"] = sv.group(1) + " portions" if sv else None
        
        # Subcategory from breadcrumbs
        sub = re.search(r'Recettes?\s*(?:>\s*|»\s*)([^>»]+)', html)
        data["subcategory"] = sub.group(1).strip() if sub else ""
        
        # Ingredients
        ingredients = []
        for sn in ["Ingrédients", "Ingredients"]:
            section = _get_section_between(html, sn)
            if section:
                for li in re.findall(r'<li[^>]*>(.*?)</li>', section, re.DOTALL):
                    text = re.sub(r'<[^>]+>', '', li).strip()
                    if text and not any(c in text for c in ["★", "☆"]):
                        qty, unit, name = parse_ingredient(text)
                        ingredients.append({
                            "original_text": text, "quantity": qty, "unit": unit,
                            "ingredient": name, "section": "", "sort_order": len(ingredients),
                        })
            if ingredients:
                break
        data["ingredients_raw"] = json.dumps(ingredients, ensure_ascii=False)
        
        # Steps
        steps = []
        for sn in ["Préparation", "Preparation"]:
            section = _get_section_between(html, sn)
            if section:
                for ol in re.findall(r'<ol[^>]*>(.*?)</ol>', section, re.DOTALL):
                    step_num = 0
                    for li in re.findall(r'<li[^>]*>(.*?)</li>', ol, re.DOTALL):
                        text = re.sub(r'<[^>]+>', '', li).strip()
                        text = re.sub(r'^Step\s+\d+\s*[:.–-]?\s*', '', text, flags=re.IGNORECASE)
                        if text:
                            step_num += 1
                            steps.append({"step": step_num, "text": text})
                if steps:
                    break
        data["steps_raw"] = json.dumps(steps, ensure_ascii=False)
        
        return data
    except Exception as e:
        print(f"   ❌ Détail: {url[:60]} — {e}")
        return None


def _get_section_between(html, section_name):
    for pat in [
        rf'<h[23][^>]*>\s*{re.escape(section_name)}\s*</h[23]>(.*?)(?=<h[23]|<footer|</div>\s*<div[^>]*class="[^"]*related|<div[^>]*id="[^"]*suggestion|$)',
    ]:
        m = re.search(pat, html, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def save_recipe(db, data):
    source_id = data.get("recipe_id")
    if not source_id:
        return None
    
    db.execute("""
        INSERT OR REPLACE INTO recipes
        (source_id, title, category, subcategory, meat_type, source_name,
         source_url, image_url, prep_time, cook_time, total_time,
         servings, rating, rating_count, ingredients_raw, steps_raw, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        source_id,
        data.get("title", ""),
        detect_category(data.get("title", ""), data.get("subcategory", "")),
        data.get("subcategory", ""),
        data.get("meat_type", ""),
        "Ricardo",
        data.get("url", ""),
        data.get("image_url"),
        data.get("time_preparation"),
        data.get("time_cooking"),
        data.get("time_total"),
        data.get("servings"),
        data.get("rating_avg"),
        data.get("rating_total", 0),
        data.get("ingredients_raw", "[]"),
        data.get("steps_raw", "[]"),
        json.dumps({"scraped_at": datetime.now().isoformat(), "source": "ricardocuisine.com"}, ensure_ascii=False),
    ))
    
    row = db.execute("SELECT id FROM recipes WHERE source_id = ?", (source_id,)).fetchone()
    if not row:
        return None
    recipe_id = row["id"]
    
    db.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
    for ing in json.loads(data.get("ingredients_raw", "[]")):
        db.execute("""
            INSERT INTO recipe_ingredients (recipe_id, ingredient, quantity, unit, original_text, section, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (recipe_id, ing.get("ingredient", ""), ing.get("quantity"),
              ing.get("unit", ""), ing.get("original_text", ""),
              ing.get("section", ""), ing.get("sort_order", 0)))
    
    return recipe_id


def run_ricardo_scraper(min_votes=5, skip_details=False, max_per_cat=None):
    print("=" * 65)
    print("🍳 SCRAPER RICARDO v4")
    print(f"   Filtre: viande hachée, ≥{min_votes} votes")
    print("=" * 65)
    
    init_db()
    db = get_db()
    
    try:
        db.execute("SELECT rating_count FROM recipes LIMIT 1")
    except sqlite3.OperationalError:
        db.execute("ALTER TABLE recipes ADD COLUMN rating_count INTEGER DEFAULT 0")
        db.commit()
    
    all_items = []
    for cat_key, en_url in CATEGORIES:
        items = scrape_category(cat_key, en_url, min_votes=min_votes)
        if max_per_cat and len(items) > max_per_cat:
            items = items[:max_per_cat]
        all_items.extend(items)
    
    print(f"\n📊 TOTAL LISTINGS: {len(all_items)} recettes à traiter")
    
    if skip_details:
        saved = 0
        for item in all_items:
            item["ingredients_raw"] = "[]"
            item["steps_raw"] = "[]"
            if save_recipe(db, item):
                saved += 1
        db.commit()
        print(f"✅ {saved} recettes (sans détails)")
        return {"saved": saved, "errors": 0, "total": len(all_items)}
    
    saved = 0
    errors = 0
    for i, item in enumerate(all_items, 1):
        print(f"\n[{i}/{len(all_items)}] {item['title'][:60]} (⭐{item['rating_avg']} — {item['rating_total']} votes)...")
        
        data = scrape_recipe_detail(item["url"], item)
        if not data:
            errors += 1
            print(f"   ❌ Abandon")
            continue
        
        rid = save_recipe(db, data)
        if rid:
            saved += 1
            ings = len(json.loads(data.get("ingredients_raw", "[]")))
            print(f"   ✅ ID {rid} ({ings} ingrédients)")
        else:
            errors += 1
            print(f"   ❌ Sauvegarde")
        
        db.commit()
        time.sleep(REQUEST_DELAY)
    
    db.close()
    print(f"\n{'='*65}")
    print(f"✅ {saved} recettes, {errors} erreurs")
    return {"saved": saved, "errors": errors, "total": len(all_items)}


if __name__ == "__main__":
    min_v = 5
    skip = False
    mpc = None
    if "--min-votes" in sys.argv:
        idx = sys.argv.index("--min-votes")
        min_v = int(sys.argv[idx + 1])
    if "--skip-details" in sys.argv:
        skip = True
    if "--max-per-cat" in sys.argv:
        idx = sys.argv.index("--max-per-cat")
        mpc = int(sys.argv[idx + 1])
    
    result = run_ricardo_scraper(min_votes=min_v, skip_details=skip, max_per_cat=mpc)
    print(json.dumps(result, indent=2))
