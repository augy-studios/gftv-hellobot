import discord
import random
from discord.ext import commands
from discord import app_commands
from core.logger import log_action

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Check the bot's latency.")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"Pong! 🏓 Latency: {latency}ms")
        await log_action(self.bot, interaction)
    
    @app_commands.command(name="help", description="Display a list of available commands categorized by their cog.")
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Help - Available Commands", color=discord.Color(random.randint(0, 0xFFFFFF)))
        embed.set_footer(text="Use / followed by the command name to execute it.")

        # Organize commands by category (cog)
        cog_commands = {}
        for cog_name, cog in self.bot.cogs.items():
            commands_list = [f"/{command.name} - {command.description}" for command in cog.get_app_commands()]
            if commands_list:
                cog_commands[cog_name] = commands_list

        # Add each category of commands to the embed
        for category, commands in cog_commands.items():
            embed.add_field(name=f"**{category} Commands**", value="\n".join(commands), inline=False)

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(General(bot))
