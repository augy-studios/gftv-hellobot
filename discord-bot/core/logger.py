"""Logging of command use and errors to the bot's log channel."""
import os
import discord
from discord.ext.commands import CommandInvokeError, CommandNotFound
from dotenv import load_dotenv

# Load environment variables from token.env
load_dotenv("token.env")
LOG_GUILD_ID = int(os.getenv("LOG_GUILD_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))


def find_log_channel(bot):
    """Return the log channel, or None (after printing why) if the guild or channel is missing."""
    guild = bot.get_guild(LOG_GUILD_ID)
    if guild is None:
        print("Log guild not found.")
        return None

    log_channel = guild.get_channel(LOG_CHANNEL_ID)
    if log_channel is None:
        print("Log channel not found.")
        return None
    return log_channel


def add_interaction_fields(embed, interaction):
    """Add the User, Server and Channel fields of an interaction to a log embed."""
    embed.add_field(name="User", value=f"{interaction.user} (ID: {interaction.user.id})", inline=True)
    embed.add_field(name="Server", value=f"{interaction.guild.name} (ID: {interaction.guild.id})", inline=True)
    embed.add_field(name="Channel", value=f"{interaction.channel.name} (ID: {interaction.channel.id})", inline=True)


async def log_action(bot, interaction):
    """Post a "Message Log" embed for a command that was just used."""
    log_channel = find_log_channel(bot)
    if log_channel is None:
        return

    embed = discord.Embed(
        title="Message Log",
        description=f"Command: {interaction.command.name} | [Message Link](https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.id})",
        color=discord.Color(0x99ff99),
    )
    add_interaction_fields(embed, interaction)

    await log_channel.send(embed=embed)


async def log_error(bot, interaction, error):
    """Post an "Error Log" embed for a command that failed."""
    log_channel = find_log_channel(bot)
    if log_channel is None:
        return
    embed = discord.Embed(
        title="Error Log",
        description=f"An error occurred during command execution: {interaction.command.name}",
        color=discord.Color.red(),
    )
    add_interaction_fields(embed, interaction)
    embed.add_field(name="Error", value=str(error), inline=False)
    await log_channel.send(embed=embed)


def setup_error_handling(bot):
    """Attach the on_command_error handler that sends command errors to the log channel."""
    @bot.event
    async def on_command_error(context, error):
        """Log command errors, ignoring commands that don't exist."""
        if isinstance(error, CommandNotFound):
            # Ignore missing commands to avoid unnecessary logs
            return
        elif isinstance(error, CommandInvokeError):
            await log_error(bot, context.interaction, error)
        else:
            await log_error(bot, context.interaction, error)  # Handle generic errors
