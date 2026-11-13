"""Settings for the Discord bot, read from token.env."""
import os
from dotenv import load_dotenv

# Load all variables from token.env
load_dotenv("token.env")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Optional numeric ids: None when the key is missing or empty
if os.getenv("LOG_GUILD_ID"):
    LOG_GUILD_ID = int(os.getenv("LOG_GUILD_ID"))
else:
    LOG_GUILD_ID = None
if os.getenv("LOG_CHANNEL_ID"):
    LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
else:
    LOG_CHANNEL_ID = None
if os.getenv("BOT_OWNER_ID"):
    BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID"))
else:
    BOT_OWNER_ID = None
