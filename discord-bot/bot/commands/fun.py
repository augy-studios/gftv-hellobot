import discord
from discord.ext import commands
from discord import app_commands
import random
import re
import requests
from core.logger import log_action

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # List of possible responses for the 8ball command
    responses = [
        "It is certain.",
        "It is decidedly so.",
        "Without a doubt.",
        "Yes - definitely.",
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
        "Very doubtful.",
        "Never gonna give you up.",
        "Never gonna give you up.",
        "Never gonna give you up.",
        "Never gonna give you up.",
        "Never gonna give you up."
    ]

    @app_commands.command(name="8ball", description="Ask the magic 8-ball any question.")
    async def eight_ball(self, interaction: discord.Interaction, question: str):
        response = random.choice(self.responses)
        embed = discord.Embed(title="🎱 Magic 8ball", color=discord.Color(random.randint(0, 0xFFFFFF)))
        embed.add_field(name="Question", value=question, inline=False)
        embed.add_field(name="Response", value=response, inline=False)
        await interaction.response.send_message(embed=embed)
        await log_action(self.bot, interaction)

    @app_commands.choices(guess=[
        app_commands.Choice(name="HEADS", value="HEADS"),
        app_commands.Choice(name="TAILS", value="TAILS")
    ])
    @app_commands.command(name="coin", description="Flip a coin and optionally guess the result.")
    async def coin(self, interaction: discord.Interaction, guess: str = None):
        result = random.choice(["HEADS", "TAILS"])
        if guess:
            if guess.upper() == result:
                response = f"🪙 The coin landed on: **{result}**\n🎉 You guessed it right!"
            else:
                response = f"🪙 The coin landed on: **{result}**\n😞 You guessed **{guess}**, better luck next time!"
        else:
            response = f"🪙 The coin landed on: **{result}**"

        await interaction.response.send_message(response)
        await log_action(self.bot, interaction)

    @app_commands.command(name="cat", description="You like kitties, don't you? This command shows you a random cat image.")
    async def cat(self, interaction: discord.Interaction):
        response = requests.get("https://api.thecatapi.com/v1/images/search").json()
        image_url = response[0]["url"]
        embed = discord.Embed(title="🐱 Meow!", color=discord.Color(random.randint(0, 0xFFFFFF)))
        embed.set_image(url=image_url)
        await interaction.response.send_message(embed=embed)
        await log_action(self.bot, interaction)
    
    @app_commands.command(name="dog", description="You like puppies, don't you? This command shows you a random dog image.")
    async def dog(self, interaction: discord.Interaction):
        response = requests.get("https://api.thedogapi.com/v1/images/search").json()
        image_url = response[0]["url"]
        embed = discord.Embed(title="🐶 Woof!", color=discord.Color(random.randint(0, 0xFFFFFF)))
        embed.set_image(url=image_url)
        await interaction.response.send_message(embed=embed)
        await log_action(self.bot, interaction)

    @app_commands.command(name="fox", description="Yip? This command shows you a random fluffy fox image.")
    async def fox(self, interaction: discord.Interaction):
        response = requests.get("https://randomfox.ca/floof/").json()
        image_url = response["image"]
        embed = discord.Embed(title="🦊 Yip!", color=discord.Color(random.randint(0, 0xFFFFFF)))
        embed.set_image(url=image_url)
        await interaction.response.send_message(embed=embed)
        await interaction.response.send_message(image_url)
        await log_action(self.bot, interaction)

async def setup(bot):
    await bot.add_cog(Fun(bot))
