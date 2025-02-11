import asyncio
from telethon import TelegramClient, events
import os
from .config import API_ID, API_HASH, BOT_TOKEN, LOG_CHANNEL_ID
from .logger import log_event
import requests

# Import commands from the cogs
from .cogs.fun import command_8ball, command_coin, command_randnum, command_roll, handle_coin_guess, command_cat, command_dog, command_fox
from .cogs.info import command_botinfo, handle_botinfo_callback
from .cogs.general import command_start, command_help, command_ping
from .cogs.botowner import command_dm, command_broadcast
from .cogs.moderation import command_ban, command_unban

def set_bot_commands():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setMyCommands"

    commands = [
        {"command": "start", "description": "Start the bot"},
        {"command": "help", "description": "Show help information"},
        {"command": "ping", "description": "Check bot latency"},
        {"command": "botinfo", "description": "Get information about the bot"},
        {"command": "8ball", "description": "Get a random answer to a question"},
        {"command": "coin", "description": "Flip a coin"},
        {"command": "randnum", "description": "Generate a random number between two values"},
        {"command": "rnum", "description": "Alias for /randnum"},
        {"command": "roll", "description": "Roll a specified number of dice with a specified number of sides"},
        {"command": "cat", "description": "You like kitties, don't you? This command shows you a random cat image."},
        {"command": "dog", "description": "You like puppies, don't you? This command shows you a random dog image."},
        {"command": "fox", "description": "Yip? This command shows you a random fluffy fox image."},
        {"command": "ban", "description": "Ban a user"},
        {"command": "unban", "description": "Unban a user"},
        {"command": "dm", "description": "Send a private message to another user (Owner only)"},
        {"command": "broadcast", "description": "Send a message to all users who interacted with the bot (Owner only)"}
    ]

    response = requests.post(url, json={"commands": commands})
    
    if response.status_code == 200:
        print("Bot commands set successfully!")
    else:
        print(f"Failed to set commands: {response.text}")

class HelloBot:
    def __init__(self, api_id, api_hash, bot_token, log_channel_id):
        self.client = TelegramClient("HelloBotSession", api_id, api_hash).start(bot_token=bot_token)
        self.log_channel_id = log_channel_id
        self.bot_username = None  # To store the bot's username dynamically

    async def fetch_bot_username(self):
        """Fetch and store the bot's username dynamically."""
        me = await self.client.get_me()
        self.bot_username = me.username.lower()
            
    def run(self):
        @self.client.on(events.NewMessage)
        async def message_handler(event):
            # Ensure bot username is fetched before processing any messages
            if not self.bot_username:
                await self.fetch_bot_username()

            # Mapping of commands to their handlers
            commands = {
                "start": command_start,
                "help": command_help,
                "ping": command_ping,
                "8ball": command_8ball,
                "coin": command_coin,
                "randnum": command_randnum,
                "rnum": command_randnum,  # Alias
                "roll": command_roll,
                "cat": command_cat,
                "dog": command_dog,
                "fox": command_fox,
                "botinfo": command_botinfo,
                "ban": command_ban,
                "unban": command_unban,
                "dm": command_dm,
                "broadcast": command_broadcast,
            }

            # Extract and clean the command
            raw_command = event.raw_text.split()[0][1:].lower()
            if "@" in raw_command:
                command, mentioned_bot = raw_command.split("@", 1)
                if mentioned_bot != self.bot_username:
                    return  # Ignore commands meant for a different bot
            else:
                command = raw_command
            # Get the handler for the command or log the event if no handler is found
            handler = commands.get(command)
            if handler:
                await handler(event, self.client)
            else:
                await log_event(event, self.client, LOG_CHANNEL_ID, bot_reply=None)
        
        # Register the callback query handler for inline buttons
        @self.client.on(events.CallbackQuery)
        async def callback_handler(event):
            action = event.data.decode("utf-8")

            # Handle botinfo buttons
            if action in ["list_users", "list_channels", "list_groups"]:
                await handle_botinfo_callback(event, self.client)
            # Handle coin-related guesses
            elif action.startswith("guess_"):
                await handle_coin_guess(event, self.client)

        print("HelloBot is now running...")
        self.client.run_until_disconnected()

if __name__ == "__main__":
    set_bot_commands()
    bot = HelloBot(API_ID, API_HASH, BOT_TOKEN, LOG_CHANNEL_ID)
    bot.run()
