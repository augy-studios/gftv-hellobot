import os

USERS_FILE = "users.txt"

# Ensure users.txt exists or create it
def ensure_users_file():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w") as f:
            pass

# Add a user to users.txt if they are not already listed
def add_user_to_file(user_id: int):
    ensure_users_file()
    with open(USERS_FILE, "r") as f:
        existing_users = f.read().splitlines()
    if str(user_id) not in existing_users:
        with open(USERS_FILE, "a") as f:
            f.write(f"{user_id}\n")

# Get known users from users.txt
def get_known_users():
    ensure_users_file()
    with open(USERS_FILE, "r") as f:
        return f.read().splitlines()
