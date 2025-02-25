import os
import discord
from discord.ext import commands
from core.logger import setup_error_handling
from config import DISCORD_TOKEN
from user_utils import add_user_to_file

# Define bot with AutoShardedBot
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent if needed
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

# Event to handle user interactions and log their ID
@bot.event
async def on_interaction(interaction: discord.Interaction):
    add_user_to_file(interaction.user.id)

# Register slash commands and fetch IDs
@bot.event
async def on_ready():
    await load_cogs()
    await bot.tree.sync()  # Sync commands with Discord
    await fetch_command_ids()  # Fetch and display command IDs
    await update_activity()  # Update the status on startup
    print(f"Logged in as {bot.user} (ID: {bot.user.id}) with {bot.shard_count} shard(s)")

# Update activity whenever the bot joins a new guild
@bot.event
async def on_guild_join(guild):
    await update_activity()

# Update activity whenever the bot leaves a guild
@bot.event
async def on_guild_remove(guild):
    await update_activity()

# Initialize error handling
setup_error_handling(bot)

# Run the bot
bot.run(DISCORD_TOKEN)