from telethon.tl.functions.channels import EditBannedRequest
from telethon.tl.types import ChatBannedRights
from telethon.errors import ChatAdminRequiredError, UserIdInvalidError, ChatWriteForbiddenError
import re
from ..config import LOG_CHANNEL_ID
from ..logger import log_event

async def command_ban(event, client):
    """
    /ban <username|user_id> [reason]
    Bans a user from the group. The user executing this command must have admin permissions.
    """

    if not await check_admin_rights(event, client):
        bot_reply = "You don't have permission to use this command."
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)
        return

    # Parse command arguments
    args = event.raw_text.split(' ', 2)
    if len(args) < 2:
        bot_reply = "Invalid syntax. Use /ban <username|user_id> [reason]."
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)
        return

    target_user = args[1]
    reason = args[2] if len(args) == 3 else "No reason provided."

    try:
        # Resolve target user
        target = await client.get_input_entity(target_user)

        # Ban the user
        rights = ChatBannedRights(
            until_date=None,  # Permanent ban
            view_messages=True  # Disable access to messages
        )
        await client(EditBannedRequest(event.chat_id, target, rights))
        bot_reply = f"User {target_user} has been banned.\nReason: {reason}"
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)

    except UserIdInvalidError:
        bot_reply = "Invalid user. Please provide a valid username or user ID."
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)
    except ChatAdminRequiredError:
        bot_reply = "You need to be an admin to execute this command."
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)
    except ChatWriteForbiddenError:
        bot_reply = "You cannot perform this action because you don't have permission to write in this chat."
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)
    except Exception as e:
        bot_reply = f"An error occurred: {e}"
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)

async def command_unban(event, client):
    """
    /unban <username|user_id>
    Unbans a user from the group. The user executing this command must have admin permissions.
    """

    if not await check_admin_rights(event, client):
        bot_reply = "You don't have permission to use this command."
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)
        return

    # Parse command arguments
    args = event.raw_text.split(' ', 1)
    if len(args) < 2:
        bot_reply = "Invalid syntax. Use /unban <username|user_id>."
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)
        return

    target_user = args[1]

    try:
        # Resolve target user
        target = await client.get_input_entity(target_user)

        # Remove ban (reset rights)
        rights = ChatBannedRights(
            until_date=None,
            view_messages=False  # Allow viewing messages again (unban)
        )
        await client(EditBannedRequest(event.chat_id, target, rights))
        bot_reply = f"User {target_user} has been unbanned."
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)

    except UserIdInvalidError:
        bot_reply = "Invalid user. Please provide a valid username or user ID."
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)
    except ChatAdminRequiredError:
        bot_reply = "You need to be an admin to execute this command."
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)
    except ChatWriteForbiddenError:
        bot_reply = "You cannot perform this action because you don't have permission to write in this chat."
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)
    except Exception as e:
        bot_reply = f"An error occurred: {e}"
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)

async def check_admin_rights(event, client):
    """
    Checks if the user executing the command has admin/moderator rights in the group.
    """

    await log_event(event, client, LOG_CHANNEL_ID)

    chat = await event.get_chat()
    sender = await event.get_sender()

    if hasattr(chat, "creator") and chat.creator and sender.id == chat.creator_id:
        return True  # Group creator always has full rights

    try:
        # Check the user's participant status
        participant = await client.get_participant(event.chat_id, sender.id)
        if participant and getattr(participant, "admin_rights", None):
            return True  # The user is an admin with rights
        return False  # No admin rights
    except Exception:
        return False  # Unable to verify rights
