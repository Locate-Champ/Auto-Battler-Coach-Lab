"""Player state and actions for TFT game loop."""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

from .types import ChampionInstance
from .constants import (
    STARTING_HP, STARTING_GOLD, STARTING_LEVEL, MAX_LEVEL,
    BENCH_SIZE, BOARD_ROWS, BOARD_COLS, MAX_ITEMS_PER_UNIT,
    BASE_INCOME, MAX_INTEREST, PASSIVE_XP_PER_ROUND,
    REFRESH_COST, XP_COST, XP_PER_BUY,
    LEVEL_XP_REQUIRED, STARTING_ROUND_GOLD,
    SELL_VALUES, NAME_TO_API, NAME_TO_COST,
    CHAMPION_TRAITS, get_streak_gold,
)

if TYPE_CHECKING:
    from simulator.core.combat_engine import CombatEngine
    from .champion_pool import ChampionPool


class Player:
    """Represents a single TFT player's state."""

    def __init__(self, player_id: int):
        self.player_id = player_id

        # Resources
        self.gold = STARTING_GOLD
        self.hp = STARTING_HP
        self.level = STARTING_LEVEL
        self.xp = 0

        # Board: dict mapping (row, col) → ChampionInstance
        self.board: Dict[Tuple[int, int], ChampionInstance] = {}
        # Bench: list of BENCH_SIZE slots (None = empty)
        self.bench: List[Optional[ChampionInstance]] = [None] * BENCH_SIZE
        # Item bench: list of item names
        self.item_bench: List[str] = []
        # Current shop: list of champion names (or None for empty slots)
        self.shop: List[Optional[str]] = [None] * 5

        # Streaks
        self.win_streak = 0
        self.loss_streak = 0

        # Game state
        self.alive = True
        self.placement = 0  # Set when eliminated (1 = winner, 8 = first out)

        # Tracking for upgrades: name → list of (location, ChampionInstance)
        # location is ('board', (row, col)) or ('bench', idx)
        self._upgrade_tracker: Dict[str, int] = {}

    @property
    def max_units(self) -> int:
        """Maximum units allowed on board (equals level)."""
        return self.level

    @property
    def board_count(self) -> int:
        """Number of units currently on the board."""
        return len(self.board)

    # ── Economy ───────────────────────────────────────────────────────────

    def add_income(self, round_num: int):
        """Add round income: base + interest + streak bonus + passive XP."""
        self.xp += PASSIVE_XP_PER_ROUND
        self._check_level_up()

        if round_num < len(STARTING_ROUND_GOLD):
            # Early rounds: fixed gold + interest
            interest = min(math.floor(self.gold / 10), MAX_INTEREST)
            self.gold += interest + STARTING_ROUND_GOLD[round_num]
        else:
            # Standard rounds: base + interest + streak
            interest = min(math.floor(self.gold / 10), MAX_INTEREST)
            streak = max(self.win_streak, self.loss_streak)
            streak_bonus = get_streak_gold(streak)
            self.gold += BASE_INCOME + interest + streak_bonus

    def can_afford(self, amount: int) -> bool:
        return self.gold >= amount

    # ── Leveling ──────────────────────────────────────────────────────────

    def buy_xp(self) -> bool:
        """Buy XP for gold. Returns True if successful."""
        if not self.can_afford(XP_COST):
            return False
        if self.level >= MAX_LEVEL:
            return False
        self.gold -= XP_COST
        self.xp += XP_PER_BUY
        self._check_level_up()
        return True

    def _check_level_up(self):
        """Auto-level when XP threshold is reached."""
        while self.level < MAX_LEVEL:
            required = LEVEL_XP_REQUIRED[self.level]
            if self.xp >= required:
                self.xp -= required
                self.level += 1
            else:
                break

    # ── Shop / Buying ─────────────────────────────────────────────────────

    def buy_champion(self, shop_slot: int, pool: 'ChampionPool') -> bool:
        """Buy a champion from the shop. Returns True if successful."""
        if shop_slot < 0 or shop_slot >= len(self.shop):
            return False
        name = self.shop[shop_slot]
        if name is None:
            return False

        cost = NAME_TO_COST.get(name, 1)
        if not self.can_afford(cost):
            return False

        # Find an empty bench slot
        bench_idx = self._find_empty_bench()
        if bench_idx is None:
            return False

        # Take from pool
        if not pool.take(name):
            return False

        self.gold -= cost
        self.shop[shop_slot] = None

        # Create champion instance
        champ = ChampionInstance(
            name=name,
            api_name=NAME_TO_API.get(name, f'TFT16_{name.capitalize()}'),
            cost=cost,
            star_level=1,
        )
        self.bench[bench_idx] = champ

        # Check for upgrade
        self._check_upgrade(name, pool)
        return True

    def _find_empty_bench(self) -> Optional[int]:
        """Find the first empty bench slot."""
        for i, slot in enumerate(self.bench):
            if slot is None:
                return i
        return None

    # ── Selling ───────────────────────────────────────────────────────────

    def sell_from_board(self, row: int, col: int, pool: 'ChampionPool') -> bool:
        """Sell a champion from the board. Returns True if successful."""
        pos = (row, col)
        champ = self.board.get(pos)
        if champ is None:
            return False
        del self.board[pos]
        self._complete_sell(champ, pool)
        return True

    def sell_from_bench(self, bench_idx: int, pool: 'ChampionPool') -> bool:
        """Sell a champion from the bench. Returns True if successful."""
        if bench_idx < 0 or bench_idx >= BENCH_SIZE:
            return False
        champ = self.bench[bench_idx]
        if champ is None:
            return False
        self.bench[bench_idx] = None
        self._complete_sell(champ, pool)
        return True

    def _complete_sell(self, champ: ChampionInstance, pool: 'ChampionPool'):
        """Handle gold refund and pool return for a sold champion."""
        self.gold += champ.sell_value
        # Return copies to pool (1-star=1, 2-star=3, 3-star=9)
        copies = 3 ** (champ.star_level - 1)
        pool.return_champion(champ.name, copies)
        # Return items to item bench
        self.item_bench.extend(champ.items)

    # ── Board Management ──────────────────────────────────────────────────

    def bench_to_board(self, bench_idx: int, row: int, col: int) -> bool:
        """Move a champion from bench to board. Returns True if successful."""
        if bench_idx < 0 or bench_idx >= BENCH_SIZE:
            return False
        champ = self.bench[bench_idx]
        if champ is None:
            return False
        pos = (row, col)
        if not self._valid_board_pos(pos):
            return False

        # If board slot is occupied, swap
        existing = self.board.get(pos)
        if existing:
            self.bench[bench_idx] = existing
            self.board[pos] = champ
            return True

        # Check board capacity
        if self.board_count >= self.max_units:
            return False

        self.bench[bench_idx] = None
        self.board[pos] = champ
        return True

    def board_to_bench(self, row: int, col: int) -> bool:
        """Move a champion from board to bench. Returns True if successful."""
        pos = (row, col)
        champ = self.board.get(pos)
        if champ is None:
            return False

        bench_idx = self._find_empty_bench()
        if bench_idx is None:
            return False

        del self.board[pos]
        self.bench[bench_idx] = champ
        return True

    def move_on_board(self, from_row: int, from_col: int,
                      to_row: int, to_col: int) -> bool:
        """Move or swap a champion on the board. Returns True if successful."""
        from_pos = (from_row, from_col)
        to_pos = (to_row, to_col)
        if not self._valid_board_pos(from_pos) or not self._valid_board_pos(to_pos):
            return False

        champ = self.board.get(from_pos)
        if champ is None:
            return False

        other = self.board.get(to_pos)
        if other:
            # Swap
            self.board[from_pos] = other
            self.board[to_pos] = champ
        else:
            del self.board[from_pos]
            self.board[to_pos] = champ
        return True

    def _valid_board_pos(self, pos: Tuple[int, int]) -> bool:
        row, col = pos
        return 0 <= row < BOARD_ROWS and 0 <= col < BOARD_COLS

    # ── Upgrades ──────────────────────────────────────────────────────────

    def _check_upgrade(self, name: str, pool: 'ChampionPool'):
        """Check if buying this champion triggers an upgrade (3 → star up).

        Checks for 1→2 star, then immediately checks for 2→3 star.
        """
        for target_star in (1, 2):
            copies = self._find_copies(name, target_star)
            if len(copies) >= 3:
                self._do_upgrade(name, target_star, copies)

    def _find_copies(self, name: str, star_level: int) -> list:
        """Find all copies of a champion at a specific star level.

        Returns list of (location_type, location_key) tuples.
        """
        copies = []
        for pos, champ in self.board.items():
            if champ.name == name and champ.star_level == star_level:
                copies.append(('board', pos))
        for idx, champ in enumerate(self.bench):
            if champ is not None and champ.name == name and champ.star_level == star_level:
                copies.append(('bench', idx))
        return copies

    def _do_upgrade(self, name: str, star_level: int, copies: list):
        """Merge 3 copies into a star-up champion."""
        new_star = star_level + 1

        # Collect all items from the copies being merged
        all_items = []
        for loc_type, loc_key in copies:
            if loc_type == 'board':
                champ = self.board[loc_key]
                all_items.extend(champ.items)
            else:
                champ = self.bench[loc_key]
                all_items.extend(champ.items)

        # Remove all 3 copies
        first_loc = None
        for loc_type, loc_key in copies:
            if first_loc is None:
                first_loc = (loc_type, loc_key)
            if loc_type == 'board':
                del self.board[loc_key]
            else:
                self.bench[loc_key] = None

        # Create upgraded champion
        upgraded = ChampionInstance(
            name=name,
            api_name=NAME_TO_API.get(name, f'TFT16_{name.capitalize()}'),
            cost=NAME_TO_COST.get(name, 1),
            star_level=new_star,
            items=all_items[:MAX_ITEMS_PER_UNIT],
        )
        # Put overflow items on item bench
        if len(all_items) > MAX_ITEMS_PER_UNIT:
            self.item_bench.extend(all_items[MAX_ITEMS_PER_UNIT:])

        # Place upgraded champ in first copy's location
        loc_type, loc_key = first_loc
        if loc_type == 'board':
            self.board[loc_key] = upgraded
        else:
            self.bench[loc_key] = upgraded

    # ── Traits ────────────────────────────────────────────────────────────

    def get_active_traits(self) -> Dict[str, int]:
        """Compute active traits from board units.

        Returns dict of trait_name → unit count.
        """
        trait_counts: Dict[str, int] = {}
        for champ in self.board.values():
            traits = CHAMPION_TRAITS.get(champ.name, [])
            for trait in traits:
                trait_counts[trait] = trait_counts.get(trait, 0) + 1
        return trait_counts

    # ── Combat Bridge ─────────────────────────────────────────────────────

    def build_combat_team(self, engine: 'CombatEngine') -> list:
        """Convert board state into combat Unit objects.

        Args:
            engine: The CombatEngine instance to create units with.

        Returns:
            List of Unit objects ready for run_combat().
        """
        units = []
        for pos, champ in self.board.items():
            unit = engine.create_unit(
                api_name=champ.api_name,
                star_level=champ.star_level,
                position=pos,
                team=0,
                items=champ.items if champ.items else None,
            )
            if unit is not None:
                units.append(unit)
        return units

    # ── HP / Elimination ──────────────────────────────────────────────────

    def take_damage(self, amount: int):
        """Take HP damage. Player is eliminated when HP reaches 0."""
        self.hp = max(0, self.hp - amount)
        if self.hp <= 0:
            self.alive = False

    def win_round(self):
        """Record a round win."""
        self.win_streak += 1
        self.loss_streak = 0
        self.gold += 1  # Win bonus

    def lose_round(self, damage: int):
        """Record a round loss and take damage."""
        self.loss_streak += 1
        self.win_streak = 0
        self.take_damage(damage)

    # ── Helpers ───────────────────────────────────────────────────────────

    def get_all_champions(self) -> List[ChampionInstance]:
        """Get all champions (board + bench) for pool return on elimination."""
        champs = list(self.board.values())
        for slot in self.bench:
            if slot is not None:
                champs.append(slot)
        return champs

    def auto_fill_board(self):
        """Move bench units to board if there's room (end-of-planning)."""
        for idx in range(BENCH_SIZE):
            if self.board_count >= self.max_units:
                break
            champ = self.bench[idx]
            if champ is None:
                continue
            # Find an empty board position
            for row in range(BOARD_ROWS):
                for col in range(BOARD_COLS):
                    if (row, col) not in self.board:
                        self.board[(row, col)] = champ
                        self.bench[idx] = None
                        break
                else:
                    continue
                break

    def __repr__(self):
        return (f"Player({self.player_id}, lvl={self.level}, "
                f"hp={self.hp}, gold={self.gold}, "
                f"board={self.board_count}/{self.max_units})")
