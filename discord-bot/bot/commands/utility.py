import io
import discord
from discord.ext import commands
from discord import app_commands
import random
import re
import math
import aiohttp
import pdfkit
import imgkit
import zipfile
from bs4 import BeautifulSoup
import asyncio
import os
import urllib.parse
from core.logger import log_action

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="randnum", description="Generate a random number between a given range.")
    @app_commands.describe(min_num="The minimum number", max_num="The maximum number")
    async def randnum(self, interaction: discord.Interaction, min_num: int, max_num: int):
        if min_num > max_num:
            await interaction.response.send_message("❌ The minimum number cannot be greater than the maximum number.", ephemeral=True)
            return

        result = random.randint(min_num, max_num)
        await interaction.response.send_message(f"🎲 Random number between {min_num} and {max_num}: **{result}**")
        await log_action(self.bot, interaction)

    @app_commands.command(name="math", description="Solve a math expression.")
    @app_commands.describe(expression="The math expression to solve")
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
    @app_commands.describe(dice="The dice format (e.g., 4d8 or d20)")
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
    @app_commands.describe(link_or_id="The YouTube video link or ID")
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
    @app_commands.describe(message="The message to repeat")
    async def say(self, interaction: discord.Interaction, message: str):
        """Repeats what the user says without replying directly."""
        await interaction.response.send_message("Processing...", delete_after=1)
        await interaction.channel.send(message.replace("\\\\n", "\n"))
        await log_action(self.bot, interaction)

    @app_commands.command(
        name="scrape",
        description="Scrape a webpage and return assets in a ZIP file."
    )
    @app_commands.describe(url="The URL of the webpage to scrape")
    async def scrape(self, interaction: discord.Interaction, url: str):

        """Scrapes a webpage and returns its HTML, PDF and image snapshot in a ZIP file."""

        # Validate the URL input
        if not url or url.strip() == "":
            await interaction.response.send_message("Error: The URL cannot be null or empty.", ephemeral=True)
            return

        await interaction.response.send_message("Scraping the webpage, please wait...", ephemeral=True)

        try:
            async with aiohttp.ClientSession() as session:
                # Fetch the original HTML content
                async with session.get(url) as response:
                    html = await response.text()

                if not html or html.strip() == "":
                    raise ValueError("Received null or empty HTML content from the provided URL.")

                # --- Prepare HTML for PDF and Image Generation ---
                # Insert a <base> tag so that wkhtmltopdf and wkhtmltoimage can resolve relative URLs
                soup_pdf = BeautifulSoup(html, 'html.parser')
                head_pdf = soup_pdf.find('head')
                if not head_pdf:
                    head_pdf = soup_pdf.new_tag('head')
                    soup_pdf.insert(0, head_pdf)
                if not head_pdf.find('base'):
                    base_tag = soup_pdf.new_tag('base', href=url)
                    head_pdf.insert(0, base_tag)
                html_for_pdf = str(soup_pdf)

                # --- Generate PDF snapshot from the HTML ---
                pdf_options = {
                    'enable-local-file-access': True,
                    'load-error-handling': 'ignore',
                }
                try:
                    pdf_bytes = pdfkit.from_string(html_for_pdf, False, options=pdf_options)
                except Exception as pdf_error:
                    raise ValueError(f"Failed to generate PDF: {pdf_error}")
                if not pdf_bytes:
                    raise ValueError("PDF conversion returned null or empty output.")
                
                # --- Generate Image (PNG) snapshot from the HTML ---
                # Use a different options dictionary for wkhtmltoimage.
                img_options = {
                    'format': 'png'
                }
                try:
                    image_bytes = imgkit.from_string(html_for_pdf, False, options=img_options)
                except Exception as image_error:
                    raise ValueError(f"Failed to generate image snapshot: {image_error}")
                if not image_bytes:
                    raise ValueError("Image conversion returned null or empty output.")

                # --- Prepare Offline HTML Version with Local Assets ---
                soup_offline = BeautifulSoup(html, 'html.parser')
                # (Optional) Insert a base tag for consistency
                head_offline = soup_offline.find('head')
                if not head_offline:
                    head_offline = soup_offline.new_tag('head')
                    soup_offline.insert(0, head_offline)
                if not head_offline.find('base'):
                    base_tag = soup_offline.new_tag('base', href=url)
                    head_offline.insert(0, base_tag)

                # Dictionary to track which resource URLs have been downloaded
                resource_map = {}  # {absolute_url: local_filename}
                # Dictionary to hold downloaded binary content: {local_filename: bytes}
                downloaded_files = {}  # {local_filename: bytes}
                counter = 1  # For generating fallback filenames

                # Tags and attributes to check for assets
                tags_to_process = {
                    'img': 'src',
                    'script': 'src',
                    'link': 'href',
                    'audio': 'src',
                    'video': 'src',
                    'source': 'src',
                }

                # Gather all resource elements that need processing
                resource_elements = []
                for tag_name, attr in tags_to_process.items():
                    for tag in soup_offline.find_all(tag_name):
                        if tag.has_attr(attr):
                            # For <link> tags, process only if they are stylesheets or icons
                            if tag_name == 'link':
                                rel = tag.get('rel', [])
                                if not any(r.lower() in ['stylesheet', 'icon'] for r in rel):
                                    continue
                            resource_elements.append((tag, attr))

                # Define a helper coroutine to download a resource
                async def fetch_resource(session, resource_url):
                    try:
                        async with session.get(resource_url) as res:
                            if res.status == 200:
                                return await res.read()
                    except Exception:
                        return None
                    return None

                # Prepare download tasks for unique resources
                download_tasks = []
                for element, attr in resource_elements:
                    original_url = element[attr]
                    absolute_url = urllib.parse.urljoin(url, original_url)
                    # If we've already processed this resource, reuse the filename
                    if absolute_url in resource_map:
                        local_filename = resource_map[absolute_url]
                    else:
                        # Derive a filename from the URL path
                        parsed = urllib.parse.urlparse(absolute_url)
                        basename = os.path.basename(parsed.path)
                        if not basename:
                            basename = f"resource_{counter}.bin"
                            counter += 1
                        # Ensure uniqueness if the filename already exists
                        if basename in downloaded_files:
                            basename = f"{os.path.splitext(basename)[0]}_{counter}{os.path.splitext(basename)[1]}"
                            counter += 1
                        local_filename = basename
                        resource_map[absolute_url] = local_filename
                        task = asyncio.create_task(fetch_resource(session, absolute_url))
                        download_tasks.append((local_filename, absolute_url, task))
                    # Update the tag to reference the local asset path within the ZIP
                    element[attr] = f"assets/{local_filename}"

                # Execute resource downloads concurrently
                for local_filename, absolute_url, task in download_tasks:
                    content = await task
                    if content:
                        downloaded_files[local_filename] = content
                    else:
                        # Log or handle failed downloads (the asset will be missing in the offline version)
                        print(f"Warning: Failed to download resource: {absolute_url}")

                # Generate the modified offline HTML with updated asset references
                html_for_offline = str(soup_offline)

                # --- Create a ZIP Archive in Memory ---
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    # Add the offline HTML file
                    zip_file.writestr("page.html", html_for_offline)
                    # Add the PDF snapshot
                    zip_file.writestr("page.pdf", pdf_bytes)
                    # Add the image snapshot
                    zip_file.writestr("page.png", image_bytes)
                    # Add each downloaded asset in an 'assets' folder
                    for filename, content in downloaded_files.items():
                        zip_file.writestr(f"assets/{filename}", content)
                zip_buffer.seek(0)

                zip_file_attachment = discord.File(fp=zip_buffer, filename="scraped.zip")
                await interaction.followup.send(f"Here is your scraped content for {url}:", file=zip_file_attachment)

        except Exception as e:
            error_str = str(e)
            if len(error_str) > 1900:
                error_str = error_str[:1900] + "..."
            await interaction.followup.send(f"An error occurred while scraping the page: {error_str}", ephemeral=True)

        await log_action(self.bot, interaction)

async def setup(bot):
    await bot.add_cog(Utility(bot))
