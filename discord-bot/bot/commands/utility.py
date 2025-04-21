import io
import cv2
import numpy as np
import trimesh
from io import BytesIO
from PIL import Image
import discord
from discord.ext import commands
from discord import app_commands, Interaction
from typing import Tuple
import random
import re
import math
import aiohttp
import pdfkit
import imgkit
import zipfile
from bs4 import BeautifulSoup
import shutil
import asyncio
import os
import requests
import urllib.parse
from urllib.parse import urljoin, urlparse
from core.logger import log_action


# --------------------------
# Country Checklist Handlers
# --------------------------
class CountryChecklistView(discord.ui.View):
    def __init__(self, continents: dict[str, list[str]], owner: discord.User):
        super().__init__(timeout=None)
        self.continents = continents
        self.owner = owner
        self.init_message: discord.Message
        self.selections: dict[str, set[str]] = {c: set() for c in continents}
        for c in continents:
            self.add_item(ContinentButton(c))
        self.add_item(DoneButton())

    async def update_embed(self, interaction: discord.Interaction):
        # edit the original checklist embed
        msg = self.init_message
        embed = msg.embeds[0]
        for idx, cont in enumerate(self.continents):
            chosen = sorted(self.selections[cont])
            value = ", ".join(chosen) if chosen else "None"
            embed.set_field_at(idx, name=cont, value=value, inline=True)
        await msg.edit(embed=embed, view=self)

class ContinentButton(discord.ui.Button):
    def __init__(self, continent: str):
        super().__init__(style=discord.ButtonStyle.primary, label=continent)
        self.continent = continent

    async def callback(self, interaction: discord.Interaction):
        view: CountryChecklistView = self.view  # type: ignore
        if interaction.user.id != view.owner.id:
            return await interaction.response.send_message("This isn't yours.", ephemeral=True)

        countries = view.continents[self.continent]
        paged = PaginatedSelectView(countries, self.continent, view)
        await interaction.response.send_message(
            f"Select in **{self.continent}** (page 1/{paged.total_pages}):",
            view=paged,
            ephemeral=True
        )

class PaginatedSelectView(discord.ui.View):
    def __init__(
        self,
        options: list[str],
        continent: str,
        parent: CountryChecklistView
    ):
        super().__init__(timeout=None)
        self.options = options
        self.continent = continent
        self.parent = parent
        self.page_size = 25
        self.pages = [options[i:i+self.page_size] for i in range(0, len(options), self.page_size)]
        self.page = 0
        self.total_pages = len(self.pages)
        self.page_selections: dict[int, set[str]] = {}
        self.update_components()

    def update_components(self):
        self.clear_items()
        opts = [discord.SelectOption(label=o, value=o) for o in self.pages[self.page]]
        self.add_item(PageSelect(opts, self))
        prev_btn = PrevButton()
        prev_btn.disabled = self.page == 0
        self.add_item(prev_btn)
        next_btn = NextButton()
        next_btn.disabled = self.page == self.total_pages - 1
        self.add_item(next_btn)
        self.add_item(SubmitButton(self.continent, self.parent))

    async def refresh(self, interaction: discord.Interaction):
        content = f"Select in **{self.continent}** (page {self.page+1}/{self.total_pages}):"
        await interaction.response.edit_message(content=content, view=self)

class PageSelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption], view: PaginatedSelectView):
        super().__init__(placeholder="Choose countries…", min_values=0, max_values=len(options), options=options)
        self.pview = view

    async def callback(self, interaction: discord.Interaction):
        self.pview.page_selections[self.pview.page] = set(self.values)
        await interaction.response.defer()

class PrevButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.secondary, label="◀️")

    async def callback(self, interaction: discord.Interaction):
        view: PaginatedSelectView = self.view  # type: ignore
        view.page -= 1
        view.update_components()
        await view.refresh(interaction)

class NextButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.secondary, label="▶️")

    async def callback(self, interaction: discord.Interaction):
        view: PaginatedSelectView = self.view  # type: ignore
        view.page += 1
        view.update_components()
        await view.refresh(interaction)

class SubmitButton(discord.ui.Button):
    def __init__(self, continent: str, parent: CountryChecklistView):
        super().__init__(style=discord.ButtonStyle.success, label="Submit")
        self.continent = continent
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        # acknowledge interaction to avoid double response
        await interaction.response.defer(ephemeral=True)
        pview: PaginatedSelectView = self.view  # type: ignore
        # combine selections from all pages
        selected = set().union(*pview.page_selections.values()) if pview.page_selections else set()
        self.parent.selections[self.continent] = selected
        # update the main embed checklist
        await self.parent.update_embed(interaction)
        # remove the ephemeral selection view
        await interaction.message.edit(content="✅ Selection saved.", view=None)

class DoneButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.success, label="Done")

    async def callback(self, interaction: discord.Interaction):
        view: CountryChecklistView = self.view  # type: ignore
        if interaction.user.id != view.owner.id:
            return await interaction.response.send_message("This isn't yours.", ephemeral=True)

        total_selected = sum(len(v) for v in view.selections.values())
        total_countries = sum(len(v) for v in view.continents.values())
        pct = (total_selected / total_countries * 100) if total_countries else 0

        # edit the original ephemeral message
        msg = view.init_message
        embed = msg.embeds[0]
        embed.add_field(
            name="Results",
            value=(
                f"{view.owner.mention} has been to **{total_selected}**/"
                f"**{total_countries}** ({pct:.2f}%) of the world!"
            ),
            inline=False
        )
        await msg.edit(embed=embed, view=None)
        # broadcast publicly
        await msg.channel.send(embed=embed)

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._load_task = bot.loop.create_task(self._load_countries())
        self.valid_users = [269080651599314944, 292864211825197056, 543846099971080192]
        # These sets help avoid downloading the same page or resource more than once.
        self.visited_pages = set()
        self.downloaded_resources = {}  # resource_url -> local_path
    
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

    # -------------------------
    # Country Checklist Handler
    # -------------------------
    async def _load_countries(self):
        """Fetch from restcountries.com and map continents to country lists."""
        url = "https://restcountries.com/v3.1/all"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
        continents = {}
        for entry in data:
            name = entry.get("name", {}).get("common")
            conts = entry.get("continents")
            if name and conts:
                continents.setdefault(conts[0], []).append(name)
        for c in continents:
            continents[c].sort()
        self.continents = continents

    @app_commands.command(
        name="countrychecklist",
        description="Mark which countries you've been to, by continent."
    )
    async def countrychecklist(self, interaction: discord.Interaction):
        await self._load_task
        embed = discord.Embed(
            title="Which countries have I been to?",
            color=discord.Color.blurple()
        )
        for continent in self.continents:
            embed.add_field(name=continent, value="None", inline=True)

        view = CountryChecklistView(self.continents, interaction.user)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        # store the initial message reference for later editing
        view.init_message = await interaction.original_response()

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
        arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
        # Map intensities [0,255] to height levels [0, thickness]
        hmap = (img.astype(np.float32) / 255.0 * thickness).astype(np.int32)
        h, w = hmap.shape
        # Build voxel grid
        vol = np.zeros((h, w, thickness), dtype=bool)
        for z in range(thickness):
            vol[:, :, z] = hmap > z
        # Create mesh via marching cubes (requires scikit-image)
        mesh = trimesh.voxel.ops.matrix_to_marching_cubes(vol)

        # OBJ / STL export
        if output_type in ('obj', 'stl'):
            mesh_bytes = mesh.export(file_type=output_type)
            return mesh_bytes, f"output.{output_type}"

        # Render scene for images
        scene = mesh.scene()
        if output_type == 'png':
            img_bytes = scene.save_image(resolution=(512, 512))
            return img_bytes, "output.png"
        elif output_type == 'gif':
            frames = []
            for angle in range(0, 360, 60):
                scene.camera.transform = trimesh.transformations.euler_matrix(0, 0, np.radians(angle))
                frame_bytes = scene.save_image(resolution=(512, 512))
                frames.append(Image.open(BytesIO(frame_bytes)))
            gif_buf = BytesIO()
            frames[0].save(gif_buf, format='GIF', save_all=True,
                           append_images=frames[1:], duration=100, loop=0)
            return gif_buf.getvalue(), "output.gif"

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
        await interaction.response.defer()

        # Read and process
        img_bytes = await image.read()
        result_bytes, sugg_name = self.convert_to_3d(
            image_bytes=img_bytes,
            thickness=thickness,
            output_type=output_type.value,
        )
        # Construct new filename from original
        base_name = image.filename.rsplit('.', 1)[0]
        ext = sugg_name.rsplit('.', 1)[-1]
        new_filename = f"{base_name}_3dified.{ext}"

        # Send file
        file = discord.File(io.BytesIO(result_bytes), filename=new_filename)
        await interaction.followup.send(file=file)
        await log_action(self.bot, interaction)

    # -------------------------
    # ----- Scrape Handler ----
    # -------------------------
    def get_local_path(self, url: str, base_output_dir: str) -> str:
        parsed = requests.utils.urlparse(url)
        path = parsed.path
        if path.endswith("/") or path == "":
            path = os.path.join(path, "index.html")
        local_path = os.path.join(base_output_dir, parsed.netloc, path.lstrip("/"))
        return local_path

    def download_file(self, url: str, local_path: str) -> bool:
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True
        except Exception as e:
            print(f"Error downloading {url}: {e}")
            return False

    def scrape_page(self, url: str, base_output_dir: str, base_domain: str):
        if url in self.visited_pages:
            return
        self.visited_pages.add(url)
        print(f"Scraping: {url}")

        try:
            resp = requests.get(url)
            resp.raise_for_status()
        except Exception as e:
            print(f"Error accessing {url}: {e}")
            return

        ctype = resp.headers.get("Content-Type", "")
        if "text/html" not in ctype:
            local_path = self.get_local_path(url, base_output_dir)
            self.download_file(url, local_path)
            return

        soup = BeautifulSoup(resp.text, "html.parser")

        def process_resource(tag, attr):
            if not tag.has_attr(attr):
                return
            orig = tag[attr]
            resource_url = requests.compat.urljoin(url, orig)
            local_res_path = self.get_local_path(resource_url, base_output_dir)
            if resource_url not in self.downloaded_resources:
                if self.download_file(resource_url, local_res_path):
                    self.downloaded_resources[resource_url] = local_res_path
            local_page_path = self.get_local_path(url, base_output_dir)
            rel = os.path.relpath(local_res_path, os.path.dirname(local_page_path))
            tag[attr] = rel

        for img in soup.find_all("img", src=True):
            process_resource(img, "src")
        for script in soup.find_all("script", src=True):
            process_resource(script, "src")
        for link in soup.find_all("link", href=True):
            if link.get("rel") and "stylesheet" in link.get("rel"):
                process_resource(link, "href")
        for media in soup.find_all(["video", "audio"], src=True):
            process_resource(media, "src")

        local_html = self.get_local_path(url, base_output_dir)
        os.makedirs(os.path.dirname(local_html), exist_ok=True)
        with open(local_html, "w", encoding="utf-8") as f:
            f.write(str(soup))

        for a in soup.find_all("a", href=True):
            link = requests.compat.urljoin(url, a["href"])
            if requests.utils.urlparse(link).netloc == base_domain:
                self.scrape_page(link, base_output_dir, base_domain)

    def upload_to_transfersh(self, file_path: str) -> str:
        filename = os.path.basename(file_path)
        with open(file_path, 'rb') as f:
            resp = requests.put(f'https://transfer.sh/{filename}', data=f)
            resp.raise_for_status()
            return resp.text.strip()

    @app_commands.command(
        name="scrape",
        description="Download a site (HTML + resources) and package it locally, then return a ZIP."
    )
    async def scrape(self, interaction: Interaction, url: str):
        if interaction.user.id not in self.valid_users:
            await interaction.response.send_message(
                "You do not have permission to execute this command.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "Scraping started... this may take some time.",
            ephemeral=True
        )

        base_output_dir = "scraped_site"
        os.makedirs(base_output_dir, exist_ok=True)
        domain = requests.utils.urlparse(url).netloc
        self.visited_pages.clear()
        self.downloaded_resources.clear()

        self.scrape_page(url, base_output_dir, domain)

        # create ZIP archive
        zip_path = shutil.make_archive(base_output_dir, 'zip', base_output_dir)
        size = os.path.getsize(zip_path)

        if size <= 50 * 1024 * 1024:
            # under 50MB – send directly
            await interaction.followup.send(file=discord.File(zip_path))
        else:
            # over 50MB – upload externally
            await interaction.followup.send(
                "Archive exceeds 50MB, uploading to transfer.sh..."
            )
            link = self.upload_to_transfersh(zip_path)
            await interaction.followup.send(f"Here's your file: {link}")
        await log_action(self.bot, interaction)

        # clean up
        shutil.rmtree(base_output_dir, ignore_errors=True)
        os.remove(zip_path)
        await asyncio.sleep(5)
        if os.path.exists(zip_path):
            os.remove(zip_path)
        if os.path.exists(base_output_dir):
            shutil.rmtree(base_output_dir, ignore_errors=True)

async def setup(bot):
    await bot.add_cog(Utility(bot))
