"""Helpers that keep the list of known users in users.txt."""
import os

USERS_FILE = "users.txt"


def ensure_users_file():
    """Create an empty users.txt if it doesn't exist yet."""
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w", encoding="utf-8"):
            pass


def sort_key_lowercase(user_line):
    """Sort key that ignores upper and lower case."""
    return user_line.lower()


async def update_known_users(bot):
    """Fetch every member of every guild and save them to users.txt as "username (userID)"."""
    ensure_users_file()
    known_users = set()

    # Collect every member of every guild the bot is in
    for guild in bot.guilds:
        async for member in guild.fetch_members(limit=None):
            known_users.add(f"{member.name} ({member.id})")

    # Sort known users alphabetically
    sorted_users = sorted(known_users, key=sort_key_lowercase)

    # Save the sorted known users to the file
    with open(USERS_FILE, "w", encoding="utf-8") as users_file:
        users_file.write("\n".join(sorted_users))


def get_known_users():
    """Return the lines of users.txt as a list."""
    ensure_users_file()
    with open(USERS_FILE, "r", encoding="utf-8") as users_file:
        return users_file.read().splitlines()
