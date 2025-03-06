import discord
from discord.ext import commands
from discord import app_commands
import random
import re
import math
import math
from core.logger import log_action

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="randnum", description="Generate a random number between a given range.")
    async def randnum(self, interaction: discord.Interaction, min_num: int, max_num: int):
        if min_num > max_num:
            await interaction.response.send_message("❌ The minimum number cannot be greater than the maximum number.", ephemeral=True)
            return

        result = random.randint(min_num, max_num)
        await interaction.response.send_message(f"🎲 Random number between {min_num} and {max_num}: **{result}**")
        await log_action(self.bot, interaction)

    @app_commands.command(name="math", description="Solve a math expression.")
    async def math(self, interaction: discord.Interaction, expression: str):
        """Evaluates a math expression safely."""
        try:
            # Allow only safe mathematical functions and numbers
            allowed_names = {name: getattr(math, name) for name in dir(math) if not name.startswith("__")}
            allowed_names.update({"abs": abs, "round": round})  # Add extra safe functions
            
            # Evaluate the expression safely
            result = eval(expression, {"__builtins__": {}}, allowed_names)
            await interaction.response.send_message(f"🧮 Result of `{expression}`: **{result}**")
        except Exception:
            if expression == "0/0":
                await interaction.response.send_message("🍪 Imagine that you have zero cookies and you split them evenly among zero friends.\nHow many cookies does each person get?\nYou see, it doesn't make sense. Cookie Monster is sad that there are no cookies, and you are sad that you have no friends.")
            else:
                await interaction.response.send_message("❌ Invalid mathematical expression.", ephemeral=True)
        await log_action(self.bot, interaction)
    
    @app_commands.command(name="roll", description="Roll dice in the format XdY (e.g., /roll 4d8 or /roll d20).")
    async def roll(self, interaction: discord.Interaction, dice: str):
        match = re.fullmatch(r'(\d*)d(\d+)', dice.strip())
        if not match:
            await interaction.response.send_message("❌ Invalid format! Use XdY (e.g., 4d8 or d20).", ephemeral=True)
            return

        num_dice = int(match.group(1)) if match.group(1) else 1
        num_sides = int(match.group(2))

        if num_dice <= 0 or num_sides <= 0:
            await interaction.response.send_message("❌ The number of dice and sides must be positive integers.", ephemeral=True)
            return
        
        if num_dice > 100 or num_sides > 100:
            await interaction.response.send_message("❌ The number of dice and sides must be 100 or less.", ephemeral=True)

        # Roll the dice and calculate results
        rolls = [random.randint(1, num_sides) for _ in range(num_dice)]
        total = sum(rolls)

        # Prepare response message
        roll_results = "\n".join([f"Dice {i + 1}: {roll}" for i, roll in enumerate(rolls)])
        response = f"{roll_results}\n**Total:** {total}"

        await interaction.response.send_message(f"🎲 Rolling {num_dice}d{num_sides}:\n{response}")
        await log_action(self.bot, interaction)

    @app_commands.command(name="ytimg", description="Get the thumbnail image of a YouTube video.")
    async def ytimg(self, interaction: discord.Interaction, link_or_id: str):
        # Regular expression patterns to extract video ID
        yt_patterns = [
            r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([\w-]+)",  # YouTube long/shorts links
            r"(?:https?://)?(?:www\.)?youtube\.com/embed/([\w-]+)",  # Embedded video link
            r"^[\w-]{11}$"  # Direct video ID
        ]

        video_id = None
        for pattern in yt_patterns:
            match = re.search(pattern, link_or_id)
            if match:
                video_id = match.group(1)
                break

        if not video_id:
            await interaction.response.send_message("❌ Invalid YouTube link or ID. Please provide a valid one.", ephemeral=True)
            return

        # Construct the thumbnail URL
        thumbnail_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
        embed = discord.Embed(title="🎬 YouTube Video Thumbnail", color=discord.Color.red())
        embed.set_image(url=thumbnail_url)
        embed.add_field(name="Video ID", value=video_id, inline=False)
        embed.add_field(name="Direct Link", value=f"[Click here]({thumbnail_url})", inline=False)

        await interaction.response.send_message(embed=embed)
        await log_action(self.bot, interaction)

    @app_commands.command(name="say", description="Make the bot repeat what you say.")
    async def say(self, interaction: discord.Interaction, message: str):
        """Repeats what the user says without replying directly."""
        await interaction.response.send_message("Processing...", delete_after=1)
        await interaction.channel.send(message.replace("\\\\n", "\n"))
        await log_action(self.bot, interaction)

async def setup(bot):
    await bot.add_cog(Utility(bot))
