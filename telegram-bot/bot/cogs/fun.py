import asyncio
import random
import requests
from telethon import Button, client, events
from ..config import LOG_CHANNEL_ID
from ..logger import log_event

# Fun commands

async def command_8ball(event, client):
    """
    /8ball <question>
    Responds with a random answer to the given question.
    """

    responses = [
        "It is certain.",
        "Without a doubt.",
        "Yes, definitely.",
        "You may rely on it.",
        "Most likely.",
        "Outlook good.",
        "Yes.",
        "Signs point to yes.",
        "Reply hazy, try again.",
        "Ask again later.",
        "Better not tell you now.",
        "Cannot predict now.",
        "Don't count on it.",
        "My reply is no.",
        "My sources say no.",
        "Outlook not so good.",
        "Very doubtful."
    ]

    question = event.raw_text[6:].strip()  # Get the question part after "/8ball "
    if not question:
        bot_reply = "Please ask a question. Example: /8ball Will I be lucky today?"
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)
    else:
        response = random.choice(responses)
        bot_reply = f"🎱 {response}"
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)

async def command_coin(event, client):
    """
    /coin
    Flips a coin with options for the user to select their guess using inline buttons.
    """

    # Display the buttons for the user to select a guess
    buttons = [
        [Button.inline("HEADS", b"guess_heads"), Button.inline("TAILS", b"guess_tails")]
    ]
    bot_reply = "🪙 Flip a coin! Select your guess below."
    await event.reply(bot_reply, buttons=buttons)
    await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)

async def handle_coin_guess(event, client):
    """
    Handles the user's guess when they select an option using the inline buttons.
    """
    user_guess = event.data.decode("utf-8").split("_")[1].upper()
    result = random.choice(["HEADS", "TAILS"])

    if user_guess == result:
        bot_reply = f"🪙 The coin landed on **{result}**. You guessed **{user_guess}**. 🎉 You win!"
    else:
        bot_reply = f"🪙 The coin landed on **{result}**. You guessed **{user_guess}**. 😞 You lose."

    await event.answer("Coin flipped!", alert=False)
    await event.edit(bot_reply)
    await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)

async def command_randnum(event, client):
    """
    /randnum <min> <max> or /rnum <min> <max>
    Returns a random number within the user-specified range.
    """

    args = event.raw_text.split()
    if len(args) != 3:
        bot_reply = "Invalid syntax. Use /randnum <min> <max>."
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)
        return

    try:
        min_num = int(args[1])
        max_num = int(args[2])
        if min_num > max_num:
            bot_reply = "The minimum value cannot be greater than the maximum value."
            await event.reply(bot_reply)
            await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)
            return

        random_number = random.randint(min_num, max_num)
        bot_reply = f"🎲 Your random number between {min_num} and {max_num} is: **{random_number}**"
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)

    except ValueError:
        bot_reply = "Please provide valid integers for the minimum and maximum values."
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)

async def command_roll(event, client):
    """
    /roll <number_of_dices>d<number_of_sides>
    Rolls specified number of dice with specified number of sides and returns the list of results and the total.
    Examples:
    - /roll d20 rolls one die with 20 sides.
    - /roll 4d8 rolls 4 dice with 8 sides.
    """

    # Parse the input to extract the number of dice and sides
    message = event.raw_text.strip().lower()
    if len(message.split()) != 2 or "d" not in message:
        bot_reply = "Invalid syntax. Use /roll <number_of_dices>d<number_of_sides>. Example: /roll 2d6 or /roll d20"
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)
        return

    try:
        # Extract the number of dice and sides using the "d" separator
        dice_input = message.split()[1]
        if dice_input.startswith("d"):
            num_dice = 1
            num_sides = int(dice_input[1:])
        else:
            num_dice, num_sides = map(int, dice_input.split("d"))

        # Validate the inputs
        if num_dice <= 0 or num_sides <= 0:
            bot_reply = "Both the number of dice and the number of sides must be greater than 0."
            await event.reply(bot_reply)
            await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)
            return

        if num_dice > 100 or num_sides > 100:
            bot_reply = "The number of dice and sides must be less than or equal to 100."
            await event.reply(bot_reply)
            await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)
            return

        # Roll the dice and calculate the results
        results = [random.randint(1, num_sides) for _ in range(num_dice)]
        total = sum(results)

        # Build the reply message
        reply = "\n".join([f"Dice {i + 1}: {result}" for i, result in enumerate(results)])
        reply += f"\n**Total:** {total}"

        await event.reply(reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=reply)

    except ValueError:
        bot_reply = "Invalid input. Please provide integers for the number of dice and sides."
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)

    try:
        await asyncio.wait_for(command_roll(event, client), timeout=10.0)

    except asyncio.TimeoutError:
        bot_reply = "The roll command timed out. Please try again."
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)

async def command_cat(event, client):
    """
    /cat
    You like kitties, don't you? This command shows you a random cat image.
    """
    try:
        response = requests.get("https://api.thecatapi.com/v1/images/search")
        data = response.json()
        image_url = data[0]['url']
        bot_reply = f"🐱 Here's a random cat:\n{image_url}"
    except Exception as e:
        bot_reply = f"Failed to fetch a cat image. Error: {e}"
    
    await event.reply(bot_reply)
    await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)

async def command_dog(event, client):
    """
    /dog
    You like puppies, don't you? This command shows you a random dog image.
    """
    try:
        response = requests.get("https://api.thedogapi.com/v1/images/search")
        data = response.json()
        image_url = data[0]['url']
        bot_reply = f"🐶 Here's a random dog:\n{image_url}"
    except Exception as e:
        bot_reply = f"Failed to fetch a dog image. Error: {e}"
    
    await event.reply(bot_reply)
    await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)

async def command_fox(event, client):
    """
    /fox
    Yip? This command shows you a random fluffy fox image.
    """
    try:
        response = requests.get("https://randomfox.ca/floof/")
        data = response.json()
        image_url = data['image']
        bot_reply = f"🦊 Here’s a random fox:\n{image_url}"
    except Exception as e:
        bot_reply = f"Failed to fetch a fox image. Error: {e}"
    
    await event.reply(bot_reply)
    await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)