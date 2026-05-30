"""!produit — Meilleurs deals viande, simple & vendeur"""
import sys, os, re, unicodedata
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db.schema import get_db

def strip_accents(s):
    s = s.replace("œ","oe").replace("Œ","OE").replace("æ","ae").replace("Æ","AE")
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))

STORE_EMOJIS = {"Super C":"🟡","Metro":"🔴","IGA":"🟢","Maxi":"🟠","Provigo":"🟣","Walmart":"🔵","Costco":"⭕"}
def store_emoji(name):
    for k,v in STORE_EMOJIS.items():
        if k in name: return v
    return "🏪"

MEAT_EMOJI = {"boeuf":"🥩","poulet":"🍗","porc":"🥓"}

DEFAULT_WEIGHTS = {
    "boeuf hache":0.454, "porc hache":0.450, "poulet hache":0.454,
    "veau hache":0.454, "dinde hache":0.454, "bacon":0.375,
    "jambon fume":0.300, "jambon":0.200, "cotelette porc":0.250,
    "filet porc":0.500, "saucisse fume":0.375, "saucisse":0.375,
    "filet poulet":0.450, "poitrine poulet":0.450,
    "ailes poulet":0.450, "cuisse poulet":0.250,
}

def find_default_weight(name):
    n = strip_accents(name.lower())
    for kw,w in DEFAULT_WEIGHTS.items():
        if kw in n: return w
    return None

def extract_weight_kg(name):
    n = name.lower()
    m = re.search(r'(\d+[,.]?\d*)\s*(kg|kilo|g|lb|lbs|livre|livres)\b', n)
    if m:
        q = float(m.group(1).replace(",","."))
        u = m.group(2).lower()
        if u=="g": return q/1000
        if u in ("lb","lbs","livre","livres"): return round(q*0.453592,3)
        return q
    return None

def short_name(name, maxlen=35):
    n = name[:maxlen]
    if len(name) > maxlen: n += "…"
    return n

def main():
    if len(sys.argv) < 2:
        query = input("🔍 Quel produit chercher ? ")
    else:
        query = " ".join(sys.argv[1:])
    if not query.strip():
        print("❌ Essaie: haché, steak, poitrine, bacon, côtelette...")
        return

    db = get_db()
    terms = [strip_accents(t).lower() for t in query.lower().strip().split()]
    max_week = db.execute("SELECT MAX(week_start) as w FROM price_history").fetchone()["w"]
    rows = db.execute("""
        SELECT p.id, p.name, p.meat_type, p.package_weight_g,
               s.name as store, ph.price, ph.unit_price, ph.unit_type,
               ph.valid_to, ph.merchant_name, ph.image_url
        FROM products p
        JOIN stores s ON s.id = p.store_id
        JOIN price_history ph ON ph.product_id = p.id
        WHERE ph.week_start = ? AND ph.price IS NOT NULL AND p.meat_type IS NOT NULL
        ORDER BY ph.price ASC LIMIT 3000
    """, (max_week,)).fetchall()
    db.close()

    results, seen = [], set()
    for r in rows:
        if all(t in strip_accents(r["name"]).lower() for t in terms):
            k = (r["name"], r["merchant_name"])
            if k not in seen:
                seen.add(k)
                results.append(r)

    if not results:
        print(f"\n❌ Rien pour « {query} » cette semaine.")
        return

    # Enrichir chaque résultat
    enriched = []
    for r in results:
        per_kg = None
        w_kg = None
        source = "?"

        # 1) Poids fixe DB
        if r["package_weight_g"] and r["price"]:
            w_kg = r["package_weight_g"] / 1000
            per_kg = r["price"] / w_kg
            source = "réel"

        # 2) Prix unitaire de l'image
        if per_kg is None and r["unit_price"]:
            ut = r["unit_type"] or ""
            if "/kg" in ut:
                per_kg = r["unit_price"]
                if r["price"] and per_kg > 0: w_kg = round(r["price"]/per_kg, 3)
                source = "image"
            elif "/100g" in ut:
                per_kg = r["unit_price"] * 10
                if r["price"] and per_kg > 0: w_kg = round(r["price"]/per_kg, 3)
                source = "image"

        # 3) Poids dans le nom
        if per_kg is None:
            w = extract_weight_kg(r["name"])
            if w and r["price"]:
                w_kg = w
                per_kg = r["price"] / w
                source = "nom"

        # 4) Estimation
        is_est = False
        if per_kg is None:
            w = find_default_weight(r["name"])
            if w and r["price"]:
                w_kg = w
                per_kg = r["price"] / w
                source = "estimé"
                is_est = True

        enriched.append({"r":r, "per_kg":per_kg, "source":source, "is_est":is_est})

    # Trier
    enriched.sort(key=lambda x: (
        0 if x["per_kg"] else 1,
        x["per_kg"] if x["per_kg"] and x["per_kg"] > 0 else 99999,
        x["r"]["price"] or 0
    ))

    with_kg = [e for e in enriched if e["per_kg"]]
    wo_kg = [e for e in enriched if not e["per_kg"]]

    # ─── TITRE ───
    mtypes = set(r["meat_type"] for r in results if r["meat_type"])
    emoji = MEAT_EMOJI.get(list(mtypes)[0],"🥩") if len(mtypes)==1 else "🥩🍗🥓"
    print(f"\n{emoji}  {query.upper()} × {len(results)} offres")

    # ─── TOP 5 ───
    for i, e in enumerate(with_kg[:5], 1):
        r = e["r"]
        tag = ""
        if e["source"] == "réel": tag = " ✅"
        elif e["source"] == "estimé": tag = " ~"
        per_lb = round(e["per_kg"] / 2.20462, 2) if e["per_kg"] else 0
        name_short = short_name(r["name"], 30)
        link = ""
        if r["image_url"]:
            link = f" · [🔗]({r['image_url']})"
        print(f"\n{i}. {store_emoji(r['merchant_name'])} {r['merchant_name']}")
        print(f"   {name_short}")
        print(f"   💰 {r['price']:.2f}$  ·  {e['per_kg']:.2f}$/kg  ·  {per_lb:.2f}$/lb{tag}{link}")
        if r["valid_to"]:
            print(f"   ⏳ jusqu'au {r['valid_to']}")

    # ─── SANS PRIX/KG ───
    if wo_kg:
        print(f"\n📋 Autres offres (pas de $/kg)")
        for e in wo_kg[:3]:
            r = e["r"]
            name_short = short_name(r["name"], 35)
            print(f"   {store_emoji(r['merchant_name'])} {r['merchant_name']} — {r['price']:.2f}$ — {name_short}")

    # ─── MEILLEUR ACHAT ───
    if with_kg:
        b = with_kg[0]
        r = b["r"]
        per_lb = round(b["per_kg"] / 2.20462, 2) if b["per_kg"] else 0
        name_short = short_name(r["name"], 40)
        tag = " ✅ poids réel" if b["source"] == "réel" else ""
        print(f"\n{'═'*35}")
        print(f"🏆  MEILLEUR ACHAT")
        print(f"{'═'*35}")
        print(f"   {store_emoji(r['merchant_name'])} {r['merchant_name']}")
        print(f"   {name_short}")
        print(f"   💰 {r['price']:.2f}$  →  {b['per_kg']:.2f}$/kg  ({per_lb:.2f}$/lb){tag}")
        if r["valid_to"]:
            print(f"   ⏳ Jusqu'au {r['valid_to']}")
        print(f"{'═'*35}")
    print()

if __name__ == "__main__":
    main()
