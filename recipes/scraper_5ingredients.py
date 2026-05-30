#!/usr/bin/env python3
"""
Scraper — 5ingredients15minutes.com + recettesjecuisine.com
Focus: viande hachée (boeuf, porc, poulet, veau, dinde)
"""
import sys, os, re, json, time, random, requests
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from recipes.schema import get_db, init_db, detect_category, parse_ingredient

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
    "Accept-Language": "fr-CA,fr;q=0.9,en;q=0.8",
}
DELAY = 0.8  # seconds between requests

# Sites config: (name, base_url, categories as [(slug, meat_type)])
SITES = [
    ("5 ingrédients 15 minutes", "https://www.5ingredients15minutes.com", [
        ("/fr/recettes/plats-principaux/viande-hachee/", "mixte"),
        ("/fr/recettes/plats-principaux/boeuf/", "boeuf"),
        ("/fr/recettes/plats-principaux/porc/", "porc"),
        ("/fr/recettes/plats-principaux/poulet/", "poulet"),
    ]),
    ("Je Cuisine", "https://www.recettesjecuisine.com", [
        ("/fr/recettes/plats-principaux/boeuf/", "boeuf"),
        ("/fr/recettes/plats-principaux/porc/", "porc"),
        ("/fr/recettes/plats-principaux/poulet/", "poulet"),
    ]),
]

# Keywords suggesting ground meat recipe
GROUND_MEAT_KW = [
    "haché", "hache", "boulette", "pain de viande", "pain a viande",
    "pain à viande", "burger", "galette", "steak haché", "chili",
    "lasagne", "casserole", "sauce à spaghetti", "bolognaise", "bolognese",
    "pâté chinois", "pate chinois", "tourtière", "cigare au chou",
    "chou farci", "taco",
]

def is_ground_meat_candidate(title, url):
    """Quick check if a recipe might contain ground meat."""
    text = (title + " " + url).lower()
    # Direct ground meat references
    if any(kw in text for kw in GROUND_MEAT_KW):
        return True
    # URL-based meat check
    if any(m in url.lower() for m in ["boeuf", "porc", "poulet", "veau", "dinde", "viande"]):
        return True
    return False

def scrape_listing(site_name, base_url, categories, max_pages=20):
    """Scrape listing pages and find candidate recipes."""
    recipes = []
    seen = set()
    
    for slug, meat_type in categories:
        print(f"\n📂 {site_name}: {slug} ({meat_type})")
        for page in range(1, max_pages + 1):
            url = f"{base_url}{slug}" if page == 1 else f"{base_url}{slug}page/{page}/"
            try:
                resp = requests.get(url, headers=HEADERS, timeout=15)
                resp.raise_for_status()
            except Exception as e:
                if page > 1:
                    print(f"   → Fin pagination page {page}: {e}")
                else:
                    print(f"   ❌ {e}")
                break
            
            html = resp.text
            articles = re.findall(r'<article[^>]*>(.*?)</article>', html, re.DOTALL)
            page_recipes = 0
            
            for art in articles:
                link_m = re.search(r'href=\"([^\"]+?)\"', art)
                if not link_m:
                    continue
                url = link_m.group(1)
                if '?gallery=' in url or 'gallery=' in url or url in seen:
                    continue
                
                # Get title
                title_m = re.search(r'class=\"tile-article__title\"[^>]*>(.*?)</h4>', art, re.DOTALL)
                if title_m:
                    title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip()
                else:
                    title_m = re.search(r'title=\"([^\"]+?)\"', art)
                    if not title_m:
                        continue
                    title = title_m.group(1).strip()
                
                # Skip gallery/list pages
                if re.match(r'^\d+\s+recettes?', title.lower()):
                    continue
                
                # Ground meat quick check
                if not is_ground_meat_candidate(title, url):
                    continue
                
                # Image
                img_m = re.search(r'<img[^>]+src=\"([^\"]+?)\"', art)
                img = img_m.group(1) if img_m else None
                
                seen.add(url)
                recipes.append({
                    "source_url": url,
                    "title": title,
                    "image_url": img,
                    "meat_type": meat_type,
                })
                page_recipes += 1
            
            print(f"   Page {page}: +{page_recipes} (total: {len(recipes)})")
            if len(articles) < 10:
                break
            time.sleep(DELAY + random.uniform(0, 0.3))
    
    return recipes

def scrape_detail(recipe, source_name):
    """Scrape a single recipe page for full details."""
    try:
        resp = requests.get(recipe["source_url"], headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        return None
    
    html = resp.text
    data = dict(recipe)
    data["source_name"] = source_name
    
    # ── Category from meta ──
    cat_m = re.search(r'itemprop=\"recipeCategory\"[^>]*content=\"([^\"]+?)\"', html)
    category = cat_m.group(1) if cat_m else ""
    data["category"] = detect_category(recipe["title"], category)
    
    # ── Image (from meta if not available) ──
    if not data.get("image_url"):
        img_m = re.search(r'<meta[^>]+itemprop=\"image\"[^>]+content=\"([^\"]+?)\"', html)
        if img_m:
            data["image_url"] = img_m.group(1)
    
    # ── Times & Servings from HTML ──
    time_items = re.findall(
        r'<li[^>]*class=\"recipe__informations--single\"[^>]*>'
        r'.*?<span class=\"title\">([^<]+)</span>'
        r'.*?<span class=\"data\"[^>]*>([^<]+)</span>',
        html, re.DOTALL
    )
    for title, value in time_items:
        t = title.strip().lower()
        v = value.strip()
        if any(x in t for x in ['préparation', 'preparation']):
            data["prep_time"] = v
        elif 'cuisson' in t:
            data["cook_time"] = v
        elif any(x in t for x in ['portion', 'portions']):
            data["servings"] = v
    
    # ── Rating ──
    vote_total_m = re.search(r'data-vote-total=\"(\d+)\"', html)
    vote_total = int(vote_total_m.group(1)) if vote_total_m else 0
    if vote_total > 0:
        avg_m = re.search(r'data-vote-average=\"([\d.]+)\"', html)
        data["rating"] = float(avg_m.group(1)) if avg_m else None
    else:
        data["rating"] = None  # No votes -> no rating
    
    # ── Ingredients ──
    ingredients = []
    ing_section = re.search(
        r'Ingrédients</h3>\s*<div[^>]*>\s*(.*?)(?=<h3)',
        html, re.DOTALL | re.IGNORECASE
    )
    
    if ing_section:
        ing_html = ing_section.group(1)
        sort_order = 0
        current_section = ""
        
        # Find all sections with their ul lists
        # Pattern: optional <p>section title</p> followed by <ul>items</ul>
        sections = re.findall(
            r'(?:<(?:p|strong)[^>]*>(.*?)</(?:p|strong)>)?\s*<ul[^>]*>(.*?)</ul>',
            ing_html, re.DOTALL
        )
        
        for p_text, ul_content in sections:
            if p_text:
                section_text = re.sub(r'<[^>]+>', '', p_text).strip()
                if any(x in section_text.lower() for x in ['pour ', 'sauce', 'garniture', 'garni', 'fromage']):
                    current_section = section_text
            
            items = re.findall(r'<li>(.*?)</li>', ul_content, re.DOTALL)
            for item in items:
                text = re.sub(r'<[^>]+>', '', item).strip()
                if text:
                    qty, unit, name = parse_ingredient(text)
                    ingredients.append({
                        "original_text": text, "quantity": qty, "unit": unit,
                        "ingredient": name, "section": current_section,
                        "sort_order": sort_order,
                    })
                    sort_order += 1
    
    # Fallback: loose ul in ingredient area
    if not ingredients and ing_section:
        for ul in re.findall(r'<ul>(.*?)</ul>', ing_section.group(1), re.DOTALL):
            for item in re.findall(r'<li>(.*?)</li>', ul, re.DOTALL):
                text = re.sub(r'<[^>]+>', '', item).strip()
                if text:
                    qty, unit, name = parse_ingredient(text)
                    ingredients.append({
                        "original_text": text, "quantity": qty, "unit": unit,
                        "ingredient": name, "section": "",
                        "sort_order": len(ingredients),
                    })
    
    data["ingredients_raw"] = json.dumps(ingredients, ensure_ascii=False)
    
    # ── Steps ──
    steps = []
    steps_section = re.search(
        r'Étapes</h3>\s*<div[^>]*>\s*(.*?)(?=<h3)',
        html, re.DOTALL | re.IGNORECASE
    )
    
    if steps_section:
        steps_html = steps_section.group(1)
        step_num = 0
        for ol in re.findall(r'<ol[^>]*>(.*?)</ol>', steps_html, re.DOTALL):
            for item in re.findall(r'<li>(.*?)</li>', ol, re.DOTALL):
                text = re.sub(r'<[^>]+>', '', item).strip()
                if text:
                    step_num += 1
                    steps.append({"step": step_num, "text": text})
        
        # Fallback: paragraphs for step-like content
        if not steps:
            for p in re.findall(r'<p>(.*?)</p>', steps_html, re.DOTALL):
                text = re.sub(r'<[^>]+>', '', p).strip()
                if text and len(text) > 30:
                    step_num += 1
                    steps.append({"step": step_num, "text": text})
    
    data["steps_raw"] = json.dumps(steps, ensure_ascii=False)
    
    # ── Source ID ──
    url_path = recipe["source_url"].replace("https://", "").replace("http://", "")
    data["id"] = f"pp-{abs(hash(url_path)) % 10**8}"
    
    return data

def save_recipe(db, data):
    """Save recipe to database."""
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
    
    recipe_id = db.execute(
        "SELECT id FROM recipes WHERE source_id = ?", (data.get("id"),)
    ).fetchone()
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

def run_site(name, base_url, categories, max_recipes=None, skip_first=0):
    """Run full scrape for one site."""
    print(f"\n{'='*60}")
    print(f"🍳 {name}")
    print(f"{'='*60}")
    
    init_db()
    db = get_db()
    
    # Phase 1: listings
    all_recipes = scrape_listing(name, base_url, categories)
    print(f"\n📊 Total candidates: {len(all_recipes)} ground meat recipe candidates")
    
    if max_recipes:
        all_recipes = all_recipes[skip_first:skip_first + max_recipes]
        print(f"   (batch {skip_first}-{skip_first + max_recipes})")
    
    # Phase 2: details
    saved = 0
    errors = 0
    skipped_no_ingredients = 0
    
    for i, recipe in enumerate(all_recipes, 1):
        short_title = recipe['title'][:55]
        print(f"\n[{skip_first + i}/{len(all_recipes)}] {short_title}")
        
        data = scrape_detail(recipe, name)
        if not data:
            errors += 1
            print(f"   ❌ Erreur chargement")
            time.sleep(2)
            continue
        
        # Check it actually has ground meat ingredients
        ings = json.loads(data.get("ingredients_raw", "[]"))
        has_ground_meat = False
        meat_keywords = ["haché", "hachée", "haches", "steak haché"]
        for ing in ings:
            txt = (ing.get("original_text", "") + " " + ing.get("ingredient", "")).lower()
            if any(kw in txt for kw in meat_keywords):
                has_ground_meat = True
                break
        
        # Also check title for ground meat dishes even if ingredients don't explicitly say "haché"
        title_lower = data.get("title", "").lower()
        title_dishes = ["boulette", "pain de viande", "pain a viande", "pain à viande",
                        "chili", "tourtière", "pâté chinois", "pate chinois",
                        "cigare au chou", "chou farci", "burger", "galette"]
        
        if not has_ground_meat:
            if any(d in title_lower for d in title_dishes):
                has_ground_meat = True
        
        if not has_ground_meat:
            skipped_no_ingredients += 1
            print(f"   ⏭️ Pas de viande hachée dans les ingrédients")
            time.sleep(DELAY + random.uniform(0, 0.3))
            continue
        
        # Rating filter
        rating = data.get("rating")
        if rating is None:
            print(f"   ℹ️ Aucune évaluation, mais sauvegarde quand même")
            # Still save since no ratings exist on these sites
        
        rid = save_recipe(db, data)
        if rid:
            saved += 1
            rating_str = f"⭐{rating}" if rating else "📝"
            print(f"   ✅ ID {rid} — {data.get('category', '?')} — {rating_str}")
        else:
            errors += 1
            print(f"   ❌ Sauvegarde")
        
        db.commit()
        time.sleep(DELAY + random.uniform(0, 0.5))
    
    db.close()
    
    print(f"\n{'='*60}")
    print(f"✅ {name}")
    print(f"   Sauvegardées: {saved}")
    print(f"   Pas viande hachée: {skipped_no_ingredients}")
    print(f"   Erreurs: {errors}")
    
    return {"saved": saved, "skipped": skipped_no_ingredients, "errors": errors}

def main():
    max_rec = None
    skip = 0
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        max_rec = int(sys.argv[idx + 1])
    if "--skip" in sys.argv:
        idx = sys.argv.index("--skip")
        skip = int(sys.argv[idx + 1])
    
    results = {}
    for name, base, cats in SITES:
        results[name] = run_site(name, base, cats, max_rec, skip)
    
    print(f"\n{'='*60}")
    print("📊 RÉSUMÉ FINAL")
    print(f"{'='*60}")
    total = sum(r["saved"] for r in results.values())
    total_skipped = sum(r["skipped"] for r in results.values())
    total_errors = sum(r["errors"] for r in results.values())
    print(f"✅ Sauvegardées: {total}")
    print(f"⏭️  Pas viande hachée: {total_skipped}")
    print(f"❌ Erreurs: {total_errors}")
    print(f"📁 DB: {os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'recipes.db')}")

if __name__ == "__main__":
    main()
