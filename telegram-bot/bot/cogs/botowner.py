from ..config import BOT_OWNER_ID, LOG_CHANNEL_ID
from ..logger import log_event

async def command_dm(event, client):
    """
    /dm <user_id/username> <message>
    Sends a private message to a user. Restricted to the bot's owner.
    """

    if event.sender_id != BOT_OWNER_ID:
        bot_reply = "You are not authorised to use this command."
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)
        return

    args = event.raw_text.split(' ', 2)
    if len(args) < 3:
        bot_reply = "Invalid syntax. Use /dm <user_id/username> <message>."
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)
        return
    
    target_user, message = args[1], args[2]

    try:
        user_entity = await client.get_input_entity(target_user) if target_user.startswith('@') else await client.get_input_entity(int(target_user))
        await client.send_message(user_entity, message)
        bot_reply = f"Message successfully sent to {target_user}."
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)
    except Exception as e:
        bot_reply = f"Failed to send the message: {e}"
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)

async def command_broadcast(event, client):
    """
    /broadcast <message>
    Sends a message to all users who have interacted with the bot.
    Restricted to the bot's owner.
    """

    await log_event(event, client, LOG_CHANNEL_ID)

    if event.sender_id != BOT_OWNER_ID:
        bot_reply = "You are not authorised to use this command."
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)
        return

    args = event.raw_text.split(' ', 1)
    if len(args) < 2:
        bot_reply = "Invalid syntax. Use /broadcast <message>."
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)
        return

    message = args[1]
    successful_sends, failed_sends = 0, 0
    try:
        with open("users.txt", "r") as f:
            user_ids = [int(line.strip()) for line in f]
        for user_id in user_ids:
            try:
                await client.send_message(user_id, message)
                successful_sends += 1
            except Exception as e:
                failed_sends += 1

        bot_reply = f"Broadcast completed.\n✅ Successfully sent to {successful_sends} users.\n❌ Failed to send to {failed_sends} users."
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)
    except Exception as e:
        bot_reply = f"An error occurred: {e}"
        await event.reply(bot_reply)
        await log_event(event, client, LOG_CHANNEL_ID, bot_reply=bot_reply)
