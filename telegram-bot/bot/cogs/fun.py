import random

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
        await event.reply("Please ask a question. Example: /8ball Will I be lucky today?")
    else:
        response = random.choice(responses)
        await event.reply(f"🎱 {response}")
