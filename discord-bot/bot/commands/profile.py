"""The /profile command: draws an ID badge for a Discord user and sends it as an image."""
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import io
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import qrcode
import random
from core.logger import log_action

# --- Badge layout ---

BADGE_WIDTH, BADGE_HEIGHT = 900, 450  # size of the ID badge
MARGIN = 20
LEFT_AREA_WIDTH = BADGE_WIDTH // 2
TEXT_AREA_X = LEFT_AREA_WIDTH + MARGIN
LINE_SPACING = 5

# The server whose badges get the globalfurry.tv QR code in the top right corner.
QR_CODE_GUILD_ID = 576590416296542249

# --- Helper Functions ---

async def download_bytes(url: str) -> io.BytesIO:
    """Download bytes from a URL and return a BytesIO object."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                return io.BytesIO(await response.read())
    return None

async def fetch_image(url: str) -> Image.Image:
    """Download an image from a URL and return a Pillow Image in RGBA mode."""
    try:
        data = await download_bytes(url)
        if data:
            return Image.open(data).convert("RGBA")
    except Exception as error:
        print(f"Error fetching image from {url}: {error}")
    return None

async def get_fallback_avatar() -> Image.Image:
    """Returns a fallback avatar image (using a placeholder image)."""
    fallback_url = "https://i.augy.xyz/M0VoBqRny.svg"
    image = await fetch_image(fallback_url)
    return image

def create_rounded_mask(size: tuple, radius: int) -> Image.Image:
    """Create a rounded rectangle mask for a given size and corner radius."""
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0) + size, radius=radius, fill=255)
    return mask

def truncate(text: str, limit: int) -> str:
    """Truncate text to a maximum length."""
    if not text:
        return ""
    if len(text) <= limit:
        return text
    else:
        return text[:limit]

def get_truetype_font(font_source, size: int) -> ImageFont.FreeTypeFont:
    """
    Given a font_source which can be a path (str) or a BytesIO object,
    resets the pointer if necessary and returns a truetype font.
    """
    if hasattr(font_source, "seek"):
        font_source.seek(0)
    return ImageFont.truetype(font_source, size)

def get_text_size(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont) -> tuple:
    """
    Returns the width and height of the given text using the provided draw context and font,
    using the textbbox method.
    """
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    return width, height

# --- Steps of the /profile command, in the order it runs them ---

async def build_background(user) -> Image.Image:
    """
    Return the badge background: the user's profile banner, resized and blurred,
    else a plain fill in their accent colour, else plain #fedc00.
    """
    try:
        banner_image = None
        banner_url = None
        if hasattr(user, "banner") and user.banner:
            banner_url = user.banner.url
        if banner_url:
            banner_image = await fetch_image(banner_url)
            if banner_image:
                banner_image = banner_image.resize((BADGE_WIDTH, BADGE_HEIGHT))
                banner_image = banner_image.filter(ImageFilter.GaussianBlur(radius=10))
        if not banner_image:
            # Use accent color if available; default to #fedc00 if not.
            color = getattr(user, "accent_color", None) or "#fedc00"
            banner_image = Image.new("RGBA", (BADGE_WIDTH, BADGE_HEIGHT), color)
    except Exception as error:
        print(f"Error with banner info: {error}")
        banner_image = Image.new("RGBA", (BADGE_WIDTH, BADGE_HEIGHT), "#fedc00")
    return banner_image

async def fetch_avatar(interaction: discord.Interaction, user) -> Image.Image:
    """
    Return the user's avatar (their server avatar when used in a server).
    If it can't be downloaded, return the placeholder avatar on a random pastel background;
    after an error, the placeholder alone.
    """
    avatar_image = None
    try:
        # In servers, use the display avatar (which may be a server-specific one)
        if interaction.guild and hasattr(user, "display_avatar"):
            avatar_url = user.display_avatar.url
        else:
            if user.avatar:
                avatar_url = user.avatar.url
            else:
                avatar_url = None

        if avatar_url:
            avatar_image = await fetch_image(avatar_url)
        if not avatar_image:
            avatar_image = await get_fallback_avatar()
            # Set a random pastel background for the fallback
            pastel = (random.randint(200, 255), random.randint(200, 255), random.randint(200, 255))
            pastel_background = Image.new("RGBA", avatar_image.size, pastel)
            pastel_background.paste(avatar_image, (0, 0), avatar_image)
            avatar_image = pastel_background
    except Exception as error:
        print(f"Error fetching avatar: {error}")
        avatar_image = await get_fallback_avatar()
    return avatar_image

def frame_avatar(avatar_image: Image.Image) -> Image.Image:
    """
    Fit the avatar to the left half of the badge, round its corners and add a white border.
    Returns the bordered avatar, ready to paste at (MARGIN, MARGIN).
    """
    # If the avatar image has transparency, composite it on a white background.
    if avatar_image.mode in ("RGBA", "LA"):
        white_background = Image.new("RGBA", avatar_image.size, (255, 255, 255, 255))
        white_background.paste(avatar_image, mask=avatar_image.split()[3])
        avatar_image = white_background

    # Resize avatar to fit (with some margin) in left half.
    target_avatar_width = LEFT_AREA_WIDTH - 2 * MARGIN
    target_avatar_height = BADGE_HEIGHT - 2 * MARGIN
    avatar_image = avatar_image.resize((target_avatar_width, target_avatar_height))

    # Create rounded corners for the avatar.
    corner_radius = 20
    mask_image = create_rounded_mask(avatar_image.size, corner_radius)
    avatar_image.putalpha(mask_image)

    # Add a white border around the avatar.
    border_size = 5
    bordered_size = (avatar_image.width + 2 * border_size, avatar_image.height + 2 * border_size)
    bordered_avatar = Image.new("RGBA", bordered_size, (0, 0, 0, 0))
    # Draw white rounded rectangle as the border.
    border_draw = ImageDraw.Draw(bordered_avatar)
    border_draw.rounded_rectangle((0, 0) + bordered_size, radius=corner_radius + border_size, fill="white")
    bordered_avatar.paste(avatar_image, (border_size, border_size), avatar_image)
    return bordered_avatar

async def load_font_source(font_url: str):
    """
    Download the font for the badge text: the custom font if a URL is given and it downloads,
    else Microsoft Yahei from GitHub. Returns the font bytes (BytesIO), the local file name
    "MicrosoftYaHei.ttf" if the default download raised an error, or None.
    """
    # Download custom font if a URL is provided; otherwise, use the default.
    # (The URL should directly point to a .ttf file.)
    font_source = None
    if font_url:
        try:
            font_bytes = await download_bytes(font_url)
            if font_bytes:
                font_source = font_bytes
        except Exception as error:
            print(f"Error downloading custom font: {error}")
    # Use default font file if custom font not available.
    if not font_source:
        default_font_url = "https://raw.githubusercontent.com/dolbydu/font/master/unicode/Microsoft%20Yahei.ttf"
        try:
            font_bytes = await download_bytes(default_font_url)
            if font_bytes:
                font_source = font_bytes
        except Exception as error:
            print(f"Error downloading default font: {error}")
            # Fallback to local file if available
            font_source = "MicrosoftYaHei.ttf"
    return font_source

def build_text_lines(interaction: discord.Interaction, user) -> list:
    """
    Return the lines of user details for the right side of the badge: username, display name
    (with the server nickname), ID and account date, then the server join date, activity and bio
    when there are any.
    """
    # Prepare user info text with truncation
    username = truncate(user.name, 16)
    display_name = truncate(user.display_name, 16)
    discord_id = str(user.id)
    server_nick = ""
    if interaction.guild:
        member = interaction.guild.get_member(user.id)
        if member and member.nick:
            server_nick = f"({truncate(member.nick, 16)})"
    created_at = user.created_at.strftime("%Y-%m-%d")
    server_join = ""
    if interaction.guild and member and member.joined_at:
        server_join = member.joined_at.strftime("%Y-%m-%d")
    activity = ""
    if user.activity and user.activity.name:
        activity = f"Playing {user.activity.name}"
    bio = ""
    try:
        if hasattr(user, "bio") and user.bio:
            bio = truncate(user.bio, 128)
    except Exception as error:
        print(f"Error accessing bio: {error}")

    # The lines in badge order; the optional ones only when there's something to show.
    text_lines = [
        f"Username: {username}",
        f"Display Name: {display_name} {server_nick}".strip(),
        f"Discord ID: {discord_id}",
        f"Discord member since: {created_at}"
    ]
    if interaction.guild and server_join:
        text_lines.append(f"Server member since: {server_join}")
    if activity:
        text_lines.append(activity)
    if bio:
        text_lines.append(f"Bio: {bio}")
    return text_lines

def build_server_info(interaction: discord.Interaction) -> str:
    """Return the footer text, "Server name (server ID)", or "" outside a server."""
    # Footer: current server info (only if in a guild)
    server_info = ""
    if interaction.guild:
        server_info = f"{interaction.guild.name} ({interaction.guild.id})"
    return server_info

def fit_font(draw: ImageDraw.Draw, text_lines: list, font_source) -> ImageFont.FreeTypeFont:
    """
    Return the font at the largest size, from 40 down to 10, at which every line fits
    in the text area. Below 10 it stops shrinking, even if a line is still too wide.
    """
    # Determine a font size that allows each line to fit in the available width.
    font_size = 40
    text_area_width = BADGE_WIDTH - TEXT_AREA_X - MARGIN

    # Start with the maximum font size and decrement until all text fits.
    while True:
        font = get_truetype_font(font_source, font_size)
        all_fit = True
        for line in text_lines:
            line_width, line_height = get_text_size(draw, line, font)
            if line_width > text_area_width:
                all_fit = False
                break
        if all_fit or font_size <= 10:
            break
        font_size -= 1
    return font

def draw_text_lines(draw: ImageDraw.Draw, text_lines: list, font: ImageFont.FreeTypeFont):
    """Draw the lines of user details down the right side of the badge, in black."""
    # Draw each text line with at least 2px spacing.
    current_y = MARGIN
    for line in text_lines:
        line_width, line_height = get_text_size(draw, line, font)
        draw.text((TEXT_AREA_X, current_y), line, font=font, fill="black")
        current_y += line_height + LINE_SPACING

def draw_footer(draw: ImageDraw.Draw, server_info: str, font_source):
    """Draw the server name and ID in small black text in the bottom right corner."""
    footer_font = get_truetype_font(font_source, 14)
    footer_width, footer_height = get_text_size(draw, server_info, footer_font)
    draw.text((BADGE_WIDTH - footer_width - MARGIN, BADGE_HEIGHT - footer_height - MARGIN), server_info, font=footer_font, fill="black")

def add_qr_code(badge: Image.Image):
    """Paste a small QR code for https://globalfurry.tv/ in the top right corner of the badge."""
    try:
        qr_code = qrcode.make("https://globalfurry.tv/")
        qr_size = 80
        qr_code = qr_code.resize((qr_size, qr_size))
        badge.paste(qr_code, (BADGE_WIDTH - qr_size - MARGIN, MARGIN))
    except Exception as error:
        print(f"Error generating QR code: {error}")

def badge_to_file(badge: Image.Image) -> discord.File:
    """Save the badge as a PNG in memory and wrap it as the Discord file profile.png."""
    buffer = io.BytesIO()
    badge.save(buffer, format="PNG")
    buffer.seek(0)
    return discord.File(fp=buffer, filename="profile.png")

# --- The Cog with the /profile Command ---

class Profile(commands.Cog):
    """The cog that holds the /profile command."""

    def __init__(self, bot: commands.Bot):
        """Keep a reference to the bot, for logging."""
        self.bot = bot

    @app_commands.command(name="profile", description="Generate a custom ID badge profile")
    @app_commands.describe(
        user="User to generate the profile for (defaults to you)",
        font_url="Optional direct link to a .ttf font file from Google Fonts (default is Microsoft Yahei)"
    )
    async def profile(self, interaction: discord.Interaction, user: discord.Member = None, font_url: str = None):
        """
        Draw a 900 x 450 ID badge for a user (you, if no user is given) and send it as profile.png.

        Left: their avatar. Right: their details. Behind: their banner or accent colour.
        In a server, the server's name and ID go in the bottom right corner.
        """
        await interaction.response.defer()  # defer to allow time for image generation
        user = user or interaction.user

        # Create base badge image (RGBA)
        badge = Image.new("RGBA", (BADGE_WIDTH, BADGE_HEIGHT))

        # BACKGROUND: Use profile banner image if available, else banner color, else default.
        background = await build_background(user)
        badge.paste(background, (0, 0))

        # LEFT SIDE: User Avatar, with rounded corners and a white border.
        avatar_image = await fetch_avatar(interaction, user)
        bordered_avatar = frame_avatar(avatar_image)
        badge.paste(bordered_avatar, (MARGIN, MARGIN), bordered_avatar)

        # TEXT INFO (Right Side): the font, the lines, the largest size that fits, then the footer.
        draw = ImageDraw.Draw(badge)
        font_source = await load_font_source(font_url)
        text_lines = build_text_lines(interaction, user)
        server_info = build_server_info(interaction)
        font = fit_font(draw, text_lines, font_source)
        draw_text_lines(draw, text_lines, font)
        # Draw footer (server name and ID) at bottom right if in a guild.
        if interaction.guild and server_info:
            draw_footer(draw, server_info, font_source)

        # QR CODE: If executed in the server with a specific ID, add a small QR at the top right.
        if interaction.guild and interaction.guild.id == QR_CODE_GUILD_ID:
            add_qr_code(badge)

        # Save the final badge image to a BytesIO buffer and send as a PNG file.
        file = badge_to_file(badge)
        await interaction.followup.send(file=file)
        await log_action(self.bot, interaction)

async def setup(bot):
    """Add the Profile cog to the bot (discord.py calls this when it loads the extension)."""
    await bot.add_cog(Profile(bot))
