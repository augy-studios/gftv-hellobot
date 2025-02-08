import time
import random
from .config import BOT_OWNER_ID

async def handle_command(command: str, event, client):
    """
    Handle commands based on the command text (e.g. 'start', 'ping', 'help', etc.).
    """
    if command == "start":
        await command_start(event, client)
    elif command == "help":
        await command_help(event, client)
    elif command == "ping":
        await command_ping(event, client)
    elif command == "8ball":
        await command_8ball(event, client)
    elif command == "dm":
        await command_dm(event, client)
    elif command == "broadcast":
        await command_broadcast(event, client)
    else:
        await event.reply("Unknown command. Try /help")

async def command_start(event, client):
    """
    /start command.
    """
    await event.reply("Hello! I am HelloBot. Type /help to see what I can do.")

async def command_help(event, client):
    """
    /help command.
    Sends the list of commands. Extra commands shown to the bot owner.
    """
    if event.sender_id == BOT_OWNER_ID:
        help_text = (
            "Available Commands:\n"
            "/start - Greet the user.\n"
            "/help - Show this help message.\n"
            "/ping - Check the bot's latency.\n"
            "/8ball <question> - Get a random answer to a question.\n"
            "/dm <user_id/username> <message> - Send a private message to another user (Owner only).\n"
            "/broadcast <message> - Send a message to all users who interacted with the bot (Owner only).\n"
        )
    else:
        help_text = (
            "Available Commands:\n"
            "/start - Greet the user.\n"
            "/help - Show this help message.\n"
            "/ping - Check the bot's latency.\n"
            "/8ball <question> - Get a random answer to a question.\n"
        )
    await event.reply(help_text)

async def command_ping(event, client):
    """
    Example /ping command to check latency (ping).
    """
    start_time = time.time()
    message = await event.reply("Pong!")
    end_time = time.time()
    
    latency_ms = (end_time - start_time) * 1000
    await message.edit(f"Pong! Latency: {latency_ms:.2f} ms")

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

async def command_dm(event, client):
    """
    /dm <user_id/username> <message>
    Sends a private message to a user. Restricted to the bot's owner.
    """
    # Ensure only the bot's owner can execute this command
    if event.sender_id != BOT_OWNER_ID:
        await event.reply("You are not authorised to use this command.")
        return

    # Split command into target and message
    args = event.raw_text.split(' ', 2)
    if len(args) < 3:
        await event.reply("Invalid syntax. Use /dm <user_id/username> <message>.")
        return
    
    target_user = args[1]
    message = args[2]

    try:
        # Check if target_user is a username or an ID
        if target_user.startswith('@'):
            user_entity = await client.get_input_entity(target_user)  # Username resolution
        else:
            user_entity = await client.get_input_entity(int(target_user))  # User ID resolution
        
        # Send the DM
        await client.send_message(user_entity, message)
        await event.reply(f"Message successfully sent to {target_user}.")
    except Exception as e:
        await event.reply(f"Failed to send the message: {e}")

async def command_broadcast(event, client):
    """
    /broadcast <message>
    Sends a message to all users who have interacted with the bot.
    Restricted to the bot's owner.
    """
    if event.sender_id != BOT_OWNER_ID:
        await event.reply("You are not authorised to use this command.")
        return
    args = event.raw_text.split(' ', 1)
    if len(args) < 2:
        await event.reply("Invalid syntax. Use /broadcast <message>.")
        return
    message = args[1]
    successful_sends = 0
    failed_sends = 0
    try:
        # Read user IDs from the file
        with open("users.txt", "r") as f:
            user_ids = [int(line.strip()) for line in f]
        # Send the broadcast message to each user
        for user_id in user_ids:
            try:
                await client.send_message(user_id, message)
                successful_sends += 1
            except Exception as e:
                print(f"Failed to send to {user_id}: {e}")
                failed_sends += 1
        await event.reply(
            f"Broadcast completed.\n"
            f"✅ Successfully sent to {successful_sends} users.\n"
            f"❌ Failed to send to {failed_sends} users."
        )
    except Exception as e:
        await event.reply(f"An error occurred: {e}")
