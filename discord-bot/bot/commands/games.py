import random
import discord
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
        msg_id = interaction.message.id
        session = self.sessions.get(msg_id)
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
        if opponent:
            self.players.append(opponent)
        else:
            self.players.append(manager.bot.user)
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
        # overridden in subclasses
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
                    if (r, c) in self.ship_positions[opponent_idx]:
                        row += '❌'
                    else:
                        row += '⚫'
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
                label = f"{chr(65+r)}{c+1}"
                view.add_item(BattleshipButton(r, c, self, label))
        return view

    async def on_interaction(self, interaction: discord.Interaction):
        # handled in button callbacks
        pass

    async def handle_fire(self, interaction, r, c):
        idx = self.current
        opponent_idx = 1 - idx
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

    @app_commands.command(name="connect4", description="Play Connect 4 with another user.")
    @app_commands.describe(opponent="Opponent (optional)")
    async def connect4(self, interaction: discord.Interaction, opponent: discord.Member = None):
        await self.manager.start_game(interaction, "connect4", opponent)

    @app_commands.command(name="reversi", description="Play Reversi (Othello).")
    @app_commands.describe(opponent="Opponent (optional)")
    async def reversi(self, interaction: discord.Interaction, opponent: discord.Member = None):
        await self.manager.start_game(interaction, "reversi", opponent)

    @app_commands.command(name="mancala", description="Play Mancala.")
    @app_commands.describe(opponent="Opponent (optional)")
    async def mancala(self, interaction: discord.Interaction, opponent: discord.Member = None):
        await self.manager.start_game(interaction, "mancala", opponent)

    @app_commands.command(name="battleship", description="Play Battleship with another user or bot.")
    @app_commands.describe(opponent="The user you want to challenge (optional)")
    async def battleship(self, interaction: discord.Interaction, opponent: discord.Member = None):
        await self.manager.start_game(interaction, "battleship", opponent)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            await self.manager.handle_interaction(interaction)

async def setup(bot):
    await bot.add_cog(Games(bot))
