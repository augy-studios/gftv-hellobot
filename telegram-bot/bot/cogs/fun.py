import random
from ..logger import log_event

# Fun commands

async def command_8ball(event, client):
    """
    /8ball <question>
    Responds with a random answer to the given question.
    """

    await log_event(event, client)

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
        await event.reply("Please ask a question. Example: /8ball Will I be lucky today?")
    else:
        response = random.choice(responses)
        await event.reply(f"🎱 {response}")

async def command_coinflip(event, client):
    """
    /coinflip or /cf
    Returns HEADS or TAILS randomly.
    """

    await log_event(event, client)

    result = random.choice(["HEADS", "TAILS"])
    await event.reply(f"🪙 The coin landed on: **{result}**")


async def command_randnum(event, client):
    """
    /randnum <min> <max> or /rnum <min> <max>
    Returns a random number within the user-specified range.
    """

    await log_event(event, client)
    
    args = event.raw_text.split()
    if len(args) != 3:
        await event.reply("Invalid syntax. Use /randnum <min> <max>.")
        return

    try:
        min_num = int(args[1])
        max_num = int(args[2])
        if min_num > max_num:
            await event.reply("The minimum value cannot be greater than the maximum value.")
            return

        random_number = random.randint(min_num, max_num)
        await event.reply(f"🎲 Your random number between {min_num} and {max_num} is: **{random_number}**")

    except ValueError:
        await event.reply("Please provide valid integers for the minimum and maximum values.")