"""Unit tests for the pure logic in the Discord bot. Run from discord-bot/: python3 -m unittest

Stand-in settings are set here, before any bot module is imported, so no
token.env is needed and nothing touches the network.
"""
import os
import sys
from pathlib import Path

# Stand-in values (setdefault: a real environment is never overwritten).
for key, value in {"DISCORD_TOKEN": "stub-token", "LOG_GUILD_ID": "1",
                   "LOG_CHANNEL_ID": "2", "BOT_OWNER_ID": "3"}.items():
    os.environ.setdefault(key, value)

# Let `import bot...`, `import core...` and `import config` work from any folder.
BOT_FOLDER = str(Path(__file__).resolve().parent.parent)
if BOT_FOLDER not in sys.path:
    sys.path.insert(0, BOT_FOLDER)
