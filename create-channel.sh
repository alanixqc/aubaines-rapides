#!/bin/bash
# Discord bot token - set via environment or .env
DISCORD_BOT_TOKEN="${DISCORD_BOT_TOKEN:?Please set DISCORD_BOT_TOKEN}"
GUILD_ID="1252770589282668607"

# Create channel
curl -s -X POST "https://discord.com/api/v10/guilds/$GUILD_ID/channels" \
  -H "Authorization: Bot $DISCORD_BOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"aubaines-rapides-image","type":0,"topic":"Rapports design critique - Aubaines Rapides"}'
