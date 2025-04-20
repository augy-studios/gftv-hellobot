import random
import discord
import chess
import xiangqi
from discord import app_commands
from discord.ext import commands
from core.logger import log_action

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
        }
        SessionClass = session_map.get(game_key)
        if not SessionClass:
            return await interaction.response.send_message(f"Game '{game_key}' not implemented yet.", ephemeral=True)

        # opponent may be passed for PvP games
        opponent = args[0] if args else None
        session = SessionClass(self, interaction, opponent)
        message = await session.start()
        self.sessions[message.id] = session

    async def handle_interaction(self, interaction: discord.Interaction):
        session = self.sessions.get(interaction.message.id)
        if session:
            await session.on_interaction(interaction)
        else:
            await interaction.response.send_message("Session expired or not found.", ephemeral=True)

# ----------------------------------------
# Base Session
# ----------------------------------------
class BaseSession:
    def __init__(self, manager: GameManager, interaction: discord.Interaction, opponent: discord.Member = None):
        self.manager = manager
        self.ctx = interaction
        self.channel = interaction.channel
        self.players = [interaction.user]
        self.players.append(opponent or manager.bot.user)
        self.current = 0

    async def start(self) -> discord.Message:
        embed = self.render()
        view = self.build_view()
        await self.initial_response(embed, view)
        return self.message

    async def initial_response(self, embed: discord.Embed, view: discord.ui.View):
        await self.manager.bot.wait_until_ready()
        self.message = await self.channel.send(embed=embed, view=view)

    async def on_interaction(self, interaction: discord.Interaction):
        pass

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

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            await self.manager.handle_interaction(interaction)

async def setup(bot):
    await bot.add_cog(Games(bot))
