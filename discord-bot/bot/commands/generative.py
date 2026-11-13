"""Generative commands: /dots and /waves draw images, /predict fits a dataset, /enhance edits a photo."""
import re
import discord
from discord.ext import commands
from discord import app_commands
import random
import math
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
from skimage.metrics import structural_similarity
import io
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
    # Step 1: a white canvas, and the light and dark ends of the colour gradient.
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    if color_name.lower() == "augy":
        base_color = (153, 255, 153)  # Augy green in RGB
    else:
        base_color = color_from_name(color_name)
    # Define light and dark versions of the base color.
    top_color = blend((255, 255, 255), base_color, 0.25)   # light tint
    bottom_color = blend((0, 0, 0), base_color, 0.5)        # darker shade

    # When overlapping is enabled, use a smaller vertical step.
    if overlap:
        step = vertical_distance * 0.5
    else:
        step = vertical_distance

    # Step 2: determine the stripe positions.
    stripes = []
    stripe_index = 0
    while True:
        y_start = stripe_index * step
        if y_start >= height:
            break
        y_end = y_start + vertical_distance
        if y_end > height:
            y_end = height
        stripes.append((y_start, y_end))
        stripe_index += 1

    stripe_count = len(stripes)

    # Step 3: draw each stripe. Later stripes will be drawn on top of earlier ones.
    for stripe_index, (y_start, y_end) in enumerate(stripes):
        # blend_fraction varies from 0 (top stripe) to 1 (bottom stripe) for the color gradient.
        if stripe_count > 1:
            blend_fraction = stripe_index / (stripe_count - 1)
        else:
            blend_fraction = 0
        row_color = blend(top_color, bottom_color, blend_fraction)

        # Top boundary oscillates between y_start and y_start + wave_amplitude.
        # Builds one (x, y) point per pixel column, left to right.
        top_boundary = [
            (column_x, y_start + wave_amplitude * ((math.sin(2 * math.pi * frequency * column_x / width) + 1) / 2))
            for column_x in range(width + 1)
        ]
        # Bottom boundary oscillates between y_end - wave_amplitude and y_end.
        # Builds one (x, y) point per pixel column, right to left, so the polygon closes.
        bottom_boundary = [
            (column_x, y_end - wave_amplitude * ((math.sin(2 * math.pi * frequency * column_x / width) + 1) / 2))
            for column_x in range(width, -1, -1)
        ]
        polygon = top_boundary + bottom_boundary
        draw.polygon(polygon, fill=row_color)

    return image

# --- /predict helpers ---

async def read_csv_data_points(interaction: discord.Interaction, csv_file: discord.Attachment):
    """
    Read (x, y) points from the first two columns of an uploaded CSV file.
    Rows whose x isn't a number are skipped; y is kept as text.
    Returns the list of points, or None after sending the user an error.
    """
    # Verify the file's extension first.
    if not csv_file.filename.lower().endswith(".csv"):
        await interaction.followup.send("Error: The uploaded file is not a CSV file.")
        return None
    data_points = []
    try:
        file_bytes = await csv_file.read()
        file_text = file_bytes.decode("utf-8")
        data_frame = pd.read_csv(io.StringIO(file_text))
        if data_frame.shape[1] < 2:
            await interaction.followup.send("Error: CSV file must have at least two columns.")
            return None
        # Use the first two columns for x and y.
        for _, row in data_frame.iterrows():
            try:
                x_value = float(row.iloc[0])
            except Exception:
                continue
            y_value = str(row.iloc[1]).strip()
            data_points.append((x_value, y_value))
    except Exception as csv_error:
        await interaction.followup.send(f"Error processing CSV file: {csv_error}")
        return None
    return data_points

async def parse_dataset_string(interaction: discord.Interaction, dataset: str):
    """
    Read (x, y) points from a dataset string such as '1,2; 2,4; 3,8'.
    Pairs with no comma, or whose x isn't a number, are skipped; y is kept as text.
    Returns the list of points, or None after sending the user an error.
    """
    if dataset.strip() == "":
        await interaction.followup.send("Error: The dataset string is empty.")
        return None
    data_points = []
    try:
        # Split the dataset string by semicolons.
        # Builds the list of non-blank "x,y" pairs.
        rows = [row for row in dataset.split(";") if row.strip()]
        data_list = []
        for row in rows:
            items = row.split(",")
            if len(items) < 2:
                continue  # Skip incomplete pairs.
            try:
                x_value = float(items[0].strip())
            except Exception:
                continue
            y_value = items[1].strip()
            data_list.append({"x": x_value, "y": y_value})
        if not data_list:
            await interaction.followup.send("Error: No valid data points found in dataset string.")
            return None
        data_frame = pd.DataFrame(data_list)
        for _, row in data_frame.iterrows():
            data_points.append((row["x"], row["y"]))
    except Exception as dataset_error:
        await interaction.followup.send(f"Error processing dataset string: {dataset_error}")
        return None
    return data_points

def numeric_y_values(data_points):
    """Return every y value as a float, or None if any y value isn't a number."""
    y_values = []
    for (_, y_value) in data_points:
        try:
            y_values.append(float(y_value))
        except ValueError:
            return None
    return y_values

def predict_numeric(data_points, y_values, target):
    """Fit a polynomial through every point and return the reply with its value at target."""
    # Use polynomial interpolation for numeric y values.
    # Builds the list of x values, in the same order as y_values.
    x_values = np.array([point[0] for point in data_points])
    y_array = np.array(y_values)
    degree = len(data_points) - 1
    coefficients = np.polyfit(x_values, y_array, degree)
    polynomial = np.poly1d(coefficients)
    prediction = polynomial(target)
    return (f"Based on the provided data, the predicted numeric value for {target} is approximately: "
            f"{prediction}")

def predict_nearest(data_points, target):
    """Return the reply with the y value of the point whose x is closest to target."""

    def distance_to_target(point):
        """How far a point's x value is from target."""
        return abs(point[0] - target)

    # Use nearest neighbor approach for non-numeric y values.
    closest_point = min(data_points, key=distance_to_target)
    return (f"Based on the provided data, the value corresponding to the x value closest to {target} "
            f"is: '{closest_point[1]}' (from x = {closest_point[0]})")

# --- /enhance modes: each takes an RGB image and returns the edited image ---

def enhance_auto(image: Image.Image) -> Image.Image:
    """Auto: a little more colour and contrast, then the DETAIL filter."""
    enhancer = ImageEnhance.Color(image)
    enhanced = enhancer.enhance(1.2)
    enhancer = ImageEnhance.Contrast(enhanced)
    enhanced = enhancer.enhance(1.1)
    return enhanced.filter(ImageFilter.DETAIL)

def enhance_background_effect(image: Image.Image) -> Image.Image:
    """Background Effect: a light Gaussian blur (radius 2)."""
    return image.filter(ImageFilter.GaussianBlur(radius=2))

def erase_reflections(image: Image.Image) -> Image.Image:
    """Erase Reflections: an unsharp mask (radius 2, 150%)."""
    return image.filter(ImageFilter.UnsharpMask(radius=2, percent=150))

def erase_shadows(image: Image.Image) -> Image.Image:
    """Erase Shadows: 10% brighter."""
    enhancer = ImageEnhance.Brightness(image)
    return enhancer.enhance(1.1)

def remaster(image: Image.Image) -> Image.Image:
    """Remaster: the DETAIL filter, then SHARPEN."""
    return image.filter(ImageFilter.DETAIL).filter(ImageFilter.SHARPEN)

def remove_lens_flare(image: Image.Image) -> Image.Image:
    """Remove Lens Flare: 10% less contrast, then 5% brighter."""
    lower_contrast = ImageEnhance.Contrast(image).enhance(0.9)
    return ImageEnhance.Brightness(lower_contrast).enhance(1.05)

# The /enhance mode values (the command's choices) and the function each one runs.
ENHANCE_MODES = {
    "auto": enhance_auto,
    "background_effect": enhance_background_effect,
    "erase_reflections": erase_reflections,
    "erase_shadows": erase_shadows,
    "remaster": remaster,
    "remove_lens_flare": remove_lens_flare,
}

def similarity_score(original: Image.Image, processed: Image.Image) -> float:
    """
    How alike two images look, from their structural similarity (SSIM) in greyscale
    at 256 x 256 pixels. 1.0 means identical.
    """
    original_array = np.array(original.resize((256, 256))).astype("float32")
    processed_array = np.array(processed.resize((256, 256))).astype("float32")
    original_gray = np.dot(original_array[..., :3], [0.2989, 0.5870, 0.1140])
    processed_gray = np.dot(processed_array[..., :3], [0.2989, 0.5870, 0.1140])
    score, _ = structural_similarity(original_gray, processed_gray, full=True,
                                     data_range=processed_gray.max() - processed_gray.min())
    return score

class Generative(commands.Cog):
    """The cog that holds the /dots, /waves, /predict and /enhance commands."""

    def __init__(self, bot):
        """Keep a reference to the bot, for logging and its latency."""
        self.bot = bot

    @staticmethod
    def _generate_dots_image(width: int, height: int, dot_diameter: int, dot_count: int = 1000, background_color: str = "#ffffff", overlap: bool = True) -> Image.Image:
        """
        Create an image with the specified background color and randomly placed colored dots.

        Parameters:
          - width, height: dimensions of the image.
          - dot_diameter: diameter of each dot.
          - dot_count: total number of dots.
          - background_color: background color as a hex code (e.g. "#ffffff").
          - overlap: if True, dots are placed without collision checking;
                     if False, dots are placed so they don't overlap (using a rejection method).
        """
        image = Image.new("RGB", (width, height), background_color)
        draw = ImageDraw.Draw(image)
        radius = dot_diameter / 2

        if overlap:
            # Simply place dots at random positions (they might overlap)
            for _ in range(dot_count):
                position_x = random.randint(0, width - dot_diameter)
                position_y = random.randint(0, height - dot_diameter)
                color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
                draw.ellipse((position_x, position_y, position_x + dot_diameter, position_y + dot_diameter), fill=color)
        else:
            # Attempt to place dots without overlapping
            placed_centers = []
            dots_placed = 0
            attempts = 0
            max_attempts = dot_count * 100  # Prevent infinite loops if dots are too many
            while dots_placed < dot_count and attempts < max_attempts:
                position_x = random.randint(0, width - dot_diameter)
                position_y = random.randint(0, height - dot_diameter)
                center_x = position_x + radius
                center_y = position_y + radius
                # A collision is a dot already placed less than one diameter away.
                collision = False
                for (placed_x, placed_y) in placed_centers:
                    distance = math.hypot(center_x - placed_x, center_y - placed_y)
                    if distance < dot_diameter:
                        collision = True
                        break
                if not collision:
                    placed_centers.append((center_x, center_y))
                    color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
                    draw.ellipse((position_x, position_y, position_x + dot_diameter, position_y + dot_diameter), fill=color)
                    dots_placed += 1
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

        Parameters (num_dots and bg_color are the option names users type, so they keep their short names):
          - width & height: dimensions of the image in pixels.
          - dot_diameter: diameter of each dot in pixels.
          - num_dots: number of dots to generate (default is 1000).
          - bg_color: hex color code for the background (default is "#ffffff").
          - overlap: if True, dots may overlap; if False, they will be placed without overlapping.
        """
        # Defer the response to allow for image generation time.
        await interaction.response.defer()

        # Step 1: check the options, replying with the first problem found.
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

        # Step 2: generate the image.
        image = Generative._generate_dots_image(width, height, dot_diameter, num_dots, bg_color, overlap)

        # Step 3: save the image to an in-memory bytes buffer and send it.
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

        # Step 1: check the options, replying with the first problem found.
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

        # Step 2: draw the image and send it, named after its settings.
        image = generate_waves_image(width, height, wave_amplitude, frequency, vertical_distance, color, overlap)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
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

        An input error is replied to and not logged; an unexpected error is replied to and logged.
        """
        # Initial response to indicate that the command is being processed
        await interaction.response.send_message("Processing...", delete_after=1)

        try:
            # Step 1: read the data points. Priority: the CSV file if provided, else the dataset string.
            if csv_file is not None:
                data_points = await read_csv_data_points(interaction, csv_file)
            elif dataset is not None:
                data_points = await parse_dataset_string(interaction, dataset)
            else:
                await interaction.followup.send("Error: Please provide a dataset string or a CSV file.")
                return
            if data_points is None:
                return  # the helper has already sent the error

            if len(data_points) < 2:
                await interaction.followup.send("Error: Please provide at least two valid data points for prediction.")
                return

            # Step 2: predict. Numeric y values get a polynomial; anything else, the nearest point.
            y_values = numeric_y_values(data_points)
            if y_values is not None:
                result = predict_numeric(data_points, y_values, target)
            else:
                result = predict_nearest(data_points, target)

            # Step 3: append processing time in milliseconds, and reply.
            latency = round(self.bot.latency * 1000)
            result += f"\n`Processing time: {latency} ms`"

            await interaction.followup.send(result)
        except Exception as error:
            await interaction.followup.send(f"An unexpected error occurred: {error}")

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
        """
        Apply an enhancement mode (Auto by default) to an uploaded image and send back enhanced.png.
        If the result looks almost the same as the original, say so instead (and don't log it).
        """
        await interaction.response.defer()

        # Step 1: download the attachment
        image_bytes = await image.read()
        original = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # Step 2: select mode (default to 'auto') and run it.
        if mode is not None:
            choice_value = mode.value
        else:
            choice_value = "auto"
        processed = ENHANCE_MODES[choice_value](original)

        # Step 3: compare structural similarity to detect minimal change
        score = similarity_score(original, processed)
        if score > 0.995:
            return await interaction.followup.send("Looks like no enhancement was needed.")

        # Step 4: send back the enhanced image
        buffer = io.BytesIO()
        processed.save(buffer, format="PNG")
        buffer.seek(0)
        file = discord.File(fp=buffer, filename="enhanced.png")
        await interaction.followup.send(file=file)
        await log_action(self.bot, interaction)

async def setup(bot):
    """Add the Generative cog to the bot (discord.py calls this when it loads the extension)."""
    await bot.add_cog(Generative(bot))
