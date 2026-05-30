"""Trouve les épiceries près d'un code postal via OpenStreetMap."""
import subprocess, json, os, sys, re
from typing import List, Optional

MAPS_CLIENT = os.path.expanduser(
    "~/AppData/Local/hermes/skills/productivity/maps/scripts/maps_client.py"
)

# Mapping: nom OSM → merchant_name dans price_history
STORE_ALIASES = {
    "iga": "IGA",
    "iga extra": "IGA",
    "maxi": "Maxi",
    "metro": "Metro",
    "metro plus": "Metro",
    "super c": "Super C",
    "provigo": "Provigo",
    "walmart": "Walmart",
    "costco": "Costco",
    "marché tradition": "Les Marchés Tradition",
    "marche tradition": "Les Marchés Tradition",
    "tigre géant": "Tigre Géant",
    "tigre geant": "Tigre Géant",
    "adonis": "Adonis",
    "kim phat": "Kim Phat",
    "marche tau": "Marché Tau",
}

# Québec FSA → ville principale (pour fallback si le code postal complet n'est pas dans Nominatim)
FSA_CITY = {
    "J7Z": "Saint-Jérôme",
    "J7Y": "Saint-Jérôme",
    "J7V": "Saint-Jérôme",
    "J7T": "Saint-Jérôme",
    "J8R": "Saint-Jérôme",
    "J8S": "Saint-Jérôme",
    "J8T": "Saint-Jérôme",
    "J0R": "Saint-Jérôme",
    # Montréal — Plateau/Mile-End/Centre
    "H2X": "Montréal",
    "H2W": "Montréal",
    "H2T": "Montréal",
    "H2J": "Montréal",
    "H2L": "Montréal",
    "H2G": "Montréal",
    "H3A": "Montréal",
    "H3B": "Montréal",
    "H3G": "Montréal",
    "H3H": "Montréal",
    "H3K": "Montréal",
    "H3L": "Montréal",
    "H4B": "Montréal",
    "H4C": "Montréal",
    # Laval
    "H7A": "Laval",
    "H7B": "Laval",
    "H7C": "Laval",
    "H7E": "Laval",
    "H7G": "Laval",
    "H7H": "Laval",
    "H7J": "Laval",
    "H7K": "Laval",
    "H7L": "Laval",
    "H7M": "Laval",
    "H7N": "Laval",
    "H7P": "Laval",
    "H7R": "Laval",
    "H7S": "Laval",
    "H7T": "Laval",
    "H7V": "Laval",
    "H7W": "Laval",
    "H7X": "Laval",
    # Québec
    "G1A": "Québec",
    "G1B": "Québec",
    "G1C": "Québec",
    "G1E": "Québec",
    "G1G": "Québec",
    "G1H": "Québec",
    "G1J": "Québec",
    "G1K": "Québec",
    "G1L": "Québec",
    "G1M": "Québec",
    "G1N": "Québec",
    "G1P": "Québec",
    "G1Q": "Québec",
    "G1R": "Québec",
    "G1S": "Québec",
    "G1T": "Québec",
    "G1V": "Québec",
    "G1W": "Québec",
    "G1X": "Québec",
    "G1Y": "Québec",
    "G2B": "Québec",
    "G2C": "Québec",
    "G2E": "Québec",
    "G2G": "Québec",
    "G1V": "Québec",
    "G1W": "Québec",
    "G3A": "Québec",
    "G3E": "Québec",
    "G3G": "Québec",
    "G3J": "Québec",
    # Longueuil / Rive-Sud
    "J4G": "Longueuil",
    "J4H": "Longueuil",
    "J4J": "Longueuil",
    "J4K": "Longueuil",
    "J4L": "Longueuil",
    "J4M": "Longueuil",
    "J4N": "Longueuil",
    "J4P": "Longueuil",
    "J4R": "Longueuil",
    "J4S": "Longueuil",
    "J4T": "Longueuil",
    "J4V": "Longueuil",
    "J4W": "Longueuil",
    "J4X": "Longueuil",
    "J4Y": "Longueuil",
    "J4Z": "Longueuil",
    # Gatineau
    "J8X": "Gatineau",
    "J8Y": "Gatineau",
    "J8Z": "Gatineau",
    "J9A": "Gatineau",
    "J9B": "Gatineau",
    "J9C": "Gatineau",
    "J9H": "Gatineau",
    "J9J": "Gatineau",
    "J9L": "Gatineau",
    "J9P": "Gatineau",
}


def _call_maps(args: list) -> dict:
    """Exécute maps_client.py avec des arguments et retourne le JSON."""
    if not os.path.exists(MAPS_CLIENT):
        return {"error": f"maps_client.py introuvable: {MAPS_CLIENT}", "status": "error"}
    try:
        proc = subprocess.run(
            [sys.executable, MAPS_CLIENT] + args,
            capture_output=True, text=True, timeout=15
        )
        return json.loads(proc.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
        return {"error": str(e), "status": "error"}


def _normalize_postal(code: str) -> str:
    """Nettoie et formate un code postal canadien."""
    c = code.strip().upper()
    # Si 6 caractères sans espace, insérer l'espace au milieu
    if re.match(r'^[A-Z]\d[A-Z]\d[A-Z]\d$', c):
        c = c[:3] + " " + c[3:]
    return c


def geocode_postal(postal_code: str) -> tuple:
    """
    Convertit un code postal en (lat, lon, display_name).
    Retourne (None, None, None) si échec.
    Essaie le code postal complet, puis FSA + ville si disponible.
    """
    pc = _normalize_postal(postal_code)

    # 1) Essayer avec la province
    data = _call_maps(["search", f"{pc}, Quebec, Canada"])
    if data.get("status") == "error" or not data.get("results"):
        data = _call_maps(["search", f"{pc}, Canada"])

    # 2) Essayer le code postal seul
    if data.get("status") == "error" or not data.get("results"):
        data = _call_maps(["search", f"{pc}"])

    # Valider que le résultat est bien au Canada
    if data.get("results"):
        r = data["results"][0]
        display = (r.get("display_name") or "").lower()
        if "united states" in display or "unitedstates" in display:
            data = {"status": "error", "error": "not in canada"}
        elif "canada" not in display and "québec" not in display and "quebec" not in display:
            data = {"status": "error", "error": "not in canada"}  # faux positif, on continue

    # 3) Fallback: FSA (3 premiers chars) + ville au Québec
    if data.get("status") == "error" or not data.get("results"):
        fsa = pc[:3]
        if fsa in FSA_CITY:
            city = FSA_CITY[fsa]
            data = _call_maps(["search", f"{fsa}, {city}, Quebec, Canada"])

    # 4) Fallback final: FSA + "Quebec Canada"
    if data.get("status") == "error" or not data.get("results"):
        fsa = pc[:3]
        data = _call_maps(["search", f"{fsa}, Quebec, Canada"])

    # 5) Dernier recours: chercher la ville dans OSM par FSA
    if data.get("status") == "error" or not data.get("results"):
        fsa = pc[:3]
        # Si FSA commence par G (Québec), J (Montréal/Laurentides), H (Montréal)
        # on essaye de trouver une ville correspondante
        if fsa.startswith("G"):
            data = _call_maps(["search", "Quebec City, Quebec, Canada"])
        elif fsa.startswith(("H", "J")):
            data = _call_maps(["search", "Montreal, Quebec, Canada"])

    if data.get("status") == "error" or not data.get("results"):
        return None, None, None

    r = data["results"][0]
    return r["lat"], r["lon"], r.get("display_name", "")


def find_nearby_store_names(postal_code: str, radius_km: int = 8) -> List[str]:
    """
    Retourne la liste des merchant_names (tels que dans price_history)
    des épiceries situées dans un rayon de radius_km autour du code postal.
    """
    lat, lon, _ = geocode_postal(postal_code)
    if lat is None:
        return []  # pas de géocodage

    data = _call_maps(["nearby", str(lat), str(lon), "supermarket",
                        "--radius", str(radius_km * 1000), "--limit", "80"])
    if data.get("status") == "error" or "results" not in data:
        return []

    stores = set()
    for r in data["results"]:
        name = (r.get("name") or "").strip().lower()
        tags = r.get("tags", {})
        brand = (tags.get("brand") or "").strip().lower()

        # Priorité à la marque (plus fiable que le nom)
        candidates = [brand, name]
        for c in candidates:
            if c in STORE_ALIASES:
                stores.add(STORE_ALIASES[c])
                break
        else:
            # Vérification fuzzy pour les noms composés
            for pattern, mapped_name in STORE_ALIASES.items():
                if pattern in name or pattern in brand:
                    stores.add(mapped_name)
                    break

    return sorted(stores)


if __name__ == "__main__":
    pc = sys.argv[1] if len(sys.argv) > 1 else "J7Z 1J6"
    print(f"🔎 Magasins près de {pc} :")
    stores = find_nearby_store_names(pc)
    for s in stores:
        print(f"   ✅ {s}")
    if not stores:
        print("   (aucun trouvé)")
