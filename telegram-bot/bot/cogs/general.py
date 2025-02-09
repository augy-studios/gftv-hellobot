import time
from ..config import BOT_OWNER_ID
from ..logger import log_event

async def command_start(event, client):
    """
    /start command.
    """

    await log_event(event, client)

    await event.reply("Hello! I am HelloBot. Type /help to see what I can do.")

async def command_help(event, client):
    """
    /help command.
    Sends the list of commands.
    """

    await log_event(event, client)

    help_text = (
        "Available Commands:\n"
        "**General Commands**\n"
        "/start - Greet the user.\n"
        "/help - Show this help message.\n"
        "/ping - Check the bot's latency.\n"

        "\n**Fun Commands**\n"
        "/8ball <question> - Get a random answer to a question.\n"
        "/coinflip (or /cf) - Flip a coin.\n"
        "/randnum <min> <max> (or /rnum <min> <max>) - Generate a random number between two values.\n"

        "\n**Moderation Commands**\n"
        "/ban <user_id/username> - Ban a user.\n"
        "/unban <user_id/username> - Unban a user.\n"

        "\n**Info Commands**\n"
        "/botinfo - Get information about the bot.\n"
    )

    if event.sender_id == BOT_OWNER_ID:
        help_text += (
            "\n**Owner Commands**\n"
            "/dm <user_id/username> <message> - Send a private message to another user.\n"
            "/broadcast <message> - Send a message to all users who interacted with the bot.\n"
        )

    await event.reply(help_text)

async def command_ping(event, client):
    """
    /ping command to check latency (ping).
    """

    await log_event(event, client)
    
    start_time = time.time()
    message = await event.reply("Pong!")
    latency_ms = (time.time() - start_time) * 1000
    await message.edit(f"Pong! Latency: {latency_ms:.2f} ms")
