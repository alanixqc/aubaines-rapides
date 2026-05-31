#!/usr/bin/env python3
"""
generate_banner.py — Génère la bannière des 5 meilleurs spéciaux de la semaine
pour le site Aubaines Rapides. À lancer chaque jeudi.
"""

import json
import os
from PIL import Image, ImageDraw, ImageFont

# ── Config ─────────────────────────────────────
DEALS_FILE = os.path.expanduser("~/aubaines-rapides/web/data/deals.json")
BG_FILE = os.path.expanduser("~/AppData/Local/hermes/images/banner_bg.png")
OUTPUT_FILE = os.path.expanduser("~/aubaines-rapides/web/images/banner-semaine.png")
FONT_DIR = "C:/Windows/Fonts"

BANNER_W = 1536
BANNER_H = 512
CARD_W = 265
CARD_H = 370
CARD_GAP = 18
MARGIN_X = 30
CARDS_START_Y = 100

# ── Fonts ──────────────────────────────────────
def get_font(name, size):
    path = os.path.join(FONT_DIR, name)
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()

FONT_BOLD_36 = get_font("arialbd.ttf", 36)
FONT_BOLD_28 = get_font("arialbd.ttf", 28)
FONT_BOLD_20 = get_font("arialbd.ttf", 20)
FONT_BOLD_18 = get_font("arialbd.ttf", 18)
FONT_BOLD_14 = get_font("arialbd.ttf", 14)
FONT_REG_16 = get_font("arial.ttf", 16)
FONT_REG_14 = get_font("arial.ttf", 14)
FONT_REG_12 = get_font("arial.ttf", 12)

# ── Store colors ────────────────────────────────
STORE_COLORS = {
    "Super C": (255, 200, 0),
    "Maxi": (0, 140, 200),
    "Provigo": (0, 160, 80),
    "IGA": (220, 60, 60),
    "Loblaws": (30, 30, 150),
    "Tigre Géant": (200, 100, 30),
    "L'Inter-Marché": (180, 60, 120),
    "Walmart": (0, 100, 200),
    "Metro": (0, 100, 50),
}

def get_store_color(store):
    for key, color in STORE_COLORS.items():
        if key.lower() in store.lower():
            return color
    return (120, 120, 120)

CAT_EMOJIS = {
    "poulet": "🐔", "boeuf": "🐄", "porc": "🐷", "legume": "🥦",
    "fruit": "🍎", "poisson": "🐟", "crevettes": "🦐", "fromage": "🧀",
    "yogourt": "🥛", "pain": "🍞", "panier": "🧺", "agneau": "🐑",
    "veau": "🐄", "jambon": "🥩", "saucisse": "🌭",
}

def cat_emoji(cat):
    for k, v in CAT_EMOJIS.items():
        if k in cat.lower():
            return v
    return "🏷️"


def truncate(text, max_len):
    return text if len(text) <= max_len else text[:max_len-1] + "…"


def load_banner_bg():
    """Load background or create a gradient fallback."""
    if os.path.exists(BG_FILE):
        bg = Image.open(BG_FILE).convert("RGBA")
        return bg.resize((BANNER_W, BANNER_H), Image.LANCZOS)
    # Fallback: gradient
    img = Image.new("RGBA", (BANNER_W, BANNER_H), (30, 40, 50, 255))
    draw = ImageDraw.Draw(img)
    for i in range(BANNER_H):
        r = int(30 + (i / BANNER_H) * 40)
        g = int(40 + (i / BANNER_H) * 30)
        b = int(50 + (i / BANNER_H) * 20)
        draw.line([(0, i), (BANNER_W, i)], fill=(r, g, b, 255))
    return img


def load_top_deals(n=5):
    """Load top N deals by cheapest $/kg."""
    with open(DEALS_FILE) as f:
        data = json.load(f)

    all_deals = (data["deals"]["deals_with_kg"] +
                 data["deals"]["deals_wo_kg"])

    # Filter those with valid per_kg
    valid = [d for d in all_deals if d.get("per_kg") and d["per_kg"] > 0]
    valid.sort(key=lambda d: d["per_kg"])

    top = valid[:n]
    # If not enough, add deals without kg sorted by price
    if len(top) < n:
        wo_kg = [d for d in all_deals if not (d.get("per_kg") and d["per_kg"] > 0)]
        wo_kg.sort(key=lambda d: float(d.get("price", 9999)))
        top.extend(wo_kg[:n - len(top)])

    return top


def draw_card(draw, x, y, w, h, deal, rank):
    """Draw a single deal card at position (x, y)."""
    store = deal.get("store", "")
    name = deal.get("name", "")
    price = deal.get("price", "")
    per_kg = deal.get("per_kg", "")
    per_lb = deal.get("per_lb", "")
    cat = deal.get("category", "")
    protein = deal.get("protein_per_dollar", "")
    pct_off = deal.get("pct_off", "")

    store_color = get_store_color(store)

    # Card shadow
    draw.rounded_rectangle([(x+3, y+3), (x+w+3, y+h+3)], radius=14, fill=(0, 0, 0, 60))

    # Card background
    draw.rounded_rectangle([(x, y), (x+w, y+h)], radius=14, fill=(255, 255, 255, 235))

    # Rank badge (top-left circle)
    badge_r = 22
    bx = x + 14
    by = y + 14
    draw.ellipse([(bx, by), (bx + badge_r*2, by + badge_r*2)], fill=(200, 30, 30, 230))
    rank_text = str(rank)
    bbox = draw.textbbox((0, 0), rank_text, font=FONT_BOLD_20)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((bx + badge_r - tw//2, by + badge_r - th//2 - 1), rank_text,
              font=FONT_BOLD_20, fill=(255, 255, 255, 255))

    # Category emoji
    emoji = cat_emoji(cat)
    draw.text((x + w - 40, y + 12), emoji, font=FONT_REG_16, fill=(100, 100, 100, 180))

    # Store name with color dot
    dot_y = y + 50
    draw.ellipse([(x + 14, dot_y + 3), (x + 22, dot_y + 11)], fill=store_color)
    draw.text((x + 28, dot_y), store[:12], font=FONT_BOLD_14, fill=(80, 80, 80, 255))

    # Product name
    name_lines = truncate(name, 60)
    # If name too long, split into two lines
    name_font = FONT_BOLD_18
    name_y = dot_y + 28
    bbox = draw.textbbox((0, 0), name_lines, font=name_font)
    nw = bbox[2] - bbox[0]
    if nw > w - 28:
        # Try splitting
        words = name_lines.split()
        line1 = ""
        line2 = ""
        half = len(words) // 2
        line1 = " ".join(words[:half])
        line2 = " ".join(words[half:])
        draw.text((x + 14, name_y), truncate(line1, 30), font=name_font, fill=(30, 30, 30, 255))
        draw.text((x + 14, name_y + 24), truncate(line2, 30), font=name_font, fill=(30, 30, 30, 255))
        name_h = 48
    else:
        draw.text((x + 14, name_y), name_lines, font=name_font, fill=(30, 30, 30, 255))
        name_h = 24

    # Price
    price_y = name_y + name_h + 10
    price_font = FONT_BOLD_28
    price_text = f"{price}$"
    # Color based on store
    price_color = (200, 50, 50) if store in ["Super C", "IGA"] else (220, 100, 20)
    draw.text((x + 14, price_y), price_text, font=price_font, fill=price_color)

    # Per kg
    ppkg_y = price_y + 36
    if per_kg:
        draw.text((x + 14, ppkg_y), f"{per_kg}$/kg", font=FONT_BOLD_14, fill=(100, 100, 100, 255))
    
    # Per lb
    pplb_y = ppkg_y + 22
    if per_lb:
        draw.text((x + 14, pplb_y), f"{per_lb}$/lb", font=FONT_REG_14, fill=(140, 140, 140, 220))

    # Protein badge
    if protein:
        prot_y = pplb_y + 26
        prot_text = f"\U0001f4aa {protein}g/$"
        bbox = draw.textbbox((0, 0), prot_text, font=FONT_REG_12)
        ptw = bbox[2] - bbox[0]
        pth = bbox[3] - bbox[1]
        bp = 5
        prot_bx = x + w - ptw - bp*2 - 12
        draw.rounded_rectangle([(prot_bx, prot_y), (prot_bx + ptw + bp*2, prot_y + pth + bp*2)],
                               radius=5, fill=(50, 140, 50, 160))
        draw.text((prot_bx + bp, prot_y + bp), prot_text, font=FONT_REG_12, fill=(255, 255, 255, 240))

    # % off badge if available
    if pct_off and float(pct_off) > 0:
        off_y = y + 120
        off_text = f"-{pct_off}%"
        bbox = draw.textbbox((0, 0), off_text, font=FONT_BOLD_14)
        otw = bbox[2] - bbox[0]
        oth = bbox[3] - bbox[1]
        op = 5
        draw.rounded_rectangle([(x + w - otw - op*2 - 14, off_y), (x + w - 14, off_y + oth + op*2)],
                               radius=5, fill=(200, 50, 50, 180))
        draw.text((x + w - otw - op - 14, off_y + op), off_text, font=FONT_BOLD_14, fill=(255, 255, 255, 240))


def build_banner():
    deals = load_top_deals(5)
    print(f"Top 5 deals loaded:")
    for i, d in enumerate(deals):
        print(f"  {i+1}. [{d.get('store','')}] {d.get('name','')[:50]} — {d.get('price','')}$ ({d.get('per_kg','?')}$/kg)")

    bg = load_banner_bg()
    draw = ImageDraw.Draw(bg)

    # Dark overlay for readability
    overlay = Image.new("RGBA", (BANNER_W, BANNER_H), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    for i in range(BANNER_H):
        alpha = int(100 + (1 - i / BANNER_H) * 80)
        overlay_draw.line([(0, i), (BANNER_W, i)], fill=(0, 0, 0, min(alpha, 160)))
    bg.paste(overlay, (0, 0), overlay)

    draw = ImageDraw.Draw(bg)

    # ── Header ──────────────────────────────────
    # Title
    title = "Meilleurs spéciaux de la semaine"
    bbox = draw.textbbox((0, 0), title, font=FONT_BOLD_36)
    tw = bbox[2] - bbox[0]
    draw.text((BANNER_W//2 - tw//2, 28), title, font=FONT_BOLD_36, fill=(255, 255, 255, 245))

    # Subtitle
    week = "Semaine du 31 mai 2026"  # TODO: auto-compute from current week
    bbox = draw.textbbox((0, 0), week, font=FONT_REG_14)
    tw = bbox[2] - bbox[0]
    draw.text((BANNER_W//2 - tw//2, 72), week, font=FONT_REG_14, fill=(200, 200, 200, 200))

    # ── Cards ───────────────────────────────────
    total_w = 5 * CARD_W + 4 * CARD_GAP
    start_x = (BANNER_W - total_w) // 2

    for i, deal in enumerate(deals):
        x = start_x + i * (CARD_W + CARD_GAP)
        draw_card(draw, x, CARDS_START_Y, CARD_W, CARD_H, deal, i+1)

    # ── Footer watermark ────────────────────────
    draw.text((20, BANNER_H - 30), "Aubaines Rapides", font=FONT_BOLD_14, fill=(255, 255, 255, 100))

    # Save
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    bg.save(OUTPUT_FILE, "PNG")
    print(f"\nBanner saved: {OUTPUT_FILE}")
    print(f"Size: {os.path.getsize(OUTPUT_FILE)} bytes")

    # Also save a webp version for faster loading
    webp_path = OUTPUT_FILE.replace(".png", ".webp")
    bg.save(webp_path, "WEBP", quality=85)
    print(f"WebP saved: {webp_path}")
    print(f"WebP size: {os.path.getsize(webp_path)} bytes")


if __name__ == "__main__":
    build_banner()
