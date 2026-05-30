#!/usr/bin/env python3
"""
Bot Discord Aubaines Rapides — autonome
Écoute #aubaines-rapides et répond aux commandes !deal et !produit
"""
import sys
import os
import re
import subprocess
import asyncio
from pathlib import Path

import discord
from discord.ext import commands

# ─── Configuration ───────────────────────────────────────────────────────────
PROJECT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_DIR / "scripts"

# Token du bot — à créer sur https://discord.com/developers/applications
# Variables d'environnement: ASUNAINS_RAPIDES_BOT_TOKEN
# Sinon: créer un fichier .env ou entrer le token ici
BOT_TOKEN = os.environ.get("AUBAINES_RAPIDES_BOT_TOKEN", "")

# ID du canal #aubaines-rapides
CHANNEL_ID = 1510059483466829996

intents = discord.Intents.default()
intents.message_content = True
intents.guild_messages = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


def run_script(script_name: str, args: list[str] = None) -> str:
    """Execute un script Python du projet et retourne sa sortie."""
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        return f"❌ Script introuvable: {script_name}"

    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(PROJECT_DIR),
            timeout=60,
        )
        output = result.stdout or result.stderr
        return output.strip() or f"❌ Aucune sortie (code {result.returncode})"
    except subprocess.TimeoutExpired:
        return "⏰ Le script a pris trop de temps (>60s)."
    except Exception as e:
        return f"❌ Erreur: {e}"


@bot.event
async def on_ready():
    print(f"✅ Bot connecté: {bot.user} (ID: {bot.user.id})")
    print(f"📡 Surveille le canal #{CHANNEL_ID}")


@bot.event
async def on_message(message):
    """Intercepte les messages dans le canal cible."""
    if message.author.bot:
        return

    # Ignorer les messages hors du canal #aubaines-rapides
    if message.channel.id != CHANNEL_ID and message.channel.type != discord.ChannelType.private:
        return

    # Laisser les commandes normales passer (pour le préfixe !)
    await bot.process_commands(message)


@bot.command(name="deal")
async def cmd_deal(ctx, postal: str = None):
    """🏆 Top 3 deals de la semaine"""
    async with ctx.typing():
        args = [postal] if postal else []
        output = run_script("deal.py", args)
        # Limiter la longueur Discord (2000 chars max)
        if len(output) > 1900:
            output = output[:1900] + "\n\n✂️ (tronqué — utilise !deal sur le site)"
        await ctx.send(output)


@bot.command(name="produit")
async def cmd_produit(ctx, *, query: str = None):
    """🔍 Chercher un produit (ex: !produit poitrine)"""
    if not query:
        await ctx.send("❌ Essaie: `!produit poitrine`, `!produit haché`, `!produit steak`")
        return
    async with ctx.typing():
        args = query.strip().split()
        output = run_script("query.py", args)
        if len(output) > 1900:
            output = output[:1900] + "\n\n✂️ (tronqué — utilise la recherche sur le site)"
        await ctx.send(output)


@bot.command(name="aide")
async def cmd_aide(ctx):
    """📖 Aide du bot"""
    embed = discord.Embed(
        title="🥩 Aubaines Rapides — Commandes",
        description="Scraper de circulaires des épiceries du Québec. Focus viande (bœuf, poulet, porc).",
        color=0xe94560,
    )
    embed.add_field(
        name="!deal [codepostal]",
        value="Top 3 deals de la semaine. Code postal optionnel pour filtrer par épiceries près de chez toi.",
        inline=False,
    )
    embed.add_field(
        name="!produit [nom]",
        value="Chercher un produit spécifique: `!produit poitrine`, `!produit haché`, `!produit steak`.",
        inline=False,
    )
    embed.add_field(
        name="📊 Site web",
        value="https://alanixqc.github.io/aubaines-rapides/",
        inline=False,
    )
    embed.set_footer(text="Mis à jour chaque mardi · Données Flipp API")
    await ctx.send(embed=embed)


@bot.command(name="stats")
async def cmd_stats(ctx):
    """📊 Stats du projet"""
    async with ctx.typing():
        status_path = PROJECT_DIR / "data" / "pipeline_status.json"
        if status_path.exists():
            import json
            with open(status_path) as f:
                status = json.load(f)
            s = status.get("stats", {})
            scrape = s.get("scrape", {})
            lines = [
                "📊 **Aubaines Rapides — Statistiques**",
                f"   Produits: {s.get('total_products', '?')}",
                f"   Prix historiques: {s.get('total_prices', '?')}",
                f"   Items viande/semaine: {scrape.get('meat_items', '?')}",
                f"   Dernier scrape: {status.get('last_run', '?')[:16]}",
                f"   Statut: {'✅ OK' if status.get('success') else '❌ Échec'}",
                f"   Site: https://alanixqc.github.io/aubaines-rapides/",
            ]
            await ctx.send("\n".join(lines))
        else:
            await ctx.send("📊 Pipeline pas encore exécuté. Premier run: mardi 8h30.")


def main():
    if not BOT_TOKEN:
        print("❌ Token manquant!")
        print("   Crée une application sur https://discord.com/developers/applications")
        print("   Puis définis la variable AUBAINES_RAPIDES_BOT_TOKEN")
        print("   Ou modifie directement BOT_TOKEN dans le script.")
        sys.exit(1)

    print("🚀 Démarrage du bot Aubaines Rapides...")
    bot.run(BOT_TOKEN)


if __name__ == "__main__":
    main()
