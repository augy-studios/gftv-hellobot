from discord.ext import commands
from discord import app_commands, ui
import discord
import platform
import random
from core.logger import log_action
from config import BOT_OWNER_ID

class Miscellaneous(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

async def setup(bot):
    await bot.add_cog(Miscellaneous(bot))
