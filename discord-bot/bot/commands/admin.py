import asyncio
import time
import datetime
import json
import os
import random
import re
import sys

from bs4 import BeautifulSoup
import lxml
import requests
from config import BOT_OWNER_ID, LOG_GUILD_ID
import discord
import psutil
from discord.ext import commands
from discord import app_commands
from core.logger import log_action

class EvalPager(discord.ui.View):
    def __init__(self, pages):
        super().__init__(timeout=300)
        self.pages = pages
        self.index = 0
        self.total = len(pages)
        # Buttons: Previous, Page Info, Next
        self.prev_button = discord.ui.Button(label="Previous", style=discord.ButtonStyle.primary, disabled=True)
        self.next_button = discord.ui.Button(label="Next", style=discord.ButtonStyle.primary, disabled=(self.total <= 1))
        self.page_button = discord.ui.Button(label=f"{self.index+1}/{self.total}", style=discord.ButtonStyle.secondary, disabled=True)
        # Assign callbacks
        self.prev_button.callback = self.prev_callback
        self.next_button.callback = self.next_callback
        # Add to view
        self.add_item(self.prev_button)
        self.add_item(self.page_button)
        self.add_item(self.next_button)

    async def prev_callback(self, interaction: discord.Interaction):
        self.index -= 1
        self._update_buttons()
        await interaction.response.edit_message(
            content=f"```py\n{self.pages[self.index]}\n```", view=self
        )

    async def next_callback(self, interaction: discord.Interaction):
        self.index += 1
        self._update_buttons()
        await interaction.response.edit_message(
            content=f"```py\n{self.pages[self.index]}\n```", view=self
        )

    def _update_buttons(self):
        self.prev_button.disabled = (self.index == 0)
        self.next_button.disabled = (self.index == self.total - 1)
        self.page_button.label = f"{self.index+1}/{self.total}"

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

    @dev.command(
        name="stats",
        description="Show process stats (CPU%, memory usage, event loop lag)"
    )
    @app_commands.check(lambda inter: inter.user.id == BOT_OWNER_ID)
    async def stats(self, interaction: discord.Interaction):
        """Usage: /dev stats"""
        proc = psutil.Process(os.getpid())
        cpu = proc.cpu_percent(interval=0.1)
        mem = proc.memory_info().rss / 1024**2  # MB
        loop = asyncio.get_running_loop()
        start = loop.time()
        await asyncio.sleep(0)
        lag_ms = (loop.time() - start) * 1000
        embed = discord.Embed(title="Bot Statistics", color=discord.Color.blurple())
        embed.add_field(name="CPU Usage", value=f"{cpu:.2f}%", inline=True)
        embed.add_field(name="Memory Usage", value=f"{mem:.2f} MB", inline=True)
        embed.add_field(name="Event Loop Lag", value=f"{lag_ms:.2f} ms", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await log_action(self.bot, interaction)

    @dev.command(
        name="reload",
        description="Reload one or all Cogs"
    )
    @app_commands.describe(cog_name="Name of the cog to reload, or 'all' for every extension")
    @app_commands.check(lambda inter: inter.user.id == BOT_OWNER_ID)
    async def reload(self, interaction: discord.Interaction, cog_name: str):
        """Usage: /dev reload <cog_name|all>"""
        reloaded = []
        errors = []
        if cog_name.lower() == 'all':
            for ext in list(self.bot.extensions):
                try:
                    await self.bot.reload_extension(ext)
                    reloaded.append(ext)
                except Exception as e:
                    errors.append(f"{ext}: {e}")
        else:
            ext = f"bot.commands.{cog_name}"
            try:
                await self.bot.reload_extension(ext)
                reloaded.append(ext)
            except Exception as e:
                errors.append(f"{ext}: {e}")
        msg = []
        if reloaded:
            msg.append(f"✅ Reloaded: {', '.join(reloaded)}")
        if errors:
            msg.append(f"❌ Errors: {'; '.join(errors)}")
        await interaction.response.send_message("\n".join(msg), ephemeral=True)
        await log_action(self.bot, interaction)

    @dev.command(
        name="sync",
        description="Force a slash-command sync (global or to a specific guild ID)"
    )
    @app_commands.describe(guild_id="Optional guild ID for guild-specific sync")
    @app_commands.check(lambda inter: inter.user.id == BOT_OWNER_ID)
    async def sync(self, interaction: discord.Interaction, guild_id: int = None):
        """Usage: /dev sync [guild_id]"""
        if guild_id:
            await self.bot.tree.sync(guild=discord.Object(id=guild_id))
            msg = f"🔄 Synced commands to guild `{guild_id}`."
        else:
            await self.bot.tree.sync()
            msg = "🔄 Synced commands globally."
        await interaction.response.send_message(msg, ephemeral=True)
        await log_action(self.bot, interaction)

    @dev.command(
        name="eval",
        description="Safely evaluate a short Python snippet"
    )
    @app_commands.describe(code="Python code to evaluate")
    @app_commands.check(lambda inter: inter.user.id == BOT_OWNER_ID)
    async def _eval(self, interaction: discord.Interaction, code: str):
        """Usage: /dev eval <code>"""
        # Define a small whitelist of builtins
        safe_builtins = {
            'len': len, 'min': min, 'max': max, 'sum': sum,
            'any': any, 'all': all, 'list': list, 'dict': dict,
            'set': set, 'tuple': tuple, 'range': range, 'sorted': sorted,
            'print': print, 'str': str, 'int': int, 'float': float, 'round': round,
            'bool': bool, 'True': True, 'False': False, 'None': None,
            'os': os, 'sys': sys, 'asyncio': asyncio, 'discord': discord, 'commands': commands,
            'psutil': psutil, 'time': time, 'random': random, 'json': json, 'datetime': datetime,
            're': re, 'requests': requests, 'BeautifulSoup': BeautifulSoup, 'lxml': lxml,
        }
        # Prepare environment
        env = {'bot': self.bot, 'discord': discord, 'commands': commands}
        env.update(safe_builtins)

        body = code.strip('` ')
        try:
            # Try single expression
            result = eval(body, {'__builtins__': {}}, env)
        except SyntaxError:
            # Try block execution
            exec_env = env.copy()
            try:
                exec(body, {'__builtins__': {}}, exec_env)
                result = exec_env
            except Exception as e:
                return await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
        except Exception as e:
            return await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

        output = str(result)
        # If output is long, split into pages with buttons
        if len(output) > 1024:
            pages = [output[i:i+1024] for i in range(0, len(output), 1024)]
            view = EvalPager(pages)
            await interaction.response.send_message(f"```py\n{pages[0]}\n```", view=view, ephemeral=True)
        else:
            await interaction.response.send_message(f"```py\n{output}```", ephemeral=True)

        await log_action(self.bot, interaction)

async def setup(bot: commands.Bot):
    guild1 = discord.Object(id=LOG_GUILD_ID)
    guild2 = discord.Object(id=576590416296542249)
    await bot.add_cog(Admin(bot), guilds=[guild1, guild2])
