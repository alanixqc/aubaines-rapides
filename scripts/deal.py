#!/usr/bin/env python3
"""!deal — Meilleur deal viande de la semaine (filtré par code postal)"""

import sys, os, re, unicodedata
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db.schema import get_db
from scripts.nearby_stores import find_nearby_store_names


def strip_accents(s):
    s = s.replace("œ", "oe").replace("Œ", "OE").replace("æ", "ae").replace("Æ", "AE")
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


STORE_EMOJIS = {
    "Super C": "🟡", "Metro": "🔴", "IGA": "🟢", "Maxi": "🟠",
    "Provigo": "🟣", "Walmart": "🔵", "Costco": "⭕",
    "Tigre Géant": "🐯", "Les Marchés Tradition": "🟤",
}

def store_emoji(name):
    for k, v in STORE_EMOJIS.items():
        if k in name:
            return v
    return "🏪"


MEAT_EMOJI = {"boeuf": "🥩", "poulet": "🍗", "porc": "🥓", "legume": "🥦", "légume": "🥦"}


DEFAULT_WEIGHTS = {
    "boeuf hache": 0.454, "porc hache": 0.450, "poulet hache": 0.454,
    "veau hache": 0.454, "dinde hache": 0.454, "bacon": 0.375,
    "jambon fume": 0.300, "jambon": 0.200, "cotelette porc": 0.250,
    "filet porc": 0.500, "saucisse fume": 0.375, "saucisse": 0.375,
    "filet poulet": 0.450, "poitrine poulet": 0.450,
    "ailes poulet": 0.450, "cuisse poulet": 0.250,
}

# Protéines en grammes pour 100g de viande CRUE (source: Fichier canadien des éléments nutritifs)
# Références:
#   Poulet: FCÉN 2018 via Manitoba Chicken (canada.ca)
#   Boeuf haché: FCÉN 2015 via Canada Beef (cdnbeefperforms.ca)
#   Steaks/maigres: FCÉN 2007 via Statistique Canada (statcan.gc.ca)
# Clé: (meat_type, mot-clef) → g protéines/100g
# Ordre: du plus spécifique au plus général

PROTEIN_TABLE = [
    # Boeuf — FCÉN (Canada Beef 2015, StatCan 2007)
    (("boeuf", "hache extra-maigre"), 21),  # FCÉN 4996 — avec/sans trait d'union
    (("boeuf", "hache extra maigre"), 21),
    (("boeuf", "extra-maigre"), 21),
    (("boeuf", "extra maigre"), 21),
    (("boeuf", "hache maigre"), 20),        # FCÉN 2683 — max 17% MG
    (("boeuf", "hache mi-maigre"), 19),     # FCÉN 2690 — max 23% MG
    (("boeuf", "hache mi maigre"), 19),
    (("boeuf", "hache"), 17),               # FCÉN 2786 — max 30% MG (régulier)
    (("boeuf", "steak"), 23),               # FCÉN — coupe maigre crue
    (("boeuf", "bifteck"), 23),
    (("boeuf", "surlonge"), 23),
    (("boeuf", "filet mignon"), 23),
    (("boeuf", "filet"), 23),
    (("boeuf", "roti"), 23),
    (("boeuf", "rôti"), 23),
    (("boeuf", "cube"), 22),
    (("boeuf", "bourguignon"), 22),
    (("boeuf", "boulette"), 18),
    (("boeuf", "burger"), 18),
    (("boeuf", "brisket"), 22),
    (("boeuf", "côte"), 21),
    (("boeuf", "cote"), 21),
    (("boeuf", "flanc"), 21),
    (("boeuf", "franc"), 21),
    (("boeuf", "entrecôte"), 23),
    (("boeuf", "entrecote"), 23),
    (("boeuf", "tournedos"), 23),
    # Poulet — FCÉN 2018 (Manitoba Chicken)
    (("poulet", "poitrine"), 23),            # FCÉN 2018 — peau enlevée, crue
    (("poulet", "filet"), 23),
    (("poulet", "cuisse"), 20),              # FCÉN 2018 — peau enlevée, crue
    (("poulet", "haut de cuisse"), 20),
    (("poulet", "aile"), 18),                # FCÉN — drumette/wingette crue
    (("poulet", "entier"), 19),
    (("poulet", "hache extra-maigre"), 18),  # FCÉN — extra maigre ≈ moins gras
    (("poulet", "hache extra maigre"), 18),
    (("poulet", "extra-maigre"), 18),
    (("poulet", "extra maigre"), 18),
    (("poulet", "hache"), 17),               # FCÉN 2018 — poulet haché cru
    (("poulet", "haché"), 17),
    (("poulet", "souvlaki"), 20),
    (("poulet", "brochette"), 20),
    (("poulet", "désossé"), 21),
    (("poulet", "desosse"), 21),
    (("poulet", "pilons"), 18),              # drumette
    (("poulet", "haut"), 18),
    (("poulet", "pané"), 16),
    (("poulet", "pane"), 16),
    (("poulet", "nugget"), 14),
    (("poulet", "croquette"), 14),
    # Porc — FCÉN 2007 (StatCan: coupe maigre = 22.1g/100g)
    (("porc", "longe"), 22),                 # coupe maigre
    (("porc", "filet"), 22),                 # tenderloin — le plus maigre
    (("porc", "côtelette"), 20),
    (("porc", "cotelette"), 20),
    (("porc", "côte"), 20),
    (("porc", "cote"), 20),
    (("porc", "hache maigre"), 18),          # moins gras → plus de protéines
    (("porc", "haché maigre"), 18),
    (("porc", "hache extra-maigre"), 19),
    (("porc", "hache extra maigre"), 19),
    (("porc", "hache"), 17),
    (("porc", "haché"), 17),
    (("porc", "bacon"), 12),
    (("porc", "jambon fume"), 20),
    (("porc", "jambon fumé"), 20),
    (("porc", "jambon"), 18),
    (("porc", "saucisse fume"), 14),
    (("porc", "saucisse fumé"), 14),
    (("porc", "saucisse"), 14),
    (("porc", "roti"), 22),
    (("porc", "rôti"), 22),
    (("porc", "souvlaki"), 18),
    (("porc", "brochette"), 18),
    (("porc", "côte levé"), 20),
    (("porc", "côte levée"), 20),
    (("porc", "cote leve"), 20),
    (("porc", "fum"), 21),
]

# Valeur par défaut par type de viande (si rien trouvé dans la table)
PROTEIN_FALLBACK = {"boeuf": 22, "poulet": 20, "porc": 20}


def get_protein_per_100g(name, meat_type):
    """Retourne les g de protéines/100g pour un produit."""
    if not meat_type:
        return 26
    meat_type = meat_type.lower()
    n = strip_accents(name.lower())
    # Chercher le match le plus spécifique (premier gagnant)
    for (mt, kw), val in PROTEIN_TABLE:
        if mt == meat_type and kw in n:
            return val
    # Fallback
    return PROTEIN_FALLBACK.get(meat_type, 26)


# Items exclus
EXCLUDE_PATTERNS = [
    "pour chien", "pour chiens", "pour chat", "pour chats",
    "dog chow", "purina", "whiskas", "friskies", "pedigree",
    "bonkers", "gâterie", "gaterie", "treat", "lick",
    "bouillon", "cube de", "poudre de",
    "aliment sec", "aliments secs", "nourriture sèche",
    "litière", "litiere", "tastefuls",
    "à mâcher", "a macher",
    "bâtonnet", "batonnet",
    "biscuit pour",
    "croustille", "chips",
    "sauce salade", "vinaigrette salade", "tartinade salade",
    "salade de", "kit de salade",
    "salade hachée", "salades hachées", "salade hachee", "salades hachees",
    "salade gastronomique", "salade plaisir",
]


def is_excluded(name):
    n = strip_accents(name.lower())
    for p in EXCLUDE_PATTERNS:
        if p in n:
            return True
    return False


def find_default_weight(name):
    n = strip_accents(name.lower())
    for kw, w in DEFAULT_WEIGHTS.items():
        if kw in n:
            return w
    return None


def extract_weight_kg(name):
    n = name.lower()
    m = re.search(r'(\d+[,.]?\d*)\s*(kg|kilo|g|lb|lbs|livre|livres)\b', n)
    if m:
        q = float(m.group(1).replace(",", "."))
        u = m.group(2).lower()
        if u == "g":
            return q / 1000
        if u in ("lb", "lbs", "livre", "livres"):
            return round(q * 0.453592, 3)
        return q
    return None


def short_name(name, maxlen=35):
    n = name[:maxlen]
    if len(name) > maxlen:
        n += "…"
    return n


def enrich(r):
    """Calcule le $/kg pour un item et retourne (per_kg, source, is_est, weight_kg)."""
    per_kg = None
    weight_kg = None
    source = "?"
    is_est = False

    # 1) Poids fixe DB (vision)
    if r["package_weight_g"] and r["price"]:
        weight_kg = r["package_weight_g"] / 1000
        per_kg = r["price"] / weight_kg
        source = "réel"

    # 2) Prix unitaire de l'image
    if per_kg is None and r["unit_price"]:
        ut = r["unit_type"] or ""
        if "/kg" in ut:
            per_kg = r["unit_price"]
            source = "image"
        elif "/100g" in ut:
            per_kg = r["unit_price"] * 10
            source = "image"

    # 3) Poids dans le nom
    if per_kg is None:
        w = extract_weight_kg(r["name"])
        if w and r["price"]:
            weight_kg = w
            per_kg = r["price"] / w
            source = "nom"

    # 4) Estimation par défaut
    if per_kg is None:
        w = find_default_weight(r["name"])
        if w and r["price"]:
            weight_kg = w
            per_kg = r["price"] / w
            source = "estimé"
            is_est = True

    # Calculer weight_kg si pas encore fait (pour les cas unit_price sans price)
    if weight_kg is None and per_kg and r["price"] and per_kg > 0:
        weight_kg = r["price"] / per_kg

    return per_kg, source, is_est, weight_kg


def format_price_line(price, per_kg, source, image_url):
    tag = ""
    if source == "réel":
        tag = " ✅"
    elif source == "estimé":
        tag = " ~"
    per_lb = per_kg / 2.20462
    return f"💰 {price:.2f}$  ·  {per_kg:.2f}$/kg  ·  {per_lb:.2f}$/lb{tag}"


def format_protein_line(name, meat_type, price, weight_kg):
    """Calcule et formate les infos nutritionnelles."""
    # Legumes -> afficher la categorie plutot que proteines
    if meat_type and meat_type.lower() in ("legume", "legume"):
        return "   🥦 Legume frais"
    prot_100g = get_protein_per_100g(name, meat_type)

    # Protéines par livre
    prot_lb = prot_100g * 4.536  # 453.6g/lb ÷ 100g

    # Protéines totales dans le paquet
    if weight_kg and weight_kg > 0:
        total_prot = weight_kg * 10 * prot_100g  # kg→g × (prot/100g)
    else:
        total_prot = None

    # Protéines par dollar
    if total_prot and price and price > 0:
        prot_per_dollar = total_prot / price
        return f"💪 {prot_100g}g/100g  ·  ~{prot_lb:.0f}g/lb  ·  {prot_per_dollar:.1f}g/$"
    else:
        return f"💪 {prot_100g}g/100g  ·  ~{prot_lb:.0f}g/lb"


def main():
    # Code postal optionnel (défaut: J7Z 1J6 — Saint-Jérôme)
    postal = sys.argv[1] if len(sys.argv) > 1 else "J7Z 1J6"

    db = get_db()
    max_week = db.execute("SELECT MAX(week_start) as w FROM price_history").fetchone()["w"]

    rows = db.execute(
        """SELECT p.id, p.name, p.meat_type, p.package_weight_g,
                  s.name as store, ph.price, ph.unit_price, ph.unit_type,
                  ph.valid_to, ph.merchant_name, ph.image_url
           FROM products p
           JOIN stores s ON s.id = p.store_id
           JOIN price_history ph ON ph.product_id = p.id
           WHERE ph.week_start = ? AND ph.price IS NOT NULL AND p.meat_type IS NOT NULL
           ORDER BY ph.price ASC LIMIT 3000""",
        (max_week,),
    ).fetchall()
    db.close()

    # Enrichir + filtrer exclus + dédoublonner (name+merchant)
    enriched = []
    seen = set()
    for r in rows:
        if is_excluded(r["name"]):
            continue
        key = (r["name"], r["merchant_name"])
        if key in seen:
            continue
        seen.add(key)
        per_kg, source, is_est, weight_kg = enrich(r)
        if per_kg:
            enriched.append({
                "r": r, "per_kg": per_kg, "source": source, "is_est": is_est,
                "weight_kg": weight_kg,
            })

    if not enriched:
        print("😕 Pas de deal à afficher cette semaine.")
        return

    # ─── FILTRE PAR MAGASINS À PROXIMITÉ ───
    nearby = find_nearby_store_names(postal)
    if nearby:
        enriched = [e for e in enriched if e["r"]["merchant_name"] in nearby]
        if not enriched:
            print("😕 Aucun deal dans les épiceries près de chez toi cette semaine.")
            return

    # Trier: meilleur $/kg en premier
    enriched.sort(key=lambda x: (
        x["per_kg"] if x["per_kg"] and x["per_kg"] > 0 else 99999,
        x["r"]["price"] or 0,
    ))

    # ─── SÉPARER VIANDE ET LÉGUMES ───
    meat_items = [e for e in enriched if e["r"]["meat_type"] != "legume"]
    veg_items = [e for e in enriched if e["r"]["meat_type"] == "legume"]

    # ─── AFFICHAGE VIANDE (top 3) ───
    def print_item(medal, e):
        r = e["r"]
        print(f"\n{medal}  {store_emoji(r['merchant_name'])} **{r['merchant_name']}**")
        print(f"   {short_name(r['name'], 35)}")
        print(f"   {format_price_line(r['price'], e['per_kg'], e['source'], r['image_url'])}")
        print(f"   {format_protein_line(r['name'], r['meat_type'], r['price'], e['weight_kg'])}")
        if r["valid_to"]:
            print(f"   ⏳ {r['valid_to']}")
        if r["image_url"]:
            print(f"   ![]({r['image_url']})")

    if meat_items:
        print("\n🥩  TOP 3 VIANDE")
        print_item("🏆", meat_items[0])
        if len(meat_items) >= 2:
            print_item("🥈", meat_items[1])
        if len(meat_items) >= 3:
            print_item("🥉", meat_items[2])

    if veg_items:
        print("\n🥦  TOP 3 LÉGUMES")
        print_item("🏆", veg_items[0])
        if len(veg_items) >= 2:
            print_item("🥈", veg_items[1])
        if len(veg_items) >= 3:
            print_item("🥉", veg_items[2])

    # ─── FOOTER ───
    store_list = ", ".join(f"{store_emoji(s)}{s}" for s in (nearby if nearby else ["tous"]))
    print(f"\n📍 {postal.upper()} · {store_list}")
    print(f"📊 {len(enriched)} offres · !produit [nom] pour plus")

    # Info fiabilité
    est_count = sum(1 for e in enriched if e["source"] == "estimé")
    real_count = sum(1 for e in enriched if e["source"] in ("réel", "image"))
    if est_count > real_count and real_count < 5:
        print("📝 Données de cette semaine seulement. Les vrais deals apparaîtront dans ~3-4 semaines.")

    print()


if __name__ == "__main__":
    main()
