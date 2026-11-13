import datetime
import logging
import discord
from discord.ext import commands
from discord import app_commands
from core.logger import log_action, log_error

class Moderation(commands.Cog):
    """Moderation commands for users, messages, threads, channels and invites."""

    def __init__(self, bot):
        """Keep a reference to the bot."""
        self.bot = bot

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Answer a caller without the permission privately; log every other error, as discord.py did before this handler."""
        if not isinstance(error, app_commands.MissingPermissions):
            # With this handler in place discord.py no longer prints the traceback itself.
            logging.getLogger(__name__).error("Error in a moderation command", exc_info=error)
            await log_error(self.bot, interaction, error)
            return
        # A DM has no permissions, so it lands here too.
        missing = ", ".join(permission.replace("_", " ") for permission in error.missing_permissions)
        message = f"❌ You need the {missing} permission to use this command."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    # --- User Moderation Commands ---

    @app_commands.command(name="kick", description="Kick a user.")
    @app_commands.describe(member="The user that you want to kick", reason="The reason for the kick")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        """Kick a member, unless it is the caller, the bot or the server owner."""
        
        if member == interaction.user:
            await interaction.response.send_message("You cannot kick yourself.")
            return
        elif member == self.bot.user:
            await interaction.response.send_message("I cannot kick myself.")
            return
        elif member == interaction.guild.owner:
            await interaction.response.send_message("You cannot kick the server owner.")
            return
        
        await member.kick(reason=reason)
        await interaction.response.send_message(f"User {member.name} kicked for reason: {reason}")
        await log_action(self.bot, interaction)

    @app_commands.command(name="ban", description="Ban a user.")
    @app_commands.describe(member="The user that you want to ban", reason="The reason for the ban")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        """Ban a member, unless it is the caller, the bot or the server owner."""
        
        if member == interaction.user:
            await interaction.response.send_message("You cannot ban yourself.")
            return
        elif member == self.bot.user:
            await interaction.response.send_message("I cannot ban myself.")
            return
        elif member == interaction.guild.owner:
            await interaction.response.send_message("You cannot ban the server owner.")
            return
        
        await member.ban(reason=reason)
        await interaction.response.send_message(f"User {member.name} banned for reason: {reason}")
        await log_action(self.bot, interaction)

    @app_commands.command(name="unban", description="Unban a user.")
    @app_commands.describe(user="The user that you want to unban", reason="The reason for the unban")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user: discord.User, reason: str = "No reason provided"):
        """Unban a user who is currently banned."""
        
        # Make sure the user is on the ban list
        bans = await interaction.guild.bans()
        if not any(ban_entry.user.id == user.id for ban_entry in bans):
            await interaction.response.send_message(f"User {user.name} is not banned.")
            return
        
        await interaction.guild.unban(user, reason=reason)
        await interaction.response.send_message(f"User {user.name} unbanned for reason: {reason}")
        await log_action(self.bot, interaction)

    @app_commands.command(name="mute", description="Mute a user.")
    @app_commands.describe(member="The user that you want to mute")
    @app_commands.checks.has_permissions(mute_members=True)
    async def mute(self, interaction: discord.Interaction, member: discord.Member):
        """Server-mute a member in voice."""
        await member.edit(mute=True)        
        await interaction.response.send_message(f"User {member.name} muted.")
        await log_action(self.bot, interaction)

    @app_commands.command(name="unmute", description="Unmute a user.")
    @app_commands.describe(member="The user that you want to unmute")
    @app_commands.checks.has_permissions(mute_members=True)
    async def unmute(self, interaction: discord.Interaction, member: discord.Member):
        """Remove a member's server mute."""
        await member.edit(mute=False)
        await interaction.response.send_message(f"User {member.name} unmuted.")
        await log_action(self.bot, interaction)

    @app_commands.command(name="deafen", description="Deafen a user.")
    @app_commands.describe(member="The user that you want to")
    @app_commands.checks.has_permissions(deafen_members=True)
    async def deafen(self, interaction: discord.Interaction, member: discord.Member):
        """Server-deafen a member in voice."""
        await member.edit(deafen=True)
        await interaction.response.send_message(f"User {member.name} deafened.")
        await log_action(self.bot, interaction)

    @app_commands.command(name="undeafen", description="Undeafen a user.")
    @app_commands.describe(member="The user that you want to undeafen")
    @app_commands.checks.has_permissions(deafen_members=True)
    async def undeafen(self, interaction: discord.Interaction, member: discord.Member):
        """Remove a member's server deafen."""
        await member.edit(deafen=False)
        await interaction.response.send_message(f"User {member.name} undeafened.")
        await log_action(self.bot, interaction)

    @app_commands.command(name="timeout", description="Timeout a user.")
    @app_commands.describe(member="The user that you want to timeout", duration="The duration of the timeout in minutes")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, duration: int):
        """Time a member out for a number of minutes, unless it is the caller, the bot or the server owner."""
        
        if member == interaction.user:
            await interaction.response.send_message("You cannot timeout yourself.")
            return
        elif member == self.bot.user:
            await interaction.response.send_message("I cannot timeout myself.")
            return
        elif member == interaction.guild.owner:
            await interaction.response.send_message("You cannot timeout the server owner.")
            return
        
        await member.edit(timed_out_until=datetime.datetime.now() + datetime.timedelta(minutes=duration))
        await interaction.response.send_message(f"User {member.name} timed out for {duration} minutes.")
        await log_action(self.bot, interaction)

    @app_commands.command(name="untimeout", description="Untimeout a user.")
    @app_commands.describe(member="The user that you want to untimeout")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def untimeout(self, interaction: discord.Interaction, member: discord.Member):
        """End a member's timeout."""
        
        if member.timed_out_until is None:
            await interaction.response.send_message(f"User {member.name} is not currently timed out.")
            return
        
        await member.edit(timed_out_until=None)
        await interaction.response.send_message(f"User {member.name} untimed out.")
        await log_action(self.bot, interaction)

    @app_commands.command(name="nickname", description="Change a user's nickname.")
    @app_commands.describe(member="The user that you want to change the nickname of", nickname="The new nickname")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    async def nickname(self, interaction: discord.Interaction, member: discord.Member, nickname: str = None):
        """Change (or clear) a member's nickname."""
        await member.edit(nick=nickname)
        await interaction.response.send_message(f"User {member.name} nickname changed to: {nickname}")
        await log_action(self.bot, interaction)

    # --- Message Moderation Commands ---

    @app_commands.command(name="purge", description="Purge messages in a channel.")
    @app_commands.describe(amount="The amount of messages to purge", user="The user whose messages to purge (optional)", but_bot="Ignore messages sent by the bot (default: True)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction, amount: int, user: discord.Member = None, but_bot: bool = True):
        """Delete recent messages in this channel, optionally only those from one user."""
        def check(message):
            """Say whether a message should be purged."""
            if but_bot and message.author == self.bot.user:
                return False
            if user and message.author != user:
                return False
            return True

        # Delete the messages that pass the check, then report how many
        deleted = await interaction.channel.purge(limit=amount, check=check)
        await interaction.response.defer()
        await interaction.followup.send(f"Purged `{len(deleted)}` messages.")
        await log_action(self.bot, interaction)

    # --- Thread Moderation Commands ---

    @app_commands.command(name="thread", description="Thread Moderation Commands")
    @app_commands.checks.has_permissions(manage_threads=True)
    @app_commands.describe(options="The thread moderation setting to change", set="The value to set (if any)")
    @app_commands.choices(
        options=[
            app_commands.Choice(name="create", value="create"),
            app_commands.Choice(name="delete", value="delete"),
            app_commands.Choice(name="archive", value="archive"),
            app_commands.Choice(name="auto_archive", value="auto_archive"),
            app_commands.Choice(name="rename", value="rename"),
            app_commands.Choice(name="lock", value="lock"),
            app_commands.Choice(name="unlock", value="unlock"),
            app_commands.Choice(name="slowmode", value="slowmode"),
            app_commands.Choice(name="type", value="type"),
        ])
    async def thread(self, interaction: discord.Interaction, options: str = None, set: str = None):
        """Moderate this thread: create, delete, archive, rename, lock, slowmode and more."""
        match options:
            # No setting chosen: ask for one
            case None:
                await interaction.response.send_message("Please specify a thread moderation setting.")
            # create: start a new thread in this channel
            case "create":
                match set:
                    # No name given: ask for one
                    case None:
                        await interaction.response.send_message("Please specify a thread name.")
                    # Create the thread and confirm
                    case _:
                        thread = await interaction.channel.create_thread(name=set)
                        await interaction.response.send_message(f"Thread {thread.name} created.")
            # delete: find a thread by its mention and delete it
            case "delete":
                match set:
                    # No thread given: ask for one
                    case None:
                        await interaction.response.send_message("Please specify a thread name or mention.")
                    # Look the thread up, then delete it or say it was not found
                    case _:
                        thread = discord.utils.get(interaction.channel.threads, mention=set)
                        if thread:
                            await thread.delete()
                            await interaction.response.send_message(f"Thread `{thread.name}` deleted.")
                        else:
                            await interaction.response.send_message(f"Thread `{set}` not found.")
            # archive: archive this thread, or unarchive it when the value is false
            case "archive":
                match set:
                    # No value: archive the thread
                    case None:
                        await interaction.channel.edit(archived=True)
                        await interaction.response.send_message("Channel archived.")
                    # false: unarchive the thread
                    case "false":
                        await interaction.channel.edit(archived=False)
                        await interaction.response.send_message("Channel unarchived.")
            # auto_archive: show or change the auto-archive duration
            case "auto_archive":
                match set:
                    # No value: show the current duration
                    case None:
                        current_auto_archive = interaction.channel.auto_archive_duration
                        await interaction.response.send_message(f"Channel auto archive duration: {current_auto_archive} minutes")
                    # false: switch auto-archive off
                    case "false":
                        await interaction.channel.edit(auto_archive_duration=0)
                        await interaction.response.send_message("Channel auto archive duration disabled.")
                    # Any other value: set the duration in minutes
                    case _:
                        await interaction.channel.edit(auto_archive_duration=int(set))
                        await interaction.response.send_message(f"Channel auto archive duration set to {set} minutes.")
            # rename: rename this thread
            case "rename":
                match set:
                    # No name given: ask for one
                    case None:
                        await interaction.response.send_message("Please specify a thread name.")
                    # Rename the thread and confirm
                    case _:
                        await interaction.channel.edit(name=set)
                        await interaction.response.send_message(f"Thread renamed to {set}.")
            # lock: lock this thread
            case "lock":
                await interaction.channel.edit(locked=True)
                await interaction.response.send_message("Channel locked.")
            # unlock: unlock this thread
            case "unlock":
                await interaction.channel.edit(locked=False)
                await interaction.response.send_message("Channel unlocked.")
            # slowmode: show or change the slowmode delay
            case "slowmode":
                match set:
                    # No value: show the current delay
                    case None:
                        current_slowmode = interaction.channel.slowmode_delay
                        await interaction.response.send_message(f"Channel slowmode: {current_slowmode} seconds")
                    # false: switch slowmode off
                    case "false":
                        await interaction.channel.edit(slowmode_delay=0)
                        await interaction.response.send_message("Slowmode disabled.")
                    # Any other value: set the delay in seconds
                    case _:
                        await interaction.channel.edit(slowmode_delay=int(set))
                        await interaction.response.send_message(f"Slowmode set to {set} seconds.")
            # type: show the channel type
            case "type":
                current_type = interaction.channel.type
                await interaction.response.send_message(f"Channel type: {current_type}")
        await log_action(self.bot, interaction)

    # --- Channel Moderation Commands ---

    @app_commands.command(name="channel", description="Channel Moderation Commands")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(options="The channel moderation setting to change", set="The value to set (if any)")
    @app_commands.choices(
        options=[
            app_commands.Choice(name="lock", value="lock"),
            app_commands.Choice(name="unlock", value="unlock"),
            app_commands.Choice(name="private", value="private"),
            app_commands.Choice(name="public", value="public"),
            app_commands.Choice(name="slowmode", value="slowmode"),
            app_commands.Choice(name="delete", value="delete"),
            app_commands.Choice(name="rename", value="rename"),
            app_commands.Choice(name="topic", value="topic"),
            app_commands.Choice(name="nsfw", value="nsfw"),
            app_commands.Choice(name="position", value="position"),
            app_commands.Choice(name="type", value="type"),
            app_commands.Choice(name="invite_links", value="invite_links"),
        ])
    async def channel(self, interaction: discord.Interaction, options: str = None, set: str = None):
        """Moderate this channel: lock, privacy, slowmode, rename, topic, NSFW, position, type and invites."""
        match options:
            # No setting chosen: ask for one
            case None:
                await interaction.response.send_message("Please specify a channel moderation setting.")
            # lock: stop @everyone from sending messages
            case "lock":
                await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
                await interaction.response.send_message("Channel locked.")
            # unlock: let @everyone send messages again
            case "unlock":
                await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
                await interaction.response.send_message("Channel unlocked.")
            # private: hide the channel from @everyone
            case "private":
                await interaction.channel.set_permissions(interaction.guild.default_role, view_channel=False)
                await interaction.response.send_message("Channel set to private.")
            # public: show the channel to @everyone
            case "public":
                await interaction.channel.set_permissions(interaction.guild.default_role, view_channel=True)
                await interaction.response.send_message("Channel set to public.")
            # slowmode: show or change the slowmode delay
            case "slowmode":
                match set:
                    # No value: show the current delay
                    case None:
                        current_slowmode = interaction.channel.slowmode_delay
                        await interaction.response.send_message(f"Channel slowmode: {current_slowmode} seconds")
                    # false: switch slowmode off
                    case "false":
                        await interaction.channel.edit(slowmode_delay=0)
                        await interaction.response.send_message("Slowmode disabled.")
                    # Any other value: set the delay in seconds
                    case _:
                        await interaction.channel.edit(slowmode_delay=int(set))
                        await interaction.response.send_message(f"Slowmode set to {set} seconds.")
            # delete: find a channel by its mention and delete it
            case "delete":
                match set:
                    # No channel given: ask for one
                    case None:
                        await interaction.response.send_message("Please specify a channel name or mention.")
                    # Look the channel up, then delete it or say it was not found
                    case _:
                        channel = discord.utils.get(interaction.guild.channels, mention=set)
                        if channel:
                            await channel.delete()
                            await interaction.response.send_message(f"Channel `#{channel.name}` deleted.")
                        else:
                            await interaction.response.send_message(f"Channel `{set}` not found.")
            # rename: rename this channel
            case "rename":
                match set:
                    # No name given: ask for one
                    case None:
                        await interaction.response.send_message("Please specify a channel name.")
                    # Rename the channel and confirm
                    case _:
                        await interaction.channel.edit(name=set)
                        await interaction.response.send_message(f"Channel renamed to {set}.")
            # topic: show or change the channel topic
            case "topic":
                match set:
                    # No value: show the current topic
                    case None:
                        current_topic = interaction.channel.topic
                        await interaction.response.send_message(f"Channel topic: {current_topic}")
                    # Any other value: set the topic
                    case _:
                        await interaction.channel.edit(topic=set)
                        await interaction.response.send_message(f"Channel topic set to: {set}")
            # nsfw: show or change the NSFW setting
            case "nsfw":
                match set:
                    # No value: show the current setting
                    case None:
                        current_nsfw = interaction.channel.is_nsfw()
                        await interaction.response.send_message(f"Channel NSFW setting: {current_nsfw}")
                    # true: mark the channel NSFW
                    case "true":
                        await interaction.channel.edit(nsfw=True)
                        await interaction.response.send_message("Channel set to NSFW.")
                    # false: mark the channel SFW
                    case "false":
                        await interaction.channel.edit(nsfw=False)
                        await interaction.response.send_message("Channel set to SFW.")
            # position: show or move the channel position
            case "position":
                match set:
                    # No value: show the current position
                    case None:
                        current_position = interaction.channel.position
                        await interaction.response.send_message(f"Channel position: {current_position}")
                    # up: move the channel up one place
                    case "up":
                        await interaction.channel.edit(position=interaction.channel.position - 1)
                        await interaction.response.send_message("Channel moved up.")
                    # down: move the channel down one place
                    case "down":
                        await interaction.channel.edit(position=interaction.channel.position + 2)
                        await interaction.response.send_message("Channel moved down.")
            # type: show or change the channel type
            case "type":
                match set:
                    # No value: show the current type
                    case None:
                        current_type = interaction.channel.type
                        await interaction.response.send_message(f"Channel type: {current_type}")
                    # text: make it a text channel
                    case "text":
                        await interaction.channel.edit(type=discord.ChannelType.text)
                        await interaction.response.send_message("Channel type set to text.")
                    # announcement: make it an announcement (news) channel
                    case "announcement":
                        await interaction.channel.edit(type=discord.ChannelType.news)
                        await interaction.response.send_message("Channel type set to news.")
            # invite_links: list the invite links for this channel
            case "invite_links":
                invites = await interaction.channel.invites()
                if invites:
                    # Build one line per invite: its link and who created it
                    invite_links = "\n".join([f"{invite.url} (created by {invite.inviter})" for invite in invites])
                    await interaction.response.send_message(f"**Current invite links**:\n`{invite_links}`")
                else:
                    await interaction.response.send_message("No invite links found for this channel.")
        await log_action(self.bot, interaction)

    # --- Invite Moderation Commands ---

    @app_commands.command(name="invite", description="Invite Moderation Commands")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(options="The invite moderation setting to change", set="The value to set (if any)")
    @app_commands.choices(
        options=[
            app_commands.Choice(name="list", value="list"),
            app_commands.Choice(name="create", value="create"),
            app_commands.Choice(name="delete", value="delete"),
        ])
    async def invite(self, interaction: discord.Interaction, options: str = None, set: str = None):
        """List, create or delete server invite links."""
        match options:
            # No setting chosen: ask for one
            case None:
                await interaction.response.send_message("Please specify an invite moderation setting.")
            # list: list invite links for this server, or for the server whose ID is given
            case "list":
                if set:
                    guild = interaction.client.get_guild(int(set))
                    if not guild:
                        await interaction.response.send_message("Invalid server ID.", ephemeral=True)
                        return
                else:
                    guild = interaction.guild

                invites = await guild.invites()
                if invites:
                    # Build one line per invite: its link, who created it and its channel
                    invite_links = "\n".join([f"{invite.url} (created by {invite.inviter} for #{invite.channel})" for invite in invites])
                    await interaction.response.send_message(f"**Current invite links**:\n```{invite_links}```", embed=None)
                else:
                    await interaction.response.send_message("No invite links found for this server.")
            # create: create a new invite link for this channel
            case "create":
                invite = await interaction.channel.create_invite(reason="Invite created by command")
                await interaction.response.send_message(f"New Invite link: {invite.url}")
            # delete: find an invite by its code and delete it
            case "delete":
                match set:
                    # No code given: ask for one
                    case None:
                        await interaction.response.send_message("Please specify an invite link to delete.")
                    # Look the invite up, then delete it or say it was not found
                    case _:
                        invite = discord.utils.get(await interaction.guild.invites(), code=set)
                        if invite:
                            await invite.delete(reason=f"Invite deleted by {interaction.user.name}")
                            await interaction.response.send_message(f"Invite link `{set}` deleted.")
                        else:
                            await interaction.response.send_message("Invite link not found.")
        await log_action(self.bot, interaction)

    # --- Creation Commands ---

    @app_commands.command(name="create_channel", description="Create a new channel.")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(type="The type of the new channel", name="The name of the new channel")
    @app_commands.choices(
        type=[
            app_commands.Choice(name="text", value="text"),
            app_commands.Choice(name="voice", value="voice"),
            app_commands.Choice(name="announcement", value="announcement"),
            app_commands.Choice(name="forum", value="forum"),
            app_commands.Choice(name="stage", value="stage"),
        ])
    async def create_channel(self, interaction: discord.Interaction, type: str, name: str = None):
        """Create a new channel of the chosen type."""
        guild = interaction.guild
        # A name is required
        if name == None:
            await interaction.response.send_message(f"Please specify a channel name.")
            return
        # Create the channel of the chosen type
        match type:
            # text channel
            case "text":
                channel = await guild.create_text_channel(name)
            # voice channel
            case "voice":
                channel = await guild.create_voice_channel(name)
            # announcement (news) channel
            case "announcement":
                channel = await guild.create_text_channel(name, type=discord.ChannelType.news)
            # forum channel
            case "forum":
                channel = await guild.create_text_channel(name, type=discord.ChannelType.forum)
            # stage channel
            case "stage":
                channel = await guild.create_stage_channel(name)
        await interaction.response.send_message(f"Channel <#{channel.id}> created.")
        await log_action(self.bot, interaction)

async def setup(bot):
    """Load the Moderation cog."""
    await bot.add_cog(Moderation(bot))
