#!/usr/bin/env python3
"""
Scraper Tigre Géant — Récupère la circulaire directement du site gianttiger.com
Utilise Playwright pour charger la page interactive et extraire items + images.
"""
import sys, os, json, re, time
from datetime import datetime, date
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db.schema import get_db, get_week_start
from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
CACHE_DIR = os.path.join(PROJECT_ROOT, "cache", "tigregeant")
FLYER_URL = "https://www.gianttiger.com/fr/collections/flyers-and-deals?view=flyers"

MEAT_KEYWORDS = {
    "boeuf": ["boeuf","bœuf","steak","haché","surlonge","burger","bifteck",
              "entrecôte","grillade","rôti de boeuf","rôti de bœuf","boston market"],
    "poulet": ["poulet","poitrine","cuisse","aile","pilons","blanc de poulet",
               "poulet entier","filet de poulet","poulet haché","la cage","nuggets"],
    "porc": ["porc","côtelette","jambon","bacon","saucisse","filet de porc",
             "longe de porc","gold label smokehouse"],
    "legume": ["légume","legume","carotte","brocoli","laitue","tomate","concombre",
               "oignon","patate","pomme de terre","salade","chou","maïs","épis",
               "poivron","haricot","bleuets","fraise","framboise","melon",
               "ananas","mangue","banane","orange","raisin","pomme","poire","citron"],
}

EXCLUDE_PATTERNS = [
    r'\bshampoo', r'\brevitalisant', r'\bnourriture\b.*\bchien\b', r'\bnourriture\b.*\bchat\b',
    r'\blitière', r'\bjouet', r'\baccessoire.*animal',
]


class TigreGeantScraper:
    def __init__(self):
        self.stats = {"items_found": 0, "items_saved": 0, "meat_items": 0}
        os.makedirs(CACHE_DIR, exist_ok=True)
    
    def classify_item(self, name: str) -> Optional[str]:
        name_lower = name.lower()
        for pat in EXCLUDE_PATTERNS:
            if re.search(pat, name_lower):
                return None
        best_type = None
        best_score = 0
        for mtype, kws in MEAT_KEYWORDS.items():
            for kw in kws:
                if kw in name_lower:
                    score = len(kw) / max(len(name_lower), 1)
                    if score > best_score:
                        best_score = score
                        best_type = mtype
        return best_type if best_score > 0.1 else "panier"
    
    def extract_price(self, text: str) -> Optional[float]:
        """Extrait le prix numérique d'un texte comme '$1.44 CH.' ou '$9 CH.' ou '2 POUR $6'"""
        if not text:
            return None
        text = text.replace(',', '.')
        # 2 POUR $6
        multi = re.search(r'(\d+)\s*(?:pour|POUR)\s*\$?([\d.]+)', text)
        if multi:
            qty = float(multi.group(1))
            total = float(multi.group(2))
            if qty > 0:
                return round(total / qty, 2)
        # $X.XX CH ou $X.XX
        simple = re.search(r'\$?([\d]+\.[\d]+)\s*(?:CH)?', text)
        if simple:
            val = float(simple.group(1))
            if val > 0:
                return val
        # $X CH (prix entier)
        simple_int = re.search(r'\$?([\d]+)\s*CH', text)
        if simple_int:
            val = float(simple_int.group(1))
            if val > 0:
                return val
        return None
    
    def extract_validity(self, text: str) -> tuple:
        """Extrait les dates de validité du texte de la circulaire."""
        dates = re.findall(r'(\d+\s*[a-zéû]+\s*-\s*\d+\s*[a-zéû]+)', text.lower())
        if dates:
            return (None, None)  # On utilisera la date de fin de semaine
        return (None, None)
    
    def run(self):
        print(f"\n{'='*60}")
        print(f"🐯 SCRAPER TIGRE GÉANT")
        print(f"📅 Semaine: {get_week_start()}")
        print(f"{'='*60}")
        
        items_data = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                locale="fr-CA",
            )
            page = context.new_page()
            
            print(f"  🌐 Chargement de la circulaire...")
            try:
                page.goto(FLYER_URL, timeout=45000, wait_until="networkidle")
            except PwTimeout:
                print("  ⚠️ Timeout sur le chargement initial, on continue...")
            
            time.sleep(5)  # Laisser le temps à l'iframe de charger
            
            # Accepter les cookies si présent
            try:
                accept = page.get_by_role("button", name="Accepter Tout")
                if accept.is_visible(timeout=3000):
                    accept.click()
                    time.sleep(2)
                    print("  ✅ Cookies acceptés")
            except:
                pass
            
            # Attendre que l'iframe de la circulaire soit chargé
            print("  📄 Extraction des items de la circulaire...")
            
            # Essayer de trouver les items dans l'iframe
            items = []
            try:
                # Chercher dans les iframes
                iframes = page.frames
                print(f"    {len(iframes)} iframes trouvés")
                
                for iframe in iframes:
                    try:
                        # Chercher les boutons avec des prix
                        buttons = iframe.get_by_role("button").all()
                        for btn in buttons:
                            label = btn.get_attribute("aria-label") or btn.text_content() or ""
                            if '$' in label or 'CH' in label:
                                items.append(label.strip())
                                self.stats["items_found"] += 1
                    except:
                        continue
            except Exception as e:
                print(f"    ⚠️ Erreur extraction: {e}")
            
            # Fallback: chercher dans la page principale
            if not items:
                print("    🔍 Fallback: recherche dans la page principale...")
                try:
                    all_buttons = page.get_by_role("button").all()
                    for btn in all_buttons:
                        label = btn.get_attribute("aria-label") or btn.text_content() or ""
                        if '$' in label and ('CH' in label or 'POUR' in label):
                            items.append(label.strip())
                except:
                    pass
            
            browser.close()
        
        # Traiter les items extraits
        print(f"\n  📦 {len(items)} items extraits de la circulaire")
        
        for item_text in items[:100]:  # Limiter à 100 items
            parsed = self.parse_item_text(item_text)
            if parsed:
                self.save_item(parsed)
        
        # ─── Enrichir avec images Shopify ───
        self.enrich_with_shopify_images()
        
        # Rapport
        print(f"\n{'='*60}")
        print(f"📊 RAPPORT TIGRE GÉANT")
        print(f"{'='*60}")
        print(f"  Items trouvés:      {self.stats['items_found']}")
        print(f"  Items sauvegardés:  {self.stats['items_saved']}")
        print(f"  Items viande:       {self.stats['meat_items']}")
        print(f"  Images Shopify:     {self.stats.get('shopify_images', 0)}")
        print(f"{'='*60}")
        
        return self.stats
    
    def parse_item_text(self, text: str) -> Optional[dict]:
        """Parse le texte d'un item de la circulaire en données structurées."""
        # Nettoie le texte: enlève les préfixes comme "Bleuets, 170 g, , $1.44 CH."
        # Format: "Produit, info, , $PRIX CH."
        # ou: "Produit, ÉCONOMISEZ X$, $PRIX CH."
        
        # Extraire le prix
        price = self.extract_price(text)
        if not price:
            return None
        
        # Extraire le nom du produit (tout avant le $)
        name_match = re.match(r'^(.*?)(?:,\s*ÉCONOMISEZ[^$]+\$?)?,\s*\$', text)
        if not name_match:
            # Fallback: prendre le début du texte
            name = text.split(',')[0].strip()
        else:
            name = name_match.group(1).strip()
        
        # Nettoyer le nom
        name = re.sub(r'\.\s*Sélectionnez.*$', '', name)  # Enlever le suffixe d'accessibilité
        name = re.sub(r'\s+', ' ', name).strip()
        
        if not name or len(name) < 3:
            return None
        
        # Classification
        meat_type = self.classify_item(name)
        
        # Image - on utilisera le screenshot de la circulaire comme référence
        image_url = None
        
        return {
            "name": name,
            "price": price,
            "meat_type": meat_type,
            "merchant": "Tigre Géant",
            "valid_to": None,
            "image_url": image_url,
        }
    
    def save_item(self, parsed: dict) -> bool:
        """Sauvegarde un item dans la base de données."""
        if not parsed or not parsed["name"]:
            return False
        
        db = get_db()
        try:
            # Trouver ou créer le store
            merchant = "Tigre Géant"
            db.execute(
                "INSERT OR IGNORE INTO stores (name, slug) VALUES (?, ?)",
                (merchant, "tigre-geant"),
            )
            
            store = db.execute(
                "SELECT id FROM stores WHERE name = ?", (merchant,)
            ).fetchone()
            if not store:
                return False
            store_id = store["id"]
            
            # Trouver ou créer le produit
            db.execute(
                """INSERT OR IGNORE INTO products (name, store_id, meat_type)
                   VALUES (?, ?, ?)""",
                (parsed["name"], store_id, parsed["meat_type"]),
            )
            product = db.execute(
                "SELECT id, meat_type FROM products WHERE name = ? AND store_id = ?",
                (parsed["name"], store_id),
            ).fetchone()
            if not product:
                return False
            product_id = product["id"]
            
            if product["meat_type"] != parsed["meat_type"]:
                db.execute("UPDATE products SET meat_type = ? WHERE id = ?",
                          (parsed["meat_type"], product_id))
            
            # Insérer l'historique de prix
            week_start = get_week_start()
            db.execute(
                """INSERT INTO price_history
                   (product_id, price, unit_type, sale_text, valid_from, valid_to,
                    week_start, merchant_name, image_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    product_id,
                    parsed["price"],
                    "ea",
                    f"${parsed['price']:.2f}",
                    None,
                    parsed["valid_to"],
                    week_start,
                    merchant,
                    parsed.get("image_url", ""),
                ),
            )
            db.commit()
            self.stats["items_saved"] += 1
            if parsed["meat_type"]:
                self.stats["meat_items"] += 1
            return True
            
        except Exception as e:
            print(f"  ⚠️ Erreur sauvegarde DB: {e}")
            db.rollback()
            return False
        finally:
            db.close()


    # ─── Enrichissement images Shopify ───
    def enrich_with_shopify_images(self):
        """Trouve les images Shopify pour les items TG sans image."""
        from difflib import SequenceMatcher
        from collections import defaultdict
        import urllib.request
        
        ACCENT_MAP = str.maketrans('éèêëàâäôöòûüùîïç', 'eeeeaaaooouuuiic')
        
        def normalize(name):
            n = name.lower().translate(ACCENT_MAP)
            n = re.sub(r'[^a-z0-9\s]', ' ', n)
            return re.sub(r'\s+', ' ', n).strip()
        
        def keywords(name):
            words = normalize(name).split()
            stop = {'le','la','les','de','du','des','un','une','et','au','aux',
                    'en','sur','par','pour','avec','sans','dans','est','ou','pas',
                    'plus','format','chaque','pack','paquet','sac','boite','boîte',
                    'sachet','ml','g','kg','lb','oz','x','environ','emb','bte'}
            return [w for w in words if len(w) > 2 and w not in stop]
        
        def similarity(a, b):
            a_n, b_n = normalize(a), normalize(b)
            if a_n == b_n:
                return 1.0
            seq = SequenceMatcher(None, a_n, b_n).ratio()
            a_kw, b_kw = set(keywords(a)), set(keywords(b))
            if not a_kw or not b_kw:
                return seq * 0.5
            jaccard = len(a_kw & b_kw) / len(a_kw | b_kw)
            return 0.5 * seq + 0.5 * jaccard
        
        # Charger/fetch produits Shopify
        shopify_path = os.path.join(CACHE_DIR, 'shopify_products.json')
        products = []
        
        if os.path.exists(shopify_path):
            with open(shopify_path) as f:
                products = json.load(f).get('products', [])
            print(f"  🛒 {len(products)} produits Shopify chargés (cache)")
        else:
            print("  🛒 Téléchargement des produits Shopify...")
            page = 1
            while True:
                url = f"https://www.gianttiger.com/fr/collections/flyers-and-deals/products.json?limit=250&page={page}"
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        data = json.loads(resp.read())
                        batch = data.get("products", [])
                        if not batch:
                            break
                        products.extend(batch)
                        page += 1
                except:
                    break
            with open(shopify_path, 'w') as f:
                json.dump({"products": products}, f, ensure_ascii=False)
            print(f"  ✅ {len(products)} produits Shopify téléchargés")
        
        # Corrections manuelles
        MANUAL = {
            "Étiquette Or Fumoir bacon": "Bacon fumée Gold Label - 375 g",
            "Étiquette Or fumoir bacon": "Bacon fumée Gold Label - 375 g",
            "Gold Label Smoke House Bacon": "Bacon fumée Gold Label - 375 g",
            "Étiquette Or original lanières de saucisses": "Lanières de saucisse Gold Label Original, 300 g",
            "Gold Label Original Sausage Strips": "Lanières de saucisse Gold Label Original, 300 g",
            "Boston Market Turkey Breast Cutlettes": "Escalopes de poitrine de dinde Boston Market, 369 g",
            "High Liner English Style Fillets": "High Liner Filets en Pâte à l'Anglaise, 500 g",
            "La Cage Regular Chicken Nuggets": "La Cage Pépites de Poulet Régulier, 550 g",
            "Aqua Star Pacific White Shrimp": "Crevettes blanches du Pacifique Aqua Star - 340 g",
            "Aqua Star White Pacific Shrimp": "Crevettes blanches du Pacifique Aqua Star - 340 g",
        }
        
        def manual_match(name):
            name_lower = name.lower()
            for k, v in MANUAL.items():
                if k.lower() in name_lower:
                    for p in products:
                        if similarity(v, p.get('title', '')) > 0.5:
                            for var in p.get('variants', []):
                                img = var.get('featured_image', {}) or {}
                                url = img.get('src', '') if img else ''
                                if url:
                                    return url
            return None
        
        # Trouver les items dans la DB qui n'ont pas d'image
        db = get_db()
        rows = db.execute("""
            SELECT ph.id, p.name, ph.price
            FROM price_history ph
            JOIN products p ON ph.product_id = p.id
            JOIN stores s ON p.store_id = s.id
            WHERE s.name = 'Tigre Géant'
              AND (ph.image_url IS NULL OR ph.image_url = '')
              AND ph.week_start = ?
        """, (get_week_start(),)).fetchall()
        
        if not rows:
            print(f"  ✅ Tous les items ont déjà une image")
            db.close()
            return
        
        print(f"  🔍 {len(rows)} items sans image → recherche Shopify...")
        updated = 0
        
        for r in rows:
            name = r['name']
            price = r['price']
            
            img_url = manual_match(name)
            
            if not img_url:
                # Fuzzy matching
                best = None
                best_score = 0
                for p in products:
                    title = p.get('title', '')
                    for v in p.get('variants', []):
                        p_price = float(v.get('price', 0))
                        img = v.get('featured_image', {}) or {}
                        url = img.get('src', '') if img else ''
                        if not url:
                            continue
                        score = similarity(name, title)
                        if abs(p_price - price) < 0.5:
                            score += 0.15
                        if score > best_score:
                            best_score = score
                            best = url
                
                if best and best_score >= 0.4:
                    img_url = best
            
            if img_url:
                db.execute("UPDATE price_history SET image_url = ? WHERE id = ?", (img_url, r['id']))
                updated += 1
        
        db.commit()
        db.close()
        self.stats['shopify_images'] = updated
        print(f"  ✅ {updated} images Shopify ajoutées")


def main():
    postal = os.environ.get("POSTAL_CODE", "J7Y4A2")
    scraper = TigreGeantScraper()
    scraper.run()


if __name__ == "__main__":
    main()
