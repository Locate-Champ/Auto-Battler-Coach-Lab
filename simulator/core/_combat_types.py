"""Combat type definitions: enums, dataclasses, and helper functions."""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# Module-level cache for combat data (loaded once, shared across all CombatEngine instances)
_COMBAT_DATA_CACHE: Dict[str, Any] = {}


def _load_combat_data(path: Path) -> dict:
    """Load combat data from JSON, using module-level cache."""
    key = str(path)
    if key not in _COMBAT_DATA_CACHE:
        if not path.is_file():
            raise FileNotFoundError(
                f"combat_data.json not found at {path}. "
                f"This file is required for the combat simulator and is part of the repository. "
                f"Restore it with: git checkout -- {path}"
            )
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
