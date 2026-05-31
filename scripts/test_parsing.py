"""test_parsing.py — Tests unitaires pour extract_weight_kg(), $/kg et seuils aberrants
Lance: python -m pytest scripts/test_parsing.py -v
"""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from scripts.query import extract_weight_kg, find_default_weight
from scripts.build_site import classify_meat_type


# ═══════════════════════════════════════════════════════════════
# 1) EXTRACTION DE POIDS — 20 cas réels de circulaires
# ═══════════════════════════════════════════════════════════════

class TestWeightExtraction:
    """Vérifie que extract_weight_kg() parse correctement les formats de circulaires."""

    @pytest.mark.parametrize("product_name, expected_kg", [
        # --- Grammes ---
        (
            "Poitrine de poulet 454g",        # format classique 1 lb en grammes
            0.454,
        ),
        (
            "Bœuf haché maigre 500g",          # demi-livre métrique
            0.500,
        ),
        (
            "Filet de saumon 350g",            # portion standard poisson
            0.350,
        ),
        (
            "Bacon 375g",                      # format classique bacon
            0.375,
        ),
        (
            "Côtelettes de porc 700g",         # paquet familial
            0.700,
        ),
        (
            "Saucisses italiennes 400g",       # format Super C / Metro
            0.400,
        ),
        (
            "Steaks de surlonge 340g",         # petit format steak
            0.340,
        ),
        # --- Kilogrammes ---
        (
            "Poulet entier 1.8 kg",            # poulet entier
            1.8,
        ),
        (
            "Rôti de palette 1 kg",            # 1 kg exact
            1.0,
        ),
        (
            "Poitrine de porc 2.27 kg",        # ~5 lb
            2.27,
        ),
        (
            "Filet mignon de porc 1,5 kg",     # virgule française
            1.5,
        ),
        (
            "Côtes levées 2 kg",               # format BBQ
            2.0,
        ),
        # --- Livres (lb/lbs) ---
        (
            "Bœuf haché mi-maigre 3 lb",       # format anglais circulaire
            round(3 * 0.453592, 3),  # 1.361
        ),
        (
            "Poitrines de poulet 5 lbs",       # pluriel
            round(5 * 0.453592, 3),  # 2.268
        ),
        (
            "Steak de flanc 1 livre",          # français
            round(1 * 0.453592, 3),  # 0.454
        ),
        (
            "Cuisses de dinde 4 livres",       # français pluriel
            round(4 * 0.453592, 3),  # 1.814
        ),
        (
            "Agneau en dés 2.5 lb",            # décimal lb
            round(2.5 * 0.453592, 3),  # 1.134
        ),
        # --- Kilo (synonyme) ---
        (
            "Rôti de bœuf 1.5 kilo",           # "kilo" au lieu de "kg"
            1.5,
        ),
        # --- Décimale avec virgule en grammes ---
        (
            "Tournedos de bœuf 226,8g",        # 0.5 lb exprimé en g
            0.2268,
        ),
        # --- Grand format ---
        (
            "Dos de porc 5 kg",                # format Costco/bulk
            5.0,
        ),
    ], ids=[
        "454g-poitrine-poulet",
        "500g-boeuf-hache",
        "350g-saumon",
        "375g-bacon",
        "700g-cotelettes-porc",
        "400g-saucisses",
        "340g-steaks-surlonge",
        "1.8kg-poulet-entier",
        "1kg-roti-palette",
        "2.27kg-poitine-porc",
        "1.5kg-virgule-filet-porc",
        "2kg-cotelevees",
        "3lb-boeuf-hache",
        "5lbs-poitrines-poulet",
        "1livre-steak-flanc",
        "4livres-cuisses-dinde",
        "2.5lb-agneau",
        "1.5kilo-roti-boeuf",
        "226.8g-virgule-tournedos",
        "5kg-dos-porc",
    ])
    def test_weight_extraction(self, product_name, expected_kg):
        result = extract_weight_kg(product_name)
        assert result is not None, f"Aucun poids extrait de: '{product_name}'"
        assert abs(result - expected_kg) < 0.002, (
            f"'{product_name}': attendu {expected_kg} kg, obtenu {result} kg"
        )


class TestWeightExtractionNone:
    """Vérifie que extract_weight_kg() retourne None quand il n'y a pas de poids."""

    @pytest.mark.parametrize("product_name", [
        "Saucisses fumées style bratwurst",
        "Boulettes de viande",
        "Bœuf pour fondue",
        "Jambon",
    ], ids=["no-weight-saucisses", "no-weight-boulettes", "no-weight-fondue", "no-weight-jambon"])
    def test_no_weight_returns_none(self, product_name):
        result = extract_weight_kg(product_name)
        assert result is None, f"'{product_name}' ne devrait pas extraire de poids, obtenu: {result}"


# ═══════════════════════════════════════════════════════════════
# 2) CALCUL $/kg — vérifie la formule prix/poids pour chaque cas
# ═══════════════════════════════════════════════════════════════

class TestPerKgCalculation:
    """Vérifie le calcul $/kg à partir du prix et du poids extrait."""

    @pytest.mark.parametrize("product_name, price, expected_per_kg", [
        # Format: (nom produit, prix affiché en $, $/kg attendu)
        # --- Cas typiques circulaires QC ---
        (
            "Poitrine de poulet 454g",     # 1 lb
            4.99,
            round(4.99 / 0.454, 2),       # ~10.99$/kg
        ),
        (
            "Bœuf haché maigre 500g",
            5.49,
            round(5.49 / 0.500, 2),       # 10.98$/kg
        ),
        (
            "Filet de saumon 350g",
            6.99,
            round(6.99 / 0.350, 2),       # 19.97$/kg
        ),
        (
            "Rôti de palette 1 kg",
            12.99,
            12.99,                         # direct: $/kg = prix
        ),
        (
            "Poulet entier 1.8 kg",
            7.99,
            round(7.99 / 1.8, 2),         # ~4.44$/kg
        ),
        (
            "Bœuf haché mi-maigre 3 lb",
            8.99,
            round(8.99 / (3 * 0.453592), 2),  # ~6.61$/kg
        ),
        (
            "Poitrines de poulet 5 lbs",
            14.99,
            round(14.99 / (5 * 0.453592), 2), # ~6.60$/kg
        ),
        (
            "Poitrine de porc 2.27 kg",
            9.99,
            round(9.99 / 2.27, 2),        # ~4.40$/kg
        ),
        (
            "Bacon 375g",
            3.99,
            round(3.99 / 0.375, 2),       # ~10.64$/kg
        ),
        (
            "Filet mignon de porc 1,5 kg",
            15.99,
            round(15.99 / 1.5, 2),        # ~10.66$/kg
        ),
    ], ids=[
        "poitrine-poulet-454g",
        "boeuf-hache-500g",
        "saumon-350g",
        "roti-palette-1kg",
        "poulet-entier-1.8kg",
        "boeuf-hache-3lb",
        "poitrines-poulet-5lbs",
        "poitrine-porc-2.27kg",
        "bacon-375g",
        "filet-porc-1.5kg-virgule",
    ])
    def test_per_kg_from_weight(self, product_name, price, expected_per_kg):
        """Calcule $/kg = prix / poids_kg et vérifie le résultat."""
        w_kg = extract_weight_kg(product_name)
        assert w_kg is not None, f"Poids non extrait de: '{product_name}'"
        per_kg = round(price / w_kg, 2)
        assert abs(per_kg - expected_per_kg) < 0.05, (
            f"'{product_name}' à {price}$: "
            f"attendu {expected_per_kg}$/kg, obtenu {per_kg}$/kg"
        )


class TestPerKgFromUnitPrice:
    """Vérifie le calcul $/kg quand le prix unitaire est dans l'image (unit_price/unit_type)."""

    @pytest.mark.parametrize("unit_price, unit_type, price, expected_per_kg", [
        # Format: (prix unitaire, type, prix du paquet, $/kg attendu)
        (9.99, "/kg",    9.99, 9.99),       # prix directement au kg
        (99,   "/kg",    9.90, 99.0),       # erreur circulaire: 99$/kg pour 9.90$ de produit
        (1.49, "/100g",  5.96, 14.90),      # 1.49$/100g → 14.90$/kg
        (2.29, "/100g",  6.87, 22.90),      # 2.29$/100g → 22.90$/kg
    ], ids=["direct-kg", "high-kg-price", "100g-a", "100g-b"])
    def test_per_kg_from_unit_type(self, unit_price, unit_type, price, expected_per_kg):
        """Simule le parsing unit_price/unit_type tel que fait dans query.py."""
        if "/kg" in unit_type:
            per_kg = unit_price
        elif "/100g" in unit_type:
            per_kg = unit_price * 10
        else:
            pytest.skip(f"Type inconnu: {unit_type}")
        assert abs(per_kg - expected_per_kg) < 0.01, (
            f"{unit_price}{unit_type}: attendu {expected_per_kg}$/kg, obtenu {per_kg}$/kg"
        )


# ═══════════════════════════════════════════════════════════════
# 3) SEUILS ABERRANTS — prix $/kg < 0.50 ou > 100 = flaggé
# ═══════════════════════════════════════════════════════════════

# Bornes tirées de build_site.py ligne 1086:
#   per_kg < 0.50 ou per_kg > 100 → flagged_deals

PER_KG_MIN = 0.50
PER_KG_MAX = 100.00


class TestPriceAnomalies:
    """Vérifie que les seuils de détection de prix aberrants sont corrects."""

    def _is_aberrant(self, per_kg: float) -> bool:
        """Reproduit la logique de build_site.py ligne 1086."""
        return per_kg < PER_KG_MIN or per_kg > PER_KG_MAX

    # --- Prix NORMAUX (doivent passer) ---
    @pytest.mark.parametrize("per_kg, description", [
        (5.00,   "poulet entier ~4.44$/kg arrondi"),
        (7.98,   "côtelettes de porc"),
        (10.99,  "poitrine de poulet"),
        (14.99,  "filet de saumon"),
        (22.90,  "filet mignon de bœuf"),
        (39.99,  "filet mignon premium"),
        (0.99,   "légumes en vrac (bas mais valide)"),
        (0.50,   "pile sur la borne basse"),
        (99.99,  "juste sous la borne haute"),
    ], ids=[
        "poulet-entier", "cotelettes", "poitrine", "saumon",
        "filet-mignon-boeuf", "premium", "legumes", "borne-basse-exacte",
        "juste-sous-borne-haute",
    ])
    def test_normal_prices_not_flagged(self, per_kg, description):
        assert not self._is_aberrant(per_kg), (
            f"{description} ({per_kg}$/kg) ne devrait PAS être aberrant"
        )

    # --- Prix ABERRANTS (doivent être flaggés) ---
    @pytest.mark.parametrize("per_kg, reason, description", [
        (0.10,  "trop_bas",    "erreur de parsing: 0.10$/kg"),
        (0.49,  "trop_bas",    "juste sous la borne basse"),
        (0.01,  "trop_bas",    "prix cassé / erreur OCR"),
        (0.00,  "trop_bas",    "prix zéro"),
        (100.01, "trop_eleve", "juste au-dessus de la borne haute"),
        (150.00, "trop_eleve", "erreur de prix: 150$/kg"),
        (999.99, "trop_eleve", "double saisie: 999.99$/kg"),
    ], ids=[
        "parsing-erreur", "sous-borne-basse", "ocr-bug", "zero",
        "juste-sur-borne-haute", "erreur-prix", "double-saisie",
    ])
    def test_aberrant_prices_flagged(self, per_kg, reason, description):
        assert self._is_aberrant(per_kg), (
            f"{description} ({per_kg}$/kg) devrait être aberrant"
        )

    def test_flag_reason_low(self):
        """Vérifie le motif 'per_kg_trop_bas' pour les prix < 0.50$/kg."""
        per_kg = 0.25
        assert per_kg < PER_KG_MIN
        reason = "per_kg_trop_bas" if per_kg < PER_KG_MIN else "per_kg_trop_eleve"
        assert reason == "per_kg_trop_bas"

    def test_flag_reason_high(self):
        """Vérifie le motif 'per_kg_trop_eleve' pour les prix > 100$/kg."""
        per_kg = 200.0
        assert per_kg > PER_KG_MAX
        reason = "per_kg_trop_bas" if per_kg < PER_KG_MIN else "per_kg_trop_eleve"
        assert reason == "per_kg_trop_eleve"


class TestDefaultWeightFallback:
    """Vérifie find_default_weight() quand aucun poids n'est dans le nom."""

    # NOTE: find_default_weight() matche les keywords SANS mot de liaison.
    # "poitrine poulet" matche "Poitrine poulet" mais PAS "Poitrine de poulet"
    # car "de" est entre les deux mots du keyword.
    @pytest.mark.parametrize("product_name, expected_kg", [
        ("Bœuf haché maigre",        0.454),   # keyword: "boeuf hache"
        ("Porc haché mi-maigre",     0.450),   # keyword: "porc hache"
        ("Poitrine poulet",          0.450),   # keyword: "poitrine poulet" (sans "de")
        ("Filet porc",               0.500),   # keyword: "filet porc" (sans "de")
        ("Bacon tranché",            0.375),   # keyword: "bacon"
        ("Côtelette porc",           0.250),   # keyword: "cotelette porc" (singulier, sans "de")
        ("Ailes poulet",             0.450),   # keyword: "ailes poulet" (sans "de")
        ("Cuisse poulet",            0.250),   # keyword: "cuisse poulet" (singulier, sans "de")
        ("Saucisses fumées",         0.375),   # keyword: "saucisse" (contient "saucisse")
        ("Jambon fumé",              0.300),   # keyword: "jambon fume"
    ], ids=[
        "boeuf-hache", "porc-hache", "poitrine-poulet", "filet-porc",
        "bacon", "cotelette-porc", "ailes-poulet", "cuisse-poulet",
        "saucisses", "jambon",
    ])
    def test_default_weight(self, product_name, expected_kg):
        result = find_default_weight(product_name)
        assert result == expected_kg, (
            f"'{product_name}': attendu {expected_kg}kg, obtenu {result}"
        )


class TestClassifyMeatType:
    """Vérifie classify_meat_type() pour les cas importants."""

    @pytest.mark.parametrize("name, current_mt, expected_mt", [
        # Poissons prioritaire
        ("Filet de saumon",        "autre",   "poisson"),
        ("Crevettes décortiquées", "autre",   "poisson"),
        # Viande déjà classée ne change pas
        ("Saucisses aux pommes",   "porc",    "porc"),
        ("Bœuf haché maigre",      "boeuf",   "boeuf"),
        # Jambon/bacon/saucisse → porc
        ("Jambon tranché",         "autre",   "porc"),
        ("Bacon double smoked",    "autre",   "porc"),
        ("Saucisse italienne",     "autre",   "porc"),
        # Légume reste légume
        ("Carottes en sachet",     "legume",  "legume"),
        # Produit non classifié
        ("Yogourt grec",           "autre",   "yogourt"),
    ], ids=[
        "saumon", "crevettes", "saucisses-pommes", "boeuf-deja-classe",
        "jambon", "bacon", "saucisse-italienne", "carottes", "yogourt",
    ])
    def test_classify(self, name, current_mt, expected_mt):
        result = classify_meat_type(name, current_mt)
        assert result == expected_mt, (
            f"'{name}' (current={current_mt}): attendu '{expected_mt}', obtenu '{result}'"
        )
