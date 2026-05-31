#!/usr/bin/env python3
"""
TikTok Recipe Scraper — Aubaines Rapides
Cherche les vidéos tendance culinaires/recettes sur TikTok.
Utilise l'API TikTokApi (wrapper non-officiel).

Usage:
  python scripts/tiktok_scraper.py                     # top 10 recettes tendance
  python scripts/tiktok_scraper.py --search "poulet"   # recherche personnalisée
  python scripts/tiktok_scraper.py --trending 20       # top 20 tendances culinaires
  python scripts/tiktok_scraper.py --save-json         # export en JSON pour le site
"""

import asyncio
import json
import os
import sys
import argparse
from datetime import datetime

# Ajouter le venv Hermes au path pour TikTokApi
VENV_SITE = os.path.expanduser(
    "~/AppData/Local/hermes/hermes-agent/venv/Lib/site-packages"
)
if os.path.exists(VENV_SITE):
    sys.path.insert(0, VENV_SITE)

# ─── Configuration ────────────────────────────────────────
MS_TOKEN = os.environ.get("TIKTOK_MS_TOKEN", "")  # Optionnel pour la recherche
COOKING_KEYWORDS = [
    "recette", "recipe", "cuisine", "cook", "cooking", "food",
    "meal prep", "dinner", "quick recipe", "easy recipe", "delicious",
    "homemade", "healthy recipe", "chicken recipe", "beef recipe",
    "pasta", "salad", "breakfast", "baking", "dessert", "sauce",
    "soup", "grocery", "meal ideas", "food hack", "kitchen hack",
    "cuisiner", "recette facile", "recette rapide", "plat",
    "gastronomie", "manger", "saine", "protéines", "lowcarb",
    "cuisine québécoise", "recette pas cher", "budget meal",
]
AUBANES_RAPIDES_DATA = os.path.expanduser("~/aubaines-rapides/web/data")


def load_categories():
    """Charge les catégories d'Aubaines Rapides pour faire correspondre les vidéos aux deals."""
    try:
        with open(os.path.join(AUBANES_RAPIDES_DATA, "deals.json")) as f:
            data = json.load(f)
        categories = set()
        for deal_list in data["deals"].values():
            for d in deal_list:
                categories.add(d.get("category", ""))
        return sorted(categories)
    except:
        return ["poulet", "boeuf", "porc", "legume", "fruit", "poisson", "pain", "fromage"]


def match_category(desc, categories):
    """Trouve la catégorie Aubaines Rapides qui correspond à une description TikTok."""
    cat_map = {
        "poulet": ["chicken", "poulet", "volaille", "wing", "breast"],
        "boeuf": ["beef", "boeuf", "steak", "burger", "ground beef", "bœuf"],
        "porc": ["pork", "porc", "bacon", "ham", "jambon", "côtelette"],
        "legume": ["vegetable", "legume", "légume", "veggie", "salad", "broccoli",
                    "carrot", "onion", "tomato", "spinach", "kale"],
        "fruit": ["fruit", "apple", "banana", "berry", "orange", "mango"],
        "poisson": ["fish", "poisson", "saumon", "salmon", "tuna", "thon", "tilapia"],
        "fromage": ["cheese", "fromage", "cheddar", "mozza"],
        "pain": ["bread", "pain", "toast", "baguette", "croissant"],
        "dessert": ["dessert", "cake", "cookie", "brownie", "gâteau", "tarte"],
        "soupe": ["soup", "soupe", "stew", "ragoût", "chili"],
        "pasta": ["pasta", "pâtes", "spaghetti", "noodle", "nouille"],
    }
    desc_lower = desc.lower()
    for cat, keywords in cat_map.items():
        if any(kw in desc_lower for kw in keywords):
            return cat
    return None


class TikTokRecipeScraper:
    def __init__(self, ms_token=None):
        self.ms_token = ms_token or MS_TOKEN
        self.api = None

    async def __aenter__(self):
        from TikTokApi import TikTokApi
        self.api = TikTokApi()
        ms_tokens = [self.ms_token] if self.ms_token else []
        await self.api.create_sessions(
            ms_tokens=ms_tokens,
            num_sessions=1,
            sleep_after=1,
        )
        return self

    async def __aexit__(self, *args):
        if self.api:
            await self.api.close_sessions()

    async def search_videos(self, query, count=10):
        """Recherche des vidéos par mot-clé (nécessite ms_token)."""
        if not self.ms_token:
            raise ValueError("ms_token requis pour la recherche de vidéos. "
                             "Définis TIKTOK_MS_TOKEN dans .env")
        
        videos = []
        async for video in self.api.search.search_type(query, "video", count=count):
            videos.append(video)
        return videos

    async def get_trending_recipes(self, count=30, max_results=10):
        """Récupère les vidéos tendance et filtre les contenus culinaires."""
        videos = []
        async for video in self.api.trending.videos(count=count):
            videos.append(video)

        # Filtrer les vidéos culinaires
        recipes = []
        for v in videos:
            desc = (v.as_dict.get("desc", "") or "").lower()
            if any(kw in desc for kw in COOKING_KEYWORDS):
                recipes.append(v)

        return recipes[:max_results]

    async def search_by_category(self, category, count=5):
        """Cherche des recettes pour une catégorie spécifique (ex: 'poulet')."""
        if self.ms_token:
            queries = [
                f"recette {category} facile",
                f"recipe {category}",
                f"cuisiner {category}",
                f"{category} meal",
            ]
            for q in queries:
                try:
                    async for v in self.api.search.search_type(q, "video", count=count):
                        return v
                except:
                    continue
        
        # Fallback: trending + filter
        return await self.get_trending_recipes(count=50, max_results=count)

    def video_to_dict(self, video):
        """Convertit une vidéo TikTok en dict simplifié."""
        d = video.as_dict
        author = d.get("author", {}) or {}
        stats = d.get("stats", {}) or {}
        music = d.get("music", {}) or {}
        
        desc = d.get("desc", "") or ""
        cover = ""
        if d.get("video"):
            cover = d.get("video", {}).get("cover", "") or ""

        return {
            "id": d.get("id", ""),
            "desc": desc[:200],
            "author": author.get("nickname", ""),
            "author_handle": author.get("uniqueId", ""),
            "likes": stats.get("diggCount", 0),
            "plays": stats.get("playCount", 0),
            "comments": stats.get("commentCount", 0),
            "shares": stats.get("shareCount", 0),
            "cover_url": cover,
            "video_url": f"https://www.tiktok.com/@{author.get('uniqueId','')}/video/{d.get('id','')}",
            "music": (music.get("title", "") or "")[:100],
            "category": match_category(desc, []),
            "fetched_at": datetime.now().isoformat(),
        }


async def main():
    parser = argparse.ArgumentParser(description="TikTok Recipe Scraper")
    parser.add_argument("--search", "-s", type=str, help="Rechercher des vidéos")
    parser.add_argument("--trending", "-t", type=int, default=10,
                        help="Nombre de vidéos tendance culinaires (défaut: 10)")
    parser.add_argument("--save-json", action="store_true",
                        help="Sauvegarder en JSON dans le dossier Aubaines Rapides")
    parser.add_argument("--category", "-c", type=str,
                        help="Catégorie spécifique (poulet, boeuf, etc.)")
    args = parser.parse_args()

    async with TikTokRecipeScraper() as scraper:
        if args.search:
            print(f"🔍 Recherche TikTok: '{args.search}'...")
            try:
                videos = await scraper.search_videos(args.search, count=10)
            except ValueError as e:
                print(f"❌ {e}")
                videos = await scraper.get_trending_recipes(count=50, max_results=10)
                print("(fallback: vidéos tendance filtrées)")
        elif args.category:
            print(f"🍽️ Recherche recettes: '{args.category}'...")
            videos = await scraper.search_by_category(args.category, count=5)
        else:
            print(f"📊 Top {args.trending} vidéos tendance culinaires...")
            videos = await scraper.get_trending_recipes(
                count=args.trending * 3, max_results=args.trending
            )

        if not videos:
            print("Aucune vidéo trouvée.")
            return

        results = [scraper.video_to_dict(v) for v in videos]

        # Affichage
        print(f"\n{'='*60}")
        print(f"🍽️  {len(results)} vidéos culinaires trouvées")
        print(f"{'='*60}\n")

        for i, r in enumerate(results, 1):
            cat_tag = f" [{r['category']}]" if r['category'] else ""
            print(f"{i}. {r['desc'][:70]}{cat_tag}")
            print(f"   👤 {r['author']}  ❤️ {r['likes']:,}  👁️ {r['plays']:,}")
            print(f"   🔗 {r['video_url']}")
            print()

        # Sauvegarde JSON
        if args.save_json:
            output_dir = AUBANES_RAPIDES_DATA
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, "tiktok_recipes.json")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump({
                    "fetched_at": datetime.now().isoformat(),
                    "search": args.search or f"trending-{args.trending}",
                    "videos": results,
                }, f, ensure_ascii=False, indent=2)
            print(f"💾 Sauvegardé: {output_path}")

        return results


if __name__ == "__main__":
    asyncio.run(main())
