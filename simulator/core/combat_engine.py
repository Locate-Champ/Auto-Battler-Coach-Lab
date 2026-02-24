"""
TFT Combat Simulator Engine v2

Core combat simulation for TFT Set 16 with:
- Physical/Magic damage with armor/MR reduction
- Critical strikes (25% base chance, 140% multiplier)
- Star level scaling (1.8x HP, 1.5x AD for 2-star)
- Attack speed and mana generation
- Ability casting with targeting
- Hex-based movement and pathfinding
- Item effects system
"""

import heapq
import json
import random
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .augment_paths import resolve_augment_data_path

# Import champion ability handlers
try:
    from .champion_abilities import ChampionAbilities

    _ABILITIES_LOADED = True
except ImportError:
    _ABILITIES_LOADED = False
    ChampionAbilities = None

# Optionally accelerate damage math with Cython (built separately)
try:
    from .combat_fast import (
        CYTHON_AVAILABLE as _CYTHON_OK,
    )
    from .combat_fast import (
        calculate_damage_fast as _cy_calculate_damage,
    )
except ImportError:
    _cy_calculate_damage = None
    _CYTHON_OK = False

# Cache item effect lookups at module level (avoids per-item import overhead)
try:
    from .item_effects import get_item_on_ability as _get_item_on_ability
    from .item_effects import get_item_on_damage_dealt as _get_item_on_damage_dealt
    from .item_effects import get_item_on_damage_taken as _get_item_on_damage_taken
    from .item_effects import get_item_on_hit as _get_item_on_hit
    from .item_effects import get_item_passive as _get_item_passive

    _ITEM_EFFECTS_LOADED = True
except ImportError:
    _ITEM_EFFECTS_LOADED = False
    _get_item_on_hit = None
    _get_item_on_ability = None
    _get_item_on_damage_dealt = None
    _get_item_on_damage_taken = None
    _get_item_passive = None

# Module-level cache for combat data (loaded once, shared across all CombatEngine instances)
_COMBAT_DATA_CACHE: Dict[str, Any] = {}


def _load_combat_data(path: Path) -> dict:
    """Load combat data from JSON, using module-level cache."""
    key = str(path)
    if key not in _COMBAT_DATA_CACHE:
        with open(path, "r", encoding="utf-8") as f:
            _COMBAT_DATA_CACHE[key] = json.load(f)
    return _COMBAT_DATA_CACHE[key]


def _star_val(var_data, star_level: int, default=0):
    """Extract star-level value from ability variable data.

    Handles both list format [0, 1star, 2star, 3star, ...] and
    dict format {'1star': val, '2star': val, ...}.
    """
    if var_data is None:
        return default
    if isinstance(var_data, list):
        if star_level < len(var_data):
            return var_data[star_level] if var_data[star_level] else default
        return default
    if isinstance(var_data, dict):
        return var_data.get(f"{star_level}star", default) or default
    # Scalar
    return var_data if var_data else default


# =============================================================================
# ENUMS
# =============================================================================


class DamageType(Enum):
    PHYSICAL = "physical"
    MAGIC = "magic"
    TRUE = "true"


class TargetingType(Enum):
    NEAREST = "nearest"
    LOWEST_HP = "lowest_hp"
    LOWEST_HP_PERCENT = "lowest_hp_percent"
    HIGHEST_HP = "highest_hp"
    FARTHEST = "farthest"
    RANDOM = "random"
    CURRENT_TARGET = "current_target"
    MOST_ENEMIES_IN_RANGE = "most_enemies_in_range"


class AbilityType(Enum):
    DAMAGE = "damage"  # Single target damage
    AOE_DAMAGE = "aoe_damage"  # Area damage
    BUFF = "buff"  # Self/ally buff
    DEBUFF = "debuff"  # Enemy debuff
    SUMMON = "summon"  # Summon unit
    DASH = "dash"  # Movement ability
    HEAL = "heal"  # Healing
    SHIELD = "shield"  # Shield


class UnitState(Enum):
    IDLE = "idle"
    MOVING = "moving"
    ATTACKING = "attacking"
    CASTING = "casting"
    STUNNED = "stunned"
    FEARED = "feared"  # Forced random movement away from source
    TAUNTED = "taunted"  # Forced to attack taunter
    ROOTED = "rooted"  # Cannot move but can attack/cast
    DEAD = "dead"
    UNTARGETABLE = "untargetable"  # Cannot be targeted (Fizz, Zhonya's, Edge of Night)


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass(slots=True)
class CombatStats:
    """Combat-ready stats for a unit."""

    hp: float
    max_hp: float
    ad: float
    ap: float = 0.0
    attack_speed: float = 0.7
    armor: float = 20.0
    magic_resist: float = 20.0
    range: int = 1
    mana: float = 0.0
    max_mana: float = 100.0
    crit_chance: float = 0.25
    crit_multiplier: float = 1.4
    damage_amp: float = 0.0  # Bonus damage multiplier (additive)
    damage_reduction: float = 0.0  # Durability (% damage reduction)
    omnivamp: float = 0.0  # Heal for % of damage dealt
    shield: float = 0.0  # Current shield amount
    move_speed: float = 550.0  # Movement speed (units per second)
    mana_regen: float = 0.0  # Bonus mana per attack (Invoker trait)

    def copy(self) -> "CombatStats":
        """Fast manual copy (10-20x faster than deepcopy for this class)."""
        return CombatStats(
            hp=self.hp,
            max_hp=self.max_hp,
            ad=self.ad,
            ap=self.ap,
            attack_speed=self.attack_speed,
            armor=self.armor,
            magic_resist=self.magic_resist,
            range=self.range,
            mana=self.mana,
            max_mana=self.max_mana,
            crit_chance=self.crit_chance,
            crit_multiplier=self.crit_multiplier,
            damage_amp=self.damage_amp,
            damage_reduction=self.damage_reduction,
            omnivamp=self.omnivamp,
            shield=self.shield,
            move_speed=self.move_speed,
            mana_regen=self.mana_regen,
        )


@dataclass
class Ability:
    """Champion ability definition."""

    name: str
    ability_type: AbilityType
    damage_type: DamageType = DamageType.MAGIC
    targeting: TargetingType = TargetingType.CURRENT_TARGET
    base_damage: Dict[int, float] = field(default_factory=dict)  # {star: damage}
    ap_scaling: float = 1.0  # AP ratio
    ad_scaling: float = 0.0  # AD ratio
    cast_time: float = 0.5  # Seconds to cast
    aoe_radius: int = 0  # Hexes for AOE
    num_targets: int = 1  # Number of targets hit
    effects: Dict[str, Any] = field(default_factory=dict)  # Special effects


@dataclass
class Item:
    """Item definition with stats and effects."""

    name: str
    stats: Dict[str, float] = field(default_factory=dict)
    on_hit: Optional[Callable] = None
    on_attack: Optional[Callable] = None
    on_damage_dealt: Optional[Callable] = None
    on_damage_taken: Optional[Callable] = None
    on_ability_cast: Optional[Callable] = None
    passive: Optional[Callable] = None


@dataclass
class Buff:
    """Temporary buff/debuff on a unit."""

    name: str
    duration: float
    stat_modifiers: Dict[str, float] = field(default_factory=dict)
    stacks: int = 1
    max_stacks: int = 1


@dataclass
class DotEffect:
    """Damage-over-time effect on a unit (burn, bleed, etc.)."""

    source_unit: Optional["Unit"]  # Who applied this DOT
    damage_per_tick: float  # Damage each tick
    tick_interval: float  # Seconds between ticks
    remaining_duration: float  # Seconds left
    damage_type: "DamageType" = DamageType.TRUE
    source_name: str = "burn"  # For logging
    time_since_last_tick: float = 0.0


@dataclass
class Unit:
    """A unit in combat."""

    name: str
    api_name: str
    star_level: int
    stats: CombatStats
    base_stats: CombatStats  # Original stats without items/buffs
    position: Tuple[int, int]  # (row, col) on hex grid
    team: int  # 0 or 1
    instance_id: str = ""  # Stable game-layer id (ChampionInstance.instance_id) when available
    items: List[Item] = field(default_factory=list)
    traits: List[str] = field(default_factory=list)
    ability: Optional[Ability] = None
    role: str = ""  # Champion role: ADCarry, APCaster, APTank, ADFighter, etc.

    # Combat state
    state: UnitState = UnitState.IDLE
    target: Optional["Unit"] = None
    attack_cooldown: float = 0.0
    cast_progress: float = 0.0
    stun_duration: float = 0.0
    is_alive: bool = True
    buffs: List[Buff] = field(default_factory=list)
    dot_effects: List[DotEffect] = field(default_factory=list)

    # Movement
    move_target: Optional[Tuple[int, int]] = None
    path: List[Tuple[int, int]] = field(default_factory=list)

    # Untargetable state (Fizz, Zhonya's, Edge of Night)
    is_targetable: bool = True
    untargetable_duration: float = 0.0
    untargetable_return_pos: Optional[Tuple[int, int]] = None  # For abilities that teleport back

    # Basic attack immunity (Huntress trait - Nidalee protected by Neeko)
    is_basic_attack_immune: bool = False

    # Enhanced attack tracking (Fizz gets buffed attacks after ability)
    enhanced_attacks_remaining: int = 0
    enhanced_attack_bonus_as: float = 0.0  # Attack speed bonus
    enhanced_attack_on_hit_dmg: float = 0.0  # On-hit magic damage

    # Stats tracking
    total_damage_dealt: float = 0.0
    total_damage_taken: float = 0.0
    total_healing: float = 0.0
    abilities_cast: int = 0
    attacks_performed: int = 0  # Track attacks for form-swap abilities like Jinx

    # Timing
    attack_windup: float = 0.3
    missile_speed: Optional[int] = None

    # Cached item flags (set once at unit creation, avoids repeated item list scans)
    _has_jeweled_gauntlet: bool = False
    _has_giant_slayer: bool = False
    _has_ionic_spark: bool = False

    def __hash__(self):
        return hash((self.api_name, id(self)))

    def __eq__(self, other):
        return id(self) == id(other)

    @property
    def is_frontline(self) -> bool:
        """Check if unit is a frontline/tank type."""
        return "Tank" in self.role or "Fighter" in self.role

    @property
    def is_backline(self) -> bool:
        """Check if unit is a backline carry type."""
        return "Carry" in self.role or "Caster" in self.role or "Specialist" in self.role


# =============================================================================
# HEX GRID UTILITIES
# =============================================================================


class HexGrid:
    """Hex grid utilities for TFT board (4 rows x 7 cols).

    Performance: Uses precomputed lookup tables for distance and neighbors
    to avoid repeated cube-coordinate conversions in the hot path.
    """

    ROWS = 4
    COLS = 7

    # Hex directions for odd-q offset coordinates
    DIRECTIONS_EVEN = [(0, -1), (1, -1), (1, 0), (0, 1), (-1, 0), (-1, -1)]
    DIRECTIONS_ODD = [(0, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0)]

    # --- Precomputed lookup tables (built once at module load) ---

    # _DISTANCE_LUT[(r1,c1)][(r2,c2)] = hex distance
    _DISTANCE_LUT: Dict[Tuple[int, int], Dict[Tuple[int, int], int]] = {}

    # _NEIGHBOR_LUT[(r,c)] = list of valid neighbor positions
    _NEIGHBOR_LUT: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}

    # _HEXES_IN_RANGE_LUT[(r,c)][radius] = list of hexes within radius
    _HEXES_IN_RANGE_LUT: Dict[Tuple[int, int], Dict[int, List[Tuple[int, int]]]] = {}

    @classmethod
    def _build_luts(cls):
        """Build all lookup tables once. Called at module load."""
        if cls._DISTANCE_LUT:
            return  # Already built

        all_hexes = [(r, c) for r in range(cls.ROWS) for c in range(cls.COLS)]

        # Build neighbor LUT
        for pos in all_hexes:
            row, col = pos
            directions = cls.DIRECTIONS_ODD if col % 2 == 1 else cls.DIRECTIONS_EVEN
            neighbors = []
            for dr, dc in directions:
                new_row, new_col = row + dr, col + dc
                if 0 <= new_row < cls.ROWS and 0 <= new_col < cls.COLS:
                    neighbors.append((new_row, new_col))
            cls._NEIGHBOR_LUT[pos] = neighbors

        # Build distance LUT using cube-coordinate conversion
        for pos1 in all_hexes:
            cls._DISTANCE_LUT[pos1] = {}
            r1, c1 = pos1
            x1 = c1
            z1 = r1 - (c1 - (c1 & 1)) // 2
            y1 = -x1 - z1
            for pos2 in all_hexes:
                r2, c2 = pos2
                x2 = c2
                z2 = r2 - (c2 - (c2 & 1)) // 2
                y2 = -x2 - z2
                cls._DISTANCE_LUT[pos1][pos2] = (abs(x1 - x2) + abs(y1 - y2) + abs(z1 - z2)) // 2

        # Build hexes-in-range LUT for common radii (0-6 covers entire board)
        for pos in all_hexes:
            cls._HEXES_IN_RANGE_LUT[pos] = {}
            for radius in range(7):
                cls._HEXES_IN_RANGE_LUT[pos][radius] = [
                    p for p in all_hexes if cls._DISTANCE_LUT[pos][p] <= radius
                ]

    @staticmethod
    def get_neighbors(pos: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Get all valid neighboring hexes (from precomputed LUT)."""
        return HexGrid._NEIGHBOR_LUT[pos]

    @staticmethod
    def hex_distance(pos1: Tuple[int, int], pos2: Tuple[int, int]) -> int:
        """Calculate distance between two hexes (from precomputed LUT)."""
        return HexGrid._DISTANCE_LUT[pos1][pos2]

    @staticmethod
    def find_path(
        start: Tuple[int, int], goal: Tuple[int, int], occupied: set
    ) -> List[Tuple[int, int]]:
        """A* pathfinding on hex grid."""
        if start == goal:
            return []

        dist_lut = HexGrid._DISTANCE_LUT
        open_set = [(0, start)]
        came_from = {}
        g_score = {start: 0}
        f_score = {start: dist_lut[start][goal]}

        while open_set:
            _, current = heapq.heappop(open_set)

            if current == goal:
                # Reconstruct path
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                return path[::-1]

            for neighbor in HexGrid._NEIGHBOR_LUT[current]:
                if neighbor in occupied and neighbor != goal:
                    continue

                tentative_g = g_score[current] + 1

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + dist_lut[neighbor][goal]
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))

        return []  # No path found

    @staticmethod
    def find_best_step(
        start: Tuple[int, int], goal: Tuple[int, int], occupied: set
    ) -> Optional[Tuple[int, int]]:
        """Find the single best next step toward goal, avoiding occupied hexes.

        Greedy neighbor selection — much cheaper than full A* for the common
        case where the path is short and unobstructed. Falls back to A* only
        when all neighbors are blocked.
        """
        dist_lut = HexGrid._DISTANCE_LUT
        best_pos = None
        best_dist = dist_lut[start][goal]

        for neighbor in HexGrid._NEIGHBOR_LUT[start]:
            if neighbor in occupied and neighbor != goal:
                continue
            d = dist_lut[neighbor][goal]
            if d < best_dist:
                best_dist = d
                best_pos = neighbor

        if best_pos is not None:
            return best_pos

        # All direct neighbors blocked — fall back to A*
        path = HexGrid.find_path(start, goal, occupied)
        return path[0] if path else None

    @staticmethod
    def get_hexes_in_range(center: Tuple[int, int], radius: int) -> List[Tuple[int, int]]:
        """Get all hexes within radius of center (from precomputed LUT)."""
        lut = HexGrid._HEXES_IN_RANGE_LUT.get(center)
        if lut and radius in lut:
            return lut[radius]
        # Fallback for out-of-range radius
        return [
            (r, c)
            for r in range(HexGrid.ROWS)
            for c in range(HexGrid.COLS)
            if HexGrid._DISTANCE_LUT[center][(r, c)] <= radius
        ]


# Build lookup tables at module load time
HexGrid._build_luts()


# =============================================================================
# TRAIT MANAGER - Handle Trait Mechanics
# =============================================================================


@dataclass(slots=True)
class TeamTraitState:
    bilgewater_count: int = 0
    shadow_isles_count: int = 0
    shadow_isles_souls: int = 0


class TraitManager:
    """Manages trait effects and mechanics.

    Key traits with special mechanics:
    - Piltover: T-Hex modules at 2/4/6 trait count
    - Shadow Isles: Soul collection from enemy deaths
    """

    BILGEWATER_SERPENTS_PER_TAKEDOWN = 1  # Patch 16.3: nerfed from 2 to 1

    # Shadow Isles soul multipliers by trait count
    SHADOW_ISLES_SOUL_MULTIPLIER = {
        2: 1.0,
        3: 1.3,
        4: 1.6,
        5: 1.9,
    }

    # Shadow Isles AD/AP bonus by trait count
    SHADOW_ISLES_STAT_BONUS = {
        2: 0.18,  # 18% AD/AP
        3: 0.20,  # 20% AD/AP
        4: 0.25,  # 25% AD/AP
        5: 0.33,  # 33% AD/AP
    }

    def __init__(self):
        self.team_state: Dict[int, TeamTraitState] = {}
        self.piltover_modules: List[str] = []

    def get_team_state(self, team_id: int) -> TeamTraitState:
        """Get (and create if needed) per-team trait state."""
        state = self.team_state.get(team_id)
        if state is None:
            state = TeamTraitState()
            self.team_state[team_id] = state
        return state

    def set_bilgewater_count(self, team_id: int, count: int):
        """Set the current Bilgewater trait count for a team."""
        state = self.get_team_state(team_id)
        state.bilgewater_count = count

    def assign_piltover_modules(self, piltover_count: int) -> List[str]:
        """Assign Piltover modules based on trait count.

        Args:
            piltover_count: Number of Piltover champions active

        Returns:
            List of module names that can be used
        """
        if not _ITEMS_LOADED:
            return []

        available_modules = []

        # Tier 1: 2 Piltover
        if piltover_count >= 2:
            tier1_modules = [
                "AccelerationGate",
                "BlastShield",
                "ContinuumCogs",
                "EMP",
                "KineticBarrier",
                "OverclockedCapacitors",
            ]
            available_modules.extend(tier1_modules)

        # Tier 2: 4 Piltover
        if piltover_count >= 4:
            tier2_modules = [
                "ArmorNullifier",
                "GigantificationRay",
                "MagnetronCoil",
                "MomentumDrive",
                "TunedOscillator",
                "ElectricalOverload",
            ]
            available_modules.extend(tier2_modules)

        # Tier 3: 6 Piltover
        if piltover_count >= 6:
            tier3_modules = [
                "MicroRockets",
                "MiningDrill",
                "90CaliberNets",
                "SuperiorLifeform",
                "UnstableCurrent",
            ]
            available_modules.extend(tier3_modules)

        return available_modules

    # =========================================================================
    # SHADOW ISLES SOUL COLLECTION
    # =========================================================================

    def set_shadow_isles_count(self, team_id: int, count: int):
        """Set the current Shadow Isles trait count for a team."""
        state = self.get_team_state(team_id)
        state.shadow_isles_count = count

    def award_soul(self, team_id: int, victim_cost: int = 1, victim_star: int = 1) -> int:
        """Award souls when an enemy dies.

        Soul value is based on victim's cost and star level.
        Higher cost/star units are worth more souls.

        Args:
            team_id: Team to award souls to
            victim_cost: Champion cost (1-5)
            victim_star: Star level (1-3)

        Returns:
            Number of souls awarded
        """
        state = self.get_team_state(team_id)
        if state.shadow_isles_count < 2:
            return 0

        # Base souls by cost
        cost_souls = {1: 1, 2: 2, 3: 3, 4: 5, 5: 8}
        base_souls = cost_souls.get(victim_cost, 1)

        # Star level multiplier
        star_mult = {1: 1.0, 2: 1.5, 3: 2.0}
        souls = int(base_souls * star_mult.get(victim_star, 1.0))

        # Apply trait count multiplier
        soul_mult = 1.0
        for tier in sorted(self.SHADOW_ISLES_SOUL_MULTIPLIER.keys(), reverse=True):
            if state.shadow_isles_count >= tier:
                soul_mult = self.SHADOW_ISLES_SOUL_MULTIPLIER[tier]
                break

        souls = int(souls * soul_mult)
        state.shadow_isles_souls += souls

        return souls

    def get_shadow_isles_stat_bonus(self, team_id: int) -> float:
        """Get the AD/AP bonus percentage for Shadow Isles units.

        Returns:
            Stat bonus as a decimal (0.18 = 18%)
        """
        state = self.get_team_state(team_id)
        if state.shadow_isles_count < 2:
            return 0.0

        for tier in sorted(self.SHADOW_ISLES_STAT_BONUS.keys(), reverse=True):
            if state.shadow_isles_count >= tier:
                return self.SHADOW_ISLES_STAT_BONUS[tier]

        return 0.0

    def apply_shadow_isles_stats(self, team_id: int, units: List["Unit"]):
        """Apply Shadow Isles stat bonuses to units with the trait.

        Called at combat start to give AD/AP bonus based on trait count.
        """
        state = self.get_team_state(team_id)
        if state.shadow_isles_count < 2:
            return

        bonus = self.get_shadow_isles_stat_bonus(team_id)

        for unit in units:
            if "Shadow Isles" in unit.traits:
                # Apply AD/AP bonus (percentage of base stats)
                ad_bonus = unit.base_stats.ad * bonus
                ap_bonus = unit.stats.ap * bonus if unit.stats.ap > 0 else 10 * bonus

                unit.stats.ad += ad_bonus
                unit.stats.ap += ap_bonus

    def get_shadow_isles_souls(self, team_id: int) -> int:
        """Get current Shadow Isles soul count for a team."""
        state = self.get_team_state(team_id)
        return state.shadow_isles_souls

    def reset_shadow_isles(self):
        """Reset Shadow Isles state for new combat."""
        for state in self.team_state.values():
            state.shadow_isles_souls = 0

    # =========================================================================
    # HUNTRESS TRAIT (Neeko + Nidalee synergy)
    # =========================================================================

    # Huntress - While Neeko is alive, Nidalee can't be targeted by basic attacks + gains Durability
    HUNTRESS_DURABILITY = 0.5  # 50% damage reduction

    def apply_huntress_synergy(self, units: List["Unit"]) -> bool:
        """Apply Huntress synergy if both Neeko and Nidalee are on the team.

        While Neeko is alive, Nidalee:
        - Cannot be targeted by basic attacks (is_basic_attack_immune)
        - Gains 50% Durability (damage reduction)

        Args:
            units: List of units on the team

        Returns:
            True if synergy was applied, False otherwise
        """
        # Find strongest Neeko and Nidalee
        neekos = [u for u in units if u.api_name == "TFT16_Neeko" and u.is_alive]
        nidalees = [u for u in units if u.api_name == "TFT16_Nidalee" and u.is_alive]

        if not neekos or not nidalees:
            return False

        # Sort by star level (descending) to find "strongest"
        strongest_neeko = max(neekos, key=lambda u: (u.star_level, u.stats.hp))
        strongest_nidalee = max(nidalees, key=lambda u: (u.star_level, u.stats.hp))

        # Mark Nidalee as protected by Neeko
        if not hasattr(strongest_nidalee, "_huntress_active"):
            strongest_nidalee._huntress_active = True
            strongest_nidalee._huntress_neeko_id = id(strongest_neeko)
            strongest_nidalee.is_basic_attack_immune = True
            strongest_nidalee.stats.damage_reduction += self.HUNTRESS_DURABILITY

        return True

    def check_huntress_on_death(self, dead_unit: "Unit", units: List["Unit"]):
        """Check if Huntress synergy should be removed when a unit dies.

        If Neeko dies, Nidalee loses her Huntress buffs.

        Args:
            dead_unit: The unit that just died
            units: List of all units
        """
        if dead_unit.api_name != "TFT16_Neeko":
            return

        # Find the Nidalee linked to this Neeko
        for unit in units:
            if (
                unit.api_name == "TFT16_Nidalee"
                and hasattr(unit, "_huntress_active")
                and hasattr(unit, "_huntress_neeko_id")
                and unit._huntress_neeko_id == id(dead_unit)
            ):
                # Remove Huntress buffs
                unit._huntress_active = False
                unit.is_basic_attack_immune = False
                unit.stats.damage_reduction = max(
                    0, unit.stats.damage_reduction - self.HUNTRESS_DURABILITY
                )

    def check_freljord_on_death(self, dead_unit: "Unit", all_units: List["Unit"]):
        """Freljord Tower destruction: stun enemies ONLY at 7 Freljord.

        At 3/5 Freljord: no stun on tower break (stats only).
        At 7 Freljord: stun the ENTIRE enemy team for 1.5s.

        Args:
            dead_unit: The unit that just died (only triggers for tower)
            all_units: All units in combat
        """
        # Only trigger when a Freljord tower is destroyed
        if not (
            getattr(dead_unit, "_is_tower", False) and dead_unit.api_name == "TFT16_FreljordProp"
        ):
            return

        by_team = getattr(self, "_freljord_by_team", {})
        freljord_count = by_team.get(dead_unit.team, 0)

        # Stun only triggers at 7 Freljord
        if freljord_count < 7:
            return

        effects = self.get_trait_tier(freljord_count, self.FRELJORD_EFFECTS)
        if not effects or "StunDuration" not in effects:
            return

        stun_duration = effects["StunDuration"]

        # 7 Freljord: stun entire enemy team
        enemies = [u for u in all_units if u.team != dead_unit.team and u.is_alive]
        for enemy in enemies:
            enemy.stun_timer = max(getattr(enemy, "stun_timer", 0), stun_duration)
            enemy.state = UnitState.STUNNED

    # =========================================================================
    # STAT-BUFFING TRAITS
    # =========================================================================

    # Arcanist (Sorcerer) - Team AP + bonus for Arcanists
    ARCANIST_EFFECTS = {
        2: {"AllyAP": 18, "BonusAP": 25},
        4: {"AllyAP": 25, "BonusAP": 40},
        6: {"AllyAP": 40, "BonusAP": 60},
    }

    # Defender - Team armor/MR + bonus for Defenders
    DEFENDER_EFFECTS = {
        2: {"TeamwideArmorMR": 12, "BonusArmorMR": 30},
        4: {"TeamwideArmorMR": 12, "BonusArmorMR": 55},
        6: {"TeamwideArmorMR": 12, "BonusArmorMR": 80},
    }

    # Bruiser (Brawler) - Team flat HP + bonus % HP for Bruisers
    BRUISER_EFFECTS = {
        2: {"TeamFlatHealth": 150, "BonusPercentHealth": 0.25},
        4: {"TeamFlatHealth": 150, "BonusPercentHealth": 0.45},
        6: {"TeamFlatHealth": 150, "BonusPercentHealth": 0.65},
    }

    # Slayer - AD + Omnivamp (scaling with missing HP handled in combat)
    SLAYER_EFFECTS = {
        2: {"BonusAD": 0.22, "BonusOmnivamp": 0.10, "AmountIncrease": 0.5},
        4: {"BonusAD": 0.33, "BonusOmnivamp": 0.16, "AmountIncrease": 0.5},
        6: {"BonusAD": 0.44, "BonusOmnivamp": 0.20, "AmountIncrease": 0.5},
    }

    # Juggernaut - Durability (more when above 50% HP) + heal allies on death
    JUGGERNAUT_EFFECTS = {
        2: {"BaseDR": 0.18, "IncreasedDR": 0.25, "HealRatio": 0.05},
        4: {"BaseDR": 0.20, "IncreasedDR": 0.30, "HealRatio": 0.05},
        6: {"BaseDR": 0.26, "IncreasedDR": 0.36, "HealRatio": 0.05},
    }

    # Invoker - Team mana regen + % mana increase for Invokers
    INVOKER_EFFECTS = {
        2: {"TeamBonusMana": 1, "PercentManaIncrease": 0.25},
        4: {"TeamBonusMana": 1, "PercentManaIncrease": 0.40},
    }

    # Vanquisher - Crit chance + crit damage (abilities can crit)
    VANQUISHER_EFFECTS = {
        2: {"BaseCritChance": 15, "CritDmg": 15},
        3: {"BaseCritChance": 20, "CritDmg": 20},
        4: {"BaseCritChance": 25, "CritDmg": 25},
        5: {"BaseCritChance": 30, "CritDmg": 30},
    }

    # Longshot - Damage amp + per-hex bonus
    LONGSHOT_EFFECTS = {
        2: {"BaseDamageAmp": 0.18, "PercentDamageIncrease": 0.02},
        3: {"BaseDamageAmp": 0.24, "PercentDamageIncrease": 0.03},
        4: {"BaseDamageAmp": 0.28, "PercentDamageIncrease": 0.04},
        5: {"BaseDamageAmp": 0.32, "PercentDamageIncrease": 0.05},
    }

    # Quickstriker (Rapidfire) - Team AS + bonus AS based on target's missing HP
    QUICKSTRIKER_EFFECTS = {
        2: {"TeamwideAS": 0.15, "MinBonusAS": 0.10, "MaxBonusAS": 0.30},
        3: {"TeamwideAS": 0.15, "MinBonusAS": 0.20, "MaxBonusAS": 0.45},
        4: {"TeamwideAS": 0.15, "MinBonusAS": 0.30, "MaxBonusAS": 0.60},
        5: {"TeamwideAS": 0.15, "MinBonusAS": 0.40, "MaxBonusAS": 0.80},
    }

    # Gunslinger - AD + every 4th attack bonus damage
    # Patch 16.4: AD 20/35% → 22/40%
    GUNSLINGER_EFFECTS = {
        2: {"AD": 0.22, "BonusDamage": 100, "NumAttacks": 4},
        4: {"AD": 0.40, "BonusDamage": 200, "NumAttacks": 4},
    }

    # Warden - Shields at HP thresholds (75% and 25%)
    WARDEN_EFFECTS = {
        2: {"PercentHealthShield": 0.16, "FirstThreshold": 0.75, "SecondThreshold": 0.25},
        3: {"PercentHealthShield": 0.20, "FirstThreshold": 0.75, "SecondThreshold": 0.25},
        4: {"PercentHealthShield": 0.26, "FirstThreshold": 0.75, "SecondThreshold": 0.25},
        5: {"PercentHealthShield": 0.33, "FirstThreshold": 0.75, "SecondThreshold": 0.25},
    }

    # =====================================================================
    # REGION TRAITS
    # =====================================================================

    # Demacia - Armor/MR for Demacia units
    DEMACIA_EFFECTS = {
        3: {"ArmorMR": 12},
        5: {"ArmorMR": 35},
        7: {"ArmorMR": 35},
        11: {"ArmorMR": 150},
    }

    # Freljord - Tower-based area buffs
    # A Frozen Tower is placed on the board before combat.
    # Units in front of the tower (toward row 0) get HP buff.
    # Units behind the tower (toward row 3) get damage buff.
    # The tower's area follows a 3-2-3-2 width pattern per row.
    # 3 Freljord: one tower, stats only (no stun)
    # 5 Freljord: second tower + increased stats (no stun)
    # 7 Freljord: stun ENTIRE enemy team when ANY tower is destroyed
    FRELJORD_EFFECTS = {
        3: {"HealthPercent": 0.08, "DA": 0.10},
        5: {"HealthPercent": 0.12, "DA": 0.16},
        7: {"HealthPercent": 0.16, "DA": 0.22, "StunDuration": 1.5},
    }

    # Void - AS for Void units
    VOID_EFFECTS = {
        2: {"BonusAS": 0.08},
        4: {"BonusAS": 0.18},
        6: {"BonusAS": 0.33},
        9: {"BonusAS": 0.40},
    }

    # Shurima - HP% + heal/sec + ArmorMR at higher tiers
    SHURIMA_EFFECTS = {
        2: {"BonusHealth": 0.20, "HealthRestorePerSecond": 20, "ASPerSecond": 0.02, "ArmorMR": 0},
        3: {"BonusHealth": 0.20, "HealthRestorePerSecond": 20, "ASPerSecond": 0.02, "ArmorMR": 50},
        4: {"BonusHealth": 0.20, "HealthRestorePerSecond": 20, "ASPerSecond": 0.02, "ArmorMR": 50},
    }

    # Yordle - flat HP + AS for Yordle units
    YORDLE_EFFECTS = {
        2: {"AS": 0.05, "BonusHealth": 40},
        4: {"AS": 0.05, "BonusHealth": 40},
        6: {"AS": 0.05, "BonusHealth": 40},
        8: {"AS": 0.05, "BonusHealth": 40},
        10: {"AS": 0.05, "BonusHealth": 40},
    }

    # Ixtal - HP for pairs + healing
    IXTAL_EFFECTS = {
        5: {"BonusHealthPairs": 250, "Heal": 2.0},
        7: {"BonusHealthPairs": 250, "Heal": 2.0},
    }

    # Zaun - Shimmer Fuse: delayed AS + durability burst (combat-time mechanic)
    ZAUN_EFFECTS = {
        3: {
            "ShimmerAS": 0.90,
            "ShimmerDurability": 0.15,
            "ShimmerDuration": 4.0,
            "InitialDelay": 4.0,
            "HealThreshold": 0.60,
        },
        5: {
            "ShimmerAS": 0.90,
            "ShimmerDurability": 0.15,
            "ShimmerDuration": 4.0,
            "InitialDelay": 4.0,
            "HealThreshold": 0.60,
            "MaxHealthHeal": 0.30,
        },
        7: {
            "ShimmerAS": 0.90,
            "ShimmerDurability": 0.15,
            "ShimmerDuration": 4.0,
            "InitialDelay": 4.0,
            "HealThreshold": 0.60,
            "MaxHealthHeal": 0.30,
        },
    }

    # Noxus - Atakhan summoning trait
    # After enemy team loses 15% total HP, Atakhan is summoned.
    # Atakhan's star level = sum of all Noxian star levels on the team.
    # Noxus breakpoints unlock different Atakhan abilities:
    #   3: Cleave (slash enemies dealing magic damage)
    #   5: Damage amp (Noxians get stacking damage amp while Atakhan alive)
    #   7: Soul drain (DOT ability on cast)
    #  10: Bring Ruin (after 10s, devour ALL enemy units)
    # Health multiplier scales by Noxus count and game stage.
    NOXUS_EFFECTS = {
        3: {"HPLostTrigger": 0.15, "RuinTimer": 10},
        5: {"HPLostTrigger": 0.15, "RuinTimer": 10},
        7: {"HPLostTrigger": 0.15, "RuinTimer": 10},
        10: {"HPLostTrigger": 0.15, "RuinTimer": 10},
    }

    # Atakhan base stats by star level (from combat_data.json)
    # Star level is determined by total Noxian star levels on team
    # Index: [_, 1-star, 2-star, 3-star, 4-star, ...]
    ATAKHAN_STATS = {
        1: {
            "hp": 320,
            "ad": 50,
            "as": 0.75,
            "armor": 45,
            "mr": 45,
            "omnivamp": 0.30,
            "cleave_damage": 150,
            "per_star_hp": 112,
            "per_star_ad_pct": 0.07,
            "per_star_ap_pct": 0.07,
            "damage_amp": 0.0,
            "dot_damage": 0,
            "dot_duration": 0,
        },
        2: {
            "hp": 560,
            "ad": 50,
            "as": 0.90,
            "armor": 60,
            "mr": 60,
            "omnivamp": 0.30,
            "cleave_damage": 225,
            "per_star_hp": 112,
            "per_star_ad_pct": 0.07,
            "per_star_ap_pct": 0.07,
            "damage_amp": 0.03,
            "dot_damage": 0,
            "dot_duration": 0,
        },
        3: {
            "hp": 800,
            "ad": 50,
            "as": 1.01,
            "armor": 75,
            "mr": 75,
            "omnivamp": 0.30,
            "cleave_damage": 340,
            "per_star_hp": 112,
            "per_star_ad_pct": 0.11,
            "per_star_ap_pct": 0.11,
            "damage_amp": 0.03,
            "dot_damage": 750,
            "dot_duration": 2.5,
        },
        4: {
            "hp": 16640,
            "ad": 50,
            "as": 1.61,
            "armor": 150,
            "mr": 150,
            "omnivamp": 1.0,
            "cleave_damage": 500,
            "per_star_hp": 112,
            "per_star_ad_pct": 0.20,
            "per_star_ap_pct": 0.20,
            "damage_amp": 0.03,
            "dot_damage": 750,
            "dot_duration": 30.0,
        },
    }

    # Atakhan star thresholds: total Noxian stars needed for each Atakhan tier
    # 3 Noxians all 1-star = 3 total => 1-star Atakhan
    # Typical 5 Noxians at 2-star = 10 total => 2-star
    # Typical 7 Noxians at 2-star = 14 total => 3-star
    # 10 Noxians at high stars = 4-star
    ATAKHAN_STAR_THRESHOLDS = [0, 3, 8, 14, 22]  # [_, 1*, 2*, 3*, 4*]

    # Noxus health multiplier by stage (patch 16.2 values)
    NOXUS_HP_MULTIPLIER = {
        5: {4: 4.5, 5: 5.25, 6: 6.5},
        7: {4: 5.75, 5: 7.25, 6: 9.25},
    }

    # Ionia - multiple sub-effects (simplified: use Determination path stats)
    IONIA_EFFECTS = {
        3: {"FlatDamage": 20, "Resists": 15, "ADAP": 10, "HealthPercent": 0.25},
        5: {"FlatDamage": 40, "Resists": 25, "ADAP": 15, "HealthPercent": 0.30},
        7: {"FlatDamage": 60, "Resists": 40, "ADAP": 20, "HealthPercent": 0.35},
        10: {"FlatDamage": 100, "Resists": 75, "ADAP": 100, "HealthPercent": 0.75},
    }

    # =====================================================================
    # CLASS TRAITS (missing)
    # =====================================================================

    # Disruptor - Damage amp + DR for Disruptor units
    DISRUPTOR_EFFECTS = {
        2: {"DamageAmp": 0.18, "DamageReduction": 0.10},
        4: {"DamageAmp": 0.40, "DamageReduction": 0.10},
    }

    # =====================================================================
    # UNIQUE / SPECIAL TRAITS
    # =====================================================================

    # Darkin - Omnivamp for Darkin units
    DARKIN_EFFECTS = {
        1: {"Vamp": 0.15},
        2: {"Vamp": 0.15},
        3: {"Vamp": 0.15},
    }

    # World Ender (Aatrox) - Durability + mana reduction
    WORLD_ENDER_EFFECTS = {
        1: {"Durability": 0.20, "ManaReduction": 10},
    }

    # Harvester (Fiddlesticks) - Enemy resist reduction + mana on kill
    HARVESTER_EFFECTS = {
        1: {"EnemyArmorMRReduction": 10, "ManaPerEnemyDeath": 10},
    }

    # Dragonborn (Shyvana) - Ability damage reduction
    DRAGONBORN_EFFECTS = {
        1: {"AbilityDamageReduction": 0.08},
    }

    # Soulbound (Lucian) - Damage amp for Lucian, DR for Senna
    SOULBOUND_EFFECTS = {
        1: {"LucianDA": 0.07, "SennaDR": 0.07},
    }

    # Eternal (Kindred) - Percent damage multiplier
    ETERNAL_EFFECTS = {
        1: {"PercentDamageMult": 3.25},
    }

    # The Boss (Sett) - Transform below HP threshold
    THE_BOSS_EFFECTS = {
        1: {"AttackSpeedPercent": 0.60, "HealPercent": 0.15, "MaxHealthThreshold": 0.45},
    }

    # Chosen Wolves (Ambessa + Kindred pair)
    CHOSEN_WOLVES_EFFECTS = {
        2: {"AmbessaBonusAD": 0.40, "WolfDamage": 0.30},
    }

    # Dragonguards (Jarvan + Shyvana pair)
    DRAGONGUARDS_EFFECTS = {
        2: {"JarvanShieldShare": 1.0},
    }

    # Sentinels of Light (Lucian + Vayne pair)
    SENTINELS_EFFECTS = {
        2: {"LucianSennaAS": 0.50, "NumBonusBolts": 2, "BoltEffectiveness": 0.25},
    }

    # Poison Pals (Singed + Teemo pair)
    POISON_PALS_EFFECTS = {
        2: {"SingedAPGain": 2, "TeemoDamageReq": 100},
    }

    # Timewinders (Ekko + Zilean)
    TIMEWINDERS_EFFECTS = {
        1: {"DamageShare": 0.10},
        2: {"DamageShare": 0.10},
    }

    def get_trait_tier(self, trait_count: int, effects_dict: Dict) -> Optional[Dict]:
        """Get the appropriate effect tier for a trait count.

        Args:
            trait_count: Number of units with the trait
            effects_dict: The trait's effect dictionary (e.g., ARCANIST_EFFECTS)

        Returns:
            The effect values for that tier, or None if not enough units
        """
        if trait_count < min(effects_dict.keys()):
            return None

        # Find highest qualifying tier
        for tier in sorted(effects_dict.keys(), reverse=True):
            if trait_count >= tier:
                return effects_dict[tier]
        return None

    def apply_stat_traits(
        self, team: List["Unit"], trait_counts: Dict[str, int], enemy_team: List["Unit"] = None
    ):
        """Apply all stat-buffing traits to a team at combat start.

        Args:
            team: List of units on this team
            trait_counts: Dict of trait name -> count for this team
            enemy_team: Enemy team (needed for Harvester resist reduction)
        """
        # --- CLASS TRAITS ---
        self._apply_arcanist(team, trait_counts.get("Arcanist", 0))
        self._apply_defender(team, trait_counts.get("Defender", 0))
        self._apply_bruiser(team, trait_counts.get("Bruiser", 0))
        self._apply_slayer(team, trait_counts.get("Slayer", 0))
        self._apply_juggernaut(team, trait_counts.get("Juggernaut", 0))
        self._apply_invoker(team, trait_counts.get("Invoker", 0))
        self._apply_vanquisher(team, trait_counts.get("Vanquisher", 0))
        self._apply_longshot(team, trait_counts.get("Longshot", 0))
        self._apply_quickstriker(team, trait_counts.get("Quickstriker", 0))
        self._apply_gunslinger(team, trait_counts.get("Gunslinger", 0))
        self._apply_warden(team, trait_counts.get("Warden", 0))
        self._apply_disruptor(team, trait_counts.get("Disruptor", 0))

        # --- REGION TRAITS ---
        self._apply_demacia(team, trait_counts.get("Demacia", 0))
        self._apply_freljord(team, trait_counts.get("Freljord", 0))
        self._apply_void(team, trait_counts.get("Void", 0))
        self._apply_shurima(team, trait_counts.get("Shurima", 0))
        self._apply_yordle(team, trait_counts.get("Yordle", 0))
        self._apply_ixtal(team, trait_counts.get("Ixtal", 0))
        self._apply_zaun(team, trait_counts.get("Zaun", 0))
        self._apply_noxus(team, trait_counts.get("Noxus", 0))
        self._apply_ionia(team, trait_counts.get("Ionia", 0))

        # --- UNIQUE TRAITS ---
        self._apply_darkin(team, trait_counts.get("Darkin", 0))
        self._apply_world_ender(team, trait_counts.get("World Ender", 0))
        self._apply_dragonborn(team, trait_counts.get("Dragonborn", 0))
        self._apply_soulbound(team, trait_counts.get("Soulbound", 0))
        self._apply_eternal(team, trait_counts.get("Eternal", 0))
        self._apply_the_boss(team, trait_counts.get("The Boss", 0))

        # Harvester needs enemy team reference
        if enemy_team is not None:
            self._apply_harvester(team, [team, enemy_team], trait_counts.get("Harvester", 0))
        else:
            self._apply_harvester(team, [team], trait_counts.get("Harvester", 0))

        # Huntress: Neeko + Nidalee synergy
        self.apply_huntress_synergy(team)

        # --- PAIR SYNERGIES ---
        self._apply_pair_synergies(team, trait_counts)

    def _apply_arcanist(self, team: List["Unit"], count: int):
        """Apply Arcanist trait: Team AP + bonus for Arcanists."""
        effects = self.get_trait_tier(count, self.ARCANIST_EFFECTS)
        if not effects:
            return

        ally_ap = effects["AllyAP"]
        bonus_ap = effects["BonusAP"]

        for unit in team:
            # All allies get base AP
            unit.stats.ap += ally_ap

            # Arcanists get additional bonus
            if "Arcanist" in unit.traits:
                unit.stats.ap += bonus_ap

    def _apply_defender(self, team: List["Unit"], count: int):
        """Apply Defender trait: Team armor/MR + bonus for Defenders."""
        effects = self.get_trait_tier(count, self.DEFENDER_EFFECTS)
        if not effects:
            return

        teamwide = effects["TeamwideArmorMR"]
        bonus = effects["BonusArmorMR"]

        for unit in team:
            # All allies get base armor/MR
            unit.stats.armor += teamwide
            unit.stats.magic_resist += teamwide

            # Defenders get additional bonus
            if "Defender" in unit.traits:
                unit.stats.armor += bonus
                unit.stats.magic_resist += bonus

    def _apply_bruiser(self, team: List["Unit"], count: int):
        """Apply Bruiser trait: Team flat HP + bonus % HP for Bruisers."""
        effects = self.get_trait_tier(count, self.BRUISER_EFFECTS)
        if not effects:
            return

        flat_hp = effects["TeamFlatHealth"]
        bonus_percent = effects["BonusPercentHealth"]

        for unit in team:
            # All allies get flat HP
            unit.stats.max_hp += flat_hp
            unit.stats.hp += flat_hp

            # Bruisers get additional % HP
            if "Bruiser" in unit.traits:
                bonus_hp = unit.base_stats.max_hp * bonus_percent
                unit.stats.max_hp += bonus_hp
                unit.stats.hp += bonus_hp

    def _apply_slayer(self, team: List["Unit"], count: int):
        """Apply Slayer trait: AD + Omnivamp for Slayers.

        Note: The missing HP AD scaling is handled during combat ticks.
        """
        effects = self.get_trait_tier(count, self.SLAYER_EFFECTS)
        if not effects:
            return

        bonus_ad_percent = effects["BonusAD"]
        bonus_omnivamp = effects["BonusOmnivamp"]

        for unit in team:
            if "Slayer" in unit.traits:
                # AD bonus (percentage of base)
                ad_bonus = unit.base_stats.ad * bonus_ad_percent
                unit.stats.ad += ad_bonus
                # Omnivamp
                unit.stats.omnivamp += bonus_omnivamp
                # Store the scaling factor for combat calculations
                unit._slayer_ad_increase = effects["AmountIncrease"]

    def _apply_juggernaut(self, team: List["Unit"], count: int):
        """Apply Juggernaut trait: Durability for Juggernauts.

        Note: The HP-conditional durability is handled during combat.
        """
        effects = self.get_trait_tier(count, self.JUGGERNAUT_EFFECTS)
        if not effects:
            return

        for unit in team:
            if "Juggernaut" in unit.traits:
                # Store Juggernaut data for combat calculations
                unit._juggernaut_base_dr = effects["BaseDR"]
                unit._juggernaut_increased_dr = effects["IncreasedDR"]
                unit._juggernaut_heal_ratio = effects["HealRatio"]
                # Apply base DR
                unit.stats.damage_reduction += effects["BaseDR"]

    def _apply_invoker(self, team: List["Unit"], count: int):
        """Apply Invoker trait: Team mana regen + % mana increase for Invokers."""
        effects = self.get_trait_tier(count, self.INVOKER_EFFECTS)
        if not effects:
            return

        team_mana = effects["TeamBonusMana"]
        percent_mana = effects["PercentManaIncrease"]

        for unit in team:
            # All allies get mana regen
            unit.stats.mana_regen += team_mana

            # Invokers get % increased mana gain
            if "Invoker" in unit.traits:
                unit._invoker_mana_increase = percent_mana

    def _apply_vanquisher(self, team: List["Unit"], count: int):
        """Apply Vanquisher trait: Crit chance + crit damage (abilities can crit)."""
        effects = self.get_trait_tier(count, self.VANQUISHER_EFFECTS)
        if not effects:
            return

        crit_chance = effects["BaseCritChance"] / 100  # Convert to decimal
        crit_dmg = effects["CritDmg"] / 100  # Convert to decimal

        for unit in team:
            if "Vanquisher" in unit.traits:
                unit.stats.crit_chance += crit_chance
                unit.stats.crit_multiplier += crit_dmg
                # Mark that abilities can crit
                unit._vanquisher_ability_crit = True

    def _apply_longshot(self, team: List["Unit"], count: int):
        """Apply Longshot trait: Damage amp + per-hex bonus for Longshots."""
        effects = self.get_trait_tier(count, self.LONGSHOT_EFFECTS)
        if not effects:
            return

        base_amp = effects["BaseDamageAmp"]
        per_hex = effects["PercentDamageIncrease"]

        for unit in team:
            if "Longshot" in unit.traits:
                unit.stats.damage_amp += base_amp
                # Store per-hex bonus for combat calculations
                unit._longshot_per_hex = per_hex

    def _apply_quickstriker(self, team: List["Unit"], count: int):
        """Apply Quickstriker trait: Team AS + bonus AS for Quickstrikers.

        Note: The target-missing-HP AS scaling is handled during combat.
        """
        effects = self.get_trait_tier(count, self.QUICKSTRIKER_EFFECTS)
        if not effects:
            return

        teamwide_as = effects["TeamwideAS"]
        min_as = effects["MinBonusAS"]
        max_as = effects["MaxBonusAS"]

        for unit in team:
            # All allies get teamwide AS
            unit.stats.attack_speed += teamwide_as

            # Quickstrikers get additional scaling (stored for combat)
            if "Quickstriker" in unit.traits:
                unit._quickstriker_min_as = min_as
                unit._quickstriker_max_as = max_as

    def _apply_gunslinger(self, team: List["Unit"], count: int):
        """Apply Gunslinger trait: AD + every Nth attack bonus damage."""
        effects = self.get_trait_tier(count, self.GUNSLINGER_EFFECTS)
        if not effects:
            return

        ad_percent = effects["AD"]
        bonus_damage = effects["BonusDamage"]
        num_attacks = effects["NumAttacks"]

        for unit in team:
            if "Gunslinger" in unit.traits:
                # AD bonus
                ad_bonus = unit.base_stats.ad * ad_percent
                unit.stats.ad += ad_bonus
                # Store bonus damage info for combat
                unit._gunslinger_bonus_damage = bonus_damage
                unit._gunslinger_attack_interval = num_attacks
                unit._gunslinger_attack_counter = 0

    def _apply_warden(self, team: List["Unit"], count: int):
        """Apply Warden trait: Setup shield thresholds for Wardens.

        Wardens gain shields when dropping below HP thresholds.
        """
        effects = self.get_trait_tier(count, self.WARDEN_EFFECTS)
        if not effects:
            return

        shield_percent = effects["PercentHealthShield"]
        first_threshold = effects["FirstThreshold"]
        second_threshold = effects["SecondThreshold"]

        for unit in team:
            if "Warden" in unit.traits:
                unit._warden_shield_percent = shield_percent
                unit._warden_first_threshold = first_threshold
                unit._warden_second_threshold = second_threshold
                unit._warden_first_triggered = False
                unit._warden_second_triggered = False

    # =====================================================================
    # REGION TRAIT METHODS
    # =====================================================================

    def _apply_demacia(self, team: List["Unit"], count: int):
        """Apply Demacia trait: Armor/MR for Demacia units."""
        effects = self.get_trait_tier(count, self.DEMACIA_EFFECTS)
        if not effects:
            return

        armor_mr = effects["ArmorMR"]

        for unit in team:
            if "Demacia" in unit.traits:
                unit.stats.armor += armor_mr
                unit.stats.magic_resist += armor_mr

    @staticmethod
    def _get_tower_zone(tower_pos: Tuple[int, int]) -> dict:
        """Compute the Freljord tower's area-of-effect zones.

        The tower affects hexes in a 3-2-3-2 width pattern:
        - At the tower's row: 3 wide (tower + 1 left + 1 right)
        - 1 row away: 2 wide
        - 2 rows away: 3 wide
        - 3 rows away: 2 wide

        Units in front of the tower (lower row = closer to enemy) get HP buff.
        Units directly beside the tower (same row) also get HP buff.
        Units behind the tower (higher row = toward back) get damage buff.

        Returns:
            {'hp': set of (row, col), 'damage': set of (row, col)}
        """
        t_row, t_col = tower_pos
        hp_hexes = set()
        damage_hexes = set()

        # Width pattern per row offset: 0→3, 1→2, 2→3, 3→2
        width_pattern = {0: 3, 1: 2, 2: 3, 3: 2}

        for row_offset in range(-3, 4):  # -3 to +3 rows from tower
            target_row = t_row + row_offset
            if target_row < 0 or target_row >= 4:
                continue

            abs_offset = abs(row_offset)
            if abs_offset > 3:
                continue

            width = width_pattern.get(abs_offset, 0)

            # Calculate which columns are in range
            # Width 3: col-1, col, col+1
            # Width 2: col, col+1 (or col-1, col depending on hex parity)
            if width == 3:
                cols = [t_col - 1, t_col, t_col + 1]
            elif width == 2:
                # For even offset rows: center on tower col
                cols = [t_col, t_col + 1] if t_col % 2 == 0 else [t_col - 1, t_col]
            else:
                cols = [t_col]

            valid_cols = [c for c in cols if 0 <= c < 7]

            for col in valid_cols:
                pos = (target_row, col)
                if pos == tower_pos:
                    continue  # Tower hex itself

                if row_offset < 0:
                    # In front of tower (lower row = toward front/enemy side)
                    hp_hexes.add(pos)
                elif row_offset > 0:
                    # Behind tower (higher row = toward back)
                    damage_hexes.add(pos)
                else:
                    # Same row as tower (beside it) = HP buff
                    hp_hexes.add(pos)

        return {"hp": hp_hexes, "damage": damage_hexes}

    def _apply_freljord(self, team: List["Unit"], count: int):
        """Apply Freljord trait via the Frozen Tower's area buffs.

        The tower provides directional buffs based on unit position:
        - HP buff to units in front of / beside the tower
        - Damage buff to units behind the tower
        Both scale with Freljord count (3/5/7 breakpoints).

        Also stores the count per team for tower destruction stun.
        """
        if not hasattr(self, "_freljord_by_team"):
            self._freljord_by_team = {}
        if team:
            team_id = team[0].team
            self._freljord_by_team[team_id] = count

        effects = self.get_trait_tier(count, self.FRELJORD_EFFECTS)
        if not effects:
            return

        hp_percent = effects["HealthPercent"]
        damage_amp = effects["DA"]

        # Find the Freljord tower on this team
        tower = None
        for unit in team:
            if getattr(unit, "_is_tower", False) and unit.api_name == "TFT16_FreljordProp":
                tower = unit
                break

        if tower:
            # Use tower position for directional buffs
            zones = self._get_tower_zone(tower.position)
            hp_zone = zones["hp"]
            damage_zone = zones["damage"]

            for unit in team:
                if unit == tower:
                    continue
                if unit.position in hp_zone:
                    bonus_hp = unit.base_stats.max_hp * hp_percent
                    unit.stats.max_hp += bonus_hp
                    unit.stats.hp += bonus_hp
                elif unit.position in damage_zone:
                    unit.stats.damage_amp += damage_amp
        else:
            # No tower placed - fall back to basic Freljord buff on Freljord units
            for unit in team:
                if "Freljord" in unit.traits:
                    bonus_hp = unit.base_stats.max_hp * hp_percent
                    unit.stats.max_hp += bonus_hp
                    unit.stats.hp += bonus_hp
                    unit.stats.damage_amp += damage_amp

    def _apply_void(self, team: List["Unit"], count: int):
        """Apply Void trait: Attack speed for Void units."""
        effects = self.get_trait_tier(count, self.VOID_EFFECTS)
        if not effects:
            return

        bonus_as = effects["BonusAS"]

        for unit in team:
            if "Void" in unit.traits:
                unit.stats.attack_speed += bonus_as

    def _apply_shurima(self, team: List["Unit"], count: int):
        """Apply Shurima trait: HP% + heal/sec + armor/MR at higher tiers."""
        effects = self.get_trait_tier(count, self.SHURIMA_EFFECTS)
        if not effects:
            return

        hp_percent = effects["BonusHealth"]
        heal_per_sec = effects["HealthRestorePerSecond"]
        armor_mr = effects.get("ArmorMR", 0)

        for unit in team:
            if "Shurima" in unit.traits:
                bonus_hp = unit.base_stats.max_hp * hp_percent
                unit.stats.max_hp += bonus_hp
                unit.stats.hp += bonus_hp
                # Store heal per second for combat-time application
                unit._shurima_heal_per_sec = heal_per_sec
                if armor_mr:
                    unit.stats.armor += armor_mr
                    unit.stats.magic_resist += armor_mr

    def _apply_yordle(self, team: List["Unit"], count: int):
        """Apply Yordle trait: AS + flat HP for Yordle units."""
        effects = self.get_trait_tier(count, self.YORDLE_EFFECTS)
        if not effects:
            return

        bonus_as = effects["AS"]
        bonus_hp = effects["BonusHealth"]

        for unit in team:
            if "Yordle" in unit.traits:
                unit.stats.attack_speed += bonus_as
                unit.stats.max_hp += bonus_hp
                unit.stats.hp += bonus_hp

    def _apply_ixtal(self, team: List["Unit"], count: int):
        """Apply Ixtal trait: Flat HP per pair of Ixtal units + healing."""
        effects = self.get_trait_tier(count, self.IXTAL_EFFECTS)
        if not effects:
            return

        hp_per_pair = effects["BonusHealthPairs"]
        heal = effects["Heal"]
        num_pairs = count // 2

        for unit in team:
            if "Ixtal" in unit.traits:
                bonus_hp = hp_per_pair * num_pairs
                unit.stats.max_hp += bonus_hp
                unit.stats.hp += bonus_hp
                # Store heal rate for combat-time
                unit._ixtal_heal_per_sec = heal

    def _apply_zaun(self, team: List["Unit"], count: int):
        """Apply Zaun trait: Setup Shimmer Fuse data for combat-time activation.

        Zaun units gain a delayed AS + durability burst during combat.
        """
        effects = self.get_trait_tier(count, self.ZAUN_EFFECTS)
        if not effects:
            return

        for unit in team:
            if "Zaun" in unit.traits:
                unit._zaun_shimmer_as = effects["ShimmerAS"]
                unit._zaun_shimmer_durability = effects["ShimmerDurability"]
                unit._zaun_shimmer_duration = effects["ShimmerDuration"]
                unit._zaun_initial_delay = effects["InitialDelay"]
                unit._zaun_shimmer_active = False
                unit._zaun_shimmer_triggered = False
                unit._zaun_heal_threshold = effects["HealThreshold"]
                unit._zaun_max_health_heal = effects.get("MaxHealthHeal", 0)

    def _apply_noxus(self, team: List["Unit"], count: int):
        """Apply Noxus trait: Set up Atakhan summoning for combat.

        After the enemy team loses 15% of total HP, Atakhan is summoned.
        Atakhan's star level = sum of all Noxian star levels.
        Noxus breakpoints (3/5/7/10) unlock different Atakhan abilities.
        """
        effects = self.get_trait_tier(count, self.NOXUS_EFFECTS)
        if not effects:
            return

        # Calculate total Noxian star levels for Atakhan's power
        total_noxian_stars = 0
        for unit in team:
            if "Noxus" in unit.traits:
                total_noxian_stars += unit.star_level

        # Determine Atakhan's star level from thresholds
        atakhan_star = 1
        for star, threshold in enumerate(self.ATAKHAN_STAR_THRESHOLDS):
            if star == 0:
                continue
            if total_noxian_stars >= threshold:
                atakhan_star = star

        # Store Noxus data on the team for mid-combat summoning
        if not hasattr(self, "_noxus_team_data"):
            self._noxus_team_data = {}

        team_id = team[0].team if team else 0
        self._noxus_team_data[team_id] = {
            "count": count,
            "total_stars": total_noxian_stars,
            "atakhan_star": atakhan_star,
            "hp_trigger": effects["HPLostTrigger"],
            "ruin_timer": effects.get("RuinTimer", 10),
            "summoned": False,
            "team": team,
        }

    def _apply_ionia(self, team: List["Unit"], count: int):
        """Apply Ionia trait: Simplified stat buffs for Ionia units.

        In the real game, each Ionia unit picks a random 'path' (Spirit,
        Determination, Enlightenment, etc.). Simplified to average stat buffs.
        """
        effects = self.get_trait_tier(count, self.IONIA_EFFECTS)
        if not effects:
            return

        resists = effects["Resists"]
        adap = effects["ADAP"]
        hp_percent = effects["HealthPercent"]

        for unit in team:
            if "Ionia" in unit.traits:
                unit.stats.armor += resists
                unit.stats.magic_resist += resists
                unit.stats.ad += adap
                unit.stats.ap += adap
                bonus_hp = unit.base_stats.max_hp * hp_percent
                unit.stats.max_hp += bonus_hp
                unit.stats.hp += bonus_hp

    # =====================================================================
    # MISSING CLASS TRAIT METHODS
    # =====================================================================

    def _apply_disruptor(self, team: List["Unit"], count: int):
        """Apply Disruptor trait: Damage amp + DR for Disruptor units."""
        effects = self.get_trait_tier(count, self.DISRUPTOR_EFFECTS)
        if not effects:
            return

        damage_amp = effects["DamageAmp"]
        damage_reduction = effects["DamageReduction"]

        for unit in team:
            if "Disruptor" in unit.traits:
                unit.stats.damage_amp += damage_amp
                unit.stats.damage_reduction += damage_reduction

    # =====================================================================
    # UNIQUE / SPECIAL TRAIT METHODS
    # =====================================================================

    def _apply_darkin(self, team: List["Unit"], count: int):
        """Apply Darkin trait: Omnivamp for Darkin units."""
        effects = self.get_trait_tier(count, self.DARKIN_EFFECTS)
        if not effects:
            return

        vamp = effects["Vamp"]

        for unit in team:
            if "Darkin" in unit.traits:
                unit.stats.omnivamp += vamp

    def _apply_world_ender(self, team: List["Unit"], count: int):
        """Apply World Ender trait: Durability + mana reduction for Aatrox."""
        effects = self.get_trait_tier(count, self.WORLD_ENDER_EFFECTS)
        if not effects:
            return

        durability = effects["Durability"]
        mana_reduction = effects["ManaReduction"]

        for unit in team:
            if "World Ender" in unit.traits:
                unit.stats.damage_reduction += durability
                unit.stats.mana = max(0, unit.stats.mana - mana_reduction)

    def _apply_harvester(self, team: List["Unit"], all_teams: List[List["Unit"]], count: int):
        """Apply Harvester trait: Reduce enemy resists + mana on kill.

        Args:
            team: Friendly team
            all_teams: All teams (to apply resist reduction to enemies)
            count: Number of Harvester units
        """
        effects = self.get_trait_tier(count, self.HARVESTER_EFFECTS)
        if not effects:
            return

        resist_reduction = effects["EnemyArmorMRReduction"]
        mana_per_kill = effects["ManaPerEnemyDeath"]

        # Apply resist reduction to enemy team
        for other_team in all_teams:
            if other_team is not team:
                for enemy in other_team:
                    enemy.stats.armor = max(0, enemy.stats.armor - resist_reduction)
                    enemy.stats.magic_resist = max(0, enemy.stats.magic_resist - resist_reduction)

        # Store mana-on-kill for combat-time
        for unit in team:
            if "Harvester" in unit.traits:
                unit._harvester_mana_per_kill = mana_per_kill

    def _apply_dragonborn(self, team: List["Unit"], count: int):
        """Apply Dragonborn trait: Ability damage reduction for Shyvana."""
        effects = self.get_trait_tier(count, self.DRAGONBORN_EFFECTS)
        if not effects:
            return

        ability_dr = effects["AbilityDamageReduction"]

        for unit in team:
            if "Dragonborn" in unit.traits:
                unit._dragonborn_ability_dr = ability_dr

    def _apply_soulbound(self, team: List["Unit"], count: int):
        """Apply Soulbound trait: Damage amp for Lucian."""
        effects = self.get_trait_tier(count, self.SOULBOUND_EFFECTS)
        if not effects:
            return

        lucian_da = effects["LucianDA"]

        for unit in team:
            if "Soulbound" in unit.traits:
                unit.stats.damage_amp += lucian_da

    def _apply_eternal(self, team: List["Unit"], count: int):
        """Apply Eternal trait: Increased damage multiplier for Kindred."""
        effects = self.get_trait_tier(count, self.ETERNAL_EFFECTS)
        if not effects:
            return

        damage_mult = effects["PercentDamageMult"]

        for unit in team:
            if "Eternal" in unit.traits:
                unit._eternal_damage_mult = damage_mult

    def _apply_the_boss(self, team: List["Unit"], count: int):
        """Apply The Boss trait: Transform data for Sett below HP threshold."""
        effects = self.get_trait_tier(count, self.THE_BOSS_EFFECTS)
        if not effects:
            return

        for unit in team:
            if "The Boss" in unit.traits:
                unit._boss_as_bonus = effects["AttackSpeedPercent"]
                unit._boss_heal_percent = effects["HealPercent"]
                unit._boss_hp_threshold = effects["MaxHealthThreshold"]
                unit._boss_transformed = False

    def _apply_pair_synergies(self, team: List["Unit"], trait_counts: Dict[str, int]):
        """Apply pair synergies that require specific champion combinations."""
        # Build name lookup
        team_api_names = {u.api_name for u in team}
        team_by_api = {u.api_name: u for u in team}

        # Chosen Wolves: Ambessa + Kindred
        if "TFT16_Ambessa" in team_api_names and "TFT16_Kindred" in team_api_names:
            effects = self.CHOSEN_WOLVES_EFFECTS[2]
            ambessa = team_by_api["TFT16_Ambessa"]
            ad_bonus = ambessa.base_stats.ad * effects["AmbessaBonusAD"]
            ambessa.stats.ad += ad_bonus
            kindred = team_by_api["TFT16_Kindred"]
            kindred._wolf_bonus_damage = effects["WolfDamage"]

        # Dragonguards: Jarvan IV + Shyvana
        if "TFT16_JarvanIV" in team_api_names and "TFT16_Shyvana" in team_api_names:
            effects = self.DRAGONGUARDS_EFFECTS[2]
            jarvan = team_by_api["TFT16_JarvanIV"]
            jarvan._dragonguard_shield_share = effects["JarvanShieldShare"]

        # Sentinels of Light: Lucian + Vayne
        if "TFT16_Lucian" in team_api_names and "TFT16_Vayne" in team_api_names:
            effects = self.SENTINELS_EFFECTS[2]
            lucian = team_by_api["TFT16_Lucian"]
            lucian.stats.attack_speed += effects["LucianSennaAS"]
            lucian._sentinel_bonus_bolts = effects["NumBonusBolts"]
            lucian._sentinel_bolt_effectiveness = effects["BoltEffectiveness"]

        # Poison Pals: Singed + Teemo
        if "TFT16_Singed" in team_api_names and "TFT16_Teemo" in team_api_names:
            effects = self.POISON_PALS_EFFECTS[2]
            singed = team_by_api["TFT16_Singed"]
            singed._poison_pals_ap_gain = effects["SingedAPGain"]
            singed._poison_pals_damage_req = effects["TeemoDamageReq"]

        # Timewinders: Ekko + Zilean
        if "TFT16_Ekko" in team_api_names and "TFT16_Zilean" in team_api_names:
            effects = self.TIMEWINDERS_EFFECTS[2]
            for api_name in ["TFT16_Ekko", "TFT16_Zilean"]:
                unit = team_by_api[api_name]
                unit._timewinder_damage_share = effects["DamageShare"]


# =============================================================================
# AUGMENT MANAGER - Handle Augment Effects
# =============================================================================

# Try to load augment data
try:
    _AUGMENT_DATA_PATH = resolve_augment_data_path()
    if _AUGMENT_DATA_PATH.exists():
        with open(_AUGMENT_DATA_PATH, "r", encoding="utf-8") as f:
            _RAW_AUGMENTS = json.load(f)
        _AUGMENTS_DATA = {a["apiName"]: a for a in _RAW_AUGMENTS if not a.get("disabled")}
        _AUGMENTS_LOADED = True
    else:
        _AUGMENTS_DATA = {}
        _AUGMENTS_LOADED = False
except Exception:
    _AUGMENTS_DATA = {}
    _AUGMENTS_LOADED = False


class AugmentManager:
    """Manages augment effects for combat simulation.

    Augment Categories:
    1. TEAM_STAT - Apply flat/percentage stat bonuses to all units
    2. TRAIT_CONDITIONAL - Apply bonuses if specific trait is active
    3. CHAMPION_SPECIFIC - Modify specific champion's abilities
    4. HEX_EFFECT - Create special hexes with aura effects
    5. ON_EVENT - Trigger effects on takedown, cast, etc.
    6. ITEM_CONDITIONAL - Apply bonuses if holding certain items
    """

    # Stat key mappings from augment effect keys to CombatStats attributes
    STAT_MAPPINGS = {
        "Health": "max_hp",
        "HP": "max_hp",
        "AD": "ad",
        "AttackDamage": "ad",
        "AP": "ap",
        "AbilityPower": "ap",
        "Armor": "armor",
        "MR": "magic_resist",
        "MagicResist": "magic_resist",
        "AttackSpeed": "attack_speed",
        "AS": "attack_speed",
        "CritChance": "crit_chance",
        "CritDamage": "crit_multiplier",
        "Omnivamp": "omnivamp",
        "DamageAmp": "damage_amp",
        "Durability": "damage_reduction",
        "ManaRegen": "mana_regen",  # Special handling
        "Mana": "mana",
        "Range": "range",
    }
    PERSISTENT_EFFECT_STAT_MAP = {
        "AbilityPower": ("ability_power", "ap"),
        "ManaRegen": ("mana_regen", "mana_regen"),
    }

    # Traits that can be checked for conditional augments
    # Maps lowercase search terms to actual trait display names (as used in combat_data.json)
    TRAIT_KEYWORDS = {
        "yordle": "Yordle",
        "slayer": "Slayer",
        "ionia": "Ionia",
        "noxus": "Noxus",
        "demacia": "Demacia",
        "bilgewater": "Bilgewater",
        "void": "Void",
        "shadow isles": "Shadow Isles",
        "piltover": "Piltover",
        "arcanist": "Arcanist",
        "sorcerer": "Arcanist",  # Backend uses Sorcerer, frontend uses Arcanist
        "automata": "Automata",
        "freljord": "Freljord",
        "targon": "Targon",
        "shurima": "Shurima",
        "zaun": "Zaun",
        "bruiser": "Bruiser",
        "defender": "Defender",
        "invoker": "Invoker",
        "juggernaut": "Juggernaut",
        "longshot": "Longshot",
        "quickstriker": "Quickstriker",
        "vanquisher": "Vanquisher",
        "warden": "Warden",
        "gunslinger": "Gunslinger",
        "ixtal": "Ixtal",
    }

    def __init__(self):
        """Initialize augment manager."""
        self.active_augments: List[str] = []  # List of active augment apiNames
        self.augment_data = _AUGMENTS_DATA if _AUGMENTS_LOADED else {}
        self.hex_effects: Dict[Tuple[int, int], Dict] = {}  # position -> effect info
        self.event_listeners: Dict[str, List[Dict]] = {
            "on_takedown": [],
            "on_cast": [],
            "on_damage_dealt": [],
            "on_round_start": [],
        }

    def reset(self):
        """Reset augment state for new combat."""
        self.hex_effects.clear()
        self.event_listeners = {
            "on_takedown": [],
            "on_cast": [],
            "on_damage_dealt": [],
            "on_round_start": [],
        }

    def set_augments(self, augment_names: List[str]):
        """Set the active augments for combat.

        Args:
            augment_names: List of augment apiNames (e.g., 'TFT16_Augment_DarkwillsInvasion')
        """
        self.active_augments = []
        for name in augment_names:
            # Try exact match first
            if name in self.augment_data:
                self.active_augments.append(name)
            else:
                # Try to find by display name
                for api_name, data in self.augment_data.items():
                    if data.get("name", "").lower() == name.lower():
                        self.active_augments.append(api_name)
                        break
                    elif data.get("en_name", "").lower() == name.lower():
                        self.active_augments.append(api_name)
                        break

    def get_augment_info(self, api_name: str) -> Optional[Dict]:
        """Get augment data by apiName."""
        return self.augment_data.get(api_name)

    def apply_augments(
        self,
        team: List["Unit"],
        trait_counts: Dict[str, int],
        round_persistent_player: Any = None,
    ):
        """Apply all active augments to a team at combat start.

        Args:
            team: List of units on this team
            trait_counts: Dict of trait name -> count for this team
        """
        for augment_name in self.active_augments:
            augment = self.get_augment_info(augment_name)
            if not augment:
                continue

            effects = augment.get("effects", {})
            desc = augment.get("desc", "").lower()

            # Determine augment type and apply appropriately
            # Check hero augments first (champion-specific)
            if self._is_hero_augment(augment_name):
                self._apply_hero_augment(team, augment_name, augment)
            elif self._is_team_stat_augment(augment):
                self._apply_team_stat_augment(team, augment, trait_counts)
            elif self._is_hex_augment(augment):
                self._setup_hex_augment(team, augment)
            elif self._is_event_augment(augment):
                self._register_event_augment(team, augment)
            elif self._is_item_conditional_augment(augment):
                self._apply_item_conditional_augment(
                    team,
                    augment,
                    round_persistent_player=round_persistent_player,
                )

    def _is_team_stat_augment(self, augment: Dict) -> bool:
        """Check if augment is a simple team-wide stat buff."""
        effects = augment.get("effects", {})
        desc = augment.get("desc", "").lower()

        # Has stat effects and applies to team
        stat_keys = [
            "Health",
            "HP",
            "AD",
            "AP",
            "Armor",
            "MR",
            "AttackSpeed",
            "DamageAmp",
            "Durability",
            "Omnivamp",
            "CritChance",
        ]

        has_stat_effects = any(
            k in effects or k.lower() in [s.lower() for s in effects.keys()] for k in stat_keys
        )

        applies_to_team = (
            "your team" in desc
            or "all allies" in desc
            or "your units" in desc
            or "your strongest" not in desc
        )

        return has_stat_effects and applies_to_team

    def _is_hex_augment(self, augment: Dict) -> bool:
        """Check if augment creates special hexes."""
        desc = augment.get("desc", "").lower()
        return "hex" in desc and ("gain a" in desc or "axiom" in augment.get("name", "").lower())

    def _is_event_augment(self, augment: Dict) -> bool:
        """Check if augment triggers on events."""
        desc = augment.get("desc", "").lower()
        return "takedown" in desc or "when" in desc and ("cast" in desc or "kill" in desc)

    def _is_item_conditional_augment(self, augment: Dict) -> bool:
        """Check if augment requires holding specific items."""
        desc = augment.get("desc", "").lower()
        return "holding" in desc or "equipped" in desc or "spatula" in desc

    # =========================================================================
    # HERO AUGMENTS - Champion-specific augments that modify abilities
    # =========================================================================

    # Hero augment definitions: apiName -> champion api_name and effects
    HERO_AUGMENTS = {
        "TFT16_Augment_XinZhaoCarry": {
            "champion": "TFT16_XinZhao",
            "name": "Trials of Twilight",
            "effects": {
                "constant_strikes": True,  # Constantly strikes nearby enemies
                "execute_threshold": 0.15,  # Execute enemies below 15% HP
                "transform_to_zaahen": True,  # Transform to Zaahen after 5 rounds as 3-star
                "rounds_to_transform": 5,
            },
        },
        "TFT16_Augment_ShadowIsles_RuinedKing": {
            "champion": "TFT16_Viego",
            "name": "The Ruined King",
            "effects": {
                "passive_share_percent": 0.30,  # Share 30% of passive with SI allies
                "soul_req_upgrade": 100,  # Ability upgrades after 100 souls
                "upgraded_ability": True,  # Track if ability has been upgraded
            },
        },
        "TFT16_Augment_RumbleCarry": {
            "champion": "TFT16_Rumble",
            "name": "Artillery Barrage",
            "effects": {
                "bonus_range": 7,  # +7 Range
                "constant_missiles": True,  # Constantly fires missiles
                "missile_as_scaling": True,  # Missile rate scales with AS
            },
        },
        "TFT16_Augment_IllaoiCarry": {
            "champion": "TFT16_Illaoi",
            "name": "Leap of Faith",
            "effects": {
                "becomes_fighter": True,  # Role changes to Fighter
                "slam_ability": True,  # Ability replaced with airborne slam
                "recast_on_kill": True,  # Recast when kills target
            },
        },
    }

    def _is_hero_augment(self, augment_name: str) -> bool:
        """Check if augment is a hero augment (champion-specific ability modifier)."""
        return augment_name in self.HERO_AUGMENTS

    def _apply_hero_augment(self, team: List["Unit"], augment_name: str, augment: Dict):
        """Apply a hero augment to the appropriate champion on the team.

        Hero augments modify a specific champion's abilities and behavior.
        """
        hero_data = self.HERO_AUGMENTS.get(augment_name)
        if not hero_data:
            return

        champion_api = hero_data["champion"]
        effects = hero_data["effects"]

        # Find the strongest matching champion on the team
        matching_units = [u for u in team if u.api_name == champion_api and u.is_alive]
        if not matching_units:
            return

        # Get strongest by star level, then items, then stats
        target_unit = max(
            matching_units, key=lambda u: (u.star_level, len(u.items), u.stats.ad + u.stats.ap)
        )

        # Apply hero augment flag and effects
        target_unit._hero_augment = augment_name
        target_unit._hero_augment_effects = effects.copy()

        # Apply immediate stat changes
        if augment_name == "TFT16_Augment_RumbleCarry":
            # Artillery Barrage: +7 Range
            target_unit.stats.range += effects.get("bonus_range", 7)

        elif augment_name == "TFT16_Augment_IllaoiCarry":
            # Leap of Faith: Change role to Fighter (affects traits)
            if effects.get("becomes_fighter"):
                target_unit._original_role = getattr(target_unit, "role", "Bruiser")
                target_unit.role = "Fighter"

        elif augment_name == "TFT16_Augment_ShadowIsles_RuinedKing":
            # The Ruined King: Share passive with SI allies
            share_pct = effects.get("passive_share_percent", 0.30)
            for ally in team:
                if ally != target_unit and ally.is_alive and "Shadow Isles" in ally.traits:
                    # Viego's passive gives stacking AD - share 30%
                    ally._viego_passive_share = share_pct

    def get_hero_augment_for_unit(self, unit: "Unit") -> Optional[Dict]:
        """Get hero augment data for a unit if they have one active."""
        augment_name = getattr(unit, "_hero_augment", None)
        if augment_name:
            return {
                "name": augment_name,
                "effects": getattr(unit, "_hero_augment_effects", {}),
                "data": self.HERO_AUGMENTS.get(augment_name, {}),
            }
        return None

    def _apply_team_stat_augment(
        self, team: List["Unit"], augment: Dict, trait_counts: Dict[str, int]
    ):
        """Apply team-wide stat buffs from an augment."""
        effects = augment.get("effects", {})
        desc = augment.get("desc", "").lower()

        # Check for trait-conditional bonuses
        enhanced_active = False
        conditional_trait = None
        for keyword, trait_name in self.TRAIT_KEYWORDS.items():
            if keyword in desc and ("if" in desc or "increased" in desc):
                # Check if this trait is active
                for trait_key in trait_counts:
                    if keyword in trait_key.lower() or trait_name.lower() in trait_key.lower():
                        if trait_counts[trait_key] >= 1:
                            enhanced_active = True
                            conditional_trait = trait_name
                            break
                break

        # Get the appropriate effect values
        for effect_key, value in effects.items():
            if effect_key.startswith("{"):
                continue  # Skip hashed/unknown keys

            # Check for enhanced version
            stat_key = effect_key
            stat_value = value

            if enhanced_active and "Enhanced" in effect_key:
                stat_key = effect_key.replace("Enhanced", "")
                stat_value = value
            elif "Enhanced" in effect_key:
                continue  # Skip enhanced value if trait not active

            # Map to CombatStats attribute
            combat_stat = self.STAT_MAPPINGS.get(stat_key)
            if not combat_stat:
                continue

            # Apply to all units
            for unit in team:
                self._apply_stat_bonus(unit, combat_stat, stat_value)

    def _apply_stat_bonus(self, unit: "Unit", stat_name: str, value: float):
        """Apply a stat bonus to a unit.

        Args:
            unit: The unit to modify
            stat_name: CombatStats attribute name
            value: The bonus value (may be flat or percentage based on stat)
        """
        if not hasattr(unit.stats, stat_name):
            return
        if value is None:
            return

        current = getattr(unit.stats, stat_name)

        # Determine if flat or percentage based on typical TFT conventions
        if stat_name in ["max_hp", "armor", "magic_resist", "ap"]:
            # These are typically flat values or percentages < 1 mean %
            if abs(value) < 1:
                # Percentage of current
                new_value = current * (1 + value)
            else:
                # Flat addition
                new_value = current + value
        elif stat_name in [
            "attack_speed",
            "crit_chance",
            "damage_amp",
            "damage_reduction",
            "omnivamp",
        ]:
            # These are percentage-based (0.15 = 15%)
            new_value = current + value
        elif stat_name == "ad":
            # AD is often percentage based in TFT
            if abs(value) < 1:
                new_value = current * (1 + value)
            else:
                new_value = current + value
        elif stat_name == "range":
            new_value = current + int(value)
        else:
            new_value = current + value

        setattr(unit.stats, stat_name, new_value)

        # Also update max_hp in hp if it increased
        if stat_name == "max_hp" and new_value > current:
            unit.stats.hp += new_value - current

    def _setup_hex_augment(self, team: List["Unit"], augment: Dict):
        """Setup hex-based augment effects (Axioms, etc.)."""
        effects = augment.get("effects", {})
        name = augment.get("name", "")

        hex_radius = effects.get("HexRadius", 2)

        # Extract effect parameters
        hex_effect = {
            "name": name,
            "radius": hex_radius,
            "effects": {},
        }

        # Map effects
        if "Resistances" in effects:
            hex_effect["effects"]["armor"] = effects["Resistances"]
            hex_effect["effects"]["magic_resist"] = effects["Resistances"]
        if "AttackSpeed" in effects:
            hex_effect["effects"]["attack_speed"] = effects["AttackSpeed"]
        if "ManaRegen" in effects:
            hex_effect["effects"]["mana_regen"] = effects["ManaRegen"]
        if "StunDuration" in effects:
            hex_effect["stun_on_threshold"] = True
            hex_effect["stun_duration"] = effects["StunDuration"]
            hex_effect["health_threshold"] = effects.get("HealthThreshold", 0.5)
        if "ShredPercent" in effects:
            hex_effect["shred"] = effects["ShredPercent"]
            hex_effect["shred_duration"] = effects.get("Duration", 5)
        if "SunderPercent" in effects:
            hex_effect["sunder"] = effects["SunderPercent"]
            hex_effect["sunder_duration"] = effects.get("Duration", 5)

        # For now, place hex at center of team's formation
        if team:
            avg_row = sum(u.position[0] for u in team) / len(team)
            avg_col = sum(u.position[1] for u in team) / len(team)
            hex_pos = (int(avg_row), int(avg_col))
            self.hex_effects[hex_pos] = hex_effect

    def _register_event_augment(self, team: List["Unit"], augment: Dict):
        """Register event-triggered augments."""
        desc = augment.get("desc", "").lower()
        effects = augment.get("effects", {})
        name = augment.get("name", "")

        event_data = {
            "name": name,
            "effects": effects,
            "augment": augment,
        }

        if "takedown" in desc:
            self.event_listeners["on_takedown"].append(event_data)
        if "cast" in desc and "when" in desc:
            self.event_listeners["on_cast"].append(event_data)

    def _apply_item_conditional_augment(
        self,
        team: List["Unit"],
        augment: Dict,
        round_persistent_player: Any = None,
    ):
        """Apply augments that check for specific items."""
        effects = augment.get("effects", {})
        desc = augment.get("desc", "").lower()

        # Check for Spatula/Frying Pan items (U.R.F. augment)
        spatula_items = ["Spatula", "FryingPan"]
        for unit in team:
            has_qualifying_item = any(
                any(s.lower() in item.name.lower() for s in spatula_items) for item in unit.items
            )

            if has_qualifying_item:
                # Apply stat bonuses
                if "AttackSpeed" in effects:
                    self._apply_stat_bonus(unit, "attack_speed", effects["AttackSpeed"])
                for effect_name, (bonus_name, stat_name) in self.PERSISTENT_EFFECT_STAT_MAP.items():
                    if effect_name not in effects:
                        continue
                    bonus_value = float(effects[effect_name])
                    if round_persistent_player is not None and unit.instance_id:
                        existing = round_persistent_player.get_augment_permanent_bonus(
                            unit.instance_id,
                            bonus_name,
                            0.0,
                        )
                        delta = bonus_value - existing
                        if delta != 0.0:
                            self._apply_stat_bonus(unit, stat_name, delta)
                        round_persistent_player.set_augment_permanent_bonus(
                            unit.instance_id,
                            bonus_name,
                            bonus_value,
                        )
                    else:
                        self._apply_stat_bonus(unit, stat_name, bonus_value)

    def apply_hex_effects(self, unit: "Unit") -> Dict[str, float]:
        """Get hex effects that apply to a unit based on their position.

        Args:
            unit: The unit to check

        Returns:
            Dict of stat bonuses from active hex effects
        """
        bonuses = {}
        for hex_pos, hex_effect in self.hex_effects.items():
            radius = hex_effect.get("radius", 2)
            if HexGrid.hex_distance(unit.position, hex_pos) <= radius:
                for stat, value in hex_effect.get("effects", {}).items():
                    bonuses[stat] = bonuses.get(stat, 0) + value
        return bonuses

    def on_takedown(self, killer: "Unit", victim: "Unit"):
        """Process takedown events for augments.

        Args:
            killer: The unit that got the kill
            victim: The unit that died
        """
        for listener in self.event_listeners["on_takedown"]:
            effects = listener.get("effects", {})

            # Bringer of Ruin style - permanent stat gains
            if "AP" in effects:
                killer.stats.ap += effects["AP"]
            if "MaxHealth" in effects:
                killer.stats.max_hp += effects["MaxHealth"]
                killer.stats.hp += effects["MaxHealth"]
            if "AD" in effects:
                killer.stats.ad += effects["AD"]

    def on_ability_cast(self, caster: "Unit"):
        """Process ability cast events for augments."""
        for listener in self.event_listeners["on_cast"]:
            effects = listener.get("effects", {})
            # Apply per-cast bonuses if any

    def get_all_augment_names(self) -> List[str]:
        """Get list of all available augment names."""
        return [data.get("name", api_name) for api_name, data in self.augment_data.items()]

    def get_combat_augments(self) -> List[Dict]:
        """Get list of augments that affect combat (not economy/shop augments)."""
        combat_augments = []
        combat_keywords = [
            "damage",
            "attack",
            "health",
            "armor",
            "resist",
            "shield",
            "heal",
            "ability",
            "mana",
            "cast",
            "attack speed",
            "omnivamp",
            "crit",
            "durability",
        ]

        for api_name, data in self.augment_data.items():
            desc = data.get("desc", "").lower()
            if any(kw in desc for kw in combat_keywords):
                combat_augments.append(
                    {
                        "apiName": api_name,
                        "name": data.get("name", ""),
                        "desc": data.get("desc", ""),
                        "effects": data.get("effects", {}),
                        "associatedTraits": data.get("associatedTraits", []),
                    }
                )

        return combat_augments


# =============================================================================
# ITEM DEFINITIONS - Set 16 Complete Item Database
# =============================================================================

# Try to import from the comprehensive item data file
try:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent / "data"))
    from set16_items import (
        ALL_ITEMS,
        ARTIFACT_ITEMS,
        BILGEWATER_STORE,
        BLACKSMITH_CONFIG,
        EMBLEM_ITEMS,
        ITEM_ALIASES,
        PILTOVER_MODULES,
        RADIANT_ITEMS,
    )

    _ITEMS_LOADED = True
except ImportError:
    _ITEMS_LOADED = False
    ALL_ITEMS = {}
    ITEM_ALIASES = {}
    ARTIFACT_ITEMS = {}
    RADIANT_ITEMS = {}
    EMBLEM_ITEMS = {}
    PILTOVER_MODULES = {}
    BILGEWATER_STORE = {}
    BLACKSMITH_CONFIG = {}


class ItemDatabase:
    """Database of TFT Set 16 items.

    Contains:
    - Base craftable items (components + completed)
    - Artifact items (from Ornn/Blacksmith trait)
    - Radiant items (upgraded versions)
    - Emblem items (trait spatulas)

    Stats format:
    - ad: percentage bonus (0.35 = 35% bonus AD)
    - ap: flat ability power
    - attack_speed: percentage (0.15 = 15% AS)
    - armor/magic_resist: flat values
    - hp: flat health
    - crit_chance: percentage (0.35 = 35%)
    - damage_amp: percentage (0.15 = 15% more damage)
    - omnivamp: percentage (0.20 = 20% healing)
    """

    # Load from comprehensive data file if available
    if _ITEMS_LOADED:
        ITEMS = ALL_ITEMS
        ALIASES = ITEM_ALIASES
        ARTIFACTS = ARTIFACT_ITEMS
        RADIANTS = RADIANT_ITEMS
        EMBLEMS = EMBLEM_ITEMS
    else:
        # Fallback to inline definitions
        ITEMS = {
            # Components
            "BFSword": {"ad": 0.10},
            "RecurveBow": {"attack_speed": 0.10},
            "NeedlesslyLargeRod": {"ap": 10},
            "TearOfTheGoddess": {"mana_regen": 1},
            "ChainVest": {"armor": 20},
            "NegatronCloak": {"magic_resist": 20},
            "GiantsBelt": {"hp": 150},
            "Spatula": {},
            "SparringGloves": {"crit_chance": 0.20},
            # Core completed items
            "Deathblade": {"ad": 0.55, "damage_amp": 0.10},
            "InfinityEdge": {"ad": 0.35, "crit_chance": 0.35, "crit_multiplier": 0.10},
            "GiantSlayer": {"ad": 0.15, "ap": 15, "attack_speed": 0.15, "damage_amp": 0.15},
            "LastWhisper": {"ad": 0.15, "attack_speed": 0.20, "crit_chance": 0.20},
            "Bloodthirster": {"ad": 0.15, "ap": 15, "magic_resist": 20, "omnivamp": 0.20},
            "RabadonsDeathcap": {"ap": 50, "damage_amp": 0.15},
            "JeweledGauntlet": {"ap": 35, "crit_chance": 0.35, "crit_multiplier": 0.10},
            "SpearOfShojin": {"ad": 0.15, "ap": 15, "mana_regen": 1},
            "WarmogsArmor": {"hp": 500},
            "GargoyleStoneplate": {"armor": 25, "magic_resist": 25, "hp": 100},
            "DragonsClaw": {"magic_resist": 75},
            "BrambleVest": {"armor": 65},
        }
        ALIASES = {
            "Gargoyle": "GargoyleStoneplate",
        }
        ARTIFACTS = {}
        RADIANTS = {}
        EMBLEMS = {}

    @staticmethod
    def create_item(name: str) -> Optional[Item]:
        """Create an item instance from name with effects."""
        # Check alias first
        resolved_name = ItemDatabase.ALIASES.get(name, name)

        if resolved_name not in ItemDatabase.ITEMS:
            print(f"Warning: Item '{name}' not found in database")
            return None

        stats = ItemDatabase.ITEMS[resolved_name].copy()

        # Get item effects (using module-level cached imports)
        if _ITEM_EFFECTS_LOADED:
            on_hit = _get_item_on_hit(resolved_name)
            on_ability = _get_item_on_ability(resolved_name)
            on_damage_dealt = _get_item_on_damage_dealt(resolved_name)
            on_damage_taken = _get_item_on_damage_taken(resolved_name)
            passive = _get_item_passive(resolved_name)
        else:
            on_hit = None
            on_ability = None
            on_damage_dealt = None
            on_damage_taken = None
            passive = None

        return Item(
            name=resolved_name,
            stats=stats,
            on_hit=on_hit,
            on_ability_cast=on_ability,
            on_damage_dealt=on_damage_dealt,
            on_damage_taken=on_damage_taken,
            passive=passive,
        )


# =============================================================================
# ABILITY DEFINITIONS
# =============================================================================


class AbilityDatabase:
    """Database of champion abilities parsed from combat_data."""

    @staticmethod
    def create_ability(api_name: str, champ_data: Dict, star_level: int) -> Optional[Ability]:
        """Create an ability from champion data."""
        ability_data = champ_data.get("ability", {})
        if not ability_data or not ability_data.get("name"):
            return None

        variables = ability_data.get("variables", {})

        # Helper to extract star-level values from a variable that may be
        # a list [0, 1star, 2star, 3star, ...] or a dict {'1star': v, ...}
        def _star_val(var, star):
            if isinstance(var, list):
                return (var[star] if star < len(var) else 0) or 0
            elif isinstance(var, dict):
                return (var.get(f"{star}star", 0)) or 0
            return 0

        # Try to find primary damage variable
        damage_by_star = {1: 0, 2: 0, 3: 0}
        damage_var = None
        num_hits = 1  # For multi-hit abilities

        # Check for multi-hit indicators (missiles, hits, etc.)
        for key in ["NumMissiles", "NumHits", "NumBounces", "NumAttacks"]:
            if key in variables:
                hit_var = variables[key]
                num_hits = _star_val(hit_var, star_level) or 1
                break

        # Common damage variable names (prefer per-hit damage for multi-hit)
        damage_keys = [
            "ADDamage",
            "APDamage",
            "Damage",
            "MagicDamage",
            "BaseDamage",
            "PrimaryDamage",
            "TotalDamage",
            "SpellDamage",
        ]

        for key in damage_keys:
            if key in variables:
                damage_var = variables[key]
                break

        # Fallback to first variable with star values
        if not damage_var:
            for key, val in variables.items():
                if isinstance(val, list) and len(val) >= 4:
                    damage_var = val
                    break
                elif isinstance(val, dict) and "1star" in val:
                    damage_var = val
                    break

        if damage_var:
            # For multi-hit abilities, multiply by number of hits
            # But cap it to avoid insane damage (TFT spreads damage across targets)
            hit_multiplier = min(num_hits, 6)  # Cap at 6 hits effective
            damage_by_star[1] = _star_val(damage_var, 1) * hit_multiplier
            damage_by_star[2] = _star_val(damage_var, 2) * hit_multiplier
            damage_by_star[3] = _star_val(damage_var, 3) * hit_multiplier

        # Determine ability type from role
        role = champ_data.get("role", "")
        if "AP" in role or "Caster" in role:
            damage_type = DamageType.MAGIC
            ap_scaling = 1.0
            ad_scaling = 0.0
        else:
            damage_type = DamageType.PHYSICAL
            ap_scaling = 0.0
            ad_scaling = 1.0

        # Check for AOE indicators
        ability_type = AbilityType.DAMAGE
        aoe_radius = 0
        num_targets = 1

        desc = ability_data.get("desc", "").lower()
        if "enemies" in desc or "all" in desc or "area" in desc:
            ability_type = AbilityType.AOE_DAMAGE
            aoe_radius = 2
            num_targets = 4
        elif "heal" in desc:
            ability_type = AbilityType.HEAL
        elif "shield" in desc:
            ability_type = AbilityType.SHIELD
        elif "dash" in desc or "leap" in desc:
            ability_type = AbilityType.DASH

        return Ability(
            name=ability_data.get("name", "Unknown").strip(),
            ability_type=ability_type,
            damage_type=damage_type,
            base_damage=damage_by_star,
            ap_scaling=ap_scaling,
            ad_scaling=ad_scaling,
            cast_time=0.5,
            aoe_radius=aoe_radius,
            num_targets=num_targets,
        )


# =============================================================================
# COMBAT ENGINE
# =============================================================================


class CombatEngine:
    """
    TFT Combat Simulation Engine v2.

    Features:
    - Full combat simulation with abilities
    - Hex-based movement and pathfinding
    - Item effects system
    - Buff/debuff tracking
    """

    # Game constants
    HEX_SIZE = 180  # Game units per hex
    # Mana per attack by role (Set 15+ role rework)
    MANA_PER_ATTACK_BY_ROLE = {
        "ADCarry": 10,
        "APCaster": 7,
        "APTank": 5,
        "ADTank": 5,
        "Tank": 5,
        "Defender": 5,
        "ADFighter": 10,
        "Specialist": 10,
        "Support": 7,
        "Assassin": 10,
    }
    MANA_PER_ATTACK_DEFAULT = 10
    MANA_ON_DAMAGE_TAKEN_CAP = 42.5  # Max mana per damage instance
    ATTACK_SPEED_CAP = 5.0  # Hard cap on attack speed
    MOVE_SPEED_BASE = 550  # Base movement speed
    HEX_MOVE_TIME = 0.5  # Seconds to move one hex at base speed

    # Star scaling
    HP_SCALING = {1: 1.0, 2: 1.8, 3: 3.24}
    AD_SCALING = {1: 1.0, 2: 1.5, 3: 2.25}

    def __init__(self, combat_data_path: Optional[Path] = None, logging_enabled: bool = True):
        """Initialize the combat engine with game data."""
        if combat_data_path is None:
            combat_data_path = Path(__file__).parent.parent / "data" / "combat_data.json"

        self.combat_data = _load_combat_data(combat_data_path)
        self.logging_enabled = logging_enabled

        self.champions = self.combat_data.get("champions", {})
        self.constants = self.combat_data.get("constants", {})

        # Combat state
        self.time = 0.0
        self.tick_rate = 0.033  # ~30 FPS simulation
        self.combat_log: List[Dict] = []
        self.units: List[Unit] = []
        self.projectiles: List[Dict] = []
        self._alive_team0: List[Unit] = []
        self._alive_team1: List[Unit] = []
        self._alive_dirty = False
        self._has_noxus = False
        self._ionic_spark_units: List[Unit] = []  # Units with Ionic Spark (cached)
        self._debug_takedowns: List[Dict[str, Any]] = []
        self._occupied_hexes: set = set()  # Cached occupied hex positions
        self._occupied_dirty = True  # True when occupied cache needs rebuild

        # Trait manager for Blacksmith, Bilgewater, Piltover
        self.trait_manager = TraitManager()
        self._round_persistent_players: Dict[
            int, Any
        ] = {}  # combat team (0/1) -> game-layer Player (or None)

        # Augment manager for augment effects
        self.augment_manager = AugmentManager()

        # Champion ability handlers
        if _ABILITIES_LOADED and ChampionAbilities:
            self.champion_abilities = ChampionAbilities(self)
        else:
            self.champion_abilities = None

    def create_unit(
        self,
        api_name: str,
        star_level: int,
        position: Tuple[int, int],
        team: int,
        items: List[str] = None,
        instance_id: str = "",
    ) -> Optional[Unit]:
        """Create a unit from champion data."""
        champ_data = self.champions.get(api_name)
        if not champ_data:
            print(f"Warning: Champion {api_name} not found in data")
            return None

        base_stats_data = champ_data.get("stats", {})
        timing = champ_data.get("timing", {})

        # Apply star scaling
        hp_mult = self.HP_SCALING.get(star_level, 1.0)
        ad_mult = self.AD_SCALING.get(star_level, 1.0)

        base_stats = CombatStats(
            hp=(base_stats_data.get("hp") or 500) * hp_mult,
            max_hp=(base_stats_data.get("hp") or 500) * hp_mult,
            ad=(base_stats_data.get("ad") or 50) * ad_mult,
            ap=0.0,
            attack_speed=base_stats_data.get("attackSpeed") or 0.7,
            armor=base_stats_data.get("armor") or 20,
            magic_resist=base_stats_data.get("magicResist") or 20,
            range=int(base_stats_data.get("range") or 1),
            mana=base_stats_data.get("startMana") or 0,
            max_mana=base_stats_data.get("mana") or 100,
            crit_chance=base_stats_data.get("critChance") or 0.25,
            crit_multiplier=base_stats_data.get("critMultiplier") or 1.4,
        )

        # Create ability
        ability = AbilityDatabase.create_ability(api_name, champ_data, star_level)

        # Create unit with copied stats (so items can modify)
        current_stats = base_stats.copy()

        unit = Unit(
            name=champ_data.get("name", api_name).strip(),
            api_name=api_name,
            instance_id=instance_id,
            star_level=star_level,
            stats=current_stats,
            base_stats=base_stats,
            position=position,
            team=team,
            traits=champ_data.get("traits", []),
            ability=ability,
            role=champ_data.get("role", ""),
            attack_windup=timing.get("attackWindup", 0.3),
            missile_speed=timing.get("missileSpeed"),
        )

        # Apply items
        if items:
            for item_name in items:
                item = ItemDatabase.create_item(item_name)
                if item:
                    self.apply_item(unit, item)

        return unit

    def set_round_persistent_players(
        self, team0_player: Any = None, team1_player: Any = None
    ) -> None:
        """Attach per-round persistent game-layer state for combat triggers.

        This is used for effects like Bilgewater takedown currency, which should
        be scoped to the owning player (not the combat engine instance).
        """
        self._round_persistent_players = {0: team0_player, 1: team1_player}

    def apply_item(self, unit: Unit, item: Item):
        """Apply item stats to a unit.

        Note: In Set 16, AD on items is a percentage (e.g., 0.35 = 35% bonus AD).
        Other stats like HP, armor, AP are flat values.
        Emblems also grant their associated trait to the unit.
        """
        unit.items.append(item)

        # Update cached item flags for hot-path checks
        if item.name == "JeweledGauntlet":
            unit._has_jeweled_gauntlet = True
        elif item.name in ("GiantSlayer", "RadiantGiantSlayer"):
            unit._has_giant_slayer = True
        elif item.name == "IonicSpark" or item.name.endswith("IonicSpark"):
            unit._has_ionic_spark = True

        # Check if item is an emblem and grant the trait
        try:
            from simulator.data.set16_items import EMBLEM_TO_TRAIT

            trait = EMBLEM_TO_TRAIT.get(item.name)
            if trait and trait not in unit.traits:
                unit.traits.append(trait)
        except ImportError:
            pass

        for stat, value in item.stats.items():
            if hasattr(unit.stats, stat):
                current = getattr(unit.stats, stat)

                # AD is a percentage multiplier in Set 16 items
                if stat == "ad":
                    # Convert percentage to flat AD based on base AD
                    flat_ad = unit.base_stats.ad * value
                    setattr(unit.stats, stat, current + flat_ad)

                # Flat stats
                elif stat == "hp":
                    # Set 16 item `hp` is flat max HP. Mirror Rust semantics.
                    unit.stats.max_hp += value
                    unit.stats.hp += value
                elif stat == "max_hp":
                    unit.stats.max_hp += value
                    unit.stats.hp += value
                elif stat in ["armor", "magic_resist", "ap"]:
                    setattr(unit.stats, stat, current + value)

                # Percentage stats (already stored as decimals)
                elif stat in [
                    "attack_speed",
                    "crit_chance",
                    "damage_amp",
                    "omnivamp",
                    "crit_multiplier",
                ]:
                    setattr(unit.stats, stat, current + value)

                # Mana stats
                elif stat == "mana_regen":
                    unit.stats.mana_regen += value

                # Bonus HP percentage (Warmog's, Dragon's Claw, Bramble Vest, Sunfire Cape)
                elif stat == "bonus_hp_pct":
                    bonus_hp = unit.base_stats.max_hp * value
                    unit.stats.max_hp += bonus_hp
                    unit.stats.hp += bonus_hp

                else:
                    setattr(unit.stats, stat, current + value)

    def _spawn_azir_soldiers(
        self, team: List[Unit], team_id: int, positions: List[Tuple[int, int]] = None
    ):
        """Spawn Sand Soldiers for Azir.

        In the game loop, soldiers are placed by the player at chosen positions
        (via Player.build_combat_team). This method is a fallback for direct
        combat engine usage (e.g., simulate_1v1) - it places soldiers in
        adjacent free hexes if no positions are specified.

        Soldiers are targetable blockers: enemies will attack them, but
        they don't attack back (0 AD). They have 750 HP, 50 armor/MR.
        Friendly units walk around them.

        Args:
            team: The team to add soldiers to
            team_id: Which team (0 or 1)
            positions: Explicit positions to place soldiers. If None,
                       auto-places adjacent to Azir (fallback).
        """
        for unit in team:
            if unit.api_name != "TFT16_Azir" or not unit.is_alive:
                continue

            if positions:
                # Use player-specified positions
                spots = [(r, c) for r, c in positions if 0 <= r < 4 and 0 <= c < 7]
            else:
                # Fallback: adjacent to Azir
                occupied = self.get_occupied_hexes()
                adjacent = HexGrid.get_neighbors(unit.position)
                spots = [
                    pos
                    for pos in adjacent
                    if pos not in occupied and 0 <= pos[0] < 4 and 0 <= pos[1] < 7
                ]

            for pos in spots[:2]:
                soldier = self.create_unit("TFT16_AzirSoldier", unit.star_level, pos, team_id)
                if soldier:
                    soldier._is_summon = True
                    soldier._summoner = unit.name
                    team.append(soldier)
                    self.units.append(soldier)
                    self._invalidate_occupied_cache()

    def get_occupied_hexes(self) -> set:
        """Get set of all occupied hex positions (cached, rebuilt on death/move)."""
        if self._occupied_dirty:
            self._occupied_hexes = {u.position for u in self.units if u.is_alive}
            self._occupied_dirty = False
        return self._occupied_hexes

    def _invalidate_occupied_cache(self):
        """Mark the occupied hex cache as needing rebuild."""
        self._occupied_dirty = True

    def set_unit_position(self, unit: Unit, new_pos: Tuple[int, int]) -> None:
        """Set a unit's position and invalidate occupied-hex caching.

        Any mid-combat position changes (dash/teleport/forced move) must go
        through this helper so occupied-hex caching stays correct.
        """
        if unit.position == new_pos:
            return
        unit.position = new_pos
        self._invalidate_occupied_cache()

    def calculate_damage(
        self,
        attacker: Unit,
        defender: Unit,
        base_damage: float,
        damage_type: DamageType,
        can_crit: bool = True,
        is_ability: bool = False,
    ) -> Tuple[float, bool]:
        """Calculate final damage after all modifiers.

        Uses Cython-accelerated math when available (~5-10x faster).
        """
        # Compute Longshot bonus (needs position LUT)
        longshot_per_hex = getattr(attacker, "_longshot_per_hex", 0)
        longshot_bonus = 0.0
        if longshot_per_hex > 0:
            distance = HexGrid._DISTANCE_LUT[attacker.position][defender.position]
            longshot_bonus = longshot_per_hex * distance

        # Map damage type to int for Cython: 0=physical, 1=magic, 2=true
        if damage_type == DamageType.PHYSICAL:
            dtype_int = 0
        elif damage_type == DamageType.MAGIC:
            dtype_int = 1
        else:
            dtype_int = 2

        # Vanquisher lets abilities crit too
        has_vanquisher = getattr(attacker, "_vanquisher_ability_crit", False)
        jg_or_vanq = attacker._has_jeweled_gauntlet or has_vanquisher

        if _CYTHON_OK:
            # Only consume RNG when a crit check would actually execute,
            # matching the Python fallback path to preserve RNG parity.
            if can_crit and (not is_ability or jg_or_vanq):
                rng_roll = random.random()
            else:
                rng_roll = 1.0  # No crit possible; don't consume RNG
            return _cy_calculate_damage(
                base_damage,
                attacker.stats.damage_amp,
                attacker.stats.crit_chance,
                attacker.stats.crit_multiplier,
                defender.stats.armor,
                defender.stats.magic_resist,
                defender.stats.damage_reduction,
                defender.stats.max_hp,
                dtype_int,
                can_crit,
                is_ability,
                jg_or_vanq,
                attacker._has_giant_slayer,
                getattr(defender, "_dragonborn_protected", False),
                longshot_bonus,
                rng_roll,
            )

        # Pure-Python fallback
        damage = base_damage
        damage *= 1 + attacker.stats.damage_amp + longshot_bonus

        did_crit = False
        if can_crit:
            if not is_ability or jg_or_vanq:
                if random.random() < attacker.stats.crit_chance:
                    damage *= attacker.stats.crit_multiplier
                    did_crit = True

        if damage_type == DamageType.PHYSICAL:
            resist = max(0, defender.stats.armor)
            damage *= 100 / (100 + resist)
        elif damage_type == DamageType.MAGIC:
            resist = max(0, defender.stats.magic_resist)
            damage *= 100 / (100 + resist)

        if defender.stats.damage_reduction > 0:
            damage *= 1 - defender.stats.damage_reduction

        if is_ability and getattr(defender, "_dragonborn_protected", False):
            damage *= 0.90

        if attacker._has_giant_slayer and defender.stats.max_hp > 1750:
            damage *= 1.15

        return max(0, damage), did_crit

    def check_hp_threshold_effects(self, unit: Unit):
        """Check for item effects that trigger at HP thresholds.

        - Edge of Night: At 60% HP, become untargetable briefly, cleanse negative effects
        - Zhonya's Paradox: At HP threshold, become invulnerable
        """
        hp_percent = unit.stats.hp / unit.stats.max_hp

        # Edge of Night - triggers at 60% HP (one time per combat)
        # Effect: untargetable, shed negative effects, heal 30% missing HP
        has_edge_of_night = any(
            i.name in ["EdgeOfNight", "TFT_Item_EdgeOfNight"] for i in unit.items
        )
        if has_edge_of_night and hp_percent <= 0.60:
            if not hasattr(unit, "_edge_of_night_triggered"):
                unit._edge_of_night_triggered = True

                # Become untargetable for 1.5 seconds
                unit.is_targetable = False
                unit.untargetable_duration = 1.5
                unit.state = UnitState.UNTARGETABLE

                # Cleanse negative effects (remove stun, debuffs)
                unit.stun_duration = 0
                unit.buffs = [b for b in unit.buffs if b.stacks > 0]

                # Heal 30% of missing HP
                missing_hp = unit.stats.max_hp - unit.stats.hp
                self.heal_unit(unit, missing_hp * 0.30, "edge_of_night")

                self.log_event(
                    "edge_of_night_proc", unit=unit.name, hp_percent=round(hp_percent * 100, 1)
                )

        # Zhonya's Paradox - triggers at HP threshold
        has_zhonyas = any(
            i.name in ["ZhonyasParadox", "TFT16_Item_ZhonyasParadox"] for i in unit.items
        )
        if has_zhonyas and hp_percent <= 0.50:
            if not hasattr(unit, "_zhonyas_triggered"):
                unit._zhonyas_triggered = True

                # Become untargetable and invulnerable for 2.5 seconds
                unit.is_targetable = False
                unit.untargetable_duration = 2.5
                unit.state = UnitState.UNTARGETABLE

                self.log_event(
                    "zhonyas_proc", unit=unit.name, hp_percent=round(hp_percent * 100, 1)
                )

        # Radiant Edge of Night - triggers at 60% HP with full heal
        has_radiant_edge = any(i.name in ["RadiantEdgeOfNight"] for i in unit.items)
        if has_radiant_edge and hp_percent <= 0.60:
            if not hasattr(unit, "_radiant_edge_triggered"):
                unit._radiant_edge_triggered = True

                # Become untargetable for 1.5 seconds
                unit.is_targetable = False
                unit.untargetable_duration = 1.5
                unit.state = UnitState.UNTARGETABLE

                # Cleanse and heal to full HP
                unit.stun_duration = 0
                missing_hp = unit.stats.max_hp - unit.stats.hp
                self.heal_unit(unit, missing_hp, "radiant_edge_of_night")

                self.log_event(
                    "radiant_edge_proc", unit=unit.name, hp_percent=round(hp_percent * 100, 1)
                )

    def gain_mana(self, unit: Unit, amount: float, source: str = "mana") -> float:
        """Gain mana for a unit, respecting Invoker and max mana cap.

        Returns the actual mana gained (after cap).
        """
        if amount <= 0 or unit.stats.max_mana <= 0:
            return 0.0

        invoker_increase = getattr(unit, "_invoker_mana_increase", 0.0)
        if invoker_increase:
            amount *= 1.0 + float(invoker_increase)

        before = unit.stats.mana
        unit.stats.mana = min(unit.stats.mana + amount, unit.stats.max_mana)
        return unit.stats.mana - before

    def apply_damage(
        self,
        attacker: Optional[Unit],
        defender: Unit,
        damage: float,
        damage_type: DamageType,
        source: str = "attack",
    ) -> float:
        """Apply damage to a unit and return actual damage dealt."""
        if not defender.is_alive:
            return 0

        # Check if defender is untargetable (shouldn't take damage)
        if not defender.is_targetable:
            return 0

        attacker_name = attacker.name if attacker is not None else "system"

        # Damage shield first
        if defender.stats.shield > 0:
            if damage <= defender.stats.shield:
                defender.stats.shield -= damage
                self.log_event(
                    "shield_absorb", attacker=attacker_name, defender=defender.name, damage=damage
                )
                return 0
            else:
                damage -= defender.stats.shield
                defender.stats.shield = 0

        # Mana on damage taken (1% pre-mitigation + 3% post-mitigation, capped)
        pre_mit_mana = damage * 0.01  # 1% of pre-mitigation damage
        post_mit_mana = min(damage, defender.stats.hp) * 0.03  # 3% of actual damage
        mana_gain = min(pre_mit_mana + post_mit_mana, self.MANA_ON_DAMAGE_TAKEN_CAP)
        self.gain_mana(defender, mana_gain, source="damage_taken")

        # Apply damage
        actual_damage = min(damage, defender.stats.hp)
        defender.stats.hp -= actual_damage
        defender.total_damage_taken += actual_damage
        if attacker is not None:
            attacker.total_damage_dealt += actual_damage

        # Omnivamp healing
        if attacker is not None and attacker.stats.omnivamp > 0:
            heal_amount = actual_damage * attacker.stats.omnivamp
            self.heal_unit(attacker, heal_amount, "omnivamp")

        # Check for death
        if defender.stats.hp <= 0:
            defender.stats.hp = 0
            defender.is_alive = False
            defender.state = UnitState.DEAD
            self._alive_dirty = True
            self._occupied_dirty = True

            # Freljord Ice Block: stun enemies on death
            if self.trait_manager:
                self.trait_manager.check_freljord_on_death(defender, self.units)

            # Check for Immortal resurrection (Zaahen)
            if self.champion_abilities and self.champion_abilities.check_immortal_resurrection(
                defender
            ):
                # Unit was resurrected - don't award takedown
                pass
            else:
                if attacker is not None:
                    self._debug_takedowns.append(
                        {
                            "killer_team": int(attacker.team),
                            "killer_api_name": attacker.api_name,
                            "victim_team": int(defender.team),
                            "victim_api_name": defender.api_name,
                        }
                    )
                # Award Bilgewater serpents for takedown (attacker's team)
                if attacker is not None and attacker.team != defender.team:
                    bg_state = self.trait_manager.get_team_state(attacker.team)
                    if "Bilgewater" in attacker.traits and bg_state.bilgewater_count >= 3:
                        player = getattr(self, "_round_persistent_players", {}).get(attacker.team)
                        if player is not None:
                            serpents = self.trait_manager.BILGEWATER_SERPENTS_PER_TAKEDOWN
                            player.add_bilgewater_serpents(serpents)
                            if serpents > 0:
                                self.log_event(
                                    "bilgewater_takedown",
                                    killer=attacker.name,
                                    victim=defender.name,
                                    serpents=serpents,
                                    total=getattr(player, "bilgewater_serpents", None),
                                )

                # Harvester: grant mana to Harvester units on enemy death
                if attacker is not None:
                    allies_team = self._alive_team0 if attacker.team == 0 else self._alive_team1
                    for ally in allies_team:
                        harvest_mana = getattr(ally, "_harvester_mana_per_kill", 0)
                        if harvest_mana > 0 and ally.is_alive:
                            self.gain_mana(ally, harvest_mana, source="harvester_kill")

                # Award Shadow Isles souls for takedown
                if attacker is not None and attacker.team != defender.team:
                    si_state = self.trait_manager.get_team_state(attacker.team)
                    if "Shadow Isles" in attacker.traits and si_state.shadow_isles_count >= 2:
                        # Get victim's cost (from champion data)
                        victim_data = self.champions.get(defender.api_name, {})
                        victim_cost = victim_data.get("cost", 1)
                        victim_star = defender.star_level

                        souls = self.trait_manager.award_soul(
                            attacker.team, victim_cost, victim_star
                        )
                        if souls > 0:
                            self.log_event(
                                "shadow_isles_soul",
                                killer=attacker.name,
                                victim=defender.name,
                                souls=souls,
                                total=si_state.shadow_isles_souls,
                                victim_cost=victim_cost,
                                victim_star=victim_star,
                            )

        if self.logging_enabled:
            self.log_event(
                "damage",
                source=source,
                attacker=attacker_name,
                defender=defender.name,
                damage=round(actual_damage, 1),
                damage_type=damage_type.value,
                defender_hp=round(defender.stats.hp, 1),
                defender_alive=defender.is_alive,
            )

        # Juggernaut: heal allies for % of damage taken
        if defender.is_alive and hasattr(defender, "_juggernaut_heal_ratio") and actual_damage > 0:
            heal_amt = actual_damage * defender._juggernaut_heal_ratio
            if heal_amt > 0:
                allies = [
                    u
                    for u in (self._alive_team0 if defender.team == 0 else self._alive_team1)
                    if u.is_alive and u is not defender
                ]
                for ally in allies:
                    self.heal_unit(ally, heal_amt, "juggernaut")

        # Check for HP threshold effects (Edge of Night, Zhonya's)
        if defender.is_alive:
            self.check_hp_threshold_effects(defender)

        # Trigger item on-damage-dealt effects for attacker
        if attacker is not None:
            for item in attacker.items:
                if item.on_damage_dealt:
                    item.on_damage_dealt(self, attacker, defender, actual_damage, damage_type)

        # Trigger item on-damage-taken effects for defender
        if defender.is_alive:
            for item in defender.items:
                if item.on_damage_taken:
                    item.on_damage_taken(self, defender, attacker, actual_damage, damage_type)

        return actual_damage

    def heal_unit(self, unit: Unit, amount: float, source: str = "heal"):
        """Heal a unit. Reduced by 33% if Wounded."""
        if not unit.is_alive:
            return

        # Check Wound debuff (33% healing reduction)
        wound_until = getattr(unit, "_wound_until", 0)
        if self.time < wound_until:
            amount *= 0.67

        actual_heal = min(amount, unit.stats.max_hp - unit.stats.hp)
        unit.stats.hp += actual_heal
        unit.total_healing += actual_heal

        if actual_heal > 0 and self.logging_enabled:
            self.log_event(
                "heal",
                unit=unit.name,
                amount=round(actual_heal, 1),
                source=source,
                hp=round(unit.stats.hp, 1),
            )

    def apply_shield(self, unit: Unit, amount: float, source: str = "shield"):
        """Apply shield to a unit."""
        if not unit.is_alive:
            return

        unit.stats.shield += amount
        self.log_event(
            "shield",
            unit=unit.name,
            amount=round(amount, 1),
            source=source,
            total_shield=round(unit.stats.shield, 1),
        )

    def apply_burn(
        self, attacker: Unit, target: Unit, burn_pct: float, duration: float, source: str = "burn"
    ):
        """Apply Burn debuff: X% max HP as true damage per second for duration.

        Damage ticks once per second over the full duration.
        """
        if not target.is_alive:
            return
        damage_per_tick = target.stats.max_hp * burn_pct
        dot = DotEffect(
            source_unit=attacker,
            damage_per_tick=damage_per_tick,
            tick_interval=1.0,
            remaining_duration=duration,
            damage_type=DamageType.TRUE,
            source_name=source,
            time_since_last_tick=0.0,
        )
        target.dot_effects.append(dot)
        self.log_event(
            "burn_applied",
            target=target.name,
            dps=round(damage_per_tick, 1),
            duration=duration,
            source=source,
        )

    def apply_cc(
        self,
        target: Unit,
        cc_type: str,
        duration: float,
        source: str = "cc",
        source_unit: "Unit" = None,
    ):
        """Apply crowd control effect to a unit.

        Args:
            target: Unit to CC
            cc_type: 'stun', 'fear', 'taunt', 'root'
            duration: Duration in seconds
            source: Source name for logging
            source_unit: For taunt, the unit that taunted
        """
        if not target.is_alive:
            return
        # Check CC immunity
        if hasattr(target, "immune_until") and self.time < target.immune_until:
            return
        # Apply tenacity
        tenacity = getattr(target, "_tenacity", 0)
        if tenacity > 0:
            duration *= 1 - tenacity
        if duration <= 0:
            return

        if cc_type == "fear":
            target.state = UnitState.FEARED
            target.stun_duration = max(target.stun_duration, duration)
        elif cc_type == "taunt":
            target.state = UnitState.TAUNTED
            target.stun_duration = max(target.stun_duration, duration)
            target._taunt_source = source_unit
        elif cc_type == "root":
            target.state = UnitState.ROOTED
            target.stun_duration = max(target.stun_duration, duration)
        else:  # stun
            target.state = UnitState.STUNNED
            target.stun_duration = max(target.stun_duration, duration)

        self.log_event(
            "cc_applied",
            target=target.name,
            cc_type=cc_type,
            duration=round(duration, 2),
            source=source,
        )

    def apply_wound(self, target: Unit, duration: float, source: str = "wound"):
        """Apply Wound debuff: reduce healing received by 33% for duration.

        Simplified: sets a marker on the unit; heal_unit checks it.
        """
        if not target.is_alive:
            return
        target._wound_until = self.time + duration
        self.log_event("wound", target=target.name, duration=duration, source=source)

    def apply_sunder(self, target: Unit, pct: float, duration: float, source: str = "sunder"):
        """Apply Sunder debuff: reduce armor by X% for duration.

        Stacks are tracked; armor is restored when the debuff expires.
        Re-applying refreshes the duration but does not double-stack from same source.
        """
        if not target.is_alive:
            return
        # Track active sunders: list of (reduction_amount, expiry_time, source)
        if not hasattr(target, "_sunder_stacks"):
            target._sunder_stacks = []
        expiry = self.time + duration
        # Refresh existing sunder from same source instead of stacking
        for i, (red, exp, src) in enumerate(target._sunder_stacks):
            if src == source:
                target._sunder_stacks[i] = (red, expiry, src)
                self.log_event("sunder_refresh", target=target.name, source=source)
                return
        # New sunder from this source
        reduction = target.stats.armor * pct
        target.stats.armor = max(0, target.stats.armor - reduction)
        target._sunder_stacks.append((reduction, expiry, source))
        self.log_event("sunder", target=target.name, reduction=round(reduction, 1), source=source)

    def apply_shred(self, target: Unit, pct: float, duration: float, source: str = "shred"):
        """Apply Shred debuff: reduce magic resist by X% for duration.

        Stacks are tracked; MR is restored when the debuff expires.
        Re-applying refreshes the duration but does not double-stack from same source.
        """
        if not target.is_alive:
            return
        if not hasattr(target, "_shred_stacks"):
            target._shred_stacks = []
        expiry = self.time + duration
        # Refresh existing shred from same source
        for i, (red, exp, src) in enumerate(target._shred_stacks):
            if src == source:
                target._shred_stacks[i] = (red, expiry, src)
                self.log_event("shred_refresh", target=target.name, source=source)
                return
        # New shred from this source
        reduction = target.stats.magic_resist * pct
        target.stats.magic_resist = max(0, target.stats.magic_resist - reduction)
        target._shred_stacks.append((reduction, expiry, source))
        self.log_event("shred", target=target.name, reduction=round(reduction, 1), source=source)

    def log_event(self, event_type: str, **kwargs):
        """Log a combat event."""
        if not self.logging_enabled:
            return
        self.combat_log.append({"time": round(self.time, 2), "type": event_type, **kwargs})

    def find_target(
        self,
        unit: Unit,
        enemies: List[Unit],
        targeting: TargetingType = TargetingType.NEAREST,
        include_untargetable: bool = False,
    ) -> Optional[Unit]:
        """Find a valid target for a unit.

        TFT targeting rules:
        1. Units prefer to target the nearest enemy
        2. Frontline units (tanks/fighters) "draw aggro" - they are prioritized
           when multiple enemies are at similar distances
        3. Some abilities have special targeting (lowest HP, farthest, etc.)
        4. Untargetable units cannot be targeted (Fizz, Zhonya's, Edge of Night)

        Args:
            include_untargetable: If True, include untargetable units (for positioning checks)
        """
        if include_untargetable:
            valid_enemies = [e for e in enemies if e.is_alive]
        else:
            valid_enemies = [e for e in enemies if e.is_alive and e.is_targetable]
        if not valid_enemies:
            return None

        if targeting == TargetingType.NEAREST:
            # TFT targeting: Prioritize frontline units when distances are close
            dist_row = HexGrid._DISTANCE_LUT[unit.position]
            min_dist = 999
            for e in valid_enemies:
                d = dist_row[e.position]
                if d < min_dist:
                    min_dist = d

            # Single pass: find closest frontline, and closest overall
            best_frontline = None
            best_frontline_dist = 999
            best_any = None
            best_any_dist = 999
            threshold = min_dist + 1

            for e in valid_enemies:
                d = dist_row[e.position]
                if d <= threshold and e.is_frontline:
                    if d < best_frontline_dist:
                        best_frontline_dist = d
                        best_frontline = e
                if d < best_any_dist:
                    best_any_dist = d
                    best_any = e

            return best_frontline if best_frontline is not None else best_any

        elif targeting == TargetingType.LOWEST_HP:
            return min(valid_enemies, key=lambda e: e.stats.hp)
        elif targeting == TargetingType.LOWEST_HP_PERCENT:
            return min(valid_enemies, key=lambda e: e.stats.hp / e.stats.max_hp)
        elif targeting == TargetingType.HIGHEST_HP:
            return max(valid_enemies, key=lambda e: e.stats.hp)
        elif targeting == TargetingType.FARTHEST:
            dist_row = HexGrid._DISTANCE_LUT[unit.position]
            return max(valid_enemies, key=lambda e: dist_row[e.position])
        elif targeting == TargetingType.RANDOM:
            return random.choice(valid_enemies)

        return valid_enemies[0]

    def get_enemies_in_range(
        self, unit: Unit, radius: int, enemies: List[Unit], include_untargetable: bool = False
    ) -> List[Unit]:
        """Get all enemies within radius of unit.

        Args:
            include_untargetable: If True, include untargetable units (for positioning/AoE checks)
        """
        dist_row = HexGrid._DISTANCE_LUT[unit.position]
        if include_untargetable:
            return [e for e in enemies if e.is_alive and dist_row[e.position] <= radius]
        return [
            e for e in enemies if e.is_alive and e.is_targetable and dist_row[e.position] <= radius
        ]

    def can_attack(self, unit: Unit, target: Unit) -> bool:
        """Check if unit can attack target (in range)."""
        return HexGrid._DISTANCE_LUT[unit.position][target.position] <= unit.stats.range

    def process_attack(self, unit: Unit):
        """Process an auto attack."""
        if not unit.target or not unit.target.is_alive:
            return

        if not self.can_attack(unit, unit.target):
            return

        # Track attacks performed
        unit.attacks_performed += 1

        # Calculate base damage
        base_damage = unit.stats.ad

        # Handle form-swapping champions like Jinx
        # Jinx: After NumAttacks (18), she switches from minigun (fast AS, single target)
        # to rockets (slower, AOE splash damage)
        is_jinx_rockets = False
        if unit.api_name == "TFT16_Jinx":
            # Get NumAttacks threshold from ability data
            champ_data = self.champions.get(unit.api_name, {})
            ability_vars = champ_data.get("ability", {}).get("variables", {})
            num_attacks_data = ability_vars.get("NumAttacks")
            threshold = _star_val(num_attacks_data, unit.star_level, 18)

            if unit.attacks_performed > threshold:
                is_jinx_rockets = True
                # Rocket form: Gets AD bonus from ability
                ad_bonus_data = ability_vars.get("ADDamage")
                ad_bonus = _star_val(ad_bonus_data, unit.star_level, 100)
                base_damage = unit.stats.ad + ad_bonus

        final_damage, did_crit = self.calculate_damage(
            unit, unit.target, base_damage, DamageType.PHYSICAL, can_crit=True
        )

        # Apply damage
        source = "jinx_rocket" if is_jinx_rockets else ("crit_attack" if did_crit else "attack")
        self.apply_damage(unit, unit.target, final_damage, DamageType.PHYSICAL, source)

        # Jinx rockets deal splash damage to nearby enemies
        if is_jinx_rockets:
            splash_targets = self.get_enemies_in_range(
                unit,
                1,
                [u for u in self.units if u.team != unit.team and u.is_alive and u != unit.target],
            )
            for splash_target in splash_targets[:2]:  # Max 2 splash targets
                splash_damage = final_damage * 0.5  # 50% splash
                self.apply_damage(
                    unit, splash_target, splash_damage, DamageType.PHYSICAL, "jinx_splash"
                )

        # Handle enhanced attacks (from Fizz ability or items)
        if unit.enhanced_attacks_remaining > 0:
            unit.enhanced_attacks_remaining -= 1

            # Apply on-hit magic damage
            if unit.enhanced_attack_on_hit_dmg > 0:
                on_hit_damage, _ = self.calculate_damage(
                    unit,
                    unit.target,
                    unit.enhanced_attack_on_hit_dmg,
                    DamageType.MAGIC,
                    can_crit=False,
                    is_ability=True,
                )
                self.apply_damage(
                    unit, unit.target, on_hit_damage, DamageType.MAGIC, "enhanced_on_hit"
                )

            # Reset bonus AS when enhanced attacks run out
            if unit.enhanced_attacks_remaining == 0:
                unit.stats.attack_speed -= unit.enhanced_attack_bonus_as
                unit.enhanced_attack_bonus_as = 0
                unit.enhanced_attack_on_hit_dmg = 0
                self.log_event("enhanced_attacks_ended", unit=unit.name)

        # Gunslinger: every Nth attack deals bonus physical damage
        if hasattr(unit, "_gunslinger_attack_counter"):
            unit._gunslinger_attack_counter += 1
            if unit._gunslinger_attack_counter >= unit._gunslinger_attack_interval:
                unit._gunslinger_attack_counter = 0
                bonus = unit._gunslinger_bonus_damage
                if bonus > 0 and unit.target and unit.target.is_alive:
                    self.apply_damage(
                        unit, unit.target, bonus, DamageType.PHYSICAL, "gunslinger_proc"
                    )

        # Gain mana (role-based)
        base_mana = self.MANA_PER_ATTACK_BY_ROLE.get(unit.role, self.MANA_PER_ATTACK_DEFAULT)
        mana_per_attack = base_mana + unit.stats.mana_regen
        self.gain_mana(unit, mana_per_attack, source="attack")

        # Item on-hit effects
        for item in unit.items:
            if item.on_hit:
                item.on_hit(self, unit, unit.target)

        # Red Buff / Morellonomicon burn now handled via item_effects.py on_hit/on_damage_dealt

    def _post_ability_cast(self, unit: Unit):
        """Shared post-ability-cast logic: item on-ability effects + Ionic Spark reaction."""
        # Trigger item on-ability effects
        for item in unit.items:
            if item.on_ability_cast:
                item.on_ability_cast(self, unit)

        # Ionic Spark reactive damage: enemies with Ionic Spark within 2 hexes
        # deal 150% of caster's max mana as magic damage to the caster.
        # Only check units with the cached _has_ionic_spark flag.
        if self._ionic_spark_units:
            dist_lut = HexGrid._DISTANCE_LUT
            spark_damage = unit.stats.max_mana * 1.50
            for enemy in self._ionic_spark_units:
                if not enemy.is_alive or enemy.team == unit.team:
                    continue
                if dist_lut[enemy.position][unit.position] <= 2:
                    final_dmg, _ = self.calculate_damage(
                        enemy, unit, spark_damage, DamageType.MAGIC, can_crit=False
                    )
                    self.apply_damage(enemy, unit, final_dmg, DamageType.MAGIC, "ionic_spark_react")

    def cast_ability(self, unit: Unit, enemies: List[Unit], allies: List[Unit]):
        """Cast unit's ability."""
        if not unit.ability:
            return

        ability = unit.ability
        unit.abilities_cast += 1

        # Get champion data for special ability handling
        champ_data = self.champions.get(unit.api_name, {})
        ability_vars = champ_data.get("ability", {}).get("variables", {})

        # Try champion-specific ability handler first
        if self.champion_abilities:
            if self.champion_abilities.cast(unit, enemies, allies, ability_vars):
                self._post_ability_cast(unit)
                self.log_event("ability_cast", unit=unit.name, ability=ability.name, targets=[])
                return  # Ability fully handled by champion-specific code

        # ==========================
        # FIZZ - Playful Trickster
        # ==========================
        # Fizz becomes UNTARGETABLE, leaps to farthest enemy within 4 hexes,
        # deals AoE damage on landing, then gains attack speed + on-hit magic damage for 4 attacks
        if unit.api_name == "TFT16_Fizz":
            # Find farthest enemy within 4 hexes
            enemies_in_range = [
                e
                for e in enemies
                if e.is_alive
                and e.is_targetable
                and HexGrid.hex_distance(unit.position, e.position) <= 4
            ]

            if not enemies_in_range:
                # No enemies in range - find closest enemy instead
                enemies_in_range = [e for e in enemies if e.is_alive and e.is_targetable]

            if enemies_in_range:
                # Target the farthest enemy in range
                target = max(
                    enemies_in_range, key=lambda e: HexGrid.hex_distance(unit.position, e.position)
                )

                # Become untargetable during leap (brief moment)
                unit.is_targetable = False
                unit.untargetable_duration = 0.3  # Brief untargetable during leap

                # Get ability damage values
                ap_dmg_data = ability_vars.get("APDamage")
                base_damage = _star_val(ap_dmg_data, unit.star_level, 150)

                # Get enhanced attack values
                as_bonus_data = ability_vars.get("ASBonus") or ability_vars.get("AttackSpeed")
                as_bonus = (
                    _star_val(as_bonus_data, unit.star_level, 100) / 100
                )  # Convert to decimal
                on_hit_data = ability_vars.get("OnHitDamage") or ability_vars.get("APOnHit")
                on_hit_dmg = _star_val(on_hit_data, unit.star_level, 50)
                num_attacks_data = ability_vars.get("NumAttacks")
                num_enhanced = int(_star_val(num_attacks_data, unit.star_level, 4))

                # Find position adjacent to target
                target_neighbors = HexGrid.get_neighbors(target.position)
                valid_spots = [n for n in target_neighbors if n not in self.get_occupied_hexes()]

                if valid_spots:
                    # Teleport to position adjacent to target
                    old_pos = unit.position
                    self.set_unit_position(unit, valid_spots[0])
                    self.log_event(
                        "fizz_leap",
                        unit=unit.name,
                        from_pos=old_pos,
                        to_pos=unit.position,
                        target=target.name,
                    )

                # Deal AoE damage on landing
                landing_targets = self.get_enemies_in_range(unit, 1, enemies)
                for enemy in landing_targets:
                    final_damage, _ = self.calculate_damage(
                        unit,
                        enemy,
                        base_damage + unit.stats.ap,
                        DamageType.MAGIC,
                        can_crit=True,
                        is_ability=True,
                    )
                    self.apply_damage(unit, enemy, final_damage, DamageType.MAGIC, "fizz_landing")

                # Grant enhanced attacks
                unit.enhanced_attacks_remaining = num_enhanced
                unit.enhanced_attack_bonus_as = as_bonus
                unit.enhanced_attack_on_hit_dmg = on_hit_dmg + (
                    unit.stats.ap * 0.5
                )  # Scales with AP
                unit.stats.attack_speed += as_bonus

                self.log_event(
                    "fizz_enhanced",
                    unit=unit.name,
                    bonus_as=as_bonus,
                    on_hit=unit.enhanced_attack_on_hit_dmg,
                    attacks=num_enhanced,
                )

            # Reset mana
            unit.stats.mana = 0

            # Shared post-cast logic (item effects + Ionic Spark reaction)
            self._post_ability_cast(unit)

            self.log_event(
                "ability_cast",
                unit=unit.name,
                ability=ability.name,
                targets=[t.name for t in enemies_in_range[:1]],
            )
            return  # Fizz ability fully handled

        # Handle Kai'Sa (and other FormSwapper champions) - uses higher of AD or AP damage
        if "FormSwapper" in unit.role:
            ad_dmg_data = ability_vars.get("ADDamage")
            ap_dmg_data = ability_vars.get("APDamage")

            ad_base = _star_val(ad_dmg_data, unit.star_level, 0)
            ap_base = _star_val(ap_dmg_data, unit.star_level, 0)

            # Calculate total damage for each form
            ad_total = ad_base + (unit.stats.ad * 1.0)  # AD scaling
            ap_total = ap_base + (unit.stats.ap * 1.0)  # AP scaling

            # Use whichever is higher
            if ad_total >= ap_total:
                base_damage = ad_base
                ability.damage_type = DamageType.PHYSICAL
                ability.ad_scaling = 1.0
                ability.ap_scaling = 0.0
            else:
                base_damage = ap_base
                ability.damage_type = DamageType.MAGIC
                ability.ad_scaling = 0.0
                ability.ap_scaling = 1.0

            # For multi-target abilities like Kai'Sa missiles
            num_targets_data = ability_vars.get("NumTargets")
            num_targets = int(_star_val(num_targets_data, unit.star_level, 4))
            num_missiles_data = ability_vars.get("NumMissiles")
            num_missiles = int(_star_val(num_missiles_data, unit.star_level, 15))

            # Kai'Sa fires missiles at multiple targets
            # 60% on current target, rest spread among others
            ability.num_targets = num_targets
            ability.ability_type = AbilityType.AOE_DAMAGE
            ability.aoe_radius = 3

            # Multiply damage by effective hits per target
            missiles_on_main = num_missiles * 0.6
            base_damage = base_damage * missiles_on_main
        else:
            # Standard ability damage
            base_damage = ability.base_damage.get(unit.star_level, 0)

        # Apply AP/AD scaling
        total_damage = base_damage
        if ability.ap_scaling > 0:
            total_damage += unit.stats.ap * ability.ap_scaling
        if ability.ad_scaling > 0:
            total_damage += unit.stats.ad * ability.ad_scaling

        # Handle tank abilities with defensive scaling
        if "Tank" in unit.role:
            # Check for armor scaling (e.g., Braum's ArmorDamage)
            armor_dmg_data = ability_vars.get("ArmorDamage")
            if armor_dmg_data:
                armor_scaling = _star_val(armor_dmg_data, unit.star_level, 0)
                total_damage += unit.stats.armor * armor_scaling

            # Check for HP scaling (e.g., percentage of max HP damage)
            hp_pct_data = ability_vars.get("HealthPercent") or ability_vars.get(
                "PercentHealthDamage"
            )
            if hp_pct_data:
                hp_scaling = _star_val(hp_pct_data, unit.star_level, 0)
                total_damage += unit.stats.max_hp * hp_scaling

            # Check for shield abilities (Galio, Nautilus, Shen, Poppy)
            shield_data = (
                ability_vars.get("Shield")
                or ability_vars.get("ShieldAmt")
                or ability_vars.get("APShield")
            )
            if shield_data:
                shield_amount = _star_val(shield_data, unit.star_level, 0)
                # Nautilus also has percent HP shield
                pct_hp_shield = ability_vars.get("PercentHealthShield")
                if pct_hp_shield:
                    pct = _star_val(pct_hp_shield, unit.star_level, 0)
                    shield_amount += unit.stats.max_hp * pct
                ability.ability_type = AbilityType.SHIELD
                total_damage = shield_amount  # Use shield amount instead of damage

        # Get targets based on ability type
        targets = []

        if ability.ability_type == AbilityType.DAMAGE:
            if unit.target and unit.target.is_alive:
                targets = [unit.target]
            else:
                target = self.find_target(unit, enemies, ability.targeting)
                if target:
                    targets = [target]

        elif ability.ability_type == AbilityType.AOE_DAMAGE:
            center = unit.target.position if unit.target else unit.position
            targets = self.get_enemies_in_range(unit, ability.aoe_radius, enemies)
            targets = targets[: ability.num_targets]

        elif ability.ability_type == AbilityType.HEAL:
            # Heal self or lowest HP ally
            targets = [min(allies, key=lambda a: a.stats.hp / a.stats.max_hp)]

        elif ability.ability_type == AbilityType.SHIELD:
            # Shield self or lowest HP ally
            targets = [min(allies, key=lambda a: a.stats.hp / a.stats.max_hp)]

        # Apply ability effects
        for target in targets:
            if ability.ability_type in [AbilityType.DAMAGE, AbilityType.AOE_DAMAGE]:
                final_damage, did_crit = self.calculate_damage(
                    unit, target, total_damage, ability.damage_type, can_crit=True, is_ability=True
                )
                self.apply_damage(
                    unit, target, final_damage, ability.damage_type, f"ability:{ability.name}"
                )

            elif ability.ability_type == AbilityType.HEAL:
                self.heal_unit(target, total_damage, f"ability:{ability.name}")

            elif ability.ability_type == AbilityType.SHIELD:
                self.apply_shield(target, total_damage, f"ability:{ability.name}")

        # Reset mana
        unit.stats.mana = 0

        # Shared post-cast logic (item effects + Ionic Spark reaction)
        self._post_ability_cast(unit)

        self.log_event(
            "ability_cast", unit=unit.name, ability=ability.name, targets=[t.name for t in targets]
        )

    def move_unit_towards(self, unit: Unit, target_pos: Tuple[int, int]):
        """Move unit one step towards target position."""
        if unit.position == target_pos:
            return

        occupied = self.get_occupied_hexes()
        occupied.discard(unit.position)  # Current pos is fine

        # Use A* pathfinding (matches Rust engine for parity)
        path = HexGrid.find_path(unit.position, target_pos, occupied)
        if path:
            old_pos = unit.position
            self.set_unit_position(unit, path[0])
            if self.logging_enabled:
                self.log_event("move", unit=unit.name, from_pos=old_pos, to_pos=path[0])

    def process_unit_tick(self, unit: Unit, enemies: List[Unit], allies: List[Unit]):
        """Process one tick for a unit."""
        if not unit.is_alive or unit.state == UnitState.DEAD:
            return

        # Handle untargetable state (Fizz, Zhonya's, Edge of Night)
        if unit.untargetable_duration > 0:
            unit.untargetable_duration -= self.tick_rate
            unit.state = UnitState.UNTARGETABLE
            unit.is_targetable = False

            if unit.untargetable_duration <= 0:
                # Untargetable ended - become targetable again
                unit.is_targetable = True
                unit.state = UnitState.IDLE

                # If there's a return position (like Spectral Cutlass), teleport back
                if unit.untargetable_return_pos:
                    self.set_unit_position(unit, unit.untargetable_return_pos)
                    unit.untargetable_return_pos = None
                    self.log_event("teleport_return", unit=unit.name, position=unit.position)
            return  # Cannot act while untargetable (unless it's Fizz mid-leap)

        # Handle stun/fear (both fully disable)
        if unit.stun_duration > 0:
            unit.stun_duration -= self.tick_rate
            # Apply tenacity to reduce remaining duration
            tenacity = getattr(unit, "_tenacity", 0)
            if tenacity > 0:
                unit.stun_duration -= self.tick_rate * tenacity
            if unit.state not in (UnitState.FEARED, UnitState.TAUNTED, UnitState.ROOTED):
                unit.state = UnitState.STUNNED
            # Fear: random movement away (treated like stun but moves)
            if unit.state == UnitState.FEARED and unit.stun_duration > 0:
                neighbors = HexGrid.get_neighbors(unit.position)
                occupied = self.get_occupied_hexes()
                valid = [n for n in neighbors if n not in occupied]
                if valid:
                    self.set_unit_position(unit, random.choice(valid))
                return
            # Taunt: forced to attack taunter (can attack, not move freely)
            if unit.state == UnitState.TAUNTED:
                taunt_src = getattr(unit, "_taunt_source", None)
                if taunt_src and taunt_src.is_alive:
                    unit.target = taunt_src
                    # Fall through to attack logic below
                else:
                    unit.state = UnitState.IDLE
                    unit.stun_duration = 0
            # Root: can't move but can attack/cast in range
            elif unit.state == UnitState.ROOTED:
                pass  # Fall through but skip movement
            else:
                return  # Regular stun: fully disabled

        # Update buffs
        unit.buffs = [b for b in unit.buffs if b.duration > 0]
        for buff in unit.buffs:
            buff.duration -= self.tick_rate

        # Passive item effects (Guinsoo's, Archangel's, Quicksilver, Dragon's Claw, etc.)
        for item in unit.items:
            if item.passive:
                item.passive(self, unit)

        # --- Trait combat-time effects ---

        # Shurima: heal over time
        if hasattr(unit, "_shurima_heal_per_sec"):
            shurima_last = getattr(unit, "_shurima_last_tick", -1.0)
            if self.time - shurima_last >= 1.0:
                unit._shurima_last_tick = self.time
                self.heal_unit(unit, unit._shurima_heal_per_sec, "shurima")

        # Ixtal: heal over time
        if hasattr(unit, "_ixtal_heal_per_sec"):
            ixtal_last = getattr(unit, "_ixtal_last_tick", -1.0)
            if self.time - ixtal_last >= 1.0:
                unit._ixtal_last_tick = self.time
                self.heal_unit(unit, unit._ixtal_heal_per_sec, "ixtal")

        # Warden: shield at HP thresholds
        if hasattr(unit, "_warden_shield_percent"):
            hp_pct = unit.stats.hp / unit.stats.max_hp if unit.stats.max_hp > 0 else 1.0
            if not unit._warden_first_triggered and hp_pct < unit._warden_first_threshold:
                unit._warden_first_triggered = True
                shield = unit.stats.max_hp * unit._warden_shield_percent
                unit.stats.shield += shield
                self.log_event(
                    "warden_shield", unit=unit.name, shield=round(shield, 1), threshold="first"
                )
            if not unit._warden_second_triggered and hp_pct < unit._warden_second_threshold:
                unit._warden_second_triggered = True
                shield = unit.stats.max_hp * unit._warden_shield_percent
                unit.stats.shield += shield
                self.log_event(
                    "warden_shield", unit=unit.name, shield=round(shield, 1), threshold="second"
                )

        # Slayer: bonus AD scaling with missing HP (checked once per second)
        if hasattr(unit, "_slayer_ad_increase"):
            slayer_last = getattr(unit, "_slayer_last_tick", -1.0)
            if self.time - slayer_last >= 1.0:
                unit._slayer_last_tick = self.time
                hp_pct = unit.stats.hp / unit.stats.max_hp if unit.stats.max_hp > 0 else 1.0
                missing_pct = 1.0 - hp_pct
                # AD bonus = base_ad * ad_increase * missing_hp_percent
                new_bonus = unit.base_stats.ad * unit._slayer_ad_increase * missing_pct
                old_bonus = getattr(unit, "_slayer_current_bonus", 0.0)
                unit.stats.ad += new_bonus - old_bonus
                unit._slayer_current_bonus = new_bonus

        # Juggernaut: increased DR below 50% HP
        if hasattr(unit, "_juggernaut_increased_dr"):
            hp_pct = unit.stats.hp / unit.stats.max_hp if unit.stats.max_hp > 0 else 1.0
            was_below = getattr(unit, "_juggernaut_below_50", False)
            if hp_pct < 0.5 and not was_below:
                unit._juggernaut_below_50 = True
                unit.stats.damage_reduction += unit._juggernaut_increased_dr
            elif hp_pct >= 0.5 and was_below:
                unit._juggernaut_below_50 = False
                unit.stats.damage_reduction -= unit._juggernaut_increased_dr

        # Zaun: shimmer fuse - delayed AS + durability burst
        if hasattr(unit, "_zaun_shimmer_as") and not getattr(
            unit, "_zaun_shimmer_triggered", False
        ):
            if self.time >= unit._zaun_initial_delay:
                hp_pct = unit.stats.hp / unit.stats.max_hp if unit.stats.max_hp > 0 else 1.0
                heal_threshold = getattr(unit, "_zaun_heal_threshold", 0.60)
                if hp_pct < heal_threshold:
                    unit._zaun_shimmer_triggered = True
                    unit._zaun_shimmer_active = True
                    unit._zaun_shimmer_end = self.time + unit._zaun_shimmer_duration
                    unit.stats.attack_speed += unit._zaun_shimmer_as
                    unit.stats.damage_reduction += unit._zaun_shimmer_durability
                    # Tier 5+: heal on activation
                    max_heal = getattr(unit, "_zaun_max_health_heal", 0)
                    if max_heal > 0:
                        self.heal_unit(unit, unit.stats.max_hp * max_heal, "zaun_shimmer")
                    self.log_event(
                        "zaun_shimmer_activate",
                        unit=unit.name,
                        as_bonus=unit._zaun_shimmer_as,
                        dr_bonus=unit._zaun_shimmer_durability,
                    )
        # Zaun shimmer expiry
        if getattr(unit, "_zaun_shimmer_active", False):
            if self.time >= unit._zaun_shimmer_end:
                unit._zaun_shimmer_active = False
                unit.stats.attack_speed -= unit._zaun_shimmer_as
                unit.stats.damage_reduction -= unit._zaun_shimmer_durability
                self.log_event("zaun_shimmer_expire", unit=unit.name)

        # Quickstriker: bonus AS based on target's missing HP (checked once per second)
        if hasattr(unit, "_quickstriker_min_as") and unit.target and unit.target.is_alive:
            qs_last = getattr(unit, "_qs_last_tick", -1.0)
            if self.time - qs_last >= 1.0:
                unit._qs_last_tick = self.time
                t_hp_pct = (
                    unit.target.stats.hp / unit.target.stats.max_hp
                    if unit.target.stats.max_hp > 0
                    else 1.0
                )
                t_missing = 1.0 - t_hp_pct
                new_bonus = (
                    unit._quickstriker_min_as
                    + (unit._quickstriker_max_as - unit._quickstriker_min_as) * t_missing
                )
                old_bonus = getattr(unit, "_qs_current_bonus", 0.0)
                unit.stats.attack_speed += new_bonus - old_bonus
                unit._qs_current_bonus = new_bonus

        # Find/update target
        if not unit.target or not unit.target.is_alive:
            unit.target = self.find_target(unit, enemies)

        if not unit.target:
            unit.state = UnitState.IDLE
            return

        # Check if in range
        in_range = self.can_attack(unit, unit.target)

        # Movement if not in range (rooted units cannot move)
        if not in_range:
            if unit.state == UnitState.ROOTED:
                return  # Rooted: can't move to get in range, just wait
            unit.state = UnitState.MOVING

            # Move towards target (simplified - one hex per 0.5s)
            if unit.attack_cooldown <= 0:
                # Find adjacent hex to target that's in range
                target_neighbors = HexGrid._NEIGHBOR_LUT[unit.target.position]
                occupied = self.get_occupied_hexes()
                dist_lut = HexGrid._DISTANCE_LUT[unit.position]

                best_spot = None
                best_dist = 999
                for n in target_neighbors:
                    if n not in occupied:
                        d = dist_lut[n]
                        if d < best_dist:
                            best_dist = d
                            best_spot = n

                if best_spot is not None:
                    self.move_unit_towards(unit, best_spot)

                unit.attack_cooldown = self.HEX_MOVE_TIME
            else:
                unit.attack_cooldown -= self.tick_rate
            return

        # Check if current target is still valid (alive and targetable)
        if unit.target and (not unit.target.is_alive or not unit.target.is_targetable):
            # Target died or became untargetable - find new target
            unit.target = self.find_target(unit, enemies)
            if not unit.target:
                unit.state = UnitState.IDLE
                return

        # In range - check for ability cast
        if unit.stats.mana >= unit.stats.max_mana and unit.ability:
            unit.state = UnitState.CASTING
            self.cast_ability(unit, enemies, allies)
            # Allow champion-specific handlers to override the cast lockout
            if getattr(unit, "_custom_cast_time", False):
                unit._custom_cast_time = False
            else:
                unit.attack_cooldown = unit.ability.cast_time
            return

        # Auto attack
        unit.state = UnitState.ATTACKING
        unit.attack_cooldown -= self.tick_rate

        if unit.attack_cooldown <= 0:
            # Enforce attack speed hard cap
            effective_as = min(unit.stats.attack_speed, self.ATTACK_SPEED_CAP)
            attack_interval = 1.0 / effective_as
            unit.attack_cooldown = attack_interval
            self.process_attack(unit)

    def tick(self):
        """Process one simulation tick."""
        self.time += self.tick_rate
        tick_rate = self.tick_rate  # Local var for tight loops

        # Refresh cached alive lists only when a unit has died
        if self._alive_dirty:
            self._alive_team0 = [u for u in self._alive_team0 if u.is_alive]
            self._alive_team1 = [u for u in self._alive_team1 if u.is_alive]
            self._all_alive = self._alive_team0 + self._alive_team1
            self._alive_dirty = False

        team0 = self._alive_team0
        team1 = self._alive_team1
        all_alive = self._all_alive

        # Process DOT effects on all alive units
        for unit in all_alive:
            if not unit.dot_effects:
                continue
            expired_any = False
            for dot in unit.dot_effects:
                dot.remaining_duration -= tick_rate
                dot.time_since_last_tick += tick_rate
                if dot.time_since_last_tick >= dot.tick_interval:
                    dot.time_since_last_tick -= dot.tick_interval
                    if unit.is_alive:
                        self.apply_damage(
                            dot.source_unit,
                            unit,
                            dot.damage_per_tick,
                            dot.damage_type,
                            dot.source_name,
                        )
                if dot.remaining_duration <= 0:
                    expired_any = True
            if expired_any:
                unit.dot_effects = [d for d in unit.dot_effects if d.remaining_duration > 0]

        # Expire sunder/shred debuffs and restore armor/MR
        current_time = self.time
        logging_on = self.logging_enabled
        for unit in all_alive:
            if not unit.is_alive:
                continue
            sunder = getattr(unit, "_sunder_stacks", None)
            if sunder:
                expired_any = False
                for reduction, expiry, src in sunder:
                    if current_time >= expiry:
                        unit.stats.armor += reduction
                        expired_any = True
                        if logging_on:
                            self.log_event(
                                "sunder_expired",
                                target=unit.name,
                                restored=round(reduction, 1),
                                source=src,
                            )
                if expired_any:
                    unit._sunder_stacks = [(r, e, s) for r, e, s in sunder if current_time < e]
            shred = getattr(unit, "_shred_stacks", None)
            if shred:
                expired_any = False
                for reduction, expiry, src in shred:
                    if current_time >= expiry:
                        unit.stats.magic_resist += reduction
                        expired_any = True
                        if logging_on:
                            self.log_event(
                                "shred_expired",
                                target=unit.name,
                                restored=round(reduction, 1),
                                source=src,
                            )
                if expired_any:
                    unit._shred_stacks = [(r, e, s) for r, e, s in shred if current_time < e]

        # Piltover module fire at 8 seconds
        if self._piltover_data and current_time >= 8.0:
            for team_id, pdata in self._piltover_data.items():
                if not pdata["fired"]:
                    pdata["fired"] = True
                    self._fire_piltover_module(pdata, team0, team1)

        # Check Noxus Atakhan summoning (only when Noxus is active)
        if self._has_noxus:
            self._check_noxus_atakhan_summon(team0, team1)
            self._check_atakhan_ruin()

        # Process units in random order to avoid bias.
        # Shuffle every 3rd tick (~0.1s game time) to reduce RNG overhead
        # while maintaining fairness at gameplay-relevant granularity.
        self._tick_count += 1
        if self._tick_count % 3 == 0:
            random.shuffle(all_alive)

        for unit in all_alive:
            enemies = team1 if unit.team == 0 else team0
            allies = team0 if unit.team == 0 else team1
            self.process_unit_tick(unit, enemies, allies)

    def _fire_piltover_module(self, pdata: Dict, team0: List[Unit], team1: List[Unit]):
        """Apply Piltover module effects at 8 seconds into combat."""
        module = pdata["module"]
        team = [u for u in pdata["team"] if u.is_alive]
        piltover_units = [u for u in pdata["piltover_units"] if u.is_alive]
        team_id = pdata.get("team", [None])[0].team if team else 0
        enemies = team1 if team_id == 0 else team0

        self.log_event("piltover_module_fire", module=module)

        if module == "BlastShield":
            for u in team:
                shield = u.stats.max_hp * 0.18
                self.apply_shield(u, shield, "piltover_blast_shield")

        elif module == "ContinuumCogs":
            for u in team:
                u.stats.ap += 15

        elif module == "EMP":
            for e in enemies:
                if e.is_alive:
                    e.stats.max_mana += 15

        elif module == "KineticBarrier":
            for u in piltover_units:
                u.stats.armor += 65
                u.stats.magic_resist += 30

        elif module == "OverclockedCapacitors":
            for u in team:
                u.stats.attack_speed += 0.25

        elif module == "AccelerationGate":
            # Mark Piltover units for mana restore after cast
            for u in piltover_units:
                u._piltover_accel_gate = True

        elif module == "ArmorNullifier":
            for u in piltover_units:
                u.stats.damage_amp += 0.25

        elif module == "GigantificationRay":
            for u in piltover_units:
                hp_bonus = u.stats.max_hp * 0.28
                u.stats.hp += hp_bonus
                u.stats.max_hp += hp_bonus

        elif module == "MagnetronCoil":
            for u in piltover_units:
                u.stats.damage_amp += 0.18

        elif module == "MomentumDrive":
            # Cleanse CC and grant tenacity (50% stun duration reduction)
            for u in team:
                if u.state == UnitState.STUNNED:
                    u.state = UnitState.IDLE
                    u.stun_duration = 0
                u._tenacity = 0.50

        elif module == "TunedOscillator":
            # Increase healing/shielding by 28% (mark for heal_unit to check)
            for u in team:
                u._healing_amp = getattr(u, "_healing_amp", 0) + 0.28

        elif module == "ElectricalOverload":
            for e in enemies:
                if e.is_alive:
                    dmg = 100 + e.stats.max_hp * 0.10
                    self.apply_damage(None, e, dmg, DamageType.TRUE, "piltover_electrical_overload")

        elif module == "90CaliberNets":
            # Stun 3 highest DPS enemies for 2s
            alive_enemies = [e for e in enemies if e.is_alive]
            alive_enemies.sort(key=lambda e: e.total_damage_dealt, reverse=True)
            for e in alive_enemies[:3]:
                e.state = UnitState.STUNNED
                e.stun_duration = 2.0

    def _check_noxus_atakhan_summon(self, team0: List[Unit], team1: List[Unit]):
        """Check if enemy team has lost enough HP to trigger Atakhan summon.

        For each team with Noxus active, check if the ENEMY team has lost
        15% of their total starting HP. If so, summon Atakhan.
        """
        noxus_data = getattr(self, "_noxus_team_data", {})
        if not noxus_data:
            return

        for team_id, data in noxus_data.items():
            if data["summoned"]:
                continue

            # Enemy team is the opposite
            enemy_team = team1 if team_id == 0 else team0
            ally_team = team0 if team_id == 0 else team1

            # Calculate enemy total HP loss
            if "_enemy_starting_hp" not in data:
                # Cache starting HP on first check (including dead enemies)
                all_enemies = [u for u in self.units if u.team != team_id]
                total_max_hp = sum(u.stats.max_hp for u in all_enemies)
                data["_enemy_starting_hp"] = total_max_hp

            starting_hp = data.get("_enemy_starting_hp", 0)
            if starting_hp <= 0:
                continue

            # Current enemy HP (alive units only)
            current_hp = sum(u.stats.hp for u in self.units if u.team != team_id and u.is_alive)
            hp_lost_pct = (starting_hp - current_hp) / starting_hp

            if hp_lost_pct >= data["hp_trigger"]:
                # Summon Atakhan!
                self._summon_atakhan(team_id, data, ally_team)
                data["summoned"] = True

    def _summon_atakhan(self, team_id: int, noxus_data: Dict, ally_team: List[Unit]):
        """Summon Atakhan onto the board for the given team.

        Creates Atakhan as a combat unit with stats scaled by:
        - Total Noxian star levels -> Atakhan's star level
        - Noxus count -> ability tier (3/5/7/10)
        """
        atakhan_star = noxus_data["atakhan_star"]
        noxus_count = noxus_data["count"]
        total_stars = noxus_data["total_stars"]

        # Get Atakhan stats for this star level
        stats = self.trait_manager.ATAKHAN_STATS.get(
            min(atakhan_star, 4), self.trait_manager.ATAKHAN_STATS[1]
        )

        # Calculate HP with per-star scaling
        base_hp = stats["hp"] + stats["per_star_hp"] * total_stars
        base_ad = stats["ad"] * (1.0 + stats["per_star_ad_pct"] * total_stars)
        base_ap_pct = stats["per_star_ap_pct"] * total_stars

        atakhan_stats = CombatStats(
            hp=base_hp,
            max_hp=base_hp,
            ad=base_ad,
            ap=base_ap_pct * 100,  # AP as flat value
            attack_speed=stats["as"],
            armor=stats["armor"],
            magic_resist=stats["mr"],
            range=1,
            mana=40 if atakhan_star >= 3 else 0,
            max_mana=85 if atakhan_star >= 3 else 0,
            crit_chance=0.25,
            crit_multiplier=1.4,
            omnivamp=stats["omnivamp"],
        )

        # Find a position to spawn (left side of board, behind allies)
        spawn_pos = self._find_atakhan_spawn(team_id, ally_team)

        atakhan = Unit(
            name="Atakhan",
            api_name="TFT16_Atakhan",
            star_level=atakhan_star,
            stats=atakhan_stats,
            base_stats=deepcopy(atakhan_stats),
            position=spawn_pos,
            team=team_id,
            traits=[],
            ability=Ability(
                name="Punish the Unworthy",
                ability_type=AbilityType.DAMAGE,
                damage_type=DamageType.MAGIC,
                targeting=TargetingType.CURRENT_TARGET,
                base_damage={1: stats["cleave_damage"]},
                ap_scaling=1.0,
                cast_time=0.5,
                aoe_radius=1,
                effects={
                    "noxus_count": noxus_count,
                    "damage_amp": stats["damage_amp"],
                    "dot_damage": stats["dot_damage"],
                    "dot_duration": stats["dot_duration"],
                },
            ),
            role="APTank",
            attack_windup=0.4,
        )

        # Mark as Atakhan for special handling
        atakhan._is_atakhan = True
        atakhan._atakhan_summon_time = self.time
        atakhan._atakhan_noxus_count = noxus_count
        atakhan._atakhan_ruin_timer = noxus_data["ruin_timer"]
        atakhan._atakhan_attacks_since_cleave = 0

        # Add to combat
        self.units.append(atakhan)
        ally_team.append(atakhan)
        self._invalidate_occupied_cache()

        # At 5+ Noxus: grant Noxians damage amp while Atakhan is alive
        if noxus_count >= 5 and stats["damage_amp"] > 0:
            for unit in ally_team:
                if "Noxus" in unit.traits:
                    unit.stats.damage_amp += stats["damage_amp"]

        self.log_event(
            "atakhan_summoned",
            team=team_id,
            star=atakhan_star,
            noxus_count=noxus_count,
            total_stars=total_stars,
            hp=round(base_hp),
            ad=round(base_ad, 1),
        )

    def _find_atakhan_spawn(self, team_id: int, ally_team: List[Unit]) -> Tuple[int, int]:
        """Find a spawn position for Atakhan (left side of board)."""
        occupied = {u.position for u in self.units if u.is_alive}

        # Atakhan spawns from the left side — prefer back row for the team
        if team_id == 0:
            preferred_rows = [3, 2, 1, 0]  # Back rows for team 0
        else:
            preferred_rows = [0, 1, 2, 3]  # Back rows for team 1

        for row in preferred_rows:
            for col in [0, 1, 2, 3, 4, 5, 6]:
                pos = (row, col)
                if pos not in occupied:
                    return pos

        # Fallback: just find any open position
        for row in range(4):
            for col in range(7):
                if (row, col) not in occupied:
                    return (row, col)
        return (0, 0)  # Absolute fallback

    def _check_atakhan_ruin(self):
        """Check if a 4-star Atakhan at 10 Noxus should BRING RUIN.

        At 10 Noxus with 4-star Atakhan, after 10 seconds from summoning,
        Atakhan devours ALL enemy units.
        """
        for unit in self.units:
            if not (unit.is_alive and getattr(unit, "_is_atakhan", False)):
                continue

            noxus_count = getattr(unit, "_atakhan_noxus_count", 0)
            if noxus_count < 10 or unit.star_level < 4:
                continue

            summon_time = getattr(unit, "_atakhan_summon_time", 0)
            ruin_timer = getattr(unit, "_atakhan_ruin_timer", 10)

            if self.time - summon_time >= ruin_timer:
                if not getattr(unit, "_ruin_triggered", False):
                    unit._ruin_triggered = True
                    # BRING RUIN: kill all enemy units
                    enemies = [u for u in self.units if u.team != unit.team and u.is_alive]
                    for enemy in enemies:
                        enemy.stats.hp = 0
                        enemy.is_alive = False
                        enemy.state = UnitState.DEAD
                    self._alive_dirty = True
                    self.log_event(
                        "atakhan_bring_ruin", team=unit.team, enemies_devoured=len(enemies)
                    )

    def _count_traits(self, team: List[Unit]) -> Dict[str, int]:
        """Count trait occurrences for a team.

        Args:
            team: List of units

        Returns:
            Dict mapping trait name to count
        """
        trait_counts = {}
        for unit in team:
            for trait in unit.traits:
                trait_counts[trait] = trait_counts.get(trait, 0) + 1
        return trait_counts

    def process_round_start(self, team: List[Unit]):
        """Process start of round for trait mechanics.

        Called at the beginning of each round to:
        - Set per-combat trait counts for combat-time triggers
        - Check Piltover module availability
        """
        team_id = team[0].team if team else 0

        # Count trait occurrences
        trait_counts = {}
        for unit in team:
            for trait in unit.traits:
                trait_counts[trait] = trait_counts.get(trait, 0) + 1

        # Log trait info
        self.log_event("round_start", trait_counts=trait_counts)

        # Bilgewater count is used for combat-time takedown rewards (currency stored in game layer).
        bilgewater_count = trait_counts.get("Bilgewater", 0)
        self.trait_manager.set_bilgewater_count(team_id, bilgewater_count)

        # Piltover module selection and storage
        piltover_count = trait_counts.get("Piltover", 0)
        if piltover_count >= 2:
            available_modules = self.trait_manager.assign_piltover_modules(piltover_count)
            if available_modules:
                selected = random.choice(available_modules)
                if not hasattr(self, "_piltover_data"):
                    self._piltover_data = {}
                piltover_units = [u for u in team if "Piltover" in u.traits]
                self._piltover_data[team_id] = {
                    "module": selected,
                    "fired": False,
                    "team": team,
                    "piltover_units": piltover_units,
                    "count": piltover_count,
                }
                self.log_event(
                    "piltover_module_selected", count=piltover_count, module=selected, team=team_id
                )

        # Shadow Isles soul collection setup
        shadow_isles_count = trait_counts.get("Shadow Isles", 0)
        self.trait_manager.set_shadow_isles_count(team_id, shadow_isles_count)
        if shadow_isles_count >= 2:
            shadow_isles_units = [u for u in team if "Shadow Isles" in u.traits]
            self.log_event(
                "shadow_isles_setup",
                count=shadow_isles_count,
                units=[u.name for u in shadow_isles_units],
                stat_bonus=self.trait_manager.get_shadow_isles_stat_bonus(team_id),
            )

    def _apply_combat_start_items(self, all_units: List[Unit]):
        """Apply combat-start item effects for all units."""
        try:
            from .item_effects import ITEM_ON_COMBAT_START, _resolve_item_name
        except ImportError:
            return
        for unit in all_units:
            if not unit.is_alive:
                continue
            for item in unit.items:
                handler = ITEM_ON_COMBAT_START.get(item.name) or ITEM_ON_COMBAT_START.get(
                    _resolve_item_name(item.name)
                )
                if handler:
                    handler(self, unit, all_units)

    def run_combat(
        self,
        team0: List[Unit],
        team1: List[Unit],
        max_time: float = 60.0,
        verbose: bool = False,
        team0_augments: List[str] = None,
        team1_augments: List[str] = None,
        seed: int = None,
    ) -> Dict:
        """Run a full combat simulation.

        Args:
            team0: List of units for team 0
            team1: List of units for team 1
            max_time: Maximum combat duration in seconds
            verbose: Include detailed combat log in results
            team0_augments: List of augment names/apiNames for team 0
            team1_augments: List of augment names/apiNames for team 1
            seed: Random seed for deterministic simulation. If None, uses current RNG state.
        """
        saved_random_state = None
        if seed is not None:
            saved_random_state = random.getstate()
            random.seed(seed)

        try:
            # Reset state
            self.time = 0.0
            self.combat_log = []
            self.units = team0 + team1
            self.projectiles = []
            self._debug_takedowns = []

            # Reset Shadow Isles souls for new combat
            self.trait_manager.reset_shadow_isles()

            # Reset Noxus Atakhan state for new combat
            self._noxus_team_data = {}

            # Reset Piltover module state for new combat
            self._piltover_data = {}

            # Reset augment manager for new combat
            self.augment_manager.reset()

            # Process round start for traits (both teams)
            self.process_round_start(team0)
            self.process_round_start(team1)

            # Apply stat-buffing traits at combat start
            team0_traits = self._count_traits(team0)
            team1_traits = self._count_traits(team1)
            self.trait_manager.apply_stat_traits(team0, team0_traits, enemy_team=team1)
            self.trait_manager.apply_stat_traits(team1, team1_traits, enemy_team=team0)

            # Shadow Isles stat bonus should be applied once per team (post-traits)
            team0_id = team0[0].team if team0 else 0
            team1_id = team1[0].team if team1 else 1
            self.trait_manager.apply_shadow_isles_stats(team0_id, team0)
            self.trait_manager.apply_shadow_isles_stats(team1_id, team1)

            # Apply augments if provided (after traits so they can stack)
            if team0_augments:
                self.augment_manager.set_augments(team0_augments)
                self.augment_manager.apply_augments(
                    team0,
                    team0_traits,
                    round_persistent_player=self._round_persistent_players.get(0),
                )
                self.log_event("augments_applied", team=0, augments=team0_augments)

            if team1_augments:
                self.augment_manager.set_augments(team1_augments)
                self.augment_manager.apply_augments(
                    team1,
                    team1_traits,
                    round_persistent_player=self._round_persistent_players.get(1),
                )
                self.log_event("augments_applied", team=1, augments=team1_augments)

            # Cache enemy starting HP for Noxus Atakhan trigger (after all buffs)
            noxus_data = getattr(self, "_noxus_team_data", {})
            for team_id, data in noxus_data.items():
                enemy_hp = sum(u.stats.max_hp for u in self.units if u.team != team_id)
                data["_enemy_starting_hp"] = enemy_hp

            # Initialize cached alive lists for tick() optimization
            self._alive_team0 = list(team0)
            self._alive_team1 = list(team1)
            self._all_alive = self._alive_team0 + self._alive_team1
            self._alive_dirty = False  # Set True when a unit dies
            self._tick_count = 0  # Counter for shuffle frequency optimization
            self._occupied_dirty = True  # Rebuild occupied hex cache
            self._has_noxus = bool(noxus_data)  # Skip Atakhan checks when no Noxus

            # Cache units with Ionic Spark for fast ability-cast reaction checks
            self._ionic_spark_units = [u for u in self.units if u._has_ionic_spark]

            # Apply combat-start item effects (Crownguard, Quicksilver, SteadfastHeart, etc.)
            self._apply_combat_start_items(team0 + team1)

            # Combat loop
            while self.time < max_time:
                if not self._alive_team0 or not self._alive_team1:
                    break

                self.tick()

            # Determine winner
            team0_survivors = [u for u in team0 if u.is_alive]
            team1_survivors = [u for u in team1 if u.is_alive]

            if team0_survivors and not team1_survivors:
                winner = 0
            elif team1_survivors and not team0_survivors:
                winner = 1
            else:
                team0_hp = sum(u.stats.hp for u in team0_survivors)
                team1_hp = sum(u.stats.hp for u in team1_survivors)
                winner = 0 if team0_hp >= team1_hp else 1

            results = {
                "winner": winner,
                "combat_time": round(self.time, 2),
                "team0_survivors": len(team0_survivors),
                "team1_survivors": len(team1_survivors),
                "team0_total_damage": round(sum(u.total_damage_dealt for u in team0), 1),
                "team1_total_damage": round(sum(u.total_damage_dealt for u in team1), 1),
                "total_damage_dealt": {
                    "team0": round(sum(u.total_damage_dealt for u in team0), 1),
                    "team1": round(sum(u.total_damage_dealt for u in team1), 1),
                },
                "team0_abilities_cast": sum(u.abilities_cast for u in team0),
                "team1_abilities_cast": sum(u.abilities_cast for u in team1),
                "combat_log": self.combat_log if verbose else [],
                "debug_takedowns": list(self._debug_takedowns),
            }

            return results
        finally:
            if saved_random_state is not None:
                random.setstate(saved_random_state)

    def _next_event_dt(self, all_alive: List[Unit]) -> float:
        """Compute the time delta to the next meaningful event.

        Scans all alive units for the minimum cooldown remaining, then
        clamps to the tick rate so we never skip past a partial tick.
        Returns a delta >= tick_rate.
        """
        dt = 999.0
        tick = self.tick_rate

        for u in all_alive:
            # Attack cooldown
            if u.attack_cooldown > tick:
                dt = min(dt, u.attack_cooldown)
            else:
                return tick  # At least one unit can act now

            # Stun duration
            if u.stun_duration > tick:
                dt = min(dt, u.stun_duration)
            else:
                if u.stun_duration > 0:
                    return tick

            # Untargetable duration
            if not u.is_targetable and u.untargetable_duration > tick:
                dt = min(dt, u.untargetable_duration)
            elif not u.is_targetable:
                return tick

            # DOT ticks
            for dot in u.dot_effects:
                remaining_to_tick = dot.tick_interval - dot.time_since_last_tick
                if remaining_to_tick <= tick:
                    return tick
                dt = min(dt, remaining_to_tick)

        # Piltover fires at 8s
        if self._piltover_data:
            for pdata in self._piltover_data.values():
                if not pdata["fired"]:
                    time_to_8 = 8.0 - self.time
                    if time_to_8 <= tick:
                        return tick
                    dt = min(dt, time_to_8)

        # Never skip past tick_rate granularity — snap to tick boundary
        # Round down to nearest tick multiple
        if dt > tick:
            dt = max(tick, (dt // tick) * tick)

        return dt

    def run_combat_adaptive_tick(
        self,
        team0: List[Unit],
        team1: List[Unit],
        max_time: float = 60.0,
        team0_augments: List[str] = None,
        team1_augments: List[str] = None,
        seed: int = None,
    ) -> Dict:
        """Run combat with adaptive tick skipping (experimental).

        Skips some idle ticks by fast-forwarding a subset of timers.
        Not guaranteed to exactly match run_combat() because many effects
        are evaluated via per-tick hooks.
        Logging is always disabled for this fast path.
        """
        saved_logging = self.logging_enabled
        self.logging_enabled = False
        saved_random_state = None

        try:
            # Use the same initialization as run_combat
            if seed is not None:
                saved_random_state = random.getstate()
                random.seed(seed)

            self.time = 0.0
            self.combat_log = []
            self.units = team0 + team1
            self.projectiles = []
            self._debug_takedowns = []
            self.trait_manager.reset_shadow_isles()
            self._noxus_team_data = {}
            self._piltover_data = {}
            self.augment_manager.reset()

            self.process_round_start(team0)
            self.process_round_start(team1)

            team0_traits = self._count_traits(team0)
            team1_traits = self._count_traits(team1)
            self.trait_manager.apply_stat_traits(team0, team0_traits, enemy_team=team1)
            self.trait_manager.apply_stat_traits(team1, team1_traits, enemy_team=team0)

            team0_id = team0[0].team if team0 else 0
            team1_id = team1[0].team if team1 else 1
            self.trait_manager.apply_shadow_isles_stats(team0_id, team0)
            self.trait_manager.apply_shadow_isles_stats(team1_id, team1)

            if team0_augments:
                self.augment_manager.set_augments(team0_augments)
                self.augment_manager.apply_augments(
                    team0,
                    team0_traits,
                    round_persistent_player=self._round_persistent_players.get(0),
                )
            if team1_augments:
                self.augment_manager.set_augments(team1_augments)
                self.augment_manager.apply_augments(
                    team1,
                    team1_traits,
                    round_persistent_player=self._round_persistent_players.get(1),
                )

            noxus_data = getattr(self, "_noxus_team_data", {})
            for team_id, data in noxus_data.items():
                enemy_hp = sum(u.stats.max_hp for u in self.units if u.team != team_id)
                data["_enemy_starting_hp"] = enemy_hp

            self._alive_team0 = list(team0)
            self._alive_team1 = list(team1)
            self._all_alive = self._alive_team0 + self._alive_team1
            self._alive_dirty = False
            self._tick_count = 0
            self._occupied_dirty = True
            self._has_noxus = bool(noxus_data)
            self._ionic_spark_units = [u for u in self.units if u._has_ionic_spark]

            self._apply_combat_start_items(team0 + team1)

            # Adaptive tick loop
            while self.time < max_time:
                if not self._alive_team0 or not self._alive_team1:
                    break

                # Compute time to next event and multi-step if possible
                all_alive = self._alive_team0 + self._alive_team1
                dt = self._next_event_dt(all_alive)

                # If we can skip ahead, fast-forward cooldowns
                if dt > self.tick_rate:
                    skip = dt - self.tick_rate
                    for u in all_alive:
                        if u.attack_cooldown > 0:
                            u.attack_cooldown -= skip
                        if u.stun_duration > 0:
                            u.stun_duration -= skip
                        if not u.is_targetable and u.untargetable_duration > 0:
                            u.untargetable_duration -= skip
                        for dot in u.dot_effects:
                            dot.remaining_duration -= skip
                            dot.time_since_last_tick += skip
                    self.time += skip

                self.tick()

            # Build result (same as run_combat)
            team0_survivors = [u for u in team0 if u.is_alive]
            team1_survivors = [u for u in team1 if u.is_alive]

            if team0_survivors and not team1_survivors:
                winner = 0
            elif team1_survivors and not team0_survivors:
                winner = 1
            else:
                team0_hp = sum(u.stats.hp for u in team0_survivors)
                team1_hp = sum(u.stats.hp for u in team1_survivors)
                winner = 0 if team0_hp >= team1_hp else 1

            return {
                "winner": winner,
                "combat_time": round(self.time, 2),
                "team0_survivors": len(team0_survivors),
                "team1_survivors": len(team1_survivors),
                "team0_total_damage": round(sum(u.total_damage_dealt for u in team0), 1),
                "team1_total_damage": round(sum(u.total_damage_dealt for u in team1), 1),
                "total_damage_dealt": {
                    "team0": round(sum(u.total_damage_dealt for u in team0), 1),
                    "team1": round(sum(u.total_damage_dealt for u in team1), 1),
                },
                "team0_abilities_cast": sum(u.abilities_cast for u in team0),
                "team1_abilities_cast": sum(u.abilities_cast for u in team1),
                "combat_log": [],
                "debug_takedowns": list(self._debug_takedowns),
            }
        finally:
            if saved_random_state is not None:
                random.setstate(saved_random_state)
            self.logging_enabled = saved_logging

    def simulate_1v1(
        self,
        champ1: str,
        champ2: str,
        star1: int = 1,
        star2: int = 1,
        items1: List[str] = None,
        items2: List[str] = None,
        augments1: List[str] = None,
        augments2: List[str] = None,
        num_simulations: int = 100,
        seed: int = None,
    ) -> Dict:
        """Simulate multiple 1v1 combats between two champions.

        Args:
            champ1: API name of first champion
            champ2: API name of second champion
            star1: Star level for champ1 (1-3)
            star2: Star level for champ2 (1-3)
            items1: List of item names for champ1
            items2: List of item names for champ2
            augments1: List of augment names for team 1
            augments2: List of augment names for team 2
            num_simulations: Number of simulations to run
            seed: Base random seed for deterministic simulations. Each sim uses seed+i.
        """
        wins = {champ1: 0, champ2: 0}
        total_damage = {champ1: 0.0, champ2: 0.0}
        abilities_cast = {champ1: 0, champ2: 0}
        combat_times = []

        for i in range(num_simulations):
            # Set seed for this specific simulation if base seed provided
            sim_seed = (seed + i) if seed is not None else None
            # Place units facing each other
            unit1 = self.create_unit(champ1, star1, (0, 3), 0, items1)
            unit2 = self.create_unit(champ2, star2, (3, 3), 1, items2)

            if not unit1 or not unit2:
                return {"error": "Invalid champion names"}

            result = self.run_combat(
                [unit1], [unit2], team0_augments=augments1, team1_augments=augments2, seed=sim_seed
            )

            if result["winner"] == 0:
                wins[champ1] += 1
            else:
                wins[champ2] += 1

            total_damage[champ1] += result["team0_total_damage"]
            total_damage[champ2] += result["team1_total_damage"]
            abilities_cast[champ1] += result["team0_abilities_cast"]
            abilities_cast[champ2] += result["team1_abilities_cast"]
            combat_times.append(result["combat_time"])

        return {
            "simulations": num_simulations,
            "win_rate": {
                champ1: round(wins[champ1] / num_simulations * 100, 1),
                champ2: round(wins[champ2] / num_simulations * 100, 1),
            },
            "avg_damage": {
                champ1: round(total_damage[champ1] / num_simulations, 1),
                champ2: round(total_damage[champ2] / num_simulations, 1),
            },
            "avg_abilities_cast": {
                champ1: round(abilities_cast[champ1] / num_simulations, 2),
                champ2: round(abilities_cast[champ2] / num_simulations, 2),
            },
            "avg_combat_time": round(sum(combat_times) / len(combat_times), 2),
        }


# =============================================================================
# DEMO
# =============================================================================


def main():
    """Demo the combat engine."""
    engine = CombatEngine()

    print("=" * 60)
    print("TFT Combat Simulator v2")
    print("=" * 60)
    print(f"\nLoaded {len(engine.champions)} champions")
    print(f"Available items: {len(ItemDatabase.ITEMS)}")

    # Debug: Show some champion stats including roles
    print("\n--- Champion Debug Info ---")
    for name in ["TFT16_Kaisa", "TFT16_Draven", "TFT16_Jinx", "TFT16_Renekton"]:
        unit = engine.create_unit(name, 2, (0, 0), 0)
        if unit:
            role_type = "Frontline" if unit.is_frontline else "Backline"
            print(
                f"{unit.name} ({unit.role}, {role_type}): HP={unit.stats.hp:.0f}, AD={unit.stats.ad:.0f}, "
                f"AS={unit.stats.attack_speed:.2f}, Range={unit.stats.range}, Mana={unit.stats.mana}/{unit.stats.max_mana}"
            )

    # 1v1: Same cost comparison
    print("\n" + "-" * 60)
    print("1v1: Draven (2*) vs Tristana (2*) - Both 3-cost ADCs")
    print("-" * 60)

    result = engine.simulate_1v1(
        "TFT16_Draven", "TFT16_Tristana", star1=2, star2=2, num_simulations=500
    )

    print(f"Simulations: {result['simulations']}")
    for champ, rate in result["win_rate"].items():
        print(f"  {champ}: {rate}% win rate")
    print(f"Average Combat Time: {result['avg_combat_time']}s")
    print("Average Abilities Cast:")
    for champ, casts in result["avg_abilities_cast"].items():
        print(f"  {champ}: {casts}")

    # 1v1: Tank vs Tank
    print("\n" + "-" * 60)
    print("1v1: Renekton (2*) vs Leona (2*) - Frontline clash")
    print("-" * 60)

    result = engine.simulate_1v1(
        "TFT16_Renekton", "TFT16_Leona", star1=2, star2=2, num_simulations=500
    )

    print(f"Simulations: {result['simulations']}")
    for champ, rate in result["win_rate"].items():
        print(f"  {champ}: {rate}% win rate")
    print(f"Average Combat Time: {result['avg_combat_time']}s")

    # 1v1 with items
    print("\n" + "-" * 60)
    print("1v1: Jinx (2*) + IE/LW vs Renekton (2*) + Warmogs/Bramble")
    print("-" * 60)

    result = engine.simulate_1v1(
        "TFT16_Jinx",
        "TFT16_Renekton",
        star1=2,
        star2=2,
        items1=["InfinityEdge", "LastWhisper"],
        items2=["WarmogsArmor", "BrambleVest"],
        num_simulations=500,
    )

    print(f"Simulations: {result['simulations']}")
    for champ, rate in result["win_rate"].items():
        print(f"  {champ}: {rate}% win rate")
    print("Average Damage:")
    for champ, dmg in result["avg_damage"].items():
        print(f"  {champ}: {dmg}")

    # Team fight
    print("\n" + "-" * 60)
    print("Team Fight: 3v3")
    print("-" * 60)

    team0 = [
        engine.create_unit("TFT16_Jinx", 2, (0, 2), 0, ["InfinityEdge"]),
        engine.create_unit("TFT16_Lux", 2, (0, 3), 0, ["RabadonsDeathcap"]),
        engine.create_unit("TFT16_Leona", 2, (1, 3), 0, ["WarmogsArmor"]),
    ]

    team1 = [
        engine.create_unit("TFT16_Draven", 2, (3, 2), 1, ["Bloodthirster"]),
        engine.create_unit("TFT16_Ahri", 2, (3, 3), 1, ["SpearOfShojin"]),
        engine.create_unit("TFT16_Braum", 2, (2, 3), 1, ["GargoyleStoneplate"]),
    ]

    result = engine.run_combat(team0, team1)

    print(f"Winner: Team {result['winner']}")
    print(f"Combat Time: {result['combat_time']}s")
    print(f"Team 0 Survivors: {result['team0_survivors']}")
    print(f"Team 1 Survivors: {result['team1_survivors']}")
    print(f"Team 0 Total Damage: {result['team0_total_damage']}")
    print(f"Team 1 Total Damage: {result['team1_total_damage']}")

    # Show item impact
    print("\n" + "-" * 60)
    print("Item Impact Test: Draven with vs without IE")
    print("-" * 60)

    result_no_items = engine.simulate_1v1(
        "TFT16_Draven", "TFT16_Leona", star1=2, star2=2, num_simulations=300
    )

    result_with_ie = engine.simulate_1v1(
        "TFT16_Draven",
        "TFT16_Leona",
        star1=2,
        star2=2,
        items1=["InfinityEdge"],
        num_simulations=300,
    )

    print(f"No items: Draven {result_no_items['win_rate']['TFT16_Draven']}% win")
    print(f"With IE:  Draven {result_with_ie['win_rate']['TFT16_Draven']}% win")

    # Test Jinx form swap (minigun -> rockets after 18 attacks)
    print("\n" + "-" * 60)
    print("Jinx Form Swap Test: Long fight to see rocket transition")
    print("-" * 60)

    # Jinx vs high HP tank - should see rocket form activate
    result = engine.simulate_1v1(
        "TFT16_Jinx",
        "TFT16_Renekton",
        star1=2,
        star2=2,
        items1=["RedBuff"],  # AS boost helps reach rocket form
        items2=["WarmogsArmor", "DragonsClaw"],  # Very tanky
        num_simulations=100,
    )

    print(f"Jinx win rate: {result['win_rate']['TFT16_Jinx']}%")
    print(f"Average combat time: {result['avg_combat_time']}s (longer = more rockets)")
    print(f"Jinx avg damage: {result['avg_damage']['TFT16_Jinx']}")

    # Tank targeting test
    print("\n" + "-" * 60)
    print("Tank Targeting Test: Frontline should draw aggro")
    print("-" * 60)

    # Setup: Draven (backline) behind Braum (frontline) vs enemy
    team_with_tank = [
        engine.create_unit("TFT16_Braum", 2, (1, 3), 0, ["WarmogsArmor"]),  # Frontline tank
        engine.create_unit("TFT16_Draven", 2, (0, 3), 0, ["InfinityEdge"]),  # Backline carry
    ]
    team_enemy = [
        engine.create_unit("TFT16_Draven", 2, (3, 3), 1, ["InfinityEdge"]),
    ]

    result = engine.run_combat(team_with_tank, team_enemy, verbose=True)

    # Check if Braum took damage (meaning he drew aggro)
    braum = team_with_tank[0]
    draven_friendly = team_with_tank[1]

    print(f"Braum damage taken: {braum.total_damage_taken:.0f}")
    print(f"Draven (friendly) damage taken: {draven_friendly.total_damage_taken:.0f}")
    if braum.total_damage_taken > draven_friendly.total_damage_taken:
        print("SUCCESS: Tank drew aggro as expected!")
    else:
        print("NOTE: Carry took more damage (may be positioning dependent)")

    print("\n" + "=" * 60)
    print("Combat Simulator Tests Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
