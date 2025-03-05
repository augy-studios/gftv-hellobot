import discord
from discord.ext import commands
from discord import app_commands
import random
import re
import requests
import math
from PIL import Image, ImageDraw
import io
import math
from core.logger import log_action

def blend(color1, color2, ratio):
    """
    Blend two RGB colours.
    'ratio' is the weight for color1 (0.0 to 1.0); color2 gets (1 - ratio).
    """
    return (
        int(ratio * color1[0] + (1 - ratio) * color2[0]),
        int(ratio * color1[1] + (1 - ratio) * color2[1]),
        int(ratio * color1[2] + (1 - ratio) * color2[2])
    )

def color_from_name(name):
    """
    Return an RGB tuple for a given basic colour name.
    Defaults to blue if the name isn’t found.
    """
    colors = {
        'red': (255, 0, 0),
        'green': (0, 255, 0),
        'blue': (0, 0, 255),
        'yellow': (255, 255, 0),
        'purple': (128, 0, 128),
        'orange': (255, 165, 0),
        'pink': (255, 192, 203),
        'cyan': (0, 255, 255),
        'magenta': (255, 0, 255),
    }
    return colors.get(name.lower(), (0, 0, 255))

def generate_waves_image(width, height, wave_amplitude, frequency, vertical_distance, color_name, overlap=False):
    """
    Create an image with a series of sine-wave stripes.

    Parameters:
      - width, height: dimensions of the image in pixels.
      - wave_amplitude: amplitude of the sine wave (in pixels).
      - frequency: number of sine wave cycles across the image width.
      - vertical_distance: the vertical distance (in pixels) between the start of each wave.
         When overlap is False, each wave occupies its own band of this height.
         When True, the vertical offset between successive waves is reduced (here, set to half),
         so that each new wave is layered on top of the one immediately above.
      - color_name: the base colour (e.g., "blue").
      - overlap (bool): if True, waves will overlap (layered from top to bottom).
      
    Color gradient:
      - The topmost wave will be filled with a light tint,
      - The bottommost wave will be filled with a darker shade,
      - Interpolating linearly from top to bottom.
      
    Sine wave boundaries:
      Within each wave stripe, the top boundary is computed as:
          y = y_start + wave_amplitude * ((sin(2π * frequency * x/width) + 1) / 2)
      and the bottom boundary is:
          y = y_end - wave_amplitude * ((sin(2π * frequency * x/width) + 1) / 2)
      so that the sine oscillations stay confined to the stripe.
    """
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    base_color = color_from_name(color_name)
    # Define light and dark versions of the base color.
    top_color = blend((255, 255, 255), base_color, 0.25)   # light tint
    bottom_color = blend((0, 0, 0), base_color, 0.5)        # darker shade

    # When overlapping is enabled, use a smaller vertical step.
    step = vertical_distance if not overlap else vertical_distance * 0.5

    # Determine the stripe positions.
    stripes = []
    i = 0
    while True:
        y_start = i * step
        if y_start >= height:
            break
        y_end = y_start + vertical_distance
        if y_end > height:
            y_end = height
        stripes.append((y_start, y_end))
        i += 1

    num_stripes = len(stripes)
    
    # Draw each stripe. Later stripes will be drawn on top of earlier ones.
    for idx, (y_start, y_end) in enumerate(stripes):
        # t varies from 0 (top stripe) to 1 (bottom stripe) for the color gradient.
        t = idx / (num_stripes - 1) if num_stripes > 1 else 0
        row_color = blend(top_color, bottom_color, t)

        # Top boundary oscillates between y_start and y_start + wave_amplitude.
        top_boundary = [
            (x, y_start + wave_amplitude * ((math.sin(2 * math.pi * frequency * x / width) + 1) / 2))
            for x in range(width + 1)
        ]
        # Bottom boundary oscillates between y_end - wave_amplitude and y_end.
        bottom_boundary = [
            (x, y_end - wave_amplitude * ((math.sin(2 * math.pi * frequency * x / width) + 1) / 2))
            for x in range(width, -1, -1)
        ]
        polygon = top_boundary + bottom_boundary
        draw.polygon(polygon, fill=row_color)

    return img

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

    @staticmethod
    def _generate_dots_image(width: int, height: int, dot_diameter: int, num_dots: int = 1000) -> Image.Image:
        """
        Create an image with a white background and randomly placed colored dots.
        """
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        
        for _ in range(num_dots):
            # Ensure the dot fits entirely within the image boundaries.
            x = random.randint(0, width - dot_diameter)
            y = random.randint(0, height - dot_diameter)
            color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
            draw.ellipse((x, y, x + dot_diameter, y + dot_diameter), fill=color)
        
        return image

    @app_commands.command(name="dots", description="Generate an image with randomly placed colored dots.")
    async def dots(self, interaction: discord.Interaction, width: int, height: int, dot_diameter: int, num_dots: int = 1000):
        # Defer the response to allow time for image generation.
        await interaction.response.defer()
        
        # Generate the image.
        image = Utility._generate_dots_image(width, height, dot_diameter, num_dots)
        
        # Save the image to an in-memory bytes buffer.
        with io.BytesIO() as image_binary:
            image.save(image_binary, 'PNG')
            image_binary.seek(0)
            file = discord.File(fp=image_binary, filename="dots.png")
            await interaction.followup.send(file=file)
        
        await log_action(self.bot, interaction)

    @app_commands.command(name="waves", description="Generate a waves image")
    async def waves(
        self,
        interaction: discord.Interaction,
        width: int,
        height: int,
        wave_amplitude: int,
        frequency: float,
        vertical_distance: int,
        color: str,
        overlap: bool = False
    ):
        """
        Generates an image of sine-wave stripes with a gradient that goes from light (top) to dark (bottom).
        
        Parameters:
          - width: Image width in pixels.
          - height: Image height in pixels.
          - wave_amplitude: Amplitude of the wave in pixels.
          - frequency: Number of sine wave cycles across the image width.
          - vertical_distance: Vertical distance (in pixels) between the start of each wave.
          - color: Base color (e.g., blue, red, green).
          - overlap: If True, each subsequent wave is drawn with a smaller vertical offset so it overlaps (layers on top of) the previous one.
          
        Slash command usage example:
          /waves width:1920 height:1080 wave_amplitude:10 frequency:3 vertical_distance:100 color:blue overlap:true
        """
        await interaction.response.defer()
        img = generate_waves_image(width, height, wave_amplitude, frequency, vertical_distance, color, overlap)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        filename = f"waves_{width}x{height}_{wave_amplitude}_{frequency}_{vertical_distance}_{color}_{overlap}.png"
        file = discord.File(fp=buffer, filename=filename)
        await interaction.followup.send(file=file)
        await log_action(self.bot, interaction)

async def setup(bot):
    await bot.add_cog(Utility(bot))
