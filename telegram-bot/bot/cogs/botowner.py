from ..config import BOT_OWNER_ID, LOG_CHANNEL_ID
from ..logger import log_event


async def reply_and_log(event, client, bot_reply):
    """Reply to the user's message, then write the same reply to the log channel."""
    await event.reply(bot_reply)
    await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)


async def command_dm(event, client):
    """
    /dm <user_id/username> <message>
    Sends a private message to a user. Restricted to the bot's owner.
    """

    # Step 1: only the bot's owner may use this command.
    if event.sender_id != BOT_OWNER_ID:
        await reply_and_log(event, client, "You are not authorised to use this command.")
        return

    # Step 2: split the message into the command, the target user and the text to send.
    command_arguments = event.raw_text.split(' ', 2)
    if len(command_arguments) < 3:
        await reply_and_log(event, client, "Invalid syntax. Use /dm <user_id/username> <message>.")
        return

    target_user, message = command_arguments[1], command_arguments[2]

    # Step 3: look the user up (by @username or numeric ID) and send the message.
    try:
        if target_user.startswith('@'):
            user_entity = await client.get_input_entity(target_user)
        else:
            user_entity = await client.get_input_entity(int(target_user))
        await client.send_message(user_entity, message)
        await reply_and_log(event, client, f"Message successfully sent to {target_user}.")
    except Exception as error:
        await reply_and_log(event, client, f"Failed to send the message: {error}")


async def command_broadcast(event, client):
    """
    /broadcast <message>
    Sends a message to all users who have interacted with the bot.
    Restricted to the bot's owner.
    """

    await log_event(event, client, LOG_CHANNEL_ID)

    # Step 1: only the bot's owner may use this command.
    if event.sender_id != BOT_OWNER_ID:
        await reply_and_log(event, client, "You are not authorised to use this command.")
        return

    # Step 2: split the message into the command and the text to broadcast.
    command_arguments = event.raw_text.split(' ', 1)
    if len(command_arguments) < 2:
        await reply_and_log(event, client, "Invalid syntax. Use /broadcast <message>.")
        return

    message = command_arguments[1]
    successful_sends, failed_sends = 0, 0

    # Step 3: send the message to every user ID saved in users.txt, counting successes and failures.
    try:
        with open("users.txt", "r") as users_file:
            # Build the list of user IDs, one per line of users.txt.
            user_ids = [int(line.strip()) for line in users_file]
        for user_id in user_ids:
            try:
                await client.send_message(user_id, message)
                successful_sends += 1
            except Exception:
                failed_sends += 1

        bot_reply = f"Broadcast completed.\n✅ Successfully sent to {successful_sends} users.\n❌ Failed to send to {failed_sends} users."
        await reply_and_log(event, client, bot_reply)
    except Exception as error:
        await reply_and_log(event, client, f"An error occurred: {error}")
