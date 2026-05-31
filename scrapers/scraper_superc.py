#!/usr/bin/env python3
"""
Super C Meat & Poultry Scraper
================================
Scrapes product data from superc.ca meat/poultry aisles using Playwright.

Targets the Drupal-based product listing pages and extracts product info from
HTML data-product-* attributes and CSS class-based pricing sections.

Categories scraped:
  - Beef & Veal
  - Chicken & Turkey
  - Pork

Output: JSON array of product objects with fields compatible with the
aubaines-rapides DB schema (similar to Flipp scraper output).

Usage:
    python scraper_superc.py                          # scrape all + print JSON
    python scraper_superc.py --save                   # scrape and save to file
    python scraper_superc.py --output out.json        # save to custom path
    python scraper_superc.py --category beef          # scrape only one category
    python scraper_superc.py --headless false         # show browser window

Requirements:
    pip install playwright
    python -m playwright install chromium
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

# ── Playwright import (lazy, so --help works without it) ──────────────────────
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout
except ImportError:
    sync_playwright = None
    PwTimeout = Exception


# ═══════════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════════

BASE_URL = "https://www.superc.ca/en"

CATEGORIES = {
    "beef": {
        "url": "/aisles/meat-poultry/beef-veal",
        "slug": "beef-veal",
        "meat_type": "boeuf",
    },
    "chicken": {
        "url": "/aisles/meat-poultry/chicken-turkey",
        "slug": "chicken-turkey",
        "meat_type": "poulet",
    },
    "pork": {
        "url": "/aisles/meat-poultry/pork",
        "slug": "pork",
        "meat_type": "porc",
    },
}

# Pagination URL pattern (page 2+): /en/aisles/meat-poultry/{slug}-page-{n}
# Page 1 has the base URL, page 2+ appends "-page-N"

DEFAULT_OUTPUT = os.path.join(
    os.path.dirname(__file__), "..", "data", "superc_products.json"
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

REQUEST_DELAY = 1.0  # seconds between page loads


# ═══════════════════════════════════════════════════════════════════════════════
# Scraper
# ═══════════════════════════════════════════════════════════════════════════════

class SuperCScraper:
    """Scrapes meat/poultry products from superc.ca using Playwright."""

    def __init__(self, headless: bool = True, delay: float = REQUEST_DELAY):
        if sync_playwright is None:
            raise ImportError(
                "playwright is not installed. Run: pip install playwright && "
                "python -m playwright install chromium"
            )
        self.headless = headless
        self.delay = delay
        self.stats = {
            "pages_scraped": 0,
            "products_found": 0,
            "products_extracted": 0,
            "categories_scraped": 0,
        }
        self._pw_ctx = None  # PlaywrightContextManager
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def __enter__(self):
        self._pw_ctx = sync_playwright()  # context manager
        self._playwright = self._pw_ctx.__enter__()  # Playwright object
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        self._context = self._browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1920, "height": 1080},
            locale="en-CA",
            timezone_id="America/Toronto",
            # Block unnecessary resources for speed
            extra_http_headers={
                "Accept-Language": "en-CA,en;q=0.9,fr-CA;q=0.8,fr;q=0.7",
            },
        )
        # Block resource types that slow us down
        self._context.route(
            re.compile(r"\.(png|jpg|jpeg|gif|svg|woff|woff2|ttf|eot)(\?|$)"),
            lambda route: route.abort(),
        )
        # But allow product images
        self._context.route(
            re.compile(r"product-images\.metro\.ca"),
            lambda route: route.continue_(),
        )
        self._page = self._context.new_page()
        return self

    def __exit__(self, *args):
        if self._browser:
            self._browser.close()
        if self._pw_ctx:
            self._pw_ctx.__exit__(*args)

    # ── Navigation helpers ────────────────────────────────────────────────

    def _navigate(self, url: str) -> bool:
        """Navigate to URL and wait for content."""
        try:
            self._page.goto(url, wait_until="domcontentloaded", timeout=60000)
            self._page.wait_for_timeout(3000)  # let JS settle
            # Forcer la langue française via cookie/lang préf
            try:
                self._page.evaluate("""() => {
                    localStorage.setItem('lang', 'fr');
                    document.cookie = "lang=fr; path=/; max-age=86400";
                }""")
            except Exception:
                pass
            self._handle_cookies()
            self._page.wait_for_timeout(1500)

            # Wait for product tiles to be present
            try:
                self._page.wait_for_selector(
                    "[data-product-code].default-product-tile",
                    timeout=20000,
                )
            except Exception:
                # Fallback: try any data-product-code element
                try:
                    self._page.wait_for_selector(
                        "[data-product-code]",
                        timeout=10000,
                    )
                except Exception:
                    pass  # will be handled by the caller

            return True
        except Exception as e:
            print(f"  ⚠️ Navigation error: {e}", file=sys.stderr)
            return False

    def _handle_cookies(self):
        """Accept cookie consent if the banner is present."""
        selectors = [
            "button#onetrust-accept-btn-handler",
            "button:has-text('Accept All')",
            "button:has-text('Accepter les témoins')",
            "button:has-text('Accepter')",
            "button:has-text('Accept')",
            ".cookie-consent button",
            "#cookie-consent button",
            "button.onetrust-close-btn-handler",
        ]
        for sel in selectors:
            try:
                btn = self._page.locator(sel)
                if btn.count() > 0 and btn.first.is_visible(timeout=2000):
                    btn.first.click(timeout=3000)
                    self._page.wait_for_timeout(1000)
                    return
            except Exception:
                continue

    def _scroll_to_bottom(self):
        """Scroll to bottom to ensure lazy-loaded content is present."""
        try:
            self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            self._page.wait_for_timeout(1500)
        except Exception:
            pass

    # ── Extraction ────────────────────────────────────────────────────────

    def _get_page_products(self) -> list[dict]:
        """
        Extract all products from the current page using JS evaluation.
        Returns a list of product dicts.
        """
        products = self._page.evaluate("""() => {
            const tiles = document.querySelectorAll(
                '[data-product-code].default-product-tile'
            );
            if (!tiles.length) {
                // Fallback: try broader selector
                const alt = document.querySelectorAll('[data-product-code]');
                if (!alt.length) return [];
                return Array.from(alt).map(tile => extractProduct(tile));
            }

            function extractProduct(tile) {
                const code = tile.getAttribute('data-product-code');
                const name = tile.getAttribute('data-product-name');
                const weighted = tile.getAttribute('data-is-weighted') === 'true';
                const discountPriceCents = tile.getAttribute('data-discount-price');
                const discountPct = tile.getAttribute('data-discount-percent');
                const category = tile.getAttribute('data-merchandise-category');
                const parentCat = tile.getAttribute('data-parent-category-hierarchy');

                // Main price from data attribute on inner div
                const mainPriceDiv = tile.querySelector('[data-main-price]');
                const mainPrice = mainPriceDiv
                    ? parseFloat(mainPriceDiv.getAttribute('data-main-price'))
                    : null;

                // Regular (before) price section - only present when on sale
                const beforePrice = tile.querySelector('.pricing__before-price');
                let regularUnitPrices = [];
                let regularPriceText = null;
                if (beforePrice) {
                    regularPriceText = beforePrice.textContent.trim();
                    const spans = beforePrice.querySelectorAll('.mr-1');
                    spans.forEach(s => regularUnitPrices.push(s.textContent.trim()));
                }

                // Sale/current price section
                const salePrice = tile.querySelector('.pricing__sale-price');
                const salePriceText = salePrice
                    ? salePrice.textContent.trim()
                    : null;

                // Unit price section (secondary price)
                const secondaryPrice = tile.querySelector('.pricing__secondary-price');
                const unitPriceText = secondaryPrice
                    ? secondaryPrice.textContent.trim()
                    : null;

                // Product full name/title — cherche d'abord le lien titre, 
                // puis .head__title, puis fallback sur data-product-name
                let fullName = name;
                const titleLink = tile.querySelector('a[data-testid="product-title"]') ||
                                  tile.querySelector('.product-tile__title a') ||
                                  tile.querySelector('[class*="product-name"] a') ||
                                  tile.querySelector('.head__title');
                if (titleLink) {
                    const t = titleLink.textContent.trim();
                    if (t) fullName = t;
                } else {
                    // Fallback: chercher le premier lien dans la tuile avec un texte long
                    const links = tile.querySelectorAll('a');
                    for (const a of links) {
                        const t = a.textContent.trim();
                        if (t.length > fullName.length) {
                            fullName = t;
                            break;
                        }
                    }
                }

                // Weight/size info
                const unitDetails = tile.querySelector('.head__unit-details');
                const packageInfo = unitDetails
                    ? unitDetails.textContent.trim()
                    : null;

                // Image
                const img = tile.querySelector('img[src*="product-images.metro"]');
                const imageUrl = img
                    ? img.getAttribute('src')
                    : null;

                // Has sale sticker
                const hasSale = !!tile.querySelector('.icon--sale');

                // Discount dollar amount
                let discountPrice = null;
                if (discountPriceCents) {
                    discountPrice = parseFloat(
                        (parseInt(discountPriceCents) / 100).toFixed(2)
                    );
                }

                return {
                    product_code: code,
                    name: name,
                    full_name: fullName,
                    main_price: mainPrice,
                    sale_price_text: salePriceText,
                    regular_price_text: regularPriceText,
                    regular_unit_prices: regularUnitPrices,
                    unit_price_text: unitPriceText,
                    discount_price: discountPrice,
                    discount_percent: discountPct
                        ? parseInt(discountPct)
                        : null,
                    has_sale: hasSale,
                    is_weighted: weighted,
                    package_info: packageInfo,
                    image_url: imageUrl,
                    meat_category: category,
                    category_hierarchy: parentCat,
                };
            }

            return Array.from(tiles).map(extractProduct);
        }""")
        return products if isinstance(products, list) else []

    def _parse_unit_price(self, text: Optional[str]) -> tuple[Optional[float], Optional[str]]:
        """
        Parse unit price text like '$10.43 /kg' or '$1.78 /100g'.
        Returns (unit_price_amount, unit_type) e.g. (10.43, '/kg').
        Handles multiple unit prices ($X.XX /kg$Y.YY /lb) - picks the /kg one.
        """
        if not text:
            return None, None

        # Extract all price-unit pairs
        # Pattern: $X.XX /kg or $X.XX /lb. or $X.XX /100g
        pairs = re.findall(
            r'\$?([\d,.]+)\s*/\s*(kg|lb\.?|100g|ea\.?|unité|unit)',
            text,
            re.IGNORECASE,
        )

        if not pairs:
            return None, None

        # Prefer /kg over /lb, /100g, etc.
        preferred = None
        fallback = None
        for amount_str, unit in pairs:
            try:
                amount = float(amount_str.replace(",", "."))
            except ValueError:
                continue

            unit_key = f"/{unit.lower().rstrip('.')}"
            normalized = unit_key if unit_key.endswith("g") or unit_key.startswith("/kg") else unit_key

            if fallback is None:
                fallback = (amount, normalized)

            if "/kg" in normalized:
                preferred = (amount, normalized)
            elif preferred is None and "/lb" in normalized:
                preferred = (amount, normalized)
            elif preferred is None and "/100g" in normalized:
                preferred = (amount, normalized)

        result = preferred or fallback
        return result if result else (None, None)

    def _parse_weight(self, package_info: Optional[str]) -> Optional[str]:
        """Extract weight/size string from package info like 'A tray contains on average 1600 g'."""
        if not package_info:
            return None
        # Remove common prefix text
        cleaned = re.sub(
            r'^(A tray contains on average|Contains approximately|Approx\.)',
            '',
            package_info,
            flags=re.IGNORECASE,
        ).strip()
        # Return the number + unit pattern if present
        weight_match = re.search(r'([\d.]+\s*(?:g|kg|lb|oz|ml|L))', cleaned, re.IGNORECASE)
        if weight_match:
            return weight_match.group(1).strip()
        # Return cleaned text as-is if it looks like a weight
        if re.search(r'\d+\s*[gklozL]', cleaned):
            return cleaned.strip()
        return cleaned.strip() if cleaned else None

    def _format_product(self, raw: dict, meat_type: str) -> dict:
        """
        Normalize a raw product dict into the standard output format
        compatible with the aubaines-rapides DB schema.
        """
        unit_price, unit_type = self._parse_unit_price(raw.get("unit_price_text"))

        # Determine the current price
        current_price = raw.get("main_price")
        if current_price is None and raw.get("sale_price_text"):
            # Try to extract from sale price text
            sale_match = re.search(r'\$?([\d,.]+)', raw["sale_price_text"])
            if sale_match:
                try:
                    current_price = float(sale_match.group(1).replace(",", "."))
                except ValueError:
                    pass

        # Determine regular price
        regular_price = None
        if raw.get("has_sale") and raw.get("discount_price"):
            # If discount_price is given, compute regular = current + discount
            if current_price is not None:
                regular_price = round(current_price + raw["discount_price"], 2)
        elif not raw.get("has_sale"):
            regular_price = current_price

        # Extract category from hierarchy or meat_category field
        category = raw.get("meat_category") or ""

        return {
            "product_code": raw.get("product_code"),
            "name": raw.get("full_name") or raw.get("name"),
            "meat_type": meat_type,
            "category": category,
            "price": current_price,
            "regular_price": regular_price,
            "unit_price": unit_price,
            "unit_type": unit_type,
            "unit_price_text": raw.get("unit_price_text"),
            "sale_text": raw.get("sale_price_text"),
            "regular_price_text": raw.get("regular_price_text"),
            "package_weight": self._parse_weight(raw.get("package_info")),
            "package_info": raw.get("package_info"),
            "image_url": raw.get("image_url"),
            "has_sale": raw.get("has_sale", False),
            "discount_price": raw.get("discount_price"),
            "discount_percent": raw.get("discount_percent"),
            "is_weighted": raw.get("is_weighted", False),
            "valid_from": date.today().isoformat(),
            "valid_to": None,  # Super C doesn't surface valid_to in HTML
            "scraped_at": datetime.now().isoformat(),
            "meat_category": raw.get("meat_category"),
        }

    def _scrape_category(self, category_key: str) -> list[dict]:
        """
        Scrape all pages of a single category.
        Returns a list of normalized product dicts.
        """
        cat = CATEGORIES[category_key]
        meat_type = cat["meat_type"]
        slug = cat["slug"]
        products = []

        page_num = 1
        first_page_retries = 2 if page_num == 1 else 1
        retry_count = 0

        while True:
            if page_num == 1:
                url = f"{BASE_URL}{cat['url']}"
            else:
                url = f"{BASE_URL}{cat['url']}-page-{page_num}"

            print(f"  📄 Page {page_num}: {url}", file=sys.stderr)

            if not self._navigate(url):
                if retry_count < first_page_retries:
                    retry_count += 1
                    print(f"    ⚠️ Retrying ({retry_count}/{first_page_retries})...",
                          file=sys.stderr)
                    time.sleep(3)
                    continue
                break

            # Wait for product tiles to appear (handled in _navigate now)
            self._scroll_to_bottom()

            # Extract products
            raw_products = self._get_page_products()

            if not raw_products:
                # Check if there are any data-product-code elements at all
                product_count = self._page.evaluate(
                    "document.querySelectorAll('[data-product-code]').length"
                )
                if product_count == 0:
                    # Check for reCAPTCHA blocker
                    body_text = self._page.evaluate(
                        "document.body?.innerText?.substring(0, 500) || ''"
                    )
                    if "recaptcha" in body_text.lower() or "captcha" in body_text.lower():
                        print(f"    ⚠️ reCAPTCHA detected, waiting 10s...", file=sys.stderr)
                        self._page.wait_for_timeout(10000)
                        product_count = self._page.evaluate(
                            "document.querySelectorAll('[data-product-code]').length"
                        )
                        if product_count > 0:
                            raw_products = self._get_page_products()
                            if raw_products:
                                continue

                    if retry_count < first_page_retries:
                        retry_count += 1
                        print(f"    ⚠️ No products yet, retrying ({retry_count}/{first_page_retries})...",
                              file=sys.stderr)
                        time.sleep(3)
                        continue
                    print(f"    ✓ No more products (end of results)", file=sys.stderr)
                    break

                print(f"    ⚠️ Could not parse {product_count} product elements, but retrying...",
                      file=sys.stderr)
                self._page.wait_for_timeout(3000)
                raw_products = self._get_page_products()
                if not raw_products:
                    print(f"    ❌ Still could not parse products. Skipping page.",
                          file=sys.stderr)
                    break

            print(f"    → {len(raw_products)} products found", file=sys.stderr)

            for rp in raw_products:
                formatted = self._format_product(rp, meat_type)
                products.append(formatted)

            self.stats["products_found"] += len(raw_products)
            self.stats["products_extracted"] += len(products)
            self.stats["pages_scraped"] += 1
            retry_count = 0  # Reset retry count on successful page

            # Check if there's a next page
            next_page_exists = self._page.evaluate(f"""() => {{
                const links = document.querySelectorAll('a.ppn--element');
                return Array.from(links).some(
                    l => l.getAttribute('href')?.includes('-page-{page_num + 1}')
                );
            }}""")

            if not next_page_exists and page_num == 1:
                # Maybe page 1 shows pagination to page 2 differently
                next_page_exists = self._page.evaluate(f"""() => {{
                    return !!document.querySelector(
                        'a[href*="{slug}-page-2"]'
                    );
                }}""")

            if not next_page_exists:
                print(f"    ✓ No more pages", file=sys.stderr)
                break

            page_num += 1
            time.sleep(self.delay)

        return products

    # ── Main runner ───────────────────────────────────────────────────────

    def scrape(self, categories: Optional[list[str]] = None) -> dict:
        """
        Scrape product data from Super C.

        Args:
            categories: List of category keys to scrape ('beef', 'chicken', 'pork').
                        If None, all categories are scraped.

        Returns:
            Dict mapping category keys to list of product dicts.
        """
        if categories is None:
            categories = list(CATEGORIES.keys())

        print(f"\n{'='*60}", file=sys.stderr)
        print(f"🛒 SUPER C — Meat & Poultry Scraper", file=sys.stderr)
        print(f"📅 {date.today().isoformat()}", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)

        results: dict[str, list[dict]] = {}

        for cat_key in categories:
            if cat_key not in CATEGORIES:
                print(f"\n  ⚠️ Unknown category: {cat_key} (skip)", file=sys.stderr)
                continue

            print(f"\n  🥩 Category: {cat_key.upper()} ({CATEGORIES[cat_key]['meat_type']})",
                  file=sys.stderr)
            products = self._scrape_category(cat_key)
            results[cat_key] = products
            self.stats["categories_scraped"] += 1

        # Print stats
        total_products = sum(len(v) for v in results.values())
        print(f"\n{'='*60}", file=sys.stderr)
        print(f"📊 STATS", file=sys.stderr)
        print(f"  Categories:     {self.stats['categories_scraped']}", file=sys.stderr)
        print(f"  Pages scraped:  {self.stats['pages_scraped']}", file=sys.stderr)
        print(f"  Products:       {total_products}", file=sys.stderr)
        print(f"  Meat types:     {{beef: {len(results.get('beef', []))}, "
              f"chicken: {len(results.get('chicken', []))}, "
              f"pork: {len(results.get('pork', []))}}}",
              file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)

        return results

    def scrape_flat(self, categories: Optional[list[str]] = None) -> list[dict]:
        """Scrape and return a flat list of all products."""
        results = self.scrape(categories)
        flat = []
        for cat_key, cat_products in results.items():
            for p in cat_products:
                p["category_key"] = cat_key
                flat.append(p)
        return flat

    # ── DB integration ────────────────────────────────────────────────────

    def store_products(self, products: list[dict]):
        """Store scraped products into the aubaines-rapides database."""
        if not HAS_DB:
            print("⚠️  Cannot store to DB: db.schema not importable", file=sys.stderr)
            return

        db = get_db()
        merchant = "Super C"

        # Ensure Super C exists in stores
        db.execute(
            "INSERT OR IGNORE INTO stores (name, slug) VALUES (?, ?)",
            (merchant, "super-c"),
        )
        store = db.execute(
            "SELECT id FROM stores WHERE slug = ?", ("super-c",)
        ).fetchone()

        if not store:
            print("❌ Store 'Super C' not found in DB", file=sys.stderr)
            db.close()
            return

        store_id = store["id"]
        week_start = get_week_start()
        inserted = 0
        errors = 0

        for p in products:
            name = p.get("name", "")
            if not name:
                continue

            try:
                # Extraire le poids en grammes à partir du package_weight (ex: "1600 g" -> 1600)
                weight_g = None
                pw = self._parse_weight(p.get("package_info"))
                if pw:
                    m = re.match(r'([\d.]+)\s*(g|kg)', str(pw), re.IGNORECASE)
                    if m:
                        val = float(m.group(1))
                        unit = m.group(2).lower()
                        if unit == 'kg':
                            weight_g = int(val * 1000)
                        else:
                            weight_g = int(val)

                # Insert or get product
                db.execute(
                    """INSERT OR IGNORE INTO products (name, store_id, meat_type, category)
                       VALUES (?, ?, ?, ?)""",
                    (name, store_id, p.get("meat_type"), p.get("category")),
                )
                product = db.execute(
                    "SELECT id FROM products WHERE name = ? AND store_id = ?",
                    (name, store_id),
                ).fetchone()

                if not product:
                    continue

                product_id = product["id"]

                # Mettre à jour le poids si on en a un
                if weight_g:
                    db.execute(
                        "UPDATE products SET package_weight_g = ? WHERE id = ? AND package_weight_g IS NULL",
                        (weight_g, product_id),
                    )

                # Insert price history
                db.execute(
                    """INSERT INTO price_history
                       (product_id, price, regular_price, unit_price, unit_type,
                        sale_text, valid_from, valid_to, week_start, merchant_name, image_url)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        product_id,
                        p.get("price"),
                        p.get("regular_price"),
                        p.get("unit_price"),
                        p.get("unit_type"),
                        p.get("sale_text") or p.get("regular_price_text"),
                        p.get("valid_from"),
                        p.get("valid_to"),
                        week_start,
                        merchant,
                        p.get("image_url", ""),
                    ),
                )
                inserted += 1

            except Exception as e:
                print(f"  ⚠️ DB error for '{name}': {e}", file=sys.stderr)
                errors += 1

        db.commit()
        db.close()
        print(f"\n  💾 DB: {inserted} products stored, {errors} errors",
              file=sys.stderr)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Super C Meat & Poultry Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scraper_superc.py                    # scrape all, print JSON to stdout
  python scraper_superc.py --save             # scrape all, save to data/superc_products.json
  python scraper_superc.py --output out.json  # scrape all, save to custom path
  python scraper_superc.py --category beef    # scrape only beef
  python scraper_superc.py --category beef,chicken  # scrape beef and chicken
  python scraper_superc.py --headless false   # show browser window
  python scraper_superc.py --store            # scrape + save to database
        """,
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save output to default JSON file",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Custom output JSON file path",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Comma-separated categories: beef,chicken,pork (default: all)",
    )
    parser.add_argument(
        "--headless",
        type=str,
        default="true",
        choices=["true", "false"],
        help="Run browser in headless mode (default: true)",
    )
    parser.add_argument(
        "--store",
        action="store_true",
        help="Store results in the aubaines-rapides database",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=REQUEST_DELAY,
        help=f"Delay between page loads in seconds (default: {REQUEST_DELAY})",
    )

    args = parser.parse_args()

    # Parse categories
    categories = None
    if args.category:
        categories = [c.strip().lower() for c in args.category.split(",")]
        for c in categories:
            if c not in CATEGORIES:
                print(f"❌ Unknown category: {c}. Choose from: {', '.join(CATEGORIES.keys())}",
                      file=sys.stderr)
                sys.exit(1)

    headless = args.headless.lower() == "true"

    # Run scraper
    try:
        with SuperCScraper(headless=headless, delay=args.delay) as scraper:
            products = scraper.scrape_flat(categories)
    except Exception as e:
        print(f"\n❌ Scraper failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

    if not products:
        print("❌ No products scraped", file=sys.stderr)
        sys.exit(1)

    # Output JSON
    output_path = None
    if args.save:
        output_path = DEFAULT_OUTPUT
    elif args.output:
        output_path = args.output

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(products, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Saved {len(products)} products to {output_path}",
              file=sys.stderr)
    else:
        # Print to stdout (pipe-friendly)
        print(json.dumps(products, indent=2, ensure_ascii=False))

    # Optional DB store
    if args.store:
        with SuperCScraper(headless=headless, delay=args.delay) as scraper:
            scraper.store_products(products)

    return products


if __name__ == "__main__":
    main()
