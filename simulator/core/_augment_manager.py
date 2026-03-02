"""Augment manager: augment loading and application."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from ._hex_grid import HexGrid
from .augment_paths import resolve_augment_data_path

if TYPE_CHECKING:
    from ._combat_types import Unit

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
except (OSError, ValueError, KeyError, TypeError):
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
