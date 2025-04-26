import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import yt_dlp
import os
from core.logger import log_action

COOKIES_FILE = "cookies.txt"  # Path to the YouTube cookies file

class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_clients = {}
        self.looping = {}  # Dictionary to track looping state per guild
        self.current_audio_file = {}  # Track the currently playing file per guild

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

    @app_commands.command(name="play", description="Play a track in the voice channel. Discord audio file link and Soundcloud links only.")
    @app_commands.describe(url="The URL of the audio file to play")
    async def play(self, interaction: discord.Interaction, url: str):
        """Plays a track in a voice channel."""
        # Ensure user is in a voice channel
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("❌ You must be in a voice channel for me to play music!", ephemeral=True)
            return

        channel = interaction.user.voice.channel
        voice_client = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)

        if not voice_client:
            voice_client = await channel.connect()

        if voice_client.is_playing():
            await interaction.response.send_message("❌ I am already playing music!", ephemeral=True)
            return
        
        if "youtube.com" in url or "youtu.be" in url:
            await interaction.response.send_message("❌ YouTube links are not supported. Please use a Discord audio file link, Soundcloud link, or BiliBili link.", ephemeral=True)
            return

        # Defer the initial response to allow followup messages
        await interaction.response.defer()

        # Prepare the audio source
        if "cdn.discordapp.com" in url:
            audio_source = discord.FFmpegPCMAudio(url, options="-vn -b:a 192k")
            song_title = "Audio File from Discord"
            audio_file = None
        else:
            # Use yt-dlp to download audio and set title to original filename
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': '%(title)s.%(ext)s',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'm4a',
                    'preferredquality': '320'  # Set high audio quality
                }],
                'quiet': True,
                'cookies': COOKIES_FILE if os.path.exists(COOKIES_FILE) else None  # Use cookies if available
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info).rsplit(".", 1)[0]  # Extract the base filename without extension
                    audio_file = f"{filename}.m4a"
                    song_title = filename.replace("_", " ")  # Replace underscores with spaces
                    audio_source = discord.FFmpegPCMAudio(f"{filename}.m4a", options="-vn -b:a 320k")  # High-quality FFmpeg playback
                    self.current_audio_file[interaction.guild.id] = audio_file  # Track current file
                except Exception as e:
                    await interaction.followup.send(f"❌ Failed to download audio: {str(e)}", ephemeral=True)
                    return

        # Play and notify
        def after_playing(error):
            if error:
                print(f"Error playing track: {error}")
            asyncio.run_coroutine_threadsafe(
                interaction.followup.send("✅ Finished playing the track."),
                self.bot.loop
            )

        voice_client.play(audio_source, after=after_playing)
        await interaction.followup.send(f"🎵 Now playing: `{song_title}`")

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
