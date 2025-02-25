import os

USERS_FILE = "users.txt"

# Ensure users.txt exists or create it
def ensure_users_file():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w") as f:
            pass

# Update known users by fetching all members from all guilds
async def update_known_users(bot):
    ensure_users_file()
    known_users = set()

    for guild in bot.guilds:
        async for member in guild.fetch_members(limit=None):
            known_users.add(str(member.id))

    # Save the known users to the file
    with open(USERS_FILE, "w") as f:
        f.write("\n".join(known_users))

# Get known users from users.txt
def get_known_users():
    ensure_users_file()
    with open(USERS_FILE, "r") as f:
        return f.read().splitlines()
