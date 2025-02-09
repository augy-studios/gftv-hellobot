from telethon.tl.functions.channels import EditBannedRequest
from telethon.tl.types import ChatBannedRights
from telethon.errors import ChatAdminRequiredError, UserIdInvalidError, ChatWriteForbiddenError
import re

async def command_ban(event, client):
    """
    /ban <username|user_id> [reason]
    Bans a user from the group. The user executing this command must have admin permissions.
    """
    if not await check_admin_rights(event, client):
        await event.reply("You don't have permission to use this command.")
        return

    # Parse command arguments
    args = event.raw_text.split(' ', 2)
    if len(args) < 2:
        await event.reply("Invalid syntax. Use /ban <username|user_id> [reason].")
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
        await event.reply(f"User {target_user} has been banned.\nReason: {reason}")

    except UserIdInvalidError:
        await event.reply("Invalid user. Please provide a valid username or user ID.")
    except ChatAdminRequiredError:
        await event.reply("I need to be an admin to execute this command.")
    except ChatWriteForbiddenError:
        await event.reply("I cannot perform this action because I don't have permission to write in this chat.")
    except Exception as e:
        await event.reply(f"An error occurred: {e}")

async def command_unban(event, client):
    """
    /unban <username|user_id>
    Unbans a user from the group. The user executing this command must have admin permissions.
    """
    if not await check_admin_rights(event, client):
        await event.reply("You don't have permission to use this command.")
        return

    # Parse command arguments
    args = event.raw_text.split(' ', 1)
    if len(args) < 2:
        await event.reply("Invalid syntax. Use /unban <username|user_id>.")
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
        await event.reply(f"User {target_user} has been unbanned.")

    except UserIdInvalidError:
        await event.reply("Invalid user. Please provide a valid username or user ID.")
    except ChatAdminRequiredError:
        await event.reply("I need to be an admin to execute this command.")
    except ChatWriteForbiddenError:
        await event.reply("I cannot perform this action because I don't have permission to write in this chat.")
    except Exception as e:
        await event.reply(f"An error occurred: {e}")

async def check_admin_rights(event, client):
    """
    Checks if the user executing the command has admin/moderator rights in the group.
    """
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
