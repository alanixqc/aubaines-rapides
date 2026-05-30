#!/usr/bin/env python3
"""
Maxi & Provigo (Loblaws Group) Meat Scraper
=============================================
Scrapes meat product data from Maxi (maxi.ca) and Provigo (provigo.ca)
using the Flipp flyers-ng API (primary) and backflipp wishabi API (fallback).

Strategies (in order of preference):
  1. Flyers-ng API: Get the full flyer for Maxi and Provigo, filter meat items
  2. Backflipp items/search API: Search for meat keywords, filter by merchant
  3. PC Express API: POST to search endpoint (currently returning 500/502)

Output: JSON array of product objects compatible with the aubaines-rapides DB schema.

Usage:
    python scraper_maxi.py                              # scrape all + print JSON
    python scraper_maxi.py --save                       # scrape and save to file
    python scraper_maxi.py --output out.json            # save to custom path
    python scraper_maxi.py --banner maxi                # scrape only Maxi
    python scraper_maxi.py --banner provigo             # scrape only Provigo
    python scraper_maxi.py --db                         # insert into database
    python scraper_maxi.py --search-only                # use backflipp search (fallback)
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

# ── HTTP imports ──────────────────────────────────────────────────────────────
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# ═══════════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════════

MERCHANTS = {
    "maxi": {
        "name": "Maxi",
        "slug": "maxi",
        "flyer_ids": [],  # populated at runtime
    },
    "provigo": {
        "name": "Provigo",
        "slug": "provigo",
        "flyer_ids": [],
    },
}

POSTAL_CODE = "J7Y5H5"
LOCALE = "fr"
FLIPP_BASE = "https://flyers-ng.flippback.com/api/flipp"
BACKFLIPP_BASE = "https://backflipp.wishabi.com/flipp"
REQUEST_DELAY = 0.3

DEFAULT_OUTPUT = os.path.join(
    os.path.dirname(__file__), "..", "data", "maxi_provigo_products.json",
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "fr-CA,fr;q=0.9,en-CA;q=0.8,en;q=0.7",
}

# ── Meat classification patterns ─────────────────────────────────────────────
# Enhanced from the existing Flipp scraper patterns

MEAT_CLASSIFIERS = {
    "boeuf": [
        r"\bbœ?uf\b", r"\bsteak\b", r"\bbifteck\b", r"\brôti\s+de\s+bœ?uf\b",
        r"\bcôte\s+de\s+bœ?uf\b", r"\bbœ?uf\s+haché\b", r"\bhaché\s+de\s+bœ?uf\b",
        r"\btournedos\b", r"\bentrecôte\b", r"\bfilet\s+mignon\b",
        r"\bribeye\b", r"\bsirloin\b", r"\bcontre-filet\b",
        r"\bfaux-filet\b", r"\bbraise\b", r"\bbourguignon\b",
        r"\bground\s+beef\b", r"\bbeef\b", r"\bburger\b",
        r"\bhamburger\b", r"\bsteak\s+haché\b", r"\bchuck\b",
        r"\bintérieur\s+de\s+ronde\b", r"\binside\s+round\b",
        r"\bcôte\s+levée\b", r"\bspare\s+ribs?\b",
        r"\bbrisket\b", r"\bflank\b",
    ],
    "poulet": [
        r"\bpoulet\b", r"\bpoitrine\s+de\s+poulet\b", r"\bcuisse\s+de\s+poulet\b",
        r"\bpilon\b", r"\bpilons?\b", r"\baile?\s+de\s+poulet\b",
        r"\bdinde\b", r"\bdindon\b", r"\bcanard\b",
        r"\bsupreme\s+de\s+poulet\b", r"\bblanc\s+de\s+poulet\b",
        r"\bpoulet\s+entier\b", r"\bpoulet\s+frais\b",
        r"\bpoulet\s+haché\b", r"\bpoulet\s+pané\b",
        r"\bchicken\b", r"\bturkey\b", r"\bchicken\s+breast\b",
        r"\bchicken\s+wings\b", r"\bchicken\s+thighs?\b",
        r"\bdrumsticks?\b", r"\bchicken\s+drumsticks?\b",
        r"\bnuggets?\b", r"\bnugget\b",
        r"\blanières?\s+de\s+poulet\b",
        r"\bescalope\s+de\s+poulet\b", r"\bescalopes?\s+de\s+poitrine\b",
        r"\bhaut\s+de\s+cuisse\b", r"\bdemi-poulet\b",
        r"\bfilet\s+de\s+poulet\b",
    ],
    "porc": [
        r"\bporc\b", r"\bfilet\s+de\s+porc\b", r"\bcôtelette\s+de\s+porc\b",
        r"\bbacon\b", r"\bjambon\b", r"\bsaucisse\b",
        r"\bcôtes\s+levées\b", r"\bribs?\b",
        r"\bbaby\s+back\s+ribs\b", r"\bspare\s+ribs\b",
        r"\blard\b", r"\bcochon\b", r"\blardon\b",
        r"\bporc\s+haché\b", r"\bsaucisses?\s+italiennes?\b",
        r"\bsaucisses?\s+merguez\b", r"\bwieners?\b",
        r"\bpork\b", r"\bpork\s+chops?\b", r"\bpork\s+tenderloin\b",
        r"\bhot.?dogs?\b", r"\bhot.?dog\b",
        r"\bkolbassa\b", r"\bkielbasa\b",
        r"\bsausage\b", r"\bsmoked\s+meat\b",
        r"\bham\b", r"\bpepperoni\b", r"\bsalami\b",
        r"\bloin\s+chop\b", r"\bpork\s+loin\b",
        r"\blonge\s+de\s+porc\b", r"\bcarré\s+de\s+porc\b",
        r"\bjarret\b", r"\bcou\s+de\s+porc\b",
        r"\bporc\s+effiloché\b", r"\bpulled\s+pork\b",
    ],
    "agneau": [
        r"\bagneau\b", r"\bagneaux\b", r"\bcôte\s+d'agneau\b",
        r"\bgigot\s+d'agneau\b", r"\blamb\b",
        r"\bépaule\s+d'agneau\b", r"\blamb\s+shoulder\b",
    ],
    "veau": [
        r"\bveau\b", r"\bescalope\s+de\s+veau\b",
        r"\bcôte\s+de\s+veau\b", r"\bveal\b",
        r"\bfoie\s+de\s+veau\b", r"\bveal\s+liver\b",
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
        r"\bpangasius\b", r"\bbasa\b", r"\bgoberge\b",
    ],
}

# Compiled meat matcher
MEAT_PATTERN = re.compile(
    "|".join(p for pats in MEAT_CLASSIFIERS.values() for p in pats),
    re.IGNORECASE,
)

# Exclusion patterns — items that match meat keywords but aren't meat
EXCLUDE_PATTERNS = [
    r"\bshampoo", r"\brevitalisant", r"\bchampignon", r"\bchampfleury",
    r"\bcantaloup", r"\btomate", r"\bpain", r"\bbun\b",
    r"\bpersonnelle", r"\bnourriture\b.{0,200}chiens?\b",
    r"\bpet\s+food\b", r"\bdog\s+food\b",
    r"\bmuffin", r"\bgâteau", r"\bmaïs\b",
    r"\bvegan\b", r"\bvég[ée]\b", r"\bvégétal",
    r"\bsalade\s+hachée\b", r"\bchopped\s+salad\b",
    r"\bsalade\s+de\s+thon\b",
    r"\bsauce\b.*\bchicken\b", r"\bsauce\b.*\bpoulet\b",
    r"\bassaisonnement\b", r"\bépice\b",
    r"\bgâterie", r"\btraiter", r"\btreat\b",
    r"\bcollation\b.*\bchien\b", r"\bdog\s+treat\b",
    r"\bcollation\s+de\s+viande",
]

# ── Meat keywords for broad flyer filtering ──────────────────────────────────
FLYER_MEAT_KEYWORDS = [
    "boeuf", "bœuf", "steak", "haché", "poulet", "poitrine", "cuisse",
    "porc", "côtelette", "bacon", "jambon", "saucisse", "viande",
    "chicken", "beef", "pork", "sausage", "ham", "ribs", "côte",
    "filet", "rôti", "grillade", "pilon", "aile", "dinde", "dindon",
    "agneau", "veau", "poisson", "saumon", "burger", "brochette",
    "escalope", "lanière", "bifteck", "brisket", "flank", "ground",
    "tenderloin", "loin", "liver", "foie",
]


# ═══════════════════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_sid() -> str:
    """Generate a session ID for the Flipp API."""
    import random
    return "".join(str(random.randint(0, 9)) for _ in range(16))


def classify_meat_type(name: str) -> str:
    """Classify meat type from product name using regex patterns.
    
    Priority:
      1. Explicit meat-type keywords (boeuf/bœuf/porc/poulet/chicken/pork etc.)
      2. Generic cuts (steak, filet, rôti, etc.) - but only if no other meat type explicit
    """
    name_lower = name.lower()

    # Check exclusions first
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, name_lower):
            return "autre"

    # Priority 1: Explicit meat-type keywords
    explicit_patterns = {
        "boeuf": [r"\bbœ?uf\b", r"\bbeef\b", r"\bground\s+beef\b"],
        "poulet": [r"\bpoulet\b", r"\bchicken\b", r"\bdinde\b", r"\bdindon\b", r"\bturkey\b", r"\bcanard\b"],
        "porc": [r"\bporc\b", r"\bpork\b", r"\bjambon\b", r"\bham\b", r"\bbacon\b"],
        "agneau": [r"\bagneau\b", r"\bagneaux\b", r"\blamb\b"],
        "veau": [r"\bveau\b", r"\bveal\b"],
        "poisson": [r"\bpoisson\b", r"\bsaumon\b", r"\bsalmon\b", r"\bcrevette\b", r"\bseafood\b",
                    r"\bfish\b", r"\bthon\b", r"\btruite\b", r"\bmorue\b", r"\bcod\b",
                    r"\bsole\b", r"\bpangasius\b", r"\bbasa\b", r"\bgoberge\b"],
    }
    for meat_type, patterns in explicit_patterns.items():
        for pattern in patterns:
            if re.search(pattern, name_lower):
                return meat_type

    # Priority 2: Generic meat cuts
    for meat_type, patterns in MEAT_CLASSIFIERS.items():
        for pattern in patterns:
            if re.search(pattern, name_lower):
                return meat_type

    return "autre"


def extract_price(price_text: str) -> tuple[Optional[float], Optional[float], Optional[str]]:
    """
    Extract numeric price from text.
    Returns (price, compare_at_price, unit_type).
    Handles formats: "2/6,00$", "3,99$/lb", "5.49$/kg", "$4.99", "4.99", "8.0"
    """
    if not price_text:
        return None, None, None

    price_text = str(price_text).strip()

    # Simple number
    simple_match = re.match(r'^(\d+\.?\d*)$', price_text)
    if simple_match:
        return float(simple_match.group(1)), None, None

    # Comma decimal: "4,99"
    simple_comma = re.match(r'^(\d+,\d+)$', price_text)
    if simple_comma:
        return float(simple_comma.group(1).replace(",", ".")), None, None

    # Multi-buy: "2/6,00$"
    multi_match = re.match(r'(\d+)\s*/\s*([\d.,]+)\s*\$\s*', price_text)
    if multi_match:
        qty = float(multi_match.group(1))
        total = float(multi_match.group(2).replace(",", "."))
        return round(total / qty, 2), None, "ea"

    # Unit price: "3,99$/lb" or "5.49$/kg"
    unit_match = re.search(r'([\d.,]+)\s*[$€]\s*/\s*(\w+)', price_text)
    if unit_match:
        price = float(unit_match.group(1).replace(",", "."))
        unit_type = f"/{unit_match.group(2)}"
        return price, None, unit_type

    # $ prefix: "$4.99" or "4,99$"
    price_match = re.search(r'([\d.,]+)\s*[$€]', price_text)
    if price_match:
        price = float(price_match.group(1).replace(",", "."))
        return price, None, None

    return None, None, None


# ═══════════════════════════════════════════════════════════════════════════════
# Scraper Classes
# ═══════════════════════════════════════════════════════════════════════════════

class MaxiProvigoScraper:
    """
    Scrapes Maxi and Provigo meat products using the Flipp flyers-ng API
    with backflipp search as fallback.
    """

    def __init__(self, banners: Optional[list[str]] = None,
                 search_only: bool = False, delay: float = REQUEST_DELAY):
        if not HAS_REQUESTS:
            raise ImportError("requests is required. Install: pip install requests")

        if banners is None:
            banners = ["maxi", "provigo"]
        self.banners = [b.lower() for b in banners]
        self.search_only = search_only
        self.delay = delay
        self.sid = _generate_sid()
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.stats = {
            "api_calls": 0,
            "flyers_found": 0,
            "flyer_items": 0,
            "meat_candidates": 0,
            "products_output": 0,
        }
        self._all_products = []

    # ── API Methods ──────────────────────────────────────────────────────

    def _api_get(self, url: str) -> Optional[dict]:
        """Make a GET request to the Flipp/Backflipp API."""
        time.sleep(self.delay)
        self.stats["api_calls"] += 1
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"  ⚠️ API Error: {e}", file=sys.stderr)
            return None

    # ── Strategy 1: Flyers-ng API ────────────────────────────────────────

    def _find_flyers(self) -> dict[str, list[int]]:
        """
        Find current flyer IDs for Maxi and Provigo.
        Returns {banner: [flyer_id, ...]}
        """
        url = f"{FLIPP_BASE}/data?locale={LOCALE}&postal_code={POSTAL_CODE}&sid={self.sid}"
        data = self._api_get(url)
        if not data or "flyers" not in data:
            return {}

        flyers = data.get("flyers", [])
        banner_flyers: dict[str, list[int]] = {b: [] for b in self.banners}

        for flyer in flyers:
            merchant = flyer.get("merchant", "").lower()
            for banner in self.banners:
                if merchant == banner:
                    banner_flyers[banner].append(flyer["id"])
                    self.stats["flyers_found"] += 1

        return banner_flyers

    def _get_flyer_items(self, flyer_id: int, default_merchant: str = "") -> list[dict]:
        """Get all items from a specific flyer."""
        url = f"{FLIPP_BASE}/flyers/{flyer_id}/flyer_items?locale={LOCALE}&sid={self.sid}"
        data = self._api_get(url)
        if not data or not isinstance(data, list):
            return []
        # Some items may not have merchant — set it from the flyer
        if default_merchant:
            for item in data:
                if not item.get("merchant"):
                    item["merchant"] = default_merchant
        return data

    # ── Strategy 2: Backflipp Search API ─────────────────────────────────

    def _search_items(self, merchant: str, query: str) -> list[dict]:
        """Search for items via the backflipp search API."""
        url = (
            f"{BACKFLIPP_BASE}/items/search"
            f"?locale={LOCALE}-ca"
            f"&postal_code={POSTAL_CODE}"
            f"&q={merchant}%20{query}"
        )
        data = self._api_get(url)
        if not data:
            return []
        items = data.get("items", [])
        # Filter to ensure we only get items from this merchant
        filtered = [
            item for item in items
            if item.get("merchant_name", "").lower() == merchant.lower()
        ]
        return filtered

    # ── Item Processing ──────────────────────────────────────────────────

    def _is_meat_item(self, name: str) -> bool:
        """Check if an item name is meat-related using broad keyword filter."""
        name_lower = name.lower()
        return any(kw in name_lower for kw in FLYER_MEAT_KEYWORDS)

    def _classify_and_filter(self, name: str) -> Optional[str]:
        """Classify meat type, returns None if not meat (after exclusions)."""
        meat_type = classify_meat_type(name)
        if meat_type == "autre":
            return None
        return meat_type

    def _process_item(self, item: dict, banner: str) -> Optional[dict]:
        """
        Process a single flyer/search item into the standard output format.
        Returns None if the item should be filtered out.
        """
        name = item.get("name", "").strip()
        if not name:
            return None

        # Classification
        meat_type = self._classify_and_filter(name)
        if not meat_type:
            return None

        self.stats["meat_candidates"] += 1

        # Price extraction
        raw_price = item.get("price", "") or item.get("current_price", "")
        compare_price_raw = item.get("original_price", None)

        price, unit_price, unit_type = extract_price(str(raw_price))
        compare_at_price = float(compare_price_raw) if compare_price_raw else None

        # Image URL
        image_url = (
            item.get("cutout_image_url", "") or
            item.get("clean_image_url", "") or
            item.get("clipping_image_url", "") or
            ""
        )

        # Dates
        valid_from = item.get("valid_from", "")
        valid_to = item.get("valid_to", "")
        if valid_from and len(valid_from) > 10:
            valid_from = valid_from[:10]
        if valid_to and len(valid_to) > 10:
            valid_to = valid_to[:10]

        # Merchant
        merchant_name = (
            item.get("merchant") or
            item.get("merchant_name") or
            banner.capitalize()
        )

        result = {
            "name": name,
            "price": price,
            "compare_at_price": compare_at_price,
            "unit_price": unit_price,
            "unit_type": unit_type,
            "sale_text": str(raw_price) if raw_price else None,
            "valid_from": valid_from or date.today().isoformat(),
            "valid_to": valid_to or None,
            "image_url": image_url,
            "merchant": merchant_name,
            "meat_type": meat_type,
            "category": self._determine_category(name, meat_type),
            "flyer_item_id": item.get("id") or item.get("flyer_item_id"),
            "scraped_at": datetime.now().isoformat(),
        }

        self.stats["products_output"] += 1
        return result

    def _determine_category(self, name: str, meat_type: str) -> str:
        """Determine a sub-category from the product name."""
        name_lower = name.lower()
        categories = {
            "haché": r"\bhach[ée]\b",
            "steak": r"\b(steak|bifteck)\b",
            "poitrine": r"\bpoitrine\b",
            "cuisse": r"\bcuisse\b",
            "aile": r"\baile\b",
            "côtelette": r"\bcôtelette\b",
            "rôti": r"\br[ôo]ti\b",
            "filet": r"\bfilet\b",
            "saucisse": r"\bsaucisse\b",
            "bacon": r"\bbacon\b",
            "jambon": r"\bjambon\b",
            "côte levée": r"\bc[ôo]te\s+lev[eé]e\b|ribs",
            "escalope": r"\bescalope\b",
            "brochette": r"\bbrochette\b",
        }
        for cat_name, pattern in categories.items():
            if re.search(pattern, name_lower):
                return cat_name
        return meat_type  # fallback to meat type

    # ── Scraping Pipeline ────────────────────────────────────────────────

    def scrape_via_flyers(self) -> list[dict]:
        """Strategy 1: Fetch flyer items for Maxi and Provigo."""
        print("  📋 Strategy: Flyers-ng API", file=sys.stderr)

        banner_flyers = self._find_flyers()
        if not banner_flyers:
            print("  ⚠️ No flyers found via Flipp API", file=sys.stderr)
            return []

        all_products = []

        for banner in self.banners:
            flyer_ids = banner_flyers.get(banner, [])
            if not flyer_ids:
                print(f"  ⚠️ No flyers found for {banner}", file=sys.stderr)
                continue

            merchant_name = MERCHANTS[banner]["name"]
            for fid in flyer_ids:
                print(f"  📄 {merchant_name} flyer #{fid}...", file=sys.stderr)
                items = self._get_flyer_items(fid, default_merchant=merchant_name)
                if not items:
                    continue

                self.stats["flyer_items"] += len(items)
                print(f"     {len(items)} items in flyer", file=sys.stderr)

                for item in items:
                    name = item.get("name", "")
                    if not self._is_meat_item(name):
                        continue
                    processed = self._process_item(item, banner)
                    if processed:
                        all_products.append(processed)

        return all_products

    def scrape_via_search(self) -> list[dict]:
        """Strategy 2: Search backflipp for meat items by merchant."""
        print("  📋 Strategy: Backflipp Search API", file=sys.stderr)

        meat_searches = ["boeuf", "poulet", "porc", "viande", "steak",
                         "bacon", "jambon", "saucisse"]
        all_products = []
        seen_names = set()

        for banner in self.banners:
            merchant_name = MERCHANTS[banner]["name"]
            for query in meat_searches:
                print(f"  🔍 Searching {merchant_name} for '{query}'...", file=sys.stderr)
                items = self._search_items(banner, query)
                if not items:
                    continue

                for item in items:
                    name = item.get("name", "").strip()
                    if not name:
                        continue
                    # Deduplicate
                    if name in seen_names:
                        continue
                    seen_names.add(name)

                    processed = self._process_item(item, banner)
                    if processed:
                        all_products.append(processed)

        return all_products

    def scrape(self) -> list[dict]:
        """Run the full scraping pipeline."""
        if not HAS_REQUESTS:
            raise ImportError("requests is required. Install: pip install requests")

        banners_str = ", ".join(m.capitalize() for m in self.banners)
        print(f"\n{'='*60}", file=sys.stderr)
        print(f"🛒 MAXI / PROVIGO — Meat Scraper", file=sys.stderr)
        print(f"   Banners: {banners_str}", file=sys.stderr)
        print(f"   Postal: {POSTAL_CODE}", file=sys.stderr)
        print(f"   Date: {date.today().isoformat()}", file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)

        all_products = []

        if not self.search_only:
            # Strategy 1: Try flyers first
            flyer_products = self.scrape_via_flyers()
            all_products.extend(flyer_products)
            print(f"\n  ✅ Flyers method: {len(flyer_products)} products", file=sys.stderr)

        # Strategy 2: Always try search to supplement
        search_products = self.scrape_via_search()
        # Deduplicate with flyer results
        existing_names = {p["name"] for p in all_products}
        for p in search_products:
            if p["name"] not in existing_names:
                all_products.append(p)
        print(f"  ✅ Search method: {len(search_products)} products "
              f"({len(search_products) - (len(all_products) - len(flyer_products))} new)",
              file=sys.stderr)

        # Sort by meat_type then name
        all_products.sort(key=lambda x: (x.get("meat_type", ""), x.get("name", "")))

        # Print summary
        print(f"\n{'='*60}", file=sys.stderr)
        print(f"📊 RESULTS", file=sys.stderr)
        print(f"   API calls:        {self.stats['api_calls']}", file=sys.stderr)
        print(f"   Meat candidates:  {self.stats['meat_candidates']}", file=sys.stderr)
        print(f"   Final products:   {self.stats['products_output']}", file=sys.stderr)
        print(f"   Deduplicated:     {len(all_products)}", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)

        # Breakdown by meat type
        for mt in ["boeuf", "poulet", "porc", "agneau", "veau", "poisson"]:
            count = sum(1 for p in all_products if p["meat_type"] == mt)
            if count:
                print(f"  🥩 {mt}: {count} products", file=sys.stderr)

        return all_products


# ═══════════════════════════════════════════════════════════════════════════════
# DB Insertion
# ═══════════════════════════════════════════════════════════════════════════════

def insert_to_db(products: list[dict]):
    """Insert scraped products into the aubaines-rapides database."""
    if not HAS_DB:
        print("⚠️ Cannot insert into DB: db.schema not available", file=sys.stderr)
        return

    conn = get_db()
    week_start = get_week_start()

    inserted = 0
    errors = 0
    for p in products:
        merchant = p.get("merchant", "").strip()
        if not merchant:
            continue

        try:
            # Get or create store
            slug = merchant.lower().replace(" ", "-").replace("é", "e").replace("è", "e")
            conn.execute(
                "INSERT OR IGNORE INTO stores (name, slug) VALUES (?, ?)",
                (merchant, slug),
            )
            cur = conn.execute(
                "SELECT id FROM stores WHERE name = ?", (merchant,)
            )
            row = cur.fetchone()
            if not row:
                errors += 1
                continue
            store_id = row["id"]

            # Upsert product
            conn.execute(
                """INSERT OR IGNORE INTO products (name, store_id, meat_type, category)
                   VALUES (?, ?, ?, ?)""",
                (p["name"], store_id, p["meat_type"], p.get("category")),
            )

            # Get product id
            cur = conn.execute(
                "SELECT id FROM products WHERE name = ? AND store_id = ?",
                (p["name"], store_id),
            )
            product_row = cur.fetchone()
            if not product_row:
                errors += 1
                continue
            product_id = product_row["id"]

            # Insert price history
            conn.execute(
                """INSERT INTO price_history
                   (product_id, price, regular_price, unit_type, sale_text,
                    valid_from, valid_to, week_start, merchant_name, image_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    product_id,
                    p.get("price"),
                    p.get("compare_at_price"),
                    p.get("unit_type"),
                    p.get("sale_text"),
                    p.get("valid_from"),
                    p.get("valid_to"),
                    week_start,
                    merchant,
                    p.get("image_url", ""),
                ),
            )
            inserted += 1

        except Exception as e:
            errors += 1
            print(f"  ⚠️ DB error for '{p.get('name', '')}': {e}", file=sys.stderr)

    conn.commit()
    conn.close()
    print(f"\n💾 DB Inserted: {inserted} products, {errors} errors", file=sys.stderr)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Maxi & Provigo Meat Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--save", action="store_true",
                        help="Save output to default path")
    parser.add_argument("--output", type=str, default=None,
                        help="Custom output JSON file path")
    parser.add_argument("--banner", type=str, default=None,
                        choices=["maxi", "provigo"],
                        help="Scrape only one banner (default: both)")
    parser.add_argument("--db", action="store_true",
                        help="Insert results into database")
    parser.add_argument("--pretty", action="store_true",
                        help="Pretty-print JSON output")
    parser.add_argument("--search-only", action="store_true",
                        help="Use only backflipp search API (skip flyers-ng)")
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY,
                        help=f"Request delay in seconds (default: {REQUEST_DELAY})")

    args = parser.parse_args()

    # Determine banners
    banners = ["maxi", "provigo"]
    if args.banner:
        banners = [args.banner]

    # Create scraper
    scraper = MaxiProvigoScraper(
        banners=banners,
        search_only=args.search_only,
        delay=args.delay,
    )

    # Run
    results = scraper.scrape()

    # Output
    json_kwargs = {"ensure_ascii": False}
    if args.pretty or args.save or args.output:
        json_kwargs["indent"] = 2

    if args.output:
        output_path = args.output
    elif args.save:
        output_path = DEFAULT_OUTPUT
    else:
        output_path = None

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, **json_kwargs)
        print(f"\n💾 Saved: {output_path}", file=sys.stderr)
    else:
        print(json.dumps(results, ensure_ascii=False, indent=2))

    # Optional DB insert
    if args.db and results:
        insert_to_db(results)

    return results


if __name__ == "__main__":
    main()
