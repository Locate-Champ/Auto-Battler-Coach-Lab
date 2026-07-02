"""Base mixin: dispatch, helpers, damage, stun, immortal resurrection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from ._combat_types import UnitState
from ._hex_grid import HexGrid

if TYPE_CHECKING:
    from ._combat_types import Unit


class _AbilitiesBaseMixin:
    """Base mixin providing cast dispatch, helpers, and common combat actions."""

    def __init__(self, engine):
        self.engine = engine

    def cast(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """
        Handle champion-specific ability casting.

        Returns True if ability was fully handled, False to continue to default processing.
        """
        handler = getattr(self, f"_cast_{unit.api_name.replace('TFT16_', '').lower()}", None)
        if handler:
            return handler(unit, enemies, allies, ability_vars)
        return False

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _get_var(self, ability_vars: Dict, key: str, star_level: int, default: float = 0) -> float:
        """Get ability variable for star level.

        Handles both list format [0, 1star, 2star, 3star, ...] and
        dict format {'1star': val, '2star': val, ...}.
        """
        var_data = ability_vars.get(key)
        if var_data is None:
            return default
        if isinstance(var_data, list):
            if star_level < len(var_data):
                return var_data[star_level] if var_data[star_level] else default
            return default
        if isinstance(var_data, dict):
            return var_data.get(f"{star_level}star", default) or default
        # Scalar value
        return var_data if var_data else default

    def _find_farthest_enemy(
        self, unit: "Unit", enemies: List["Unit"], max_range: int = 99
    ) -> Optional["Unit"]:
        """Find farthest targetable enemy within range."""
        valid = [
            e
            for e in enemies
            if e.is_alive
            and e.is_targetable
            and HexGrid.hex_distance(unit.position, e.position) <= max_range
        ]
        if not valid:
            return None
        return max(valid, key=lambda e: HexGrid.hex_distance(unit.position, e.position))

    def _find_nearest_enemy(self, unit: "Unit", enemies: List["Unit"]) -> Optional["Unit"]:
        """Find nearest targetable enemy."""
        valid = [e for e in enemies if e.is_alive and e.is_targetable]
        if not valid:
            return None
        return min(valid, key=lambda e: HexGrid.hex_distance(unit.position, e.position))

    def _find_lowest_hp_enemy(self, unit: "Unit", enemies: List["Unit"]) -> Optional["Unit"]:
        """Find enemy with lowest current HP."""
        valid = [e for e in enemies if e.is_alive and e.is_targetable]
        if not valid:
            return None
        return min(valid, key=lambda e: e.stats.hp)

    def _get_enemies_in_radius(
        self, center: Tuple[int, int], radius: int, enemies: List["Unit"]
    ) -> List["Unit"]:
        """Get all enemies within radius of a position."""
        return [
            e
            for e in enemies
            if e.is_alive and e.is_targetable and HexGrid.hex_distance(center, e.position) <= radius
        ]

    def _dash_to_position(self, unit: "Unit", target_pos: Tuple[int, int]) -> bool:
        """Move unit to target position (or adjacent hex if occupied)."""
        occupied = self.engine.get_occupied_hexes()

        if target_pos not in occupied:
            old_pos = unit.position
            self.engine.set_unit_position(unit, target_pos)
            self.engine.log_event("dash", unit=unit.name, from_pos=old_pos, to_pos=target_pos)
            return True

        # Find adjacent hex
        neighbors = HexGrid.get_neighbors(target_pos)
        valid = [n for n in neighbors if n not in occupied]
        if valid:
            old_pos = unit.position
            self.engine.set_unit_position(unit, valid[0])
            self.engine.log_event("dash", unit=unit.name, from_pos=old_pos, to_pos=valid[0])
            return True
        return False

    def _hex_distance(self, pos1: Tuple[int, int], pos2: Tuple[int, int]) -> int:
        """Helper to calculate hex distance."""
        return HexGrid.hex_distance(pos1, pos2)

    def _apply_stun(self, target: "Unit", duration: float, source: str):
        """Apply stun to a target. Blocked by Quicksilver or Titan's Resolve (25 stacks)."""
        from .item_effects import get_item_data  # KEEP deferred -- cross-module circular risk

        # Quicksilver CC immunity (18s from combat start)
        qs_until = get_item_data(target, "Quicksilver", "immune_until", 0)
        if qs_until and self.engine.time < qs_until:
            self.engine.log_event("cc_immune", target=target.name, source="Quicksilver")
            return

        # Titan's Resolve CC immunity (at 25 stacks)
        if get_item_data(target, "TitansResolve", "cc_immune", False):
            self.engine.log_event("cc_immune", target=target.name, source="TitansResolve")
            return

        target.stun_duration = max(target.stun_duration, duration)
        target.state = UnitState.STUNNED
        self.engine.log_event("stun", target=target.name, duration=duration, source=source)

    def _deal_damage(
        self,
        attacker: "Unit",
        target: "Unit",
        damage: float,
        damage_type,
        source: str,
        can_crit: bool = True,
    ) -> Tuple[float, float]:
        """Deal damage and return (actual_damage, excess_damage)."""
        final_damage, did_crit = self.engine.calculate_damage(
            attacker, target, damage, damage_type, can_crit=can_crit, is_ability=True
        )
        hp_before = target.stats.hp
        actual = self.engine.apply_damage(attacker, target, final_damage, damage_type, source)
        excess = max(0, final_damage - hp_before) if not target.is_alive else 0
        return actual, excess

    # =========================================================================
    # IMMORTAL TRAIT - Resurrection for Zaahen
    # =========================================================================

    def check_immortal_resurrection(self, unit: "Unit") -> bool:
        """Check if unit should resurrect via Immortal trait."""
        if "Immortal" not in unit.traits:
            return False

        if hasattr(unit, "_immortal_used"):
            return False

        # Resurrect with 60% HP
        unit._immortal_used = True
        unit.is_alive = True
        unit.stats.hp = unit.stats.max_hp * 0.6
        unit.state = UnitState.IDLE

        self.engine.log_event("immortal_resurrect", unit=unit.name, hp=unit.stats.hp)
        return True
