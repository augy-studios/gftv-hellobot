from discord.ext import commands
from discord import app_commands, ui
import discord
import platform
import random
from core.logger import log_action
from config import BOT_OWNER_ID
from user_utils import ensure_users_file, get_known_users

class ListView(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @ui.button(label="List Known Users", style=discord.ButtonStyle.primary, custom_id="list_users")
    async def list_users(self, interaction: discord.Interaction, button: ui.Button):
        known_users = get_known_users()  # Use the function from user_utils.py
        response = "Known Users:\n" + "\n".join(known_users) if known_users else "No known users found."
        await interaction.response.send_message(content=f"```{response[:1900]}```", ephemeral=True)

    @ui.button(label="List Channels", style=discord.ButtonStyle.success, custom_id="list_channels")
    async def list_channels(self, interaction: discord.Interaction, button: ui.Button):
        channels = [f"{channel.name} ({channel.id})" for guild in self.bot.guilds for channel in guild.channels]
        response = "Channels:\n" + "\n".join(channels) if channels else "No channels found."
        await interaction.response.send_message(content=f"```{response[:1900]}```", ephemeral=True)

    @ui.button(label="List Guilds", style=discord.ButtonStyle.danger, custom_id="list_guilds")
    async def list_guilds(self, interaction: discord.Interaction, button: ui.Button):
        guilds = [f"{guild.name} ({guild.id})" for guild in self.bot.guilds]
        response = "Guilds:\n" + "\n".join(guilds) if guilds else "No guilds found."
        await interaction.response.send_message(content=f"```{response[:1900]}```", ephemeral=True)

class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="userinfo", description="Get user information.")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member):
        embed = discord.Embed(title="User Info", color=discord.Color(random.randint(0, 0xFFFFFF)))
        embed.add_field(name="Username", value=member.name, inline=False)
        embed.add_field(name="User ID", value=member.id, inline=False)
        embed.add_field(name="Joined", value=member.joined_at, inline=False)
        await interaction.response.send_message(embed=embed)
        await log_action(self.bot, interaction)

    @app_commands.command(name="serverinfo", description="Get server information.")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        embed = discord.Embed(title="Guild Info", color=discord.Color(random.randint(0, 0xFFFFFF)))
        embed.add_field(name="Guild Name", value=guild.name)
        embed.add_field(name="Guild ID", value=guild.id)
        embed.add_field(name="Member Count", value=guild.member_count)
        await interaction.response.send_message(embed=embed)
        await log_action(self.bot, interaction)

    @app_commands.command(name="botinfo", description="Get detailed bot information.")
    async def botinfo(self, interaction: discord.Interaction):
        ensure_users_file()  # Make sure the users.txt file is checked/created
        known_users = get_known_users()  # Get users from users.txt
        total_channels = sum(len(guild.channels) for guild in self.bot.guilds)
        total_guilds = len(self.bot.guilds)

        # Get bot description from application info
        app_info = await self.bot.application_info()
        bot_description = app_info.description or "No description provided."

        # Embed information
        embed = discord.Embed(title="Bot Info", color=discord.Color(random.randint(0, 0xFFFFFF)))
        embed.add_field(name="Bot Name", value=self.bot.user.name, inline=True)
        embed.add_field(name="Owner ID", value=str(BOT_OWNER_ID), inline=True)
        embed.add_field(name="Bot Description", value=bot_description, inline=False)
        embed.add_field(name="Python Version", value=platform.python_version(), inline=True)
        embed.add_field(name="Library", value="discord.py", inline=True)
        embed.add_field(name="Guilds", value=str(total_guilds), inline=True)
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
