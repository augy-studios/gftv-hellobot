"""Turn-based games played with buttons: Tic-Tac-Toe, Connect 4, Chess, Hangman, Wordle,
Trivia, Flag Match, simplified UNO and Battle."""
import random
import aiohttp
import discord
import chess
import requests
from discord import app_commands
from discord.ext import commands
from core.logger import log_action


def load_wordlist(length=None):
    """Fetch the word list for Hangman and Wordle from the CDN and return its words in lower case.

    wordlist.json maps word lengths to lists of words. With a length, only the
    words of that length are returned; without one, every word in the file is.
    """
    wordlist_url = 'https://cdn.augystudios.com/hellobot/wordlist.json'
    response = requests.get(wordlist_url)
    words_by_length = response.json()
    if length:
        # builds the words of the asked-for length, in lower case
        return [word.lower() for word in words_by_length.get(str(length), [])]
    all_words = []
    for word_list in words_by_length.values():
        if isinstance(word_list, list):
            all_words.extend(word_list)
    # builds every word in the file, in lower case
    return [word.lower() for word in all_words]


# ----------------------------------------
# Game Sessions and Manager
# ----------------------------------------
class GameManager:
    """Starts game sessions and finds them again by the id of the message each one lives in."""

    def __init__(self, bot: commands.Bot):
        """Keep the bot and start with no sessions."""
        self.bot = bot
        self.sessions = {}  # message_id -> session

    async def start_game(self, interaction: discord.Interaction, game_key: str, *args):
        """Start the game named by `game_key`, send its first message and remember the session."""
        session_map = {
            "tictactoe": TicTacToeSession,
            "connect4": Connect4Session,
            "chess": ChessSession,
            "hangman": HangmanSession,
            "wordle": WordleSession,
            "trivia": TriviaSession,
            "flagmatch": FlagMatchSession,
            "uno": UnoSession,
            "battle": BattleSession,
        }
        session_class = session_map.get(game_key)
        # solo play fallback: for multiplayer games, user plays with self if no opponent provided
        multiplayer_games = {"tictactoe", "connect4", "reversi", "mancala", "battleship", "checkers", "chess", "xiangqi", "battle"}
        if game_key in multiplayer_games and (len(args) == 0 or args[0] is None):
            args = (interaction.user,)

        if not session_class:
            return await interaction.response.send_message(
                f"Game '{game_key}' not implemented yet.", ephemeral=True
            )
        session = session_class(self, interaction, *args)
        message = await session.start()
        self.sessions[message.id] = session

    async def handle_interaction(self, interaction: discord.Interaction):
        """Pass a button press to the session that owns the message, or say the session has expired."""
        session = self.sessions.get(interaction.message.id)
        if session:
            await session.on_interaction(interaction)
        else:
            await interaction.response.send_message(
                "Session expired or not found.", ephemeral=True
            )


# ----------------------------------------
# Base Session
# ----------------------------------------
class BaseSession:
    """What every game shares: the players, whose turn it is, and sending the first message."""

    def __init__(self, manager: GameManager, interaction: discord.Interaction, *args):
        """Set up the two players: whoever started the game, then the opponent given or else the bot."""
        self.manager = manager
        self.interaction = interaction
        self.channel = interaction.channel
        self.players = [interaction.user]
        if args and isinstance(args[0], discord.Member):
            self.players.append(args[0])
        else:
            self.players.append(manager.bot.user)
        self.current = 0

    async def start(self) -> discord.Message:
        """Send the game's first message and return it."""
        embed = self.render()
        view = self.build_view()

        try:
            # First try replying to the interaction directly
            await self.interaction.response.send_message(embed=embed, view=view)
            # Then fetch the message we just sent
            message = await self.interaction.original_response()
        except discord.errors.HTTPException:
            # If we've already replied (e.g. via a button), fall back to followup
            message = await self.interaction.followup.send(embed=embed, view=view)

        self.message = message
        return message

    async def on_interaction(self, interaction: discord.Interaction):
        """Handle a button press. Each game overrides this."""
        pass  # overridden by each game

    def next_player(self):
        """Pass the turn to the next player and return them."""
        self.current = (self.current + 1) % len(self.players)
        return self.players[self.current]


# ----------------------------------------
# Tic-Tac-Toe
# ----------------------------------------
class TicTacToeSession(BaseSession):
    """Tic-Tac-Toe on a 3 by 3 grid of buttons."""

    WIN_CONDITIONS = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],
        [0, 3, 6], [1, 4, 7], [2, 5, 8],
        [0, 4, 8], [2, 4, 6],
    ]
    SYMBOLS = ['❌', '⭕']

    def __init__(self, manager, interaction, opponent):
        """Start with an empty board of nine squares."""
        super().__init__(manager, interaction, opponent)
        self.board = [None] * 9

    def render(self):
        """Build the embed: whose turn it is, then the board, one line per row."""
        rows = []
        for row in range(3):
            # builds the row's three squares, showing an empty one as ⬜
            rows.append(''.join(self.board[row * 3 + column] or '⬜' for column in range(3)))
        embed = discord.Embed(
            title="Tic-Tac-Toe",
            description=f"{self.players[self.current].mention}'s turn ({self.SYMBOLS[self.current]})\n" + '\n'.join(rows),
            color=0x00ff00
        )
        embed.set_footer(text="Click a square to play.")
        return embed

    def build_view(self):
        """Build the nine square buttons."""
        view = discord.ui.View(timeout=None)
        for position in range(9):
            view.add_item(TTTButton(position, self))
        return view

    async def on_interaction(self, interaction: discord.Interaction):
        """Do nothing: the square buttons handle the presses."""
        # interactions handled in buttons
        pass

    async def handle_move(self, interaction, position):
        """Play the current player's symbol at `position`, then end the game or pass the turn."""
        if interaction.user != self.players[self.current]:
            return await interaction.response.send_message("Not your turn!", ephemeral=True)
        if self.board[position] is not None:
            return await interaction.response.send_message("Square already taken!", ephemeral=True)
        self.board[position] = self.SYMBOLS[self.current]
        # win check
        for winning_line in self.WIN_CONDITIONS:
            # checks whether all three squares of the line hold the current player's symbol
            if all(self.board[square] == self.SYMBOLS[self.current] for square in winning_line):
                embed = discord.Embed(title="Tic-Tac-Toe", description=f"{interaction.user.mention} wins! 🎉", color=0xffff00)
                return await interaction.response.edit_message(embed=embed, view=None)
        # draw
        if all(self.board):
            embed = discord.Embed(title="Tic-Tac-Toe", description="Draw! 🤝", color=0xaaaaaa)
            return await interaction.response.edit_message(embed=embed, view=None)
        # next turn
        self.next_player()
        embed = self.render()
        view = self.build_view()
        await interaction.response.edit_message(embed=embed, view=view)


class TTTButton(discord.ui.Button):
    """One square of the Tic-Tac-Toe board."""

    def __init__(self, position, session):
        """Make a blank square button on the row its position belongs to."""
        super().__init__(style=discord.ButtonStyle.secondary, label='⬜', row=position // 3)
        self.position = position
        self.session = session

    async def callback(self, interaction):
        """Play this square."""
        await self.session.handle_move(interaction, self.position)


# ----------------------------------------
# Connect 4
# ----------------------------------------
class Connect4Session(BaseSession):
    """Connect 4 on a board of 6 rows and 7 columns, with one button per column."""

    ROWS, COLUMNS = 6, 7
    SYMBOLS = ['🔴', '🟡']

    def __init__(self, manager, interaction, opponent):
        """Start with an empty board."""
        super().__init__(manager, interaction, opponent)
        # builds one row of empty slots per board row
        self.board = [[None] * self.COLUMNS for _ in range(self.ROWS)]

    def render(self):
        """Build the embed: whose turn it is, then the board, one line per row."""
        lines = []
        for row in range(self.ROWS):
            # builds the row's slots, showing an empty one as ⚪
            lines.append(''.join(self.board[row][column] or '⚪' for column in range(self.COLUMNS)))
        embed = discord.Embed(
            title="Connect 4",
            description=f"{self.players[self.current].mention}'s turn ({self.SYMBOLS[self.current]})\n" + '\n'.join(lines),
            color=0x00ff00
        )
        embed.set_footer(text="Click column buttons to drop a disc.")
        return embed

    def build_view(self):
        """Build one button per column."""
        view = discord.ui.View(timeout=None)
        for column in range(self.COLUMNS):
            view.add_item(C4Button(column, self))
        return view

    async def on_interaction(self, interaction):
        """Do nothing: the column buttons handle the presses."""
        pass

    async def handle_move(self, interaction, column):
        """Drop the current player's disc into `column`, then end the game or pass the turn."""
        if interaction.user != self.players[self.current]:
            return await interaction.response.send_message("Not your turn!", ephemeral=True)
        # drop disc into the lowest empty slot of the column
        for row in reversed(range(self.ROWS)):
            if self.board[row][column] is None:
                self.board[row][column] = self.SYMBOLS[self.current]
                break
        else:
            return await interaction.response.send_message("Column full!", ephemeral=True)
        # win?
        if self.check_win(row, column):
            embed = discord.Embed(title="Connect 4", description=f"{interaction.user.mention} wins! 🎉", color=0xffff00)
            return await interaction.response.edit_message(embed=embed, view=None)
        # draw? (checks whether the top slot of every column is filled)
        if all(self.board[0][column_index] for column_index in range(self.COLUMNS)):
            embed = discord.Embed(title="Connect 4", description="Draw! 🤝", color=0xaaaaaa)
            return await interaction.response.edit_message(embed=embed, view=None)
        # next
        self.next_player()
        embed = self.render()
        view = self.build_view()
        await interaction.response.edit_message(embed=embed, view=view)

    def check_win(self, row, column):
        """Return True when the disc at (row, column) makes four in a line for the current player."""
        symbol = self.SYMBOLS[self.current]
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
        for row_step, column_step in directions:
            count = 1
            # count the matching discs on both sides of the new one
            for sign in (1, -1):
                check_row, check_column = row, column
                while True:
                    check_row += row_step * sign
                    check_column += column_step * sign
                    if (0 <= check_row < self.ROWS and 0 <= check_column < self.COLUMNS
                            and self.board[check_row][check_column] == symbol):
                        count += 1
                    else:
                        break
            if count >= 4:
                return True
        return False


class C4Button(discord.ui.Button):
    """The button for one Connect 4 column."""

    def __init__(self, column, session):
        """Make the button, labelled with the column number counting from 1."""
        super().__init__(style=discord.ButtonStyle.secondary, label=str(column + 1))
        self.column = column
        self.session = session

    async def callback(self, interaction):
        """Drop a disc into this column."""
        await self.session.handle_move(interaction, self.column)


# ----------------------------------------
# ChessSession
# ----------------------------------------
class ChessSession(BaseSession):
    """Chess, with moves typed in UCI form (for example e2e4)."""

    def __init__(self, manager, interaction, opponent):
        """Start from the usual opening position."""
        super().__init__(manager, interaction, opponent)
        self.board = chess.Board()

    def render(self):
        """Build the embed: the board drawn in text, and whose turn it is."""
        board_text = self.board.unicode(invert_color=True)
        embed = discord.Embed(
            title="Chess",
            description=f"```\n{board_text}\n```",
            color=0xFFFFFF
        )
        embed.set_footer(text=f"{self.players[self.current].mention}'s turn. Click Move.")
        return embed

    def build_view(self):
        """Build the Move button."""
        view = discord.ui.View(timeout=None)
        view.add_item(ChessMoveButton(self))
        return view

    async def on_interaction(self, interaction: discord.Interaction):
        """Do nothing: the Move button handles the presses."""
        pass

    async def make_move(self, interaction, uci_move: str):
        """Play a UCI move if it's legal, then end the game or pass the turn."""
        try:
            move = chess.Move.from_uci(uci_move)
            if move not in self.board.legal_moves:
                raise ValueError
            self.board.push(move)
        except Exception:
            return await interaction.response.send_message("Invalid move! Use UCI like e2e4.", ephemeral=True)
        if self.board.is_checkmate():
            return await interaction.response.edit_message(
                embed=discord.Embed(title="Chess", description=f"Checkmate — {interaction.user.mention} wins! 🎉"), view=None)
        if self.board.is_stalemate() or self.board.is_insufficient_material():
            return await interaction.response.edit_message(
                embed=discord.Embed(title="Chess", description="Draw! 🤝"), view=None)
        self.next_player()
        await interaction.response.edit_message(embed=self.render(), view=self.build_view())


class ChessMoveButton(discord.ui.Button):
    """The Move button, which opens the form for typing a move."""

    def __init__(self, session):
        """Make the Move button."""
        super().__init__(style=discord.ButtonStyle.primary, label="Move")
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        """Open the move form."""
        await interaction.response.send_modal(ChessMoveModal(self.session))


class ChessMoveModal(discord.ui.Modal):
    """The form where a player types a chess move."""

    def __init__(self, session):
        """Make the form with one Move field."""
        super().__init__(title="Enter Move (UCI)")
        self.session = session
        self.move = discord.ui.TextInput(label="Move", placeholder="e2e4", max_length=5)
        self.add_item(self.move)

    async def on_submit(self, interaction: discord.Interaction):
        """Play the typed move."""
        await self.session.make_move(interaction, self.move.value.strip())


# ----------------------------------------
# HangmanSession
# ----------------------------------------
class HangmanSession(BaseSession):
    """Hangman: guess the word a letter (or the whole word) at a time, with six wrong guesses allowed."""

    MAX_WRONG = 6

    def __init__(self, manager, interaction, length: int = None):
        """Pick a random word (of `length` letters, if given) with nothing guessed yet."""
        super().__init__(manager, interaction)
        words = load_wordlist(length)
        self.word = random.choice(words)
        self.guessed = set()
        self.wrong = 0

    def render(self):
        """Build the embed: the word with unguessed letters as underscores, and the wrong-guess count."""
        shown_letters = []
        for letter in self.word:
            if letter in self.guessed:
                shown_letters.append(letter)
            else:
                shown_letters.append('_')
        display = ' '.join(shown_letters)
        embed = discord.Embed(
            title="Hangman",
            description=f"`{display}`\nWrong guesses: {self.wrong}/{self.MAX_WRONG}",
            color=0xFF00FF
        )
        embed.set_footer(text="Enter a letter or full word.")
        return embed

    def build_view(self):
        """Build the Guess button."""
        view = discord.ui.View(timeout=None)
        view.add_item(HangmanGuessButton(self))
        return view

    async def on_interaction(self, interaction: discord.Interaction):
        """Do nothing: the Guess button handles the presses."""
        pass

    async def guess(self, interaction, text: str):
        """Take a guessed letter or word, then show the win, the loss or the updated board."""
        text = text.lower().strip()
        if len(text) == 1:
            if text in self.guessed:
                return await interaction.response.send_message("Already guessed!", ephemeral=True)
            if text in self.word:
                self.guessed.add(text)
            else:
                self.wrong += 1
                self.guessed.add(text)
        else:
            if text == self.word:
                self.guessed.update(self.word)
            else:
                self.wrong += 1
        # checks whether every letter of the word has been guessed
        if all(letter in self.guessed for letter in self.word):
            embed = discord.Embed(
                title="Hangman",
                description=f"You solved it! The word was **{self.word}** 🎉"
            )
            return await interaction.response.edit_message(embed=embed, view=None)
        if self.wrong >= self.MAX_WRONG:
            embed = discord.Embed(
                title="Hangman",
                description=f"Game over! Word was **{self.word}**."
            )
            return await interaction.response.edit_message(embed=embed, view=None)
        await interaction.response.edit_message(embed=self.render(), view=self.build_view())


class HangmanGuessButton(discord.ui.Button):
    """The Guess button, which opens the form for a Hangman guess."""

    def __init__(self, session):
        """Make the Guess button."""
        super().__init__(style=discord.ButtonStyle.primary, label="Guess")
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        """Open the guess form."""
        modal = HangmanModal(self.session)
        await interaction.response.send_modal(modal)


class HangmanModal(discord.ui.Modal):
    """The form where a player types a letter or a word."""

    def __init__(self, session):
        """Make the form with one Letter or Word field."""
        super().__init__(title="Hangman Guess")
        self.session = session
        self.text = discord.ui.TextInput(label="Letter or Word", max_length=20)
        self.add_item(self.text)

    async def on_submit(self, interaction: discord.Interaction):
        """Make the typed guess."""
        await self.session.guess(interaction, self.text.value)


# ----------------------------------------
# WordleSession
# ----------------------------------------
class WordleSession(BaseSession):
    """Wordle: six guesses at a word of the chosen length (five letters unless asked)."""

    MAX_GUESSES = 6

    def __init__(self, manager, interaction, length: int = 5):
        """Pick a random word of `length` letters, with no guesses yet."""
        super().__init__(manager, interaction)
        words = load_wordlist(length)
        self.target = random.choice(words)
        self.length = length
        self.guesses = []

    def render(self):
        """Build the embed: one row of coloured squares per guess, and the guess number in the footer.

        Green is the right letter in the right place, yellow a letter that's somewhere
        in the word, black a letter that isn't. Repeated letters aren't counted, so a
        letter that's in the word once is yellow every time it appears in a guess.
        """
        lines = []
        for guess_word in self.guesses:
            squares = []
            for letter_index in range(self.length):
                if guess_word[letter_index] == self.target[letter_index]:
                    squares.append('🟩')
                elif guess_word[letter_index] in self.target:
                    squares.append('🟨')
                else:
                    squares.append('⬛')
            lines.append(''.join(squares))
        embed = discord.Embed(
            title="Wordle",
            description='\n'.join(lines),
            color=0x00FF00
        )
        embed.set_footer(text=f"Guess {len(self.guesses) + 1}/{self.MAX_GUESSES}")
        return embed

    def build_view(self):
        """Build the Guess button."""
        view = discord.ui.View(timeout=None)
        view.add_item(WordleGuessButton(self))
        return view

    async def on_interaction(self, interaction: discord.Interaction):
        """Do nothing: the Guess button handles the presses."""
        pass

    async def guess(self, interaction, word: str):
        """Take a guessed word of the right length, then show the win, the loss or the updated rows."""
        word = word.lower().strip()
        if len(word) != self.length:
            return await interaction.response.send_message(
                f"Word must be {self.length} letters.", ephemeral=True
            )
        self.guesses.append(word)
        if word == self.target:
            return await interaction.response.edit_message(
                embed=discord.Embed(title="Wordle", description=f"Correct! {self.target}"),
                view=None
            )
        if len(self.guesses) >= self.MAX_GUESSES:
            return await interaction.response.edit_message(
                embed=discord.Embed(title="Wordle", description=f"Out of guesses! Word was {self.target}"),
                view=None
            )
        await interaction.response.edit_message(embed=self.render(), view=self.build_view())


class WordleGuessButton(discord.ui.Button):
    """The Guess button, which opens the form for a Wordle guess."""

    def __init__(self, session):
        """Make the Guess button."""
        super().__init__(style=discord.ButtonStyle.primary, label="Guess")
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        """Open the guess form."""
        modal = WordleModal(self.session)
        await interaction.response.send_modal(modal)


class WordleModal(discord.ui.Modal):
    """The form where a player types a Wordle guess."""

    def __init__(self, session):
        """Make the form with one Guess field, as long as the word."""
        super().__init__(title="Wordle Guess")
        self.session = session
        self.text = discord.ui.TextInput(label="Guess", max_length=session.length)
        self.add_item(self.text)

    async def on_submit(self, interaction: discord.Interaction):
        """Make the typed guess."""
        await self.session.guess(interaction, self.text.value)


# ----------------------------------------
# TriviaSession using Open Trivia DB
# ----------------------------------------
class TriviaSession(BaseSession):
    """One multiple-choice question from Open Trivia DB."""

    def __init__(self, manager, interaction, category: str = None):
        """Keep the category (an Open Trivia DB category id, or None for any)."""
        super().__init__(manager, interaction)
        self.category = category
        self.question = None
        self.correct = None
        self.options = []

    async def start(self):
        """Fetch the question, then send the first message."""
        await self.fetch_question()
        return await super().start()

    async def fetch_question(self):
        """Fetch one question (from the category, if any) and shuffle its answers."""
        url = 'https://opentdb.com/api.php?amount=1&type=multiple'
        if self.category:
            url += f'&category={self.category}'
        async with aiohttp.ClientSession() as http_session:
            async with http_session.get(url) as response:
                trivia_data = await response.json()
        question_data = trivia_data['results'][0]
        self.question = discord.utils.escape_markdown(question_data['question'])
        self.correct = question_data['correct_answer']
        answer_options = question_data['incorrect_answers'] + [question_data['correct_answer']]
        random.shuffle(answer_options)
        self.options = answer_options

    def render(self):
        """Build the embed with the question."""
        embed = discord.Embed(title="Trivia", description=self.question, color=0xFFD700)
        return embed

    def build_view(self):
        """Build one button per answer."""
        view = discord.ui.View(timeout=None)
        for option in self.options:
            view.add_item(TriviaButton(option, self))
        return view

    async def on_interaction(self, interaction):
        """Do nothing: the answer buttons handle the presses."""
        pass

    async def answer(self, interaction, choice: str):
        """Say whether the chosen answer is right, and what the right answer was."""
        if choice == self.correct:
            description = f"✅ Correct! The answer was **{self.correct}**."
        else:
            description = f"❌ Wrong! It was **{self.correct}**."
        embed = discord.Embed(title="Trivia", description=description)
        await interaction.response.edit_message(embed=embed, view=None)


class TriviaButton(discord.ui.Button):
    """The button for one trivia answer."""

    def __init__(self, label, session):
        """Make the button, labelled with the answer (cut to 100 characters)."""
        super().__init__(style=discord.ButtonStyle.secondary, label=label[:100])
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        """Answer with this button's label."""
        await self.session.answer(interaction, self.label)


# ----------------------------------------
# FlagMatchSession
# ----------------------------------------
class FlagMatchSession(BaseSession):
    """Flag Match: one flag and four country names to choose from."""

    def __init__(self, manager, interaction):
        """Start with no flags; they're fetched when the game starts."""
        super().__init__(manager, interaction)
        self.flags = []  # list of (name, url)
        self.correct = None

    async def start(self) -> discord.Message:
        """Fetch the flags, then send the first message."""
        # load four flags and pick the correct one
        await self.fetch_flags()
        # now self.correct is set, so render() will work
        return await super().start()

    async def fetch_flags(self):
        """Pick four random countries and choose one of them as the answer."""
        # get 4 random countries
        async with aiohttp.ClientSession() as http_session:
            async with http_session.get('https://restcountries.com/v3.1/all') as response:
                country_data = await response.json()
        chosen_countries = random.sample(country_data, 4)
        # builds a (country name, flag image url) pair for each chosen country
        self.flags = [(country['name']['common'], country['flags']['png']) for country in chosen_countries]
        self.correct = random.choice(self.flags)

    def render(self):
        """Build the embed: the question and the answer's flag."""
        _country_name, flag_url = self.correct
        embed = discord.Embed(
            title="Flag Match",
            description="Which country does this flag belong to?",
            color=discord.Color.random()
        )
        embed.set_image(url=flag_url)
        return embed

    def build_view(self):
        """Shuffle the four countries and build one button per country name."""
        view = discord.ui.View(timeout=None)
        random.shuffle(self.flags)
        for country_name, _flag_url in self.flags:
            view.add_item(FlagButton(country_name, self))
        return view

    async def answer(self, interaction: discord.Interaction, choice: str):
        """Say whether the chosen country is right, and offer a Play Again button."""
        # treat truncated choice as correct if it appears in the full country name
        full_name = self.correct[0]
        if choice.lower() in full_name.lower():
            result = f"✅ Correct! It was **{full_name}**!"
        else:
            result = f"❌ Wrong! It was **{full_name}**."

        # rebuild the embed to show the original flag + question + result
        _country_name, flag_url = self.correct
        embed = discord.Embed(
            title="Flag Match",
            description=f"Which country does this flag belong to?\n{result}",
            color=discord.Color.random()
        )
        embed.set_image(url=flag_url)

        # attach only our Play Again button
        view = discord.ui.View(timeout=None)
        view.add_item(PlayAgainButton(self))

        await interaction.response.edit_message(embed=embed, view=view)


class FlagButton(discord.ui.Button):
    """The button for one country name."""

    def __init__(self, label, session):
        """Make the button, labelled with the country name (cut to 20 characters)."""
        super().__init__(style=discord.ButtonStyle.secondary, label=label[:20])
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        """Answer with this button's label."""
        await self.session.answer(interaction, self.label)


class PlayAgainButton(discord.ui.Button):
    """The Play Again button, which starts a new round in the same message."""

    def __init__(self, session):
        """Make the Play Again button."""
        super().__init__(style=discord.ButtonStyle.secondary, label="Play Again")
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        """Fetch new flags and show the new round in the same message."""
        # 1) Pick new flags
        await self.session.fetch_flags()
        # 2) Build the fresh embed + buttons
        embed = self.session.render()
        view = self.session.build_view()
        # 3) Edit the very same message
        await interaction.response.edit_message(embed=embed, view=view)


# ----------------------------------------
# UnoSession (Simplified)
# ----------------------------------------
class UnoSession(BaseSession):
    """A simplified UNO with only colour and number cards."""

    COLORS = ["R", "G", "B", "Y"]  # Red, Green, Blue, Yellow

    def __init__(self, manager, interaction, *args):
        """Build and shuffle the deck, deal five cards to each player and turn one card face up."""
        super().__init__(manager, interaction)
        # build deck: builds one card per colour and number 0 to 9, then doubles the list
        self.deck = [f"{color}{number}" for color in self.COLORS for number in range(0, 10)] * 2
        random.shuffle(self.deck)
        # deal 5 cards each
        self.hands = {}
        for player in self.players:
            # builds the player's hand from the top five cards of the deck
            self.hands[player] = [self.deck.pop() for _ in range(5)]
        self.discard = [self.deck.pop()]

    def render(self):
        """Build the embed: the top card and the current player's hand."""
        current_player = self.players[self.current]
        top_card = self.discard[-1]
        hand = ','.join(self.hands[current_player])
        embed = discord.Embed(
            title="UNO (Simplified)",
            description=f"Top: {top_card} \nYour hand: {hand}",
            color=0xFF4500
        )
        embed.set_footer(text="Play a matching card or draw.")
        return embed

    def build_view(self):
        """Build a button for each card the current player can play, plus Draw."""
        view = discord.ui.View(timeout=None)
        # buttons for playable cards
        top_card = self.discard[-1]
        top_color = top_card[0]
        top_number = top_card[1:]
        for card in self.hands[self.players[self.current]]:
            if card[0] == top_color or card[1:] == top_number:
                view.add_item(UnoPlayButton(card, self))
        view.add_item(UnoDrawButton(self))
        return view

    async def on_interaction(self, interaction):
        """Do nothing: the card and Draw buttons handle the presses."""
        pass

    async def play_card(self, interaction, card):
        """Play a matching card from the current player's hand, then end the game or pass the turn."""
        player = self.players[self.current]
        if card not in self.hands[player]:
            return await interaction.response.send_message("You don't have that card!", ephemeral=True)
        top_card = self.discard[-1]
        if not (card[0] == top_card[0] or card[1:] == top_card[1:]):
            return await interaction.response.send_message("Can't play that card!", ephemeral=True)
        self.hands[player].remove(card)
        self.discard.append(card)
        if not self.hands[player]:
            embed = discord.Embed(title="UNO", description=f"{player.mention} wins! 🎉")
            return await interaction.response.edit_message(embed=embed, view=None)
        self.next_player()
        await interaction.response.edit_message(embed=self.render(), view=self.build_view())

    async def draw_card(self, interaction):
        """Draw a card for the current player (reshuffling the discards if the deck is empty) and pass the turn."""
        player = self.players[self.current]
        if not self.deck:
            self.deck = self.discard[:-1]
            random.shuffle(self.deck)
        card = self.deck.pop()
        self.hands[player].append(card)
        self.next_player()
        await interaction.response.edit_message(embed=self.render(), view=self.build_view())


class UnoPlayButton(discord.ui.Button):
    """The button for one playable card."""

    def __init__(self, card, session):
        """Make the button, labelled with the card."""
        super().__init__(style=discord.ButtonStyle.secondary, label=card)
        self.card = card
        self.session = session

    async def callback(self, interaction):
        """Play this card."""
        await self.session.play_card(interaction, self.card)


class UnoDrawButton(discord.ui.Button):
    """The Draw button."""

    def __init__(self, session):
        """Make the Draw button."""
        super().__init__(style=discord.ButtonStyle.primary, label="Draw")
        self.session = session

    async def callback(self, interaction):
        """Draw a card."""
        await self.session.draw_card(interaction)


# ----------------------------------------
# BattleSession (1v1 health-based fight)
# ----------------------------------------
class BattleSession(BaseSession):
    """Battle: take turns to strike the other player or heal, until someone reaches 0 HP."""

    def __init__(self, manager, interaction, opponent=None):
        """Start every player on 100 HP."""
        super().__init__(manager, interaction, opponent)
        # builds a health of 100 for each player
        self.health = {player: 100 for player in self.players}

    def render(self):
        """Build the embed: each player's HP, and whose turn it is."""
        # builds one "name: HP" line per player
        lines = [f"{player.display_name}: {self.health[player]} HP" for player in self.players]
        embed = discord.Embed(
            title="Battle",
            description="\n".join(lines),
            color=0x8B0000
        )
        embed.set_footer(text=f"{self.players[self.current].mention}'s turn.")
        return embed

    def build_view(self):
        """Build the Strike and Heal buttons."""
        view = discord.ui.View(timeout=None)
        view.add_item(BattleButton("Strike", self))
        view.add_item(BattleButton("Heal", self))
        return view

    async def action(self, interaction, choice):
        """Strike the other player or heal, then end the game or pass the turn."""
        actor = self.players[self.current]
        target = self.players[(self.current + 1) % len(self.players)]
        if choice == "Strike":
            damage = random.randint(10, 25)
            self.health[target] -= damage
            result_text = f"{actor.display_name} strikes {target.display_name} for {damage} damage!"
        else:
            heal_amount = random.randint(5, 15)
            self.health[actor] = min(100, self.health[actor] + heal_amount)
            result_text = f"{actor.display_name} heals for {heal_amount} HP!"
        if self.health[target] <= 0:
            embed = discord.Embed(title="Battle", description=f"{actor.display_name} wins! 🎉")
            return await interaction.response.edit_message(embed=embed, view=None)
        self.next_player()
        embed = self.render()
        embed.set_footer(text=result_text)
        await interaction.response.edit_message(embed=embed, view=self.build_view())


class BattleButton(discord.ui.Button):
    """The Strike or Heal button."""

    def __init__(self, label, session):
        """Make the button; its label is also the action it takes."""
        super().__init__(style=discord.ButtonStyle.primary, label=label)
        self.choice = label
        self.session = session

    async def callback(self, interaction):
        """Take this button's action."""
        await self.session.action(interaction, self.choice)


# ----------------------------------------
# Cog Definition
# ----------------------------------------
class Games(commands.Cog):
    """A Cog housing turn-based games using Discord interactions."""

    def __init__(self, bot: commands.Bot):
        """Keep the bot and make the game manager."""
        self.bot = bot
        self.manager = GameManager(bot)

    @app_commands.command(name="tictactoe", description="Play Tic-Tac-Toe with another user.")
    @app_commands.describe(opponent="Opponent (optional)")
    async def tictactoe(self, interaction: discord.Interaction, opponent: discord.Member = None):
        """Start a game of Tic-Tac-Toe."""
        await self.manager.start_game(interaction, "tictactoe", opponent)
        await log_action(self.bot, interaction)

    @app_commands.command(name="connect4", description="Play Connect 4 with another user.")
    @app_commands.describe(opponent="Opponent (optional)")
    async def connect4(self, interaction: discord.Interaction, opponent: discord.Member = None):
        """Start a game of Connect 4."""
        await self.manager.start_game(interaction, "connect4", opponent)
        await log_action(self.bot, interaction)

    @app_commands.command(name="chess", description="Play Chess with another user or bot.")
    @app_commands.describe(opponent="Opponent (optional)")
    async def chess(self, interaction: discord.Interaction, opponent: discord.Member = None):
        """Start a game of Chess."""
        await self.manager.start_game(interaction, "chess", opponent)
        await log_action(self.bot, interaction)

    @app_commands.command(name="hangman", description="Play Hangman.")
    @app_commands.describe(length="Word length (optional)")
    # The default length is picked once, when this file loads, not on each use.
    async def hangman(self, interaction: discord.Interaction, length: int = random.randint(4, 13)):
        """Start a game of Hangman."""
        await self.manager.start_game(interaction, "hangman", length)
        await log_action(self.bot, interaction)

    @app_commands.command(name="wordle", description="Play Wordle.")
    @app_commands.describe(length="Word length")
    async def wordle(self, interaction: discord.Interaction, length: int = 5):
        """Start a game of Wordle."""
        await self.manager.start_game(interaction, "wordle", length)
        await log_action(self.bot, interaction)

    @app_commands.command(name="trivia", description="Answer a trivia question.")
    @app_commands.describe(category="Open Trivia DB category ID (optional)")
    async def trivia(self, interaction: discord.Interaction, category: str = None):
        """Ask a trivia question."""
        await self.manager.start_game(interaction, "trivia", category)
        await log_action(self.bot, interaction)

    @app_commands.command(name="flagmatch", description="Match a country to its flag.")
    async def flagmatch(self, interaction: discord.Interaction):
        """Start a round of Flag Match."""
        await self.manager.start_game(interaction, "flagmatch")
        await log_action(self.bot, interaction)

    @app_commands.command(name="uno", description="Play simplified UNO with color/number cards.")
    async def uno(self, interaction: discord.Interaction):
        """Start a game of simplified UNO."""
        await self.manager.start_game(interaction, "uno")
        await log_action(self.bot, interaction)

    @app_commands.command(name="battle", description="Battle another player or bot.")
    @app_commands.describe(opponent="Opponent (optional)")
    async def battle(self, interaction: discord.Interaction, opponent: discord.Member = None):
        """Start a Battle."""
        await self.manager.start_game(interaction, "battle", opponent)
        await log_action(self.bot, interaction)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Pass a button press to the game manager when it belongs to a running game."""
        if interaction.type == discord.InteractionType.component:
            message = interaction.message
            # only handle it if we really have a session for that message
            if message and message.id in self.manager.sessions:
                await self.manager.handle_interaction(interaction)


async def setup(bot):
    """Add the Games cog to the bot."""
    await bot.add_cog(Games(bot))
