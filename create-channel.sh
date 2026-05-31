#!/bin/bash
# Read token
TOKEN=*** "^DISCORD_BOT_TOKEN=*** "$HOME/AppData/Local/hermes/.env" | cut -d= -f2 | head -1)
GUILD_ID="1252770589282668607"

# Create channel
curl -s -X POST "https://discord.com/api/v10/guilds/$GUILD_ID/channels" \
  -H "Authorization: Bot $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"aubaines-rapides-image","type":0,"topic":"Rapports design critique - Aubaines Rapides"}'
