import asyncio
import time
import datetime
import json
import os
import random
import re
import sys
import csv
from datetime import datetime

from bs4 import BeautifulSoup
import lxml
import requests
from config import BOT_OWNER_ID, LOG_GUILD_ID
import discord
import psutil
from discord.ext import commands
from discord import app_commands
from core.logger import log_action

def is_bot_owner(interaction: discord.Interaction) -> bool:
    """Check for the /dev commands: true only for the bot owner."""
    return interaction.user.id == BOT_OWNER_ID


class EvalPager(discord.ui.View):
    """Pages through long /dev eval output with Previous and Next buttons."""

    def __init__(self, pages):
        """Create the navigation buttons for the given pages."""
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
        """Show the previous page of output."""
        self.index -= 1
        self._update_buttons()
        await interaction.response.edit_message(
            content=f"```py\n{self.pages[self.index]}\n```", view=self
        )

    async def next_callback(self, interaction: discord.Interaction):
        """Show the next page of output."""
        self.index += 1
        self._update_buttons()
        await interaction.response.edit_message(
            content=f"```py\n{self.pages[self.index]}\n```", view=self
        )

    def _update_buttons(self):
        """Disable the buttons at either end and refresh the page label."""
        self.prev_button.disabled = (self.index == 0)
        self.next_button.disabled = (self.index == self.total - 1)
        self.page_button.label = f"{self.index+1}/{self.total}"

class SessionsPager(discord.ui.View):
    """Pages through the session data with Previous and Next buttons."""

    def __init__(self, pages):
        """Create the navigation buttons for the given pages."""
        super().__init__(timeout=300)
        self.pages = pages
        self.index = 0
        self.total = len(pages)

        # buttons
        self.prev_button = discord.ui.Button(label="Previous", style=discord.ButtonStyle.primary, disabled=True)
        self.page_button = discord.ui.Button(label=f"{self.index+1}/{self.total}", style=discord.ButtonStyle.secondary, disabled=True)
        self.next_button = discord.ui.Button(label="Next", style=discord.ButtonStyle.primary, disabled=(self.total <= 1))

        # attach callbacks
        self.prev_button.callback = self.prev_callback
        self.next_button.callback = self.next_callback

        # add to view
        self.add_item(self.prev_button)
        self.add_item(self.page_button)
        self.add_item(self.next_button)

    def _update_buttons(self):
        """Disable the buttons at either end and refresh the page label."""
        self.prev_button.disabled = (self.index == 0)
        self.next_button.disabled = (self.index == self.total - 1)
        self.page_button.label = f"{self.index+1}/{self.total}"

    async def prev_callback(self, interaction: discord.Interaction):
        """Show the previous page of sessions."""
        self.index -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self._make_embed(), view=self)

    async def next_callback(self, interaction: discord.Interaction):
        """Show the next page of sessions."""
        self.index += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self._make_embed(), view=self)

    def _make_embed(self) -> discord.Embed:
        """Build the embed for the current page of sessions."""
        embed = discord.Embed(title="Session Data", color=discord.Color.random())
        chunk = self.pages[self.index]
        for session in chunk:
            embed.add_field(
                name=f"Session ID: {session['session_id']}",
                value=f"ID: {session['id']}\nTimestamp: {session['timestamp']}",
                inline=False
            )
        embed.set_footer(text=f"Page {self.index+1}/{self.total}")
        return embed

class Admin(commands.Cog):
    """Owner-only /dev commands: restart, stats, reload, sync, eval and sessions."""

    def __init__(self, bot: commands.Bot):
        """Keep a reference to the bot."""
        self.bot = bot

    dev = app_commands.Group(
        name="dev",
        description="Developer-only commands"
    )

    @dev.command(
        name="restart",
        description="Restart the bot (owner only)"
    )
    @app_commands.check(is_bot_owner)
    async def restart(self, interaction: discord.Interaction):
        """Close the bot and start it again. Usage: /dev restart"""
        await interaction.response.send_message("🔄 Restarting…", ephemeral=True)
        await self.bot.close()
        os.execv(sys.executable, [sys.executable, "-m", "main"])
        await log_action(self.bot, interaction)

    @restart.error
    async def restart_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Tell non-owners they may not restart the bot."""
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(
                "❌ You don't have permissions to run this.", ephemeral=True
            )

    @dev.command(
        name="stats",
        description="Show process stats (CPU%, memory usage, event loop lag)"
    )
    @app_commands.check(is_bot_owner)
    async def stats(self, interaction: discord.Interaction):
        """Show CPU, memory and event loop lag. Usage: /dev stats"""
        # Measure this process's CPU and memory use
        process = psutil.Process(os.getpid())
        cpu_percent = process.cpu_percent(interval=0.1)
        memory_usage = process.memory_info().rss / 1024**2  # MB
        # Measure how long the event loop takes to come back after a yield
        loop = asyncio.get_running_loop()
        start_time = loop.time()
        await asyncio.sleep(0)
        lag_ms = (loop.time() - start_time) * 1000
        # Report the numbers
        embed = discord.Embed(title="Bot Statistics", color=discord.Color.blurple())
        embed.add_field(name="CPU Usage", value=f"{cpu_percent:.2f}%", inline=True)
        embed.add_field(name="Memory Usage", value=f"{memory_usage:.2f} MB", inline=True)
        embed.add_field(name="Event Loop Lag", value=f"{lag_ms:.2f} ms", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await log_action(self.bot, interaction)

    @dev.command(
        name="reload",
        description="Reload one or all Cogs"
    )
    @app_commands.describe(cog_name="Name of the cog to reload, or 'all' for every extension")
    @app_commands.check(is_bot_owner)
    async def reload(self, interaction: discord.Interaction, cog_name: str):
        """Reload one cog or all of them. Usage: /dev reload <cog_name|all>"""
        reloaded = []
        errors = []
        # Reload every loaded extension, or just the named one
        if cog_name.lower() == 'all':
            for extension in list(self.bot.extensions):
                try:
                    await self.bot.reload_extension(extension)
                    reloaded.append(extension)
                except Exception as error:
                    errors.append(f"{extension}: {error}")
        else:
            extension = f"bot.commands.{cog_name}"
            try:
                await self.bot.reload_extension(extension)
                reloaded.append(extension)
            except Exception as error:
                errors.append(f"{extension}: {error}")
        # Report what was reloaded and what failed
        message_lines = []
        if reloaded:
            message_lines.append(f"✅ Reloaded: {', '.join(reloaded)}")
        if errors:
            message_lines.append(f"❌ Errors: {'; '.join(errors)}")
        await interaction.response.send_message("\n".join(message_lines), ephemeral=True)
        await log_action(self.bot, interaction)

    @dev.command(
        name="sync",
        description="Force a slash-command sync (global or to a specific guild ID)"
    )
    @app_commands.describe(guild_id="Optional guild ID for guild-specific sync")
    @app_commands.check(is_bot_owner)
    async def sync(self, interaction: discord.Interaction, guild_id: int = None):
        """Sync slash commands. Usage: /dev sync [guild_id]"""
        # Sync to one guild, or globally
        if guild_id:
            await self.bot.tree.sync(guild=discord.Object(id=guild_id))
            message = f"🔄 Synced commands to guild `{guild_id}`."
        else:
            await self.bot.tree.sync()
            message = "🔄 Synced commands globally."
        await interaction.response.send_message(message, ephemeral=True)
        await log_action(self.bot, interaction)

    @dev.command(
        name="eval",
        description="Safely evaluate a short Python snippet"
    )
    @app_commands.describe(code="Python code to evaluate")
    @app_commands.check(is_bot_owner)
    async def _eval(self, interaction: discord.Interaction, code: str):
        """Evaluate a Python snippet with a small whitelist of builtins. Usage: /dev eval <code>"""
        # Step 1: define a small whitelist of builtins
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
        # Step 2: prepare environment
        environment = {'bot': self.bot, 'discord': discord, 'commands': commands}
        environment.update(safe_builtins)

        # Step 3: run it as one expression, falling back to a block of statements
        body = code.strip('` ')
        try:
            # Try single expression
            result = eval(body, {'__builtins__': {}}, environment)
        except SyntaxError:
            # Try block execution
            exec_environment = environment.copy()
            try:
                exec(body, {'__builtins__': {}}, exec_environment)
                result = exec_environment
            except Exception as error:
                return await interaction.response.send_message(f"❌ Error: {error}", ephemeral=True)
        except Exception as error:
            return await interaction.response.send_message(f"❌ Error: {error}", ephemeral=True)

        # Step 4: send the output
        output = str(result)
        # If output is long, split into pages with buttons
        if len(output) > 1024:
            # Cut the output into 1024-character pages
            pages = [output[start:start + 1024] for start in range(0, len(output), 1024)]
            view = EvalPager(pages)
            await interaction.response.send_message(f"```py\n{pages[0]}\n```", view=view, ephemeral=True)
        else:
            await interaction.response.send_message(f"```py\n{output}```", ephemeral=True)

        await log_action(self.bot, interaction)

    @dev.command(
        name="sessions",
        description="Display session data from sessions.csv"
    )
    @app_commands.check(is_bot_owner)
    async def sessions(self, interaction: discord.Interaction):
        """Show the rows of sessions.csv in pages. Usage: /dev sessions"""
        try:
            # Step 1: load all sessions
            sessions = []
            with open("sessions.csv", "r", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    timestamp_seconds = int(datetime.fromisoformat(row["datetime_now"]).timestamp())
                    sessions.append({
                        "id": row["id"],
                        "session_id": row["session_id"],
                        "timestamp": f"<t:{timestamp_seconds}:F>"
                    })

            if not sessions:
                return await interaction.response.send_message("No session data found.", ephemeral=True)

            # Step 2: chunk into pages of 25
            # Build one list of up to 25 sessions per page
            chunks = [sessions[start:start + 25] for start in range(0, len(sessions), 25)]
            # Step 3: send the first page with its buttons
            pager = SessionsPager(chunks)
            first_embed = pager._make_embed()

            await interaction.response.send_message(embed=first_embed, view=pager, ephemeral=True)
        except FileNotFoundError:
            await interaction.response.send_message("❌ `sessions.csv` file not found.", ephemeral=True)
        except Exception as error:
            await interaction.response.send_message(f"❌ Error: {error}", ephemeral=True)
        await log_action(self.bot, interaction)

async def setup(bot: commands.Bot):
    """Load the Admin cog into the two guilds it serves."""
    guild1 = discord.Object(id=LOG_GUILD_ID)
    guild2 = discord.Object(id=576590416296542249)
    await bot.add_cog(Admin(bot), guilds=[guild1, guild2])
