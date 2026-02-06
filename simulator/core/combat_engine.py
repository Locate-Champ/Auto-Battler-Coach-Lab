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
        return var_data.get(f'{star_level}star', default) or default
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
    - Shadow Isles: Soul collection from enemy deaths
    """

    # Bilgewater serpent rewards by trait count
    BILGEWATER_SERPENTS_PER_ROUND = {
        3: 15,
        5: 35,
        7: 65,
        10: 150,
    }
    BILGEWATER_SERPENTS_PER_TAKEDOWN = 2

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
        self.blacksmith_progress: Dict[str, int] = {}  # unit_id -> rounds_crafted
        self.blacksmith_items: Dict[str, List[str]] = {}  # unit_id -> list of crafted artifacts
        self.bilgewater_serpents: int = 0
        self.bilgewater_purchases: int = 0  # Track total purchases
        self.piltover_modules: List[str] = []
        self.round_number: int = 0
        self.bilgewater_count: int = 0  # Current Bilgewater trait count

        # Shadow Isles soul tracking
        self.shadow_isles_souls: int = 0
        self.shadow_isles_count: int = 0  # Current Shadow Isles trait count
        self.shadow_isles_units: List['Unit'] = []  # Units with the trait

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

    # =========================================================================
    # SHADOW ISLES SOUL COLLECTION
    # =========================================================================

    def set_shadow_isles_count(self, count: int, units: List['Unit'] = None):
        """Set the current Shadow Isles trait count and track affected units.

        Args:
            count: Number of Shadow Isles champions active
            units: List of Shadow Isles units to track
        """
        self.shadow_isles_count = count
        if units:
            self.shadow_isles_units = units

    def award_soul(self, victim_cost: int = 1, victim_star: int = 1) -> int:
        """Award souls when an enemy dies.

        Soul value is based on victim's cost and star level.
        Higher cost/star units are worth more souls.

        Args:
            victim_cost: Champion cost (1-5)
            victim_star: Star level (1-3)

        Returns:
            Number of souls awarded
        """
        if self.shadow_isles_count < 2:
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
            if self.shadow_isles_count >= tier:
                soul_mult = self.SHADOW_ISLES_SOUL_MULTIPLIER[tier]
                break

        souls = int(souls * soul_mult)
        self.shadow_isles_souls += souls

        return souls

    def get_shadow_isles_stat_bonus(self) -> float:
        """Get the AD/AP bonus percentage for Shadow Isles units.

        Returns:
            Stat bonus as a decimal (0.18 = 18%)
        """
        if self.shadow_isles_count < 2:
            return 0.0

        for tier in sorted(self.SHADOW_ISLES_STAT_BONUS.keys(), reverse=True):
            if self.shadow_isles_count >= tier:
                return self.SHADOW_ISLES_STAT_BONUS[tier]

        return 0.0

    def apply_shadow_isles_stats(self, units: List['Unit']):
        """Apply Shadow Isles stat bonuses to units with the trait.

        Called at combat start to give AD/AP bonus based on trait count.
        """
        if self.shadow_isles_count < 2:
            return

        bonus = self.get_shadow_isles_stat_bonus()

        for unit in units:
            if 'Shadow Isles' in unit.traits:
                # Apply AD/AP bonus (percentage of base stats)
                ad_bonus = unit.base_stats.ad * bonus
                ap_bonus = unit.stats.ap * bonus if unit.stats.ap > 0 else 10 * bonus

                unit.stats.ad += ad_bonus
                unit.stats.ap += ap_bonus

    def reset_shadow_isles(self):
        """Reset Shadow Isles state for new combat."""
        self.shadow_isles_souls = 0

    # =========================================================================
    # HUNTRESS TRAIT (Neeko + Nidalee synergy)
    # =========================================================================

    # Huntress - While Neeko is alive, Nidalee can't be targeted by basic attacks + gains Durability
    HUNTRESS_DURABILITY = 0.5  # 50% damage reduction

    def apply_huntress_synergy(self, units: List['Unit']) -> bool:
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
        neekos = [u for u in units if u.api_name == 'TFT16_Neeko' and u.is_alive]
        nidalees = [u for u in units if u.api_name == 'TFT16_Nidalee' and u.is_alive]

        if not neekos or not nidalees:
            return False

        # Sort by star level (descending) to find "strongest"
        strongest_neeko = max(neekos, key=lambda u: (u.star_level, u.stats.hp))
        strongest_nidalee = max(nidalees, key=lambda u: (u.star_level, u.stats.hp))

        # Mark Nidalee as protected by Neeko
        if not hasattr(strongest_nidalee, '_huntress_active'):
            strongest_nidalee._huntress_active = True
            strongest_nidalee._huntress_neeko_id = id(strongest_neeko)
            strongest_nidalee.is_basic_attack_immune = True
            strongest_nidalee.stats.damage_reduction += self.HUNTRESS_DURABILITY

        return True

    def check_huntress_on_death(self, dead_unit: 'Unit', units: List['Unit']):
        """Check if Huntress synergy should be removed when a unit dies.

        If Neeko dies, Nidalee loses her Huntress buffs.

        Args:
            dead_unit: The unit that just died
            units: List of all units
        """
        if dead_unit.api_name != 'TFT16_Neeko':
            return

        # Find the Nidalee linked to this Neeko
        for unit in units:
            if (unit.api_name == 'TFT16_Nidalee' and
                hasattr(unit, '_huntress_active') and
                hasattr(unit, '_huntress_neeko_id') and
                unit._huntress_neeko_id == id(dead_unit)):

                # Remove Huntress buffs
                unit._huntress_active = False
                unit.is_basic_attack_immune = False
                unit.stats.damage_reduction = max(0, unit.stats.damage_reduction - self.HUNTRESS_DURABILITY)

    # =========================================================================
    # STAT-BUFFING TRAITS
    # =========================================================================

    # Arcanist (Sorcerer) - Team AP + bonus for Arcanists
    ARCANIST_EFFECTS = {
        2: {'AllyAP': 18, 'BonusAP': 25},
        4: {'AllyAP': 25, 'BonusAP': 40},
        6: {'AllyAP': 40, 'BonusAP': 60},
    }

    # Defender - Team armor/MR + bonus for Defenders
    DEFENDER_EFFECTS = {
        2: {'TeamwideArmorMR': 12, 'BonusArmorMR': 30},
        4: {'TeamwideArmorMR': 12, 'BonusArmorMR': 55},
        6: {'TeamwideArmorMR': 12, 'BonusArmorMR': 80},
    }

    # Bruiser (Brawler) - Team flat HP + bonus % HP for Bruisers
    BRUISER_EFFECTS = {
        2: {'TeamFlatHealth': 150, 'BonusPercentHealth': 0.25},
        4: {'TeamFlatHealth': 150, 'BonusPercentHealth': 0.45},
        6: {'TeamFlatHealth': 150, 'BonusPercentHealth': 0.65},
    }

    # Slayer - AD + Omnivamp (scaling with missing HP handled in combat)
    SLAYER_EFFECTS = {
        2: {'BonusAD': 0.22, 'BonusOmnivamp': 0.10, 'AmountIncrease': 0.5},
        4: {'BonusAD': 0.33, 'BonusOmnivamp': 0.16, 'AmountIncrease': 0.5},
        6: {'BonusAD': 0.44, 'BonusOmnivamp': 0.20, 'AmountIncrease': 0.5},
    }

    # Juggernaut - Durability (more when above 50% HP) + heal allies on death
    JUGGERNAUT_EFFECTS = {
        2: {'BaseDR': 0.18, 'IncreasedDR': 0.25, 'HealRatio': 0.05},
        4: {'BaseDR': 0.20, 'IncreasedDR': 0.30, 'HealRatio': 0.05},
        6: {'BaseDR': 0.26, 'IncreasedDR': 0.36, 'HealRatio': 0.05},
    }

    # Invoker - Team mana regen + % mana increase for Invokers
    INVOKER_EFFECTS = {
        2: {'TeamBonusMana': 1, 'PercentManaIncrease': 0.25},
        4: {'TeamBonusMana': 1, 'PercentManaIncrease': 0.40},
    }

    # Vanquisher - Crit chance + crit damage (abilities can crit)
    VANQUISHER_EFFECTS = {
        2: {'BaseCritChance': 15, 'CritDmg': 15},
        3: {'BaseCritChance': 20, 'CritDmg': 20},
        4: {'BaseCritChance': 25, 'CritDmg': 25},
        5: {'BaseCritChance': 30, 'CritDmg': 30},
    }

    # Longshot - Damage amp + per-hex bonus
    LONGSHOT_EFFECTS = {
        2: {'BaseDamageAmp': 0.18, 'PercentDamageIncrease': 0.02},
        3: {'BaseDamageAmp': 0.24, 'PercentDamageIncrease': 0.03},
        4: {'BaseDamageAmp': 0.28, 'PercentDamageIncrease': 0.04},
        5: {'BaseDamageAmp': 0.32, 'PercentDamageIncrease': 0.05},
    }

    # Quickstriker (Rapidfire) - Team AS + bonus AS based on target's missing HP
    QUICKSTRIKER_EFFECTS = {
        2: {'TeamwideAS': 0.15, 'MinBonusAS': 0.10, 'MaxBonusAS': 0.30},
        3: {'TeamwideAS': 0.15, 'MinBonusAS': 0.20, 'MaxBonusAS': 0.45},
        4: {'TeamwideAS': 0.15, 'MinBonusAS': 0.30, 'MaxBonusAS': 0.60},
        5: {'TeamwideAS': 0.15, 'MinBonusAS': 0.40, 'MaxBonusAS': 0.80},
    }

    # Gunslinger - AD + every 4th attack bonus damage
    GUNSLINGER_EFFECTS = {
        2: {'AD': 0.20, 'BonusDamage': 100, 'NumAttacks': 4},
        4: {'AD': 0.35, 'BonusDamage': 200, 'NumAttacks': 4},
    }

    # Warden - Shields at HP thresholds (75% and 25%)
    WARDEN_EFFECTS = {
        2: {'PercentHealthShield': 0.16, 'FirstThreshold': 0.75, 'SecondThreshold': 0.25},
        3: {'PercentHealthShield': 0.20, 'FirstThreshold': 0.75, 'SecondThreshold': 0.25},
        4: {'PercentHealthShield': 0.26, 'FirstThreshold': 0.75, 'SecondThreshold': 0.25},
        5: {'PercentHealthShield': 0.33, 'FirstThreshold': 0.75, 'SecondThreshold': 0.25},
    }

    # =====================================================================
    # REGION TRAITS
    # =====================================================================

    # Demacia - Armor/MR for Demacia units
    DEMACIA_EFFECTS = {
        3: {'ArmorMR': 12},
        5: {'ArmorMR': 35},
        7: {'ArmorMR': 35},
        11: {'ArmorMR': 150},
    }

    # Freljord - HP% + Damage Amp for Freljord units
    FRELJORD_EFFECTS = {
        3: {'HealthPercent': 0.08, 'DA': 0.10},
        5: {'HealthPercent': 0.12, 'DA': 0.16},
        7: {'HealthPercent': 0.16, 'DA': 0.22},
    }

    # Void - AS for Void units
    VOID_EFFECTS = {
        2: {'BonusAS': 0.08},
        4: {'BonusAS': 0.18},
        6: {'BonusAS': 0.33},
        9: {'BonusAS': 0.40},
    }

    # Shurima - HP% + heal/sec + ArmorMR at higher tiers
    SHURIMA_EFFECTS = {
        2: {'BonusHealth': 0.20, 'HealthRestorePerSecond': 20, 'ASPerSecond': 0.02, 'ArmorMR': 0},
        3: {'BonusHealth': 0.20, 'HealthRestorePerSecond': 20, 'ASPerSecond': 0.02, 'ArmorMR': 50},
        4: {'BonusHealth': 0.20, 'HealthRestorePerSecond': 20, 'ASPerSecond': 0.02, 'ArmorMR': 50},
    }

    # Yordle - flat HP + AS for Yordle units
    YORDLE_EFFECTS = {
        2: {'AS': 0.05, 'BonusHealth': 40},
        4: {'AS': 0.05, 'BonusHealth': 40},
        6: {'AS': 0.05, 'BonusHealth': 40},
        8: {'AS': 0.05, 'BonusHealth': 40},
        10: {'AS': 0.05, 'BonusHealth': 40},
    }

    # Ixtal - HP for pairs + healing
    IXTAL_EFFECTS = {
        5: {'BonusHealthPairs': 250, 'Heal': 2.0},
        7: {'BonusHealthPairs': 250, 'Heal': 2.0},
    }

    # Zaun - Shimmer Fuse: delayed AS + durability burst (combat-time mechanic)
    ZAUN_EFFECTS = {
        3: {'ShimmerAS': 0.90, 'ShimmerDurability': 0.15, 'ShimmerDuration': 4.0, 'InitialDelay': 4.0, 'HealThreshold': 0.60},
        5: {'ShimmerAS': 0.90, 'ShimmerDurability': 0.15, 'ShimmerDuration': 4.0, 'InitialDelay': 4.0, 'HealThreshold': 0.60, 'MaxHealthHeal': 0.30},
        7: {'ShimmerAS': 0.90, 'ShimmerDurability': 0.15, 'ShimmerDuration': 4.0, 'InitialDelay': 4.0, 'HealThreshold': 0.60, 'MaxHealthHeal': 0.30},
    }

    # Noxus - gain stats when losing HP (combat-time mechanic)
    NOXUS_EFFECTS = {
        3: {'HPLostTrigger': 0.15},
        5: {'HPLostTrigger': 0.15},
        7: {'HPLostTrigger': 0.15},
        10: {'HPLostTrigger': 0.15},
    }

    # Ionia - multiple sub-effects (simplified: use Determination path stats)
    IONIA_EFFECTS = {
        3: {'FlatDamage': 20, 'Resists': 15, 'ADAP': 10, 'HealthPercent': 0.25},
        5: {'FlatDamage': 40, 'Resists': 25, 'ADAP': 15, 'HealthPercent': 0.30},
        7: {'FlatDamage': 60, 'Resists': 40, 'ADAP': 20, 'HealthPercent': 0.35},
        10: {'FlatDamage': 100, 'Resists': 75, 'ADAP': 100, 'HealthPercent': 0.75},
    }

    # =====================================================================
    # CLASS TRAITS (missing)
    # =====================================================================

    # Disruptor - Damage amp + DR for Disruptor units
    DISRUPTOR_EFFECTS = {
        2: {'DamageAmp': 0.18, 'DamageReduction': 0.10},
        4: {'DamageAmp': 0.40, 'DamageReduction': 0.10},
    }

    # =====================================================================
    # UNIQUE / SPECIAL TRAITS
    # =====================================================================

    # Darkin - Omnivamp for Darkin units
    DARKIN_EFFECTS = {
        1: {'Vamp': 0.15},
        2: {'Vamp': 0.15},
        3: {'Vamp': 0.15},
    }

    # World Ender (Aatrox) - Durability + mana reduction
    WORLD_ENDER_EFFECTS = {
        1: {'Durability': 0.20, 'ManaReduction': 10},
    }

    # Harvester (Fiddlesticks) - Enemy resist reduction + mana on kill
    HARVESTER_EFFECTS = {
        1: {'EnemyArmorMRReduction': 10, 'ManaPerEnemyDeath': 10},
    }

    # Dragonborn (Shyvana) - Ability damage reduction
    DRAGONBORN_EFFECTS = {
        1: {'AbilityDamageReduction': 0.08},
    }

    # Soulbound (Lucian) - Damage amp for Lucian, DR for Senna
    SOULBOUND_EFFECTS = {
        1: {'LucianDA': 0.07, 'SennaDR': 0.07},
    }

    # Eternal (Kindred) - Percent damage multiplier
    ETERNAL_EFFECTS = {
        1: {'PercentDamageMult': 3.25},
    }

    # The Boss (Sett) - Transform below HP threshold
    THE_BOSS_EFFECTS = {
        1: {'AttackSpeedPercent': 0.60, 'HealPercent': 0.15, 'MaxHealthThreshold': 0.45},
    }

    # Chosen Wolves (Ambessa + Kindred pair)
    CHOSEN_WOLVES_EFFECTS = {
        2: {'AmbessaBonusAD': 0.40, 'WolfDamage': 0.30},
    }

    # Dragonguards (Jarvan + Shyvana pair)
    DRAGONGUARDS_EFFECTS = {
        2: {'JarvanShieldShare': 1.0},
    }

    # Sentinels of Light (Lucian + Vayne pair)
    SENTINELS_EFFECTS = {
        2: {'LucianSennaAS': 0.50, 'NumBonusBolts': 2, 'BoltEffectiveness': 0.25},
    }

    # Poison Pals (Singed + Teemo pair)
    POISON_PALS_EFFECTS = {
        2: {'SingedAPGain': 2, 'TeemoDamageReq': 100},
    }

    # Timewinders (Ekko + Zilean)
    TIMEWINDERS_EFFECTS = {
        1: {'DamageShare': 0.10},
        2: {'DamageShare': 0.10},
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

    def apply_stat_traits(self, team: List['Unit'], trait_counts: Dict[str, int],
                         enemy_team: List['Unit'] = None):
        """Apply all stat-buffing traits to a team at combat start.

        Args:
            team: List of units on this team
            trait_counts: Dict of trait name -> count for this team
            enemy_team: Enemy team (needed for Harvester resist reduction)
        """
        # --- CLASS TRAITS ---
        self._apply_arcanist(team, trait_counts.get('Arcanist', 0))
        self._apply_defender(team, trait_counts.get('Defender', 0))
        self._apply_bruiser(team, trait_counts.get('Bruiser', 0))
        self._apply_slayer(team, trait_counts.get('Slayer', 0))
        self._apply_juggernaut(team, trait_counts.get('Juggernaut', 0))
        self._apply_invoker(team, trait_counts.get('Invoker', 0))
        self._apply_vanquisher(team, trait_counts.get('Vanquisher', 0))
        self._apply_longshot(team, trait_counts.get('Longshot', 0))
        self._apply_quickstriker(team, trait_counts.get('Quickstriker', 0))
        self._apply_gunslinger(team, trait_counts.get('Gunslinger', 0))
        self._apply_warden(team, trait_counts.get('Warden', 0))
        self._apply_disruptor(team, trait_counts.get('Disruptor', 0))

        # --- REGION TRAITS ---
        self._apply_demacia(team, trait_counts.get('Demacia', 0))
        self._apply_freljord(team, trait_counts.get('Freljord', 0))
        self._apply_void(team, trait_counts.get('Void', 0))
        self._apply_shurima(team, trait_counts.get('Shurima', 0))
        self._apply_yordle(team, trait_counts.get('Yordle', 0))
        self._apply_ixtal(team, trait_counts.get('Ixtal', 0))
        self._apply_zaun(team, trait_counts.get('Zaun', 0))
        self._apply_noxus(team, trait_counts.get('Noxus', 0))
        self._apply_ionia(team, trait_counts.get('Ionia', 0))

        # --- UNIQUE TRAITS ---
        self._apply_darkin(team, trait_counts.get('Darkin', 0))
        self._apply_world_ender(team, trait_counts.get('World Ender', 0))
        self._apply_dragonborn(team, trait_counts.get('Dragonborn', 0))
        self._apply_soulbound(team, trait_counts.get('Soulbound', 0))
        self._apply_eternal(team, trait_counts.get('Eternal', 0))
        self._apply_the_boss(team, trait_counts.get('The Boss', 0))

        # Harvester needs enemy team reference
        if enemy_team is not None:
            self._apply_harvester(team, [team, enemy_team],
                                  trait_counts.get('Harvester', 0))
        else:
            self._apply_harvester(team, [team],
                                  trait_counts.get('Harvester', 0))

        # --- PAIR SYNERGIES ---
        self._apply_pair_synergies(team, trait_counts)

    def _apply_arcanist(self, team: List['Unit'], count: int):
        """Apply Arcanist trait: Team AP + bonus for Arcanists."""
        effects = self.get_trait_tier(count, self.ARCANIST_EFFECTS)
        if not effects:
            return

        ally_ap = effects['AllyAP']
        bonus_ap = effects['BonusAP']

        for unit in team:
            # All allies get base AP
            unit.stats.ap += ally_ap

            # Arcanists get additional bonus
            if 'Arcanist' in unit.traits:
                unit.stats.ap += bonus_ap

    def _apply_defender(self, team: List['Unit'], count: int):
        """Apply Defender trait: Team armor/MR + bonus for Defenders."""
        effects = self.get_trait_tier(count, self.DEFENDER_EFFECTS)
        if not effects:
            return

        teamwide = effects['TeamwideArmorMR']
        bonus = effects['BonusArmorMR']

        for unit in team:
            # All allies get base armor/MR
            unit.stats.armor += teamwide
            unit.stats.magic_resist += teamwide

            # Defenders get additional bonus
            if 'Defender' in unit.traits:
                unit.stats.armor += bonus
                unit.stats.magic_resist += bonus

    def _apply_bruiser(self, team: List['Unit'], count: int):
        """Apply Bruiser trait: Team flat HP + bonus % HP for Bruisers."""
        effects = self.get_trait_tier(count, self.BRUISER_EFFECTS)
        if not effects:
            return

        flat_hp = effects['TeamFlatHealth']
        bonus_percent = effects['BonusPercentHealth']

        for unit in team:
            # All allies get flat HP
            unit.stats.max_hp += flat_hp
            unit.stats.hp += flat_hp

            # Bruisers get additional % HP
            if 'Bruiser' in unit.traits:
                bonus_hp = unit.base_stats.max_hp * bonus_percent
                unit.stats.max_hp += bonus_hp
                unit.stats.hp += bonus_hp

    def _apply_slayer(self, team: List['Unit'], count: int):
        """Apply Slayer trait: AD + Omnivamp for Slayers.

        Note: The missing HP AD scaling is handled during combat ticks.
        """
        effects = self.get_trait_tier(count, self.SLAYER_EFFECTS)
        if not effects:
            return

        bonus_ad_percent = effects['BonusAD']
        bonus_omnivamp = effects['BonusOmnivamp']

        for unit in team:
            if 'Slayer' in unit.traits:
                # AD bonus (percentage of base)
                ad_bonus = unit.base_stats.ad * bonus_ad_percent
                unit.stats.ad += ad_bonus
                # Omnivamp
                unit.stats.omnivamp += bonus_omnivamp
                # Store the scaling factor for combat calculations
                unit._slayer_ad_increase = effects['AmountIncrease']

    def _apply_juggernaut(self, team: List['Unit'], count: int):
        """Apply Juggernaut trait: Durability for Juggernauts.

        Note: The HP-conditional durability is handled during combat.
        """
        effects = self.get_trait_tier(count, self.JUGGERNAUT_EFFECTS)
        if not effects:
            return

        for unit in team:
            if 'Juggernaut' in unit.traits:
                # Store Juggernaut data for combat calculations
                unit._juggernaut_base_dr = effects['BaseDR']
                unit._juggernaut_increased_dr = effects['IncreasedDR']
                unit._juggernaut_heal_ratio = effects['HealRatio']
                # Apply base DR
                unit.stats.damage_reduction += effects['BaseDR']

    def _apply_invoker(self, team: List['Unit'], count: int):
        """Apply Invoker trait: Team mana regen + % mana increase for Invokers."""
        effects = self.get_trait_tier(count, self.INVOKER_EFFECTS)
        if not effects:
            return

        team_mana = effects['TeamBonusMana']
        percent_mana = effects['PercentManaIncrease']

        for unit in team:
            # All allies get mana regen
            if not hasattr(unit.stats, 'mana_regen'):
                unit.stats.mana_regen = 0
            unit.stats.mana_regen = getattr(unit.stats, 'mana_regen', 0) + team_mana

            # Invokers get % increased mana gain
            if 'Invoker' in unit.traits:
                unit._invoker_mana_increase = percent_mana

    def _apply_vanquisher(self, team: List['Unit'], count: int):
        """Apply Vanquisher trait: Crit chance + crit damage (abilities can crit)."""
        effects = self.get_trait_tier(count, self.VANQUISHER_EFFECTS)
        if not effects:
            return

        crit_chance = effects['BaseCritChance'] / 100  # Convert to decimal
        crit_dmg = effects['CritDmg'] / 100  # Convert to decimal

        for unit in team:
            if 'Vanquisher' in unit.traits:
                unit.stats.crit_chance += crit_chance
                unit.stats.crit_multiplier += crit_dmg
                # Mark that abilities can crit
                unit._vanquisher_ability_crit = True

    def _apply_longshot(self, team: List['Unit'], count: int):
        """Apply Longshot trait: Damage amp + per-hex bonus for Longshots."""
        effects = self.get_trait_tier(count, self.LONGSHOT_EFFECTS)
        if not effects:
            return

        base_amp = effects['BaseDamageAmp']
        per_hex = effects['PercentDamageIncrease']

        for unit in team:
            if 'Longshot' in unit.traits:
                unit.stats.damage_amp += base_amp
                # Store per-hex bonus for combat calculations
                unit._longshot_per_hex = per_hex

    def _apply_quickstriker(self, team: List['Unit'], count: int):
        """Apply Quickstriker trait: Team AS + bonus AS for Quickstrikers.

        Note: The target-missing-HP AS scaling is handled during combat.
        """
        effects = self.get_trait_tier(count, self.QUICKSTRIKER_EFFECTS)
        if not effects:
            return

        teamwide_as = effects['TeamwideAS']
        min_as = effects['MinBonusAS']
        max_as = effects['MaxBonusAS']

        for unit in team:
            # All allies get teamwide AS
            unit.stats.attack_speed += teamwide_as

            # Quickstrikers get additional scaling (stored for combat)
            if 'Quickstriker' in unit.traits:
                unit._quickstriker_min_as = min_as
                unit._quickstriker_max_as = max_as

    def _apply_gunslinger(self, team: List['Unit'], count: int):
        """Apply Gunslinger trait: AD + every Nth attack bonus damage."""
        effects = self.get_trait_tier(count, self.GUNSLINGER_EFFECTS)
        if not effects:
            return

        ad_percent = effects['AD']
        bonus_damage = effects['BonusDamage']
        num_attacks = effects['NumAttacks']

        for unit in team:
            if 'Gunslinger' in unit.traits:
                # AD bonus
                ad_bonus = unit.base_stats.ad * ad_percent
                unit.stats.ad += ad_bonus
                # Store bonus damage info for combat
                unit._gunslinger_bonus_damage = bonus_damage
                unit._gunslinger_attack_interval = num_attacks
                unit._gunslinger_attack_counter = 0

    def _apply_warden(self, team: List['Unit'], count: int):
        """Apply Warden trait: Setup shield thresholds for Wardens.

        Wardens gain shields when dropping below HP thresholds.
        """
        effects = self.get_trait_tier(count, self.WARDEN_EFFECTS)
        if not effects:
            return

        shield_percent = effects['PercentHealthShield']
        first_threshold = effects['FirstThreshold']
        second_threshold = effects['SecondThreshold']

        for unit in team:
            if 'Warden' in unit.traits:
                unit._warden_shield_percent = shield_percent
                unit._warden_first_threshold = first_threshold
                unit._warden_second_threshold = second_threshold
                unit._warden_first_triggered = False
                unit._warden_second_triggered = False

    # =====================================================================
    # REGION TRAIT METHODS
    # =====================================================================

    def _apply_demacia(self, team: List['Unit'], count: int):
        """Apply Demacia trait: Armor/MR for Demacia units."""
        effects = self.get_trait_tier(count, self.DEMACIA_EFFECTS)
        if not effects:
            return

        armor_mr = effects['ArmorMR']

        for unit in team:
            if 'Demacia' in unit.traits:
                unit.stats.armor += armor_mr
                unit.stats.magic_resist += armor_mr

    def _apply_freljord(self, team: List['Unit'], count: int):
        """Apply Freljord trait: HP% + damage amp for Freljord units."""
        effects = self.get_trait_tier(count, self.FRELJORD_EFFECTS)
        if not effects:
            return

        hp_percent = effects['HealthPercent']
        damage_amp = effects['DA']

        for unit in team:
            if 'Freljord' in unit.traits:
                bonus_hp = unit.base_stats.max_hp * hp_percent
                unit.stats.max_hp += bonus_hp
                unit.stats.hp += bonus_hp
                unit.stats.damage_amp += damage_amp

    def _apply_void(self, team: List['Unit'], count: int):
        """Apply Void trait: Attack speed for Void units."""
        effects = self.get_trait_tier(count, self.VOID_EFFECTS)
        if not effects:
            return

        bonus_as = effects['BonusAS']

        for unit in team:
            if 'Void' in unit.traits:
                unit.stats.attack_speed += bonus_as

    def _apply_shurima(self, team: List['Unit'], count: int):
        """Apply Shurima trait: HP% + heal/sec + armor/MR at higher tiers."""
        effects = self.get_trait_tier(count, self.SHURIMA_EFFECTS)
        if not effects:
            return

        hp_percent = effects['BonusHealth']
        heal_per_sec = effects['HealthRestorePerSecond']
        armor_mr = effects.get('ArmorMR', 0)

        for unit in team:
            if 'Shurima' in unit.traits:
                bonus_hp = unit.base_stats.max_hp * hp_percent
                unit.stats.max_hp += bonus_hp
                unit.stats.hp += bonus_hp
                # Store heal per second for combat-time application
                unit._shurima_heal_per_sec = heal_per_sec
                if armor_mr:
                    unit.stats.armor += armor_mr
                    unit.stats.magic_resist += armor_mr

    def _apply_yordle(self, team: List['Unit'], count: int):
        """Apply Yordle trait: AS + flat HP for Yordle units."""
        effects = self.get_trait_tier(count, self.YORDLE_EFFECTS)
        if not effects:
            return

        bonus_as = effects['AS']
        bonus_hp = effects['BonusHealth']

        for unit in team:
            if 'Yordle' in unit.traits:
                unit.stats.attack_speed += bonus_as
                unit.stats.max_hp += bonus_hp
                unit.stats.hp += bonus_hp

    def _apply_ixtal(self, team: List['Unit'], count: int):
        """Apply Ixtal trait: Flat HP per pair of Ixtal units + healing."""
        effects = self.get_trait_tier(count, self.IXTAL_EFFECTS)
        if not effects:
            return

        hp_per_pair = effects['BonusHealthPairs']
        heal = effects['Heal']
        num_pairs = count // 2

        for unit in team:
            if 'Ixtal' in unit.traits:
                bonus_hp = hp_per_pair * num_pairs
                unit.stats.max_hp += bonus_hp
                unit.stats.hp += bonus_hp
                # Store heal rate for combat-time
                unit._ixtal_heal_per_sec = heal

    def _apply_zaun(self, team: List['Unit'], count: int):
        """Apply Zaun trait: Setup Shimmer Fuse data for combat-time activation.

        Zaun units gain a delayed AS + durability burst during combat.
        """
        effects = self.get_trait_tier(count, self.ZAUN_EFFECTS)
        if not effects:
            return

        for unit in team:
            if 'Zaun' in unit.traits:
                unit._zaun_shimmer_as = effects['ShimmerAS']
                unit._zaun_shimmer_durability = effects['ShimmerDurability']
                unit._zaun_shimmer_duration = effects['ShimmerDuration']
                unit._zaun_initial_delay = effects['InitialDelay']
                unit._zaun_shimmer_active = False
                unit._zaun_shimmer_triggered = False

    def _apply_noxus(self, team: List['Unit'], count: int):
        """Apply Noxus trait: Setup HP-loss trigger for combat-time activation.

        Noxus units gain stats when they lose 15% of max HP.
        """
        effects = self.get_trait_tier(count, self.NOXUS_EFFECTS)
        if not effects:
            return

        for unit in team:
            if 'Noxus' in unit.traits:
                unit._noxus_hp_trigger = effects['HPLostTrigger']
                unit._noxus_triggered = False
                unit._noxus_tier = count

    def _apply_ionia(self, team: List['Unit'], count: int):
        """Apply Ionia trait: Simplified stat buffs for Ionia units.

        In the real game, each Ionia unit picks a random 'path' (Spirit,
        Determination, Enlightenment, etc.). Simplified to average stat buffs.
        """
        effects = self.get_trait_tier(count, self.IONIA_EFFECTS)
        if not effects:
            return

        resists = effects['Resists']
        adap = effects['ADAP']
        hp_percent = effects['HealthPercent']

        for unit in team:
            if 'Ionia' in unit.traits:
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

    def _apply_disruptor(self, team: List['Unit'], count: int):
        """Apply Disruptor trait: Damage amp + DR for Disruptor units."""
        effects = self.get_trait_tier(count, self.DISRUPTOR_EFFECTS)
        if not effects:
            return

        damage_amp = effects['DamageAmp']
        damage_reduction = effects['DamageReduction']

        for unit in team:
            if 'Disruptor' in unit.traits:
                unit.stats.damage_amp += damage_amp
                unit.stats.damage_reduction += damage_reduction

    # =====================================================================
    # UNIQUE / SPECIAL TRAIT METHODS
    # =====================================================================

    def _apply_darkin(self, team: List['Unit'], count: int):
        """Apply Darkin trait: Omnivamp for Darkin units."""
        effects = self.get_trait_tier(count, self.DARKIN_EFFECTS)
        if not effects:
            return

        vamp = effects['Vamp']

        for unit in team:
            if 'Darkin' in unit.traits:
                unit.stats.omnivamp += vamp

    def _apply_world_ender(self, team: List['Unit'], count: int):
        """Apply World Ender trait: Durability + mana reduction for Aatrox."""
        effects = self.get_trait_tier(count, self.WORLD_ENDER_EFFECTS)
        if not effects:
            return

        durability = effects['Durability']
        mana_reduction = effects['ManaReduction']

        for unit in team:
            if 'World Ender' in unit.traits:
                unit.stats.damage_reduction += durability
                unit.stats.mana = max(0, unit.stats.mana - mana_reduction)

    def _apply_harvester(self, team: List['Unit'], all_teams: List[List['Unit']], count: int):
        """Apply Harvester trait: Reduce enemy resists + mana on kill.

        Args:
            team: Friendly team
            all_teams: All teams (to apply resist reduction to enemies)
            count: Number of Harvester units
        """
        effects = self.get_trait_tier(count, self.HARVESTER_EFFECTS)
        if not effects:
            return

        resist_reduction = effects['EnemyArmorMRReduction']
        mana_per_kill = effects['ManaPerEnemyDeath']

        # Apply resist reduction to enemy team
        for other_team in all_teams:
            if other_team is not team:
                for enemy in other_team:
                    enemy.stats.armor = max(0, enemy.stats.armor - resist_reduction)
                    enemy.stats.magic_resist = max(0, enemy.stats.magic_resist - resist_reduction)

        # Store mana-on-kill for combat-time
        for unit in team:
            if 'Harvester' in unit.traits:
                unit._harvester_mana_per_kill = mana_per_kill

    def _apply_dragonborn(self, team: List['Unit'], count: int):
        """Apply Dragonborn trait: Ability damage reduction for Shyvana."""
        effects = self.get_trait_tier(count, self.DRAGONBORN_EFFECTS)
        if not effects:
            return

        ability_dr = effects['AbilityDamageReduction']

        for unit in team:
            if 'Dragonborn' in unit.traits:
                unit._dragonborn_ability_dr = ability_dr

    def _apply_soulbound(self, team: List['Unit'], count: int):
        """Apply Soulbound trait: Damage amp for Lucian."""
        effects = self.get_trait_tier(count, self.SOULBOUND_EFFECTS)
        if not effects:
            return

        lucian_da = effects['LucianDA']

        for unit in team:
            if 'Soulbound' in unit.traits:
                unit.stats.damage_amp += lucian_da

    def _apply_eternal(self, team: List['Unit'], count: int):
        """Apply Eternal trait: Increased damage multiplier for Kindred."""
        effects = self.get_trait_tier(count, self.ETERNAL_EFFECTS)
        if not effects:
            return

        damage_mult = effects['PercentDamageMult']

        for unit in team:
            if 'Eternal' in unit.traits:
                unit._eternal_damage_mult = damage_mult

    def _apply_the_boss(self, team: List['Unit'], count: int):
        """Apply The Boss trait: Transform data for Sett below HP threshold."""
        effects = self.get_trait_tier(count, self.THE_BOSS_EFFECTS)
        if not effects:
            return

        for unit in team:
            if 'The Boss' in unit.traits:
                unit._boss_as_bonus = effects['AttackSpeedPercent']
                unit._boss_heal_percent = effects['HealPercent']
                unit._boss_hp_threshold = effects['MaxHealthThreshold']
                unit._boss_transformed = False

    def _apply_pair_synergies(self, team: List['Unit'], trait_counts: Dict[str, int]):
        """Apply pair synergies that require specific champion combinations."""
        # Build name lookup
        team_api_names = {u.api_name for u in team}
        team_by_api = {u.api_name: u for u in team}

        # Chosen Wolves: Ambessa + Kindred
        if 'TFT16_Ambessa' in team_api_names and 'TFT16_Kindred' in team_api_names:
            effects = self.CHOSEN_WOLVES_EFFECTS[2]
            ambessa = team_by_api['TFT16_Ambessa']
            ad_bonus = ambessa.base_stats.ad * effects['AmbessaBonusAD']
            ambessa.stats.ad += ad_bonus
            kindred = team_by_api['TFT16_Kindred']
            kindred._wolf_bonus_damage = effects['WolfDamage']

        # Dragonguards: Jarvan IV + Shyvana
        if 'TFT16_JarvanIV' in team_api_names and 'TFT16_Shyvana' in team_api_names:
            effects = self.DRAGONGUARDS_EFFECTS[2]
            jarvan = team_by_api['TFT16_JarvanIV']
            jarvan._dragonguard_shield_share = effects['JarvanShieldShare']

        # Sentinels of Light: Lucian + Vayne
        if 'TFT16_Lucian' in team_api_names and 'TFT16_Vayne' in team_api_names:
            effects = self.SENTINELS_EFFECTS[2]
            lucian = team_by_api['TFT16_Lucian']
            lucian.stats.attack_speed += effects['LucianSennaAS']
            lucian._sentinel_bonus_bolts = effects['NumBonusBolts']
            lucian._sentinel_bolt_effectiveness = effects['BoltEffectiveness']

        # Poison Pals: Singed + Teemo
        if 'TFT16_Singed' in team_api_names and 'TFT16_Teemo' in team_api_names:
            effects = self.POISON_PALS_EFFECTS[2]
            singed = team_by_api['TFT16_Singed']
            singed._poison_pals_ap_gain = effects['SingedAPGain']
            singed._poison_pals_damage_req = effects['TeemoDamageReq']

        # Timewinders: Ekko + Zilean
        if 'TFT16_Ekko' in team_api_names and 'TFT16_Zilean' in team_api_names:
            effects = self.TIMEWINDERS_EFFECTS[2]
            for api_name in ['TFT16_Ekko', 'TFT16_Zilean']:
                unit = team_by_api[api_name]
                unit._timewinder_damage_share = effects['DamageShare']


# =============================================================================
# AUGMENT MANAGER - Handle Augment Effects
# =============================================================================

# Try to load augment data
try:
    _AUGMENT_DATA_PATH = Path(__file__).parent.parent.parent / "data" / "api" / "processed" / "augments_set16.json"
    if _AUGMENT_DATA_PATH.exists():
        with open(_AUGMENT_DATA_PATH, 'r', encoding='utf-8') as f:
            _RAW_AUGMENTS = json.load(f)
        _AUGMENTS_DATA = {a['apiName']: a for a in _RAW_AUGMENTS if not a.get('disabled')}
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
        'Health': 'max_hp',
        'HP': 'max_hp',
        'AD': 'ad',
        'AttackDamage': 'ad',
        'AP': 'ap',
        'AbilityPower': 'ap',
        'Armor': 'armor',
        'MR': 'magic_resist',
        'MagicResist': 'magic_resist',
        'AttackSpeed': 'attack_speed',
        'AS': 'attack_speed',
        'CritChance': 'crit_chance',
        'CritDamage': 'crit_multiplier',
        'Omnivamp': 'omnivamp',
        'DamageAmp': 'damage_amp',
        'Durability': 'damage_reduction',
        'ManaRegen': 'mana_regen',  # Special handling
        'Mana': 'mana',
        'Range': 'range',
    }

    # Traits that can be checked for conditional augments
    # Maps lowercase search terms to actual trait display names (as used in combat_data.json)
    TRAIT_KEYWORDS = {
        'yordle': 'Yordle',
        'slayer': 'Slayer',
        'ionia': 'Ionia',
        'noxus': 'Noxus',
        'demacia': 'Demacia',
        'bilgewater': 'Bilgewater',
        'void': 'Void',
        'shadow isles': 'Shadow Isles',
        'piltover': 'Piltover',
        'arcanist': 'Arcanist',
        'sorcerer': 'Arcanist',  # Backend uses Sorcerer, frontend uses Arcanist
        'automata': 'Automata',
        'freljord': 'Freljord',
        'targon': 'Targon',
        'shurima': 'Shurima',
        'zaun': 'Zaun',
        'bruiser': 'Bruiser',
        'defender': 'Defender',
        'invoker': 'Invoker',
        'juggernaut': 'Juggernaut',
        'longshot': 'Longshot',
        'quickstriker': 'Quickstriker',
        'vanquisher': 'Vanquisher',
        'warden': 'Warden',
        'gunslinger': 'Gunslinger',
        'ixtal': 'Ixtal',
    }

    def __init__(self):
        """Initialize augment manager."""
        self.active_augments: List[str] = []  # List of active augment apiNames
        self.augment_data = _AUGMENTS_DATA if _AUGMENTS_LOADED else {}
        self.hex_effects: Dict[Tuple[int, int], Dict] = {}  # position -> effect info
        self.event_listeners: Dict[str, List[Dict]] = {
            'on_takedown': [],
            'on_cast': [],
            'on_damage_dealt': [],
            'on_round_start': [],
        }
        # Track permanent stat gains from on-event augments
        self.permanent_bonuses: Dict[str, Dict[str, float]] = {}  # unit_id -> stat_bonuses

    def reset(self):
        """Reset augment state for new combat."""
        self.hex_effects.clear()
        self.event_listeners = {
            'on_takedown': [],
            'on_cast': [],
            'on_damage_dealt': [],
            'on_round_start': [],
        }
        self.permanent_bonuses.clear()

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
                    if data.get('name', '').lower() == name.lower():
                        self.active_augments.append(api_name)
                        break
                    elif data.get('en_name', '').lower() == name.lower():
                        self.active_augments.append(api_name)
                        break

    def get_augment_info(self, api_name: str) -> Optional[Dict]:
        """Get augment data by apiName."""
        return self.augment_data.get(api_name)

    def apply_augments(self, team: List['Unit'], trait_counts: Dict[str, int]):
        """Apply all active augments to a team at combat start.

        Args:
            team: List of units on this team
            trait_counts: Dict of trait name -> count for this team
        """
        for augment_name in self.active_augments:
            augment = self.get_augment_info(augment_name)
            if not augment:
                continue

            effects = augment.get('effects', {})
            desc = augment.get('desc', '').lower()

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
                self._apply_item_conditional_augment(team, augment)

    def _is_team_stat_augment(self, augment: Dict) -> bool:
        """Check if augment is a simple team-wide stat buff."""
        effects = augment.get('effects', {})
        desc = augment.get('desc', '').lower()

        # Has stat effects and applies to team
        stat_keys = ['Health', 'HP', 'AD', 'AP', 'Armor', 'MR', 'AttackSpeed',
                     'DamageAmp', 'Durability', 'Omnivamp', 'CritChance']

        has_stat_effects = any(k in effects or k.lower() in [s.lower() for s in effects.keys()]
                               for k in stat_keys)

        applies_to_team = ('your team' in desc or 'all allies' in desc or
                           'your units' in desc or not 'your strongest' in desc)

        return has_stat_effects and applies_to_team

    def _is_hex_augment(self, augment: Dict) -> bool:
        """Check if augment creates special hexes."""
        desc = augment.get('desc', '').lower()
        return 'hex' in desc and ('gain a' in desc or 'axiom' in augment.get('name', '').lower())

    def _is_event_augment(self, augment: Dict) -> bool:
        """Check if augment triggers on events."""
        desc = augment.get('desc', '').lower()
        return 'takedown' in desc or 'when' in desc and ('cast' in desc or 'kill' in desc)

    def _is_item_conditional_augment(self, augment: Dict) -> bool:
        """Check if augment requires holding specific items."""
        desc = augment.get('desc', '').lower()
        return 'holding' in desc or 'equipped' in desc or 'spatula' in desc

    # =========================================================================
    # HERO AUGMENTS - Champion-specific augments that modify abilities
    # =========================================================================

    # Hero augment definitions: apiName -> champion api_name and effects
    HERO_AUGMENTS = {
        'TFT16_Augment_XinZhaoCarry': {
            'champion': 'TFT16_XinZhao',
            'name': 'Trials of Twilight',
            'effects': {
                'constant_strikes': True,      # Constantly strikes nearby enemies
                'execute_threshold': 0.15,     # Execute enemies below 15% HP
                'transform_to_zaahen': True,   # Transform to Zaahen after 5 rounds as 3-star
                'rounds_to_transform': 5,
            }
        },
        'TFT16_Augment_ShadowIsles_RuinedKing': {
            'champion': 'TFT16_Viego',
            'name': 'The Ruined King',
            'effects': {
                'passive_share_percent': 0.30,  # Share 30% of passive with SI allies
                'soul_req_upgrade': 100,        # Ability upgrades after 100 souls
                'upgraded_ability': True,       # Track if ability has been upgraded
            }
        },
        'TFT16_Augment_RumbleCarry': {
            'champion': 'TFT16_Rumble',
            'name': 'Artillery Barrage',
            'effects': {
                'bonus_range': 7,               # +7 Range
                'constant_missiles': True,      # Constantly fires missiles
                'missile_as_scaling': True,     # Missile rate scales with AS
            }
        },
        'TFT16_Augment_IllaoiCarry': {
            'champion': 'TFT16_Illaoi',
            'name': 'Leap of Faith',
            'effects': {
                'becomes_fighter': True,        # Role changes to Fighter
                'slam_ability': True,           # Ability replaced with airborne slam
                'recast_on_kill': True,         # Recast when kills target
            }
        },
    }

    def _is_hero_augment(self, augment_name: str) -> bool:
        """Check if augment is a hero augment (champion-specific ability modifier)."""
        return augment_name in self.HERO_AUGMENTS

    def _apply_hero_augment(self, team: List['Unit'], augment_name: str, augment: Dict):
        """Apply a hero augment to the appropriate champion on the team.

        Hero augments modify a specific champion's abilities and behavior.
        """
        hero_data = self.HERO_AUGMENTS.get(augment_name)
        if not hero_data:
            return

        champion_api = hero_data['champion']
        effects = hero_data['effects']

        # Find the strongest matching champion on the team
        matching_units = [u for u in team if u.api_name == champion_api and u.is_alive]
        if not matching_units:
            return

        # Get strongest by star level, then items, then stats
        target_unit = max(matching_units, key=lambda u: (
            u.star_level,
            len(u.items),
            u.stats.ad + u.stats.ap
        ))

        # Apply hero augment flag and effects
        target_unit._hero_augment = augment_name
        target_unit._hero_augment_effects = effects.copy()

        # Apply immediate stat changes
        if augment_name == 'TFT16_Augment_RumbleCarry':
            # Artillery Barrage: +7 Range
            target_unit.stats.range += effects.get('bonus_range', 7)

        elif augment_name == 'TFT16_Augment_IllaoiCarry':
            # Leap of Faith: Change role to Fighter (affects traits)
            if effects.get('becomes_fighter'):
                target_unit._original_role = getattr(target_unit, 'role', 'Bruiser')
                target_unit.role = 'Fighter'

        elif augment_name == 'TFT16_Augment_ShadowIsles_RuinedKing':
            # The Ruined King: Share passive with SI allies
            share_pct = effects.get('passive_share_percent', 0.30)
            for ally in team:
                if ally != target_unit and ally.is_alive and 'Shadow Isles' in ally.traits:
                    # Viego's passive gives stacking AD - share 30%
                    ally._viego_passive_share = share_pct

    def get_hero_augment_for_unit(self, unit: 'Unit') -> Optional[Dict]:
        """Get hero augment data for a unit if they have one active."""
        augment_name = getattr(unit, '_hero_augment', None)
        if augment_name:
            return {
                'name': augment_name,
                'effects': getattr(unit, '_hero_augment_effects', {}),
                'data': self.HERO_AUGMENTS.get(augment_name, {})
            }
        return None

    def _apply_team_stat_augment(self, team: List['Unit'], augment: Dict,
                                  trait_counts: Dict[str, int]):
        """Apply team-wide stat buffs from an augment."""
        effects = augment.get('effects', {})
        desc = augment.get('desc', '').lower()

        # Check for trait-conditional bonuses
        enhanced_active = False
        conditional_trait = None
        for keyword, trait_name in self.TRAIT_KEYWORDS.items():
            if keyword in desc and ('if' in desc or 'increased' in desc):
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
            if effect_key.startswith('{'):
                continue  # Skip hashed/unknown keys

            # Check for enhanced version
            stat_key = effect_key
            stat_value = value

            if enhanced_active and 'Enhanced' in effect_key:
                stat_key = effect_key.replace('Enhanced', '')
                stat_value = value
            elif 'Enhanced' in effect_key:
                continue  # Skip enhanced value if trait not active

            # Map to CombatStats attribute
            combat_stat = self.STAT_MAPPINGS.get(stat_key)
            if not combat_stat:
                continue

            # Apply to all units
            for unit in team:
                self._apply_stat_bonus(unit, combat_stat, stat_value)

    def _apply_stat_bonus(self, unit: 'Unit', stat_name: str, value: float):
        """Apply a stat bonus to a unit.

        Args:
            unit: The unit to modify
            stat_name: CombatStats attribute name
            value: The bonus value (may be flat or percentage based on stat)
        """
        if not hasattr(unit.stats, stat_name):
            return

        current = getattr(unit.stats, stat_name)

        # Determine if flat or percentage based on typical TFT conventions
        if stat_name in ['max_hp', 'armor', 'magic_resist', 'ap']:
            # These are typically flat values or percentages < 1 mean %
            if abs(value) < 1:
                # Percentage of current
                new_value = current * (1 + value)
            else:
                # Flat addition
                new_value = current + value
        elif stat_name in ['attack_speed', 'crit_chance', 'damage_amp',
                           'damage_reduction', 'omnivamp']:
            # These are percentage-based (0.15 = 15%)
            new_value = current + value
        elif stat_name == 'ad':
            # AD is often percentage based in TFT
            if abs(value) < 1:
                new_value = current * (1 + value)
            else:
                new_value = current + value
        elif stat_name == 'range':
            new_value = current + int(value)
        else:
            new_value = current + value

        setattr(unit.stats, stat_name, new_value)

        # Also update max_hp in hp if it increased
        if stat_name == 'max_hp' and new_value > current:
            unit.stats.hp += (new_value - current)

    def _setup_hex_augment(self, team: List['Unit'], augment: Dict):
        """Setup hex-based augment effects (Axioms, etc.)."""
        effects = augment.get('effects', {})
        name = augment.get('name', '')

        hex_radius = effects.get('HexRadius', 2)

        # Extract effect parameters
        hex_effect = {
            'name': name,
            'radius': hex_radius,
            'effects': {},
        }

        # Map effects
        if 'Resistances' in effects:
            hex_effect['effects']['armor'] = effects['Resistances']
            hex_effect['effects']['magic_resist'] = effects['Resistances']
        if 'AttackSpeed' in effects:
            hex_effect['effects']['attack_speed'] = effects['AttackSpeed']
        if 'ManaRegen' in effects:
            hex_effect['effects']['mana_regen'] = effects['ManaRegen']
        if 'StunDuration' in effects:
            hex_effect['stun_on_threshold'] = True
            hex_effect['stun_duration'] = effects['StunDuration']
            hex_effect['health_threshold'] = effects.get('HealthThreshold', 0.5)
        if 'ShredPercent' in effects:
            hex_effect['shred'] = effects['ShredPercent']
            hex_effect['shred_duration'] = effects.get('Duration', 5)
        if 'SunderPercent' in effects:
            hex_effect['sunder'] = effects['SunderPercent']
            hex_effect['sunder_duration'] = effects.get('Duration', 5)

        # For now, place hex at center of team's formation
        if team:
            avg_row = sum(u.position[0] for u in team) / len(team)
            avg_col = sum(u.position[1] for u in team) / len(team)
            hex_pos = (int(avg_row), int(avg_col))
            self.hex_effects[hex_pos] = hex_effect

    def _register_event_augment(self, team: List['Unit'], augment: Dict):
        """Register event-triggered augments."""
        desc = augment.get('desc', '').lower()
        effects = augment.get('effects', {})
        name = augment.get('name', '')

        event_data = {
            'name': name,
            'effects': effects,
            'augment': augment,
        }

        if 'takedown' in desc:
            self.event_listeners['on_takedown'].append(event_data)
        if 'cast' in desc and 'when' in desc:
            self.event_listeners['on_cast'].append(event_data)

    def _apply_item_conditional_augment(self, team: List['Unit'], augment: Dict):
        """Apply augments that check for specific items."""
        effects = augment.get('effects', {})
        desc = augment.get('desc', '').lower()

        # Check for Spatula/Frying Pan items (U.R.F. augment)
        spatula_items = ['Spatula', 'FryingPan']
        for unit in team:
            has_qualifying_item = any(
                any(s.lower() in item.name.lower() for s in spatula_items)
                for item in unit.items
            )

            if has_qualifying_item:
                # Apply stat bonuses
                if 'AttackSpeed' in effects:
                    self._apply_stat_bonus(unit, 'attack_speed', effects['AttackSpeed'])
                if 'ManaRegen' in effects:
                    # Store mana regen for per-tick application
                    unit_id = f"{unit.api_name}_{id(unit)}"
                    if unit_id not in self.permanent_bonuses:
                        self.permanent_bonuses[unit_id] = {}
                    self.permanent_bonuses[unit_id]['mana_regen'] = effects['ManaRegen']

    def apply_hex_effects(self, unit: 'Unit') -> Dict[str, float]:
        """Get hex effects that apply to a unit based on their position.

        Args:
            unit: The unit to check

        Returns:
            Dict of stat bonuses from active hex effects
        """
        bonuses = {}
        for hex_pos, hex_effect in self.hex_effects.items():
            radius = hex_effect.get('radius', 2)
            if HexGrid.hex_distance(unit.position, hex_pos) <= radius:
                for stat, value in hex_effect.get('effects', {}).items():
                    bonuses[stat] = bonuses.get(stat, 0) + value
        return bonuses

    def on_takedown(self, killer: 'Unit', victim: 'Unit'):
        """Process takedown events for augments.

        Args:
            killer: The unit that got the kill
            victim: The unit that died
        """
        for listener in self.event_listeners['on_takedown']:
            effects = listener.get('effects', {})

            # Bringer of Ruin style - permanent stat gains
            if 'AP' in effects:
                killer.stats.ap += effects['AP']
            if 'MaxHealth' in effects:
                killer.stats.max_hp += effects['MaxHealth']
                killer.stats.hp += effects['MaxHealth']
            if 'AD' in effects:
                killer.stats.ad += effects['AD']

    def on_ability_cast(self, caster: 'Unit'):
        """Process ability cast events for augments."""
        for listener in self.event_listeners['on_cast']:
            effects = listener.get('effects', {})
            # Apply per-cast bonuses if any

    def get_all_augment_names(self) -> List[str]:
        """Get list of all available augment names."""
        return [data.get('name', api_name) for api_name, data in self.augment_data.items()]

    def get_combat_augments(self) -> List[Dict]:
        """Get list of augments that affect combat (not economy/shop augments)."""
        combat_augments = []
        combat_keywords = ['damage', 'attack', 'health', 'armor', 'resist', 'shield',
                          'heal', 'ability', 'mana', 'cast', 'attack speed', 'omnivamp',
                          'crit', 'durability']

        for api_name, data in self.augment_data.items():
            desc = data.get('desc', '').lower()
            if any(kw in desc for kw in combat_keywords):
                combat_augments.append({
                    'apiName': api_name,
                    'name': data.get('name', ''),
                    'desc': data.get('desc', ''),
                    'effects': data.get('effects', {}),
                    'associatedTraits': data.get('associatedTraits', []),
                })

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
        """Create an item instance from name with effects."""
        # Check alias first
        resolved_name = ItemDatabase.ALIASES.get(name, name)

        if resolved_name not in ItemDatabase.ITEMS:
            print(f"Warning: Item '{name}' not found in database")
            return None

        stats = ItemDatabase.ITEMS[resolved_name].copy()

        # Get item effects
        try:
            from .item_effects import (
                get_item_on_hit, get_item_on_ability,
                get_item_on_damage_dealt, get_item_on_damage_taken
            )
            on_hit = get_item_on_hit(resolved_name)
            on_ability = get_item_on_ability(resolved_name)
            on_damage_dealt = get_item_on_damage_dealt(resolved_name)
            on_damage_taken = get_item_on_damage_taken(resolved_name)
        except ImportError:
            on_hit = None
            on_ability = None
            on_damage_dealt = None
            on_damage_taken = None

        return Item(
            name=resolved_name,
            stats=stats,
            on_hit=on_hit,
            on_ability_cast=on_ability,
            on_damage_dealt=on_damage_dealt,
            on_damage_taken=on_damage_taken
        )


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

        # Helper to extract star-level values from a variable that may be
        # a list [0, 1star, 2star, 3star, ...] or a dict {'1star': v, ...}
        def _star_val(var, star):
            if isinstance(var, list):
                return (var[star] if star < len(var) else 0) or 0
            elif isinstance(var, dict):
                return (var.get(f'{star}star', 0)) or 0
            return 0

        # Try to find primary damage variable
        damage_by_star = {1: 0, 2: 0, 3: 0}
        damage_var = None
        num_hits = 1  # For multi-hit abilities

        # Check for multi-hit indicators (missiles, hits, etc.)
        for key in ['NumMissiles', 'NumHits', 'NumBounces', 'NumAttacks']:
            if key in variables:
                hit_var = variables[key]
                num_hits = _star_val(hit_var, star_level) or 1
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
                if isinstance(val, list) and len(val) >= 4:
                    damage_var = val
                    break
                elif isinstance(val, dict) and '1star' in val:
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

        # Augment manager for augment effects
        self.augment_manager = AugmentManager()

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

                # Award Shadow Isles souls for takedown
                if self.trait_manager.shadow_isles_count >= 2 and attacker.team != defender.team:
                    # Get victim's cost (from champion data)
                    victim_data = self.champions.get(defender.api_name, {})
                    victim_cost = victim_data.get('cost', 1)
                    victim_star = defender.star_level

                    souls = self.trait_manager.award_soul(victim_cost, victim_star)
                    if souls > 0:
                        self.log_event('shadow_isles_soul', killer=attacker.name,
                                      victim=defender.name, souls=souls,
                                      total=self.trait_manager.shadow_isles_souls,
                                      victim_cost=victim_cost, victim_star=victim_star)

        self.log_event('damage', source=source, attacker=attacker.name,
                      defender=defender.name, damage=round(actual_damage, 1),
                      damage_type=damage_type.value,
                      defender_hp=round(defender.stats.hp, 1),
                      defender_alive=defender.is_alive)

        # Check for HP threshold effects (Edge of Night, Zhonya's)
        if defender.is_alive:
            self.check_hp_threshold_effects(defender)

        # Trigger item on-damage-dealt effects for attacker
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
            num_attacks_data = ability_vars.get('NumAttacks')
            threshold = _star_val(num_attacks_data, unit.star_level, 18)

            if unit.attacks_performed > threshold:
                is_jinx_rockets = True
                # Rocket form: Gets AD bonus from ability
                ad_bonus_data = ability_vars.get('ADDamage')
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
                ap_dmg_data = ability_vars.get('APDamage')
                base_damage = _star_val(ap_dmg_data, unit.star_level, 150)

                # Get enhanced attack values
                as_bonus_data = ability_vars.get('ASBonus') or ability_vars.get('AttackSpeed')
                as_bonus = _star_val(as_bonus_data, unit.star_level, 100) / 100  # Convert to decimal
                on_hit_data = ability_vars.get('OnHitDamage') or ability_vars.get('APOnHit')
                on_hit_dmg = _star_val(on_hit_data, unit.star_level, 50)
                num_attacks_data = ability_vars.get('NumAttacks')
                num_enhanced = int(_star_val(num_attacks_data, unit.star_level, 4))

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

            # Trigger item on-ability effects
            for item in unit.items:
                if item.on_ability_cast:
                    item.on_ability_cast(self, unit)

            self.log_event('ability_cast', unit=unit.name, ability=ability.name,
                          targets=[t.name for t in enemies_in_range[:1]])
            return  # Fizz ability fully handled

        # Handle Kai'Sa (and other FormSwapper champions) - uses higher of AD or AP damage
        if 'FormSwapper' in unit.role:
            ad_dmg_data = ability_vars.get('ADDamage')
            ap_dmg_data = ability_vars.get('APDamage')

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
            num_targets_data = ability_vars.get('NumTargets')
            num_targets = int(_star_val(num_targets_data, unit.star_level, 4))
            num_missiles_data = ability_vars.get('NumMissiles')
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
        if 'Tank' in unit.role:
            # Check for armor scaling (e.g., Braum's ArmorDamage)
            armor_dmg_data = ability_vars.get('ArmorDamage')
            if armor_dmg_data:
                armor_scaling = _star_val(armor_dmg_data, unit.star_level, 0)
                total_damage += unit.stats.armor * armor_scaling

            # Check for HP scaling (e.g., percentage of max HP damage)
            hp_pct_data = ability_vars.get('HealthPercent') or ability_vars.get('PercentHealthDamage')
            if hp_pct_data:
                hp_scaling = _star_val(hp_pct_data, unit.star_level, 0)
                total_damage += unit.stats.max_hp * hp_scaling

            # Check for shield abilities (Galio, Nautilus, Shen, Poppy)
            shield_data = ability_vars.get('Shield') or ability_vars.get('ShieldAmt') or ability_vars.get('APShield')
            if shield_data:
                shield_amount = _star_val(shield_data, unit.star_level, 0)
                # Nautilus also has percent HP shield
                pct_hp_shield = ability_vars.get('PercentHealthShield')
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

        # Trigger item on-ability effects
        for item in unit.items:
            if item.on_ability_cast:
                item.on_ability_cast(self, unit)

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

        # Shadow Isles soul collection setup
        shadow_isles_count = trait_counts.get('Shadow Isles', 0)
        if shadow_isles_count >= 2:
            shadow_isles_units = [u for u in team if 'Shadow Isles' in u.traits]
            self.trait_manager.set_shadow_isles_count(shadow_isles_count, shadow_isles_units)
            self.trait_manager.apply_shadow_isles_stats(team)
            self.log_event('shadow_isles_setup', count=shadow_isles_count,
                          units=[u.name for u in shadow_isles_units],
                          stat_bonus=self.trait_manager.get_shadow_isles_stat_bonus())

    def run_combat(self, team0: List[Unit], team1: List[Unit],
                  max_time: float = 60.0, verbose: bool = False,
                  team0_augments: List[str] = None,
                  team1_augments: List[str] = None,
                  seed: int = None) -> Dict:
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
        # Set random seed for determinism if provided
        if seed is not None:
            random.seed(seed)

        # Reset state
        self.time = 0.0
        self.combat_log = []
        self.units = team0 + team1
        self.projectiles = []

        # Reset Shadow Isles souls for new combat
        self.trait_manager.reset_shadow_isles()

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

        # Apply augments if provided (after traits so they can stack)
        if team0_augments:
            self.augment_manager.set_augments(team0_augments)
            self.augment_manager.apply_augments(team0, team0_traits)
            self.log_event('augments_applied', team=0, augments=team0_augments)

        if team1_augments:
            self.augment_manager.set_augments(team1_augments)
            self.augment_manager.apply_augments(team1, team1_traits)
            self.log_event('augments_applied', team=1, augments=team1_augments)

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
            'total_damage_dealt': {
                'team0': round(sum(u.total_damage_dealt for u in team0), 1),
                'team1': round(sum(u.total_damage_dealt for u in team1), 1),
            },
            'team0_abilities_cast': sum(u.abilities_cast for u in team0),
            'team1_abilities_cast': sum(u.abilities_cast for u in team1),
            'combat_log': self.combat_log if verbose else [],
        }

        return results

    def simulate_1v1(self, champ1: str, champ2: str,
                    star1: int = 1, star2: int = 1,
                    items1: List[str] = None, items2: List[str] = None,
                    augments1: List[str] = None, augments2: List[str] = None,
                    num_simulations: int = 100,
                    seed: int = None) -> Dict:
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
                return {'error': 'Invalid champion names'}

            result = self.run_combat([unit1], [unit2],
                                     team0_augments=augments1,
                                     team1_augments=augments2,
                                     seed=sim_seed)

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
