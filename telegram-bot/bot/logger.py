from telethon import events, TelegramClient
from .config import LOG_CHANNEL_ID

async def log_event(event: events.NewMessage.Event, client: TelegramClient, log_channel_id: int, bot_reply: str = None):
    """
    Logs the details of an incoming message or command to the specified log channel,
    including the bot's reply if provided.
    """

    # Determine the event type and extract details accordingly
    if isinstance(event, events.NewMessage.Event):
        message_text = event.raw_text
    elif isinstance(event, events.CallbackQuery.Event):
        message_text = f"Button clicked: {event.data.decode('utf-8')}"
    else:
        message_text = "Unknown event type"
    
    # Basic info from the event
    sender = await event.get_sender()
    sender_id = sender.id if sender else None
    sender_username = sender.username if sender else "N/A"
    
    chat = await event.get_chat()
    chat_id = event.chat_id
    chat_title = getattr(chat, 'title', None)  # for groups/channels
    message_text = event.raw_text
    
    # If you need a clickable message link for groups/supergroups
    # for private chats this won't be valid
    try:
        # The link format for supergroups (and channels) is t.me/c/<local_id>/<message_id>
        # local_id is chat_id without the -100 prefix for channels
        # For normal groups, a more robust approach might be `event.message.link`
        message_link = event.message.link
    except:
        # Fallback: no direct link available
        message_link = "No link"
    
    if chat_id == LOG_CHANNEL_ID:
        return  # Skip logging messages from the log channel
    
    # Check if there are attachments (photos, documents, etc.)
    attachment_info = "Yes (media attached)" if event.message.media else "No"
    
    # Build the log message
    log_text = (
        f"**New Message/Command Logged**\n"
        f"**Chat ID:** {chat_id}\n"
        f"**Chat Title:** {chat_title}\n"
        f"**Sender ID:** {sender_id}\n"
        f"**Sender Username:** @{sender_username}\n"
        f"**Message ID:** {event.message.id}\n"
        f"**Message Link:** {message_link}\n"
        f"**Has Attachment?:** {attachment_info}\n"
        f"**Content:** ```{message_text}```"
    )

    if bot_reply:
        log_text += f"\n**Bot's Reply:** ```{bot_reply}```"
    
    # Send the log to the specified log channel
    try:
        # Properly resolve the entity
        await client.send_message(log_channel_id, log_text, link_preview=True)
        print(f"Logging from Channel ID: {chat_id}")
        print(f"Logging to Channel ID: {log_channel_id}")
        print(f"---")
    except Exception as e:
        print(f"Failed to send log message: {e}")
