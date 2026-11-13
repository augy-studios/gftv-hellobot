"""Tests for the moderation cog's permission checks in bot/commands/moderation.py.

@commands.has_permissions does nothing on slash commands, so every moderation command now
carries app_commands.checks.has_permissions, and the cog answers a refused caller.
"""
import asyncio
import unittest
from unittest import mock

from discord import app_commands

from bot.commands import moderation


def moderation_commands():
    """Every slash command the Moderation cog defines."""
    return [value for value in vars(moderation.Moderation).values() if isinstance(value, app_commands.Command)]


class PermissionCheckTests(unittest.TestCase):
    """Each moderation command checks the caller's permissions before it runs."""

    def test_every_command_has_a_permission_check(self):
        """All 15 commands carry at least one check."""
        commands = moderation_commands()
        self.assertEqual(len(commands), 15)
        for command in commands:
            with self.subTest(command=command.name):
                self.assertTrue(command.checks, f"/{command.name} has no permission check")

    def test_a_caller_without_the_permission_is_refused(self):
        """The kick check fails for a member without kick_members, and passes with it."""
        kick = vars(moderation.Moderation)["kick"]
        interaction = mock.MagicMock()
        interaction.guild = mock.MagicMock()
        interaction.permissions = mock.MagicMock(kick_members=False)
        with self.assertRaises(app_commands.MissingPermissions):
            kick.checks[0](interaction)
        interaction.permissions = mock.MagicMock(kick_members=True)
        self.assertTrue(kick.checks[0](interaction))

    def test_refused_callers_get_a_reply(self):
        """cog_app_command_error answers a missing permission and a DM, privately."""
        sent = []

        async def send_message(text, **kwargs):
            sent.append((text, kwargs))

        cog = object.__new__(moderation.Moderation)
        interaction = mock.MagicMock()
        interaction.response.is_done.return_value = False
        interaction.response.send_message = send_message
        asyncio.run(cog.cog_app_command_error(interaction, app_commands.MissingPermissions(["kick_members"])))
        asyncio.run(cog.cog_app_command_error(interaction, app_commands.NoPrivateMessage()))
        self.assertEqual(sent[0], ("❌ You need the kick members permission to use this command.", {"ephemeral": True}))
        self.assertEqual(sent[1], ("❌ Moderation commands only work in a server.", {"ephemeral": True}))
