"""Tests for the dice parser behind /roll in bot/commands/utility.py.

The parser lives inside the command callback, so the callback is called
directly with a fake interaction and the replies it sends are inspected.
"""
import asyncio
import re
import unittest
from unittest import mock

from bot.commands import utility


def run_roll(dice):
    """Call the /roll callback with `dice`; return the list of (text, kwargs) it sent."""
    sent = []

    async def send_message(text, **kwargs):
        sent.append((text, kwargs))

    interaction = mock.MagicMock()
    interaction.response.send_message = send_message
    # Utility.__init__ starts a background task, so make the cog without running it.
    cog = object.__new__(utility.Utility)
    cog.bot = mock.MagicMock()
    with mock.patch.object(utility, "log_action", new=mock.AsyncMock()):
        asyncio.run(utility.Utility.roll.callback(cog, interaction, dice))
    return sent


class DiceParserTests(unittest.TestCase):
    """/roll accepts XdY or dY and rejects anything else."""

    def test_four_d_eight_rolls_four_dice(self):
        sent = run_roll("4d8")
        self.assertEqual(len(sent), 1)
        text = sent[0][0]
        self.assertIn("Rolling 4d8", text)
        rolls = [int(n) for n in re.findall(r"Dice \d+: (\d+)", text)]
        self.assertEqual(len(rolls), 4)
        self.assertTrue(all(1 <= roll <= 8 for roll in rolls))
        self.assertIn(f"**Total:** {sum(rolls)}", text)

    def test_missing_count_means_one_die(self):
        text = run_roll("d20")[0][0]
        self.assertIn("Rolling 1d20", text)
        self.assertEqual(len(re.findall(r"Dice \d+:", text)), 1)

    def test_whitespace_around_is_ignored(self):
        self.assertIn("Rolling 2d6", run_roll("  2d6 ")[0][0])

    def test_invalid_formats_are_rejected_privately(self):
        for bad in ["", "abc", "4d", "d", "2d6+1", "4x8", "-1d6", "2 d 6"]:
            with self.subTest(bad=bad):
                sent = run_roll(bad)
                self.assertEqual(len(sent), 1)
                self.assertIn("Invalid format", sent[0][0])
                self.assertTrue(sent[0][1].get("ephemeral"))

    def test_zero_dice_or_sides_are_rejected(self):
        for bad in ["0d6", "3d0"]:
            with self.subTest(bad=bad):
                sent = run_roll(bad)
                self.assertEqual(len(sent), 1)
                self.assertIn("must be positive", sent[0][0])

    def test_one_hundred_is_allowed(self):
        sent = run_roll("100d100")
        self.assertEqual(len(sent), 1)
        self.assertIn("Rolling 100d100", sent[0][0])

    def test_over_one_hundred_sends_the_warning_and_then_still_rolls(self):
        # As the code stands there is no `return` after the "100 or less" warning,
        # so the roll goes ahead and a second reply is sent. Pinned here as current behaviour.
        sent = run_roll("101d6")
        self.assertIn("100 or less", sent[0][0])
        self.assertEqual(len(sent), 2)
        self.assertIn("Rolling 101d6", sent[1][0])


if __name__ == "__main__":
    unittest.main()
