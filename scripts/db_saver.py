#!/usr/bin/env python3
"""db_saver.py — Utilitaire pour sauvegarder les données scrapées dans la DB.
Tous les scrapers peuvent importer save_to_db() pour écriture unifiée."""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db.schema import get_db
from datetime import date, datetime, timedelta

def get_week_start(d=None):
    """Retourne la date du jour (YYYY-MM-DD) pour grouper les prix par jour de scraping.
    NOTE: build_site.py utilise directement week_start comme clé de semaine."""
    d = d or date.today()
    return d.isoformat()

def save_products_to_db(products, merchant_name, slug=None):
    """Sauvegarde une liste de produits scrapés dans aubaines.db.
    
    Args:
        products: liste de dict avec name, price, was_price (optionnel), image, store
        merchant_name: nom du marchand (ex: 'Maxi', 'IGA')
    """
    db = get_db()
    week_start = get_week_start()
    
    # ── Trouver ou créer le store ──
    store = db.execute("SELECT id FROM stores WHERE name = ?", (merchant_name,)).fetchone()
    if not store:
        slug = slug or merchant_name.lower().replace(" ", "-")
        db.execute("INSERT INTO stores (name, slug) VALUES (?, ?)", (merchant_name, slug))
        db.commit()
        store = db.execute("SELECT id FROM stores WHERE name = ?", (merchant_name,)).fetchone()
    store_id = store["id"]
    
    inserted = 0
    for p in products:
        try:
            name = p.get("name", "").strip()
            if not name:
                continue
            
            # ── Trouver ou créer le produit ──
            existing = db.execute(
                "SELECT id FROM products WHERE name = ? AND store_id = ?",
                (name, store_id),
            ).fetchone()
            
            if not existing:
                package_weight = p.get("package_weight_g") or p.get("weight_g")
                db.execute(
                    """INSERT INTO products (name, store_id, meat_type, category, package_weight_g)
                       VALUES (?, ?, ?, ?, ?)""",
                    (name, store_id, p.get("meat_type"), p.get("category", "Viande"), package_weight),
                )
                db.commit()
                existing = db.execute(
                    "SELECT id FROM products WHERE name = ? AND store_id = ?",
                    (name, store_id),
                ).fetchone()
            
            product_id = existing["id"]
            
            # ── Insérer le prix ──
            price = p.get("price")
            reg_price = p.get("was_price") or p.get("regular_price")
            
            # Nettoyer les prix (accepter None pour price si pas dispo)
            if price is not None:
                db.execute(
                    """INSERT INTO price_history 
                       (product_id, week_start, price, regular_price, merchant_name, image_url)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (product_id, week_start, float(price),
                     float(reg_price) if reg_price else None,
                     merchant_name, p.get("image", "")),
                )
                inserted += 1
        
        except Exception as e:
            print(f"   ⚠️ DB error: {p.get('name','?')}: {e}", file=sys.stderr)
    
    db.commit()
    db.close()
    print(f"   💾 {inserted} prix sauvegardés pour {merchant_name}")
    return inserted

def save_deals_json(products, store_key):
    """Sauvegarde aussi en JSON pour le site (fichier supplementary)."""
    out_dir = os.path.join(os.path.dirname(__file__), "..", "web", "data")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"deals_{store_key}.json")
    import json
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    return out_path
