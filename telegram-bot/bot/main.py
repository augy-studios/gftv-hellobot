import asyncio
from telethon import TelegramClient, events
import os
from .config import API_ID, API_HASH, BOT_TOKEN, LOG_CHANNEL_ID
from .logger import log_event
import requests

# Import commands from the cogs
from .cogs.fun import command_8ball, command_coinflip, command_randnum
from .cogs.info import command_botinfo
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
        {"command": "coinflip", "description": "Flip a coin"},
        {"command": "cf", "description": "Alias for /coinflip"},
        {"command": "randnum", "description": "Generate a random number between two values"},
        {"command": "rnum", "description": "Alias for /randnum"},
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

# Call the function to set commands when the bot starts
if __name__ == "__main__":
    set_bot_commands()

class HelloBot:
    def __init__(self, api_id, api_hash, bot_token, log_channel_id):
        self.client = TelegramClient("HelloBotSession", api_id, api_hash).start(bot_token=bot_token)
        self.log_channel_id = log_channel_id
            
    def run(self):
        @self.client.on(events.NewMessage)
        async def message_handler(event):
            # Mapping of commands to their handlers
            commands = {
                "start": command_start,
                "help": command_help,
                "ping": command_ping,
                "8ball": command_8ball,
                "coinflip": command_coinflip,
                "cf": command_coinflip,  # Alias
                "randnum": command_randnum,
                "rnum": command_randnum,  # Alias
                "botinfo": command_botinfo,
                "ban": command_ban,
                "unban": command_unban,
                "dm": command_dm,
                "broadcast": command_broadcast,
            }

            command = event.raw_text.split()[0][1:].lower()
            handler = commands.get(command)
            if handler:
                await handler(event, self.client)
            else:
                await event.reply("Unknown command.")
        
        print("HelloBot is now running...")
        self.client.run_until_disconnected()

if __name__ == "__main__":
    bot = HelloBot(API_ID, API_HASH, BOT_TOKEN, LOG_CHANNEL_ID)
    bot.run()
