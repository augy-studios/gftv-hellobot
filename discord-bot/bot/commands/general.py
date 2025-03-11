import discord
import random
import re
from discord.ext import commands
from discord import app_commands
from core.logger import log_action

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.command_ids = {}  # Store command IDs dynamically

    async def fetch_command_ids(self):
        """Fetch and store command IDs after syncing."""
        commands = await self.bot.tree.fetch_commands()
        for cmd in commands:
            self.command_ids[cmd.name] = cmd.id

    @app_commands.command(name="ping", description="Check the bot's latency.")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"Pong! 🏓 Latency: {latency}ms")
        await log_action(self.bot, interaction)

    @app_commands.command(name="help", description="Display a list of available commands categorized by their category.")
    @app_commands.describe(category="Choose a category to see its commands")
    async def help_command(self, interaction: discord.Interaction, category: str = None):
        embed = discord.Embed(title="Help - Available Commands", color=discord.Color.random())
        embed.description = "Use / followed by the command name to interact with the bot. Click on a command to execute it."
        embed.set_footer(text="Made with ❤️ by GFTV Intl © 2025 All Rights Sniffed • https://globalfurry.tv/")

        # Organize commands by category (cog)
        cog_commands = {}
        for cog_name, cog in self.bot.cogs.items():
            commands_list = []

            for command in cog.get_app_commands():
                command_id = self.command_ids.get(command.name)
                if command_id:
                    commands_list.append(f"**</{command.name}:{command_id}>** - {command.description}")
                else:
                    commands_list.append(f"**/{command.name}** - {command.description}")

            if commands_list:
                cog_commands[cog_name] = commands_list

        # Add each category of commands to the embed
        if category:
            if category in cog_commands:
                embed.add_field(name=f"**{category} Commands**", value="\n".join(cog_commands[category]), inline=False)
            else:
                await interaction.response.send_message(f"❌ No commands found for category: {category}", ephemeral=True)
                return
        else:
            for category, commands in cog_commands.items():
                embed.add_field(name=f"**{category} Commands**", value="\n".join(commands), inline=False)

        await interaction.response.send_message(embed=embed)

    @help_command.autocomplete("category")
    async def help_command_autocomplete(self, interaction: discord.Interaction, current: str):
        categories = [cog_name for cog_name in self.bot.cogs.keys()]
        return [app_commands.Choice(name=category, value=category) for category in categories if current.lower() in category.lower()]

async def setup(bot):
    cog = General(bot)
    await cog.fetch_command_ids()  # Fetch IDs before adding the cog
    await bot.add_cog(cog)
