import random
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

async def command_coinflip(event, client):
    """
    /coinflip or /cf
    Returns HEADS or TAILS randomly.
    """

    result = random.choice(["HEADS", "TAILS"])
    bot_reply = f"🪙 The coin landed on: **{result}**"
    await event.reply(bot_reply)
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
