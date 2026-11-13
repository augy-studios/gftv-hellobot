import sys
from telethon import Button
from ..config import BOT_OWNER_ID, LOG_CHANNEL_ID
from ..logger import log_event

# Info commands

async def command_botinfo(event, client):
    """
    /botinfo
    Displays general bot information.
    """
    # Step 1: log the command, then collect the bot's details.
    await log_event(event, client, LOG_CHANNEL_ID)

    bot_entity = await client.get_me()
    python_version = sys.version.split()[0]
    library_used = "Telethon"

    known_users = await count_lines("users.txt")
    groups = await count_lines("groups.txt")
    channels = await count_lines("channels.txt")

    # Step 2: build the info message.
    info_text = (
        f"🤖 **Bot Information**\n"
        f"**Bot Name:** {bot_entity.first_name}\n"
        f"**Python Version:** {python_version}\n"
        f"**Library Used:** {library_used}\n"
        f"**Known Users:** {known_users}\n"
        f"**Groups Joined:** {groups}\n"
        f"**Channels Joined:** {channels}\n"
    )

    # Step 3: the owner also gets buttons that list users, channels and groups.
    if event.sender_id == BOT_OWNER_ID:
        buttons = [
            [Button.inline("List Known Users", b"list_users")],
            [Button.inline("List Channels", b"list_channels")],
            [Button.inline("List Groups", b"list_groups")]
        ]
        await event.reply(info_text, buttons=buttons)
    else:
        await event.reply(info_text)

async def handle_botinfo_callback(event, client):
    """
    Handles button interactions from the botinfo command.
    """
    action = event.data.decode("utf-8")

    if action == "list_users":
        response = await get_list("users.txt", "No known users.")
    elif action == "list_channels":
        response = await get_list("channels.txt", "No channels found.")
    elif action == "list_groups":
        response = await get_list("groups.txt", "No groups found.")
    else:
        response = "Invalid action."

    await event.answer()
    await event.edit(response)
    await log_event(event, client, LOG_CHANNEL_ID, bot_reply=response)

async def get_list(file_name, empty_message):
    """
    Reads a file and returns its contents as a formatted list.
    """
    try:
        with open(file_name, "r") as list_file:
            # Build the list of non-empty lines, stripped of whitespace.
            lines = [line.strip() for line in list_file if line.strip()]
            if lines:
                return "\n".join(lines)
            return empty_message
    except FileNotFoundError:
        return empty_message

async def count_lines(file_name):
    """
    Count the number of lines in a file.
    """
    try:
        with open(file_name, "r") as count_file:
            # Count one for every line in the file.
            return sum(1 for _ in count_file)
    except FileNotFoundError:
        return 0
