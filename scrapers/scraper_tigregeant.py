#!/usr/bin/env python3
"""
Tigre Géant / Giant Tiger Shopify Scraper
===========================================
Scrapes product data from gianttiger.com using their public Shopify REST API.

The API at /collections/flyers-and-deals/products.json returns all flyer items
with full product metadata (prices, variants, images, tags).

Strategy:
  1) Paginate through the products.json API (limit=250, ~2 pages = ~352 products)
  2) Filter to Meat/Deli product_type (and optionally broader meat categories)
  3) Extract: name, price, compare_at_price, image_url, category
  4) Classify meat_type (boeuf/poulet/porc/agneau/veau) from product name
  5) Output clean JSON compatible with aubaines-rapides DB schema

Usage:
    python scraper_tigregeant.py                          # scrape all + print JSON
    python scraper_tigregeant.py --save                   # scrape and save to file
    python scraper_tigregeant.py --output out.json        # save to custom path
    python scraper_tigregeant.py --all-meat               # include frozen/fresh meat
    python scraper_tigregeant.py --no-qc-filter           # skip QC province filter
    python scraper_tigregeant.py --db                     # insert into database

API details:
  - Endpoint: https://www.gianttiger.com/collections/flyers-and-deals/products.json
  - Parameters: ?limit=250&page=N
  - Product types include: Meat/Deli, Fresh, Frozen, Dairy & Eggs, etc.
  - Meat/Deli items have product_type "Meat/Deli"
  - Tags include L1/L2/L3 category hierarchy and mms_province_code:X
  - Tag badge_en:Advertised indicates featured/flyer items
  - No API key required — fully public read-only endpoint.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, date
from typing import Optional

# ── Path setup for sibling imports ────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from db.schema import get_db, get_week_start
    HAS_DB = True
except ImportError:
    HAS_DB = False

# ── HTTP import ────────────────────────────────────────────────────────────────
try:
    import urllib.request
    import urllib.error
    HAS_URLLIB = True
except ImportError:
    HAS_URLLIB = False


# ═══════════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════════

MERCHANT_NAME = "Tigre Géant"
MERCHANT_SLUG = "tigre-geant"

API_BASE = "https://www.gianttiger.com/collections/flyers-and-deals/products.json"
API_LIMIT = 250
MAX_PAGES = 10  # safety limit

DEFAULT_OUTPUT = os.path.join(
    os.path.dirname(__file__), "..", "data", "tigregeant_products.json",
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "fr-CA,fr;q=0.9,en-CA;q=0.8,en;q=0.7",
    "Referer": "https://www.gianttiger.com/",
}
REQUEST_DELAY = 0.25

# ── Which product types are meat? ──────────────────────────────────────────────
MEAT_PRODUCT_TYPES = {"Meat/Deli"}

# Additional L3 meat categories for --all-meat mode
ALL_MEAT_L3_CATEGORIES = [
    "Meat", "Beef", "Pork", "Chicken", "Turkey", "Lamb", "Veal",
    "Sausage", "Bacon", "Deli", "Seafood",
]

# ── Meat classification from name ──────────────────────────────────────────────
MEAT_CLASSIFIERS = {
    "boeuf": [
        r"\bbœ?uf\b", r"\bsteak\b", r"\bbifteck\b", r"\brôti\s+de\s+bœ?uf\b",
        r"\bcôte\s+de\s+bœ?uf\b", r"\bbœ?uf\s+haché\b", r"\bhaché\s+de\s+bœ?uf\b",
        r"\btournedos\b", r"\bentrecôte\b", r"\bfilet\s+mignon\b",
        r"\bribeye\b", r"\bsirloin\b", r"\bcontre-filet\b",
        r"\bfaux-filet\b", r"\bbraise\b", r"\bbourguignon\b",
        r"\bground\s+beef\b", r"\bbeef\b", r"\bburger\b",
        r"\bbœ?uf\s+haché\b", r"\bhamburger\b",
        r"\bsteak\s+haché\b", r"\bchuck\b",
    ],
    "poulet": [
        r"\bpoulet\b", r"\bpoitrine\s+de\s+poulet\b", r"\bcuisse\s+de\s+poulet\b",
        r"\bpilon\b", r"\bpilons?\b", r"\baile?\s+de\s+poulet\b",
        r"\bdinde\b", r"\bdindon\b", r"\bcanard\b",
        r"\bsupreme\s+de\s+poulet\b", r"\bblanc\s+de\s+poulet\b",
        r"\bpoulet\s+entier\b", r"\bpoulet\s+frais\b",
        r"\bpoulet\s+surgelé\b", r"\bpoulet\s+breaded\b",
        r"\bchicken\b", r"\bturkey\b", r"\bchicken\s+breast\b",
        r"\bchicken\s+wings\b", r"\bchicken\s+thighs\b",
        r"\bdrumsticks?\b", r"\bchicken\s+drumsticks?\b",
        r"\bnuggets?\b", r"\bnugget\b",
        r"\blanières?\s+de\s+poulet\b",
    ],
    "porc": [
        r"\bporc\b", r"\bfilet\s+de\s+porc\b", r"\bcôtelette\s+de\s+porc\b",
        r"\bbacon\b", r"\bjambon\b", r"\bsaucisse\b",
        r"\bcôtes\s+levées\b", r"\bribs?\b",
        r"\bbaby\s+back\s+ribs\b", r"\bspare\s+ribs\b",
        r"\blard\b", r"\bcochon\b", r"\blardon\b",
        r"\bporc\s+haché\b", r"\bsaucisses\s+italiennes\b",
        r"\bsaucisses\s+merguez\b", r"\bwieners?\b",
        r"\bpork\b", r"\bpork\s+chops?\b", r"\bpork\s+tenderloin\b",
        r"\bhot.?dogs?\b", r"\bhot.?dog\b",
        r"\bkolbassa\b", r"\bkielbasa\b",
        r"\bsausage\b", r"\bsmoked\s+meat\b",
        r"\bham\b", r"\bpepperoni\b", r"\bsalami\b",
        r"\bloin\s+chop\b", r"\bpork\s+loin\b",
    ],
    "agneau": [
        r"\bagneau\b", r"\bagneaux\b", r"\bcôte\s+d'agneau\b",
        r"\bgigot\s+d'agneau\b", r"\blamb\b",
    ],
    "veau": [
        r"\bveau\b", r"\bescalope\s+de\s+veau\b",
        r"\bcôte\s+de\s+veau\b", r"\bveal\b",
    ],
    "poisson": [
        r"\bpoisson\b", r"\bsaumon\b", r"\btruite\b", r"\bmorue\b",
        r"\baiglefin\b", r"\bhadock\b", r"\bsole\b",
        r"\bthon\b", r"\bcrevette\b", r"\bcrevettes\b",
        r"\bhomard\b", r"\bcrabe\b", r"\bpalourde\b",
        r"\bmoule\b", r"\bmoules\b", r"\bcalmar\b",
        r"\bfish\b", r"\bsalmon\b", r"\btilapia\b",
        r"\bcod\b", r"\bhaddock\b", r"\bseafood\b",
        r"\bmer\b", r"\bfruits\s+de\s+mer\b",
    ],
}

# Compiled meat matcher
MEAT_PATTERN = re.compile(
    "|".join(p for pats in MEAT_CLASSIFIERS.values() for p in pats),
    re.IGNORECASE,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Core Scraper
# ═══════════════════════════════════════════════════════════════════════════════

class TigreGeantScraper:
    """Scrapes Giant Tiger's Shopify API for flyer/deal products."""

    def __init__(self, all_meat: bool = False, qc_filter: bool = True,
                 delay: float = REQUEST_DELAY):
        self.all_meat = all_meat
        self.qc_filter = qc_filter
        self.delay = delay
        self.stats = {
            "pages_fetched": 0,
            "products_total": 0,
            "meat_candidates": 0,
            "qc_kept": 0,
            "products_output": 0,
        }

    # ── API Fetching ────────────────────────────────────────────────────────

    def fetch_page(self, page: int) -> list[dict]:
        """Fetch one page of products from the Shopify API."""
        url = f"{API_BASE}?limit={API_LIMIT}&page={page}"
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            products = data.get("products", [])
            self.stats["pages_fetched"] += 1
            print(f"  📄 Page {page}: {len(products)} produits", file=sys.stderr)
            return products
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return []  # No more pages
            print(f"  ⚠️  Page {page}: HTTP {e.code}", file=sys.stderr)
            return []
        except Exception as e:
            print(f"  ⚠️  Page {page}: {e}", file=sys.stderr)
            return []

    def fetch_all_pages(self) -> list[dict]:
        """Paginate through all available pages."""
        all_products = []
        seen_handles = set()

        for page in range(1, MAX_PAGES + 1):
            products = self.fetch_page(page)
            if not products:
                break  # No more data

            # Deduplicate by handle
            for p in products:
                handle = p.get("handle", "")
                if handle and handle not in seen_handles:
                    seen_handles.add(handle)
                    all_products.append(p)

            time.sleep(self.delay)

        self.stats["products_total"] = len(all_products)
        print(f"\n  📊 Total produits bruts: {len(all_products)}", file=sys.stderr)
        return all_products

    # ── Filtering ───────────────────────────────────────────────────────────

    def _get_tags(self, product: dict) -> list[str]:
        tags = product.get("tags", [])
        if isinstance(tags, str):
            return [t.strip() for t in tags.split(",")]
        return list(tags)

    def _get_category_from_tags(self, tags: list[str], level: str = "L3") -> str:
        """Extract L1/L2/L3 category from tags."""
        prefix = f"{level}_category_en:"
        for t in tags:
            if t.startswith(prefix):
                return t.split(":", 1)[1]
        return ""

    def _has_province_code(self, tags: list[str], province: str = "QC") -> bool:
        """Check if a product is available in the given province."""
        for t in tags:
            if t == f"mms_province_code:{province}":
                return True
        return False

    def is_meat_product(self, product: dict) -> bool:
        """Determine if a product is meat/deli related."""
        product_type = product.get("product_type", "")
        tags = self._get_tags(product)

        # Primary: product_type is Meat/Deli
        if product_type in MEAT_PRODUCT_TYPES:
            return True

        # Extended: check L3 category for meat keywords (only in --all-meat mode)
        if self.all_meat:
            l3 = self._get_category_from_tags(tags, "L3")
            l2 = self._get_category_from_tags(tags, "L2")
            combined = f"{l2} {l3}"
            for kw in ALL_MEAT_L3_CATEGORIES:
                if kw.lower() in combined.lower():
                    return True

        return False

    def classify_meat_type(self, name: str) -> str:
        """Classify meat type from product name."""
        for meat_type, patterns in MEAT_CLASSIFIERS.items():
            for pattern in patterns:
                if re.search(pattern, name, re.IGNORECASE):
                    return meat_type
        return "viande"

    def extract_variant_info(self, product: dict) -> tuple[Optional[str], Optional[str]]:
        """Extract price and compare_at_price from the first variant."""
        variants = product.get("variants", [])
        if not variants:
            return (None, None)
        v = variants[0]
        return (v.get("price"), v.get("compare_at_price"))

    def extract_image_url(self, product: dict) -> str:
        """Extract the primary image URL."""
        images = product.get("images", [])
        if images:
            return images[0].get("src", "")
        # Fallback: variant featured_image
        variants = product.get("variants", [])
        if variants and variants[0].get("featured_image"):
            return variants[0]["featured_image"].get("src", "")
        return ""

    def determine_category(self, product: dict, tags: list[str]) -> str:
        """Determine a meaningful category string."""
        l3 = self._get_category_from_tags(tags, "L3")
        if l3:
            return l3
        l2 = self._get_category_from_tags(tags, "L2")
        if l2:
            return l2
        return product.get("product_type", "")

    def process_product(self, product: dict) -> Optional[dict]:
        """
        Process a single product into the standardized output format.
        Returns None if the product should be filtered out.
        """
        name = product.get("title", "").strip()
        if not name:
            return None

        product_type = product.get("product_type", "")
        tags = self._get_tags(product)

        # Check meat filter
        if not self.is_meat_product(product):
            return None
        self.stats["meat_candidates"] += 1

        # Check QC filter
        is_qc = self._has_province_code(tags, "QC")
        if self.qc_filter and not is_qc:
            return None
        self.stats["qc_kept"] += 1

        # Extract data
        price, compare_at_price = self.extract_variant_info(product)
        image_url = self.extract_image_url(product)
        category = self.determine_category(product, tags)
        meat_type = self.classify_meat_type(name)

        # Check badge
        has_badge = any("badge_en:Advertised" in t for t in tags)

        result = {
            "name": name,
            "price": float(price) if price else None,
            "compare_at_price": float(compare_at_price) if compare_at_price else None,
            "image_url": image_url,
            "category": category,
            "meat_type": meat_type,
            "product_type": product_type,
            "is_advertised": has_badge,
            "available_qc": is_qc,
            "id": product.get("id"),
            "handle": product.get("handle"),
            "scraped_at": datetime.now().isoformat(),
        }

        self.stats["products_output"] += 1
        return result

    # ── Main Pipeline ───────────────────────────────────────────────────────

    def scrape(self) -> list[dict]:
        """Run the full scraping pipeline."""
        if not HAS_URLLIB:
            raise ImportError("urllib is required but not available")

        print("🔍 Tigre Géant / Giant Tiger Shopify Scraper", file=sys.stderr)
        print(f"   API: {API_BASE}", file=sys.stderr)
        print(f"   Mode: {'Tous les types de viande' if self.all_meat else 'Meat/Deli uniquement'}", file=sys.stderr)
        print(f"   Filtre QC: {'Oui' if self.qc_filter else 'Non'}", file=sys.stderr)
        print(file=sys.stderr)

        # Step 1: Fetch all products
        all_products = self.fetch_all_pages()

        # Step 2: Process and filter
        results = []
        for p in all_products:
            processed = self.process_product(p)
            if processed:
                results.append(processed)

        # Step 3: Sort by meat_type then name
        results.sort(key=lambda x: (x["meat_type"], x["name"]))

        # Print summary
        print(file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(f"📊 RÉSULTATS", file=sys.stderr)
        print(f"   Produits bruts:         {self.stats['products_total']}", file=sys.stderr)
        print(f"   Candidats viande:       {self.stats['meat_candidates']}", file=sys.stderr)
        print(f"   Disponibles au QC:      {self.stats['qc_kept']}", file=sys.stderr)
        print(f"   Produits finaux:        {self.stats['products_output']}", file=sys.stderr)
        print("=" * 60, file=sys.stderr)

        return results


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Tigre Géant / Giant Tiger Shopify Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--save", action="store_true",
                        help="Save output to default path")
    parser.add_argument("--output", type=str, default=None,
                        help="Custom output JSON file path")
    parser.add_argument("--all-meat", action="store_true",
                        help="Include frozen/fresh meat products beyond Meat/Deli type")
    parser.add_argument("--no-qc-filter", action="store_true",
                        help="Skip QC province filter (include all regions)")
    parser.add_argument("--db", action="store_true",
                        help="Insert results into database")
    parser.add_argument("--pretty", action="store_true",
                        help="Pretty-print JSON output")

    args = parser.parse_args()

    # Create scraper
    scraper = TigreGeantScraper(
        all_meat=args.all_meat,
        qc_filter=not args.no_qc_filter,
    )

    # Run
    results = scraper.scrape()

    # Output
    json_kwargs = {"ensure_ascii": False, "indent": 2} if args.pretty or args.save else {"ensure_ascii": False}
    
    # Determine output path
    if args.output:
        output_path = args.output
    elif args.save:
        output_path = DEFAULT_OUTPUT
    else:
        output_path = None

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Sauvegardé: {output_path}", file=sys.stderr)
    else:
        # Print to stdout
        print(json.dumps(results, ensure_ascii=False, indent=2))

    # Optional DB insert
    if args.db and results:
        insert_to_db(results)

    return results


def insert_to_db(products: list[dict]):
    """Insert scraped products into the aubaines-rapides database."""
    if not HAS_DB:
        print("⚠️  Cannot insert into DB: db.schema not available", file=sys.stderr)
        return

    conn = get_db()
    week_start = get_week_start()

    # Get or create store
    cur = conn.execute(
        "SELECT id FROM stores WHERE name = ? OR slug = ?",
        (MERCHANT_NAME, MERCHANT_SLUG),
    )
    row = cur.fetchone()
    if row:
        store_id = row["id"]
    else:
        conn.execute(
            "INSERT INTO stores (name, slug) VALUES (?, ?)",
            (MERCHANT_NAME, MERCHANT_SLUG),
        )
        conn.commit()
        cur = conn.execute("SELECT last_insert_rowid()")
        store_id = cur.fetchone()[0]
        print(f"🏪 Store créé: {MERCHANT_NAME} (id={store_id})", file=sys.stderr)

    inserted = 0
    for p in products:
        # Upsert product
        conn.execute(
            """INSERT OR IGNORE INTO products (name, store_id, meat_type, category)
               VALUES (?, ?, ?, ?)""",
            (p["name"], store_id, p["meat_type"], p["category"]),
        )

        # Get product id
        cur = conn.execute(
            "SELECT id FROM products WHERE name = ? AND store_id = ?",
            (p["name"], store_id),
        )
        prod_row = cur.fetchone()
        if not prod_row:
            continue
        product_id = prod_row["id"]

        # Insert price history
        conn.execute(
            """INSERT INTO price_history
               (product_id, price, regular_price, week_start, merchant_name, scanned_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))""",
            (product_id, p["price"], p["compare_at_price"],
             week_start, MERCHANT_NAME),
        )
        inserted += 1

    conn.commit()
    conn.close()
    print(f"💾 DB: {inserted} prix insérés pour {MERCHANT_NAME}", file=sys.stderr)


if __name__ == "__main__":
    main()
