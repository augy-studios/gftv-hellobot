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


class MathExpressionTests(unittest.TestCase):
    """evaluate_math_expression() behind /math: arithmetic and the math module, nothing else."""

    def test_arithmetic_and_math_functions(self):
        """Ordinary expressions give the same answers eval() gave."""
        evaluate = utility.evaluate_math_expression
        self.assertEqual(evaluate("2 + 3 * 4"), 14)
        self.assertEqual(evaluate("(2 + 3) * 4"), 20)
        self.assertEqual(evaluate("7 // 2"), 3)
        self.assertEqual(evaluate("7 % 4"), 3)
        self.assertEqual(evaluate("-2 ** 2"), -4)
        self.assertEqual(evaluate("2 ** -1"), 0.5)
        self.assertAlmostEqual(evaluate("sqrt(16) + sin(pi / 2)"), 5.0)
        self.assertEqual(evaluate("factorial(5)"), 120)
        self.assertEqual(evaluate("abs(-3) + round(2.6)"), 6)
        self.assertEqual(evaluate("round(1234, -2)"), 1200)
        self.assertEqual(evaluate("round(3.14159, 2)"), 3.14)

    def test_zero_division_still_raises(self):
        """0/0 still raises, so /math can send its cookie message."""
        with self.assertRaises(ZeroDivisionError):
            utility.evaluate_math_expression("0/0")

    def test_escapes_are_refused(self):
        """The expressions that escaped eval()'s empty __builtins__ are refused before running."""
        for expression in [
            "().__class__.__bases__[0].__subclasses__()",
            "[x for x in (1, 2)]",
            "__import__('os')",
            "(lambda: 1)()",
            "'a' * 3",
            "math",
            "sqrt",
            "pow(2, 3, mod=5)",
            "factorial.__self__",
        ]:
            with self.subTest(expression=expression):
                with self.assertRaises((utility.UnsafeMathExpression, SyntaxError)):
                    utility.evaluate_math_expression(expression)

    def test_huge_results_are_refused_quickly(self):
        """Results that would take minutes or not fit in a message are refused."""
        for expression in ["9**9**9", "2**100000", "factorial(100000)", "(10**1000)**1000", "1" * 201,
                           "round(5, -10**9)", "round(10**1000, -100000000)", "round(2.5, 1.5)"]:
            with self.subTest(expression=expression[:20]):
                with self.assertRaises(utility.UnsafeMathExpression):
                    utility.evaluate_math_expression(expression)

    def test_math_command_replies(self):
        """/math sends the result, or the invalid-expression reply for a refused one."""
        sent = []

        async def send_message(text, **kwargs):
            sent.append((text, kwargs))

        interaction = mock.MagicMock()
        interaction.response.send_message = send_message
        cog = object.__new__(utility.Utility)
        cog.bot = mock.MagicMock()
        with mock.patch.object(utility, "log_action", new=mock.AsyncMock()):
            asyncio.run(utility.Utility.math.callback(cog, interaction, "6 * 7"))
            asyncio.run(utility.Utility.math.callback(cog, interaction, "().__class__"))
            asyncio.run(utility.Utility.math.callback(cog, interaction, "0/0"))
        self.assertIn("**42**", sent[0][0])
        self.assertEqual(sent[1], ("❌ Invalid mathematical expression.", {"ephemeral": True}))
        self.assertTrue(sent[2][0].startswith("🍪"))
