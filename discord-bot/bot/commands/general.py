import discord
import random
from discord.ext import commands
from discord import app_commands
from core.logger import log_action

class HelpView(discord.ui.View):
    def __init__(self, pages: list[discord.Embed]):
        super().__init__(timeout=120)
        self.pages = pages
        self.current = 0

        # Navigation buttons
        self.prev_button = discord.ui.Button(label="Previous", style=discord.ButtonStyle.secondary)
        self.page_button = discord.ui.Button(label=f"1/{len(pages)}", style=discord.ButtonStyle.gray, disabled=True)
        self.next_button = discord.ui.Button(label="Next", style=discord.ButtonStyle.secondary)

        # Assign callbacks
        self.prev_button.callback = self.prev_page
        self.next_button.callback = self.next_page

        # Add buttons to view
        self.add_item(self.prev_button)
        self.add_item(self.page_button)
        self.add_item(self.next_button)

        self.update_buttons()

    async def prev_page(self, interaction: discord.Interaction):
        self.current = max(self.current - 1, 0)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    async def next_page(self, interaction: discord.Interaction):
        self.current = min(self.current + 1, len(self.pages) - 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    def update_buttons(self):
        self.prev_button.disabled = (self.current == 0)
        self.next_button.disabled = (self.current == len(self.pages) - 1)
        self.page_button.label = f"{self.current + 1}/{len(self.pages)}"

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.command_ids = {}  # Store command IDs dynamically

    async def fetch_command_ids(self):
        """Fetch and store command IDs after syncing."""
        commands = await self.bot.tree.fetch_commands()
        for cmd in commands:
            self.command_ids[cmd.name] = cmd.id

    @app_commands.command(name="ping", description="Check the bot's latency.")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"Pong! 🏓 Latency: {latency}ms")
        await log_action(self.bot, interaction)

    @app_commands.command(name="hello", description="Learn more about the bot.")
    @app_commands.describe(language="The language to say hello in")
    @app_commands.choices(
        language=[
            app_commands.Choice(name="English", value="en"),
            app_commands.Choice(name="Chinese", value="zh"),
            app_commands.Choice(name="Malay", value="ms"),
            app_commands.Choice(name="Tamil", value="ta"),
            app_commands.Choice(name="Spanish", value="es"),
            app_commands.Choice(name="Indonesian", value="id"),
            app_commands.Choice(name="Norwegian", value="no"),
            app_commands.Choice(name="French", value="fr"),
            app_commands.Choice(name="German", value="de"),
            app_commands.Choice(name="Esperanto", value="eo"),
            app_commands.Choice(name="Traditional Chinese", value="zh-tw"),
            app_commands.Choice(name="Japanese", value="ja"),
            app_commands.Choice(name="Korean", value="ko"),
            app_commands.Choice(name="Portuguese", value="pt"),
            app_commands.Choice(name="Thai", value="th"),
            app_commands.Choice(name="Vietnamese", value="vi"),
            app_commands.Choice(name="Russian", value="ru"),
            app_commands.Choice(name="Tagalog", value="tl")
        ]
    )
    async def hello(self, interaction: discord.Interaction, language: str = "en"):
        hello_messages = {
            "en": "Hi, I'm HelloBot! 👋\nI'm created by GFTV, for GFTV.\nI was born yesterday but I do a kickass job watching over GFTV communities! 😛",
            "zh": "嗨，我是 HelloBot！👋\n我是由 GFTV 创建，为 GFTV 而生。\n我昨天才诞生，但我已经在 GFTV 社区里干得超棒啦！😛",
            "ms": "Hai, saya HelloBot! 👋\nSaya dicipta oleh GFTV, untuk GFTV.\nSaya dilahirkan semalam tetapi saya melakukan kerja yang hebat menjaga komuniti GFTV! 😛",
            "ta": "வணக்கம், நான் ஹலோபாட்! 👋\nநான் ஜிஎஃப்டிவி மூலம் உருவாக்கப்பட்டேன், ஜிஎஃப்டிவி குழுக்களுக்காக.\nநான் நேற்று பிறக்கின்றேன், ஆனால் ஜிஎஃப்டிவி சமூகங்களை காத்திருக்கிறேன்! 😛",
            "es": "¡Hola, soy HelloBot! 👋\nSoy creado por GFTV, para GFTV.\nNací ayer pero hago un trabajo increíble vigilando las comunidades de GFTV! 😛",
            "id": "Hai, saya HelloBot! 👋\nSaya dibuat oleh GFTV, untuk GFTV.\nSaya lahir kemarin tapi saya melakukan pekerjaan yang luar biasa menjaga komunitas GFTV! 😛",
            "no": "Hei, jeg er HelloBot! 👋\nJeg er laget av GFTV, for GFTV.\nJeg ble født i går, men jeg gjør en kjempejobb med å passe på GFTV-samfunnene! 😛",
            "fr": "Salut, je suis HelloBot! 👋\nJe suis créé par GFTV, pour GFTV.\nJe suis né hier mais je fais un travail incroyable en surveillant les communautés GFTV! 😛",
            "de": "Hallo, ich bin HelloBot! 👋\nIch wurde von GFTV erstellt, für GFTV.\nIch wurde gestern geboren, aber ich mache einen großartigen Job, um die GFTV-Gemeinschaften zu überwachen! 😛",
            "eo": "Saluton, mi estas HelloBot! 👋\nMi estas kreita de GFTV, por GFTV.\nMi naskiĝis hieraŭ, sed mi faras bonegan laboron gardante la GFTV-komunumojn! 😛",
            "zh-tw": "嗨，我是 HelloBot！👋\n我是由 GFTV 創建，為 GFTV 而生。\n我昨天才誕生，但我已經在 GFTV 社區裡幹得超棒啦！😛",
            "ja": "こんにちは、私はHelloBotです！👋\n私はGFTVによって作成され、GFTVのために存在します。\n私は昨日生まれましたが、GFTVコミュニティを見守る素晴らしい仕事をしています！😛",
            "ko": "안녕하세요, 저는 HelloBot입니다! 👋\n저는 GFTV에 의해 만들어졌으며, GFTV를 위해 존재합니다.\n저는 어제 태어났지만 GFTV 커뮤니티를 지키는 멋진 일을 하고 있습니다! 😛",
            "pt": "Oi, eu sou o HelloBot! 👋\nFui criado pela GFTV, para a GFTV.\nNasci ontem, mas faço um trabalho incrível cuidando das comunidades da GFTV! 😛",
            "th": "สวัสดี, ฉันคือ HelloBot! 👋\nฉันถูกสร้างโดย GFTV เพื่อ GFTV\nฉันเพิ่งเกิดเมื่อวานนี้ แต่ฉันทำงานได้ยอดเยี่ยมในการดูแลชุมชน GFTV! 😛",
            "vi": "Chào, tôi là HelloBot! 👋\nTôi được tạo ra bởi GFTV, cho GFTV.\nTôi mới sinh ra hôm qua nhưng tôi làm việc rất tốt trong việc giám sát các cộng đồng GFTV! 😛",
            "ru": "Привет, я HelloBot! 👋\nЯ создан GFTV, для GFTV.\nЯ родился вчера, но я отлично справляюсь с наблюдением за сообществами GFTV! 😛",
            "tl": "Kumusta, ako si HelloBot! 👋\nAko ay nilikha ng GFTV, para sa GFTV.\nAko ay ipinanganak kahapon ngunit gumagawa ako ng kahanga-hangang trabaho sa pagbabantay sa mga komunidad ng GFTV! 😛"
        }

        embed = discord.Embed(title="Hello!", color=discord.Color.random())
        embed.description = hello_messages.get(language, hello_messages["en"])
        link_to_add_bot = f"https://discord.com/oauth2/authorize?client_id={self.bot.user.id}"
        embed.add_field(name="Add Me to Your Server", value=f"[Click here!]({link_to_add_bot})")
        link_to_hello = "https://hello.globalfurry.tv/"
        embed.add_field(name="About HelloSpot", value=f"[Learn more about GFTV's HelloSpot!]({link_to_hello})")
        link_to_docs = "https://hellobot.globalfurry.tv/"
        embed.add_field(name="How to Use", value=f"[View the documentation!]({link_to_docs})")
        link_to_status = "https://pages.statusbot.us/id/873989298507120690"
        embed.add_field(name="Bot Status", value=f"[Check the bot's status here!]({link_to_status})")
        link_to_coffee = "https://donate.stripe.com/28o2akeAr3hv0DK6oo"
        embed.add_field(name="Support the Bot", value=f"[Buy me a coffee!]({link_to_coffee})")
        link_to_monthly_support = "https://donate.stripe.com/6oEbKUdwn9FTgCI7st"
        embed.add_field(name="Monthly Support", value=f"[Support us monthly!]({link_to_monthly_support})")
        embed.set_footer(text="Made with ❤️ by GFTV Intl © 2025 All Rights Sniffed • https://globalfurry.tv/")
        await interaction.response.send_message(embed=embed)
        await log_action(self.bot, interaction)

    @app_commands.command(name="help", description="Display a list of available commands categorized by their category.")
    @app_commands.describe(category="Choose a category to see its commands")
    async def help_command(self, interaction: discord.Interaction, category: str | None = None):
        base_embed = discord.Embed(
            title="Help - Available Commands",
            color=discord.Color.random()
        )
        base_embed.set_footer(text="Made with ❤️ by GFTV Intl © 2025 All Rights Sniffed • https://globalfurry.tv/")

        # Collect commands grouped by Cog
        cog_commands: dict[str, list[str]] = {}
        for cog_name, cog in self.bot.cogs.items():
            lines: list[str] = []
            for cmd in cog.get_app_commands():
                cmd_id = self.command_ids.get(cmd.name)
                mention = f"</{cmd.name}:{cmd_id}>" if cmd_id else f"/{cmd.name}"
                lines.append(f"**{mention}** - {cmd.description}\n")
            if lines:
                cog_commands[cog_name] = lines

        # Handle invalid category
        if category and category not in cog_commands:
            await interaction.response.send_message(
                f"❌ No commands found for category: {category}",
                ephemeral=True
            )
            return

        # Build pages with a 1024-character limit per page
        pages_content: list[str] = []
        current_content = ""
        items = ((category, cog_commands[category]),) if category else cog_commands.items()

        for cog_name, lines in items:
            header = f"**{cog_name} Commands**\n"
            # Start new page if header itself doesn't fit
            if current_content and len(current_content) + len(header) > 1024:
                pages_content.append(current_content)
                current_content = ""

            # Ensure header present
            if not current_content.startswith(header):
                current_content += header

            # Add each command line, splitting pages as needed
            for line in lines:
                if len(current_content) + len(line) > 1024:
                    pages_content.append(current_content)
                    current_content = header + line
                else:
                    current_content += line

        if current_content:
            pages_content.append(current_content)

        # Convert to embeds
        pages: list[discord.Embed] = []
        for content in pages_content:
            embed = base_embed.copy()
            embed.description = content
            pages.append(embed)

        # Send paginated view
        view = HelpView(pages)
        await interaction.response.send_message(embed=pages[0], view=view)

    @help_command.autocomplete("category")
    async def help_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=c, value=c)
            for c in self.bot.cogs.keys()
            if current.lower() in c.lower()
        ]

async def setup(bot):
    cog = General(bot)
    await cog.fetch_command_ids()  # Fetch IDs before adding the cog
    await bot.add_cog(cog)
