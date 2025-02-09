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
        embed = discord.Embed(title="🎱 Magic 8ball", color=discord.Color(random.randint(0, 0xFFFFFF)))
        embed.add_field(name="Question", value=question, inline=False)
        embed.add_field(name="Response", value=response, inline=False)
        await interaction.response.send_message(embed=embed)
        await log_action(self.bot, interaction)

    # /coinflip command with alias /cf
    @app_commands.command(name="coinflip", description="Flip a coin and get HEADS or TAILS.")
    async def coinflip(self, interaction: discord.Interaction):
        result = random.choice(["HEADS", "TAILS"])
        await interaction.response.send_message(f"🪙 The coin landed on: **{result}**")
        await log_action(self.bot, interaction)
    
    # /randnum command with alias /rnum
    @app_commands.command(name="randnum", description="Generate a random number between a given range.")
    async def randnum(self, interaction: discord.Interaction, min_num: int, max_num: int):
        if min_num > max_num:
            await interaction.response.send_message("❌ The minimum number cannot be greater than the maximum number.", ephemeral=True)
            return

        result = random.randint(min_num, max_num)
        await interaction.response.send_message(f"🎲 Random number between {min_num} and {max_num}: **{result}**")
        await log_action(self.bot, interaction)

async def setup(bot):
    await bot.add_cog(Fun(bot))
