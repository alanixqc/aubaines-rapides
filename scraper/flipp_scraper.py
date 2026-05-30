"""
Scraper Flipp — Récupère les circulaires des épiceries du Québec
Focus: Viande (boeuf, poulet, porc)
"""
import sys
import os
import re
import json
import random
import time
from datetime import datetime, date
from typing import Optional

import requests

# Ajouter le dossier parent au path pour pouvoir importer db
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db.schema import get_db, get_week_start

# ─── Configuration ───────────────────────────────────────────────────────────

POSTAL_CODE = "J7Y4A2"  # Saint-Jérôme
LOCALE = "fr"  # Français
FLIPP_API_BASE = "https://flyers-ng.flippback.com/api/flipp"
REQUEST_DELAY = 0.5  # secondes entre chaque requête

# Liste blanche — ÉPICERIES QUÉBÉCOISES seulement
# (filtre les pharmacies, fast-food, salons, quincailleries, etc.)
QUEBEC_GROCERY_STORES = {
    "Super C", "Metro", "IGA", "Maxi", "Provigo",
    "Walmart", "Costco",
    "Adonis", "Marché Tau", "Kim Phat",
    "Rachelle Béry", "Les Marchés Tradition", "Mayrand",
    "Marche C & T", "Marché C & T",
    "Fruiterie Potager", "5 Saveurs", "L'Inter-Marché",
    "Supermarché Aurès",
    "Tigre Géant", "Les aliments M&M",
    "le Choix du Président",
}

# Mots-clés viande — français et anglais
MEAT_KEYWORDS = {
    "boeuf": {
        "fr": ["boeuf", "bœuf", "steak", "haché", "surlonge", "ribeye",
               "côte de boeuf", "rôti de boeuf", "bourguignon", "bifteck",
               "entrecôte", "faux-filet", "t-bone", "flanc", "palette de boeuf",
               "grillade de boeuf", "boeuf braisé", "cubes de boeuf",
               "tournedos", "steak haché", "boeuf au jus"],
        "en": ["beef", "ground beef", "sirloin", "roast beef",
               "stewing beef", "stir fry beef", "beef steak",
               "rib steak", "t-bone steak", "beef tenderloin",
               "beef brisket", "beef flank"],
    },
    "poulet": {
        "fr": ["poulet", "poitrine", "cuisse", "pilons", "ailes",
               "poulet entier", "poulet rôti", "blanc de poulet",
               "haut de cuisse", "demi-poulet", "filet de poulet",
               "poulet désossé", "poulet haché", "drumstick",
               "poitrine de poulet", "cuisse de poulet"],
        "en": ["chicken", "chicken breast", "chicken thigh",
               "chicken wing", "chicken leg", "whole chicken",
               "chicken drumstick", "chicken tender", "chicken fillet",
               "chicken cutlet", "ground chicken", "chicken roast"],
    },
    "porc": {
        "fr": ["porc", "côtelette", "rôti de porc", "bacon",
               "jambon", "saucisse", "filet de porc", "longe de porc",
               "carré de porc", "jarret", "cou de porc", "oreille de porc",
               "palette de porc", "grillade de porc", "porc haché",
               "côte levée", "spare ribs", "bacon tranché",
               "jambon fumé", "rôti de porc", "saucisse italienne",
               "saucisse à déjeuner"],
        "en": ["pork", "pork chop", "pork roast", "bacon",
               "ham", "sausage", "pork tenderloin", "pork loin",
               "pork shoulder", "pork belly", "pork ribs",
               "pork cutlet", "ground pork", "pork steak", "pork filet",
               "spare ribs", "back ribs", "breakfast sausage"],
    },
    "legume": {
        "fr": ["légume", "legume", "légumes", "legumes", "carotte", "carottes",
               "brocoli", "brocolis", "chou-fleur", "chou fleur", "laitue",
               "tomate", "tomates", "concombre", "concombres",
               "poivron", "poivrons", "oignon", "oignons", "patate", "patates",
               "pomme de terre", "pommes de terre", "céleri", "celeri",
               "épinard", "epinard", "épinards", "epinards",
               "chou", "choux", "chou frisé", "kale", "courge", "courges",
               "courgette", "courgettes", "aubergine", "aubergines",
               "betterave", "betteraves", "radis", "navet", "navets",
               "asperge", "asperges", "haricot", "haricots", "pois", "maïs", "mais",
               "champignon", "champignons", "salade", "salades", "avocat", "avocats",
               "bok choy", "endive", "endives", "scarole", "panais",
               "topinambour", "artichaut", "germe de luzerne",
               "pousse de bambou", "chataigne d'eau", "légumineuse",
               "lentille", "lentilles", "pois chiche", "pois chiches", "pois cassé",
               "brocolini", "okra", "légume surgelé", "legume surgele",
               "légume congelé", "legume congele", "mélange de légumes",
               "melange de legumes"],
        "en": ["vegetable", "vegetables", "carrot", "carrots", "broccoli",
               "cauliflower", "lettuce", "tomato", "tomatoes", "cucumber",
               "cucumbers", "pepper", "peppers", "onion", "onions",
               "potato", "potatoes", "celery", "spinach",
               "cabbage", "kale", "squash", "zucchini", "eggplant",
               "eggplants", "beet", "beets", "radish", "turnip",
               "asparagus", "beans", "peas", "corn", "mushroom",
               "mushrooms", "salad", "avocado", "avocados",
               "mixed vegetables", "frozen vegetables"],
    },
}


def generate_sid() -> str:
    """Génère un session ID pour l'API Flipp."""
    return "".join(str(random.randint(0, 9)) for _ in range(16))


class FlippScraper:
    """Scraper pour l'API Flipp."""

    def __init__(self, postal_code: str = POSTAL_CODE):
        self.postal_code = postal_code
        self.sid = generate_sid()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Accept-Language": "fr-CA,fr;q=0.9,en-CA;q=0.8,en;q=0.7",
        })
        self.stats = {"api_calls": 0, "items_scraped": 0, "meat_items": 0}

    def _api_get(self, url: str) -> Optional[dict]:
        """Fait un appel GET à l'API Flipp."""
        time.sleep(REQUEST_DELAY)
        self.stats["api_calls"] += 1
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"  ⚠️ Erreur API: {e}")
            return None

    def get_flyers(self) -> list[dict]:
        """Récupère toutes les circulaires disponibles pour le code postal."""
        url = f"{FLIPP_API_BASE}/data?locale={LOCALE}&postal_code={self.postal_code}&sid={self.sid}"
        print(f"\n📡 Récupération des circulaires pour {self.postal_code}...")
        data = self._api_get(url)
        if not data or "flyers" not in data:
            print("  ❌ Aucune circulaire trouvée")
            return []
        print(f"  ✅ {len(data['flyers'])} circulaires trouvées")
        return data["flyers"]

    def get_flyer_items(self, flyer_id: int, default_merchant: str = "") -> list[dict]:
        """Récupère les items d'une circulaire spécifique."""
        url = f"{FLIPP_API_BASE}/flyers/{flyer_id}/flyer_items?locale={LOCALE}&sid={self.sid}"
        data = self._api_get(url)
        if not data or not isinstance(data, list):
            return []
        # Certains items Flipp n'ont pas de merchant — on utilise celui de la circulaire
        if default_merchant:
            for item in data:
                if not item.get("merchant"):
                    item["merchant"] = default_merchant
        return data

    def classify_meat(self, item_name: str) -> tuple[Optional[str], float]:
        """
        Détermine si un item est de la viande et quel type.
        Utilise des regex avec word boundaries pour éviter les faux positifs.
        Retourne (meat_type, score_de_confiance 0–1).
        """
        name_lower = item_name.lower()
        name_len = len(name_lower) if name_lower else 1

        # Mots exclusifs — si présents, on ignore la classification viande
        # (évite 'shampooing'/'champignon'/'hamburger' → 'ham' en anglais)
        exclude_patterns = [
            r'\bshampoo', r'\brevitalisant', r'\bchampignon', r'\bchampfleury',
            r'\bcantaloup', r'\bpain', r'\bburger bun',
            r'\bhot.dog', r'\bhamburger', r'\bhambourgeois',
            r'\bpersonnelle', r'\bnourriture\b.*\bchien\b',
            r'\bfour\b.*\bmicro.ondes\b', r'\bensemble?\b.*\bconstruction\b',
            r'\bmuffin', r'\bgâteau',
            r'\bcroustille', r'\bchips\b',
            r'\bsalade.*gastronomique', r'\bsalade.*plaisir', r'\bsalade.*préparée',
            r'\bsalade.*preparée', r'\bsalade.*césar', r'\bsalade.*cesar',
            r'\bsalade.*repas', r'\bsalade.*kit',
            r'\bsalade\s+de\b', r'\bkit\s+de\s+salade',
            r'\bsalade.*hachée', r'\bsalade.*hachee',
            r'\b(sauce|vinaigrette).*salade', r'\btartinade.*salade',
        ]
        for pattern in exclude_patterns:
            if re.search(pattern, name_lower):
                return None, 0.0

        best_type = None
        best_score = 0.0

        for meat_type, keywords in MEAT_KEYWORDS.items():
            # Check français
            for kw in keywords["fr"]:
                # Mots composés (2+ mots) → sous-chaîne
                if len(kw.split()) >= 2:
                    if kw in name_lower:
                        score = len(kw) / name_len
                        if score > best_score:
                            best_score = score
                            best_type = meat_type
                else:
                    # Mots simples → word boundary
                    if re.search(r'\b' + re.escape(kw) + r'\b', name_lower):
                        score = len(kw) / name_len
                        if score > best_score:
                            best_score = score
                            best_type = meat_type

            # Check anglais
            for kw in keywords["en"]:
                if len(kw.split()) >= 2:
                    if kw in name_lower:
                        score = len(kw) / name_len
                        if score > best_score:
                            best_score = score
                            best_type = meat_type
                else:
                    if re.search(r'\b' + re.escape(kw) + r'\b', name_lower):
                        score = len(kw) / name_len
                        if score > best_score:
                            best_score = score
                            best_type = meat_type

        return best_type, best_score

    def extract_price(self, price_text: str) -> tuple[Optional[float], Optional[float], Optional[str]]:
        """
        Extrait le prix numérique à partir d'un texte.
        Retourne (price, unit_price, unit_type).
        Gère les formats: "2/6,00$", "3,99$/lb", "5,49$/kg", "$4.99 ea", "4.99"
        """
        if not price_text:
            return None, None, None

        price_text = str(price_text).strip()

        # Cas simple: juste un nombre (Flipp retourne "4.99", "1.69", etc.)
        simple_match = re.match(r'^(\d+\.?\d*)$', price_text)
        if simple_match:
            return float(simple_match.group(1)), None, None

        # Format avec virgule décimale sans $: "4,99"
        simple_comma = re.match(r'^(\d+,\d+)$', price_text)
        if simple_comma:
            return float(simple_comma.group(1).replace(",", ".")), None, None

        # Détecter le format "2/6,00$" (2 pour 6$) — avec ou sans $
        multi_match = re.match(r'(\d+)\s*/\s*([\d.,]+)\s*\$?\s*', price_text)
        if multi_match:
            qty = float(multi_match.group(1))
            total = float(multi_match.group(2).replace(",", "."))
            return round(total / qty, 2), None, "ea"

        # Détecter "3,99$/lb" ou "5.49$/kg"
        unit_match = re.search(r'([\d.,]+)\s*[$\$]\s*/\s*(\w+)', price_text)
        if unit_match:
            price = float(unit_match.group(1).replace(",", "."))
            unit_type = f"/{unit_match.group(2)}"
            return price, None, unit_type

        # Détecter "$4.99" ou "4,99$"
        price_match = re.search(r'([\d.,]+)\s*[$\$]', price_text)
        if price_match:
            price = float(price_match.group(1).replace(",", "."))
            return price, None, None

        return None, None, None

    def parse_item(self, item: dict) -> Optional[dict]:
        """
        Parse un item de circulaire et le prépare pour la DB.
        Inclut l'URL de l'image et le flipp_item_id pour extraction
        du poids via vision.
        """
        name = item.get("name", "").strip()
        if not name:
            return None

        price = item.get("price", "")
        valid_from = item.get("valid_from", "")
        valid_to = item.get("valid_to", "")
        merchant = item.get("merchant", "")

        # Prix
        price_num, unit_price, unit_type = self.extract_price(price)

        # Classification viande
        meat_type, confidence = self.classify_meat(name)

        # Image Flipp pour extraction du poids via vision
        image_url = item.get("cutout_image_url", "")
        flipp_item_id = item.get("id")

        return {
            "name": name,
            "price": price_num,
            "price_text": price,
            "valid_from": valid_from[:10] if valid_from else None,
            "valid_to": valid_to[:10] if valid_to else None,
            "merchant": merchant,
            "meat_type": meat_type,
            "meat_confidence": confidence,
            "unit_type": unit_type,
            "image_url": image_url,
            "flipp_item_id": flipp_item_id,
        }

    def store_item(self, parsed: dict) -> bool:
        """Sauvegarde un item parsé dans la base de données."""
        if not parsed or not parsed["name"]:
            return False
        merchant = parsed["merchant"]
        if not merchant:
            return False  # skip si pas de marchand

        db = get_db()
        try:
            # 1. Trouver ou créer le store
            merchant = parsed["merchant"]
            db.execute(
                "INSERT OR IGNORE INTO stores (name, slug) VALUES (?, ?)",
                (merchant, merchant.lower().replace(" ", "-")),
            )

            # 2. Trouver ou créer le produit
            store = db.execute(
                "SELECT id FROM stores WHERE name = ?", (merchant,)
            ).fetchone()
            if not store:
                return False

            store_id = store["id"]

            db.execute(
                """INSERT OR IGNORE INTO products (name, store_id, meat_type)
                   VALUES (?, ?, ?)""",
                (parsed["name"], store_id, parsed["meat_type"]),
            )
            product = db.execute(
                "SELECT id, meat_type FROM products WHERE name = ? AND store_id = ?",
                (parsed["name"], store_id),
            ).fetchone()
            product_id = product["id"]
            
            # Update meat_type si change (ex: NULL -> legume ou legume -> NULL)
            if product["meat_type"] != parsed["meat_type"]:
                db.execute("UPDATE products SET meat_type = ? WHERE id = ?",
                           (parsed["meat_type"], product_id))

            # 3. Insérer l'historique de prix
            week_start = get_week_start()
            db.execute(
                """INSERT INTO price_history
                   (product_id, price, unit_type, sale_text, valid_from, valid_to,
                    week_start, merchant_name, image_url, flipp_item_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    product_id,
                    parsed["price"],
                    parsed["unit_type"],
                    parsed["price_text"],
                    parsed["valid_from"],
                    parsed["valid_to"],
                    week_start,
                    merchant,
                    parsed.get("image_url", ""),
                    parsed.get("flipp_item_id"),
                ),
            )
            db.commit()
            self.stats["items_scraped"] += 1
            if parsed["meat_type"]:
                self.stats["meat_items"] += 1
            return True

        except Exception as e:
            print(f"  ⚠️ Erreur sauvegarde DB: {e}")
            db.rollback()
            return False
        finally:
            db.close()

    def run(self):
        """Exécute le scraping complet."""
        print(f"\n{'='*60}")
        print(f"🛒 AUBANES RAPIDES — Scraper Flipp")
        print(f"📍 Code postal: {self.postal_code}")
        print(f"📅 Semaine: {get_week_start()}")
        print(f"{'='*60}")

        flyers = self.get_flyers()
        if not flyers:
            print("❌ Aucune circulaire récupérée")
            return self.stats

        # Filtrer — uniquement les épiceries QUÉBÉCOISES de notre liste
        grocery_flyers = [
            f for f in flyers
            if f.get("merchant") in QUEBEC_GROCERY_STORES
        ]

        print(f"  🏪 {len(grocery_flyers)} circulaires d'épiceries identifiées")

        items_by_store = {}

        for flyer in grocery_flyers:
            flyer_id = flyer["id"]
            merchant = flyer.get("merchant", "Inconnu")
            print(f"\n  📄 {merchant} (flyer #{flyer_id})...")

            items = self.get_flyer_items(flyer_id, default_merchant=merchant)
            if not items:
                print(f"    ⚠️ Aucun item")
                continue

            print(f"    {len(items)} items dans la circulaire")

            store_items = []
            for item in items:
                parsed = self.parse_item(item)
                if parsed:
                    self.store_item(parsed)
                    store_items.append(parsed)

            items_by_store[merchant] = store_items

        # Rapport
        print(f"\n{'='*60}")
        print(f"📊 RAPPORT DE SCRAPING")
        print(f"{'='*60}")
        print(f"  Appels API:       {self.stats['api_calls']}")
        print(f"  Items scrapés:    {self.stats['items_scraped']}")
        print(f"  Items viande:     {self.stats['meat_items']}")
        print(f"{'='*60}")

        # Afficher les items viande trouvés
        self.print_meat_report()

        return self.stats

    def print_meat_report(self):
        """Affiche un rapport des viandes trouvées."""
        db = get_db()
        week_start = get_week_start()

        for meat_type in ["boeuf", "poulet", "porc"]:
            rows = db.execute(
                """SELECT p.name, s.name as store, ph.price, ph.sale_text,
                          ph.valid_from, ph.valid_to
                   FROM price_history ph
                   JOIN products p ON p.id = ph.product_id
                   JOIN stores s ON s.id = p.store_id
                   WHERE p.meat_type = ?
                     AND ph.week_start = ?
                   ORDER BY s.name, p.name""",
                (meat_type, week_start),
            ).fetchall()

            if rows:
                print(f"\n  🥩 {meat_type.upper()} ({len(rows)} items)")
                print(f"  {'─'*50}")
                for r in rows:
                    store_info = f"[{r['store']}]"
                    price_info = f"${r['price']:.2f}" if r["price"] else "N/D"
                    sale = f" — {r['sale_text']}" if r["sale_text"] else ""
                    dates = f" ({r['valid_from']} → {r['valid_to']})" if r["valid_from"] else ""
                    print(f"    {store_info:15s} {r['name'][:45]:45s} {price_info:>8s}{sale}{dates}")

        db.close()


def main():
    postal = os.environ.get("POSTAL_CODE", POSTAL_CODE)
    scraper = FlippScraper(postal_code=postal)
    scraper.run()


if __name__ == "__main__":
    main()
