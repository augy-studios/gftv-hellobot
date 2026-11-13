#!/usr/bin/env python3
"""Import every cog of both bots with stand-in settings and no network.

Each bot has a package called `bot`, so each one is imported in its own
subprocess. Nothing logs in to Discord or Telegram, and `token.env` is never
read: the checks run from an empty temporary folder with stub env values.

Usage: python3 tools/check_imports.py
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Modules imported per bot (relative to the bot's own folder).
DISCORD_MODULES = [
    "config",
    "user_utils",
    "core.logger",
    "bot.commands.admin",
    "bot.commands.fun",
    "bot.commands.games",
    "bot.commands.general",
    "bot.commands.generative",
    "bot.commands.info",
    "bot.commands.miscellaneous",
    "bot.commands.moderation",
    "bot.commands.profile",
    "bot.commands.utility",
]
TELEGRAM_MODULES = [
    "bot.config",
    "bot.logger",
    "bot.cogs.botowner",
    "bot.cogs.fun",
    "bot.cogs.general",
    "bot.cogs.info",
    "bot.cogs.moderation",
    "bot.main",  # importing it only defines things: the bot starts under __main__
]

# Stand-in values: harmless, and never a real token.
STUB_ENV = {
    "DISCORD_TOKEN": "stub-token",
    "LOG_GUILD_ID": "1",
    "LOG_CHANNEL_ID": "2",
    "BOT_OWNER_ID": "3",
    "API_ID": "4",
    "API_HASH": "stub-hash",
    "BOT_TOKEN": "stub-token",
}


def block_network():
    """Make any socket connection fail, so an import that reaches out is caught."""
    import socket

    def refuse(*args, **kwargs):
        raise RuntimeError("network access during import check")

    socket.socket.connect = refuse
    socket.socket.connect_ex = refuse
    socket.getaddrinfo = refuse


# Packages that are stubbed only when the real one can't be loaded on this machine
# (for example a compiled wheel that doesn't support the local OS). name -> attributes.
STUB_IF_BROKEN = {
    "skimage.metrics": ["structural_similarity"],
}


def stub_broken_packages():
    """Replace any package from STUB_IF_BROKEN that fails to import with an empty stand-in."""
    import importlib
    import types
    from unittest import mock

    for name, attributes in STUB_IF_BROKEN.items():
        try:
            module = importlib.import_module(name)
            for attribute in attributes:  # some packages load lazily, so touch each name
                getattr(module, attribute)
        except Exception as error:  # noqa: BLE001
            print(f"  stub  {name} (real package won't load here: {type(error).__name__})")
            parts = name.split(".")
            for depth in range(1, len(parts) + 1):
                parent_name = ".".join(parts[:depth])
                sys.modules[parent_name] = types.ModuleType(parent_name)
            for attribute in attributes:
                setattr(sys.modules[name], attribute, mock.MagicMock())


def import_modules(bot_folder, modules):
    """Child process: import each module and report failures. Returns the exit code."""
    sys.path.insert(0, bot_folder)
    block_network()
    stub_broken_packages()
    failures = 0
    for module in modules:
        try:
            __import__(module)
            print(f"  ok    {module}")
        except BaseException as error:  # noqa: BLE001 - report everything
            failures += 1
            print(f"  FAIL  {module}: {type(error).__name__}: {error}")
    return 1 if failures else 0


def run_bot(label, folder, modules):
    """Parent: run one bot's imports in a clean subprocess. Returns True on success."""
    print(f"{label}:")
    environment = {key: value for key, value in os.environ.items() if not key.startswith("PYTHONPATH")}
    environment.update(STUB_ENV)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    with tempfile.TemporaryDirectory() as empty_folder:
        # Run from an empty folder so no token.env or data file can be found or created.
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--child", str(REPO_ROOT / folder), *modules],
            cwd=empty_folder,
            env=environment,
        )
    return result.returncode == 0


def main():
    """Entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        sys.exit(import_modules(sys.argv[2], sys.argv[3:]))
    discord_ok = run_bot("discord-bot", "discord-bot", DISCORD_MODULES)
    telegram_ok = run_bot("telegram-bot", "telegram-bot", TELEGRAM_MODULES)
    if discord_ok and telegram_ok:
        print("check_imports: all imports ok")
        return 0
    print("check_imports: FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
