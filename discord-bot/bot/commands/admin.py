import os
import sys
from config import BOT_OWNER_ID
import discord
from discord.ext import commands
from discord import app_commands
from core.logger import log_action

class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    dev = app_commands.Group(
        name="dev",
        description="Developer-only commands"
    )

    @dev.command(
        name="restart",
        description="Restart the bot (owner only)"
    )
    @app_commands.check(lambda inter: inter.user.id == BOT_OWNER_ID)
    async def restart(self, interaction: discord.Interaction):
        """Usage: /dev restart"""
        await interaction.response.send_message("🔄 Restarting…", ephemeral=True)
        await self.bot.close()
        os.execv(sys.executable, [sys.executable, "-m", "main"])
        await log_action(self.bot, interaction)

    @restart.error
    async def restart_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(
                "❌ You don't have permissions to run this.", ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
