import re
import discord
from discord.ext import commands
from discord import app_commands
import random
import math
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
from skimage.metrics import structural_similarity as compare_ssim
import io
import math
import numpy as np
import pandas as pd
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
    Defaults to blue if the name isn't found.
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
    if color_name.lower() == "augy":
        base_color = (153, 255, 153)  # Augy green in RGB
    else:
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
    @app_commands.describe(
        width="Width of the image in pixels",
        height="Height of the image in pixels",
        dot_diameter="Diameter of each dot in pixels",
        num_dots="Number of dots to generate (default is 1000)",
        bg_color="Background color as a hex code (default is #ffffff)",
        overlap="If True, dots may overlap; if False, they will be placed without overlapping"
    )
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

        if width > 4096 or height > 4096:
            await interaction.followup.send("Error: Image dimensions must be 4096 pixels or less.")
            return
        if width < 1 or height < 1:
            await interaction.followup.send("Error: Image dimensions must be positive.")
            return
        if dot_diameter > width or dot_diameter > height:
            await interaction.followup.send("Error: Dot diameter must be less than the image dimensions.")
            return
        if dot_diameter < 1:
            await interaction.followup.send("Error: Dot diameter must be positive.")
            return
        if num_dots < 1:
            await interaction.followup.send("Error: Number of dots must be positive.")
            return
        if num_dots > 20000:
            await interaction.followup.send("Error: Number of dots must be 20000 or less.")
            return
        if bg_color.lower() == "augy":
            bg_color = "#99FF99"  # Augy green in hex
        if not re.match(r'^#[0-9a-fA-F]{6}$', bg_color):
            await interaction.followup.send("Error: Background color must be a valid hex color code.")
            return
        
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
    @app_commands.describe(
        width="Image width in pixels",
        height="Image height in pixels",
        wave_amplitude="Amplitude of the wave in pixels",
        frequency="Number of sine wave cycles across the image width",
        vertical_distance="Vertical distance between the start of each wave in pixels",
        color="Base color (e.g., blue, red, green)",
        overlap="If True, each subsequent wave is drawn with a smaller vertical offset so it overlaps the previous one"
    )
    @app_commands.choices(color=[
        app_commands.Choice(name="Red", value="red"),
        app_commands.Choice(name="Green", value="green"),
        app_commands.Choice(name="Blue", value="blue"),
        app_commands.Choice(name="Yellow", value="yellow"),
        app_commands.Choice(name="Purple", value="purple"),
        app_commands.Choice(name="Orange", value="orange"),
        app_commands.Choice(name="Pink", value="pink"),
        app_commands.Choice(name="Cyan", value="cyan"),
        app_commands.Choice(name="Magenta", value="magenta"),
        app_commands.Choice(name="Augy Green", value="augy")
    ])
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

        if width < 1 or height < 1:
            await interaction.followup.send("Error: Image dimensions must be positive.")
            return
        if width > 4096 or height > 4096:
            await interaction.followup.send("Error: Image dimensions must be 4096 pixels or less.")
            return
        if wave_amplitude < 1:
            await interaction.followup.send("Error: Wave amplitude must be positive.")
            return
        if wave_amplitude > height:
            await interaction.followup.send("Error: Wave amplitude must be less than the image height.")
            return
        if frequency <= 0:
            await interaction.followup.send("Error: Frequency must be a positive number.")
            return
        if frequency > width/2 or frequency > height/2 or frequency > 100:
            await interaction.followup.send("Error: Frequency must be 100 or less and less than half the image dimensions.")
            return
        if vertical_distance < 1:
            await interaction.followup.send("Error: Vertical distance must be positive.")
            return
        if vertical_distance > height:
            await interaction.followup.send("Error: Vertical distance must be less than the image height.")
            return
        if not re.match(r'^[a-zA-Z]+$', color):
            await interaction.followup.send("Error: Color must be a valid basic color name.")
            return
        
        img = generate_waves_image(width, height, wave_amplitude, frequency, vertical_distance, color, overlap)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        filename = f"waves_{width}x{height}_{wave_amplitude}_{frequency}_{vertical_distance}_{color}_{overlap}.png"
        file = discord.File(fp=buffer, filename=filename)
        await interaction.followup.send(file=file)
        await log_action(self.bot, interaction)

    @app_commands.command(name="predict", description="Predict a value based on a dataset")
    @app_commands.describe(
        target="The x value you want to predict for (e.g., 69)",
        dataset="A dataset as a string (e.g. '1,2; 2,4; 3,8; 4,16; 5,32'). Optional if CSV file is provided.",
        csv_file="Upload a CSV file with two columns (x, y). Optional if dataset string is provided."
    )
    async def predict(
        self,
        interaction: discord.Interaction,
        target: float,
        dataset: str = None,
        csv_file: discord.Attachment = None
    ):
        """
        Predicts a value based on a provided dataset string or CSV file.
        
        - If all y values are numeric, a polynomial interpolation is used.
        - Otherwise, a nearest neighbor approach returns the y value corresponding to the x value closest to the target.
        """
        # Initial response to indicate that the command is being processed
        await interaction.response.send_message("Processing...", delete_after=1)
        
        data_points = []  # List to hold tuples (x, y)

        try:
            # Priority: Process CSV file if provided, verifying its extension.
            if csv_file is not None:
                if not csv_file.filename.lower().endswith(".csv"):
                    await interaction.followup.send("Error: The uploaded file is not a CSV file.")
                    return
                try:
                    file_bytes = await csv_file.read()
                    file_str = file_bytes.decode("utf-8")
                    df = pd.read_csv(io.StringIO(file_str))
                    if df.shape[1] < 2:
                        await interaction.followup.send("Error: CSV file must have at least two columns.")
                        return
                    # Use the first two columns for x and y.
                    for _, row in df.iterrows():
                        try:
                            x_val = float(row.iloc[0])
                        except Exception:
                            continue
                        y_val = str(row.iloc[1]).strip()
                        data_points.append((x_val, y_val))
                except Exception as csv_err:
                    await interaction.followup.send(f"Error processing CSV file: {csv_err}")
                    return

            # Process the dataset string if provided.
            elif dataset is not None:
                if dataset.strip() == "":
                    await interaction.followup.send("Error: The dataset string is empty.")
                    return
                try:
                    # Split the dataset string by semicolons.
                    rows = [row for row in dataset.split(";") if row.strip()]
                    data_list = []
                    for row in rows:
                        items = row.split(",")
                        if len(items) < 2:
                            continue  # Skip incomplete pairs.
                        try:
                            x_val = float(items[0].strip())
                        except Exception:
                            continue
                        y_val = items[1].strip()
                        data_list.append({"x": x_val, "y": y_val})
                    if not data_list:
                        await interaction.followup.send("Error: No valid data points found in dataset string.")
                        return
                    df = pd.DataFrame(data_list)
                    for _, row in df.iterrows():
                        data_points.append((row["x"], row["y"]))
                except Exception as ds_err:
                    await interaction.followup.send(f"Error processing dataset string: {ds_err}")
                    return
            else:
                await interaction.followup.send("Error: Please provide a dataset string or a CSV file.")
                return

            if len(data_points) < 2:
                await interaction.followup.send("Error: Please provide at least two valid data points for prediction.")
                return

            # Check whether all y values are numeric.
            all_numeric = True
            numeric_y_vals = []
            for (x, y) in data_points:
                try:
                    numeric_y_vals.append(float(y))
                except ValueError:
                    all_numeric = False
                    break

            # Prediction logic:
            if all_numeric:
                # Use polynomial interpolation for numeric y values.
                x_vals = np.array([pt[0] for pt in data_points])
                y_vals = np.array(numeric_y_vals)
                degree = len(data_points) - 1
                coeffs = np.polyfit(x_vals, y_vals, degree)
                poly = np.poly1d(coeffs)
                prediction = poly(target)
                result = (f"Based on the provided data, the predicted numeric value for {target} is approximately: "
                          f"{prediction}")
            else:
                # Use nearest neighbor approach for non-numeric y values.
                closest_point = min(data_points, key=lambda pt: abs(pt[0] - target))
                result = (f"Based on the provided data, the value corresponding to the x value closest to {target} "
                          f"is: '{closest_point[1]}' (from x = {closest_point[0]})")
                
            # Append processing time in milliseconds.
            latency = round(self.bot.latency * 1000)
            result += f"\n`Processing time: {latency} ms`"
            
            await interaction.followup.send(result)
        except Exception as e:
            await interaction.followup.send(f"An unexpected error occurred: {e}")
        
        await log_action(self.bot, interaction)

    @app_commands.command(
        name="enhance",
        description="Enhance an image file. If no change is needed, I'll let you know."
    )
    @app_commands.describe(
        image="The image to enhance",
        mode="Enhancement mode (optional; defaults to Auto)"
    )
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="Auto", value="auto"),
            app_commands.Choice(name="Background Effect", value="background_effect"),
            app_commands.Choice(name="Erase Reflections", value="erase_reflections"),
            app_commands.Choice(name="Erase Shadows", value="erase_shadows"),
            app_commands.Choice(name="Remaster", value="remaster"),
            app_commands.Choice(name="Remove Lens Flare", value="remove_lens_flare"),
        ]
    )
    async def enhance(
        self,
        interaction: discord.Interaction,
        image: discord.Attachment,
        mode: app_commands.Choice[str] = None
    ):
        await interaction.response.defer()

        # download the attachment
        img_bytes = await image.read()
        original = Image.open(io.BytesIO(img_bytes)).convert("RGB")

        # define enhancement functions
        def enhance_auto(img: Image.Image) -> Image.Image:
            enh = ImageEnhance.Color(img).enhance(1.2)
            enh = ImageEnhance.Contrast(enh).enhance(1.1)
            return enh.filter(ImageFilter.DETAIL)

        def enhance_background_effect(img: Image.Image) -> Image.Image:
            return img.filter(ImageFilter.GaussianBlur(radius=2))

        def erase_reflections(img: Image.Image) -> Image.Image:
            return img.filter(ImageFilter.UnsharpMask(radius=2, percent=150))

        def erase_shadows(img: Image.Image) -> Image.Image:
            enhancer = ImageEnhance.Brightness(img)
            return enhancer.enhance(1.1)

        def remaster(img: Image.Image) -> Image.Image:
            return img.filter(ImageFilter.DETAIL).filter(ImageFilter.SHARPEN)

        def remove_lens_flare(img: Image.Image) -> Image.Image:
            img_mod = ImageEnhance.Contrast(img).enhance(0.9)
            return ImageEnhance.Brightness(img_mod).enhance(1.05)

        # map modes to their functions
        modes = {
            "auto": enhance_auto,
            "background_effect": enhance_background_effect,
            "erase_reflections": erase_reflections,
            "erase_shadows": erase_shadows,
            "remaster": remaster,
            "remove_lens_flare": remove_lens_flare,
        }

        # select mode (default to 'auto')
        choice_value = mode.value if mode is not None else "auto"
        processed = modes[choice_value](original)

        # compare structural similarity to detect minimal change
        orig_np = np.array(original.resize((256, 256))).astype("float32")
        proc_np = np.array(processed.resize((256, 256))).astype("float32")
        grayA = np.dot(orig_np[..., :3], [0.2989, 0.5870, 0.1140])
        grayB = np.dot(proc_np[..., :3], [0.2989, 0.5870, 0.1140])
        score, _ = compare_ssim(grayA, grayB, full=True, data_range=grayB.max() - grayB.min())

        if score > 0.995:
            return await interaction.followup.send("Looks like no enhancement was needed.")

        # send back the enhanced image
        buf = io.BytesIO()
        processed.save(buf, format="PNG")
        buf.seek(0)
        file = discord.File(fp=buf, filename="enhanced.png")
        await interaction.followup.send(file=file)
        await log_action(self.bot, interaction)

async def setup(bot):
    await bot.add_cog(Generative(bot))
