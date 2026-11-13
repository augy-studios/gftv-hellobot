"""Tests for the Wordle scoring and the Hangman display in bot/commands/games.py.

The session classes are used as they are. Their constructors fetch a word list
over the network, so `load_wordlist` is replaced with a one-word list.
"""
import unittest
from unittest import mock

from bot.commands import games

GREEN, YELLOW, BLACK = "🟩", "🟨", "⬛"


def make_session(session_class, word, *args):
    """Build a session whose secret word is `word`, with no network and a fake manager and interaction."""
    manager = mock.MagicMock()
    interaction = mock.MagicMock()
    with mock.patch.object(games, "load_wordlist", return_value=[word]):
        return session_class(manager, interaction, *args)


class WordleScoringTests(unittest.TestCase):
    """WordleSession.render() turns each guess into a row of coloured squares."""

    def rows(self, target, guesses):
        session = make_session(games.WordleSession, target, len(target))
        session.guesses = list(guesses)
        return session.render().description.split("\n")

    def test_exact_match_is_all_green(self):
        self.assertEqual(self.rows("crane", ["crane"]), [GREEN * 5])

    def test_no_shared_letters_is_all_black(self):
        self.assertEqual(self.rows("crane", ["moist"]), [BLACK * 5])

    def test_right_letter_wrong_place_is_yellow(self):
        # "nacre" has the letters of "crane"; only the final "e" is in the right place
        self.assertEqual(self.rows("crane", ["nacre"]), [YELLOW * 4 + GREEN])

    def test_mixed_green_yellow_black(self):
        # target "crane", guess "crate": c,r,a green; t black; e green
        self.assertEqual(self.rows("crane", ["crate"]), [GREEN * 3 + BLACK + GREEN])

    def test_repeated_letter_is_yellow_each_time_as_the_code_stands(self):
        # The code checks `g[i] in target`, so a letter that appears once in the
        # target is yellow every time it appears in the guess (real Wordle would not do this).
        self.assertEqual(self.rows("abcde", ["aaaaa"]), [GREEN + YELLOW * 4])

    def test_several_guesses_make_several_rows(self):
        self.assertEqual(self.rows("crane", ["moist", "crane"]), [BLACK * 5, GREEN * 5])

    def test_footer_counts_the_next_guess(self):
        session = make_session(games.WordleSession, "crane", 5)
        session.guesses = ["moist", "plumb"]
        self.assertEqual(session.render().footer.text, "Guess 3/6")


class HangmanDisplayTests(unittest.TestCase):
    """HangmanSession.render() shows guessed letters and underscores."""

    def description(self, word, guessed=(), wrong=0):
        session = make_session(games.HangmanSession, word, len(word))
        session.guessed = set(guessed)
        session.wrong = wrong
        return session.render().description

    def test_nothing_guessed_is_all_underscores(self):
        self.assertEqual(self.description("python"), "`_ _ _ _ _ _`\nWrong guesses: 0/6")

    def test_guessed_letters_are_shown_in_place(self):
        self.assertEqual(self.description("hello", guessed="lo"), "`_ _ l l o`\nWrong guesses: 0/6")

    def test_all_letters_guessed_shows_the_word(self):
        self.assertEqual(self.description("cat", guessed="cat"), "`c a t`\nWrong guesses: 0/6")

    def test_wrong_guess_counter(self):
        self.assertEqual(self.description("cat", guessed="z", wrong=1), "`_ _ _`\nWrong guesses: 1/6")

    def test_max_wrong_is_six(self):
        self.assertEqual(games.HangmanSession.MAX_WRONG, 6)


if __name__ == "__main__":
    unittest.main()
