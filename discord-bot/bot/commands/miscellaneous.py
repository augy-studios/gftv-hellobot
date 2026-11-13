from discord.ext import commands
from discord import app_commands, ui
import discord
import platform
import random
from core.logger import log_action
from config import BOT_OWNER_ID

class Miscellaneous(commands.Cog):
    """Placeholder cog for miscellaneous commands (none yet)."""

    def __init__(self, bot):
        """Keep a reference to the bot."""
        self.bot = bot

async def setup(bot):
    """Load the Miscellaneous cog."""
    await bot.add_cog(Miscellaneous(bot))
