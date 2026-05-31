"""
Tests de parsing des prix pour Aubaines Rapides.

Valide:
  1. extract_weight_kg() — extraction du poids depuis un nom de produit
  2. Calcul $/kg — depuis poids dans le nom, unit_price, package_weight_g
  3. Détection des prix aberrants (< 0.50$/kg ou > 100$/kg)

Les fonctions sont re-définies ici (mêmes algo que scripts/query.py et
scripts/build_site.py) pour éviter les imports qui dépendent de la DB.
"""
import re
import unicodedata
import pytest


# ── Fonctions copiées de scripts/query.py (identiques) ──────────────────────

def strip_accents(s):
    s = s.replace("œ", "oe").replace("Œ", "OE").replace("æ", "ae").replace("Æ", "AE")
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def extract_weight_kg(name):
    """Extrait le poids en kg depuis le nom du produit."""
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


DEFAULT_WEIGHTS = {
    "boeuf hache": 0.454, "porc hache": 0.450, "poulet hache": 0.454,
    "veau hache": 0.454, "dinde hache": 0.454, "bacon": 0.375,
    "jambon fume": 0.300, "jambon": 0.200, "cotelette porc": 0.250,
    "filet porc": 0.500, "saucisse fume": 0.375, "saucisse": 0.375,
    "filet poulet": 0.450, "poitrine poulet": 0.450,
    "ailes poulet": 0.450, "cuisse poulet": 0.250,
}


def find_default_weight(name):
    n = strip_accents(name.lower())
    for kw, w in DEFAULT_WEIGHTS.items():
        if kw in n:
            return w
    return None


def compute_per_kg(price, package_weight_g=None, unit_price=None, unit_type=None, name=None):
    """Reproduit la logique de enrich() de query.py / build_site.py.

    Priorité: package_weight_g > unit_price > extract_weight_kg > find_default_weight
    Retourne (per_kg, source) ou (None, None) si rien trouvé.
    """
    per_kg = None
    source = None

    # 1) Poids fixe DB
    if package_weight_g and price:
        w_kg = package_weight_g / 1000
        per_kg = round(price / w_kg, 2)
        source = "reel"

    # 2) Prix unitaire de l'image
    if per_kg is None and unit_price:
        ut = unit_type or ""
        if "/kg" in ut:
            per_kg = round(unit_price, 2)
            source = "image"
        elif "/100g" in ut:
            per_kg = round(unit_price * 10, 2)
            source = "image"

    # 3) Poids dans le nom
    if per_kg is None and name:
        w = extract_weight_kg(name)
        if w and price:
            per_kg = round(price / w, 2)
            source = "nom"

    # 4) Estimation par défaut
    if per_kg is None and name:
        w = find_default_weight(name)
        if w and price:
            per_kg = round(price / w, 2)
            source = "estime"

    return per_kg, source


def is_aberrant(per_kg):
    """Un prix est aberrant si < 0.50$/kg ou > 100$/kg (logique build_site.py)."""
    return per_kg is not None and (per_kg < 0.50 or per_kg > 100)


# ── 1. Tests extract_weight_kg() ────────────────────────────────────────────

class TestExtractWeightKg:
    """Extraction du poids en kg depuis le nom du produit."""

    # --- grammes ---
    def test_500g(self):
        assert extract_weight_kg("Poulet 500g") == 0.500

    def test_100g(self):
        assert extract_weight_kg("Fromage 100g") == 0.100

    def test_250g(self):
        assert extract_weight_kg("Bacon 250g") == 0.250

    def test_375g(self):
        assert extract_weight_kg("Saucisse 375g") == 0.375

    def test_750g(self):
        assert extract_weight_kg("Boeuf haché 750g") == 0.750

    # --- kg ---
    def test_1kg(self):
        assert extract_weight_kg("Poulet entier 1kg") == 1.0

    def test_2_27kg(self):
        assert extract_weight_kg("Poulet 2.27kg") == 2.27

    def test_2_27kg_virgule(self):
        assert extract_weight_kg("Poulet 2,27kg") == 2.27

    def test_5kg(self):
        assert extract_weight_kg("Sac de patates 5kg") == 5.0

    # --- livres ---
    def test_1lb(self):
        assert extract_weight_kg("Boeuf 1lb") == pytest.approx(0.454, abs=0.001)

    def test_2lbs(self):
        assert extract_weight_kg("Poulet 2lbs") == pytest.approx(0.907, abs=0.001)

    def test_1livre(self):
        assert extract_weight_kg("Porc 1livre") == pytest.approx(0.454, abs=0.001)

    def test_2livres(self):
        assert extract_weight_kg("Boeuf 2livres") == pytest.approx(0.907, abs=0.001)

    # --- cas sans poids ---
    def test_aucun_poids(self):
        assert extract_weight_kg("Steak de boeuf") is None

    def test_aucun_poids_prix_seul(self):
        assert extract_weight_kg("Poulet 5,99$") is None

    # --- cas limites ---
    def test_espaces_entre_nombre_et_unite(self):
        assert extract_weight_kg("Boeuf 500 g") == 0.500

    def test_kilo_raccourci(self):
        assert extract_weight_kg("Pommes 2 kilo") == 2.0


# ── 2. Tests find_default_weight() ──────────────────────────────────────────

class TestFindDefaultWeight:
    """Poids par défaut quand aucun poids n'est dans le nom."""

    def test_boeuf_hache(self):
        assert find_default_weight("Boeuf haché mi-maigre") == 0.454

    def test_bacon(self):
        assert find_default_weight("Bacon nature") == 0.375

    def test_poitrine_poulet(self):
        assert find_default_weight("Poitrine de poulet") == 0.450

    def test_cuisse_poulet(self):
        assert find_default_weight("Cuisse de poulet") == 0.250

    def test_inconnu(self):
        assert find_default_weight("Salade César") is None


# ── 3. Tests calcul $/kg ────────────────────────────────────────────────────

class TestPerKgCalculation:
    """Calcul du prix au kilo via les 4 méthodes (priorité)."""

    # --- Cas réels de circulaires québécoises ---

    def test_prix_simple_500g(self):
        """4,99$ avec poids 500g → 9.98$/kg"""
        per_kg, src = compute_per_kg(4.99, package_weight_g=500)
        assert per_kg == pytest.approx(9.98, abs=0.05)
        assert src == "reel"

    def test_prix_simple_2_27kg(self):
        """12,99$ avec poids 2.27kg → 5.72$/kg"""
        per_kg, src = compute_per_kg(12.99, package_weight_g=2270)
        assert per_kg == pytest.approx(5.72, abs=0.05)
        assert src == "reel"

    def test_unit_price_par_kg(self):
        """3,99$/kg → 3.99$/kg direct"""
        per_kg, src = compute_per_kg(3.99, unit_price=3.99, unit_type="/kg")
        assert per_kg == pytest.approx(3.99, abs=0.01)
        assert src == "image"

    def test_unit_price_par_100g(self):
        """1,99$/100g → 19.90$/kg"""
        per_kg, src = compute_per_kg(1.99, unit_price=1.99, unit_type="/100g")
        assert per_kg == pytest.approx(19.90, abs=0.10)
        assert src == "image"

    def test_poids_dans_nom_lb(self):
        """3,99$/lb → 8.80$/kg (conversion via extract_weight_kg)"""
        per_kg, src = compute_per_kg(3.99, name="Boeuf 1lb")
        assert per_kg == pytest.approx(3.99 / 0.454, abs=0.10)
        assert src == "nom"

    def test_poids_dans_nom_500g(self):
        """4,99$ avec 500g dans le nom → 9.98$/kg"""
        per_kg, src = compute_per_kg(4.99, name="Poulet 500g")
        assert per_kg == pytest.approx(9.98, abs=0.05)
        assert src == "nom"

    def test_estimation_boeuf_hache(self):
        """5,99$ boeuf haché (estimé 0.454kg) → 13.19$/kg"""
        per_kg, src = compute_per_kg(5.99, name="Boeuf haché mi-maigre")
        assert per_kg == pytest.approx(13.19, abs=0.10)
        assert src == "estime"

    def test_estimation_bacon(self):
        """4,49$ bacon (estimé 0.375kg) → 11.97$/kg"""
        per_kg, src = compute_per_kg(4.49, name="Bacon double fumé")
        assert per_kg == pytest.approx(11.97, abs=0.10)
        assert src == "estime"

    def test_estimation_cuisse_poulet(self):
        """3,49$ cuisse de poulet (estimé 0.250kg) → 13.96$/kg"""
        per_kg, src = compute_per_kg(3.49, name="Cuisse de poulet")
        assert per_kg == pytest.approx(13.96, abs=0.10)
        assert src == "estime"

    # --- Priorité: package_weight_g > unit_price > nom > estimation ---

    def test_priorite_package_weight_sur_unit_price(self):
        """Si les deux existent, package_weight_g gagne."""
        per_kg, src = compute_per_kg(
            10.0, package_weight_g=1000, unit_price=8.0, unit_type="/kg"
        )
        assert src == "reel"
        assert per_kg == 10.0

    def test_priorite_unit_price_sur_nom(self):
        """Si unit_price existe, il bat le poids dans le nom."""
        per_kg, src = compute_per_kg(
            10.0, unit_price=15.0, unit_type="/kg", name="Boeuf 1kg"
        )
        assert src == "image"
        assert per_kg == 15.0

    def test_priorite_nom_sur_estimation(self):
        """Poids dans le nom bat l'estimation par défaut."""
        per_kg, src = compute_per_kg(10.0, name="Boeuf haché 1kg")
        assert src == "nom"
        assert per_kg == 10.0

    # --- Multi-prix (format "2/5$", "achetez-en 2") ---

    def test_multi_buy_2pour5(self):
        """Format '2/5$' → 2.50$/unité, puis calcul $/kg."""
        # Simule le parsing: 5$ pour 2 unités → 2.50$ l'unité
        prix_unitaire = 5.0 / 2  # 2.50$
        per_kg, src = compute_per_kg(prix_unitaire, package_weight_g=454)
        assert per_kg == pytest.approx(2.50 / 0.454, abs=0.10)
        assert src == "reel"

    def test_achetez_en_2_payez(self):
        """Format 'achetez-en 2, payez 5,00$' → 2.50$/unité."""
        prix_unitaire = 5.0 / 2  # 2.50$
        per_kg, src = compute_per_kg(prix_unitaire, name="Boeuf haché")
        assert per_kg == pytest.approx(2.50 / 0.454, abs=0.10)
        assert src == "estime"

    # --- Aucun poids trouvable ---

    def test_aucun_poids(self):
        """Produit sans poids → None."""
        per_kg, src = compute_per_kg(5.99, name=" mystère")
        assert per_kg is None
        assert src is None

    def test_sans_prix(self):
        """Pas de prix → None."""
        per_kg, src = compute_per_kg(None, name="Boeuf 1kg")
        assert per_kg is None


# ── 4. Tests détection prix aberrants ────────────────────────────────────────

class TestAberrantDetection:
    """Détection des prix $/kg aberrants (< 0.50 ou > 100)."""

    def test_normal_est_ok(self):
        assert not is_aberrant(12.50)

    def test_trop_bas(self):
        assert is_aberrant(0.10)

    def test_trop_haut(self):
        assert is_aberrant(150.0)

    def test_limite_basse(self):
        """0.50$/kg est la limite → considéré aberrant (strictement < 0.50)."""
        assert not is_aberrant(0.50)  # 0.50 n'est PAS < 0.50
        assert is_aberrant(0.49)

    def test_limite_haute(self):
        """100$/kg est la limite → considéré aberrant (strictement > 100)."""
        assert not is_aberrant(100.0)  # 100.0 n'est PAS > 100
        assert is_aberrant(100.01)

    def test_none_est_ok(self):
        """None = pas calculé, pas aberrant."""
        assert not is_aberrant(None)

    # --- Cas réels qui devraient passer ou être flaggés ---

    def test_poulet_500g_a_4_99_ok(self):
        """Poulet 4.99$/500g = 9.98$/kg → normal."""
        per_kg, _ = compute_per_kg(4.99, package_weight_g=500)
        assert not is_aberrant(per_kg)

    def test_boeuf_2_27kg_a_12_99_ok(self):
        """Boeuf 12.99$/2.27kg = 5.72$/kg → normal."""
        per_kg, _ = compute_per_kg(12.99, package_weight_g=2270)
        assert not is_aberrant(per_kg)

    def test_prix_excessif_flagge(self):
        """Fromage 8.99$/50g = 179.80$/kg → aberrant."""
        per_kg, _ = compute_per_kg(8.99, package_weight_g=50)
        assert is_aberrant(per_kg)

    def test_prix_ridicule_flagge(self):
        """Produit 0.99$/5kg = 0.20$/kg → aberrant."""
        per_kg, _ = compute_per_kg(0.99, package_weight_g=5000)
        assert is_aberrant(per_kg)

    def test_eau_10l_a_2_99_ok(self):
        """Eau 2.99$/10L = 0.30$/kg → aberrant (normal pour de l'eau)."""
        per_kg, _ = compute_per_kg(2.99, package_weight_g=10000)
        # 0.299 < 0.50 → flaggé comme aberrant
        assert is_aberrant(per_kg)
