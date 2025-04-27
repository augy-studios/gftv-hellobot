import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import yt_dlp
import os
import csv
import random
import string
from datetime import datetime
from core.logger import log_action

COOKIES_FILE = "cookies.txt"  # Path to the YouTube cookies file
QUEUE_FILE = "queue.csv"
FIELDNAMES = ['id','track_id','song_link','title','artist','requestor_userid','datetime_now']

# View for player controls during playback
class PlayerControls(discord.ui.View):
    def __init__(self, voice_cog, guild_id):
        super().__init__(timeout=None)
        self.voice_cog = voice_cog
        self.guild_id = guild_id

    @discord.ui.button(emoji="⏸️", style=discord.ButtonStyle.primary, custom_id="play_pause")
    async def play_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = discord.utils.get(self.voice_cog.bot.voice_clients, guild=interaction.guild)
        if vc and vc.is_playing():
            vc.pause()
            button.emoji = "▶️"
        elif vc and vc.is_paused():
            vc.resume()
            button.emoji = "⏸️"
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji="🔄", style=discord.ButtonStyle.secondary, custom_id="restart")
    async def restart(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Restart the currently playing track from the beginning."""
        await interaction.response.defer()
        await self.voice_cog._restart_current(interaction)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger, custom_id="stop")
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Stop playback and safely log the action."""
        vc = discord.utils.get(self.voice_cog.bot.voice_clients, guild=interaction.guild)
        if vc:
            vc.stop()
        await interaction.response.defer()

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.danger, custom_id="loop")
    async def loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = not self.voice_cog.looping.get(self.guild_id, False)
        self.voice_cog.looping[self.guild_id] = state
        button.style = discord.ButtonStyle.success if state else discord.ButtonStyle.danger
        await interaction.response.edit_message(view=self)

# View for queue pagination
class QueueView(discord.ui.View):
    def __init__(self, pages):
        super().__init__(timeout=60)
        self.pages = pages
        self.current = 0
        self.total = len(pages)
        # disable prev on first page
        self.prev.disabled = True
        # set page label
        self.page.label = f"{self.current+1}/{self.total}"
        if self.total <= 1:
            self.next.disabled = True

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary, custom_id="queue_prev")
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current -= 1
        self.prev.disabled = (self.current == 0)
        self.next.disabled = False
        self.page.label = f"{self.current+1}/{self.total}"
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    @discord.ui.button(label="1/1", style=discord.ButtonStyle.secondary, disabled=True, custom_id="queue_page")
    async def page(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, custom_id="queue_next")
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current += 1
        self.prev.disabled = False
        self.next.disabled = (self.current == self.total - 1)
        self.page.label = f"{self.current+1}/{self.total}"
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_clients = {}
        self.looping = {}  # Dictionary to track looping state per guild
        self.history = {}
        # ensure queue file exists with header
        if not os.path.exists(QUEUE_FILE):
            with open(QUEUE_FILE, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(FIELDNAMES)

    def generate_track_id(self):
        existing = set()
        with open(QUEUE_FILE, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing.add(row['track_id'])
        while True:
            tid = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
            if tid not in existing:
                return tid

    def add_to_queue(self, track):
        """
        Append a track dict to the CSV, aligned with fixed FIELDNAMES.
        """
        # Ensure all fields present (id left blank)
        row = { key: track.get(key, '') for key in FIELDNAMES }
        with open(QUEUE_FILE, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writerow(row)

    @app_commands.command(name="join", description="Join the voice channel you are currently in.")
    async def join(self, interaction: discord.Interaction):
        """Joins the voice channel the command executor is in."""
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("❌ You must be in a voice channel for me to join!", ephemeral=True)
            return

        channel = interaction.user.voice.channel
        voice_client = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)

        if voice_client and voice_client.is_connected():
            await interaction.response.send_message("✅ I am already in a voice channel.", ephemeral=True)
        else:
            await channel.connect()
            await interaction.response.send_message(f"✅ Joined {channel.name}.")
        await log_action(self.bot, interaction)

    @app_commands.command(name="leave", description="Leave the voice channel.")
    async def leave(self, interaction: discord.Interaction):
        """Leaves the voice channel the bot is currently in."""
        voice_client = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)

        if voice_client and voice_client.is_connected():
            await voice_client.disconnect()
            await interaction.response.send_message("✅ Left the voice channel.")
        else:
            await interaction.response.send_message("❌ I am not in any voice channel!", ephemeral=True)
        await log_action(self.bot, interaction)

    @app_commands.command(name="play", description="Play a track or add to queue if one is already playing.")
    @app_commands.describe(url="The URL of the audio file or stream to play.")
    async def play(self, interaction: discord.Interaction, url: str):
        # Ensure user is in voice channel
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("❌ You must be in a voice channel!", ephemeral=True)
            return
        channel = interaction.user.voice.channel
        vc = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        if not vc:
            vc = await channel.connect()

        # If already playing, enqueue immediately without deferring
        if vc.is_playing():
            # Minimal metadata; full info will display when played
            track = {
                'track_id': self.generate_track_id(),
                'song_link': url,
                'title': url,  # placeholder; actual title extracted later
                'artist': 'Unknown',
                'requestor_userid': str(interaction.user.id),
                'datetime_now': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            self.add_to_queue(track)
            await interaction.response.send_message(
                f"✅ Added to queue: **{track['title']}** (ID: {track['track_id']})",
                ephemeral=True
            )
            return

        # Not playing: defer and extract metadata for immediate play
        await interaction.response.defer()
        song_title = "Unknown Title"
        artist = "Unknown"
        audio_url = url
        try:
            if "cdn.discordapp.com" in url:
                source = discord.FFmpegPCMAudio(url, options="-vn -b:a 192k")
                song_title = "Audio File"
            else:
                ydl_opts = {'format':'bestaudio/best', 'quiet':True, 'cookies': COOKIES_FILE if os.path.exists(COOKIES_FILE) else None}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    audio_url = info['url']
                    song_title = info.get('title', song_title)
                    artist = info.get('uploader', artist)
                    source = discord.FFmpegPCMAudio(audio_url, options="-vn -b:a 192k")
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to extract audio: {e}", ephemeral=True)
            return

        # Build track dict
        track = {
            'track_id': self.generate_track_id(),
            'song_link': url,
            'title': song_title,
            'artist': artist,
            'requestor_userid': str(interaction.user.id),
            'datetime_now': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        await self.play_track(track, interaction)
        await log_action(self.bot, interaction)

    async def play_track(self, track, interaction):
        guild_id = interaction.guild.id
        # track history
        self.history.setdefault(guild_id, []).append(track)

        # get or reconnect voice client
        vc = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        # If not connected, try reconnecting to user's channel
        if not vc or not vc.is_connected():
            # fall back to last-known voice channel of user
            if interaction.user.voice and interaction.user.voice.channel:
                vc = await interaction.user.voice.channel.connect()
            else:
                # no channel available
                await interaction.followup.send("❌ Unable to join voice channel.", ephemeral=True)
                return

        # prepare source
        source = None
        url = track['song_link']
        if "cdn.discordapp.com" in url:
            source = discord.FFmpegPCMAudio(url, options="-vn -b:a 192k")
        else:
            ydl_opts = {'format':'bestaudio/best', 'quiet':True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                source_url = info.get('url')
                source = discord.FFmpegPCMAudio(source_url, options="-vn -b:a 192k")

        def after_play(error):
            if error:
                # we got here because vc.stop() was called (e.g. manual skip),
                # so don’t auto-schedule another play
                print(f"Playback stopped with error (or manual skip): {error}")
                return
            
            # only schedule auto-next when the track really finishes
            coro = self._play_next(interaction)
            asyncio.run_coroutine_threadsafe(coro, self.bot.loop)

        # play audio
        vc.play(source, after=after_play)

        # send now playing embed
        embed = discord.Embed(title="Now Playing", description=f"**{track['title']}** by *{track['artist']}*")
        embed.set_footer(text=f"Requested by {interaction.user.display_name} • {track['datetime_now']}")
        view = PlayerControls(self, guild_id)
        await interaction.followup.send(embed=embed, view=view)

    async def _play_next(self, interaction: discord.Interaction):
        """
        Play next track in queue (looping handled separately).
        """
        guild_id = interaction.guild.id
        # handle looping option
        if self.looping.get(guild_id, False):
            last = self.history.get(guild_id, [])[-1]
            return await self.play_track(last, interaction)

        # read queue file
        with open(QUEUE_FILE, newline='') as f:
            rows = list(csv.DictReader(f))

        if not rows:
            await interaction.channel.send("✅ Queue is empty.")
            return

        # pop the next track and rewrite queue without it
        next_track = rows.pop(0)
        with open(QUEUE_FILE, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)

        # play the next track
        await self.play_track(next_track, interaction)

    async def _play_previous(self, interaction):
        hist = self.history.get(interaction.guild.id, [])
        if len(hist) < 2:
            await interaction.response.send_message("❌ No previous track.", ephemeral=True)
            return
        prev_track = hist[-2]
        await self.play_track(prev_track, interaction)

    async def _send_queue_pages(self, interaction: discord.Interaction):
        """
        Helper to load queue.csv, build paginated embeds, and send a /queue show response.
        """
        # Load queue rows
        with open(QUEUE_FILE, newline='') as f:
            rows = list(csv.DictReader(f))

        # Empty queue
        if not rows:
            await interaction.response.send_message("✅ Queue is empty.")
            return

        # Build embed pages
        pages = []
        per_page = 5
        for i in range(0, len(rows), per_page):
            embed = discord.Embed(title="Current Queue")
            for idx, row in enumerate(rows[i:i+per_page], start=i+1):
                # Resolve requestor display name
                member = interaction.guild.get_member(int(row['requestor_userid']))
                if member:
                    requester = member.display_name
                else:
                    user = await self.bot.fetch_user(int(row['requestor_userid']))
                    requester = user.name

                embed.add_field(
                    name=f"{idx}. {row['title']}",
                    value=(
                        f"Artist: {row['artist']}\n"
                        f"Requested by {requester}\n"
                        f"ID: `{row['track_id']}`"
                    ),
                    inline=False
                )
            pages.append(embed)

        # Send first page (with pagination if needed)
        if len(pages) == 1:
            await interaction.response.send_message(embed=pages[0])
        else:
            view = QueueView(pages)
            await interaction.response.send_message(embed=pages[0], view=view)
    
    async def _restart_current(self, interaction: discord.Interaction):
        """Stop and replay the currently playing track from the beginning."""
        guild_id = interaction.guild.id
        vc = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        # Get last-played track from history
        history = self.history.get(guild_id, [])
        if not history or not vc:
            await interaction.followup.send("❌ No track is currently playing.", ephemeral=True)
            return
        current = history[-1]
        # Stop current playback and restart
        vc.stop()
        await self.play_track(current, interaction)

    @app_commands.command(name="playing", description="Show info about the currently playing track.")
    async def playing(self, interaction: discord.Interaction):
        """
        Reports the currently playing track from history, or a message if nothing is playing.
        """
        # Find voice client for this guild
        vc = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        # Check if there's active playback
        if not vc or (not vc.is_playing() and not vc.is_paused()):
            await interaction.response.send_message("❌ Nothing is playing right now.", ephemeral=True)
            return

        # Get the last track from history
        guild_id = interaction.guild.id
        history = self.history.get(guild_id, [])
        if not history:
            await interaction.response.send_message("❌ Nothing is playing right now.", ephemeral=True)
            return
        current = history[-1]

        # Resolve requester name
        try:
            member = interaction.guild.get_member(int(current['requestor_userid']))
            if member:
                requester = member.display_name
            else:
                user = await self.bot.fetch_user(int(current['requestor_userid']))
                requester = user.name
        except Exception:
            requester = "Unknown"

        # Build and send embed
        embed = discord.Embed(
            title="Now Playing",
            description=f"**{current['title']}** by *{current['artist']}*"
        )
        embed.add_field(name="Link", value=current['song_link'], inline=False)
        embed.set_footer(text=f"Requested by {requester} • {current['datetime_now']}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="skip", description="Skip to the next track in the queue.")
    async def skip(self, interaction: discord.Interaction):
        """Stops current playback and plays the next queued track."""
        await interaction.response.defer()
        vc = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
        await self._play_next(interaction)
        await log_action(self.bot, interaction)

    queue = app_commands.Group(name="queue", description="View and manage the playback queue.")

    @queue.command(name="show", description="Show the current queue.")
    async def queue_show(self, interaction: discord.Interaction):
        await self._send_queue_pages(interaction)
        await log_action(self.bot, interaction)

    @queue.command(name="clear", description="Clear the entire queue.")
    async def queue_clear(self, interaction: discord.Interaction):
        # reset queue file with only header
        with open(QUEUE_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['id','track_id','song_link','title','artist','requestor_userid','datetime_now'])
        await interaction.response.send_message("✅ Queue cleared.")
        await log_action(self.bot, interaction)

    @queue.command(name="remove", description="Remove a specific track from the queue.")
    @app_commands.describe(track_id="The ID of the track to remove.")
    async def queue_remove(self, interaction: discord.Interaction, track_id: str):
        with open(QUEUE_FILE, newline='') as f:
            rows = list(csv.DictReader(f))
        filtered = [r for r in rows if r['track_id'] != track_id]
        if len(filtered) == len(rows):
            await interaction.response.send_message(f"❌ No track with ID `{track_id}` found.", ephemeral=True)
            return
        with open(QUEUE_FILE, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(filtered)
        await interaction.response.send_message(f"✅ Removed track `{track_id}` from the queue.")
        await log_action(self.bot, interaction)

    @queue.command(name="bump", description="Move a specific track to the top of the queue.")
    @app_commands.describe(track_id="The ID of the track to bump.")
    async def queue_bump(self, interaction: discord.Interaction, track_id: str):
        with open(QUEUE_FILE, newline='') as f:
            rows = list(csv.DictReader(f))
        for idx, r in enumerate(rows):
            if r['track_id'] == track_id:
                track = rows.pop(idx)
                rows.insert(0, track)
                break
        else:
            await interaction.response.send_message(f"❌ No track with ID `{track_id}` found.", ephemeral=True)
            return
        with open(QUEUE_FILE, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        await interaction.response.send_message(f"✅ Bumped track `{track_id}` to the top of the queue.")
        await log_action(self.bot, interaction)

    @app_commands.command(name="pause", description="Pause the currently playing track.")
    async def pause(self, interaction: discord.Interaction):
        """Pauses the track currently being played."""
        voice_client = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        if voice_client and voice_client.is_playing():
            voice_client.pause()
            await interaction.response.send_message("⏸️ Music paused.")
        else:
            await interaction.response.send_message("❌ No track is currently playing.", ephemeral=True)
        await log_action(self.bot, interaction)

    @app_commands.command(name="resume", description="Resume the currently paused track.")
    async def resume(self, interaction: discord.Interaction):
        """Resumes a paused track."""
        voice_client = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        if voice_client and voice_client.is_paused():
            voice_client.resume()
            await interaction.response.send_message("▶️ Music resumed.")
        else:
            await interaction.response.send_message("❌ No track is currently paused.", ephemeral=True)
        await log_action(self.bot, interaction)

    @app_commands.command(name="loop", description="Toggle looping for the currently playing track.")
    @app_commands.describe(toggle="Toggle looping on or off")
    @app_commands.choices(toggle=[
        app_commands.Choice(name="on", value="on"),
        app_commands.Choice(name="off", value="off")
    ])
    async def loop(self, interaction: discord.Interaction, toggle: str):
        """Toggles looping for the current track."""
        guild_id = interaction.guild.id

        if toggle == "on":
            self.looping[guild_id] = True
            await interaction.response.send_message("🔁 Looping is now **enabled**.")
        else:
            self.looping[guild_id] = False
            await interaction.response.send_message("🔁 Looping is now **disabled**.")
        await log_action(self.bot, interaction)
    
    @app_commands.command(name="stop", description="Stop the currently playing track.")
    async def stop(self, interaction: discord.Interaction):
        """Stops the track currently being played."""
        voice_client = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        guild_id = interaction.guild.id
        if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
            self.looping[guild_id] = False  # Disable looping when stopping
            voice_client.stop()
            await interaction.response.send_message("⏹️ Music stopped.")
        else:
            await interaction.response.send_message("❌ No track is currently playing.", ephemeral=True)
        await log_action(self.bot, interaction)

async def setup(bot):
    await bot.add_cog(Voice(bot))
