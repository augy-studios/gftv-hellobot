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
    await log_event(event, client, LOG_CHANNEL_ID)

    bot_entity = await client.get_me()
    python_version = sys.version.split()[0]
    library_used = "Telethon"

    known_users = await count_lines("users.txt")
    groups = await count_lines("groups.txt")
    channels = await count_lines("channels.txt")

    info_text = (
        f"🤖 **Bot Information**\n"
        f"**Bot Name:** {bot_entity.first_name}\n"
        f"**Python Version:** {python_version}\n"
        f"**Library Used:** {library_used}\n"
        f"**Known Users:** {known_users}\n"
        f"**Groups Joined:** {groups}\n"
        f"**Channels Joined:** {channels}\n"
    )

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
        with open(file_name, "r") as f:
            lines = [line.strip() for line in f if line.strip()]
            return "\n".join(lines) if lines else empty_message
    except FileNotFoundError:
        return empty_message

async def count_lines(file_name):
    """
    Count the number of lines in a file.
    """
    try:
        with open(file_name, "r") as f:
            return sum(1 for _ in f)
    except FileNotFoundError:
        return 0
