"""
Base de données — Schema & Initialisation
"""
import sqlite3
import os
from datetime import date, datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "aubaines.db")

SCHEMA_SQL = """
-- Magasins d'épicerie
CREATE TABLE IF NOT EXISTS stores (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    slug        TEXT    NOT NULL UNIQUE,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Produits individuels des circulaires
CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    store_id    INTEGER NOT NULL REFERENCES stores(id),
    meat_type   TEXT,       -- 'boeuf', 'poulet', 'porc'
    category    TEXT,       -- sous-catégorie (steak, haché, poitrine, etc.)
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(name, store_id)
);

-- Historique des prix (52 semaines)
CREATE TABLE IF NOT EXISTS price_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      INTEGER NOT NULL REFERENCES products(id),
    price           REAL,
    regular_price   REAL,
    unit_price      REAL,
    unit_type       TEXT,       -- '/kg', '/100g', '/lb', 'ea', etc.
    sale_text       TEXT,       -- '2/6,00$', '50% de rabais', etc.
    valid_from      TEXT,       -- date début aubaine
    valid_to        TEXT,       -- date fin aubaine
    week_start      TEXT    NOT NULL,  -- lundi de la semaine
    flyer_id        INTEGER,   -- identifiant Flipp
    merchant_name   TEXT,
    scanned_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Index pour requêtes rapides
CREATE INDEX IF NOT EXISTS idx_price_history_product 
    ON price_history(product_id, week_start);
CREATE INDEX IF NOT EXISTS idx_price_history_week 
    ON price_history(week_start);
CREATE INDEX IF NOT EXISTS idx_products_meat 
    ON products(meat_type);
CREATE INDEX IF NOT EXISTS idx_products_store 
    ON products(store_id);
"""


def get_db():
    """Ouvre et retourne une connexion à la base de données."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Crée les tables si elles n'existent pas."""
    conn = get_db()
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    print(f"✅ Base initialisée : {DB_PATH}")


def seed_stores():
    """Ajoute les épiceries du Québec."""
    stores = [
        ("Super C", "super-c"),
        ("Metro", "metro"),
        ("IGA", "iga"),
        ("Maxi", "maxi"),
        ("Provigo", "provigo"),
        ("Walmart", "walmart"),
        ("Costco", "costco"),
        ("Adonis", "adonis"),
        ("Marché Tau", "marche-tau"),
        ("Kim Phat", "kim-phat"),
    ]
    conn = get_db()
    for name, slug in stores:
        conn.execute(
            "INSERT OR IGNORE INTO stores (name, slug) VALUES (?, ?)",
            (name, slug),
        )
    conn.commit()
    conn.close()
    print(f"✅ {len(stores)} magasins ajoutés")


def get_week_start(dt=None):
    """Retourne le lundi de la semaine donnée."""
    if dt is None:
        dt = date.today()
    return dt.strftime("%Y-%m-%d")


if __name__ == "__main__":
    init_db()
    seed_stores()
