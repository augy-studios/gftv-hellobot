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

class Generative(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @staticmethod
    def _generate_dots_image(width: int, height: int, dot_diameter: int, num_dots: int = 1000, bg_color: str = "#ffffff", overlap: bool = True) -> Image.Image:
        """
        Create an image with the specified background color and randomly placed colored dots.
        
        Parameters:
          - width, height: dimensions of the image.
          - dot_diameter: diameter of each dot.
          - num_dots: total number of dots.
          - bg_color: background color as a hex code (e.g. "#ffffff").
          - overlap: if True, dots are placed without collision checking; 
                     if False, dots are placed so they don't overlap (using a rejection method).
        """
        image = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(image)
        radius = dot_diameter / 2
        
        if overlap:
            # Simply place dots at random positions (they might overlap)
            for _ in range(num_dots):
                x = random.randint(0, width - dot_diameter)
                y = random.randint(0, height - dot_diameter)
                color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
                draw.ellipse((x, y, x + dot_diameter, y + dot_diameter), fill=color)
        else:
            # Attempt to place dots without overlapping
            placed_centers = []
            placed = 0
            attempts = 0
            max_attempts = num_dots * 100  # Prevent infinite loops if dots are too many
            while placed < num_dots and attempts < max_attempts:
                x = random.randint(0, width - dot_diameter)
                y = random.randint(0, height - dot_diameter)
                center_x = x + radius
                center_y = y + radius
                collision = False
                for (cx, cy) in placed_centers:
                    distance = math.hypot(center_x - cx, center_y - cy)
                    if distance < dot_diameter:
                        collision = True
                        break
                if not collision:
                    placed_centers.append((center_x, center_y))
                    color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
                    draw.ellipse((x, y, x + dot_diameter, y + dot_diameter), fill=color)
                    placed += 1
                attempts += 1
        
        return image

    @app_commands.command(name="dots", description="Generate an image with randomly placed colored dots.")
    async def dots(self, interaction: discord.Interaction, 
                   width: int, 
                   height: int, 
                   dot_diameter: int, 
                   num_dots: int = 1000, 
                   bg_color: str = "#ffffff", 
                   overlap: bool = True):
        """
        Generates a dots image with the provided parameters.
        
        Parameters:
          - width & height: dimensions of the image in pixels.
          - dot_diameter: diameter of each dot in pixels.
          - num_dots: number of dots to generate (default is 1000).
          - bg_color: hex color code for the background (default is "#ffffff").
          - overlap: if True, dots may overlap; if False, they will be placed without overlapping.
        """
        # Defer the response to allow for image generation time.
        await interaction.response.defer()
        
        # Generate the image.
        image = Generative._generate_dots_image(width, height, dot_diameter, num_dots, bg_color, overlap)
        
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
    await bot.add_cog(Generative(bot))
