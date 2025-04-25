import random
import json
import aiohttp
import discord
import chess
from discord import app_commands
from discord.ext import commands
from core.logger import log_action

# Load wordlist for hangman and wordle from external CDN
# wordlist.json maps string lengths to lists of words
import requests

def load_wordlist(length=None):
    url = 'https://cdn.augystudios.com/hellobot/wordlist.json'
    resp = requests.get(url)
    data = resp.json()
    if length:
        return [w.lower() for w in data.get(str(length), [])]
    all_words = []
    for lst in data.values():
        if isinstance(lst, list):
            all_words.extend(lst)
    return [w.lower() for w in all_words]

# ----------------------------------------
# Game Sessions and Manager
# ----------------------------------------
class GameManager:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sessions = {}  # message_id -> session

    async def start_game(self, interaction: discord.Interaction, game_key: str, *args):
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
        SessionClass = session_map.get(game_key)
        # solo play fallback: for multiplayer games, user plays with self if no opponent provided
        multiplayer_games = {"tictactoe", "connect4", "reversi", "mancala", "battleship", "checkers", "chess", "xiangqi", "battle"}
        if game_key in multiplayer_games and (len(args) == 0 or args[0] is None):
            args = (interaction.user,)

        if not SessionClass:
            return await interaction.response.send_message(
                f"Game '{game_key}' not implemented yet.", ephemeral=True
            )
        session = SessionClass(self, interaction, *args)
        message = await session.start()
        self.sessions[message.id] = session

    async def handle_interaction(self, interaction: discord.Interaction):
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
    def __init__(self, manager: GameManager, interaction: discord.Interaction, *args):
        self.manager = manager
        self.ctx     = interaction
        self.channel = interaction.channel
        self.players = [interaction.user]
        if args and isinstance(args[0], discord.Member):
            self.players.append(args[0])
        else:
            self.players.append(manager.bot.user)
        self.current = 0

    async def start(self) -> discord.Message:
        embed = self.render()
        view  = self.build_view()

        try:
            # First try replying to the interaction directly
            await self.ctx.response.send_message(embed=embed, view=view)
            # Then fetch the message we just sent
            msg = await self.ctx.original_response()
        except discord.errors.HTTPException:
            # If we've already replied (e.g. via a button), fall back to followup
            msg = await self.ctx.followup.send(embed=embed, view=view)

        self.message = msg
        return msg

    async def on_interaction(self, interaction: discord.Interaction):
        pass  # overridden by each game

    def next_player(self):
        self.current = (self.current + 1) % len(self.players)
        return self.players[self.current]
    
# ----------------------------------------
# Tic-Tac-Toe
# ----------------------------------------
class TicTacToeSession(BaseSession):
    WIN_CONDITIONS = [
        [0,1,2],[3,4,5],[6,7,8],
        [0,3,6],[1,4,7],[2,5,8],
        [0,4,8],[2,4,6]
    ]
    SYMBOLS = ['❌','⭕']

    def __init__(self, manager, interaction, opponent):
        super().__init__(manager, interaction, opponent)
        self.board = [None]*9
        
    def render(self):
        rows = []
        for r in range(3):
            rows.append(''.join(self.board[r*3+c] or '⬜' for c in range(3)))
        embed = discord.Embed(
            title="Tic-Tac-Toe",
            description=f"{self.players[self.current].mention}'s turn ({self.SYMBOLS[self.current]})\n" + '\n'.join(rows),
            color=0x00ff00
        )
        embed.set_footer(text="Click a square to play.")
        return embed
    
    def build_view(self):
        view = discord.ui.View(timeout=None)
        for pos in range(9):
            view.add_item(TTTButton(pos, self))
        return view

    async def on_interaction(self, interaction: discord.Interaction):
        # interactions handled in buttons
        pass

    async def handle_move(self, interaction, pos):
        if interaction.user != self.players[self.current]:
            return await interaction.response.send_message("Not your turn!", ephemeral=True)
        if self.board[pos] is not None:
            return await interaction.response.send_message("Square already taken!", ephemeral=True)
        self.board[pos] = self.SYMBOLS[self.current]
        # win check
        for cond in self.WIN_CONDITIONS:
            if all(self.board[i]==self.SYMBOLS[self.current] for i in cond):
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
    def __init__(self, pos, session):
        super().__init__(style=discord.ButtonStyle.secondary, label='⬜', row=pos//3)
        self.pos = pos
        self.session = session

    async def callback(self, interaction):
        await self.session.handle_move(interaction, self.pos)

# ----------------------------------------
# Connect 4
# ----------------------------------------
class Connect4Session(BaseSession):
    ROWS, COLS = 6,7
    SYMBOLS = ['🔴','🟡']

    def __init__(self, manager, interaction, opponent):
        super().__init__(manager, interaction, opponent)
        self.board = [[None]*self.COLS for _ in range(self.ROWS)]

    def render(self):
        lines = [''.join(self.board[r][c] or '⚪' for c in range(self.COLS)) for r in range(self.ROWS)]
        embed = discord.Embed(
            title="Connect 4",
            description=f"{self.players[self.current].mention}'s turn ({self.SYMBOLS[self.current]})\n" + '\n'.join(lines),
            color=0x00ff00
        )
        embed.set_footer(text="Click column buttons to drop a disc.")
        return embed

    def build_view(self):
        view = discord.ui.View(timeout=None)
        for col in range(self.COLS):
            view.add_item(C4Button(col, self))
        return view
    
    async def on_interaction(self, interaction):
        pass

    async def handle_move(self, interaction, col):
        if interaction.user != self.players[self.current]:
            return await interaction.response.send_message("Not your turn!", ephemeral=True)
        # drop disc
        for r in reversed(range(self.ROWS)):
            if self.board[r][col] is None:
                self.board[r][col] = self.SYMBOLS[self.current]
                break
        else:
            return await interaction.response.send_message("Column full!", ephemeral=True)
        # win?
        if self.check_win(r, col):
            embed = discord.Embed(title="Connect 4", description=f"{interaction.user.mention} wins! 🎉", color=0xffff00)
            return await interaction.response.edit_message(embed=embed, view=None)
        # draw?
        if all(self.board[0][c] for c in range(self.COLS)):
            embed = discord.Embed(title="Connect 4", description="Draw! 🤝", color=0xaaaaaa)
            return await interaction.response.edit_message(embed=embed, view=None)
        # next
        self.next_player()
        embed = self.render()
        view = self.build_view()
        await interaction.response.edit_message(embed=embed, view=view)

    def check_win(self, row, col):
        sym = self.SYMBOLS[self.current]
        dirs = [(1,0),(0,1),(1,1),(1,-1)]
        for dr,dc in dirs:
            cnt=1
            for sign in (1,-1):
                r,c = row, col
                while True:
                    r+=dr*sign; c+=dc*sign
                    if 0<=r<self.ROWS and 0<=c<self.COLS and self.board[r][c]==sym:
                        cnt+=1
                    else: break
            if cnt>=4: return True
        return False

class C4Button(discord.ui.Button):
    def __init__(self, col, session):
        super().__init__(style=discord.ButtonStyle.secondary, label=str(col+1))
        self.col = col
        self.session = session
    async def callback(self, interaction):
        await self.session.handle_move(interaction, self.col)

# ----------------------------------------
# ChessSession
# ----------------------------------------
class ChessSession(BaseSession):
    def __init__(self, manager, interaction, opponent):
        super().__init__(manager, interaction, opponent)
        self.board = chess.Board()

    def render(self):
        board_str = self.board.unicode(invert_color=True)
        embed = discord.Embed(
            title="Chess",
            description=f"```\n{board_str}\n```",
            color=0xFFFFFF
        )
        embed.set_footer(text=f"{self.players[self.current].mention}'s turn. Click Move.")
        return embed

    def build_view(self):
        view = discord.ui.View(timeout=None)
        view.add_item(ChessMoveButton(self))
        return view

    async def on_interaction(self, interaction: discord.Interaction): pass

    async def make_move(self, interaction, uci: str):
        try:
            move = chess.Move.from_uci(uci)
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
    def __init__(self, session):
        super().__init__(style=discord.ButtonStyle.primary, label="Move")
        self.session = session
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ChessMoveModal(self.session))

class ChessMoveModal(discord.ui.Modal):
    def __init__(self, session):
        super().__init__(title="Enter Move (UCI)")
        self.session = session
        self.move = discord.ui.TextInput(label="Move", placeholder="e2e4", max_length=5)
        self.add_item(self.move)

    async def on_submit(self, interaction: discord.Interaction):
        await self.session.make_move(interaction, self.move.value.strip())

# ----------------------------------------
# HangmanSession
# ----------------------------------------
class HangmanSession(BaseSession):
    MAX_WRONG = 6
    def __init__(self, manager, interaction, length: int = None):
        super().__init__(manager, interaction)
        words = load_wordlist(length)
        self.word = random.choice(words)
        self.guessed = set()
        self.wrong = 0

    def render(self):
        display = ' '.join(c if c in self.guessed else '_' for c in self.word)
        embed = discord.Embed(
            title="Hangman",
            description=f"`{display}`\nWrong guesses: {self.wrong}/{self.MAX_WRONG}",
            color=0xFF00FF
        )
        embed.set_footer(text="Enter a letter or full word.")
        return embed

    def build_view(self):
        view = discord.ui.View(timeout=None)
        view.add_item(HangmanGuessButton(self))
        return view

    async def on_interaction(self, interaction: discord.Interaction):
        pass

    async def guess(self, interaction, text: str):
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
        if all(c in self.guessed for c in self.word):
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
    def __init__(self, session):
        super().__init__(style=discord.ButtonStyle.primary, label="Guess")
        self.session = session
    async def callback(self, interaction: discord.Interaction):
        modal = HangmanModal(self.session)
        await interaction.response.send_modal(modal)

class HangmanModal(discord.ui.Modal):
    def __init__(self, session):
        super().__init__(title="Hangman Guess")
        self.session = session
        self.text = discord.ui.TextInput(label="Letter or Word", max_length=20)
        self.add_item(self.text)
    async def on_submit(self, interaction: discord.Interaction):
        await self.session.guess(interaction, self.text.value)

# ----------------------------------------
# WordleSession
# ----------------------------------------
class WordleSession(BaseSession):
    MAX_GUESSES = 6
    def __init__(self, manager, interaction, length: int = 5):
        super().__init__(manager, interaction)
        words = load_wordlist(length)
        self.target = random.choice(words)
        self.length = length
        self.guesses = []

    def render(self):
        lines = []
        for g in self.guesses:
            line = ''.join(
                '🟩' if g[i] == self.target[i] else
                '🟨' if g[i] in self.target else
                '⬛'
                for i in range(self.length)
            )
            lines.append(line)
        embed = discord.Embed(
            title="Wordle",
            description='\n'.join(lines),
            color=0x00FF00
        )
        embed.set_footer(text=f"Guess {len(self.guesses)+1}/{self.MAX_GUESSES}")
        return embed

    def build_view(self):
        view = discord.ui.View(timeout=None)
        view.add_item(WordleGuessButton(self))
        return view

    async def on_interaction(self, interaction: discord.Interaction):
        pass

    async def guess(self, interaction, word: str):
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
    def __init__(self, session):
        super().__init__(style=discord.ButtonStyle.primary, label="Guess")
        self.session = session
    async def callback(self, interaction: discord.Interaction):
        modal = WordleModal(self.session)
        await interaction.response.send_modal(modal)

class WordleModal(discord.ui.Modal):
    def __init__(self, session):
        super().__init__(title="Wordle Guess")
        self.session = session
        self.text = discord.ui.TextInput(label="Guess", max_length=session.length)
        self.add_item(self.text)
    async def on_submit(self, interaction: discord.Interaction):
        await self.session.guess(interaction, self.text.value)

# ----------------------------------------
# TriviaSession using Open Trivia DB
# ----------------------------------------
class TriviaSession(BaseSession):
    def __init__(self, manager, interaction, category: str = None):
        super().__init__(manager, interaction)
        self.category = category
        self.question = None
        self.correct = None
        self.options = []

    async def start(self):
        await self.fetch_question()
        return await super().start()

    async def fetch_question(self):
        url = 'https://opentdb.com/api.php?amount=1&type=multiple'
        if self.category:
            url += f'&category={self.category}'
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as r:
                data = await r.json()
        q = data['results'][0]
        self.question = discord.utils.escape_markdown(q['question'])
        self.correct = q['correct_answer']
        opts = q['incorrect_answers'] + [q['correct_answer']]
        random.shuffle(opts)
        self.options = opts

    def render(self):
        embed=discord.Embed(title="Trivia", description=self.question, color=0xFFD700)
        return embed

    def build_view(self):
        view=discord.ui.View(timeout=None)
        for opt in self.options:
            view.add_item(TriviaButton(opt, self))
        return view

    async def on_interaction(self, interaction): pass

    async def answer(self, interaction, choice: str):
        if choice==self.correct:
            desc = f"✅ Correct! The answer was **{self.correct}**."
        else:
            desc = f"❌ Wrong! It was **{self.correct}**."
        embed=discord.Embed(title="Trivia", description=desc)
        await interaction.response.edit_message(embed=embed, view=None)

class TriviaButton(discord.ui.Button):
    def __init__(self, label, session):
        super().__init__(style=discord.ButtonStyle.secondary, label=label[:100])
        self.session=session
    async def callback(self, interaction: discord.Interaction):
        await self.session.answer(interaction, self.label)

# ----------------------------------------
# FlagMatchSession
# ----------------------------------------
class FlagMatchSession(BaseSession):
    def __init__(self, manager, interaction):
        super().__init__(manager, interaction)
        self.flags   = []  # list of (name, url)
        self.correct = None

    async def start(self) -> discord.Message:
        # load four flags and pick the correct one
        await self.fetch_flags()
        # now self.correct is set, so render() will work
        return await super().start()

    async def fetch_flags(self):
        # get 4 random countries
        async with aiohttp.ClientSession() as session:
            async with session.get('https://restcountries.com/v3.1/all') as r:
                data = await r.json()
        choices = random.sample(data, 4)
        self.flags   = [(c['name']['common'], c['flags']['png']) for c in choices]
        self.correct = random.choice(self.flags)

    def render(self):
        name, url = self.correct
        embed = discord.Embed(
            title="Flag Match",
            description="Which country does this flag belong to?",
            color=0x0000FF
        )
        embed.set_image(url=url)
        return embed

    def build_view(self):
        view = discord.ui.View(timeout=None)
        random.shuffle(self.flags)
        for name, _ in self.flags:
            view.add_item(FlagButton(name, self))
        return view

    async def answer(self, interaction, choice: str):
        # determine result text
        if choice == self.correct[0]:
            result = f"✅ Correct! It was **{self.correct[0]}**!"
        else:
            result = f"❌ Wrong! It was **{self.correct[0]}**."

        # rebuild the embed to show the original flag + question + result
        name, url = self.correct
        embed = discord.Embed(
            title="Flag Match",
            description=f"Which country does this flag belong to?\n{result}",
            color=0x0000FF
        )
        embed.set_image(url=url)

        # attach only our Play Again button
        view = discord.ui.View(timeout=None)
        view.add_item(PlayAgainButton(self))

        await interaction.response.edit_message(embed=embed, view=view)

class FlagButton(discord.ui.Button):
    def __init__(self, label, session):
        super().__init__(style=discord.ButtonStyle.secondary, label=label[:20])
        self.session=session
    async def callback(self, interaction: discord.Interaction):
        await self.session.answer(interaction, self.label)

class PlayAgainButton(discord.ui.Button):
    def __init__(self, session):
        super().__init__(style=discord.ButtonStyle.secondary, label="Play Again")
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        # 1) Pick new flags
        await self.session.fetch_flags()
        # 2) Build the fresh embed + buttons
        embed = self.session.render()
        view  = self.session.build_view()
        # 3) Edit the very same message
        await interaction.response.edit_message(embed=embed, view=view)

# ----------------------------------------
# UnoSession (Simplified)
# ----------------------------------------
class UnoSession(BaseSession):
    COLORS = ["R","G","B","Y"]  # Red, Green, Blue, Yellow
    def __init__(self, manager, interaction, *args):
        super().__init__(manager, interaction)
        # build deck
        self.deck = [f"{color}{num}" for color in self.COLORS for num in range(0,10)] * 2
        random.shuffle(self.deck)
        # deal 5 cards each
        self.hands = {p: [self.deck.pop() for _ in range(5)] for p in self.players}
        self.discard = [self.deck.pop()]

    def render(self):
        idx = self.current
        top = self.discard[-1]
        hand = ','.join(self.hands[self.players[idx]])
        embed = discord.Embed(
            title="UNO (Simplified)",
            description=f"Top: {top} \nYour hand: {hand}",
            color=0xFF4500
        )
        embed.set_footer(text="Play a matching card or draw.")
        return embed

    def build_view(self):
        view = discord.ui.View(timeout=None)
        # buttons for playable cards
        top = self.discard[-1]
        color_top, num_top = top[0], top[1:]
        for card in self.hands[self.players[self.current]]:
            if card[0]==color_top or card[1:]==num_top:
                view.add_item(UnoPlayButton(card, self))
        view.add_item(UnoDrawButton(self))
        return view

    async def on_interaction(self, interaction):
        pass

    async def play_card(self, interaction, card):
        idx = self.current; player = self.players[idx]
        if card not in self.hands[player]:
            return await interaction.response.send_message("You don't have that card!", ephemeral=True)
        top = self.discard[-1]
        if not (card[0]==top[0] or card[1:]==top[1:]):
            return await interaction.response.send_message("Can't play that card!", ephemeral=True)
        self.hands[player].remove(card)
        self.discard.append(card)
        if not self.hands[player]:
            embed = discord.Embed(title="UNO", description=f"{player.mention} wins! 🎉")
            return await interaction.response.edit_message(embed=embed, view=None)
        self.next_player()
        await interaction.response.edit_message(embed=self.render(), view=self.build_view())

    async def draw_card(self, interaction):
        idx = self.current; player = self.players[idx]
        if not self.deck:
            self.deck = self.discard[:-1]
            random.shuffle(self.deck)
        card = self.deck.pop()
        self.hands[player].append(card)
        self.next_player()
        await interaction.response.edit_message(embed=self.render(), view=self.build_view())

class UnoPlayButton(discord.ui.Button):
    def __init__(self, card, session):
        super().__init__(style=discord.ButtonStyle.secondary, label=card)
        self.card = card; self.session = session
    async def callback(self, interaction):
        await self.session.play_card(interaction, self.card)

class UnoDrawButton(discord.ui.Button):
    def __init__(self, session):
        super().__init__(style=discord.ButtonStyle.primary, label="Draw")
        self.session = session
    async def callback(self, interaction):
        await self.session.draw_card(interaction)

# ----------------------------------------
# BattleSession (1v1 health-based fight)
# ----------------------------------------
class BattleSession(BaseSession):
    def __init__(self, manager, interaction, opponent=None):
        super().__init__(manager, interaction, opponent)
        self.hp = {p:100 for p in self.players}

    def render(self):
        lines = [f"{p.display_name}: {self.hp[p]} HP" for p in self.players]
        embed = discord.Embed(
            title="Battle",
            description="\n".join(lines),
            color=0x8B0000
        )
        embed.set_footer(text=f"{self.players[self.current].mention}'s turn.")
        return embed

    def build_view(self):
        view = discord.ui.View(timeout=None)
        view.add_item(BattleButton("Strike", self))
        view.add_item(BattleButton("Heal", self))
        return view

    async def action(self, interaction, choice):
        actor = self.players[self.current]
        target = self.players[(self.current+1)%len(self.players)]
        if choice=="Strike":
            dmg=random.randint(10,25)
            self.hp[target]-=dmg
            res=f"{actor.display_name} strikes {target.display_name} for {dmg} damage!"
        else:
            heal=random.randint(5,15)
            self.hp[actor]=min(100,self.hp[actor]+heal)
            res=f"{actor.display_name} heals for {heal} HP!"
        if self.hp[target]<=0:
            embed=discord.Embed(title="Battle", description=f"{actor.display_name} wins! 🎉")
            return await interaction.response.edit_message(embed=embed, view=None)
        self.next_player()
        embed=self.render(); embed.set_footer(text=res)
        await interaction.response.edit_message(embed=embed, view=self.build_view())

class BattleButton(discord.ui.Button):
    def __init__(self,label,session):
        super().__init__(style=discord.ButtonStyle.primary,label=label)
        self.choice=label;self.session=session
    async def callback(self,interaction): await self.session.action(interaction,self.choice)

# ----------------------------------------
# Cog Definition
# ----------------------------------------
class Games(commands.Cog):
    """A Cog housing turn-based games using Discord interactions."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.manager = GameManager(bot)

    @app_commands.command(name="tictactoe", description="Play Tic-Tac-Toe with another user.")
    @app_commands.describe(opponent="Opponent (optional)")
    async def tictactoe(self, interaction: discord.Interaction, opponent: discord.Member = None):
        await self.manager.start_game(interaction, "tictactoe", opponent)
        await log_action(self.bot, interaction)

    @app_commands.command(name="connect4", description="Play Connect 4 with another user.")
    @app_commands.describe(opponent="Opponent (optional)")
    async def connect4(self, interaction: discord.Interaction, opponent: discord.Member = None):
        await self.manager.start_game(interaction, "connect4", opponent)
        await log_action(self.bot, interaction)

    @app_commands.command(name="chess", description="Play Chess with another user or bot.")
    @app_commands.describe(opponent="Opponent (optional)")
    async def chess(self, interaction: discord.Interaction, opponent: discord.Member = None):
        await self.manager.start_game(interaction, "chess", opponent)
        await log_action(self.bot, interaction)
    
    @app_commands.command(name="hangman", description="Play Hangman.")
    @app_commands.describe(length="Word length (optional)")
    async def hangman(self, interaction: discord.Interaction, length: int = random.randint(4, 13)):
        await self.manager.start_game(interaction, "hangman", length)
        await log_action(self.bot, interaction)

    @app_commands.command(name="wordle", description="Play Wordle.")
    @app_commands.describe(length="Word length")
    async def wordle(self, interaction: discord.Interaction, length: int = 5):
        await self.manager.start_game(interaction, "wordle", length)
        await log_action(self.bot, interaction)

    @app_commands.command(name="trivia", description="Answer a trivia question.")
    @app_commands.describe(category="Open Trivia DB category ID (optional)")
    async def trivia(self, interaction: discord.Interaction, category: str = None):
        await self.manager.start_game(interaction, "trivia", category)
        await log_action(self.bot, interaction)

    @app_commands.command(name="flagmatch", description="Match a country to its flag.")
    async def flagmatch(self, interaction: discord.Interaction):
        await self.manager.start_game(interaction, "flagmatch")
        await log_action(self.bot, interaction)

    @app_commands.command(name="uno", description="Play simplified UNO with color/number cards.")
    async def uno(self, interaction: discord.Interaction):
        await self.manager.start_game(interaction, "uno")
        await log_action(self.bot, interaction)

    @app_commands.command(name="battle", description="Battle another player or bot.")
    @app_commands.describe(opponent="Opponent (optional)")
    async def battle(self, interaction: discord.Interaction, opponent: discord.Member = None):
        await self.manager.start_game(interaction, "battle", opponent)
        await log_action(self.bot, interaction)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            msg = interaction.message
            # only handle it if we really have a session for that message
            if msg and msg.id in self.manager.sessions:
                await self.manager.handle_interaction(interaction)

async def setup(bot):
    await bot.add_cog(Games(bot))
