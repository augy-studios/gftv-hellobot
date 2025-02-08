
import discord
from discord.ext import commands
from discord import app_commands
import random
from core.logger import log_action

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # List of possible responses for the 8ball command
    responses = [
        "It is certain.",
        "It is decidedly so.",
        "Without a doubt.",
        "Yes – definitely.",
        "You may rely on it.",
        "As I see it, yes.",
        "Most likely.",
        "Outlook good.",
        "Yes.",
        "Signs point to yes.",
        "Reply hazy, try again.",
        "Ask again later.",
        "Better not tell you now.",
        "Cannot predict now.",
        "Concentrate and ask again.",
        "Don't count on it.",
        "My reply is no.",
        "My sources say no.",
        "Outlook not so good.",
        "Very doubtful."
    ]

    @app_commands.command(name="8ball", description="Ask the magic 8-ball any question.")
    async def eight_ball(self, interaction: discord.Interaction, question: str):
        response = random.choice(self.responses)
        await interaction.response.send_message(f"🎱 {response}")
        await log_action(self.bot, interaction)

async def setup(bot):
    await bot.add_cog(Fun(bot))
