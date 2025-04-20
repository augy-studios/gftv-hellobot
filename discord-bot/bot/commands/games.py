import random
import json
import aiohttp
import discord
import chess
import xiangqi
from discord import app_commands
from discord.ext import commands
from core.logger import log_action

# Load wordlist for hangman and wordle
def load_wordlist(length=None):
    with open('wordlist.json') as f:
        data = json.load(f)
    if length:
        # fetch list for this length
        return [w.lower() for w in data.get(str(length), [])]
    # flatten all lists
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
            "reversi": ReversiSession,
            "mancala": MancalaSession,
            "battleship": BattleshipSession,
            "checkers": CheckersSession,
            "chess": ChessSession,
            "xiangqi": XiangqiSession,
            "risk": RiskSession,
            "hangman": HangmanSession,
            "wordle": WordleSession,
            "trivia": TriviaSession,
            "ladder": LadderSession,
            "flagmatch": FlagMatchSession,
            "catan": CatanSession,
            "uno": UnoSession,
            "blackjack": BlackjackSession,
            "adventure": AdventureSession,
            "battle": BattleSession,
            "dicecombat": DiceCombatSession,
        }
        SessionClass = session_map.get(game_key)
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
        self.ctx = interaction
        self.channel = interaction.channel
        self.players = [interaction.user]
        if args and isinstance(args[0], discord.Member):
            self.players.append(args[0])
        else:
            self.players.append(manager.bot.user)
        self.current = 0

    async def start(self) -> discord.Message:
        embed = self.render()
        view = self.build_view()
        await self.manager.bot.wait_until_ready()
        self.message = await self.channel.send(embed=embed, view=view)
        return self.message

    async def on_interaction(self, interaction: discord.Interaction):
        pass  # override in subclasses

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
# Reversi (Othello)
# ----------------------------------------
class ReversiSession(BaseSession):
    SIZE=8
    SYMBOLS=['⚫','⚪']

    def __init__(self, manager, interaction, opponent):
        super().__init__(manager, interaction, opponent)
        # None=empty, 0=black,1=white
        self.board=[[None]*self.SIZE for _ in range(self.SIZE)]
        mid=self.SIZE//2
        self.board[mid-1][mid-1]=1; self.board[mid][mid]=1
        self.board[mid-1][mid]=0; self.board[mid][mid-1]=0

    def render(self):
        lines=[]
        for r in range(self.SIZE):
            line=''.join(
                self.SYMBOLS[self.board[r][c]] if self.board[r][c] is not None else '◻️'
                for c in range(self.SIZE)
            )
            lines.append(line)
        embed=discord.Embed(
            title="Reversi",
            description=f"{self.players[self.current].mention}'s turn ({self.SYMBOLS[self.current]})\n"+"\n".join(lines),
            color=0x008888
        )
        embed.set_footer(text="Click a valid square to place.")
        return embed
    
    def build_view(self):
        view=discord.ui.View(timeout=None)
        for r in range(self.SIZE):
            for c in range(self.SIZE):
                view.add_item(ReversiButton(r,c,self))
        return view

    async def on_interaction(self, interaction): pass

    async def handle_move(self, interaction, r, c):
        if interaction.user!=self.players[self.current]:
            return await interaction.response.send_message("Not your turn!", ephemeral=True)
        if self.board[r][c] is not None or not self._can_flip(r,c):
            return await interaction.response.send_message("Invalid move!", ephemeral=True)
        self.board[r][c]=self.current
        self._flip_pieces(r,c)
        self.next_player()
        embed=self.render(); view=self.build_view()
        await interaction.response.edit_message(embed=embed, view=view)

    def _can_flip(self,r,c):
        return bool(self._collect_flips(r,c))

    def _collect_flips(self,r,c):
        flips=[]; opp=1-self.current
        dirs=[(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]
        for dr,dc in dirs:
            path=[]; nr, nc = r+dr, c+dc
            while 0<=nr<self.SIZE and 0<=nc<self.SIZE and self.board[nr][nc]==opp:
                path.append((nr,nc)); nr+=dr; nc+=dc
            if path and 0<=nr<self.SIZE and 0<=nc<self.SIZE and self.board[nr][nc]==self.current:
                flips.extend(path)
        return flips

    def _flip_pieces(self,r,c):
        for nr,nc in self._collect_flips(r,c):
            self.board[nr][nc]=self.current

class ReversiButton(discord.ui.Button):
    def __init__(self,r,c,session):
        super().__init__(style=discord.ButtonStyle.primary, label='◻️', row=r)
        self.r, self.c, self.session = r,c,session
    async def callback(self, interaction):
        await self.session.handle_move(interaction,self.r,self.c)

# ----------------------------------------
# Mancala (Kalah)
# ----------------------------------------
class MancalaSession(BaseSession):
    PITS=6

    def __init__(self, manager, interaction, opponent):
        super().__init__(manager, interaction, opponent)
        # pits[ player ][0-5 ], stores[player]
        self.pits=[[4]*self.PITS for _ in range(2)]
        self.stores=[0,0]

    def render(self):
        top=' '.join(str(self.pits[1][i]) for i in range(self.PITS-1,-1,-1))
        bottom=' '.join(str(self.pits[0][i]) for i in range(self.PITS))
        embed=discord.Embed(
            title="Mancala",
            description=(f"Store2: {self.stores[1]}\n"+ top +"\n"+ bottom +"\n"+ f"Store1: {self.stores[0]}\n"+
                         f"{self.players[self.current].mention}'s turn. Click a pit (1-{self.PITS}) to sow."),
            color=0x884400
        )
        return embed

    def build_view(self):
        view=discord.ui.View(timeout=None)
        for i in range(self.PITS):
            view.add_item(MancalaButton(i,self))
        return view

    async def on_interaction(self, interaction): pass

    async def handle_move(self, interaction, pit):
        if interaction.user!=self.players[self.current]:
            return await interaction.response.send_message("Not your turn!", ephemeral=True)
        seeds=self.pits[self.current][pit]
        if seeds==0: return await interaction.response.send_message("Empty pit!", ephemeral=True)
        self.pits[self.current][pit]=0
        idx=pit; player=self.current
        while seeds>0:
            idx+=1
            if idx==self.PITS and player!=self.current:
                idx=0; player=1-player
            if idx<self.PITS:
                self.pits[player][idx]+=1
                seeds-=1
            else:
                self.stores[player]+=1; seeds-=1; idx=-1; player=1-player
        # next player
        self.next_player()
        embed=self.render(); view=self.build_view()
        await interaction.response.edit_message(embed=embed, view=view)

class MancalaButton(discord.ui.Button):
    def __init__(self,pit,session):
        super().__init__(style=discord.ButtonStyle.secondary, label=str(pit+1))
        self.pit,self.session=pit,session
    async def callback(self, interaction):
        await self.session.handle_move(interaction,self.pit)

# ----------------------------------------
# Battleship
# ----------------------------------------
class BattleshipSession(BaseSession):
    SIZE = 5
    SHIP_SIZES = [2, 3, 4]

    def __init__(self, manager, interaction, opponent):
        super().__init__(manager, interaction, opponent)
        # positions: list of sets per player
        self.ship_positions = [self._place_ships(), self._place_ships()]
        self.guesses = [set(), set()]

    def _place_ships(self):
        positions = set()
        for size in self.SHIP_SIZES:
            placed = False
            while not placed:
                orient = random.choice([0, 1])  # 0 horizontal, 1 vertical
                if orient == 0:
                    row = random.randrange(self.SIZE)
                    col = random.randrange(self.SIZE - size + 1)
                    coords = [(row, col + i) for i in range(size)]
                else:
                    row = random.randrange(self.SIZE - size + 1)
                    col = random.randrange(self.SIZE)
                    coords = [(row + i, col) for i in range(size)]
                if not any(c in positions for c in coords):
                    positions.update(coords)
                    placed = True
        return positions

    def render(self):
        idx = self.current
        opponent_idx = 1 - idx
        lines = []
        for r in range(self.SIZE):
            row = ''
            for c in range(self.SIZE):
                if (r, c) in self.guesses[idx]:
                    row += '❌' if (r, c) in self.ship_positions[opponent_idx] else '⚫'
                else:
                    row += '⬜'
            lines.append(row)
        embed = discord.Embed(
            title="Battleship",
            description=(f"{self.players[idx].mention}'s turn — fire at a coordinate:\n" + '\n'.join(lines)),
            color=0x0000ff
        )
        embed.set_footer(text="Click a square to fire.")
        return embed

    def build_view(self):
        view = discord.ui.View(timeout=None)
        for r in range(self.SIZE):
            for c in range(self.SIZE):
                label = f"{chr(65 + r)}{c + 1}"
                view.add_item(BattleshipButton(r, c, self, label))
        return view

    async def on_interaction(self, interaction: discord.Interaction):
        pass

    async def handle_fire(self, interaction, r, c):
        idx, opponent_idx = self.current, 1 - self.current
        if interaction.user != self.players[idx]:
            return await interaction.response.send_message("Not your turn!", ephemeral=True)
        if (r, c) in self.guesses[idx]:
            return await interaction.response.send_message("Already fired there!", ephemeral=True)
        self.guesses[idx].add((r, c))
        hit = (r, c) in self.ship_positions[opponent_idx]
        if hit:
            self.ship_positions[opponent_idx].remove((r, c))
        # check win
        if not self.ship_positions[opponent_idx]:
            embed = discord.Embed(
                title="Battleship",
                description=f"{self.players[idx].mention} sank all ships and wins! 🎉",
                color=0xff0000
            )
            return await interaction.response.edit_message(embed=embed, view=None)
        # prepare next turn
        result = "Hit! ✅" if hit else "Miss! ❌"
        self.next_player()
        embed = self.render()
        embed.set_footer(text=result)
        await interaction.response.edit_message(embed=embed, view=self.build_view())

class BattleshipButton(discord.ui.Button):
    def __init__(self, r, c, session, label):
        super().__init__(style=discord.ButtonStyle.primary, label=label, row=r)
        self.r = r
        self.c = c
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        await self.session.handle_fire(interaction, self.r, self.c)

# ----------------------------------------
# Checkers
# ----------------------------------------
class CheckersSession(BaseSession):
    SIZE = 8
    SYMBOLS = {0: '⚫', 1: '🔴'}

    def __init__(self, manager, interaction, opponent):
        super().__init__(manager, interaction, opponent)
        self.board = [[None] * self.SIZE for _ in range(self.SIZE)]
        for r in range(self.SIZE):
            for c in range(self.SIZE):
                if (r + c) % 2 == 1:
                    if r < 3:
                        self.board[r][c] = 0
                    elif r > 4:
                        self.board[r][c] = 1
        self.selected = None

    def render(self):
        lines = []
        for r in range(self.SIZE):
            row = ''
            for c in range(self.SIZE):
                piece = self.board[r][c]
                if piece is None:
                    row += '⬛' if (r + c) % 2 else '⬜'
                else:
                    row += self.SYMBOLS[piece]
            lines.append(row)
        embed = discord.Embed(
            title="Checkers",
            description='\n'.join(lines),
            color=0x8B4513
        )
        if self.selected:
            sr, sc = self.selected
            embed.set_footer(text=f"Selected {chr(65+sc)}{sr+1}, choose destination.")
        else:
            embed.set_footer(text=f"{self.players[self.current].mention}'s turn ({self.SYMBOLS[self.current]}). Select piece.")
        return embed

    def build_view(self):
        view = discord.ui.View(timeout=None)
        for r in range(self.SIZE):
            for c in range(self.SIZE):
                if (r + c) % 2 == 1:
                    label = f"{chr(65+c)}{r+1}"
                    view.add_item(CheckersButton(r, c, self, label))
        return view

    async def on_interaction(self, interaction: discord.Interaction):
        pass

    async def handle_click(self, interaction, r, c):
        if interaction.user != self.players[self.current]:
            return await interaction.response.send_message("Not your turn!", ephemeral=True)
        if self.selected is None:
            if self.board[r][c] != self.current:
                return await interaction.response.send_message("Select your own piece!", ephemeral=True)
            moves = self.valid_moves(r, c)
            if not moves:
                return await interaction.response.send_message("No valid moves!", ephemeral=True)
            self.selected = (r, c)
            embed = self.render()
            view = self.build_view()
            return await interaction.response.edit_message(embed=embed, view=view)
        else:
            sr, sc = self.selected
            if (r, c) not in self.valid_moves(sr, sc):
                return await interaction.response.send_message("Invalid destination!", ephemeral=True)
            self.board[sr][sc] = None
            self.board[r][c] = self.current
            if abs(r - sr) == 2:
                mr = (r + sr) // 2
                mc = (c + sc) // 2
                self.board[mr][mc] = None
            if not any(
                self.board[i][j] == (1 - self.current)
                for i in range(self.SIZE)
                for j in range(self.SIZE)
            ):
                embed = discord.Embed(
                    title="Checkers",
                    description=f"{self.players[self.current].mention} wins! 🎉",
                    color=0xFFFF00
                )
                return await interaction.response.edit_message(embed=embed, view=None)
            self.selected = None
            self.next_player()
            embed = self.render()
            view = self.build_view()
            return await interaction.response.edit_message(embed=embed, view=view)

    def valid_moves(self, r, c):
        moves = []
        direction = 1 if self.current == 0 else -1
        for dc in (-1, 1):
            nr, nc = r + direction, c + dc
            if 0 <= nr < self.SIZE and 0 <= nc < self.SIZE and self.board[nr][nc] is None:
                moves.append((nr, nc))
            jr, jc = r + 2 * direction, c + 2 * dc
            if (
                0 <= jr < self.SIZE
                and 0 <= jc < self.SIZE
                and self.board[nr][nc] == 1 - self.current
                and self.board[jr][jc] is None
            ):
                moves.append((jr, jc))
        return moves

class CheckersButton(discord.ui.Button):
    def __init__(self, r, c, session, label):
        super().__init__(style=discord.ButtonStyle.secondary, label=label, row=r)
        self.r = r
        self.c = c
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        await self.session.handle_click(interaction, self.r, self.c)

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
# XiangqiSession
# ----------------------------------------
class XiangqiSession(BaseSession):
    def __init__(self, manager, interaction, opponent):
        super().__init__(manager, interaction, opponent)
        self.board = xiangqi.Board()

    def render(self):
        board_str = str(self.board)
        embed = discord.Embed(
            title="Xiangqi",
            description=f"```\n{board_str}\n```",
            color=0xAAAAAA
        )
        embed.set_footer(text=f"{self.players[self.current].mention}'s turn. Click Move.")
        return embed

    def build_view(self):
        view = discord.ui.View(timeout=None)
        view.add_item(XiangqiMoveButton(self))
        return view

    async def on_interaction(self, interaction: discord.Interaction): pass

    async def make_move(self, interaction, uci: str):
        try:
            move = xiangqi.Move.from_uci(uci)
            if not self.board.is_legal(move):
                raise ValueError
            self.board.push(move)
        except Exception:
            return await interaction.response.send_message("Invalid Xiangqi move! UCI format.", ephemeral=True)
        if self.board.is_checkmated():
            return await interaction.response.edit_message(
                embed=discord.Embed(title="Xiangqi", description=f"Checkmate — {interaction.user.mention} wins! 🎉"), view=None)
        if self.board.is_stalemated():
            return await interaction.response.edit_message(
                embed=discord.Embed(title="Xiangqi", description="Draw! 🤝"), view=None)
        self.next_player()
        await interaction.response.edit_message(embed=self.render(), view=self.build_view())

class XiangqiMoveButton(discord.ui.Button):
    def __init__(self, session):
        super().__init__(style=discord.ButtonStyle.primary, label="Move")
        self.session = session
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(XiangqiMoveModal(self.session))

class XiangqiMoveModal(discord.ui.Modal):
    def __init__(self, session):
        super().__init__(title="Enter Xiangqi Move (UCI)")
        self.session = session
        self.move = discord.ui.TextInput(label="Move", placeholder="h2e2", max_length=5)
        self.add_item(self.move)

    async def on_submit(self, interaction: discord.Interaction):
        await self.session.make_move(interaction, self.move.value.strip())

# ----------------------------------------
# RiskSession - Simplified territory conquest
# ----------------------------------------
class RiskSession(BaseSession):
    TERRITORIES = [f"T{i+1}" for i in range(6)]
    OWNER_EMOJIS = ["🔴", "🔵"]

    def __init__(self, manager, interaction, opponent):
        super().__init__(manager, interaction, opponent)
        # assign random owners to 6 territories
        owners = [i % 2 for i in range(len(self.TERRITORIES))]
        random.shuffle(owners)
        self.owners = owners  # list of 0 or 1

    def render(self):
        lines = []
        for idx, name in enumerate(self.TERRITORIES):
            emoji = self.OWNER_EMOJIS[self.owners[idx]]
            lines.append(f"{name}: {emoji}")
        embed = discord.Embed(
            title="Risk",
            description="\n".join(lines),
            color=0x00AAAA
        )
        embed.set_footer(text=f"{self.players[self.current].mention}'s turn. Click Attack or End Turn.")
        return embed

    def build_view(self):
        view = discord.ui.View(timeout=None)
        view.add_item(RiskAttackButton(self))
        view.add_item(RiskEndButton(self))
        return view

    async def on_interaction(self, interaction: discord.Interaction):
        # handled by buttons
        pass

    async def attack(self, interaction, frm: str, to: str):
        try:
            i_from = self.TERRITORIES.index(frm.upper())
            i_to = self.TERRITORIES.index(to.upper())
        except ValueError:
            return await interaction.response.send_message("Invalid territory names!", ephemeral=True)
        if self.owners[i_from] != self.current:
            return await interaction.response.send_message("You don't own the attack territory!", ephemeral=True)
        if self.owners[i_to] == self.current:
            return await interaction.response.send_message("You already own the target territory!", ephemeral=True)
        # dice roll
        attack_roll = random.randint(1, 6)
        defend_roll = random.randint(1, 6)
        result = f"You rolled {attack_roll}, defender rolled {defend_roll}. "
        if attack_roll > defend_roll:
            self.owners[i_to] = self.current
            result += "You conquered it! 🎉"
        else:
            result += "Attack failed."
        # check win
        if all(o == self.current for o in self.owners):
            embed = discord.Embed(
                title="Risk", description=f"{self.players[self.current].mention} controls all territories and wins! 🎉", color=0xFFFF00
            )
            return await interaction.response.edit_message(embed=embed, view=None)
        # next turn
        self.next_player()
        embed = self.render()
        embed.set_footer(text=result)
        await interaction.response.edit_message(embed=embed, view=self.build_view())

    async def end_turn(self, interaction):
        self.next_player()
        embed = self.render()
        await interaction.response.edit_message(embed=embed, view=self.build_view())

class RiskAttackButton(discord.ui.Button):
    def __init__(self, session):
        super().__init__(style=discord.ButtonStyle.danger, label="Attack")
        self.session = session
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(RiskAttackModal(self.session))

class RiskAttackModal(discord.ui.Modal):
    def __init__(self, session):
        super().__init__(title="Risk Attack")
        self.session = session
        self.frm = discord.ui.TextInput(label="From (e.g. T1)")
        self.to = discord.ui.TextInput(label="To (e.g. T2)")
        self.add_item(self.frm)
        self.add_item(self.to)

    async def on_submit(self, interaction: discord.Interaction):
        await self.session.attack(interaction, self.frm.value, self.to.value)

class RiskEndButton(discord.ui.Button):
    def __init__(self, session):
        super().__init__(style=discord.ButtonStyle.secondary, label="End Turn")
        self.session = session
    async def callback(self, interaction: discord.Interaction):
        await self.session.end_turn(interaction)

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
            description=f"{display}\nWrong guesses: {self.wrong}/{self.MAX_WRONG}",
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
# LadderSession for Word Ladders
# ----------------------------------------
class LadderSession(BaseSession):
    def __init__(self, manager, interaction, start: str, end: str):
        super().__init__(manager, interaction)
        self.start = start.lower()
        self.end = end.lower()
        self.path = self.find_path()

    def find_path(self):
        words = set(load_wordlist(len(self.start)))
        queue = [[self.start]]
        visited = {self.start}
        while queue:
            path = queue.pop(0)
            last = path[-1]
            if last==self.end:
                return path
            for i in range(len(last)):
                for c in 'abcdefghijklmnopqrstuvwxyz':
                    w = last[:i]+c+last[i+1:]
                    if w in words and w not in visited:
                        visited.add(w)
                        queue.append(path+[w])
        return None

    def render(self):
        if not self.path:
            desc = f"No ladder found from {self.start} to {self.end}."
        else:
            desc = ' -> '.join(self.path)
        embed=discord.Embed(title="Word Ladder", description=desc)
        return embed

    def build_view(self):
        return discord.ui.View()  # no interactions

# ----------------------------------------
# FlagMatchSession
# ----------------------------------------
class FlagMatchSession(BaseSession):
    def __init__(self, manager, interaction):
        super().__init__(manager, interaction)
        self.flags = []  # list of (name, url)
        self.correct = None

    async def start(self):
        await self.fetch_flags()
        return await super().start()

    async def fetch_flags(self):
        # get 4 random countries
        async with aiohttp.ClientSession() as session:
            async with session.get('https://restcountries.com/v3.1/all') as r:
                data = await r.json()
        choices = random.sample(data, 4)
        self.flags = [(c['name']['common'], c['flags']['png']) for c in choices]
        self.correct = random.choice(self.flags)

    def render(self):
        name, url = self.correct
        embed=discord.Embed(title="Flag Match", description="Which country does this flag belong to?", color=0x0000FF)
        embed.set_image(url=url)
        return embed

    def build_view(self):
        view=discord.ui.View(timeout=None)
        random.shuffle(self.flags)
        for name, _ in self.flags:
            view.add_item(FlagButton(name, self))
        return view

    async def on_interaction(self, interaction): pass

    async def answer(self, interaction, choice: str):
        if choice==self.correct[0]:
            desc = "✅ Correct!"
        else:
            desc = f"❌ Wrong! It was {self.correct[0]}."
        embed=discord.Embed(title="Flag Match", description=desc)
        await interaction.response.edit_message(embed=embed, view=None)

class FlagButton(discord.ui.Button):
    def __init__(self, label, session):
        super().__init__(style=discord.ButtonStyle.secondary, label=label[:20])
        self.session=session
    async def callback(self, interaction: discord.Interaction):
        await self.session.answer(interaction, self.label)

# ----------------------------------------
# CatanSession (Simplified)
# ----------------------------------------
class CatanSession(BaseSession):
    RESOURCES = ["wood", "brick", "sheep", "wheat", "ore"]
    COST = {"wood":1, "brick":1, "sheep":1, "wheat":1}

    def __init__(self, manager, interaction, *args):
        super().__init__(manager, interaction)
        # initialize resource counts and victory points
        self.resources = [{r:0 for r in self.RESOURCES} for _ in self.players]
        self.vp = [0 for _ in self.players]

    def render(self):
        idx = self.current
        lines = []
        for i, player in enumerate(self.players):
            res = ', '.join(f"{r}: {self.resources[i][r]}" for r in self.RESOURCES)
            lines.append(f"{player.display_name}: VP {self.vp[i]} | {res}")
        embed = discord.Embed(
            title="Catan (Simplified)",
            description="\n".join(lines),
            color=0xDAA520
        )
        embed.set_footer(text=f"{self.players[idx].mention}'s turn. Roll dice or build settlement.")
        return embed

    def build_view(self):
        view = discord.ui.View(timeout=None)
        view.add_item(CatanRollButton(self))
        view.add_item(CatanBuildButton(self))
        return view

    async def on_interaction(self, interaction):
        pass

    async def roll_dice(self, interaction):
        idx = self.current
        d1, d2 = random.randint(1,6), random.randint(1,6)
        # each player gains one random resource per die
        for i in range(len(self.players)):
            for _ in (d1, d2):
                res = random.choice(self.RESOURCES)
                self.resources[i][res] += 1
        result = f"Rolled {d1}+{d2}. All players gain resources."
        self.next_player()
        embed = self.render(); embed.set_footer(text=result)
        await interaction.response.edit_message(embed=embed, view=self.build_view())

    async def build_settlement(self, interaction):
        idx = self.current
        # check cost
        if any(self.resources[idx][r] < c for r, c in self.COST.items()):
            return await interaction.response.send_message("Not enough resources!", ephemeral=True)
        for r, c in self.COST.items():
            self.resources[idx][r] -= c
        self.vp[idx] += 1
        result = f"Built settlement! +1 VP."
        if self.vp[idx] >= 3:
            embed = discord.Embed(
                title="Catan", description=f"{self.players[idx].mention} wins with {self.vp[idx]} VP! 🎉"
            )
            return await interaction.response.edit_message(embed=embed, view=None)
        self.next_player()
        embed = self.render(); embed.set_footer(text=result)
        await interaction.response.edit_message(embed=embed, view=self.build_view())

class CatanRollButton(discord.ui.Button):
    def __init__(self, session):
        super().__init__(style=discord.ButtonStyle.primary, label="Roll Dice")
        self.session = session
    async def callback(self, interaction):
        await self.session.roll_dice(interaction)

class CatanBuildButton(discord.ui.Button):
    def __init__(self, session):
        super().__init__(style=discord.ButtonStyle.success, label="Build Settlement")
        self.session = session
    async def callback(self, interaction):
        await self.session.build_settlement(interaction)

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
# BlackjackSession
# ----------------------------------------
class BlackjackSession(BaseSession):
    DECK = [str(v) for v in range(2,11)] + ['J','Q','K','A']
    VALUE = {**{str(v):v for v in range(2,11)}, 'J':10,'Q':10,'K':10,'A':11}

    def __init__(self, manager, interaction, *args):
        super().__init__(manager, interaction)
        # build and shuffle deck
        self.deck = BlackjackSession.DECK*4
        random.shuffle(self.deck)
        self.hands = {p: [self.deck.pop(), self.deck.pop()] for p in self.players}
        self.stand = {p: False for p in self.players}

    def hand_value(self, hand):
        val = sum(BlackjackSession.VALUE[c] for c in hand)
        # adjust aces
        for c in hand:
            if val>21 and c=='A': val-=10
        return val

    def render(self):
        idx = self.current; player = self.players[idx]
        your = self.hands[player]
        your_val = self.hand_value(your)
        embed = discord.Embed(
            title="Blackjack",
            description=f"Your hand: {','.join(your)} ({your_val})",
            color=0x000000
        )
        embed.set_footer(text="Hit or Stand.")
        return embed

    def build_view(self):
        view = discord.ui.View(timeout=None)
        view.add_item(HitButton(self))
        view.add_item(StandButton(self))
        return view

    async def on_interaction(self, interaction):
        pass

    async def hit(self, interaction):
        player = self.players[self.current]
        self.hands[player].append(self.deck.pop())
        if self.hand_value(self.hands[player])>21:
            embed = discord.Embed(title="Blackjack", description="Bust! You lose.")
            return await interaction.response.edit_message(embed=embed, view=None)
        await interaction.response.edit_message(embed=self.render(), view=self.build_view())

    async def stand_turn(self, interaction):
        player = self.players[self.current]
        self.stand[player] = True
        self.next_player()
        opponent = self.players[self.current]
        # dealer logic: hit until >=17
        while self.hand_value(self.hands[opponent])<17:
            self.hands[opponent].append(self.deck.pop())
        pval = self.hand_value(self.hands[player])
        oval = self.hand_value(self.hands[opponent])
        if oval>21 or pval>oval:
            msg="You win!"
        elif pval<oval:
            msg="You lose."
        else:
            msg="Push."
        embed = discord.Embed(title="Blackjack", description=msg)
        return await interaction.response.edit_message(embed=embed, view=None)

class HitButton(discord.ui.Button):
    def __init__(self, session): super().__init__(style=discord.ButtonStyle.primary, label="Hit"); self.session=session
    async def callback(self, interaction): await self.session.hit(interaction)

class StandButton(discord.ui.Button):
    def __init__(self, session): super().__init__(style=discord.ButtonStyle.secondary, label="Stand"); self.session=session
    async def callback(self, interaction): await self.session.stand_turn(interaction)

# ----------------------------------------
# AdventureSession (Turn-Based RPG)
# ----------------------------------------
class AdventureSession(BaseSession):
    MAX_HP = 100

    def __init__(self, manager, interaction, *args):
        super().__init__(manager, interaction)
        self.hp = {p: self.MAX_HP for p in self.players}
        self.turn_desc = f"{self.players[self.current].mention}, choose your action."  

    def render(self):
        lines = [f"{p.display_name}: {self.hp[p]} HP" for p in self.players]
        embed = discord.Embed(
            title="Adventure RPG",
            description="\n".join(lines),
            color=0x228B22
        )
        embed.set_footer(text=self.turn_desc)
        return embed

    def build_view(self):
        view = discord.ui.View(timeout=None)
        view.add_item(AdventureActionButton("Attack", self))
        view.add_item(AdventureActionButton("Defend", self))
        view.add_item(AdventureActionButton("Flee", self))
        return view

    async def on_interaction(self, interaction):
        pass

    async def action(self, interaction, choice):
        actor = self.players[self.current]
        target = self.players[(self.current+1) % len(self.players)]
        if choice == "Attack":
            dmg = random.randint(5, 20)
            self.hp[target] -= dmg
            result = f"{actor.display_name} attacks {target.display_name} for {dmg} damage!"
        elif choice == "Defend":
            heal = random.randint(5, 15)
            self.hp[actor] = min(self.MAX_HP, self.hp[actor] + heal)
            result = f"{actor.display_name} defends and recovers {heal} HP!"
        else:
            result = f"{actor.display_name} flees! Game over."
            embed = discord.Embed(title="Adventure RPG", description=result)
            return await interaction.response.edit_message(embed=embed, view=None)
        # check for defeat
        if self.hp[target] <= 0:
            embed = discord.Embed(title="Adventure RPG", description=f"{actor.display_name} wins! 🎉")
            return await interaction.response.edit_message(embed=embed, view=None)
        # next turn
        self.next_player()
        self.turn_desc = result
        embed = self.render()
        await interaction.response.edit_message(embed=embed, view=self.build_view())

class AdventureActionButton(discord.ui.Button):
    def __init__(self, label, session):
        super().__init__(style=discord.ButtonStyle.primary, label=label)
        self.choice = label
        self.session = session
    async def callback(self, interaction):
        await self.session.action(interaction, self.choice)

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
# DiceCombatSession (roll d20 or multiple dice)
# ----------------------------------------
class DiceCombatSession(BaseSession):
    def render(self):
        embed=discord.Embed(
            title="Dice Combat",
            description="Roll a d20 or custom dice set.",
            color=0x00008B
        )
        embed.set_footer(text=f"{self.players[self.current].mention}'s turn.")
        return embed

    def build_view(self):
        view=discord.ui.View(timeout=None)
        view.add_item(DiceButton("d20", self))
        view.add_item(DiceButton("2d6", self))
        return view

    async def action(self,interaction,expr):
        rolls=[random.randint(1,int(num)) for num in expr.lower().split('d')[1].split()] if 'd' in expr else []
        # simpler: parse '2d6'
        if 'd' in expr:
            count,num=expr.lower().split('d')
            rolls=[random.randint(1,int(num)) for _ in range(int(count))]
        total=sum(rolls)
        res=f"Rolled {expr}: {rolls} (Total {total})"
        self.next_player()
        embed=discord.Embed(title="Dice Combat", description=res)
        return await interaction.response.edit_message(embed=embed, view=self.build_view())

class DiceButton(discord.ui.Button):
    def __init__(self,label,session):
        super().__init__(style=discord.ButtonStyle.secondary,label=label)
        self.expr=label;self.session=session
    async def callback(self,interaction): await self.session.action(interaction,self.expr)

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

    @app_commands.command(name="reversi", description="Play Reversi (Othello).")
    @app_commands.describe(opponent="Opponent (optional)")
    async def reversi(self, interaction: discord.Interaction, opponent: discord.Member = None):
        await self.manager.start_game(interaction, "reversi", opponent)
        await log_action(self.bot, interaction)

    @app_commands.command(name="mancala", description="Play Mancala.")
    @app_commands.describe(opponent="Opponent (optional)")
    async def mancala(self, interaction: discord.Interaction, opponent: discord.Member = None):
        await self.manager.start_game(interaction, "mancala", opponent)
        await log_action(self.bot, interaction)

    @app_commands.command(name="battleship", description="Play Battleship with another user or bot.")
    @app_commands.describe(opponent="The user you want to challenge (optional)")
    async def battleship(self, interaction: discord.Interaction, opponent: discord.Member = None):
        await self.manager.start_game(interaction, "battleship", opponent)
        await log_action(self.bot, interaction)

    @app_commands.command(name="checkers", description="Play Checkers with another user or bot.")
    @app_commands.describe(opponent="The user you want to challenge (optional)")
    async def checkers(self, interaction: discord.Interaction, opponent: discord.Member = None):
        await self.manager.start_game(interaction, "checkers", opponent)
        await log_action(self.bot, interaction)

    @app_commands.command(name="chess", description="Play Chess with another user or bot.")
    @app_commands.describe(opponent="Opponent (optional)")
    async def chess(self, interaction: discord.Interaction, opponent: discord.Member = None):
        await self.manager.start_game(interaction, "chess", opponent)
        await log_action(self.bot, interaction)

    @app_commands.command(name="xiangqi", description="Play Xiangqi (Chinese Chess) with another user or bot.")
    @app_commands.describe(opponent="Opponent (optional)")
    async def xiangqi(self, interaction: discord.Interaction, opponent: discord.Member = None):
        await self.manager.start_game(interaction, "xiangqi", opponent)
        await log_action(self.bot, interaction)

    @app_commands.command(name="risk", description="Play simplified Risk territory conquest.")
    async def risk(self, interaction: discord.Interaction):
        await self.manager.start_game(interaction, "risk")
        await log_action(self.bot, interaction)

    @app_commands.command(name="hangman", description="Play Hangman.")
    @app_commands.describe(length="Word length (optional)")
    async def hangman(self, interaction: discord.Interaction, length: int = None):
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

    @app_commands.command(name="ladder", description="Solve a word ladder.")
    @app_commands.describe(start="Start word", end="End word")
    async def ladder(self, interaction: discord.Interaction, start: str, end: str):
        await self.manager.start_game(interaction, "ladder", start, end)
        await log_action(self.bot, interaction)

    @app_commands.command(name="flagmatch", description="Match a country to its flag.")
    async def flagmatch(self, interaction: discord.Interaction):
        await self.manager.start_game(interaction, "flagmatch")
        await log_action(self.bot, interaction)

    @app_commands.command(name="catan", description="Play Catan (simplified) with resources and settlements.")
    async def catan(self, interaction: discord.Interaction):
        await self.manager.start_game(interaction, "catan")
        await log_action(self.bot, interaction)

    @app_commands.command(name="uno", description="Play simplified UNO with color/number cards.")
    async def uno(self, interaction: discord.Interaction):
        await self.manager.start_game(interaction, "uno")
        await log_action(self.bot, interaction)

    @app_commands.command(name="blackjack", description="Play Blackjack against the dealer.")
    async def blackjack(self, interaction: discord.Interaction):
        await self.manager.start_game(interaction, "blackjack")
        await log_action(self.bot, interaction)

    @app_commands.command(name="adventure", description="Start a turn-based RPG.")
    async def adventure(self, interaction: discord.Interaction):
        await self.manager.start_game(interaction, "adventure")
        await log_action(self.bot, interaction)

    @app_commands.command(name="battle", description="Battle another player or bot.")
    @app_commands.describe(opponent="Opponent (optional)")
    async def battle(self, interaction: discord.Interaction, opponent: discord.Member = None):
        await self.manager.start_game(interaction, "battle", opponent)
        await log_action(self.bot, interaction)

    @app_commands.command(name="dicecombat", description="Roll dice for combat.")
    async def dicecombat(self, interaction: discord.Interaction):
        await self.manager.start_game(interaction, "dicecombat")
        await log_action(self.bot, interaction)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            await self.manager.handle_interaction(interaction)

async def setup(bot):
    await bot.add_cog(Games(bot))
