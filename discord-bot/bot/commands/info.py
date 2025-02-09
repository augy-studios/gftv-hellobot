from discord.ext import commands
from discord import app_commands, ui
import discord
import platform
from core.logger import log_action
from config import BOT_OWNER_ID

class ListView(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @ui.button(label="List Known Users", style=discord.ButtonStyle.primary, custom_id="list_users")
    async def list_users(self, interaction: discord.Interaction, button: ui.Button):
        known_users = {user.id: user.name for guild in self.bot.guilds for user in guild.members}
        response = "Known Users:\n" + "\n".join([f"{user_id}: {name}" for user_id, name in known_users.items()])
        await interaction.response.send_message(f"```{response[:1900]}```")
        await log_action(self.bot, interaction)

    @ui.button(label="List Channels", style=discord.ButtonStyle.success, custom_id="list_channels")
    async def list_channels(self, interaction: discord.Interaction, button: ui.Button):
        channels = [f"{channel.name} ({channel.id})" for guild in self.bot.guilds for channel in guild.channels]
        response = "Channels:\n" + "\n".join(channels)
        await interaction.response.send_message(f"```{response[:1900]}```")
        await log_action(self.bot, interaction)

    @ui.button(label="List Groups", style=discord.ButtonStyle.danger, custom_id="list_groups")
    async def list_groups(self, interaction: discord.Interaction, button: ui.Button):
        groups = [f"{guild.name} ({guild.id})" for guild in self.bot.guilds]
        response = "Groups:\n" + "\n".join(groups)
        await interaction.response.send_message(f"```{response[:1900]}```")
        await log_action(self.bot, interaction)

class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="userinfo", description="Get user information.")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member):
        embed = discord.Embed(title="User Info", color=discord.Color.green())
        embed.add_field(name="Username", value=member.name, inline=False)
        embed.add_field(name="User ID", value=member.id, inline=False)
        embed.add_field(name="Joined", value=member.joined_at, inline=False)
        await interaction.response.send_message(embed=embed)
        await log_action(self.bot, interaction)

    @app_commands.command(name="serverinfo", description="Get server information.")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        embed = discord.Embed(title="Server Info", color=discord.Color.orange())
        embed.add_field(name="Server Name", value=guild.name)
        embed.add_field(name="Server ID", value=guild.id)
        embed.add_field(name="Member Count", value=guild.member_count)
        await interaction.response.send_message(embed=embed)
        await log_action(self.bot, interaction)

    @app_commands.command(name="botinfo", description="Get detailed bot information.")
    async def botinfo(self, interaction: discord.Interaction):
        # Counting important bot stats
        known_users = {user.id for guild in self.bot.guilds for user in guild.members}
        total_channels = sum(len(guild.channels) for guild in self.bot.guilds)
        total_guilds = len(self.bot.guilds)

        # Embed information
        embed = discord.Embed(title="Bot Info", color=discord.Color.purple())
        embed.add_field(name="Bot Name", value=self.bot.user.name, inline=True)
        embed.add_field(name="Owner ID", value=str(BOT_OWNER_ID), inline=True)
        embed.add_field(name="Python Version", value=platform.python_version(), inline=True)
        embed.add_field(name="Library", value="discord.py", inline=True)
        embed.add_field(name="Groups", value=str(total_guilds), inline=True)
        embed.add_field(name="Channels", value=str(total_channels), inline=True)
        embed.add_field(name="Known Users", value=str(len(known_users)), inline=True)

        # Check if the user is the bot owner
        if interaction.user.id == BOT_OWNER_ID:
            await interaction.response.send_message(embed=embed, view=ListView(self.bot))
        else:
            await interaction.response.send_message(embed=embed)

        await log_action(self.bot, interaction)

async def setup(bot):
    await bot.add_cog(Info(bot))
