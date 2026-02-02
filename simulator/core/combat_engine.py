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

import json
import random
import math
import heapq
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple, Callable
from pathlib import Path
from enum import Enum
from copy import deepcopy

# Import champion ability handlers
try:
    from .champion_abilities import ChampionAbilities
    _ABILITIES_LOADED = True
except ImportError:
    _ABILITIES_LOADED = False
    ChampionAbilities = None


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
    DAMAGE = "damage"              # Single target damage
    AOE_DAMAGE = "aoe_damage"      # Area damage
    BUFF = "buff"                  # Self/ally buff
    DEBUFF = "debuff"              # Enemy debuff
    SUMMON = "summon"              # Summon unit
    DASH = "dash"                  # Movement ability
    HEAL = "heal"                  # Healing
    SHIELD = "shield"              # Shield


class UnitState(Enum):
    IDLE = "idle"
    MOVING = "moving"
    ATTACKING = "attacking"
    CASTING = "casting"
    STUNNED = "stunned"
    DEAD = "dead"
    UNTARGETABLE = "untargetable"  # Cannot be targeted (Fizz, Zhonya's, Edge of Night)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
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
    damage_amp: float = 0.0       # Bonus damage multiplier (additive)
    damage_reduction: float = 0.0  # Durability (% damage reduction)
    omnivamp: float = 0.0         # Heal for % of damage dealt
    shield: float = 0.0           # Current shield amount
    move_speed: float = 550.0     # Movement speed (units per second)


@dataclass
class Ability:
    """Champion ability definition."""
    name: str
    ability_type: AbilityType
    damage_type: DamageType = DamageType.MAGIC
    targeting: TargetingType = TargetingType.CURRENT_TARGET
    base_damage: Dict[int, float] = field(default_factory=dict)  # {star: damage}
    ap_scaling: float = 1.0       # AP ratio
    ad_scaling: float = 0.0       # AD ratio
    cast_time: float = 0.5        # Seconds to cast
    aoe_radius: int = 0           # Hexes for AOE
    num_targets: int = 1          # Number of targets hit
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
class Unit:
    """A unit in combat."""
    name: str
    api_name: str
    star_level: int
    stats: CombatStats
    base_stats: CombatStats  # Original stats without items/buffs
    position: Tuple[int, int]  # (row, col) on hex grid
    team: int  # 0 or 1
    items: List[Item] = field(default_factory=list)
    traits: List[str] = field(default_factory=list)
    ability: Optional[Ability] = None
    role: str = ""  # Champion role: ADCarry, APCaster, APTank, ADFighter, etc.

    # Combat state
    state: UnitState = UnitState.IDLE
    target: Optional['Unit'] = None
    attack_cooldown: float = 0.0
    cast_progress: float = 0.0
    stun_duration: float = 0.0
    is_alive: bool = True
    buffs: List[Buff] = field(default_factory=list)

    # Movement
    move_target: Optional[Tuple[int, int]] = None
    path: List[Tuple[int, int]] = field(default_factory=list)

    # Untargetable state (Fizz, Zhonya's, Edge of Night)
    is_targetable: bool = True
    untargetable_duration: float = 0.0
    untargetable_return_pos: Optional[Tuple[int, int]] = None  # For abilities that teleport back

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

    def __hash__(self):
        return hash((self.api_name, id(self)))

    def __eq__(self, other):
        return id(self) == id(other)

    @property
    def is_frontline(self) -> bool:
        """Check if unit is a frontline/tank type."""
        return 'Tank' in self.role or 'Fighter' in self.role

    @property
    def is_backline(self) -> bool:
        """Check if unit is a backline carry type."""
        return 'Carry' in self.role or 'Caster' in self.role or 'Specialist' in self.role


# =============================================================================
# HEX GRID UTILITIES
# =============================================================================

class HexGrid:
    """Hex grid utilities for TFT board (4 rows x 7 cols)."""

    ROWS = 4
    COLS = 7

    # Hex directions for odd-q offset coordinates
    DIRECTIONS_EVEN = [(0, -1), (1, -1), (1, 0), (0, 1), (-1, 0), (-1, -1)]
    DIRECTIONS_ODD = [(0, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0)]

    @staticmethod
    def get_neighbors(pos: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Get all valid neighboring hexes."""
        row, col = pos
        directions = HexGrid.DIRECTIONS_ODD if col % 2 == 1 else HexGrid.DIRECTIONS_EVEN
        neighbors = []
        for dr, dc in directions:
            new_row, new_col = row + dr, col + dc
            if 0 <= new_row < HexGrid.ROWS and 0 <= new_col < HexGrid.COLS:
                neighbors.append((new_row, new_col))
        return neighbors

    @staticmethod
    def hex_distance(pos1: Tuple[int, int], pos2: Tuple[int, int]) -> int:
        """Calculate distance between two hexes in hex steps."""
        r1, c1 = pos1
        r2, c2 = pos2

        # Convert odd-q offset to cube coordinates
        x1 = c1
        z1 = r1 - (c1 - (c1 & 1)) // 2
        y1 = -x1 - z1

        x2 = c2
        z2 = r2 - (c2 - (c2 & 1)) // 2
        y2 = -x2 - z2

        return (abs(x1 - x2) + abs(y1 - y2) + abs(z1 - z2)) // 2

    @staticmethod
    def find_path(start: Tuple[int, int], goal: Tuple[int, int],
                  occupied: set) -> List[Tuple[int, int]]:
        """A* pathfinding on hex grid."""
        if start == goal:
            return []

        open_set = [(0, start)]
        came_from = {}
        g_score = {start: 0}
        f_score = {start: HexGrid.hex_distance(start, goal)}

        while open_set:
            _, current = heapq.heappop(open_set)

            if current == goal:
                # Reconstruct path
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                return path[::-1]

            for neighbor in HexGrid.get_neighbors(current):
                if neighbor in occupied and neighbor != goal:
                    continue

                tentative_g = g_score[current] + 1

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + HexGrid.hex_distance(neighbor, goal)
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))

        return []  # No path found

    @staticmethod
    def get_hexes_in_range(center: Tuple[int, int], radius: int) -> List[Tuple[int, int]]:
        """Get all hexes within radius of center."""
        hexes = []
        for row in range(HexGrid.ROWS):
            for col in range(HexGrid.COLS):
                if HexGrid.hex_distance(center, (row, col)) <= radius:
                    hexes.append((row, col))
        return hexes


# =============================================================================
# TRAIT MANAGER - Handle Trait Mechanics
# =============================================================================

class TraitManager:
    """Manages trait effects and mechanics.

    Key traits with special mechanics:
    - Blacksmith (Ornn): Craft artifact items over 4 rounds
    - Bilgewater: Serpent currency for store purchases
    - Piltover: T-Hex modules at 2/4/6 trait count
    """

    # Bilgewater serpent rewards by trait count
    BILGEWATER_SERPENTS_PER_ROUND = {
        3: 15,
        5: 35,
        7: 65,
        10: 150,
    }
    BILGEWATER_SERPENTS_PER_TAKEDOWN = 2

    def __init__(self):
        self.blacksmith_progress: Dict[str, int] = {}  # unit_id -> rounds_crafted
        self.blacksmith_items: Dict[str, List[str]] = {}  # unit_id -> list of crafted artifacts
        self.bilgewater_serpents: int = 0
        self.bilgewater_purchases: int = 0  # Track total purchases
        self.piltover_modules: List[str] = []
        self.round_number: int = 0
        self.bilgewater_count: int = 0  # Current Bilgewater trait count

    def start_round(self, units: List['Unit']):
        """Process start of round for trait mechanics."""
        self.round_number += 1

        # Blacksmith progress
        for unit in units:
            if 'Blacksmith' in unit.traits:
                unit_id = f"{unit.api_name}_{id(unit)}"
                if unit_id not in self.blacksmith_progress:
                    self.blacksmith_progress[unit_id] = 0
                    self.blacksmith_items[unit_id] = []

                self.blacksmith_progress[unit_id] += 1

                # Check if artifact is ready (4 rounds)
                if self.blacksmith_progress[unit_id] >= 4:
                    self.blacksmith_progress[unit_id] = 0
                    self._craft_artifact(unit)

    def _craft_artifact(self, unit: 'Unit'):
        """Ornn crafts an artifact item."""
        unit_id = f"{unit.api_name}_{id(unit)}"

        # Get random artifact from the pool
        if _ITEMS_LOADED and ARTIFACT_ITEMS:
            import random
            artifact_name = random.choice(list(ARTIFACT_ITEMS.keys()))
            self.blacksmith_items[unit_id].append(artifact_name)

            # Ornn also gains HP per item crafted
            hp_bonus = BLACKSMITH_CONFIG.get('hp_per_item', {}).get(unit.star_level, 250)
            unit.stats.max_hp += hp_bonus
            unit.stats.hp += hp_bonus

            return artifact_name
        return None

    def get_crafted_artifacts(self, unit: 'Unit') -> List[str]:
        """Get list of artifacts crafted by a Blacksmith unit."""
        unit_id = f"{unit.api_name}_{id(unit)}"
        return self.blacksmith_items.get(unit_id, [])

    def get_blacksmith_progress(self, unit: 'Unit') -> int:
        """Get current crafting progress for a Blacksmith unit."""
        unit_id = f"{unit.api_name}_{id(unit)}"
        return self.blacksmith_progress.get(unit_id, 0)

    def set_bilgewater_count(self, count: int):
        """Set the current Bilgewater trait count."""
        self.bilgewater_count = count

    def award_round_serpents(self) -> int:
        """Award serpents at the start of a round based on Bilgewater trait count.

        Returns the amount of serpents awarded.
        """
        if self.bilgewater_count < 3:
            return 0

        # Find the highest tier we qualify for
        serpent_reward = 0
        for tier in sorted(self.BILGEWATER_SERPENTS_PER_ROUND.keys(), reverse=True):
            if self.bilgewater_count >= tier:
                serpent_reward = self.BILGEWATER_SERPENTS_PER_ROUND[tier]
                break

        self.bilgewater_serpents += serpent_reward
        return serpent_reward

    def award_takedown_serpents(self) -> int:
        """Award serpents for a takedown (kill/assist).

        Returns the amount of serpents awarded.
        """
        if self.bilgewater_count < 3:
            return 0

        self.bilgewater_serpents += self.BILGEWATER_SERPENTS_PER_TAKEDOWN
        return self.BILGEWATER_SERPENTS_PER_TAKEDOWN

    def add_bilgewater_serpents(self, amount: int):
        """Add serpent currency from Bilgewater trait."""
        self.bilgewater_serpents += amount

    def buy_from_bilgewater_store(self, item_key: str) -> Optional[str]:
        """Purchase item from Bilgewater store using serpents.

        Args:
            item_key: Key from BILGEWATER_STORE (champion or item)

        Returns the item/champion purchased, or None if insufficient serpents or max purchases reached.
        """
        if not _ITEMS_LOADED:
            return None

        max_purchases = BILGEWATER_STORE.get('max_purchases', 8)
        if self.bilgewater_purchases >= max_purchases:
            return None

        # Check items first
        store_items = BILGEWATER_STORE.get('items', {})
        if item_key in store_items:
            item_info = store_items[item_key]
            cost = item_info.get('cost', 0)

            if self.bilgewater_serpents >= cost:
                self.bilgewater_serpents -= cost
                self.bilgewater_purchases += 1
                return item_key

        # Check champions
        store_champions = BILGEWATER_STORE.get('champions', {})
        if item_key in store_champions:
            champ_info = store_champions[item_key]
            cost = champ_info.get('cost', 0)

            if self.bilgewater_serpents >= cost:
                self.bilgewater_serpents -= cost
                self.bilgewater_purchases += 1
                return item_key

        return None

    def get_store_affordables(self) -> Dict[str, List[str]]:
        """Get list of items and champions affordable with current serpents.

        Returns dict with 'items' and 'champions' keys.
        """
        if not _ITEMS_LOADED:
            return {'items': [], 'champions': []}

        max_purchases = BILGEWATER_STORE.get('max_purchases', 8)
        if self.bilgewater_purchases >= max_purchases:
            return {'items': [], 'champions': []}

        affordables = {'items': [], 'champions': []}

        for item_key, item_info in BILGEWATER_STORE.get('items', {}).items():
            if self.bilgewater_serpents >= item_info.get('cost', 0):
                affordables['items'].append(item_key)

        for champ_key, champ_info in BILGEWATER_STORE.get('champions', {}).items():
            if self.bilgewater_serpents >= champ_info.get('cost', 0):
                affordables['champions'].append(champ_key)

        return affordables

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
                "AccelerationGate", "BlastShield", "ContinuumCogs",
                "EMP", "KineticBarrier", "OverclockedCapacitors"
            ]
            available_modules.extend(tier1_modules)

        # Tier 2: 4 Piltover
        if piltover_count >= 4:
            tier2_modules = [
                "ArmorNullifier", "GigantificationRay", "MagnetronCoil",
                "MomentumDrive", "TunedOscillator", "ElectricalOverload"
            ]
            available_modules.extend(tier2_modules)

        # Tier 3: 6 Piltover
        if piltover_count >= 6:
            tier3_modules = [
                "MicroRockets", "MiningDrill", "90CaliberNets",
                "SuperiorLifeform", "UnstableCurrent"
            ]
            available_modules.extend(tier3_modules)

        return available_modules


# =============================================================================
# ITEM DEFINITIONS - Set 16 Complete Item Database
# =============================================================================

# Try to import from the comprehensive item data file
try:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / "data"))
    from set16_items import (
        ALL_ITEMS, ITEM_ALIASES, ARTIFACT_ITEMS, RADIANT_ITEMS,
        EMBLEM_ITEMS, PILTOVER_MODULES, BILGEWATER_STORE, BLACKSMITH_CONFIG
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
        """Create an item instance from name."""
        # Check alias first
        resolved_name = ItemDatabase.ALIASES.get(name, name)

        if resolved_name not in ItemDatabase.ITEMS:
            print(f"Warning: Item '{name}' not found in database")
            return None

        stats = ItemDatabase.ITEMS[resolved_name].copy()
        return Item(name=resolved_name, stats=stats)


# =============================================================================
# ABILITY DEFINITIONS
# =============================================================================

class AbilityDatabase:
    """Database of champion abilities parsed from combat_data."""

    @staticmethod
    def create_ability(api_name: str, champ_data: Dict, star_level: int) -> Optional[Ability]:
        """Create an ability from champion data."""
        ability_data = champ_data.get('ability', {})
        if not ability_data or not ability_data.get('name'):
            return None

        variables = ability_data.get('variables', {})

        # Try to find primary damage variable
        damage_by_star = {1: 0, 2: 0, 3: 0}
        damage_var = None
        num_hits = 1  # For multi-hit abilities

        # Check for multi-hit indicators (missiles, hits, etc.)
        for key in ['NumMissiles', 'NumHits', 'NumBounces', 'NumAttacks']:
            if key in variables:
                hit_var = variables[key]
                if isinstance(hit_var, dict):
                    # Use star level value
                    num_hits = hit_var.get(f'{star_level}star', 1) or 1
                break

        # Common damage variable names (prefer per-hit damage for multi-hit)
        damage_keys = ['ADDamage', 'APDamage', 'Damage', 'MagicDamage', 'BaseDamage',
                       'PrimaryDamage', 'TotalDamage', 'SpellDamage']

        for key in damage_keys:
            if key in variables:
                damage_var = variables[key]
                break

        # Fallback to first variable with star values
        if not damage_var:
            for key, val in variables.items():
                if isinstance(val, dict) and '1star' in val:
                    damage_var = val
                    break

        if damage_var:
            # For multi-hit abilities, multiply by number of hits
            # But cap it to avoid insane damage (TFT spreads damage across targets)
            hit_multiplier = min(num_hits, 6)  # Cap at 6 hits effective
            damage_by_star[1] = (damage_var.get('1star', 0) or 0) * hit_multiplier
            damage_by_star[2] = (damage_var.get('2star', 0) or 0) * hit_multiplier
            damage_by_star[3] = (damage_var.get('3star', 0) or 0) * hit_multiplier

        # Determine ability type from role
        role = champ_data.get('role', '')
        if 'AP' in role or 'Caster' in role:
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

        desc = ability_data.get('desc', '').lower()
        if 'enemies' in desc or 'all' in desc or 'area' in desc:
            ability_type = AbilityType.AOE_DAMAGE
            aoe_radius = 2
            num_targets = 4
        elif 'heal' in desc:
            ability_type = AbilityType.HEAL
        elif 'shield' in desc:
            ability_type = AbilityType.SHIELD
        elif 'dash' in desc or 'leap' in desc:
            ability_type = AbilityType.DASH

        return Ability(
            name=ability_data.get('name', 'Unknown').strip(),
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
    HEX_SIZE = 180              # Game units per hex
    MANA_PER_ATTACK = 10        # Mana gained per auto attack
    MANA_ON_DAMAGE_TAKEN = 0.01 # Mana per 1% max HP lost
    MOVE_SPEED_BASE = 550       # Base movement speed
    HEX_MOVE_TIME = 0.5         # Seconds to move one hex at base speed

    # Star scaling
    HP_SCALING = {1: 1.0, 2: 1.8, 3: 3.24}
    AD_SCALING = {1: 1.0, 2: 1.5, 3: 2.25}

    def __init__(self, combat_data_path: Optional[Path] = None):
        """Initialize the combat engine with game data."""
        if combat_data_path is None:
            combat_data_path = Path(__file__).parent.parent / "data" / "combat_data.json"

        with open(combat_data_path, 'r', encoding='utf-8') as f:
            self.combat_data = json.load(f)

        self.champions = self.combat_data.get('champions', {})
        self.constants = self.combat_data.get('constants', {})

        # Combat state
        self.time = 0.0
        self.tick_rate = 0.033  # ~30 FPS simulation
        self.combat_log: List[Dict] = []
        self.units: List[Unit] = []
        self.projectiles: List[Dict] = []

        # Trait manager for Blacksmith, Bilgewater, Piltover
        self.trait_manager = TraitManager()

        # Champion ability handlers
        if _ABILITIES_LOADED and ChampionAbilities:
            self.champion_abilities = ChampionAbilities(self)
        else:
            self.champion_abilities = None

    def create_unit(self, api_name: str, star_level: int, position: Tuple[int, int],
                   team: int, items: List[str] = None) -> Optional[Unit]:
        """Create a unit from champion data."""
        champ_data = self.champions.get(api_name)
        if not champ_data:
            print(f"Warning: Champion {api_name} not found in data")
            return None

        base_stats_data = champ_data.get('stats', {})
        timing = champ_data.get('timing', {})

        # Apply star scaling
        hp_mult = self.HP_SCALING.get(star_level, 1.0)
        ad_mult = self.AD_SCALING.get(star_level, 1.0)

        base_stats = CombatStats(
            hp=(base_stats_data.get('hp') or 500) * hp_mult,
            max_hp=(base_stats_data.get('hp') or 500) * hp_mult,
            ad=(base_stats_data.get('ad') or 50) * ad_mult,
            ap=0.0,
            attack_speed=base_stats_data.get('attackSpeed') or 0.7,
            armor=base_stats_data.get('armor') or 20,
            magic_resist=base_stats_data.get('magicResist') or 20,
            range=int(base_stats_data.get('range') or 1),
            mana=base_stats_data.get('startMana') or 0,
            max_mana=base_stats_data.get('mana') or 100,
            crit_chance=base_stats_data.get('critChance') or 0.25,
            crit_multiplier=base_stats_data.get('critMultiplier') or 1.4,
        )

        # Create ability
        ability = AbilityDatabase.create_ability(api_name, champ_data, star_level)

        # Create unit with copied stats (so items can modify)
        current_stats = deepcopy(base_stats)

        unit = Unit(
            name=champ_data.get('name', api_name).strip(),
            api_name=api_name,
            star_level=star_level,
            stats=current_stats,
            base_stats=base_stats,
            position=position,
            team=team,
            traits=champ_data.get('traits', []),
            ability=ability,
            role=champ_data.get('role', ''),
            attack_windup=timing.get('attackWindup', 0.3),
            missile_speed=timing.get('missileSpeed'),
        )

        # Apply items
        if items:
            for item_name in items:
                item = ItemDatabase.create_item(item_name)
                if item:
                    self.apply_item(unit, item)

        return unit

    def apply_item(self, unit: Unit, item: Item):
        """Apply item stats to a unit.

        Note: In Set 16, AD on items is a percentage (e.g., 0.35 = 35% bonus AD).
        Other stats like HP, armor, AP are flat values.
        """
        unit.items.append(item)

        for stat, value in item.stats.items():
            if hasattr(unit.stats, stat):
                current = getattr(unit.stats, stat)

                # AD is a percentage multiplier in Set 16 items
                if stat == 'ad':
                    # Convert percentage to flat AD based on base AD
                    flat_ad = unit.base_stats.ad * value
                    setattr(unit.stats, stat, current + flat_ad)

                # Flat stats
                elif stat in ['hp', 'max_hp', 'armor', 'magic_resist', 'ap']:
                    setattr(unit.stats, stat, current + value)

                # Percentage stats (already stored as decimals)
                elif stat in ['attack_speed', 'crit_chance', 'damage_amp', 'omnivamp', 'crit_multiplier']:
                    setattr(unit.stats, stat, current + value)

                # Mana stats
                elif stat == 'mana_regen':
                    # Mana regen doesn't map to a single stat, skip for now
                    pass

                else:
                    setattr(unit.stats, stat, current + value)

    def get_occupied_hexes(self) -> set:
        """Get set of all occupied hex positions."""
        return {u.position for u in self.units if u.is_alive}

    def calculate_damage(self, attacker: Unit, defender: Unit,
                        base_damage: float, damage_type: DamageType,
                        can_crit: bool = True, is_ability: bool = False) -> Tuple[float, bool]:
        """Calculate final damage after all modifiers."""
        damage = base_damage

        # Apply damage amp
        damage *= (1 + attacker.stats.damage_amp)

        # Check for crit
        did_crit = False
        if can_crit:
            # Check for Jeweled Gauntlet (abilities can crit)
            has_jeweled = any(i.name == "JeweledGauntlet" for i in attacker.items)
            if not is_ability or has_jeweled:
                if random.random() < attacker.stats.crit_chance:
                    damage *= attacker.stats.crit_multiplier
                    did_crit = True

        # Apply resistance reduction
        if damage_type == DamageType.PHYSICAL:
            resist = max(0, defender.stats.armor)
            damage *= 100 / (100 + resist)
        elif damage_type == DamageType.MAGIC:
            resist = max(0, defender.stats.magic_resist)
            damage *= 100 / (100 + resist)

        # Apply durability (damage reduction)
        if defender.stats.damage_reduction > 0:
            damage *= (1 - defender.stats.damage_reduction)

        # Giant Slayer check
        if any(i.name == "GiantSlayer" for i in attacker.items):
            if defender.stats.max_hp > 1750:
                damage *= 1.25

        return max(0, damage), did_crit

    def check_hp_threshold_effects(self, unit: Unit):
        """Check for item effects that trigger at HP thresholds.

        - Edge of Night: At 60% HP, become untargetable briefly, cleanse negative effects
        - Zhonya's Paradox: At HP threshold, become invulnerable
        """
        hp_percent = unit.stats.hp / unit.stats.max_hp

        # Edge of Night - triggers at 60% HP (one time per combat)
        has_edge_of_night = any(i.name in ["EdgeOfNight", "TFT_Item_EdgeOfNight"] for i in unit.items)
        if has_edge_of_night and hp_percent <= 0.60:
            # Check if we already triggered (use a marker)
            if not hasattr(unit, '_edge_of_night_triggered'):
                unit._edge_of_night_triggered = True

                # Become untargetable for 1.5 seconds
                unit.is_targetable = False
                unit.untargetable_duration = 1.5
                unit.state = UnitState.UNTARGETABLE

                # Cleanse negative effects (remove stun, debuffs)
                unit.stun_duration = 0
                unit.buffs = [b for b in unit.buffs if b.stacks > 0]  # Remove debuffs (simplified)

                self.log_event('edge_of_night_proc', unit=unit.name, hp_percent=round(hp_percent * 100, 1))

        # Zhonya's Paradox - triggers at HP threshold
        has_zhonyas = any(i.name in ["ZhonyasParadox", "TFT16_Item_ZhonyasParadox"] for i in unit.items)
        if has_zhonyas and hp_percent <= 0.50:
            if not hasattr(unit, '_zhonyas_triggered'):
                unit._zhonyas_triggered = True

                # Become untargetable and invulnerable for 2.5 seconds
                unit.is_targetable = False
                unit.untargetable_duration = 2.5
                unit.state = UnitState.UNTARGETABLE

                self.log_event('zhonyas_proc', unit=unit.name, hp_percent=round(hp_percent * 100, 1))

        # Radiant Edge of Night - triggers at 60% HP with full heal
        has_radiant_edge = any(i.name in ["RadiantEdgeOfNight"] for i in unit.items)
        if has_radiant_edge and hp_percent <= 0.60:
            if not hasattr(unit, '_radiant_edge_triggered'):
                unit._radiant_edge_triggered = True

                # Become untargetable for 1.5 seconds
                unit.is_targetable = False
                unit.untargetable_duration = 1.5
                unit.state = UnitState.UNTARGETABLE

                # Cleanse and heal to full HP
                unit.stun_duration = 0
                missing_hp = unit.stats.max_hp - unit.stats.hp
                self.heal_unit(unit, missing_hp, "radiant_edge_of_night")

                self.log_event('radiant_edge_proc', unit=unit.name, hp_percent=round(hp_percent * 100, 1))

    def apply_damage(self, attacker: Unit, defender: Unit, damage: float,
                    damage_type: DamageType, source: str = "attack") -> float:
        """Apply damage to a unit and return actual damage dealt."""
        if not defender.is_alive:
            return 0

        # Check if defender is untargetable (shouldn't take damage)
        if not defender.is_targetable:
            return 0

        # Damage shield first
        if defender.stats.shield > 0:
            if damage <= defender.stats.shield:
                defender.stats.shield -= damage
                self.log_event('shield_absorb', attacker=attacker.name,
                              defender=defender.name, damage=damage)
                return 0
            else:
                damage -= defender.stats.shield
                defender.stats.shield = 0

        # Mana on damage taken
        hp_percent_lost = damage / defender.stats.max_hp
        mana_gain = hp_percent_lost * 100 * self.MANA_ON_DAMAGE_TAKEN
        defender.stats.mana = min(defender.stats.mana + mana_gain, defender.stats.max_mana)

        # Apply damage
        actual_damage = min(damage, defender.stats.hp)
        defender.stats.hp -= actual_damage
        defender.total_damage_taken += actual_damage
        attacker.total_damage_dealt += actual_damage

        # Omnivamp healing
        if attacker.stats.omnivamp > 0:
            heal_amount = actual_damage * attacker.stats.omnivamp
            self.heal_unit(attacker, heal_amount, "omnivamp")

        # Check for death
        if defender.stats.hp <= 0:
            defender.stats.hp = 0
            defender.is_alive = False
            defender.state = UnitState.DEAD

            # Check for Immortal resurrection (Zaahen)
            if self.champion_abilities and self.champion_abilities.check_immortal_resurrection(defender):
                # Unit was resurrected - don't award takedown
                pass
            else:
                # Award Bilgewater serpents for takedown (attacker's team)
                if 'Bilgewater' in attacker.traits or self.trait_manager.bilgewater_count >= 3:
                    serpents = self.trait_manager.award_takedown_serpents()
                    if serpents > 0:
                        self.log_event('bilgewater_takedown', killer=attacker.name,
                                      victim=defender.name, serpents=serpents,
                                      total=self.trait_manager.bilgewater_serpents)

        self.log_event('damage', source=source, attacker=attacker.name,
                      defender=defender.name, damage=round(actual_damage, 1),
                      damage_type=damage_type.value,
                      defender_hp=round(defender.stats.hp, 1),
                      defender_alive=defender.is_alive)

        # Check for HP threshold effects (Edge of Night, Zhonya's)
        if defender.is_alive:
            self.check_hp_threshold_effects(defender)

        return actual_damage

    def heal_unit(self, unit: Unit, amount: float, source: str = "heal"):
        """Heal a unit."""
        if not unit.is_alive:
            return

        actual_heal = min(amount, unit.stats.max_hp - unit.stats.hp)
        unit.stats.hp += actual_heal
        unit.total_healing += actual_heal

        if actual_heal > 0:
            self.log_event('heal', unit=unit.name, amount=round(actual_heal, 1),
                          source=source, hp=round(unit.stats.hp, 1))

    def apply_shield(self, unit: Unit, amount: float, source: str = "shield"):
        """Apply shield to a unit."""
        if not unit.is_alive:
            return

        unit.stats.shield += amount
        self.log_event('shield', unit=unit.name, amount=round(amount, 1),
                      source=source, total_shield=round(unit.stats.shield, 1))

    def log_event(self, event_type: str, **kwargs):
        """Log a combat event."""
        self.combat_log.append({
            'time': round(self.time, 2),
            'type': event_type,
            **kwargs
        })

    def find_target(self, unit: Unit, enemies: List[Unit],
                   targeting: TargetingType = TargetingType.NEAREST,
                   include_untargetable: bool = False) -> Optional[Unit]:
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
            # Units within 1 hex of the closest are considered "in range"
            distances = [(e, HexGrid.hex_distance(unit.position, e.position)) for e in valid_enemies]
            min_dist = min(d for _, d in distances)

            # Get all enemies within 1 hex of the closest
            close_enemies = [e for e, d in distances if d <= min_dist + 1]

            # Prefer frontline targets among close enemies
            frontline = [e for e in close_enemies if e.is_frontline]
            if frontline:
                # Among frontline, pick the closest
                return min(frontline, key=lambda e: HexGrid.hex_distance(unit.position, e.position))

            # Otherwise, just pick the closest overall
            return min(valid_enemies, key=lambda e: HexGrid.hex_distance(unit.position, e.position))

        elif targeting == TargetingType.LOWEST_HP:
            return min(valid_enemies, key=lambda e: e.stats.hp)
        elif targeting == TargetingType.LOWEST_HP_PERCENT:
            return min(valid_enemies, key=lambda e: e.stats.hp / e.stats.max_hp)
        elif targeting == TargetingType.HIGHEST_HP:
            return max(valid_enemies, key=lambda e: e.stats.hp)
        elif targeting == TargetingType.FARTHEST:
            return max(valid_enemies, key=lambda e: HexGrid.hex_distance(unit.position, e.position))
        elif targeting == TargetingType.RANDOM:
            return random.choice(valid_enemies)

        return valid_enemies[0]

    def get_enemies_in_range(self, unit: Unit, radius: int,
                            enemies: List[Unit],
                            include_untargetable: bool = False) -> List[Unit]:
        """Get all enemies within radius of unit.

        Args:
            include_untargetable: If True, include untargetable units (for positioning/AoE checks)
        """
        if include_untargetable:
            return [e for e in enemies if e.is_alive and
                    HexGrid.hex_distance(unit.position, e.position) <= radius]
        return [e for e in enemies if e.is_alive and e.is_targetable and
                HexGrid.hex_distance(unit.position, e.position) <= radius]

    def can_attack(self, unit: Unit, target: Unit) -> bool:
        """Check if unit can attack target (in range)."""
        distance = HexGrid.hex_distance(unit.position, target.position)
        return distance <= unit.stats.range

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
            ability_vars = champ_data.get('ability', {}).get('variables', {})
            num_attacks_data = ability_vars.get('NumAttacks', {})
            threshold = num_attacks_data.get(f'{unit.star_level}star', 18) or 18

            if unit.attacks_performed > threshold:
                is_jinx_rockets = True
                # Rocket form: Gets AD bonus from ability
                ad_bonus_data = ability_vars.get('ADDamage', {})
                ad_bonus = ad_bonus_data.get(f'{unit.star_level}star', 100) or 100
                base_damage = unit.stats.ad + ad_bonus

        final_damage, did_crit = self.calculate_damage(
            unit, unit.target, base_damage, DamageType.PHYSICAL, can_crit=True
        )

        # Apply damage
        source = "jinx_rocket" if is_jinx_rockets else ("crit_attack" if did_crit else "attack")
        self.apply_damage(unit, unit.target, final_damage, DamageType.PHYSICAL, source)

        # Jinx rockets deal splash damage to nearby enemies
        if is_jinx_rockets:
            splash_targets = self.get_enemies_in_range(unit, 1, [u for u in self.units if u.team != unit.team and u.is_alive and u != unit.target])
            for splash_target in splash_targets[:2]:  # Max 2 splash targets
                splash_damage = final_damage * 0.5  # 50% splash
                self.apply_damage(unit, splash_target, splash_damage, DamageType.PHYSICAL, "jinx_splash")

        # Handle enhanced attacks (from Fizz ability or items)
        if unit.enhanced_attacks_remaining > 0:
            unit.enhanced_attacks_remaining -= 1

            # Apply on-hit magic damage
            if unit.enhanced_attack_on_hit_dmg > 0:
                on_hit_damage, _ = self.calculate_damage(
                    unit, unit.target, unit.enhanced_attack_on_hit_dmg,
                    DamageType.MAGIC, can_crit=False, is_ability=True
                )
                self.apply_damage(unit, unit.target, on_hit_damage, DamageType.MAGIC, "enhanced_on_hit")

            # Reset bonus AS when enhanced attacks run out
            if unit.enhanced_attacks_remaining == 0:
                unit.stats.attack_speed -= unit.enhanced_attack_bonus_as
                unit.enhanced_attack_bonus_as = 0
                unit.enhanced_attack_on_hit_dmg = 0
                self.log_event('enhanced_attacks_ended', unit=unit.name)

        # Gain mana
        unit.stats.mana = min(unit.stats.mana + self.MANA_PER_ATTACK, unit.stats.max_mana)

        # Item on-hit effects
        for item in unit.items:
            if item.on_hit:
                item.on_hit(self, unit, unit.target)

        # Red Buff burn (this is the actual base item - 1% max HP burn)
        if any(i.name == "RedBuff" for i in unit.items):
            self._apply_burn(unit, unit.target, "red_buff",
                            unit.target.stats.max_hp * 0.01, 5.0)

    def _proc_void_staff(self, unit: Unit, target: Unit):
        """Proc Void Staff MR shred (30% for 5s)."""
        # Void Staff shreds MR on hit - simplified as instant MR reduction
        mr_shred = target.stats.magic_resist * 0.30
        target.stats.magic_resist = max(0, target.stats.magic_resist - mr_shred)

    def _apply_burn(self, attacker: Unit, target: Unit, source: str,
                   damage_per_tick: float, duration: float):
        """Apply burn debuff (simplified - instant damage for now)."""
        total_damage = damage_per_tick * duration
        damage, _ = self.calculate_damage(attacker, target, total_damage,
                                         DamageType.TRUE, can_crit=False)
        self.apply_damage(attacker, target, damage, DamageType.TRUE, source)

    def cast_ability(self, unit: Unit, enemies: List[Unit], allies: List[Unit]):
        """Cast unit's ability."""
        if not unit.ability:
            return

        ability = unit.ability
        unit.abilities_cast += 1

        # Get champion data for special ability handling
        champ_data = self.champions.get(unit.api_name, {})
        ability_vars = champ_data.get('ability', {}).get('variables', {})

        # Try champion-specific ability handler first
        if self.champion_abilities:
            if self.champion_abilities.cast(unit, enemies, allies, ability_vars):
                return  # Ability fully handled by champion-specific code

        # ==========================
        # FIZZ - Playful Trickster
        # ==========================
        # Fizz becomes UNTARGETABLE, leaps to farthest enemy within 4 hexes,
        # deals AoE damage on landing, then gains attack speed + on-hit magic damage for 4 attacks
        if unit.api_name == "TFT16_Fizz":
            # Find farthest enemy within 4 hexes
            enemies_in_range = [e for e in enemies if e.is_alive and e.is_targetable and
                               HexGrid.hex_distance(unit.position, e.position) <= 4]

            if not enemies_in_range:
                # No enemies in range - find closest enemy instead
                enemies_in_range = [e for e in enemies if e.is_alive and e.is_targetable]

            if enemies_in_range:
                # Target the farthest enemy in range
                target = max(enemies_in_range, key=lambda e: HexGrid.hex_distance(unit.position, e.position))

                # Become untargetable during leap (brief moment)
                unit.is_targetable = False
                unit.untargetable_duration = 0.3  # Brief untargetable during leap

                # Get ability damage values
                ap_dmg_data = ability_vars.get('APDamage', {})
                base_damage = ap_dmg_data.get(f'{unit.star_level}star', 150) or 150

                # Get enhanced attack values
                as_bonus_data = ability_vars.get('ASBonus', ability_vars.get('AttackSpeed', {}))
                as_bonus = (as_bonus_data.get(f'{unit.star_level}star', 100) or 100) / 100  # Convert to decimal
                on_hit_data = ability_vars.get('OnHitDamage', ability_vars.get('APOnHit', {}))
                on_hit_dmg = on_hit_data.get(f'{unit.star_level}star', 50) or 50
                num_attacks_data = ability_vars.get('NumAttacks', {})
                num_enhanced = int(num_attacks_data.get(f'{unit.star_level}star', 4) or 4)

                # Find position adjacent to target
                target_neighbors = HexGrid.get_neighbors(target.position)
                valid_spots = [n for n in target_neighbors if n not in self.get_occupied_hexes()]

                if valid_spots:
                    # Teleport to position adjacent to target
                    old_pos = unit.position
                    unit.position = valid_spots[0]
                    self.log_event('fizz_leap', unit=unit.name, from_pos=old_pos,
                                  to_pos=unit.position, target=target.name)

                # Deal AoE damage on landing
                landing_targets = self.get_enemies_in_range(unit, 1, enemies)
                for enemy in landing_targets:
                    final_damage, _ = self.calculate_damage(
                        unit, enemy, base_damage + unit.stats.ap,
                        DamageType.MAGIC, can_crit=True, is_ability=True
                    )
                    self.apply_damage(unit, enemy, final_damage, DamageType.MAGIC, "fizz_landing")

                # Grant enhanced attacks
                unit.enhanced_attacks_remaining = num_enhanced
                unit.enhanced_attack_bonus_as = as_bonus
                unit.enhanced_attack_on_hit_dmg = on_hit_dmg + (unit.stats.ap * 0.5)  # Scales with AP
                unit.stats.attack_speed += as_bonus

                self.log_event('fizz_enhanced', unit=unit.name, bonus_as=as_bonus,
                              on_hit=unit.enhanced_attack_on_hit_dmg, attacks=num_enhanced)

            # Reset mana
            unit.stats.mana = 0
            self.log_event('ability_cast', unit=unit.name, ability=ability.name,
                          targets=[t.name for t in enemies_in_range[:1]])
            return  # Fizz ability fully handled

        # Handle Kai'Sa (and other FormSwapper champions) - uses higher of AD or AP damage
        if 'FormSwapper' in unit.role:
            ad_dmg_data = ability_vars.get('ADDamage', {})
            ap_dmg_data = ability_vars.get('APDamage', {})

            ad_base = ad_dmg_data.get(f'{unit.star_level}star', 0) or 0
            ap_base = ap_dmg_data.get(f'{unit.star_level}star', 0) or 0

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
            num_targets_data = ability_vars.get('NumTargets', {})
            num_targets = int(num_targets_data.get(f'{unit.star_level}star', 4) or 4)
            num_missiles_data = ability_vars.get('NumMissiles', {})
            num_missiles = int(num_missiles_data.get(f'{unit.star_level}star', 15) or 15)

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
        if 'Tank' in unit.role:
            # Check for armor scaling (e.g., Braum's ArmorDamage)
            armor_dmg_data = ability_vars.get('ArmorDamage', {})
            if armor_dmg_data:
                armor_scaling = armor_dmg_data.get(f'{unit.star_level}star', 0) or 0
                total_damage += unit.stats.armor * armor_scaling

            # Check for HP scaling (e.g., percentage of max HP damage)
            hp_pct_data = ability_vars.get('HealthPercent', ability_vars.get('PercentHealthDamage', {}))
            if hp_pct_data:
                hp_scaling = hp_pct_data.get(f'{unit.star_level}star', 0) or 0
                total_damage += unit.stats.max_hp * hp_scaling

            # Check for shield abilities (Galio, Nautilus, Shen, Poppy)
            shield_data = ability_vars.get('Shield', ability_vars.get('ShieldAmt', ability_vars.get('APShield', {})))
            if shield_data:
                shield_amount = shield_data.get(f'{unit.star_level}star', 0) or 0
                # Nautilus also has percent HP shield
                pct_hp_shield = ability_vars.get('PercentHealthShield', {})
                if pct_hp_shield:
                    pct = pct_hp_shield.get(f'{unit.star_level}star', 0) or 0
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
            targets = targets[:ability.num_targets]

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
                    unit, target, total_damage, ability.damage_type,
                    can_crit=True, is_ability=True
                )
                self.apply_damage(unit, target, final_damage, ability.damage_type,
                                 f"ability:{ability.name}")

            elif ability.ability_type == AbilityType.HEAL:
                self.heal_unit(target, total_damage, f"ability:{ability.name}")

            elif ability.ability_type == AbilityType.SHIELD:
                self.apply_shield(target, total_damage, f"ability:{ability.name}")

        # Reset mana
        unit.stats.mana = 0

        self.log_event('ability_cast', unit=unit.name, ability=ability.name,
                      targets=[t.name for t in targets])

    def move_unit_towards(self, unit: Unit, target_pos: Tuple[int, int]):
        """Move unit one step towards target position."""
        if unit.position == target_pos:
            return

        occupied = self.get_occupied_hexes()
        occupied.discard(unit.position)  # Current pos is fine

        path = HexGrid.find_path(unit.position, target_pos, occupied)
        if path:
            next_pos = path[0]
            if next_pos not in occupied or next_pos == target_pos:
                unit.position = next_pos
                self.log_event('move', unit=unit.name,
                              from_pos=unit.position, to_pos=next_pos)

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
                    unit.position = unit.untargetable_return_pos
                    unit.untargetable_return_pos = None
                    self.log_event('teleport_return', unit=unit.name, position=unit.position)
            return  # Cannot act while untargetable (unless it's Fizz mid-leap)

        # Handle stun
        if unit.stun_duration > 0:
            unit.stun_duration -= self.tick_rate
            unit.state = UnitState.STUNNED
            return

        # Update buffs
        unit.buffs = [b for b in unit.buffs if b.duration > 0]
        for buff in unit.buffs:
            buff.duration -= self.tick_rate

        # Find/update target
        if not unit.target or not unit.target.is_alive:
            unit.target = self.find_target(unit, enemies)

        if not unit.target:
            unit.state = UnitState.IDLE
            return

        # Check if in range
        in_range = self.can_attack(unit, unit.target)

        # Movement if not in range
        if not in_range:
            unit.state = UnitState.MOVING

            # Move towards target (simplified - one hex per 0.5s)
            if unit.attack_cooldown <= 0:
                # Find adjacent hex to target that's in range
                target_neighbors = HexGrid.get_neighbors(unit.target.position)
                valid_spots = [n for n in target_neighbors
                              if n not in self.get_occupied_hexes()]

                if valid_spots:
                    best_spot = min(valid_spots,
                                   key=lambda s: HexGrid.hex_distance(unit.position, s))
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
            unit.attack_cooldown = unit.ability.cast_time
            return

        # Auto attack
        unit.state = UnitState.ATTACKING
        unit.attack_cooldown -= self.tick_rate

        if unit.attack_cooldown <= 0:
            attack_interval = 1.0 / unit.stats.attack_speed
            unit.attack_cooldown = attack_interval
            self.process_attack(unit)

    def tick(self):
        """Process one simulation tick."""
        self.time += self.tick_rate

        team0 = [u for u in self.units if u.team == 0 and u.is_alive]
        team1 = [u for u in self.units if u.team == 1 and u.is_alive]

        # Process in random order to avoid bias
        units_to_process = [u for u in self.units if u.is_alive]
        random.shuffle(units_to_process)

        for unit in units_to_process:
            enemies = team1 if unit.team == 0 else team0
            allies = team0 if unit.team == 0 else team1
            self.process_unit_tick(unit, enemies, allies)

    def process_round_start(self, team: List[Unit]):
        """Process start of round for trait mechanics.

        Called at the beginning of each round to:
        - Progress Blacksmith crafting
        - Award Bilgewater serpents
        - Check Piltover module availability
        """
        self.trait_manager.start_round(team)

        # Count trait occurrences
        trait_counts = {}
        for unit in team:
            for trait in unit.traits:
                trait_counts[trait] = trait_counts.get(trait, 0) + 1

        # Log trait info
        self.log_event('round_start',
                      round=self.trait_manager.round_number,
                      trait_counts=trait_counts)

        # Check Blacksmith progress
        for unit in team:
            if 'Blacksmith' in unit.traits:
                progress = self.trait_manager.get_blacksmith_progress(unit)
                artifacts = self.trait_manager.get_crafted_artifacts(unit)
                if artifacts:
                    self.log_event('blacksmith_status', unit=unit.name,
                                  progress=progress, artifacts_crafted=len(artifacts),
                                  latest_artifact=artifacts[-1] if artifacts else None)

        # Bilgewater serpent rewards
        bilgewater_count = trait_counts.get('Bilgewater', 0)
        self.trait_manager.set_bilgewater_count(bilgewater_count)
        if bilgewater_count >= 3:
            serpent_reward = self.trait_manager.award_round_serpents()
            self.log_event('bilgewater_serpents', count=bilgewater_count,
                          reward=serpent_reward,
                          total=self.trait_manager.bilgewater_serpents)

            # Show affordable items
            affordables = self.trait_manager.get_store_affordables()
            if affordables['items'] or affordables['champions']:
                self.log_event('bilgewater_store', affordable_items=affordables['items'],
                              affordable_champions=affordables['champions'])

        # Piltover module availability
        piltover_count = trait_counts.get('Piltover', 0)
        if piltover_count >= 2:
            available_modules = self.trait_manager.assign_piltover_modules(piltover_count)
            self.log_event('piltover_modules', count=piltover_count,
                          available=len(available_modules))

    def run_combat(self, team0: List[Unit], team1: List[Unit],
                  max_time: float = 60.0, verbose: bool = False) -> Dict:
        """Run a full combat simulation."""
        # Reset state
        self.time = 0.0
        self.combat_log = []
        self.units = team0 + team1
        self.projectiles = []

        # Process round start for traits (both teams)
        self.process_round_start(team0)
        self.process_round_start(team1)

        # Combat loop
        while self.time < max_time:
            team0_alive = any(u.is_alive for u in team0)
            team1_alive = any(u.is_alive for u in team1)

            if not team0_alive or not team1_alive:
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
            'winner': winner,
            'combat_time': round(self.time, 2),
            'team0_survivors': len(team0_survivors),
            'team1_survivors': len(team1_survivors),
            'team0_total_damage': round(sum(u.total_damage_dealt for u in team0), 1),
            'team1_total_damage': round(sum(u.total_damage_dealt for u in team1), 1),
            'team0_abilities_cast': sum(u.abilities_cast for u in team0),
            'team1_abilities_cast': sum(u.abilities_cast for u in team1),
            'combat_log': self.combat_log if verbose else [],
        }

        return results

    def simulate_1v1(self, champ1: str, champ2: str,
                    star1: int = 1, star2: int = 1,
                    items1: List[str] = None, items2: List[str] = None,
                    num_simulations: int = 100) -> Dict:
        """Simulate multiple 1v1 combats between two champions."""
        wins = {champ1: 0, champ2: 0}
        total_damage = {champ1: 0.0, champ2: 0.0}
        abilities_cast = {champ1: 0, champ2: 0}
        combat_times = []

        for _ in range(num_simulations):
            # Place units facing each other
            unit1 = self.create_unit(champ1, star1, (0, 3), 0, items1)
            unit2 = self.create_unit(champ2, star2, (3, 3), 1, items2)

            if not unit1 or not unit2:
                return {'error': 'Invalid champion names'}

            result = self.run_combat([unit1], [unit2])

            if result['winner'] == 0:
                wins[champ1] += 1
            else:
                wins[champ2] += 1

            total_damage[champ1] += result['team0_total_damage']
            total_damage[champ2] += result['team1_total_damage']
            abilities_cast[champ1] += result['team0_abilities_cast']
            abilities_cast[champ2] += result['team1_abilities_cast']
            combat_times.append(result['combat_time'])

        return {
            'simulations': num_simulations,
            'win_rate': {
                champ1: round(wins[champ1] / num_simulations * 100, 1),
                champ2: round(wins[champ2] / num_simulations * 100, 1),
            },
            'avg_damage': {
                champ1: round(total_damage[champ1] / num_simulations, 1),
                champ2: round(total_damage[champ2] / num_simulations, 1),
            },
            'avg_abilities_cast': {
                champ1: round(abilities_cast[champ1] / num_simulations, 2),
                champ2: round(abilities_cast[champ2] / num_simulations, 2),
            },
            'avg_combat_time': round(sum(combat_times) / len(combat_times), 2),
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
            print(f"{unit.name} ({unit.role}, {role_type}): HP={unit.stats.hp:.0f}, AD={unit.stats.ad:.0f}, "
                  f"AS={unit.stats.attack_speed:.2f}, Range={unit.stats.range}, Mana={unit.stats.mana}/{unit.stats.max_mana}")

    # 1v1: Same cost comparison
    print("\n" + "-" * 60)
    print("1v1: Draven (2*) vs Tristana (2*) - Both 3-cost ADCs")
    print("-" * 60)

    result = engine.simulate_1v1(
        "TFT16_Draven", "TFT16_Tristana",
        star1=2, star2=2,
        num_simulations=500
    )

    print(f"Simulations: {result['simulations']}")
    for champ, rate in result['win_rate'].items():
        print(f"  {champ}: {rate}% win rate")
    print(f"Average Combat Time: {result['avg_combat_time']}s")
    print(f"Average Abilities Cast:")
    for champ, casts in result['avg_abilities_cast'].items():
        print(f"  {champ}: {casts}")

    # 1v1: Tank vs Tank
    print("\n" + "-" * 60)
    print("1v1: Renekton (2*) vs Leona (2*) - Frontline clash")
    print("-" * 60)

    result = engine.simulate_1v1(
        "TFT16_Renekton", "TFT16_Leona",
        star1=2, star2=2,
        num_simulations=500
    )

    print(f"Simulations: {result['simulations']}")
    for champ, rate in result['win_rate'].items():
        print(f"  {champ}: {rate}% win rate")
    print(f"Average Combat Time: {result['avg_combat_time']}s")

    # 1v1 with items
    print("\n" + "-" * 60)
    print("1v1: Jinx (2*) + IE/LW vs Renekton (2*) + Warmogs/Bramble")
    print("-" * 60)

    result = engine.simulate_1v1(
        "TFT16_Jinx", "TFT16_Renekton",
        star1=2, star2=2,
        items1=["InfinityEdge", "LastWhisper"],
        items2=["WarmogsArmor", "BrambleVest"],
        num_simulations=500
    )

    print(f"Simulations: {result['simulations']}")
    for champ, rate in result['win_rate'].items():
        print(f"  {champ}: {rate}% win rate")
    print(f"Average Damage:")
    for champ, dmg in result['avg_damage'].items():
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
        "TFT16_Draven", "TFT16_Leona",
        star1=2, star2=2,
        num_simulations=300
    )

    result_with_ie = engine.simulate_1v1(
        "TFT16_Draven", "TFT16_Leona",
        star1=2, star2=2,
        items1=["InfinityEdge"],
        num_simulations=300
    )

    print(f"No items: Draven {result_no_items['win_rate']['TFT16_Draven']}% win")
    print(f"With IE:  Draven {result_with_ie['win_rate']['TFT16_Draven']}% win")

    # Test Jinx form swap (minigun -> rockets after 18 attacks)
    print("\n" + "-" * 60)
    print("Jinx Form Swap Test: Long fight to see rocket transition")
    print("-" * 60)

    # Jinx vs high HP tank - should see rocket form activate
    result = engine.simulate_1v1(
        "TFT16_Jinx", "TFT16_Renekton",
        star1=2, star2=2,
        items1=["RedBuff"],  # AS boost helps reach rocket form
        items2=["WarmogsArmor", "DragonsClaw"],  # Very tanky
        num_simulations=100
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


if __name__ == '__main__':
    main()
