#!/usr/bin/env python3
"""
PC Express Meat Scraper (INDÉPENDANT de Flipp)
===============================================
Scrape les données de viande/poisson des épiceries du groupe Loblaws
via le site PC Express (Maxi, Provigo, L'Inter-Marché).

Utilise Playwright pour charger les pages et extraire les prix du DOM.
NE dépend PAS de Flipp/flippback/wishabi.

Usage:
    python scraper_pcexpress.py --banner maxi --output data.json
    python scraper_pcexpress.py --banner provigo --db
    python scraper_pcexpress.py --banner maxi --postal J7Z1J6
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, date
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from db.schema import get_db, get_week_start
    HAS_DB = True
except ImportError:
    HAS_DB = False

# ─── Configuration ───────────────────────────────────────────────────────────

BANNER_CONFIG = {
    "maxi": {
        "name": "Maxi",
        "domain": "maxi.ca",
        "banner_id": "maxi",
        "locale": "fr",
        "cat_url": "https://www.maxi.ca/fr/viande-poeisson/c/LC_0301",
    },
    "provigo": {
        "name": "Provigo",
        "domain": "provigo.ca",
        "banner_id": "provigo",
        "locale": "fr",
        "cat_url": "https://www.provigo.ca/fr/viande-poeisson/c/LC_0301",
    },
    "intermarche": {
        "name": "L'Inter-Marché",
        "domain": "intermarche.com",
        "banner_id": "intermarche",
        "locale": "fr",
        "cat_url": "https://www.intermarche.com/fr/viande-poeisson/c/LC_0301",
    },
}

POSTAL_CODE = "J7Z1J6"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DEFAULT_OUTPUT = os.path.join(OUTPUT_DIR, "pcexpress_products.json")

# Mots-clés viande pour le filtrage
MEAT_KEYWORDS = [
    "boeuf", "bœuf", "steak", "haché", "poulet", "poitrine", "cuisse",
    "porc", "côtelette", "bacon", "jambon", "saucisse", "viande",
    "chicken", "beef", "pork", "sausage", "ham", "ribs", "côte",
    "filet", "rôti", "grillade", "pilon", "aile", "dinde", "dindon",
    "agneau", "veau", "poisson", "saumon", "burger", "brochette",
    "escalope", "lanière", "bifteck", "brisket", "ground",
    "tenderloin", "loin", "liver", "foie", "merlu", "crevette",
    "thon", "truite", "morue", "saumon", "flétan", "sole", "tilapia",
]

EXCLUDE_PATTERNS = [
    re.compile(r, re.IGNORECASE) for r in [
        r"\btapis\b", r"\blitière\b", r"\bcollation\b.*\bchien\b",
        r"\bdog\s+treat\b", r"\bcollation\s+de\s+viande",
        r"\bnourriture\s+(pour\s+)?(chien|chat)\b",
        r"\baliment\s+pour\s+(chien|chat)\b",
    ]
]


def classify_meat_type(name: str) -> Optional[str]:
    """Classifie le type de viande à partir du nom."""
    name_lower = name.lower()

    for pat in EXCLUDE_PATTERNS:
        if pat.search(name_lower):
            return None

    if re.search(r"\bbœ?uf\b|\bbeef\b", name_lower):
        return "boeuf"
    if re.search(r"\bpoulet\b|\bchicken\b|\bdinde\b|\bdindon\b|\bturkey\b", name_lower):
        return "poulet"
    if re.search(r"\bporc\b|\bpork\b|\bjambon\b|\bham\b|\bbacon\b", name_lower):
        return "porc"
    if re.search(r"\bagneau\b|\blamb\b", name_lower):
        return "agneau"
    if re.search(r"\bveau\b|\bveal\b", name_lower):
        return "veau"
    if re.search(r"\bpoisson\b|\bsaumon\b|\bsalmon\b|\bcrevette\b|\bthon\b|\btruite\b|\bmorue\b|\bseafood\b|\bfish\b", name_lower):
        return "poisson"
    return "viande"


def parse_price(text: str) -> Optional[float]:
    """Extrait un prix d'une chaîne comme '3,99$' ou '3.99'."""
    if not text:
        return None
    m = re.search(r"(\d+[.,]\d{2})", text.replace("$", ""))
    if m:
        return float(m.group(1).replace(",", "."))
    return None


def parse_per_kg(text: str) -> Optional[float]:
    """Extrait le prix au kg d'une chaîne comme '9,46$/1kg' ou '0,22$/100g'."""
    if not text:
        return None
    m = re.search(r"(\d+[.,]\d{2})\$?/\s*(\d+)\s*g", text)
    if m:
        price = float(m.group(1).replace(",", "."))
        grams = int(m.group(2))
        return round(price / (grams / 1000), 2) if grams > 0 else None
    m2 = re.search(r"(\d+[.,]\d{2})\$?/\s*1\s*kg", text)
    if m2:
        return float(m2.group(1).replace(",", "."))
    return None


def is_meat_product(name: str) -> bool:
    """Vérifie si le nom contient un mot-clé viande."""
    name_lower = name.lower()
    for pat in EXCLUDE_PATTERNS:
        if pat.search(name_lower):
            return False
    return any(kw in name_lower for kw in MEAT_KEYWORDS)


def scrape_banner(banner_id: str, postal_code: str = POSTAL_CODE, headless: bool = True) -> list[dict]:
    """Scrape les produits viande/poisson d'une épicerie Loblaws via Playwright."""
    config = BANNER_CONFIG.get(banner_id)
    if not config:
        print(f"❌ Bannière inconnue: {banner_id}")
        return []

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ Playwright requis: pip install playwright && playwright install chromium")
        return []

    products = []
    store_name = config["name"]
    cat_url = config["cat_url"]

    print(f"\n🛒 Scraping {store_name} via {cat_url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ])
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            locale="fr-CA",
            timezone_id="America/Toronto",
        )

        # Ajouter des cookies pour le code postal
        context.add_cookies([
            {"name": "auto_store_selected", "value": "true", "domain": f".{config['domain']}", "path": "/"},
            {"name": "postal_code", "value": postal_code, "domain": f".{config['domain']}", "path": "/"},
        ])

        page = context.new_page()

        try:
            # Aller à la catégorie viande
            print(f"   🌐 Chargement de la page...")
            page.goto(cat_url, wait_until="networkidle", timeout=30000)
            time.sleep(2)

            # Vérifier si la page a des produits
            content = page.content()

            # Extraire les produits du DOM
            # PC Express utilise des cartes produits avec data-testid ou classes spécifiques
            product_cards = page.query_selector_all('[data-testid="product-card"], .product-card, article[class*="product"], [class*="ProductTile"], .css-1dbjc4n')

            if not product_cards:
                # Fallback: chercher les liens de produits
                product_cards = page.query_selector_all('a[href*="/product/"], a[href*="/p/"]')

            if not product_cards:
                # Fallback: extraire tous les items de liste de best-sellers
                product_cards = page.query_selector_all('[data-testid="product-tile"], [class*="tile"], li[class*="product"]')

            print(f"   📦 {len(product_cards)} cartes produits trouvées")

            for card in product_cards[:100]:  # max 100 pour éviter les timeouts
                try:
                    text = card.inner_text()
                    html = card.inner_html()

                    # Extraire le nom
                    name_el = card.query_selector('h3, [data-testid="product-name"], [class*="name"], [class*="title"], a')
                    name = name_el.inner_text().strip() if name_el else ""

                    if not name:
                        # Prendre la première ligne significative
                        lines = [l.strip() for l in text.split("\n") if l.strip()]
                        name = lines[0] if lines else ""

                    if not name or len(name) < 3:
                        continue

                    # Filtrer viande
                    if not is_meat_product(name):
                        continue

                    meat_type = classify_meat_type(name)
                    if meat_type is None:
                        continue

                    # Extraire le prix
                    price_text = card.query_selector('[data-testid="product-price"], [class*="price"], .price, [class*="sale"]')
                    price_val = None
                    if price_text:
                        price_val = parse_price(price_text.inner_text())

                    if not price_val:
                        # Chercher dans tout le texte
                        price_matches = re.findall(r"(\d+[.,]\d{2})\$", text)
                        if price_matches:
                            price_val = float(price_matches[0].replace(",", "."))

                    # Prix au kg
                    per_kg = parse_per_kg(text)
                    if not per_kg:
                        per_kg_matches = re.findall(r"(\d+[.,]\d{2})\$?/(?:1\s*kg|kg|lb)", text)
                        if per_kg_matches:
                            per_kg = float(per_kg_matches[0].replace(",", "."))

                    # URL de l'image
                    img_el = card.query_selector('img')
                    img_url = ""
                    if img_el:
                        img_url = img_el.get_attribute("src") or img_el.get_attribute("data-src") or ""

                    # URL du produit
                    link_el = card.query_selector('a')
                    product_url = ""
                    if link_el:
                        product_url = link_el.get_attribute("href") or ""

                    if price_val and price_val > 0 and price_val < 200:
                        product = {
                            "name": name,
                            "name_short": name[:60],
                            "store": store_name,
                            "store_emoji": "🏪",
                            "price": price_val,
                            "per_kg": per_kg,
                            "category": meat_type,
                            "product_type": _classify_fresh(name),
                            "image_url": img_url,
                            "source": f"pcx-{banner_id}",
                            "valid_to": "",
                            "url": product_url,
                        }
                        products.append(product)

                except Exception as e:
                    continue

        except Exception as e:
            print(f"   ❌ Erreur scraping {store_name}: {e}")

        finally:
            browser.close()

    print(f"   ✅ {len(products)} produits viande trouvés chez {store_name}")
    return products


def _classify_fresh(name: str) -> str:
    """Détermine si le produit est frais ou transformé."""
    fresh_keywords = [
        "frais", "friche", "entier", "désossé", "poitrine", "cuisse",
        "filet", "rôti", "steak", "bifteck", "côte", "côtelette",
        "escalope", "haché", "hachée", "grillade", "pilon", "aile",
    ]
    transformed_keywords = [
        "saucisse", "jambon", "bacon", "burger", "farci", "fumé",
        "mariné", "pané", "sauté", "préparé", "salami", "pepperoni",
    ]
    name_lower = name.lower()
    for kw in transformed_keywords:
        if kw in name_lower:
            return "transformé"
    for kw in fresh_keywords:
        if kw in name_lower:
            return "frais"
    return "frais"


def save_products(products: list[dict], output_path: str):
    """Sauvegarde les produits en JSON."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(products, f, indent=2, ensure_ascii=False)
    print(f"📁 Sauvegardé: {output_path} ({len(products)} produits)")


def save_to_db(products: list[dict], banner_id: str):
    """Insère les produits dans la base de données."""
    if not HAS_DB:
        print("⚠️ DB non disponible, installation requise")
        return

    db = get_db()
    week_start = get_week_start()

    # Récupérer ou créer le store
    store_name = BANNER_CONFIG[banner_id]["name"]
    store = db.execute("SELECT id FROM stores WHERE name = ?", (store_name,)).fetchone()
    if not store:
        db.execute("INSERT INTO stores (name) VALUES (?)", (store_name,))
        db.commit()
        store = db.execute("SELECT id FROM stores WHERE name = ?", (store_name,)).fetchone()
    store_id = store["id"]

    inserted = 0
    for p in products:
        try:
            # Vérifier si le produit existe déjà
            existing = db.execute(
                "SELECT id FROM products WHERE name = ? AND store_id = ?",
                (p["name"], store_id),
            ).fetchone()

            if not existing:
                db.execute(
                    """INSERT INTO products (name, store_id, meat_type, category, package_weight_g)
                       VALUES (?, ?, ?, ?, ?)""",
                    (p["name"], store_id, p["category"], p["category"], None),
                )
                db.commit()
                existing = db.execute(
                    "SELECT id FROM products WHERE name = ? AND store_id = ?",
                    (p["name"], store_id),
                ).fetchone()

            product_id = existing["id"]

            # Insérer le prix
            db.execute(
                """INSERT INTO price_history (product_id, week_start, price, unit_price, unit_type, merchant_name, image_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (product_id, week_start, p["price"], p.get("per_kg"),
                 "kg" if p.get("per_kg") else None, store_name, p.get("image_url", "")),
            )
            inserted += 1

        except Exception as e:
            print(f"   ⚠️ Erreur insertion {p['name']}: {e}")

    db.commit()
    db.close()
    print(f"💾 {inserted} nouveaux prix insérés pour {store_name}")


def main():
    parser = argparse.ArgumentParser(description="PC Express meat scraper (indépendant de Flipp)")
    parser.add_argument("--banner", choices=list(BANNER_CONFIG.keys()), default="maxi",
                        help="Bannière à scraper")
    parser.add_argument("--output", default="", help="Fichier de sortie JSON")
    parser.add_argument("--db", action="store_true", help="Insérer dans la base de données")
    parser.add_argument("--postal", default=POSTAL_CODE, help="Code postal")
    parser.add_argument("--headless", action="store_true", default=True, help="Mode headless")
    parser.add_argument("--visible", action="store_true", help="Mode visible (debug)")
    args = parser.parse_args()

    headless = not args.visible

    products = scrape_banner(args.banner, args.postal, headless=headless)

    if not products:
        print("⚠️ Aucun produit trouvé")
        return

    if args.output:
        save_products(products, args.output)
    else:
        # Sauvegarde par défaut
        default = os.path.join(OUTPUT_DIR, f"pcexpress_{args.banner}.json")
        save_products(products, default)

    if args.db:
        save_to_db(products, args.banner)


if __name__ == "__main__":
    main()
