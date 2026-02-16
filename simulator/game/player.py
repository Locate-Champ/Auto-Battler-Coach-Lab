"""Player state and actions for TFT game loop."""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from .types import ChampionInstance
from .constants import (
    STARTING_HP, STARTING_GOLD, STARTING_LEVEL, MAX_LEVEL,
    BENCH_SIZE, BOARD_ROWS, BOARD_COLS, MAX_ITEMS_PER_UNIT,
    ITEM_BENCH_SIZE, ITEM_COMPONENTS_LIST,
    BASE_INCOME, MAX_INTEREST, PASSIVE_XP_PER_ROUND,
    REFRESH_COST, XP_COST, XP_PER_BUY,
    LEVEL_XP_REQUIRED, STARTING_ROUND_GOLD,
    SELL_VALUES, NAME_TO_API, NAME_TO_COST,
    CHAMPION_TRAITS, get_streak_gold,
    is_component, combine_items,
)

if TYPE_CHECKING:
    from simulator.core.combat_engine import CombatEngine
    from .champion_pool import ChampionPool

try:
    from simulator.data.set16_items import ARTIFACT_ITEMS, BASE_COMPLETED, BLACKSMITH_CONFIG
except ImportError:
    BASE_COMPLETED = ()
    ARTIFACT_ITEMS = {}
    BLACKSMITH_CONFIG = {}

_THIEFS_EXCLUDED = frozenset({
    'ThiefsGloves', 'TacticiansCrown', 'TacticiansCape', 'TacticiansShield',
})
_THIEFS_POOL = tuple(name for name in BASE_COMPLETED if name not in _THIEFS_EXCLUDED)

_BILGEWATER_SERPENTS_PER_ROUND = {
    3: 15,
    5: 35,
    7: 65,
    10: 150,
}


class Player:
    """Represents a single TFT player's state."""

    def __init__(self, player_id: int):
        self.player_id = player_id
        self._next_instance_id: int = 0

        # Resources
        self.gold = STARTING_GOLD
        self.hp = STARTING_HP
        self.level = STARTING_LEVEL
        self.xp = 0

        # Board: dict mapping (row, col) → ChampionInstance
        self.board: Dict[Tuple[int, int], ChampionInstance] = {}
        self._empty_positions: set[Tuple[int, int]] = {
            (row, col)
            for row in range(BOARD_ROWS)
            for col in range(BOARD_COLS)
        }
        self._traits_cache: Optional[Dict[str, int]] = None
        # Bench: list of BENCH_SIZE slots (None = empty)
        self.bench: List[Optional[ChampionInstance]] = [None] * BENCH_SIZE
        # Item bench: list of item names
        self.item_bench: List[str] = []
        # Current shop: list of champion names (or None for empty slots)
        self.shop: List[Optional[str]] = [None] * 5

        # Placeable structures (set during planning phase)
        # Freljord Tower: position on board where ice tower is placed
        self.tower_position: Optional[Tuple[int, int]] = None
        # Azir Soldiers: up to 2 positions where soldiers are placed
        self.soldier_positions: List[Tuple[int, int]] = []

        # Streaks
        self.win_streak = 0
        self.loss_streak = 0

        # Game state
        self.alive = True
        self.placement = 0  # Set when eliminated (1 = winner, 8 = first out)
        self.elimination_hp = 0  # Raw HP after lethal damage (can be negative)

        # Tracking for upgrades: name → list of (location, ChampionInstance)
        # location is ('board', (row, col)) or ('bench', idx)
        self._upgrade_tracker: Dict[str, int] = {}

        # Cached max_units value (invalidated on level/item changes)
        self._max_units_cache: Optional[int] = None

        # Round-persistent trait currencies (stored at the game layer)
        self.bilgewater_serpents: int = 0
        self.bilgewater_purchases: Dict[str, int] = {}
        self.blacksmith_progress: Dict[str, int] = {}  # instance_id -> rounds progressed
        self.blacksmith_artifacts: Dict[str, List[str]] = {}  # instance_id -> crafted artifacts
        self.augment_permanent_bonuses: Dict[str, Dict[str, float]] = {}  # instance_id -> bonus_name -> value

    def _alloc_instance_id(self) -> str:
        iid = f"p{self.player_id}_u{self._next_instance_id}"
        self._next_instance_id += 1
        return iid

    def add_bilgewater_serpents(self, amount: int) -> None:
        if amount <= 0:
            return
        self.bilgewater_serpents += amount

    def get_augment_permanent_bonus(self, instance_id: str, bonus_name: str, default: float = 0.0) -> float:
        bonuses = self.augment_permanent_bonuses.get(instance_id)
        if bonuses is None:
            return default
        return float(bonuses.get(bonus_name, default))

    def set_augment_permanent_bonus(self, instance_id: str, bonus_name: str, value: float) -> None:
        bonuses = self.augment_permanent_bonuses.setdefault(instance_id, {})
        bonuses[bonus_name] = float(value)

    def _augment_bonus_stat_map(self, engine: Any) -> Dict[str, str]:
        augment_manager = getattr(engine, 'augment_manager', None)
        effect_map = getattr(augment_manager, 'PERSISTENT_EFFECT_STAT_MAP', {})
        bonus_map: Dict[str, str] = {}
        if not isinstance(effect_map, dict):
            return bonus_map

        for value in effect_map.values():
            if not isinstance(value, (list, tuple)) or len(value) != 2:
                continue
            bonus_map[str(value[0])] = str(value[1])
        return bonus_map

    def _apply_persistent_augment_bonuses(
        self,
        unit: Any,
        bonus_stat_map: Dict[str, str],
    ) -> None:
        if not unit.instance_id:
            return
        bonuses = self.augment_permanent_bonuses.get(unit.instance_id)
        if not bonuses:
            return

        for bonus_name, bonus_value in bonuses.items():
            stat_name = bonus_stat_map.get(bonus_name)
            if stat_name is None:
                continue
            current = getattr(unit.stats, stat_name, None)
            if current is None:
                continue
            setattr(unit.stats, stat_name, float(current) + float(bonus_value))

    def award_bilgewater_round_serpents(self) -> int:
        traits = self.get_active_traits()
        count = int(traits.get('bilgewater', 0) or 0)
        if count < 3:
            return 0

        reward = 0
        for tier in sorted(_BILGEWATER_SERPENTS_PER_ROUND.keys(), reverse=True):
            if count >= tier:
                reward = _BILGEWATER_SERPENTS_PER_ROUND[tier]
                break

        self.add_bilgewater_serpents(reward)
        return reward

    def progress_blacksmith(self) -> List[str]:
        """Advance Blacksmith crafting for any on-board Blacksmith unit(s).

        Returns the list of crafted artifact item names added to the item bench.
        """
        if not ARTIFACT_ITEMS:
            return []

        rounds_to_craft = int(BLACKSMITH_CONFIG.get('rounds_to_craft', 4) or 4)
        if rounds_to_craft <= 0:
            rounds_to_craft = 4

        crafted: List[str] = []
        for champ in self.board.values():
            traits = CHAMPION_TRAITS.get(champ.name, [])
            if 'blacksmith' not in traits:
                continue

            iid = champ.instance_id
            progress = self.blacksmith_progress.get(iid, 0) + 1
            if progress >= rounds_to_craft:
                progress = 0
                artifact_key = random.choice(list(ARTIFACT_ITEMS.keys()))
                artifact_item = f"Artifact_{artifact_key}"
                if self.add_item_to_bench(artifact_item):
                    crafted.append(artifact_item)
                self.blacksmith_artifacts.setdefault(iid, []).append(artifact_item)
            self.blacksmith_progress[iid] = progress
        return crafted

    def invalidate_max_units(self):
        """Call when level changes or Tactician items are added/removed."""
        self._max_units_cache = None

    @property
    def max_units(self) -> int:
        """Maximum units allowed on board (level + Tactician items)."""
        if self._max_units_cache is not None:
            return self._max_units_cache
        bonus = 0
        # Tactician's Crown/Cape/Shield each grant +1 team size
        tactician_items = {'TacticiansCrown', 'TacticiansCape', 'TacticiansShield'}
        for item in self.item_bench:
            if item in tactician_items:
                bonus += 1
        # Also check items equipped on board/bench units
        for row_col, champ in self.board.items():
            for item in champ.items:
                if item in tactician_items:
                    bonus += 1
        for champ in self.bench:
            if champ:
                for item in champ.items:
                    if item in tactician_items:
                        bonus += 1
        self._max_units_cache = self.level + bonus
        return self._max_units_cache

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
        old_level = self.level
        while self.level < MAX_LEVEL:
            required = LEVEL_XP_REQUIRED[self.level]
            if self.xp >= required:
                self.xp -= required
                self.level += 1
            else:
                break
        if self.level != old_level:
            self.invalidate_max_units()

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
            instance_id=self._alloc_instance_id(),
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
        champ = self._board_remove(pos)
        if champ is None:
            return False
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
        self.augment_permanent_bonuses.pop(champ.instance_id, None)
        # Return items to item bench
        self.item_bench.extend(champ.items)
        self.invalidate_max_units()

    # ── Item Management ──────────────────────────────────────────────────

    def add_item_to_bench(self, item_name: str) -> bool:
        """Add an item component to the item bench. Returns True if successful."""
        if len(self.item_bench) >= ITEM_BENCH_SIZE:
            return False
        self.item_bench.append(item_name)
        self.invalidate_max_units()
        return True

    def equip_item(self, item_bench_idx: int, target_pos: Tuple[int, int]) -> bool:
        """Equip an item from item bench onto a board champion.

        If the champion already has a component and we're equipping another component,
        they auto-combine into a completed item. If the champion already has 3 items
        (completed), the equip fails.

        Args:
            item_bench_idx: Index into self.item_bench.
            target_pos: (row, col) of the target board champion.

        Returns:
            True if the item was successfully equipped.
        """
        if item_bench_idx < 0 or item_bench_idx >= len(self.item_bench):
            return False
        item = self.item_bench[item_bench_idx]

        champ = self.board.get(target_pos)
        if champ is None:
            return False

        if len(champ.items) >= MAX_ITEMS_PER_UNIT:
            return False

        # Try to combine with an existing component on the champion
        if is_component(item):
            for i, existing in enumerate(champ.items):
                if is_component(existing):
                    combined = combine_items(existing, item)
                    if combined is not None:
                        # Replace the component with the completed item
                        champ.items[i] = combined
                        self.item_bench.pop(item_bench_idx)
                        return True

        # No combination possible — just add the item directly
        champ.items.append(item)
        self.item_bench.pop(item_bench_idx)
        self.invalidate_max_units()
        return True

    def equip_item_bench(self, item_bench_idx: int, bench_idx: int) -> bool:
        """Equip an item from item bench onto a bench champion.

        Same combining logic as equip_item but for bench units.
        """
        if item_bench_idx < 0 or item_bench_idx >= len(self.item_bench):
            return False
        item = self.item_bench[item_bench_idx]

        champ = self.bench[bench_idx] if 0 <= bench_idx < BENCH_SIZE else None
        if champ is None:
            return False

        if len(champ.items) >= MAX_ITEMS_PER_UNIT:
            return False

        # Try to combine with an existing component on the champion
        if is_component(item):
            for i, existing in enumerate(champ.items):
                if is_component(existing):
                    combined = combine_items(existing, item)
                    if combined is not None:
                        champ.items[i] = combined
                        self.item_bench.pop(item_bench_idx)
                        return True

        # No combination — just add
        champ.items.append(item)
        self.item_bench.pop(item_bench_idx)
        return True

    # ── Board Management ──────────────────────────────────────────────────

    def _board_add(self, pos: Tuple[int, int], champ: ChampionInstance) -> None:
        self.board[pos] = champ
        self._empty_positions.discard(pos)
        self._traits_cache = None

    def _board_remove(self, pos: Tuple[int, int]) -> Optional[ChampionInstance]:
        champ = self.board.pop(pos, None)
        if champ is not None:
            self._empty_positions.add(pos)
            self._traits_cache = None
        return champ

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
            self._traits_cache = None
            return True

        # Check board capacity
        if self.board_count >= self.max_units:
            return False

        self.bench[bench_idx] = None
        self._board_add(pos, champ)
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

        removed = self._board_remove(pos)
        if removed is None:
            return False
        self.bench[bench_idx] = removed
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
            self._board_remove(from_pos)
            self._board_add(to_pos, champ)
        return True

    def _valid_board_pos(self, pos: Tuple[int, int]) -> bool:
        row, col = pos
        return 0 <= row < BOARD_ROWS and 0 <= col < BOARD_COLS

    # ── Upgrades ──────────────────────────────────────────────────────────

    def _check_upgrade(self, name: str, pool: 'ChampionPool'):
        """Check if buying this champion triggers an upgrade (3 → star up).

        Checks for 1→2 star, then immediately checks for 2→3 star.
        """
        star1_copies = []
        star2_copies = []

        for pos, champ in self.board.items():
            if champ.name != name:
                continue
            if champ.star_level == 1:
                star1_copies.append(('board', pos))
            elif champ.star_level == 2:
                star2_copies.append(('board', pos))

        for idx, champ in enumerate(self.bench):
            if champ is None or champ.name != name:
                continue
            if champ.star_level == 1:
                star1_copies.append(('bench', idx))
            elif champ.star_level == 2:
                star2_copies.append(('bench', idx))

        upgraded_to_two = False
        if len(star1_copies) >= 3:
            self._do_upgrade(name, 1, star1_copies)
            upgraded_to_two = True

        if len(star2_copies) >= 3:
            self._do_upgrade(name, 2, star2_copies)
            return

        if upgraded_to_two:
            copies_after_upgrade = self._find_copies(name, 2)
            if len(copies_after_upgrade) >= 3:
                self._do_upgrade(name, 2, copies_after_upgrade)

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
        merged_instance_ids = []
        for loc_type, loc_key in copies:
            if loc_type == 'board':
                champ = self.board[loc_key]
            else:
                champ = self.bench[loc_key]
            if champ is None:
                continue
            all_items.extend(champ.items)
            merged_instance_ids.append(champ.instance_id)

        # Remove all 3 copies
        first_loc = None
        upgrade_instance_id = ''
        for loc_type, loc_key in copies:
            if first_loc is None:
                first_loc = (loc_type, loc_key)
                if loc_type == 'board':
                    upgrade_instance_id = self.board[loc_key].instance_id
                else:
                    champ = self.bench[loc_key]
                    upgrade_instance_id = champ.instance_id if champ is not None else ''
            if loc_type == 'board':
                self._board_remove(loc_key)
            else:
                self.bench[loc_key] = None

        # Create upgraded champion
        upgraded = ChampionInstance(
            instance_id=upgrade_instance_id or self._alloc_instance_id(),
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
            self._board_add(loc_key, upgraded)
        else:
            self.bench[loc_key] = upgraded

        merged_bonus_values: Dict[str, float] = {}
        for instance_id in merged_instance_ids:
            bonuses = self.augment_permanent_bonuses.pop(instance_id, None)
            if bonuses is None:
                continue
            for bonus_name, bonus_value in bonuses.items():
                value = float(bonus_value)
                existing = merged_bonus_values.get(bonus_name)
                if existing is None or value > existing:
                    merged_bonus_values[bonus_name] = value
        if merged_bonus_values:
            self.augment_permanent_bonuses[upgraded.instance_id] = merged_bonus_values

    # ── Traits ────────────────────────────────────────────────────────────

    def get_active_traits(self) -> Dict[str, int]:
        """Compute active traits from board units.

        Returns dict of trait_name → unit count.
        """
        if self._traits_cache is not None:
            return self._traits_cache

        trait_counts: Dict[str, int] = {}
        for champ in self.board.values():
            traits = CHAMPION_TRAITS.get(champ.name, [])
            for trait in traits:
                trait_counts[trait] = trait_counts.get(trait, 0) + 1
        self._traits_cache = trait_counts
        return self._traits_cache

    # ── Placeable Structures ─────────────────────────────────────────────

    def place_tower(self, row: int, col: int) -> bool:
        """Place the Freljord tower at a board position.

        The tower is a separate structure (not a unit) that provides
        area buffs. Requires Freljord 3+ to be active.
        """
        if not (0 <= row < BOARD_ROWS and 0 <= col < BOARD_COLS):
            return False
        # Tower can be placed on any hex (even occupied - it's a structure)
        self.tower_position = (row, col)
        return True

    def place_soldier(self, row: int, col: int) -> bool:
        """Place an Azir soldier at a board position.

        Requires Azir on the board. Max 2 soldiers.
        Soldiers can be placed on any empty hex on your side.
        """
        if not (0 <= row < BOARD_ROWS and 0 <= col < BOARD_COLS):
            return False
        if len(self.soldier_positions) >= 2:
            return False
        # Don't place on top of another soldier
        if (row, col) in self.soldier_positions:
            return False
        self.soldier_positions.append((row, col))
        return True

    def has_azir_on_board(self) -> bool:
        """Check if Azir is on the board."""
        for champ in self.board.values():
            if champ.name == 'azir':
                return True
        return False

    def has_freljord_active(self) -> bool:
        """Check if Freljord 3+ is active (needed for tower)."""
        traits = self.get_active_traits()
        return traits.get('freljord', 0) >= 3

    # ── Combat Bridge ─────────────────────────────────────────────────────

    def build_combat_team(self, engine: Any, use_rust_engine: bool = False) -> list:
        """Convert board state into combat Unit objects.

        Also spawns Freljord tower and Azir soldiers at their placed positions.

        Args:
            engine: The CombatEngine instance to create units with.
            use_rust_engine: Return Rust unit spec dicts instead of Python Unit objects.

        Returns:
            List of Unit objects or Rust unit specs ready for run_combat().
        """
        units = []
        bonus_stat_map = self._augment_bonus_stat_map(engine)
        for pos, champ in self.board.items():
            items = list(champ.items) if champ.items else None

            # Thief's Gloves: replace with 2 random items based on player level
            if items and any(i in ('ThiefsGloves', 'TFT_Item_ThiefsGloves') for i in items):
                items = self._roll_thiefs_gloves_items()

            if use_rust_engine:
                units.append({
                    'api_name': champ.api_name,
                    'star_level': champ.star_level,
                    'position': [pos[0], pos[1]],
                    'team': 0,
                    'items': items or [],
                    'traits': [],
                })
            else:
                unit = engine.create_unit(
                    api_name=champ.api_name,
                    star_level=champ.star_level,
                    position=pos,
                    team=0,
                    items=items,
                    instance_id=champ.instance_id,
                )
                if unit is not None:
                    self._apply_persistent_augment_bonuses(unit, bonus_stat_map)
                    units.append(unit)

        # Spawn Azir soldiers at player-placed positions
        if self.has_azir_on_board() and self.soldier_positions:
            # Get Azir's star level for soldier scaling
            azir_star = 1
            for champ in self.board.values():
                if champ.name == 'azir':
                    azir_star = champ.star_level
                    break
            for pos in self.soldier_positions:
                if use_rust_engine:
                    units.append({
                        'api_name': 'TFT16_AzirSoldier',
                        'star_level': azir_star,
                        'position': [pos[0], pos[1]],
                        'team': 0,
                        'items': [],
                        'traits': [],
                    })
                else:
                    soldier = engine.create_unit(
                        'TFT16_AzirSoldier', azir_star, pos, 0
                    )
                    if soldier:
                        soldier._is_summon = True
                        soldier._summoner = 'Azir'
                        units.append(soldier)

        # Spawn Freljord tower at player-placed position
        if self.tower_position and self.has_freljord_active():
            if use_rust_engine:
                units.append({
                    'api_name': 'TFT16_FreljordProp',
                    'star_level': 1,
                    'position': [self.tower_position[0], self.tower_position[1]],
                    'team': 0,
                    'items': [],
                    'traits': [],
                })
            else:
                tower = engine.create_unit(
                    'TFT16_FreljordProp', 1, self.tower_position, 0
                )
                if tower:
                    tower._is_tower = True
                    units.append(tower)

        return units

    # Thief's Gloves tier odds by player level
    _THIEFS_GLOVES_TIERS = {
        1: [1.0, 0.0, 0.0, 0.0],
        2: [1.0, 0.0, 0.0, 0.0],
        3: [1.0, 0.0, 0.0, 0.0],
        4: [0.80, 0.20, 0.0, 0.0],
        5: [0.60, 0.30, 0.10, 0.0],
        6: [0.40, 0.40, 0.20, 0.0],
        7: [0.20, 0.40, 0.30, 0.10],
        8: [0.10, 0.30, 0.40, 0.20],
        9: [0.0, 0.20, 0.40, 0.40],
    }

    def _roll_thiefs_gloves_items(self) -> list:
        """Roll 2 random completed items for Thief's Gloves based on player level."""
        if not _THIEFS_POOL:
            return []
        return [random.choice(_THIEFS_POOL), random.choice(_THIEFS_POOL)]

    # ── HP / Elimination ──────────────────────────────────────────────────

    def take_damage(self, amount: int):
        """Take HP damage. Player is eliminated when HP reaches 0."""
        raw_hp = self.hp - amount
        if raw_hp <= 0:
            self.elimination_hp = raw_hp
            self.hp = 0
            self.alive = False
            return
        self.elimination_hp = 0
        self.hp = raw_hp

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
            if not self._empty_positions:
                break
            target_pos = min(self._empty_positions)
            self._board_add(target_pos, champ)
            self.bench[idx] = None

    def __repr__(self):
        return (f"Player({self.player_id}, lvl={self.level}, "
                f"hp={self.hp}, gold={self.gold}, "
                f"board={self.board_count}/{self.max_units})")
