import os
import discord
from discord.ext import commands
from core.logger import setup_error_handling
from config import DISCORD_TOKEN
from user_utils import update_known_users

# Define bot with AutoShardedBot
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent if needed
intents.guilds = True
intents.members = True  # Required to fetch all members
bot = commands.AutoShardedBot(command_prefix="!", intents=intents)

# Function to update the activity
async def update_activity():
    activity = discord.Activity(type=discord.ActivityType.watching, name=f"over GFTV communities ({bot.shard_count} shards)")
    await bot.change_presence(activity=activity)

# Load cogs
async def load_cogs():
    await bot.load_extension("bot.commands.general")
    await bot.load_extension("bot.commands.moderation")
    await bot.load_extension("bot.commands.info")
    await bot.load_extension("bot.commands.fun")

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
    await fetch_command_ids()  # Fetch and display command IDs
    await update_known_users(bot)  # Update known users with all guild members
    await update_activity()  # Update the status on startup
    print(f"Logged in as {bot.user} (ID: {bot.user.id}) with {bot.shard_count} shard(s)")

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

# Initialize error handling
setup_error_handling(bot)

# Run the bot
bot.run(DISCORD_TOKEN)