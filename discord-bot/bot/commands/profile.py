import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import io
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import qrcode
import random
from core.logger import log_action

# --- Helper Functions ---

async def download_bytes(url: str) -> io.BytesIO:
    """Download bytes from a URL and return a BytesIO object."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return io.BytesIO(await resp.read())
    return None

async def fetch_image(url: str) -> Image.Image:
    """Download an image from a URL and return a Pillow Image in RGBA mode."""
    try:
        data = await download_bytes(url)
        if data:
            return Image.open(data).convert("RGBA")
    except Exception as e:
        print(f"Error fetching image from {url}: {e}")
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
    return text if len(text) <= limit else text[:limit]

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

# --- The Cog with the /profile Command ---

class Profile(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="profile", description="Generate a custom ID badge profile")
    @app_commands.describe(
        user="User to generate the profile for (defaults to you)",
        font_url="Optional direct link to a .ttf font file from Google Fonts (default is Microsoft Yahei)"
    )
    async def profile(self, interaction: discord.Interaction, user: discord.Member = None, font_url: str = None):
        await interaction.response.defer()  # defer to allow time for image generation
        user = user or interaction.user

        # -----------------------------------------------------------
        # Settings and dimensions
        badge_width, badge_height = 900, 450  # size of the ID badge
        margin = 20
        left_area_width = badge_width // 2
        text_area_x = left_area_width + margin
        line_spacing = 5

        # Create base badge image (RGBA)
        badge = Image.new("RGBA", (badge_width, badge_height))
        
        # -----------------------------------------------------------
        # BACKGROUND: Use profile banner image if available, else banner color, else default.
        try:
            banner_img = None
            banner_url = None
            if hasattr(user, "banner") and user.banner:
                banner_url = user.banner.url
            if banner_url:
                banner_img = await fetch_image(banner_url)
                if banner_img:
                    banner_img = banner_img.resize((badge_width, badge_height))
                    banner_img = banner_img.filter(ImageFilter.GaussianBlur(radius=10))
            if not banner_img:
                # Use accent color if available; default to #fedc00 if not.
                color = getattr(user, "accent_color", None) or "#fedc00"
                banner_img = Image.new("RGBA", (badge_width, badge_height), color)
        except Exception as e:
            print(f"Error with banner info: {e}")
            banner_img = Image.new("RGBA", (badge_width, badge_height), "#fedc00")
        badge.paste(banner_img, (0, 0))

        # -----------------------------------------------------------
        # LEFT SIDE: User Avatar
        avatar_img = None
        try:
            # In servers, use the display avatar (which may be a server-specific one)
            if interaction.guild and hasattr(user, "display_avatar"):
                avatar_url = user.display_avatar.url
            else:
                avatar_url = user.avatar.url if user.avatar else None

            if avatar_url:
                avatar_img = await fetch_image(avatar_url)
            if not avatar_img:
                avatar_img = await get_fallback_avatar()
                # Set a random pastel background for the fallback
                pastel = (random.randint(200, 255), random.randint(200, 255), random.randint(200, 255))
                temp = Image.new("RGBA", avatar_img.size, pastel)
                temp.paste(avatar_img, (0, 0), avatar_img)
                avatar_img = temp
        except Exception as e:
            print(f"Error fetching avatar: {e}")
            avatar_img = await get_fallback_avatar()

        # If the avatar image has transparency, composite it on a white background.
        if avatar_img.mode in ("RGBA", "LA"):
            bg = Image.new("RGBA", avatar_img.size, (255, 255, 255, 255))
            bg.paste(avatar_img, mask=avatar_img.split()[3])
            avatar_img = bg

        # Resize avatar to fit (with some margin) in left half.
        target_avatar_width = left_area_width - 2 * margin
        target_avatar_height = badge_height - 2 * margin
        avatar_img = avatar_img.resize((target_avatar_width, target_avatar_height))

        # Create rounded corners for the avatar.
        corner_radius = 20
        mask_img = create_rounded_mask(avatar_img.size, corner_radius)
        avatar_img.putalpha(mask_img)

        # Add a white border around the avatar.
        border_size = 5
        bordered_size = (avatar_img.width + 2 * border_size, avatar_img.height + 2 * border_size)
        bordered_avatar = Image.new("RGBA", bordered_size, (0, 0, 0, 0))
        # Draw white rounded rectangle as the border.
        border_mask = create_rounded_mask(bordered_size, corner_radius + border_size)
        border_draw = ImageDraw.Draw(bordered_avatar)
        border_draw.rounded_rectangle((0, 0) + bordered_size, radius=corner_radius + border_size, fill="white")
        bordered_avatar.paste(avatar_img, (border_size, border_size), avatar_img)

        # Paste the avatar (with border) onto the left side.
        badge.paste(bordered_avatar, (margin, margin), bordered_avatar)

        # -----------------------------------------------------------
        # TEXT INFO (Right Side)
        draw = ImageDraw.Draw(badge)
        current_y = margin

        # Download custom font if a URL is provided; otherwise, use the default.
        # (The URL should directly point to a .ttf file.)
        font_source = None
        if font_url:
            try:
                font_bytes = await download_bytes(font_url)
                if font_bytes:
                    font_source = font_bytes
            except Exception as e:
                print(f"Error downloading custom font: {e}")
        # Use default font file if custom font not available.
        if not font_source:
            default_font_url = "https://raw.githubusercontent.com/dolbydu/font/master/unicode/Microsoft%20Yahei.ttf"
            try:
                font_bytes = await download_bytes(default_font_url)
                if font_bytes:
                    font_source = font_bytes
            except Exception as e:
                print(f"Error downloading default font: {e}")
                # Fallback to local file if available
                font_source = "MicrosoftYaHei.ttf"

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
        except Exception as e:
            print(f"Error accessing bio: {e}")
        
        # Footer: current server info (only if in a guild)
        server_info = ""
        if interaction.guild:
            server_info = f"{interaction.guild.name} ({interaction.guild.id})"
        
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

        # Determine a font size that allows each line to fit in the available width.
        max_font_size = 40
        text_area_width = badge_width - text_area_x - margin

        # Start with the maximum font size and decrement until all text fits.
        while True:
            font = get_truetype_font(font_source, max_font_size)
            all_fit = True
            for line in text_lines:
                w, h = get_text_size(draw, line, font)
                if w > text_area_width:
                    all_fit = False
                    break
            if all_fit or max_font_size <= 10:
                break
            max_font_size -= 1

        # Draw each text line with at least 2px spacing.
        current_y = margin
        for line in text_lines:
            w, h = get_text_size(draw, line, font)
            draw.text((text_area_x, current_y), line, font=font, fill="black")
            current_y += h + line_spacing

        # Draw footer (server name and ID) at bottom right if in a guild.
        if interaction.guild and server_info:
            footer_font = get_truetype_font(font_source, 14)
            fw, fh = get_text_size(draw, server_info, footer_font)
            draw.text((badge_width - fw - margin, badge_height - fh - margin), server_info, font=footer_font, fill="black")

        # -----------------------------------------------------------
        # QR CODE: If executed in the server with a specific ID, add a small QR at the top right.
        if interaction.guild and interaction.guild.id == 576590416296542249:
            try:
                qr = qrcode.make("https://globalfurry.tv/")
                qr_size = 80
                qr = qr.resize((qr_size, qr_size))
                badge.paste(qr, (badge_width - qr_size - margin, margin))
            except Exception as e:
                print(f"Error generating QR code: {e}")

        # -----------------------------------------------------------
        # Save the final badge image to a BytesIO buffer and send as a PNG file.
        buffer = io.BytesIO()
        badge.save(buffer, format="PNG")
        buffer.seek(0)
        file = discord.File(fp=buffer, filename="profile.png")
        await interaction.followup.send(file=file)
        await log_action(self.bot, interaction)

async def setup(bot):
    await bot.add_cog(Profile(bot))
