"""Utility commands: random numbers, maths, dice, YouTube thumbnails, link fixes, /say,
the country checklist, /3dify, /scrape and /translate."""
import io
import cv2
import numpy as np
import trimesh
from io import BytesIO
from PIL import Image
import discord
from discord.ext import commands
from discord import TextChannel, app_commands, Interaction
from gtts import gTTS
from deep_translator import GoogleTranslator
from langdetect import detect, DetectorFactory
from typing import Optional, Tuple
import random
import re
import math
import ast
import operator
import logging
from bs4 import BeautifulSoup
import shutil
import json
import asyncio
import subprocess
import shlex
import os
import requests
from core.logger import log_action
from config import BOT_OWNER_ID

logger = logging.getLogger(__name__)

# Ensure consistent detection
DetectorFactory.seed = 0

# Top 20 most used languages mapping to codes
TOP_20_LANGUAGE_CODES = {
    "English": "en",
    "Chinese": "zh-cn",
    "Spanish": "es",
    "Hindi": "hi",
    "Arabic": "ar",
    "Bengali": "bn",
    "Portuguese": "pt",
    "Russian": "ru",
    "Japanese": "ja",
    "Punjabi": "pa",
    "Marathi": "mr",
    "Telugu": "te",
    "Turkish": "tr",
    "Korean": "ko",
    "French": "fr",
    "German": "de",
    "Vietnamese": "vi",
    "Tamil": "ta",
    "Urdu": "ur",
    "Javanese": "jv"
}

TOP_20_LANGUAGES = list(TOP_20_LANGUAGE_CODES.keys())


# --------------------------
# Country Checklist Handlers
# --------------------------
# /math works out an expression by walking its syntax tree, never with eval(). Only numbers,
# + - * / // % **, the math module's functions and constants, abs and round are allowed, and
# results are kept small enough that no expression can stall the bot.
MATH_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
MATH_UNARY_OPERATORS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
MATH_MAX_EXPRESSION_LENGTH = 200
MATH_MAX_RESULT_BITS = 5000  # about 1,500 digits, so the reply fits in one Discord message
MATH_MAX_LARGE_FUNCTION_ARGUMENT = 1000  # factorial, comb, perm; the result cap usually binds first
MATH_MAX_ROUND_DIGITS = 400  # round(x, -n) works out 10**n internally
MATH_LARGE_RESULT_FUNCTIONS = {"factorial", "comb", "perm"}


class UnsafeMathExpression(ValueError):
    """An expression that uses something /math doesn't allow, or whose result would be too large."""


def build_math_names():
    """Name -> value for every public name in the math module, plus abs and round."""
    names = {name: getattr(math, name) for name in dir(math) if not name.startswith("_")}
    names["abs"] = abs
    names["round"] = round
    return names


MATH_NAMES = build_math_names()


def check_math_result_size(value):
    """Return value, or raise if it is a whole number too large to show."""
    if isinstance(value, int) and value.bit_length() > MATH_MAX_RESULT_BITS:
        raise UnsafeMathExpression("result too large")
    return value


def evaluate_math_node(node):
    """Work out one node of a parsed expression, allowing only the operations listed above."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise UnsafeMathExpression("only numbers are allowed")
        return node.value
    if isinstance(node, ast.Name):
        value = MATH_NAMES.get(node.id)
        if value is None or callable(value):
            raise UnsafeMathExpression(f"unknown name {node.id}")
        return value
    if isinstance(node, ast.UnaryOp) and type(node.op) in MATH_UNARY_OPERATORS:
        return MATH_UNARY_OPERATORS[type(node.op)](evaluate_math_node(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in MATH_BINARY_OPERATORS:
        left = evaluate_math_node(node.left)
        right = evaluate_math_node(node.right)
        if isinstance(node.op, ast.Pow) and isinstance(left, int) and isinstance(right, int) and right > 0:
            # Check the size before working it out: a huge power can take minutes.
            if abs(left) > 1 and (abs(left).bit_length() - 1) * right > MATH_MAX_RESULT_BITS:
                raise UnsafeMathExpression("result too large")
        return check_math_result_size(MATH_BINARY_OPERATORS[type(node.op)](left, right))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
        function = MATH_NAMES.get(node.func.id)
        if function is None or not callable(function):
            raise UnsafeMathExpression(f"unknown function {node.func.id}")
        arguments = [evaluate_math_node(argument) for argument in node.args]
        if node.func.id == "round" and len(arguments) > 1:
            digits = arguments[1]
            if not isinstance(digits, int) or abs(digits) > MATH_MAX_ROUND_DIGITS:
                raise UnsafeMathExpression("round() digits out of range")
        if node.func.id in MATH_LARGE_RESULT_FUNCTIONS:
            for argument in arguments:
                if abs(argument) > MATH_MAX_LARGE_FUNCTION_ARGUMENT:
                    raise UnsafeMathExpression("argument too large")
        return check_math_result_size(function(*arguments))
    raise UnsafeMathExpression(f"{type(node).__name__} is not allowed")


def evaluate_math_expression(expression):
    """Work out a /math expression safely. Raises on anything not allowed, as eval() raised on bad input."""
    if len(expression) > MATH_MAX_EXPRESSION_LENGTH:
        raise UnsafeMathExpression("expression too long")
    return evaluate_math_node(ast.parse(expression, mode="eval").body)


class CountryChecklistView(discord.ui.View):
    """The checklist message's buttons: one per continent, plus Done."""

    def __init__(self, continents: dict[str, list[str]], owner: discord.User):
        """Keep the continents and the owner, start with nothing chosen, and add the buttons."""
        super().__init__(timeout=None)
        self.continents = continents
        self.owner = owner
        self.init_message: discord.Message  # set after send
        # builds an empty set of chosen countries for each continent
        self.selections = {continent: set() for continent in continents}
        for continent in continents:
            self.add_item(ContinentButton(continent))
        self.add_item(DoneButton())

    async def update_embed(self, interaction: discord.Interaction):
        """Rewrite each continent's field of the checklist message with the countries chosen so far."""
        # Edit the stored embed message
        message = self.init_message
        embed = message.embeds[0]
        for field_index, continent in enumerate(self.continents):
            chosen_countries = sorted(self.selections.get(continent, []))
            if chosen_countries:
                field_value = ", ".join(chosen_countries)
            else:
                field_value = "None"
            embed.set_field_at(field_index, name=continent, value=field_value, inline=True)
        await message.edit(embed=embed, view=self)


class ContinentButton(discord.ui.Button):
    """The button for one continent, which opens its country picker."""

    def __init__(self, continent: str):
        """Make the button, labelled with the continent."""
        super().__init__(style=discord.ButtonStyle.primary, label=continent)
        self.continent = continent

    async def callback(self, interaction: discord.Interaction):
        """Send the owner a private, paged picker of this continent's countries."""
        checklist_view: CountryChecklistView = self.view  # type: ignore
        if interaction.user.id != checklist_view.owner.id:
            return await interaction.response.send_message("This isn't yours.", ephemeral=True)

        countries = checklist_view.continents.get(self.continent, [])
        paginator_view = PaginatedSelectView(countries, self.continent, checklist_view)
        await interaction.response.send_message(
            f"Select in **{self.continent}** (page 1/{paginator_view.total_pages}):",
            view=paginator_view,
            ephemeral=True
        )


class PaginatedSelectView(discord.ui.View):
    """The country picker for one continent, 25 countries to a page."""

    def __init__(self, options: list[str], continent: str, parent: CountryChecklistView):
        """Split the countries into pages and show the first one."""
        super().__init__(timeout=None)
        self.options = options
        self.continent = continent
        self.parent = parent
        self.page_size = 25
        # builds the pages: slices of up to page_size countries each
        self.pages = [options[start_index:start_index + self.page_size]
                      for start_index in range(0, len(options), self.page_size)]
        self.page = 0
        self.total_pages = len(self.pages)
        self.page_selections: dict[int, set[str]] = {}
        self.update_components()

    def update_components(self):
        """Rebuild the controls for the current page: the country select, previous, next and Submit."""
        self.clear_items()
        # builds one select option per country on this page
        select_options = [discord.SelectOption(label=country, value=country) for country in self.pages[self.page]]
        self.add_item(PageSelect(select_options, self))
        previous_button = PrevButton()
        previous_button.disabled = self.page == 0
        self.add_item(previous_button)
        next_button = NextButton()
        next_button.disabled = self.page == self.total_pages - 1
        self.add_item(next_button)
        self.add_item(SubmitButton(self.continent, self.parent))

    async def refresh(self, interaction: discord.Interaction):
        """Show the current page in the picker message."""
        await interaction.response.edit_message(
            content=f"Select in **{self.continent}** (page {self.page + 1}/{self.total_pages}):",
            view=self
        )


class PageSelect(discord.ui.Select):
    """The country select for one page of the picker."""

    def __init__(self, options: list[discord.SelectOption], paginator_view: PaginatedSelectView):
        """Make the select; any number of this page's countries can be chosen."""
        super().__init__(placeholder="Choose countries…", min_values=0, max_values=len(options), options=options)
        self.paginator_view = paginator_view

    async def callback(self, interaction: discord.Interaction):
        """Remember the countries chosen on this page."""
        self.paginator_view.page_selections[self.paginator_view.page] = set(self.values)
        await interaction.response.defer()


class PrevButton(discord.ui.Button):
    """The button that goes back one page."""

    def __init__(self):
        """Make the ◀️ button."""
        super().__init__(style=discord.ButtonStyle.secondary, label="◀️")

    async def callback(self, interaction: discord.Interaction):
        """Show the previous page."""
        paginator_view: PaginatedSelectView = self.view  # type: ignore
        paginator_view.page -= 1
        paginator_view.update_components()
        await paginator_view.refresh(interaction)


class NextButton(discord.ui.Button):
    """The button that goes forward one page."""

    def __init__(self):
        """Make the ▶️ button."""
        super().__init__(style=discord.ButtonStyle.secondary, label="▶️")

    async def callback(self, interaction: discord.Interaction):
        """Show the next page."""
        paginator_view: PaginatedSelectView = self.view  # type: ignore
        paginator_view.page += 1
        paginator_view.update_components()
        await paginator_view.refresh(interaction)


class SubmitButton(discord.ui.Button):
    """The Submit button, which saves the picker's choices to the checklist."""

    def __init__(self, continent: str, parent: CountryChecklistView):
        """Make the Submit button for one continent of the checklist."""
        super().__init__(style=discord.ButtonStyle.success, label="Submit")
        self.continent = continent
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        """Save the countries chosen on every page, update the checklist and close the picker."""
        await interaction.response.defer(ephemeral=True)
        paginator_view: PaginatedSelectView = self.view  # type: ignore
        if paginator_view.page_selections:
            selection = set().union(*paginator_view.page_selections.values())
        else:
            selection = set()
        self.parent.selections[self.continent] = selection
        await self.parent.update_embed(interaction)
        await interaction.message.edit(content="✅ Selection saved.", view=None)


class DoneButton(discord.ui.Button):
    """The Done button, which adds up the checklist and posts the result."""

    def __init__(self):
        """Make the Done button."""
        super().__init__(style=discord.ButtonStyle.success, label="Done")

    async def callback(self, interaction: discord.Interaction):
        """Add the owner's total to the checklist, close it, and post the result in the channel."""
        checklist_view: CountryChecklistView = self.view  # type: ignore
        if interaction.user.id != checklist_view.owner.id:
            return await interaction.response.send_message("This isn't yours.", ephemeral=True)
        # adds up the countries chosen across all continents
        total_selected = sum(len(chosen_countries) for chosen_countries in checklist_view.selections.values())
        # adds up all the countries in the list
        total_countries = sum(len(countries) for countries in checklist_view.continents.values())
        if total_countries:
            percent = (total_selected / total_countries * 100)
        else:
            percent = 0
        message = checklist_view.init_message
        embed = message.embeds[0]
        embed.add_field(name="Results",
                        value=f"{checklist_view.owner.mention} has been to **{total_selected}**/**{total_countries}** ({percent:.2f}%) of the world!",
                        inline=False)
        await message.edit(embed=embed, view=None)
        await message.channel.send(embed=embed)


# --------------------------
# Translation Handlers
# --------------------------
class TranslateView(discord.ui.View):
    """The buttons under a translation that read the original or the translation aloud."""

    def __init__(self, original_text: str, translated_text: str, source_language_code: str, target_language_code: str):
        """Keep both texts and their language codes for the buttons."""
        super().__init__(timeout=None)
        self.original_text = original_text
        self.translated_text = translated_text
        self.source_language_code = source_language_code
        self.target_language_code = target_language_code

    @discord.ui.button(label="🔊 Listen to original", style=discord.ButtonStyle.primary)
    async def listen_original(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Send the original text as an MP3 of speech."""
        # Use detected or specified language code for original
        text_to_speech = gTTS(text=self.original_text, lang=self.source_language_code)
        audio_file = BytesIO()
        text_to_speech.write_to_fp(audio_file)
        audio_file.seek(0)
        attachment = discord.File(audio_file, filename="original.mp3")
        await interaction.response.send_message(content="Original text audio:", file=attachment)

    @discord.ui.button(label="🔊 Listen to translated", style=discord.ButtonStyle.primary)
    async def listen_translated(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Send the translated text as an MP3 of speech."""
        text_to_speech = gTTS(text=self.translated_text, lang=self.target_language_code)
        audio_file = BytesIO()
        text_to_speech.write_to_fp(audio_file)
        audio_file.seek(0)
        attachment = discord.File(audio_file, filename="translated.mp3")
        await interaction.response.send_message(content="Translated text audio:", file=attachment)


class Utility(commands.Cog):
    """The utility commands, and the helpers behind /countrychecklist, /3dify, /scrape and /translate."""

    def __init__(self, bot):
        """Start loading the country list in the background and set up the lookups the commands use."""
        self.bot = bot
        # Kick off an initial load
        self._load_task = bot.loop.create_task(self._load_countries())
        self.valid_users = [269080651599314944, 292864211825197056, 543846099971080192]

        # These sets help avoid downloading the same page or resource more than once.
        self.visited_pages = set()
        self.downloaded_resources = {}  # resource_url -> local_path

        # Map language names to codes: builds lower-case language name -> code
        self.language_name_to_code = {name.lower(): code for name, code in TOP_20_LANGUAGE_CODES.items()}
        # Map codes to display names: builds code -> language name
        self.language_code_to_name = {code: name for name, code in TOP_20_LANGUAGE_CODES.items()}

    @app_commands.command(name="randnum", description="Generate a random number between a given range.")
    @app_commands.describe(minimum_number="The minimum number", maximum_number="The maximum number")
    @app_commands.rename(minimum_number="min_num", maximum_number="max_num")
    async def randnum(self, interaction: discord.Interaction, minimum_number: int, maximum_number: int):
        """Send a random whole number between the minimum and maximum, inclusive."""
        if minimum_number > maximum_number:
            await interaction.response.send_message("❌ The minimum number cannot be greater than the maximum number.", ephemeral=True)
            return

        result = random.randint(minimum_number, maximum_number)
        await interaction.response.send_message(f"🎲 Random number between {minimum_number} and {maximum_number}: **{result}**")
        await log_action(self.bot, interaction)

    @app_commands.command(name="math", description="Solve a math expression.")
    @app_commands.describe(expression="The math expression to solve")
    async def math(self, interaction: discord.Interaction, expression: str):
        """Evaluates a math expression safely."""
        try:
            # Work out the expression from its syntax tree (see evaluate_math_expression)
            result = evaluate_math_expression(expression)
            await interaction.response.send_message(f"🧮 Result of `{expression}`: **{result}**")
        except Exception:
            if expression == "0/0":
                await interaction.response.send_message("🍪 Imagine that you have zero cookies and you split them evenly among zero friends.\nHow many cookies does each person get?\nYou see, it doesn't make sense. Cookie Monster is sad that there are no cookies, and you are sad that you have no friends.")
            else:
                await interaction.response.send_message("❌ Invalid mathematical expression.", ephemeral=True)
        await log_action(self.bot, interaction)

    @app_commands.command(name="roll", description="Roll dice in the format XdY (e.g., /roll 4d8 or /roll d20).")
    @app_commands.describe(dice="The dice format (e.g., 4d8 or d20)")
    async def roll(self, interaction: discord.Interaction, dice: str):
        """Roll dice written as XdY (or dY for one die) and send each roll and the total."""
        # Read the number of dice (1 if left out) and the number of sides
        match = re.fullmatch(r'(\d*)d(\d+)', dice.strip())
        if not match:
            await interaction.response.send_message("❌ Invalid format! Use XdY (e.g., 4d8 or d20).", ephemeral=True)
            return

        if match.group(1):
            number_of_dice = int(match.group(1))
        else:
            number_of_dice = 1
        number_of_sides = int(match.group(2))

        # Check the numbers
        if number_of_dice <= 0 or number_of_sides <= 0:
            await interaction.response.send_message("❌ The number of dice and sides must be positive integers.", ephemeral=True)
            return

        # There's no return after this warning, so the roll still goes ahead as a second reply.
        if number_of_dice > 100 or number_of_sides > 100:
            await interaction.response.send_message("❌ The number of dice and sides must be 100 or less.", ephemeral=True)

        # Roll the dice and calculate results: builds one random roll per die
        rolls = [random.randint(1, number_of_sides) for _ in range(number_of_dice)]
        total = sum(rolls)

        # Prepare response message: builds one "Dice N: roll" line per die
        roll_results = "\n".join([f"Dice {roll_index + 1}: {roll}" for roll_index, roll in enumerate(rolls)])
        response = f"{roll_results}\n**Total:** {total}"

        await interaction.response.send_message(f"🎲 Rolling {number_of_dice}d{number_of_sides}:\n{response}")
        await log_action(self.bot, interaction)

    @app_commands.command(name="ytimg", description="Get the thumbnail image of a YouTube video.")
    @app_commands.describe(link_or_id="The YouTube video link or ID")
    async def ytimg(self, interaction: discord.Interaction, link_or_id: str):
        """Send the full-size thumbnail of a YouTube video, from its link or id."""
        # Regular expression patterns to extract video ID
        youtube_patterns = [
            r"(?:https?://)?(?:www\.|m\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([\w-]+)",  # YouTube long/shorts links
            r"(?:https?://)?(?:www\.|m\.)?youtube\.com/embed/([\w-]+)",  # Embedded video link
            r"^[\w-]{11}$"  # Direct video ID
        ]

        video_id = None
        for pattern in youtube_patterns:
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

    @app_commands.command(name="fix", description="Fixes Twitter, Instagram, and BlueSky links to bypass login walls.")
    @app_commands.describe(url="The social media link to fix")
    async def fix(self, interaction: discord.Interaction, url: str):
        """Fixes known social media links to an alternative view."""
        patterns = {
            r"(https?://(?:www\.)?(?:twitter|x)\.com/+)": "https://fixupx.com/",
            r"(https?://bsky\.app/profile/+)": "https://fxbsky.app/profile/",
            r"(https?://www\.instagram\.com/(reel|post)/[\w\d_/]+)": "https://www.ddinstagram.com"
        }

        fixed_url = None

        for pattern, fixup_base in patterns.items():
            match = re.match(pattern, url)
            if match:
                if "instagram.com" in url:
                    # Replace only the "www.instagram.com" part for Instagram
                    fixed_url = url.replace("www.instagram.com", "www.ddinstagram.com")
                else:
                    fixed_url = url.replace(match.group(1), fixup_base)
                break
        if fixed_url:
            await interaction.response.send_message(f"🔗 Here's your fixed link: {fixed_url}")
        else:
            await interaction.response.send_message("❌ This link doesn't have an eligible fixup.", ephemeral=True)

        await log_action(self.bot, interaction)

    @app_commands.command(name="say", description="Make the bot repeat what you say.")
    @app_commands.describe(
        message="The message to repeat, use \\n for a new line",
        channel="Optional: the channel to send the message in (defaults to current channel)"
    )
    async def say(
        self,
        interaction: discord.Interaction,
        message: str,
        channel: Optional[TextChannel] = None
    ):
        """Post a message as the bot, here or in another channel (bot owner or Manage Messages only)."""
        # Permission check
        if not interaction.user.id == BOT_OWNER_ID:
            if not interaction.user.guild_permissions.manage_messages:
                return await interaction.response.send_message(
                    "❌ You do not have permission to use this command.", ephemeral=True
                )

        # Defer the response (ephemeral)
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("Processing…", ephemeral=True)

        # Determine target channel
        target_channel: TextChannel = channel or interaction.channel  # type: ignore
        # Send the user message, preserving newlines
        await target_channel.send(message.replace("\\n", "\n"))
        await log_action(self.bot, interaction)

    # -------------------------
    # Country Checklist Handler
    # -------------------------
    async def _load_countries(self):
        """Load the bundled continent -> country list (countries.json), handling errors."""
        # restcountries.com v3.1 was shut down (v5 needs an API key), so the list ships with the bot.
        path = os.path.join(os.path.dirname(__file__), "countries.json")
        try:
            with open(path, encoding="utf-8") as countries_file:
                country_data = json.load(countries_file)
            if not isinstance(country_data, dict):
                raise ValueError("countries.json must be a JSON object of continent -> [countries]")
        except Exception as error:
            logger.error(f"Failed to load country data: {error}")
            self.continents = {}
            return

        # builds continent -> sorted country names, leaving out empty continents
        continents = {continent: sorted(country_names) for continent, country_names in country_data.items() if country_names}
        self.continents = continents
        # adds up the countries across all continents
        country_count = sum(len(country_names) for country_names in continents.values())
        logger.info(f"Loaded {country_count} countries across {len(continents)} continents.")

    @app_commands.command(
        name="countrychecklist",
        description="Mark which countries you've been to, by continent."
    )
    async def countrychecklist(self, interaction: discord.Interaction):
        """Send a private checklist of countries, one button per continent."""
        # Wait for the initial load; retry on failure
        await self._load_task
        if not getattr(self, 'continents', None):
            await self._load_countries()

        # Build the embed
        embed = discord.Embed(
            title="Which countries have I been to?",
            color=discord.Color.blurple()
        )
        if not self.continents:
            embed.description = "⚠️ Country data unavailable. Please try again later."
        else:
            for continent in self.continents:
                embed.add_field(name=continent, value="None", inline=True)

        view = CountryChecklistView(self.continents, interaction.user)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.init_message = await interaction.original_response()
        await log_action(self.bot, interaction)

    # -------------------------
    # ----- 3Dify Handler -----
    # -------------------------
    @staticmethod
    def convert_to_3d(image_bytes: bytes, thickness: int, output_type: str) -> Tuple[bytes, str]:
        """
        Converts a 2D image into a 3D mesh by voxelizing based on grayscale height,
        then exports to PNG, GIF, OBJ, or STL. Returns raw bytes and a suggested filename.
        """
        # Load image as grayscale
        image_array = np.frombuffer(image_bytes, np.uint8)
        grayscale_image = cv2.imdecode(image_array, cv2.IMREAD_GRAYSCALE)
        # Map intensities [0,255] to height levels [0, thickness]
        height_map = (grayscale_image.astype(np.float32) / 255.0 * thickness).astype(np.int32)
        height, width = height_map.shape
        # Build voxel grid: each level is filled where the pixel is taller than it
        voxels = np.zeros((height, width, thickness), dtype=bool)
        for level in range(thickness):
            voxels[:, :, level] = height_map > level
        # Create mesh via marching cubes (requires scikit-image)
        mesh = trimesh.voxel.ops.matrix_to_marching_cubes(voxels)

        # OBJ / STL export
        if output_type in ('obj', 'stl'):
            mesh_bytes = mesh.export(file_type=output_type)
            return mesh_bytes, f"output.{output_type}"

        # Render scene for images
        scene = mesh.scene()
        if output_type == 'png':
            png_bytes = scene.save_image(resolution=(512, 512))
            return png_bytes, "output.png"
        elif output_type == 'gif':
            # One frame every 60 degrees round the model, joined into a looping GIF
            frames = []
            for angle in range(0, 360, 60):
                scene.camera.transform = trimesh.transformations.euler_matrix(0, 0, np.radians(angle))
                frame_bytes = scene.save_image(resolution=(512, 512))
                frames.append(Image.open(BytesIO(frame_bytes)))
            gif_buffer = BytesIO()
            frames[0].save(gif_buffer, format='GIF', save_all=True,
                           append_images=frames[1:], duration=100, loop=0)
            return gif_buffer.getvalue(), "output.gif"

        # Fallback
        return image_bytes, "output.png"

    @app_commands.command(name="3dify", description="Convert an image into a 3D object")
    @app_commands.describe(
        image="The image file to convert",
        output_type="Type of output file",
        thickness="Thickness/extrusion depth in pixels"
    )
    @app_commands.choices(
        output_type=[
            app_commands.Choice(name="Image (PNG)", value="png"),
            app_commands.Choice(name="Animated Image (GIF)", value="gif"),
            app_commands.Choice(name="Model (OBJ)", value="obj"),
            app_commands.Choice(name="Model (STL)", value="stl"),
        ]
    )
    async def three_dify(
        self,
        interaction: discord.Interaction,
        image: discord.Attachment,
        output_type: app_commands.Choice[str],
        thickness: int = 10,
    ):
        """
        /3dify image: converts a 2D image into a 3D model or rendered image

        - image: upload a PNG/JPEG/etc.
        - output_type: choose your return format (default: PNG)
        - thickness: extrusion depth in pixels (default: 10)
        """

        # Validate thickness
        if thickness < 0 or thickness > 20:
            await interaction.response.send_message(
                "❌ Thickness must be between 0 and 20 pixels.", ephemeral=True
            )
            return

        await interaction.response.defer()

        # Read and process
        uploaded_image_bytes = await image.read()
        result_bytes, suggested_name = self.convert_to_3d(
            image_bytes=uploaded_image_bytes,
            thickness=thickness,
            output_type=output_type.value,
        )
        # Construct new filename from original
        base_name = image.filename.rsplit('.', 1)[0]
        extension = suggested_name.rsplit('.', 1)[-1]
        new_filename = f"{base_name}_3dified.{extension}"

        # Send file
        file = discord.File(io.BytesIO(result_bytes), filename=new_filename)
        await interaction.followup.send(file=file)
        await log_action(self.bot, interaction)

    # -------------------------
    # ----- Scrape Handler ----
    # -------------------------
    def get_local_path(self, url: str, base_output_directory: str) -> str:
        """Where a URL is saved locally: <output folder>/<host>/<path>, with index.html for a folder path."""
        parsed_url = requests.utils.urlparse(url)
        path = parsed_url.path or "/"
        if path.endswith("/"):
            path = os.path.join(path, "index.html")
        return os.path.join(base_output_directory, parsed_url.netloc, path.lstrip("/"))

    def download_file(self, url: str, local_path: str) -> bool:
        """Download a URL to a local file; return True on success, False (after printing why) on failure."""
        try:
            response = requests.get(url, stream=True, timeout=10)
            response.raise_for_status()
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "wb") as output_file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        output_file.write(chunk)
            return True
        except Exception as error:
            print(f"Error downloading {url}: {error}")
            return False

    def scrape_page(self, url: str, base_output_directory: str, base_domain: str):
        """Save a page and the files it uses, point it at the local copies, then follow its same-site links."""
        # Skip a page that's already been visited
        if url in self.visited_pages:
            return
        self.visited_pages.add(url)

        # Fetch the page
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except Exception as error:
            print(f"Error accessing {url}: {error}")
            return

        # Save anything that isn't HTML as it is
        if "text/html" not in response.headers.get("Content-Type", ""):
            self.download_file(url, self.get_local_path(url, base_output_directory))
            return
        soup = BeautifulSoup(response.text, "lxml")

        def process_resource(tag, attribute):
            """Download the file a tag points to (once) and point the tag at the local copy."""
            if not tag.has_attr(attribute):
                return
            original_url = tag[attribute]
            resource_url = requests.compat.urljoin(url, original_url)
            local_resource_path = self.get_local_path(resource_url, base_output_directory)
            if resource_url not in self.downloaded_resources:
                if self.download_file(resource_url, local_resource_path):
                    self.downloaded_resources[resource_url] = local_resource_path
            tag[attribute] = os.path.relpath(local_resource_path,
                                             os.path.dirname(self.get_local_path(url, base_output_directory)))

        # Download the page's images, scripts, stylesheets, video and audio
        for image_tag in soup.find_all("img", src=True):
            process_resource(image_tag, "src")
        for script_tag in soup.find_all("script", src=True):
            process_resource(script_tag, "src")
        for link_tag in soup.find_all("link", href=True):
            if link_tag.get("rel") and "stylesheet" in link_tag.get("rel"):
                process_resource(link_tag, "href")
        for media_tag in soup.find_all(["video", "audio"], src=True):
            process_resource(media_tag, "src")

        # Save the page, now pointing at the local copies
        local_html = self.get_local_path(url, base_output_directory)
        os.makedirs(os.path.dirname(local_html), exist_ok=True)
        with open(local_html, "w", encoding="utf-8") as html_file:
            html_file.write(str(soup))

        # Follow the links that stay on the same site
        for anchor_tag in soup.find_all("a", href=True):
            next_url = requests.compat.urljoin(url, anchor_tag["href"])
            if requests.utils.urlparse(next_url).netloc == base_domain:
                self.scrape_page(next_url, base_output_directory, base_domain)

    def upload_with_npm_cli(self, file_path: str) -> str:
        """
        Uploads via uploadr-cli (npm package). Requires `npm install -g uploadr-cli`.
        """
        command = f"uploadr upload {shlex.quote(file_path)}"
        completed_process = subprocess.run(command, shell=True, capture_output=True, text=True)
        if completed_process.returncode != 0:
            raise RuntimeError(f"uploadr-cli failed: {completed_process.stderr.strip()}")
        return completed_process.stdout.strip()

    def perform_scrape_and_package(self, url: str) -> str:
        """Scrape a site into a fresh scraped_site folder, zip it, and return the zip's path."""
        base_output_directory = "scraped_site"
        shutil.rmtree(base_output_directory, ignore_errors=True)
        self.visited_pages.clear()
        self.downloaded_resources.clear()
        os.makedirs(base_output_directory, exist_ok=True)
        self.scrape_page(url, base_output_directory, requests.utils.urlparse(url).netloc)
        return shutil.make_archive(base_output_directory, 'zip', base_output_directory)

    @app_commands.command(name="scrape",
                          description="Scrape and ZIP a site, then send or upload via uploadr-cli.")
    async def scrape(self, interaction: Interaction, url: str):
        """Scrape a site and send it as a ZIP, or upload it with uploadr-cli if it's over 500MB (allowed users only)."""
        if interaction.user.id not in self.valid_users:
            await interaction.response.send_message(
                "You do not have permission to execute this command.", ephemeral=True
            )
            return
        await interaction.response.defer(thinking=True, ephemeral=True)
        zip_path = ''
        try:
            zip_path = await asyncio.to_thread(self.perform_scrape_and_package, url)
            archive_size = os.path.getsize(zip_path)
            if archive_size <= 500 * 1024 * 1024:
                await interaction.followup.send(file=discord.File(zip_path))
                return
            await interaction.followup.send("Archive exceeds 500MB, uploading via uploadr-cli...")
            link = await asyncio.to_thread(self.upload_with_npm_cli, zip_path)
            await interaction.followup.send(f"Uploaded via uploadr-cli: {link}")
        except Exception as error:
            await interaction.followup.send(
                f"Upload failed: {error}\nPlease ensure uploadr-cli is installed and in your PATH, or download the ZIP directly."
            )
        finally:
            await asyncio.to_thread(shutil.rmtree, "scraped_site", True)
            if zip_path and os.path.exists(zip_path):
                await asyncio.to_thread(os.remove, zip_path)
        await log_action(self.bot, interaction)

    # -------------------------
    # ----- Translate Handler --
    # -------------------------

    async def source_autocomplete(self, interaction: discord.Interaction, current: str):
        """Autocomplete for source language: includes 'Auto' + top20."""
        language_entries = ['Auto'] + TOP_20_LANGUAGES
        # builds a choice for each language that contains what's been typed, at most 25
        return [app_commands.Choice(name=language, value=language)
                for language in language_entries if current.lower() in language.lower()][:25]

    async def target_autocomplete(self, interaction: discord.Interaction, current: str):
        """Autocomplete for target language: only top20."""
        # builds a choice for each language that contains what's been typed, at most 25
        return [app_commands.Choice(name=language, value=language)
                for language in TOP_20_LANGUAGES if current.lower() in language.lower()][:25]

    @app_commands.command(name="translate", description="Translate text between languages.")
    @app_commands.describe(
        text="Text to translate",
        from_language="Source language (default: auto-detect)",
        to_language="Target language"
    )
    @app_commands.rename(from_language="from_lang", to_language="to_lang")
    @app_commands.autocomplete(from_language=source_autocomplete, to_language=target_autocomplete)
    async def translate(
        self,
        interaction: discord.Interaction,
        text: str,
        to_language: str,
        from_language: str = 'Auto'
    ):
        """Translate text into another language, with buttons that read both versions aloud."""
        await interaction.response.defer()

        # Determine source language code and display name
        if from_language.lower() == 'auto':
            detected_code = detect(text)
            source_language_code = detected_code
            source_display_name = self.language_code_to_name.get(source_language_code, source_language_code)
            source_label = f"Auto-detected ({source_display_name})"
        else:
            source_language_code = self.language_name_to_code.get(from_language.lower(), from_language)
            source_label = self.language_code_to_name.get(source_language_code, from_language)

        # Determine target language code and display name
        target_language_code = self.language_name_to_code.get(to_language.lower(), to_language)
        target_label = self.language_code_to_name.get(target_language_code, to_language)

        # Perform translation
        translated_text = GoogleTranslator(source=source_language_code, target=target_language_code).translate(text)

        # Build embed
        embed = discord.Embed(title="Translation", color=discord.Color.blurple())
        embed.add_field(name=f"Translate From ({source_label})", value=text, inline=False)
        embed.add_field(name=f"Translate To ({target_label})", value=translated_text, inline=False)

        # Add TTS buttons
        view = TranslateView(
            original_text=text,
            translated_text=translated_text,
            source_language_code=source_language_code,
            target_language_code=target_language_code
        )
        await interaction.followup.send(embed=embed, view=view)
        await log_action(self.bot, interaction)


async def setup(bot):
    """Add the Utility cog to the bot."""
    await bot.add_cog(Utility(bot))
