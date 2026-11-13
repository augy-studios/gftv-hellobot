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
intents.voice_states = True
# Plain Bot, not AutoShardedBot: the sharded client's reconnect path in discord.py 2.5.x
# doesn't catch ReconnectWebSocket and terminates the process instead of reconnecting.
# Sharding is only required past 2500 guilds anyway.
bot = commands.Bot(command_prefix="!", intents=intents)

# ----- Guard to load cogs only once -----
cogs_loaded = False

# ----- Session-ID generation & logging -----
SESSION_FILE = "sessions.csv"


def generate_session_id():
    """Return a random 8-character session id made of lowercase letters and digits."""
    allowed_characters = string.ascii_lowercase + string.digits
    return "".join(random.choice(allowed_characters) for _ in range(8))  # builds the 8 random characters


# Step 1: create the file with its header if it doesn't exist
if not os.path.exists(SESSION_FILE):
    with open(SESSION_FILE, "w", newline="", encoding="utf-8") as session_file:
        session_writer = csv.writer(session_file)
        session_writer.writerow(["id", "session_id", "datetime_now"])

# Step 2: read the existing session ids and find the highest row id
existing_session_ids = set()
max_row_id = 0
with open(SESSION_FILE, newline="", encoding="utf-8") as session_file:
    session_reader = csv.DictReader(session_file)
    for row in session_reader:
        existing_session_ids.add(row["session_id"])
        try:
            row_id = int(row["id"])
            max_row_id = max(max_row_id, row_id)
        except ValueError:
            pass

# Step 3: pick a session id that hasn't been used before
session_id = generate_session_id()
while session_id in existing_session_ids:
    session_id = generate_session_id()

# Step 4: append the new row
new_row_id = max_row_id + 1
now_iso = datetime.datetime.now().isoformat()
with open(SESSION_FILE, "a", newline="", encoding="utf-8") as session_file:
    session_writer = csv.writer(session_file)
    session_writer.writerow([new_row_id, session_id, now_iso])

# ----- Activity updater -----
async def update_activity():
    """Set the bot's status to "Hello, GFTV!" with this run's session id."""
    # set a custom status with an emoji
    await bot.change_presence(
        activity=discord.CustomActivity(name=f"Hello, GFTV! (Session ID: {session_id})", emoji=":wave:")
    )

# ----- Load extensions, events, etc. -----
async def load_cogs():
    """Load every cog module that isn't loaded yet."""
    extensions = [
        "bot.commands.general",
        "bot.commands.info",
        "bot.commands.utility",
        "bot.commands.moderation",
        "bot.commands.games",
        "bot.commands.fun",
        "bot.commands.generative",
        "bot.commands.profile",
        "bot.commands.admin",
    ]
    for extension_name in extensions:
        if extension_name not in bot.extensions:
            try:
                await bot.load_extension(extension_name)
                print(f"Loaded extension: {extension_name}")
            except commands.ExtensionAlreadyLoaded:
                print(f"Extension already loaded, skipping: {extension_name}")

# Function to fetch and display command IDs
async def fetch_command_ids():
    """Print every registered slash command with its id."""
    registered_commands = await bot.tree.fetch_commands()
    print("\n=== Registered Slash Commands ===")
    for registered_command in registered_commands:
        print(f"/{registered_command.name} - ID: {registered_command.id}")
    print("================================\n")

# Event to update known users when the bot is ready
@bot.event
async def on_ready():
    """On connect: load the cogs once, sync commands, refresh known users and the status."""
    global cogs_loaded
    if not cogs_loaded:
        await load_cogs()
        cogs_loaded = True
    else:
        print(f"{bot.user} reconnected; cogs already loaded")
    await bot.tree.sync()  # Sync commands with Discord
    await bot.tree.sync(guild=discord.Object(id=LOG_GUILD_ID))
    await bot.tree.sync(guild=discord.Object(id=576590416296542249))
    await fetch_command_ids()  # Fetch and display command IDs
    await update_known_users(bot)  # Update known users with all guild members
    await update_activity()  # Update the status on startup
    print(f"Logged in as {bot.user} (ID: {bot.user.id}) "
          f"with {bot.shard_count or 1} shard(s) [Session ID: {session_id}]")

# Update known users and activity when joining a new guild
@bot.event
async def on_guild_join(guild):
    """Refresh known users and the status after joining a guild."""
    print(f"Joined new guild: {guild.name} (ID: {guild.id})")
    await update_known_users(bot)
    await update_activity()

# Update known users and activity when leaving a guild
@bot.event
async def on_guild_remove(guild):
    """Refresh known users and the status after leaving a guild."""
    print(f"Left guild: {guild.name} (ID: {guild.id})")
    await update_known_users(bot)
    await update_activity()

@bot.listen("on_socket_response")
async def _debug_voice(payload):
    """Print a line whenever a voice state or voice server update arrives."""
    event_type = payload.get("t")
    if event_type in {"VOICE_STATE_UPDATE", "VOICE_SERVER_UPDATE"}:
        print("[VOICE EVENT]", event_type)

# ----- Error handling & run bot -----
setup_error_handling(bot)
bot.run(DISCORD_TOKEN)