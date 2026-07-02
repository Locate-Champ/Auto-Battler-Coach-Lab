"""Item and ability database factories."""

import sys
from pathlib import Path
from typing import Dict, Optional

from ._combat_types import (
    Ability,
    AbilityType,
    DamageType,
    Item,
)

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

# Try to import from the comprehensive item data file
try:
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
            for _key, val in variables.items():
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
