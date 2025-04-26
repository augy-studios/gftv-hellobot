import os
import csv
import string
import datetime
import random

import discord
from discord.ext import commands

from core.logger import setup_error_handling
from config import DISCORD_TOKEN, LOG_GUILD_ID
from user_utils import update_known_users

# ----- Bot setup -----
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
bot = commands.AutoShardedBot(command_prefix="!", intents=intents)

# ----- Session-ID generation & logging -----
SESSION_FILE = "sessions.csv"

def generate_session_id():
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choice(chars) for _ in range(8))

# Create file + header if it doesn't exist
if not os.path.exists(SESSION_FILE):
    with open(SESSION_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "session_id", "datetime_now"])

# Read existing IDs & find max row-ID
existing = set()
max_id = 0
with open(SESSION_FILE, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        existing.add(row["session_id"])
        try:
            row_id = int(row["id"])
            max_id = max(max_id, row_id)
        except ValueError:
            pass

# Pick a fresh session_id
session_id = generate_session_id()
while session_id in existing:
    session_id = generate_session_id()

# Append new row
new_id = max_id + 1
now_iso = datetime.datetime.now().isoformat()
with open(SESSION_FILE, "a", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([new_id, session_id, now_iso])

# ----- Activity updater -----
async def update_activity():
    # set a custom status with an emoji
    await bot.change_presence(
        activity=discord.CustomActivity(name=f"Hello, GFTV! (Session ID: {session_id})", emoji=":wave:")
    )

# ----- Load extensions, events, etc. -----
async def load_cogs():
    await bot.load_extension("bot.commands.general")
    await bot.load_extension("bot.commands.info")
    await bot.load_extension("bot.commands.utility")
    await bot.load_extension("bot.commands.voice")
    await bot.load_extension("bot.commands.moderation")
    await bot.load_extension("bot.commands.games")
    await bot.load_extension("bot.commands.fun")
    await bot.load_extension("bot.commands.generative")
    await bot.load_extension("bot.commands.profile")
    await bot.load_extension("bot.commands.admin")

# Function to fetch and display command IDs
async def fetch_command_ids():
    commands = await bot.tree.fetch_commands()
    print("\n=== Registered Slash Commands ===")
    for cmd in commands:
        print(f"/{cmd.name} - ID: {cmd.id}")
    print("================================\n")

# Event to update known users when the bot is ready
@bot.event
async def on_ready():
    await load_cogs()
    await bot.tree.sync()  # Sync commands with Discord
    await bot.tree.sync(guild=discord.Object(id=LOG_GUILD_ID))
    await bot.tree.sync(guild=discord.Object(id=576590416296542249))
    await fetch_command_ids()  # Fetch and display command IDs
    await update_known_users(bot)  # Update known users with all guild members
    await update_activity()  # Update the status on startup
    print(f"Logged in as {bot.user} (ID: {bot.user.id}) with {bot.shard_count} shard(s) [Session ID: {session_id}]")

# Update known users and activity when joining a new guild
@bot.event
async def on_guild_join(guild):
    await update_known_users(bot)
    await update_activity()

# Update known users and activity when leaving a guild
@bot.event
async def on_guild_remove(guild):
    await update_known_users(bot)
    await update_activity()

# ----- Error handling & run bot -----
setup_error_handling(bot)
bot.run(DISCORD_TOKEN)