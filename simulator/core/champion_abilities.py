"""
TFT Set 16 Champion Ability Implementations

This module contains specific ability logic for each champion that goes beyond
the basic damage/heal/shield mechanics in the combat engine.

Each champion handler returns True if the ability was fully handled,
or False if it should fall through to default ability processing.
"""

from typing import List, Dict, Optional, Tuple, TYPE_CHECKING
from enum import Enum
import random

if TYPE_CHECKING:
    from .combat_engine import CombatEngine, Unit, HexGrid, DamageType


class ChampionAbilities:
    """Handler for champion-specific ability mechanics."""

    def __init__(self, engine: 'CombatEngine'):
        self.engine = engine

    def cast(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
             ability_vars: Dict) -> bool:
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
        """Get ability variable for star level."""
        var_data = ability_vars.get(key, {})
        if isinstance(var_data, dict):
            return var_data.get(f'{star_level}star', default) or default
        return var_data if var_data else default

    def _find_farthest_enemy(self, unit: 'Unit', enemies: List['Unit'],
                             max_range: int = 99) -> Optional['Unit']:
        """Find farthest targetable enemy within range."""
        from .combat_engine import HexGrid
        valid = [e for e in enemies if e.is_alive and e.is_targetable and
                 HexGrid.hex_distance(unit.position, e.position) <= max_range]
        if not valid:
            return None
        return max(valid, key=lambda e: HexGrid.hex_distance(unit.position, e.position))

    def _find_nearest_enemy(self, unit: 'Unit', enemies: List['Unit']) -> Optional['Unit']:
        """Find nearest targetable enemy."""
        from .combat_engine import HexGrid
        valid = [e for e in enemies if e.is_alive and e.is_targetable]
        if not valid:
            return None
        return min(valid, key=lambda e: HexGrid.hex_distance(unit.position, e.position))

    def _find_lowest_hp_enemy(self, unit: 'Unit', enemies: List['Unit']) -> Optional['Unit']:
        """Find enemy with lowest current HP."""
        valid = [e for e in enemies if e.is_alive and e.is_targetable]
        if not valid:
            return None
        return min(valid, key=lambda e: e.stats.hp)

    def _get_enemies_in_radius(self, center: Tuple[int, int], radius: int,
                               enemies: List['Unit']) -> List['Unit']:
        """Get all enemies within radius of a position."""
        from .combat_engine import HexGrid
        return [e for e in enemies if e.is_alive and e.is_targetable and
                HexGrid.hex_distance(center, e.position) <= radius]

    def _dash_to_position(self, unit: 'Unit', target_pos: Tuple[int, int]) -> bool:
        """Move unit to target position (or adjacent hex if occupied)."""
        from .combat_engine import HexGrid
        occupied = self.engine.get_occupied_hexes()

        if target_pos not in occupied:
            old_pos = unit.position
            unit.position = target_pos
            self.engine.log_event('dash', unit=unit.name, from_pos=old_pos, to_pos=target_pos)
            return True

        # Find adjacent hex
        neighbors = HexGrid.get_neighbors(target_pos)
        valid = [n for n in neighbors if n not in occupied]
        if valid:
            old_pos = unit.position
            unit.position = valid[0]
            self.engine.log_event('dash', unit=unit.name, from_pos=old_pos, to_pos=valid[0])
            return True
        return False

    def _apply_stun(self, target: 'Unit', duration: float, source: str):
        """Apply stun to a target."""
        from .combat_engine import UnitState
        target.stun_duration = max(target.stun_duration, duration)
        target.state = UnitState.STUNNED
        self.engine.log_event('stun', target=target.name, duration=duration, source=source)

    def _deal_damage(self, attacker: 'Unit', target: 'Unit', damage: float,
                     damage_type, source: str, can_crit: bool = True) -> Tuple[float, float]:
        """Deal damage and return (actual_damage, excess_damage)."""
        final_damage, did_crit = self.engine.calculate_damage(
            attacker, target, damage, damage_type, can_crit=can_crit, is_ability=True
        )
        hp_before = target.stats.hp
        actual = self.engine.apply_damage(attacker, target, final_damage, damage_type, source)
        excess = max(0, final_damage - hp_before) if not target.is_alive else 0
        return actual, excess

    # =========================================================================
    # CHAMPION ABILITY HANDLERS (alphabetical order)
    # =========================================================================

    def _cast_aatrox(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                     ability_vars: Dict) -> bool:
        """Aatrox - The Darkin Blade: 3-hit combo with execute on 3rd hit."""
        from .combat_engine import DamageType, UnitState

        # Track cast count for combo
        if not hasattr(unit, '_aatrox_combo'):
            unit._aatrox_combo = 0

        unit._aatrox_combo += 1
        combo_hit = unit._aatrox_combo

        # Get damage values
        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 95)

        # Apply damage multipliers for 2nd and 3rd hits
        if combo_hit == 2:
            multiplier = self._get_var(ability_vars, 'SecondCastPercentDamage', unit.star_level, 1.2)
            ad_damage *= multiplier
            # Stun on 2nd cast
            stun_duration = self._get_var(ability_vars, 'SecondCastStunDuration', unit.star_level, 1.0)
            if unit.target and unit.target.is_alive:
                self._apply_stun(unit.target, stun_duration, "aatrox_stun")
        elif combo_hit >= 3:
            multiplier = self._get_var(ability_vars, 'ThirdCastPercentDamage', unit.star_level, 1.6)
            ad_damage *= multiplier
            unit._aatrox_combo = 0  # Reset combo

            # Execute mechanic on 3rd hit
            execute_threshold = self._get_var(ability_vars, 'ThirdCastExecute', unit.star_level, 0.15)
            if unit.target and unit.target.is_alive:
                if unit.target.stats.hp / unit.target.stats.max_hp <= execute_threshold:
                    # Execute!
                    self.engine.apply_damage(unit, unit.target, unit.target.stats.hp + 1,
                                            DamageType.TRUE, "aatrox_execute")
                    self.engine.log_event('execute', unit=unit.name, target=unit.target.name,
                                         threshold=execute_threshold)
                    unit.stats.mana = 0
                    return True

        # Normal damage
        if unit.target and unit.target.is_alive:
            self._deal_damage(unit, unit.target, ad_damage + unit.stats.ad,
                             DamageType.PHYSICAL, f"aatrox_hit{combo_hit}")

        # World Ender: Brief untargetable + AD from omnivamp
        if combo_hit == 1 and unit.stats.omnivamp > 0:
            bonus_ad = unit.stats.omnivamp * 100  # Convert to AD bonus
            unit.stats.ad += bonus_ad
            unit.is_targetable = False
            unit.untargetable_duration = 0.5
            self.engine.log_event('world_ender', unit=unit.name, bonus_ad=bonus_ad)

        unit.stats.mana = 0
        return True

    def _cast_ambessa(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                      ability_vars: Dict) -> bool:
        """Ambessa - Lacerate: Dash + damage with kill reset."""
        from .combat_engine import DamageType, HexGrid

        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 45)
        slam_mult = self._get_var(ability_vars, 'SlamDamageMultiplier', unit.star_level, 3.15)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Dash to target
        self._dash_to_position(unit, target.position)

        # Deal slam damage
        total_damage = (ad_damage + unit.stats.ad) * slam_mult
        actual, excess = self._deal_damage(unit, target, total_damage,
                                           DamageType.PHYSICAL, "ambessa_slam")

        # Kill reset - if target died, reset mana for another cast
        if not target.is_alive:
            unit.stats.mana = unit.stats.max_mana * 0.5  # Partial refund
            self.engine.log_event('ambessa_reset', unit=unit.name)
        else:
            unit.stats.mana = 0

        return True

    def _cast_aphelios(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                       ability_vars: Dict) -> bool:
        """Aphelios - Incendiary Onslaught: Dual weapons, Infernum hits 3 targets."""
        from .combat_engine import DamageType

        num_targets = int(self._get_var(ability_vars, 'NumTargets', unit.star_level, 3))
        num_attacks = int(self._get_var(ability_vars, 'NumAttacks', unit.star_level, 8))
        attack_speed = self._get_var(ability_vars, 'AttackSpeed', unit.star_level, 2.0)
        severum_damage = self._get_var(ability_vars, 'SeverumADDamage', unit.star_level, 70)
        omnivamp = self._get_var(ability_vars, 'Omnivamp', unit.star_level, 0.1)

        # Get up to 3 targets
        targets = sorted(enemies, key=lambda e: not e.is_alive)[:num_targets]
        targets = [t for t in targets if t.is_alive and t.is_targetable]

        if not targets:
            return False

        # Perform attacks on all targets
        for _ in range(num_attacks):
            for target in targets:
                if not target.is_alive:
                    continue
                damage = severum_damage + unit.stats.ad
                actual, _ = self._deal_damage(unit, target, damage,
                                              DamageType.PHYSICAL, "aphelios_infernum")
                # Omnivamp healing
                heal = actual * omnivamp
                self.engine.heal_unit(unit, heal, "aphelios_omnivamp")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Incendiary Onslaught",
                             targets=[t.name for t in targets])
        return True

    def _cast_aurelionsol(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                          ability_vars: Dict) -> bool:
        """Aurelion Sol - The Skies Descend: Upgradable via stardust thresholds."""
        from .combat_engine import DamageType

        # Track stardust accumulation
        if not hasattr(unit, '_stardust'):
            unit._stardust = 0

        # Get damage based on stardust threshold
        base_damage = self._get_var(ability_vars, 'Damage', unit.star_level, 480)

        # Check thresholds for upgrades
        thresholds = []
        for i in range(1, 9):
            thresh = self._get_var(ability_vars, f'StardustThreshold{i}', unit.star_level, i * 200)
            thresholds.append(thresh)

        upgrade_level = 0
        for i, thresh in enumerate(thresholds):
            if unit._stardust >= thresh:
                upgrade_level = i + 1

        # Damage scales with upgrade level
        damage = base_damage * (1 + upgrade_level * 0.25)

        # Hit all enemies
        for enemy in enemies:
            if enemy.is_alive and enemy.is_targetable:
                actual, _ = self._deal_damage(unit, enemy, damage + unit.stats.ap,
                                              DamageType.MAGIC, "aurelion_stars")
                # Accumulate stardust from damage dealt
                unit._stardust += actual * 0.1

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="The Skies Descend",
                             stardust=unit._stardust, upgrade_level=upgrade_level)
        return True

    def _cast_caitlyn(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                      ability_vars: Dict) -> bool:
        """Caitlyn - Ace in the Hole: Excess damage overflows to next target."""
        from .combat_engine import DamageType

        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 475)
        ap_damage = self._get_var(ability_vars, 'APDamage', unit.star_level, 40)

        total_damage = ad_damage + unit.stats.ad + ap_damage + unit.stats.ap

        # Get sorted targets by distance
        targets = sorted([e for e in enemies if e.is_alive and e.is_targetable],
                        key=lambda e: -e.stats.hp)  # Target lowest HP first for execute feel

        remaining_damage = total_damage
        targets_hit = []

        for target in targets:
            if remaining_damage <= 0:
                break

            actual, excess = self._deal_damage(unit, target, remaining_damage,
                                               DamageType.PHYSICAL, "caitlyn_ace")
            targets_hit.append(target.name)
            remaining_damage = excess  # Carry over excess

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Ace in the Hole",
                             targets=targets_hit, excess_used=total_damage - remaining_damage > ad_damage)
        return True

    def _cast_darius(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                     ability_vars: Dict) -> bool:
        """Darius - Decimate: Bleed stacking with execute threshold."""
        from .combat_engine import DamageType

        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 90)
        heal_amount = self._get_var(ability_vars, 'APHealing', unit.star_level, 180)
        bleed_dps = self._get_var(ability_vars, 'PhysicalDamagePerSecond', unit.star_level, 15)
        execute_per_stack = self._get_var(ability_vars, 'ExecutePercentPerHemorrhage', unit.star_level, 0.08)
        bleed_duration = self._get_var(ability_vars, 'BleedDuration', unit.star_level, 4.0)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Track bleed stacks on target
        if not hasattr(target, '_darius_bleed'):
            target._darius_bleed = 0
        target._darius_bleed = min(5, target._darius_bleed + 1)

        # Apply bleed damage
        bleed_total = bleed_dps * bleed_duration
        self.engine._apply_burn(unit, target, "darius_bleed", bleed_dps, bleed_duration)

        # Check execute threshold
        execute_threshold = execute_per_stack * target._darius_bleed
        if target.stats.hp / target.stats.max_hp <= execute_threshold:
            self.engine.apply_damage(unit, target, target.stats.hp + 1,
                                    DamageType.TRUE, "darius_execute")
            self.engine.log_event('execute', unit=unit.name, target=target.name,
                                 stacks=target._darius_bleed)
        else:
            # Normal damage
            self._deal_damage(unit, target, ad_damage + unit.stats.ad,
                             DamageType.PHYSICAL, "darius_decimate")

        # Heal
        self.engine.heal_unit(unit, heal_amount + unit.stats.ap, "darius_heal")

        unit.stats.mana = 0
        return True

    def _cast_draven(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                     ability_vars: Dict) -> bool:
        """Draven - Spinning Axes: Axe cycling with gold on takedown."""
        from .combat_engine import DamageType

        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 120)
        gold_amount = int(self._get_var(ability_vars, 'GoldAmount', unit.star_level, 1))

        # Track axes
        if not hasattr(unit, '_draven_axes'):
            unit._draven_axes = 2  # Start with 2 axes

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Throw axes (damage per axe)
        for i in range(unit._draven_axes):
            if not target.is_alive:
                break
            actual, _ = self._deal_damage(unit, target, ad_damage + unit.stats.ad,
                                          DamageType.PHYSICAL, f"draven_axe_{i+1}")

            # Gold on takedown
            if not target.is_alive:
                if not hasattr(unit, '_draven_gold'):
                    unit._draven_gold = 0
                unit._draven_gold += gold_amount
                self.engine.log_event('draven_gold', unit=unit.name, gold=gold_amount,
                                     total=unit._draven_gold)

        unit.stats.mana = 0
        return True

    def _cast_lissandra(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                        ability_vars: Dict) -> bool:
        """Lissandra - Frozen Tomb: Stun with excess damage to nearby enemies."""
        from .combat_engine import DamageType, HexGrid

        target_damage = self._get_var(ability_vars, 'TargetDamage', unit.star_level, 275)
        secondary_damage = self._get_var(ability_vars, 'SecondaryDamage', unit.star_level, 415)
        stun_duration = self._get_var(ability_vars, 'StunDuration', unit.star_level, 1.0)
        num_overkill = int(self._get_var(ability_vars, 'NumOverkillEnemies', unit.star_level, 2))
        chill_amp = self._get_var(ability_vars, 'DamageAmpChilledTargets', unit.star_level, 0.12)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Stun primary target
        self._apply_stun(target, stun_duration, "lissandra_tomb")

        # Deal damage to primary target
        actual, excess = self._deal_damage(unit, target, target_damage + unit.stats.ap,
                                           DamageType.MAGIC, "lissandra_tomb")

        # Excess damage overflows to nearby enemies
        if excess > 0:
            nearby = self._get_enemies_in_radius(target.position, 2, enemies)
            nearby = [e for e in nearby if e != target and e.is_alive][:num_overkill]

            for secondary in nearby:
                overflow_damage = min(excess, secondary_damage + unit.stats.ap)
                self._deal_damage(unit, secondary, overflow_damage,
                                 DamageType.MAGIC, "lissandra_overflow")
                excess -= overflow_damage
                if excess <= 0:
                    break

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Frozen Tomb",
                             excess_used=excess > 0)
        return True

    def _cast_lux(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                  ability_vars: Dict) -> bool:
        """Lux - Final Spark: Line laser toward target, width ~200 game units.

        The laser fires in a LINE toward Lux's target (not board-wide).
        Width of 200 game units translates to hitting enemies in the same hex
        column as the beam travels, or very slightly adjacent.
        """
        from .combat_engine import DamageType, HexGrid

        primary_damage = self._get_var(ability_vars, 'PrimaryDamage', unit.star_level, 330)
        secondary_damage = self._get_var(ability_vars, 'SecondaryDamage', unit.star_level, 90)
        q_damage = self._get_var(ability_vars, 'QDamage', unit.star_level, 30)
        stun_duration = self._get_var(ability_vars, 'StunDuration', unit.star_level, 1.0)

        # Get target to determine laser direction
        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        unit_row, unit_col = unit.position
        target_row, target_col = target.position

        # Calculate laser direction (simplified: fires toward target's column)
        # Beam width of 200 = roughly same row ±0.5, so we check row distance
        targets_hit = []

        for enemy in enemies:
            if not enemy.is_alive or not enemy.is_targetable:
                continue

            enemy_row, enemy_col = enemy.position

            # Check if enemy is in the beam path
            # The beam goes from Lux toward her target direction
            # Hit enemies if they're roughly in line (same row or very close)
            row_diff = abs(enemy_row - unit_row)

            # Enemy must be between Lux and far side of board (in beam direction)
            # and within beam width (row_diff <= 0.5 rounded = 0 or 1 at edge)
            in_beam_path = False

            if target_col >= unit_col:  # Firing right
                in_beam_path = enemy_col >= unit_col
            else:  # Firing left
                in_beam_path = enemy_col <= unit_col

            # Beam width check - direct hit (same row) vs edge hit
            if in_beam_path and row_diff == 0:
                # Direct center hit - full damage
                self._deal_damage(unit, enemy, primary_damage + unit.stats.ap,
                                 DamageType.MAGIC, "lux_laser")
                targets_hit.append(enemy.name)
            elif in_beam_path and row_diff == 1:
                # Edge of beam - reduced damage
                self._deal_damage(unit, enemy, secondary_damage + unit.stats.ap,
                                 DamageType.MAGIC, "lux_laser_edge")
                targets_hit.append(enemy.name)

        # Q hits closest 2 enemies with stun
        q_targets = sorted([e for e in enemies if e.is_alive and e.is_targetable],
                          key=lambda e: HexGrid.hex_distance(unit.position, e.position))[:2]
        for q_target in q_targets:
            self._apply_stun(q_target, stun_duration, "lux_q")
            self._deal_damage(unit, q_target, q_damage + unit.stats.ap,
                             DamageType.MAGIC, "lux_q")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Final Spark",
                             targets=targets_hit, direction="toward_target")
        return True

    def _cast_malzahar(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                       ability_vars: Dict) -> bool:
        """Malzahar - Void Swarm: Summon untargetable voidlings."""
        from .combat_engine import DamageType

        num_minions = int(self._get_var(ability_vars, 'NumMinions', unit.star_level, 2))
        num_attacks = int(self._get_var(ability_vars, 'NumAttacks', unit.star_level, 8))
        damage_per_attack = self._get_var(ability_vars, 'Damage', unit.star_level, 29)

        # Simulate voidling attacks (they're untargetable so we just deal damage over time)
        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        total_damage = damage_per_attack * num_attacks * num_minions

        # Deal damage over multiple hits
        for i in range(num_minions * num_attacks):
            if not target.is_alive:
                target = self._find_nearest_enemy(unit, enemies)
                if not target:
                    break
            self._deal_damage(unit, target, damage_per_attack + unit.stats.ap * 0.1,
                             DamageType.MAGIC, "voidling_attack")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Void Swarm",
                             minions=num_minions, attacks=num_attacks)
        return True

    def _cast_renekton(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                       ability_vars: Dict) -> bool:
        """Renekton - Slice and Dice: Dash through enemies with multi-slash."""
        from .combat_engine import DamageType, HexGrid

        dash_damage = self._get_var(ability_vars, 'DashADDamage', unit.star_level, 80)
        slash_damage = self._get_var(ability_vars, 'SlashADDamage', unit.star_level, 50)
        dash_range = int(self._get_var(ability_vars, 'DashRange', unit.star_level, 2))

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Dash to target
        old_pos = unit.position
        self._dash_to_position(unit, target.position)

        # Damage enemies along the dash path
        path_enemies = [e for e in enemies if e.is_alive and e.is_targetable and
                       HexGrid.hex_distance(old_pos, e.position) <= dash_range]

        for enemy in path_enemies:
            self._deal_damage(unit, enemy, dash_damage + unit.stats.ad,
                             DamageType.PHYSICAL, "renekton_dash")

        # Slash damage to nearby enemies
        nearby = self._get_enemies_in_radius(unit.position, 1, enemies)
        for enemy in nearby:
            self._deal_damage(unit, enemy, slash_damage + unit.stats.ad,
                             DamageType.PHYSICAL, "renekton_slash")

        unit.stats.mana = 0
        return True

    def _cast_seraphine(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                        ability_vars: Dict) -> bool:
        """Seraphine - Grand Encore: Crystal accumulation to super-cast."""
        from .combat_engine import DamageType

        damage_per_crystal = self._get_var(ability_vars, 'DamagePerCrystal', unit.star_level, 35)
        cast_breakpoint = int(self._get_var(ability_vars, 'CastBreakpoint', unit.star_level, 12))
        big_cast_damage = self._get_var(ability_vars, 'BigCastDamage', unit.star_level, 270)
        big_cast_heal = self._get_var(ability_vars, 'BigCastHeal', unit.star_level, 40)
        crystals_per_cast = int(self._get_var(ability_vars, 'CrystalsPerCast', unit.star_level, 3))
        falloff = self._get_var(ability_vars, 'BigCastDamageFalloff', unit.star_level, 0.3)

        # Track casts for big cast
        if not hasattr(unit, '_seraphine_casts'):
            unit._seraphine_casts = 0
        unit._seraphine_casts += 1

        # Check if it's time for big cast
        if unit._seraphine_casts >= cast_breakpoint:
            unit._seraphine_casts = 0

            # Big cast - line across board
            unit_row = unit.position[0]
            targets_hit = []

            for enemy in enemies:
                if not enemy.is_alive or not enemy.is_targetable:
                    continue

                # Hit enemies in line (same row or adjacent)
                if abs(enemy.position[0] - unit_row) <= 1:
                    # Damage falls off with distance
                    dist = abs(enemy.position[1] - unit.position[1])
                    damage = big_cast_damage * (1 - falloff * dist)
                    self._deal_damage(unit, enemy, damage + unit.stats.ap,
                                     DamageType.MAGIC, "seraphine_big_cast")
                    targets_hit.append(enemy.name)

            # Heal allies
            for ally in allies:
                if ally.is_alive:
                    self.engine.heal_unit(ally, big_cast_heal + unit.stats.ap * 0.5, "seraphine_heal")

            self.engine.log_event('seraphine_big_cast', unit=unit.name, targets=targets_hit)
        else:
            # Normal cast - crystal damage
            crystals = crystals_per_cast
            targets = sorted([e for e in enemies if e.is_alive and e.is_targetable],
                            key=lambda e: e.stats.hp)[:2]

            for target in targets:
                damage = damage_per_crystal * crystals
                self._deal_damage(unit, target, damage + unit.stats.ap,
                                 DamageType.MAGIC, "seraphine_crystal")

        unit.stats.mana = 0
        return True

    def _cast_swain(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                    ability_vars: Dict) -> bool:
        """Swain - Nevermove: AoE stun with passive drain."""
        from .combat_engine import DamageType

        passive_damage = self._get_var(ability_vars, 'PassiveDamage', unit.star_level, 20)
        stun_duration = self._get_var(ability_vars, 'StunDuration', unit.star_level, 1.5)
        heal_percent = self._get_var(ability_vars, 'PercentMaximumHealthHealing', unit.star_level, 0.015)

        # AoE stun
        nearby = self._get_enemies_in_radius(unit.position, 2, enemies)

        for enemy in nearby:
            # Stun
            self._apply_stun(enemy, stun_duration, "swain_nevermove")
            # Damage
            self._deal_damage(unit, enemy, passive_damage + unit.stats.ap,
                             DamageType.MAGIC, "swain_aoe")

        # Self heal
        heal = unit.stats.max_hp * heal_percent
        self.engine.heal_unit(unit, heal, "swain_drain")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Nevermove",
                             targets=[e.name for e in nearby])
        return True

    def _cast_vayne(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                    ability_vars: Dict) -> bool:
        """Vayne - Tumble: Dash + Silver Bolts true damage."""
        from .combat_engine import DamageType, HexGrid

        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 100)
        dash_range = int(self._get_var(ability_vars, 'HexDashRange', unit.star_level, 3))

        # Track silver bolts stacks
        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        if not hasattr(target, '_vayne_bolts'):
            target._vayne_bolts = 0
        target._vayne_bolts += 1

        # Dash away from target
        old_pos = unit.position
        # Find hex further from enemies
        best_hex = None
        best_dist = 0
        for row in range(4):
            for col in range(7):
                pos = (row, col)
                if pos in self.engine.get_occupied_hexes():
                    continue
                dist = min(HexGrid.hex_distance(pos, e.position)
                          for e in enemies if e.is_alive)
                if dist > best_dist and HexGrid.hex_distance(old_pos, pos) <= dash_range:
                    best_dist = dist
                    best_hex = pos

        if best_hex:
            unit.position = best_hex
            self.engine.log_event('vayne_tumble', unit=unit.name, from_pos=old_pos, to_pos=best_hex)

        # Deal damage
        self._deal_damage(unit, target, ad_damage + unit.stats.ad,
                         DamageType.PHYSICAL, "vayne_tumble")

        # Silver Bolts proc on 3rd hit
        if target._vayne_bolts >= 3:
            target._vayne_bolts = 0
            true_damage = target.stats.max_hp * 0.14  # 14% max HP true damage
            self.engine.apply_damage(unit, target, true_damage, DamageType.TRUE, "vayne_silver_bolts")
            self.engine.log_event('silver_bolts', unit=unit.name, target=target.name, damage=true_damage)

        unit.stats.mana = 0
        return True

    def _cast_veigar(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                     ability_vars: Dict) -> bool:
        """Veigar - Dark Storm: Permanent AP stacking with innate AP scaling."""
        from .combat_engine import DamageType

        damage = self._get_var(ability_vars, 'Damage', unit.star_level, 62)
        num_meteors = int(self._get_var(ability_vars, 'NumMeteors', unit.star_level, 12))
        ap_per_kill = self._get_var(ability_vars, 'APPerKill', unit.star_level, 1)
        percent_on_primary = self._get_var(ability_vars, 'PercentOnPrimaryTarget', unit.star_level, 0.7)
        increased_ap_ratio = self._get_var(ability_vars, 'IncreasedAPRatio', unit.star_level, 0.5)

        # Innate AP scaling bonus
        bonus_ap_mult = 1 + increased_ap_ratio

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Focus meteors on primary target
        primary_meteors = int(num_meteors * percent_on_primary)
        secondary_meteors = num_meteors - primary_meteors

        kills = 0

        # Primary target meteors
        for _ in range(primary_meteors):
            if not target.is_alive:
                break
            meteor_damage = damage + (unit.stats.ap * bonus_ap_mult)
            hp_before = target.stats.hp
            self._deal_damage(unit, target, meteor_damage, DamageType.MAGIC, "veigar_meteor")
            if not target.is_alive and hp_before > 0:
                kills += 1

        # Secondary targets
        other_enemies = [e for e in enemies if e.is_alive and e.is_targetable and e != target]
        for _ in range(secondary_meteors):
            if not other_enemies:
                break
            sec_target = random.choice(other_enemies)
            meteor_damage = damage + (unit.stats.ap * bonus_ap_mult)
            hp_before = sec_target.stats.hp
            self._deal_damage(unit, sec_target, meteor_damage, DamageType.MAGIC, "veigar_meteor")
            if not sec_target.is_alive:
                kills += 1
                other_enemies.remove(sec_target)

        # Permanent AP gain on kills
        if kills > 0:
            ap_gain = ap_per_kill * kills
            unit.base_stats.ap += ap_gain
            unit.stats.ap += ap_gain
            self.engine.log_event('veigar_ap_stack', unit=unit.name, kills=kills, ap_gain=ap_gain,
                                 total_ap=unit.stats.ap)

        unit.stats.mana = 0
        return True

    def _cast_wukong(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                     ability_vars: Dict) -> bool:
        """Wukong - Diverting Trickster: Summon clone."""
        from .combat_engine import DamageType

        clone_hp_pct = self._get_var(ability_vars, 'SummonMaxHealthPercent', unit.star_level, 0.4)
        clone_flat_hp = self._get_var(ability_vars, 'SummonFlatHealth', unit.star_level, 150)
        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 100)
        resists = self._get_var(ability_vars, 'Resists', unit.star_level, 100)
        duration = self._get_var(ability_vars, 'Duration', unit.star_level, 4)

        # Track clone (simulate damage output)
        clone_hp = unit.stats.max_hp * clone_hp_pct + clone_flat_hp
        clone_damage = ad_damage * 0.4  # Clone deals 40% damage

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Clone attacks (simplified - just deal damage over duration)
        attacks = int(duration / (1 / unit.stats.attack_speed))
        for _ in range(attacks):
            if not target.is_alive:
                target = self._find_nearest_enemy(unit, enemies)
                if not target:
                    break
            self._deal_damage(unit, target, clone_damage, DamageType.PHYSICAL, "wukong_clone")

        # Main Wukong also deals damage
        self._deal_damage(unit, target, ad_damage + unit.stats.ad,
                         DamageType.PHYSICAL, "wukong_strike")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Diverting Trickster",
                             clone_hp=clone_hp)
        return True

    def _cast_yasuo(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                    ability_vars: Dict) -> bool:
        """Yasuo - Sweeping Blade: Dash with Yone synergy."""
        from .combat_engine import DamageType, HexGrid

        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 85)
        yasuo_ad_pct = self._get_var(ability_vars, 'YasuoADPercent', unit.star_level, 1.0)
        brother_damage = self._get_var(ability_vars, 'AttributeBrothersDamageToYasuo', unit.star_level, 1.0)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Check for Yone synergy
        yone_present = any(u.api_name == "TFT16_Yone" and u.is_alive
                          for u in self.engine.units if u.team == unit.team)

        damage = ad_damage + unit.stats.ad * yasuo_ad_pct
        if yone_present:
            damage *= (1 + brother_damage)
            self.engine.log_event('yasuo_yone_synergy', unit=unit.name, bonus_mult=brother_damage)

        # Dash to target
        self._dash_to_position(unit, target.position)

        # Deal damage
        self._deal_damage(unit, target, damage, DamageType.PHYSICAL, "yasuo_sweep")

        unit.stats.mana = 0
        return True

    def _cast_yone(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                   ability_vars: Dict) -> bool:
        """Yone - Kin of the Stained Blade: Yasuo synergy with dual scaling."""
        from .combat_engine import DamageType, HexGrid

        ad_damage = self._get_var(ability_vars, 'StrikeADDamage', unit.star_level, 160)
        ap_damage = self._get_var(ability_vars, 'StrikeAPDamage', unit.star_level, 160)
        knockup_duration = self._get_var(ability_vars, 'KnockupDuration', unit.star_level, 1.5)
        yasuo_mult = self._get_var(ability_vars, 'YasuoADPercent', unit.star_level, 2.5)
        dash_range = self._get_var(ability_vars, 'DashHexRange', unit.star_level, 2.5)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Check for Yasuo synergy
        yasuo = None
        for u in self.engine.units:
            if u.api_name == "TFT16_Yasuo" and u.is_alive and u.team == unit.team:
                yasuo = u
                break

        # Calculate damage with potential Yasuo multiplier
        total_ad = ad_damage + unit.stats.ad
        total_ap = ap_damage + unit.stats.ap
        if yasuo:
            total_ad *= yasuo_mult
            self.engine.log_event('yone_yasuo_synergy', unit=unit.name, yasuo=yasuo.name)

        # Dash and damage
        self._dash_to_position(unit, target.position)

        # Dual damage type
        self._deal_damage(unit, target, total_ad, DamageType.PHYSICAL, "yone_strike_ad")
        self._deal_damage(unit, target, total_ap, DamageType.MAGIC, "yone_strike_ap")

        # Knockup (stun)
        self._apply_stun(target, knockup_duration, "yone_knockup")

        unit.stats.mana = 0
        return True

    def _cast_yunara(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                     ability_vars: Dict) -> bool:
        """Yunara - Transcendent State: Infinite range + piercing attacks."""
        from .combat_engine import DamageType

        buff_duration = self._get_var(ability_vars, 'BuffDuration', unit.star_level, 4)
        attack_speed = self._get_var(ability_vars, 'AttackSpeed', unit.star_level, 0.75)
        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 80)
        bonus_crit = self._get_var(ability_vars, 'BonusCritDamage', unit.star_level, 0.33)
        damage_reduction = self._get_var(ability_vars, 'DamageReductionPerEnemyHit', unit.star_level, 0.75)

        # Grant infinite range temporarily
        old_range = unit.stats.range
        unit.stats.range = 99  # Infinite range

        # Grant attack speed
        unit.stats.attack_speed += attack_speed

        # Grant crit damage
        unit.stats.crit_multiplier += bonus_crit

        # Track buff expiration
        if not hasattr(unit, '_yunara_buff_end'):
            unit._yunara_buff_end = 0
        unit._yunara_buff_end = self.engine.time + buff_duration

        # Deal piercing damage to all enemies in a line
        unit_row = unit.position[0]
        enemies_hit = 0
        current_damage = ad_damage + unit.stats.ad

        # Sort enemies by column (left to right)
        line_enemies = sorted([e for e in enemies if e.is_alive and e.is_targetable],
                             key=lambda e: e.position[1])

        for enemy in line_enemies:
            if enemies_hit > 0:
                current_damage *= damage_reduction  # Reduced damage per enemy hit
            self._deal_damage(unit, enemy, current_damage, DamageType.PHYSICAL, "yunara_pierce")
            enemies_hit += 1

        unit.stats.mana = 0
        self.engine.log_event('yunara_transcendent', unit=unit.name, enemies_hit=enemies_hit,
                             duration=buff_duration)
        return True

    def _cast_zaahen(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                     ability_vars: Dict) -> bool:
        """Zaahen - Divine Challenge: AoE damage with execute after 22 casts."""
        from .combat_engine import DamageType

        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 90)
        ap_damage = self._get_var(ability_vars, 'APDamage', unit.star_level, 20)
        aoe_mult = self._get_var(ability_vars, 'AOEDamageMultiplier', unit.star_level, 0.4)
        casts_to_ult = int(self._get_var(ability_vars, 'CastsToUlt', unit.star_level, 22))
        big_aoe_mult = self._get_var(ability_vars, 'BigAOEDamageMultiplier', unit.star_level, 2.0)

        # Track casts
        if not hasattr(unit, '_zaahen_casts'):
            unit._zaahen_casts = 0
        unit._zaahen_casts += 1

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Check for ultimate (Divine Challenge instant kill)
        if unit._zaahen_casts >= casts_to_ult:
            unit._zaahen_casts = 0

            # Execute primary target
            self.engine.apply_damage(unit, target, target.stats.hp + 1,
                                    DamageType.TRUE, "zaahen_execute")
            self.engine.log_event('zaahen_divine_challenge', unit=unit.name, target=target.name)

            # Big AoE to other enemies
            for enemy in enemies:
                if enemy.is_alive and enemy.is_targetable and enemy != target:
                    big_damage = (ad_damage + ap_damage) * big_aoe_mult
                    self._deal_damage(unit, enemy, big_damage, DamageType.MAGIC, "zaahen_aoe")
        else:
            # Normal cast
            total_damage = ad_damage + unit.stats.ad + ap_damage + unit.stats.ap
            self._deal_damage(unit, target, total_damage, DamageType.PHYSICAL, "zaahen_strike")

            # AoE damage
            nearby = self._get_enemies_in_radius(target.position, 1, enemies)
            for enemy in nearby:
                if enemy != target:
                    aoe_damage = total_damage * aoe_mult
                    self._deal_damage(unit, enemy, aoe_damage, DamageType.PHYSICAL, "zaahen_aoe")

        unit.stats.mana = 0
        return True

    def _cast_annie(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                    ability_vars: Dict) -> bool:
        """Annie - Tibbers Rampage: Summon Tibbers + board-wide damage on first cast."""
        from .combat_engine import DamageType

        aoe_damage = self._get_var(ability_vars, 'Damage', unit.star_level, 1500)
        tibbers_damage = self._get_var(ability_vars, 'SingleTargetDamage', unit.star_level, 250)
        duration = self._get_var(ability_vars, 'Duration', unit.star_level, 45)

        # Track if this is first cast
        if not hasattr(unit, '_annie_tibbers_active'):
            unit._annie_tibbers_active = False

        if not unit._annie_tibbers_active:
            # First cast: Board-wide damage
            unit._annie_tibbers_active = True
            for enemy in enemies:
                if enemy.is_alive and enemy.is_targetable:
                    self._deal_damage(unit, enemy, aoe_damage + unit.stats.ap,
                                     DamageType.MAGIC, "annie_tibbers_aoe")
            self.engine.log_event('tibbers_summon', unit=unit.name, first_cast=True)
        else:
            # Subsequent casts: Tibbers attacks
            target = unit.target or self._find_nearest_enemy(unit, enemies)
            if target:
                # Tibbers attacks target multiple times (simulated)
                attacks = int(duration / 2)  # Attack every 2 seconds
                for _ in range(min(attacks, 5)):  # Cap at 5 attacks
                    if not target.is_alive:
                        target = self._find_nearest_enemy(unit, enemies)
                        if not target:
                            break
                    self._deal_damage(unit, target, tibbers_damage + unit.stats.ap * 0.3,
                                     DamageType.MAGIC, "tibbers_attack")

        unit.stats.mana = 0
        return True

    def _cast_bard(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                   ability_vars: Dict) -> bool:
        """Bard - Traveler's Call: Meeps attack multiple enemies."""
        from .combat_engine import DamageType, HexGrid

        damage = self._get_var(ability_vars, 'Damage', unit.star_level, 120)
        num_missiles = int(self._get_var(ability_vars, 'NumMissilesBase', unit.star_level, 6))
        pct_on_current = self._get_var(ability_vars, 'PercentDamageOnCurrentTarget', unit.star_level, 0.75)
        search_radius = int(self._get_var(ability_vars, 'EnemyHexSearchRadius', unit.star_level, 3))

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Meeps hit current target primarily
        main_missiles = int(num_missiles * pct_on_current)
        other_missiles = num_missiles - main_missiles

        # Main target damage
        for _ in range(main_missiles):
            if not target.is_alive:
                break
            self._deal_damage(unit, target, damage + unit.stats.ap,
                             DamageType.MAGIC, "bard_meep")

        # Spread remaining to nearby enemies
        nearby = self._get_enemies_in_radius(target.position, search_radius, enemies)
        nearby = [e for e in nearby if e != target and e.is_alive]

        missiles_remaining = other_missiles
        for enemy in nearby:
            if missiles_remaining <= 0:
                break
            self._deal_damage(unit, enemy, damage + unit.stats.ap,
                             DamageType.MAGIC, "bard_meep")
            missiles_remaining -= 1

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Traveler's Call",
                             missiles=num_missiles)
        return True

    def _cast_diana(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                    ability_vars: Dict) -> bool:
        """Diana - Lunar Rush: Dash + shield + pull enemies."""
        from .combat_engine import DamageType, HexGrid

        shield_amount = self._get_var(ability_vars, 'Shield', unit.star_level, 100)
        damage = self._get_var(ability_vars, 'TargetDamage', unit.star_level, 125)
        hex_limit = int(self._get_var(ability_vars, 'HexLimit', unit.star_level, 4))
        leona_ap = self._get_var(ability_vars, 'DianaAP', unit.star_level, 3)

        # Check for Leona synergy
        has_leona = any(u.api_name == "TFT16_Leona" and u.is_alive
                       for u in self.engine.units if u.team == unit.team)
        if has_leona:
            unit.stats.ap += leona_ap  # Bonus AP from Leona
            self.engine.log_event('diana_leona_synergy', unit=unit.name, bonus_ap=leona_ap)

        # Apply shield
        self.engine.apply_shield(unit, shield_amount + unit.stats.ap * 0.5, "diana_shield")

        # Dash to farthest enemy within range
        enemies_in_range = [e for e in enemies if e.is_alive and e.is_targetable and
                          HexGrid.hex_distance(unit.position, e.position) <= hex_limit]

        if enemies_in_range:
            target = max(enemies_in_range, key=lambda e: HexGrid.hex_distance(unit.position, e.position))
            self._dash_to_position(unit, target.position)

            # Damage and pull nearby enemies together
            nearby = self._get_enemies_in_radius(target.position, 2, enemies)
            for enemy in nearby:
                self._deal_damage(unit, enemy, damage + unit.stats.ap,
                                 DamageType.MAGIC, "diana_lunar_rush")

        unit.stats.mana = 0
        return True

    def _cast_fiddlesticks(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                           ability_vars: Dict) -> bool:
        """Fiddlesticks - Crowstorm: AoE damage with fear + mana drain."""
        from .combat_engine import DamageType

        fear_duration = self._get_var(ability_vars, 'FearDuration', unit.star_level, 1.25)
        mana_drain = self._get_var(ability_vars, 'ManaLossPerSecond', unit.star_level, 22)
        dps = self._get_var(ability_vars, 'DamagePerSecond', unit.star_level, 100)
        bonus_damage_pct = self._get_var(ability_vars, 'NearestBonusDamage', unit.star_level, 0.33)
        aoe_radius = int(self._get_var(ability_vars, 'AOERadius', unit.star_level, 2))

        nearby = self._get_enemies_in_radius(unit.position, aoe_radius, enemies)

        # Find 2 nearest for bonus damage
        sorted_nearby = sorted(nearby, key=lambda e: self._hex_distance(unit.position, e.position))
        nearest_two = sorted_nearby[:2]

        for enemy in nearby:
            # Apply fear (stun)
            self._apply_stun(enemy, fear_duration, "fiddlesticks_fear")

            # Drain mana
            enemy.stats.mana = max(0, enemy.stats.mana - mana_drain * 3)  # 3 sec worth

            # Deal damage (bonus to 2 nearest)
            total_damage = dps * 3  # 3 seconds of damage
            if enemy in nearest_two:
                total_damage *= (1 + bonus_damage_pct)

            self._deal_damage(unit, enemy, total_damage + unit.stats.ap,
                             DamageType.MAGIC, "fiddlesticks_crowstorm")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Crowstorm",
                             enemies_hit=len(nearby))
        return True

    def _hex_distance(self, pos1: Tuple[int, int], pos2: Tuple[int, int]) -> int:
        """Helper to calculate hex distance."""
        from .combat_engine import HexGrid
        return HexGrid.hex_distance(pos1, pos2)

    def _cast_gangplank(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                        ability_vars: Dict) -> bool:
        """Gangplank - Powder Kegs: Barrel chain explosion with armor shred."""
        from .combat_engine import DamageType

        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 190)
        num_barrels = int(self._get_var(ability_vars, 'NumofBarrels', unit.star_level, 3))
        falloff = self._get_var(ability_vars, 'FalloffDamage', unit.star_level, 0.25)
        armor_reduction = self._get_var(ability_vars, 'ArmorReduction', unit.star_level, 10)

        # Place barrels on enemies (simplified)
        targets = sorted([e for e in enemies if e.is_alive and e.is_targetable],
                        key=lambda e: e.stats.hp)[:num_barrels]

        for i, target in enumerate(targets):
            # Falloff damage for each barrel in chain
            damage_mult = 1.0 - (falloff * i)
            final_damage = (ad_damage + unit.stats.ad) * damage_mult

            # Apply armor reduction
            target.stats.armor = max(0, target.stats.armor - armor_reduction)

            self._deal_damage(unit, target, final_damage,
                             DamageType.PHYSICAL, "gangplank_barrel")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Powder Kegs",
                             barrels=num_barrels)
        return True

    def _cast_kindred(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                      ability_vars: Dict) -> bool:
        """Kindred - Lamb's Respite: 2-hex radius zone with shield + double AS."""
        from .combat_engine import DamageType

        shield_amount = self._get_var(ability_vars, 'ShieldAmount', unit.star_level, 350)
        duration = self._get_var(ability_vars, 'Duration', unit.star_level, 2.5)
        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 25)
        heal_pct = self._get_var(ability_vars, 'HealPercentage', unit.star_level, 0.08)
        extra_arrows = int(self._get_var(ability_vars, 'NumExtraArrows', unit.star_level, 1))

        # Zone radius is 2 hexes
        zone_radius = 2

        # Apply shield to self and allies within 2-hex zone
        self.engine.apply_shield(unit, shield_amount, "kindred_respite")
        allies_in_zone = []
        for ally in allies:
            if ally.is_alive and ally != unit:
                if self._hex_distance(unit.position, ally.position) <= zone_radius:
                    self.engine.apply_shield(ally, shield_amount * 0.5, "kindred_respite")
                    allies_in_zone.append(ally.name)

        # Double attack speed while in zone (for Kindred)
        unit.stats.attack_speed *= 2

        # Attack with extra arrows
        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if target:
            # Main attack
            self._deal_damage(unit, target, ad_damage + unit.stats.ad,
                             DamageType.PHYSICAL, "kindred_attack")

            # Heal on attack
            heal = target.stats.max_hp * heal_pct
            self.engine.heal_unit(unit, heal, "kindred_heal")

            # Extra arrows to nearby enemies (within zone radius)
            nearby = self._get_enemies_in_radius(unit.position, zone_radius, enemies)
            nearby = [e for e in nearby if e != target and e.is_alive][:extra_arrows]
            for enemy in nearby:
                self._deal_damage(unit, enemy, ad_damage * 0.5,
                                 DamageType.PHYSICAL, "kindred_arrow")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Lamb's Respite",
                             zone_radius=zone_radius, allies_shielded=allies_in_zone)
        return True

    def _cast_leblanc(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                      ability_vars: Dict) -> bool:
        """LeBlanc - Distortions: Multi-target dash + stun."""
        from .combat_engine import DamageType, HexGrid

        num_targets = int(self._get_var(ability_vars, 'NumTargets', unit.star_level, 3))
        damage = self._get_var(ability_vars, 'Damage', unit.star_level, 300)
        secondary_damage = self._get_var(ability_vars, 'SecondaryDamage', unit.star_level, 180)
        stun_duration = self._get_var(ability_vars, 'StunDuration', unit.star_level, 1.0)
        search_radius = int(self._get_var(ability_vars, 'NearbyEnemyHexRadius', unit.star_level, 3))

        # Get targets
        targets = sorted([e for e in enemies if e.is_alive and e.is_targetable],
                        key=lambda e: e.stats.hp)[:num_targets]

        for i, target in enumerate(targets):
            # Dash to target
            self._dash_to_position(unit, target.position)

            # Primary or secondary damage
            dmg = damage if i == 0 else secondary_damage
            self._deal_damage(unit, target, dmg + unit.stats.ap,
                             DamageType.MAGIC, "leblanc_distortion")

            # Stun
            self._apply_stun(target, stun_duration, "leblanc_stun")

        unit.stats.mana = 0
        return True

    def _cast_leona(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                    ability_vars: Dict) -> bool:
        """Leona - Solar Eclipse: Passive DR + taunt."""
        from .combat_engine import DamageType

        flat_dr = self._get_var(ability_vars, 'FlatDR', unit.star_level, 15)
        moonlight_dr = self._get_var(ability_vars, 'MoonlightDamageReduction', unit.star_level, 0.10)

        # Check for Diana synergy
        has_diana = any(u.api_name == "TFT16_Diana" and u.is_alive
                       for u in self.engine.units if u.team == unit.team)

        # Apply passive damage reduction
        unit.stats.damage_reduction += flat_dr / 100  # Convert to percentage

        if has_diana:
            unit.stats.damage_reduction += moonlight_dr
            self.engine.log_event('leona_diana_synergy', unit=unit.name, bonus_dr=moonlight_dr)

        # Taunt nearby enemies (make them target Leona)
        for enemy in enemies:
            if enemy.is_alive and self._hex_distance(unit.position, enemy.position) <= 2:
                enemy.target = unit
                self.engine.log_event('leona_taunt', taunted=enemy.name)

        unit.stats.mana = 0
        return True

    def _cast_milio(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                    ability_vars: Dict) -> bool:
        """Milio - Ultra Mega Fire Kick: Bouncing fireball."""
        from .combat_engine import DamageType

        num_bounces = int(self._get_var(ability_vars, 'NumBounces', unit.star_level, 3))
        damage = self._get_var(ability_vars, 'MagicDamage', unit.star_level, 190)
        aoe_damage = self._get_var(ability_vars, 'MagicDamageAOE', unit.star_level, 160)
        bounce_range = int(self._get_var(ability_vars, 'BounceSearchRange', unit.star_level, 2))

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        hit_enemies = set()
        current_target = target

        for bounce in range(num_bounces):
            if not current_target or not current_target.is_alive:
                break

            hit_enemies.add(current_target)

            # Main damage on bounce target
            self._deal_damage(unit, current_target, damage + unit.stats.ap,
                             DamageType.MAGIC, f"milio_bounce_{bounce+1}")

            # AoE damage to nearby
            nearby = self._get_enemies_in_radius(current_target.position, 1, enemies)
            for enemy in nearby:
                if enemy != current_target and enemy not in hit_enemies:
                    self._deal_damage(unit, enemy, aoe_damage + unit.stats.ap * 0.5,
                                     DamageType.MAGIC, "milio_splash")

            # Find next bounce target
            next_targets = [e for e in self._get_enemies_in_radius(current_target.position, bounce_range, enemies)
                           if e not in hit_enemies and e.is_alive]
            current_target = next_targets[0] if next_targets else None

        unit.stats.mana = 0
        return True

    def _cast_missfortune(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                          ability_vars: Dict) -> bool:
        """Miss Fortune - Bullet Time: Multi-wave AOE + ricochet autos."""
        from .combat_engine import DamageType

        ricochet_mult = self._get_var(ability_vars, 'AutoRicochetMultiplier', unit.star_level, 0.5)
        base_waves = int(self._get_var(ability_vars, 'BaseNumWaves', unit.star_level, 2))
        casts_per_wave = int(self._get_var(ability_vars, 'NumCaststoGainExtraWave', unit.star_level, 3))

        # Track casts for extra waves
        if not hasattr(unit, '_mf_casts'):
            unit._mf_casts = 0
        unit._mf_casts += 1

        extra_waves = unit._mf_casts // casts_per_wave
        total_waves = base_waves + extra_waves

        # Fire waves across the board
        unit_col = unit.position[1]
        targets_hit = []

        for wave in range(total_waves):
            for enemy in enemies:
                if not enemy.is_alive or not enemy.is_targetable:
                    continue

                # Hit enemies in cone (simplified as row-based)
                if abs(enemy.position[1] - unit_col) <= 2:
                    wave_damage = (unit.stats.ad * 0.5) * (1 - 0.1 * wave)  # Falloff per wave
                    self._deal_damage(unit, enemy, wave_damage,
                                     DamageType.PHYSICAL, f"mf_wave_{wave+1}")
                    if enemy.name not in targets_hit:
                        targets_hit.append(enemy.name)

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Bullet Time",
                             waves=total_waves)
        return True

    def _cast_nidalee(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                      ability_vars: Dict) -> bool:
        """Nidalee - Javelin Toss / Takedown: Huntress execute with role-based damage."""
        from .combat_engine import DamageType

        target_damage = self._get_var(ability_vars, 'TargetDamage', unit.star_level, 320)
        secondary_damage = self._get_var(ability_vars, 'SecondaryDamage', unit.star_level, 100)
        tank_mult = self._get_var(ability_vars, 'TankDamageMult', unit.star_level, 0.6)
        fighter_mult = self._get_var(ability_vars, 'FighterDamageMult', unit.star_level, 0.3)
        reduction_per_cast = self._get_var(ability_vars, 'DamageReductionPerCast', unit.star_level, 0.7)

        # Track casts for damage reduction
        if not hasattr(unit, '_nidalee_casts'):
            unit._nidalee_casts = 0
        unit._nidalee_casts += 1

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Calculate damage with role-based reduction
        damage = target_damage + unit.stats.ap

        if 'Tank' in target.role:
            damage *= tank_mult
        elif 'Fighter' in target.role:
            damage *= fighter_mult

        # Reduction per prior cast
        if unit._nidalee_casts > 1:
            damage *= (reduction_per_cast ** (unit._nidalee_casts - 1))

        self._deal_damage(unit, target, damage, DamageType.MAGIC, "nidalee_javelin")

        # Secondary damage to nearby
        nearby = self._get_enemies_in_radius(target.position, 1, enemies)
        for enemy in nearby:
            if enemy != target:
                self._deal_damage(unit, enemy, secondary_damage + unit.stats.ap * 0.3,
                                 DamageType.MAGIC, "nidalee_pounce")

        unit.stats.mana = 0
        return True

    def _cast_singed(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                     ability_vars: Dict) -> bool:
        """Singed - Poison Trail: Walk through enemies, drawing aggro."""
        from .combat_engine import DamageType

        dps = self._get_var(ability_vars, 'DamagePerSecond', unit.star_level, 8)
        armor_mr_reduction = self._get_var(ability_vars, 'ArmorMR', unit.star_level, 20)
        heal_per_sec = self._get_var(ability_vars, 'HealPerSecond', unit.star_level, 15)
        duration = self._get_var(ability_vars, 'PoisonCloudDuration', unit.star_level, 4)

        # Singed walks through enemy team (dash to far side)
        far_enemy = self._find_farthest_enemy(unit, enemies)
        if far_enemy:
            self._dash_to_position(unit, far_enemy.position)

        # Apply poison to all enemies passed
        for enemy in enemies:
            if enemy.is_alive and enemy.is_targetable:
                # Apply stat reduction
                enemy.stats.armor = max(0, enemy.stats.armor - armor_mr_reduction)
                enemy.stats.magic_resist = max(0, enemy.stats.magic_resist - armor_mr_reduction)

                # Poison damage over time
                total_damage = dps * duration
                self._deal_damage(unit, enemy, total_damage + unit.stats.ap,
                                 DamageType.MAGIC, "singed_poison")

                # Draw aggro (make enemies target Singed)
                if enemy.is_backline:  # Backline especially re-targets
                    enemy.target = unit

        # Self-heal
        heal = heal_per_sec * duration
        self.engine.heal_unit(unit, heal, "singed_heal")

        unit.stats.mana = 0
        return True

    def _cast_taric(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                    ability_vars: Dict) -> bool:
        """Taric - Cosmic Radiance: Ally MR aura + invulnerability."""
        from .combat_engine import DamageType

        passive_dr = self._get_var(ability_vars, 'PassiveDR', unit.star_level, 0.9)
        invuln_threshold = self._get_var(ability_vars, 'InvunerabilityHealthThreshold', unit.star_level, 0.35)
        invuln_duration = self._get_var(ability_vars, 'InvunerabilityDuration', unit.star_level, 2)
        passive_heal = self._get_var(ability_vars, 'PassiveHeal', unit.star_level, 300)
        mr_for_allies = self._get_var(ability_vars, 'MRForAllies', unit.star_level, 10)

        # Apply MR aura to allies
        for ally in allies:
            if ally.is_alive:
                ally.stats.magic_resist += mr_for_allies

        # Apply passive DR to self
        unit.stats.damage_reduction = max(unit.stats.damage_reduction, passive_dr)

        # Check for invulnerability threshold
        hp_percent = unit.stats.hp / unit.stats.max_hp
        if hp_percent <= invuln_threshold:
            if not hasattr(unit, '_taric_invuln_used'):
                unit._taric_invuln_used = True
                unit.is_targetable = False
                unit.untargetable_duration = invuln_duration
                self.engine.heal_unit(unit, passive_heal, "taric_invuln_heal")
                self.engine.log_event('taric_invuln', unit=unit.name)

        unit.stats.mana = 0
        return True

    def _cast_thresh(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                     ability_vars: Dict) -> bool:
        """Thresh - The Box: Hook enemies, drain health based on team's Shadow Isles souls."""
        from .combat_engine import DamageType

        # Get soul count from centralized TraitManager
        soul_count = getattr(self.engine.trait_manager, 'shadow_isles_souls', 0)

        # Get damage variables
        health_drain_per_soul = self._get_var(ability_vars, 'HealthDrainPerSoul', unit.star_level, 5)
        box_damage = self._get_var(ability_vars, 'APPassiveDamage', unit.star_level, 50)

        # Hook nearest enemy
        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if target:
            # Pull target towards Thresh
            old_pos = target.position
            self._dash_to_position(target, unit.position)
            self.engine.log_event('thresh_hook', unit=unit.name, target=target.name,
                                 from_pos=old_pos)

            # Box damage
            self._deal_damage(unit, target, box_damage + unit.stats.ap,
                             DamageType.MAGIC, "thresh_box")

            # Drain based on team's Shadow Isles souls
            if soul_count > 0:
                drain_damage = health_drain_per_soul * soul_count
                self._deal_damage(unit, target, drain_damage, DamageType.MAGIC, "thresh_soul_drain")
                self.engine.heal_unit(unit, drain_damage * 0.5, "thresh_soul_heal")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="The Box",
                             souls=soul_count, drain=health_drain_per_soul * soul_count if soul_count > 0 else 0)
        return True

    def _cast_warwick(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                      ability_vars: Dict) -> bool:
        """Warwick - Infinite Duress: Single cast, ally AS buff."""
        from .combat_engine import DamageType

        # Track if already cast (single cast only)
        if hasattr(unit, '_warwick_cast'):
            return False

        unit._warwick_cast = True

        attack_speed = self._get_var(ability_vars, 'AttackSpeed', unit.star_level, 0.8)
        omnivamp = self._get_var(ability_vars, 'Omnivamp', unit.star_level, 0.15)
        ally_as = self._get_var(ability_vars, 'AllyAttackSpeed', unit.star_level, 0.2)
        ally_duration = self._get_var(ability_vars, 'AllyBuffDuration', unit.star_level, 3)

        # Buff self
        unit.stats.attack_speed += attack_speed
        unit.stats.omnivamp += omnivamp

        # Buff allies
        for ally in allies:
            if ally.is_alive and ally != unit:
                ally.stats.attack_speed += ally_as

        self.engine.log_event('warwick_infinite_duress', unit=unit.name,
                             ally_as_buff=ally_as)

        unit.stats.mana = 0
        return True

    def _cast_xerath(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                     ability_vars: Dict) -> bool:
        """Xerath - Rite of the Arcane: Multiple blasts across random enemies."""
        from .combat_engine import DamageType

        num_blasts = int(self._get_var(ability_vars, 'NumberOfBlasts', unit.star_level, 10))
        damage = self._get_var(ability_vars, 'Damage', unit.star_level, 390)
        range_enemies = int(self._get_var(ability_vars, 'SpellRangeInEnemies', unit.star_level, 4))
        charm_bonus = int(self._get_var(ability_vars, 'XerathCharmExtraBlasts', unit.star_level, 3))

        # Check for charm item (simplified)
        has_charm = any(i.name == "XerathCharm" for i in unit.items)
        if has_charm:
            num_blasts += charm_bonus

        valid_targets = [e for e in enemies if e.is_alive and e.is_targetable][:range_enemies]

        if not valid_targets:
            return False

        # Distribute blasts evenly
        blasts_per_target = num_blasts // len(valid_targets)
        remainder = num_blasts % len(valid_targets)

        for i, target in enumerate(valid_targets):
            target_blasts = blasts_per_target + (1 if i < remainder else 0)
            for _ in range(target_blasts):
                if not target.is_alive:
                    break
                self._deal_damage(unit, target, damage + unit.stats.ap,
                                 DamageType.MAGIC, "xerath_blast")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Rite of the Arcane",
                             blasts=num_blasts)
        return True

    def _cast_zilean(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                     ability_vars: Dict) -> bool:
        """Zilean - Time Bomb: Distance-based targeting with chain explosions."""
        from .combat_engine import DamageType, HexGrid

        magic_damage = self._get_var(ability_vars, 'MagicDamage', unit.star_level, 75)
        explosion_damage = self._get_var(ability_vars, 'ExplosionDamage', unit.star_level, 150)
        mana_on_kill = self._get_var(ability_vars, 'ManaOnKill', unit.star_level, 15)

        # Target farthest enemy
        target = self._find_farthest_enemy(unit, enemies)
        if not target:
            return False

        # Track bombs on target
        if not hasattr(target, '_zilean_bombs'):
            target._zilean_bombs = 0
        target._zilean_bombs += 1

        # Apply initial damage
        self._deal_damage(unit, target, magic_damage + unit.stats.ap,
                         DamageType.MAGIC, "zilean_bomb")

        # Check for double bomb explosion
        if target._zilean_bombs >= 2:
            target._zilean_bombs = 0

            # Big explosion
            self._deal_damage(unit, target, explosion_damage + unit.stats.ap,
                             DamageType.MAGIC, "zilean_explosion")

            # Chain to nearby enemies
            nearby = self._get_enemies_in_radius(target.position, 2, enemies)
            for enemy in nearby:
                if enemy != target and enemy.is_alive:
                    self._deal_damage(unit, enemy, explosion_damage * 0.5,
                                     DamageType.MAGIC, "zilean_chain")

        # Mana on kill
        if not target.is_alive:
            unit.stats.mana = min(unit.stats.mana + mana_on_kill, unit.stats.max_mana)

        unit.stats.mana = 0
        return True

    def _cast_loris(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                    ability_vars: Dict) -> bool:
        """Loris - Piltover Tussle: Dash + taunt + knockup."""
        from .combat_engine import DamageType

        shield_amount = self._get_var(ability_vars, 'Shield', unit.star_level, 700)
        damage = self._get_var(ability_vars, 'Damage', unit.star_level, 150)
        knockup_duration = self._get_var(ability_vars, 'KnockupDuration', unit.star_level, 1.25)

        # Apply shield
        self.engine.apply_shield(unit, shield_amount, "loris_shield")

        # Dash to target
        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if target:
            self._dash_to_position(unit, target.position)

            # Knockup (stun) and damage
            self._apply_stun(target, knockup_duration, "loris_knockup")
            self._deal_damage(unit, target, damage + unit.stats.armor * 0.5,
                             DamageType.PHYSICAL, "loris_slam")

            # Taunt nearby enemies
            nearby = self._get_enemies_in_radius(unit.position, 2, enemies)
            for enemy in nearby:
                enemy.target = unit

        unit.stats.mana = 0
        return True

    def _cast_skarner(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                      ability_vars: Dict) -> bool:
        """Skarner - Impale: Grab multiple enemies, armor aura."""
        from .combat_engine import DamageType

        armor_for_allies = self._get_var(ability_vars, 'ArmorForAllies', unit.star_level, 10)
        impale_duration = self._get_var(ability_vars, 'ImpaleDuration', unit.star_level, 2)
        damage_pct_armor = self._get_var(ability_vars, 'DamagePercentArmor', unit.star_level, 1.2)
        max_targets = int(self._get_var(ability_vars, 'ImpaleMaxTargets', unit.star_level, 3))

        # Apply armor aura to allies
        for ally in allies:
            if ally.is_alive:
                ally.stats.armor += armor_for_allies

        # Grab multiple enemies
        targets = sorted([e for e in enemies if e.is_alive and e.is_targetable],
                        key=lambda e: self._hex_distance(unit.position, e.position))[:max_targets]

        for target in targets:
            # Pull to Skarner (impale)
            old_pos = target.position
            self._dash_to_position(target, unit.position)

            # Stun during impale
            self._apply_stun(target, impale_duration, "skarner_impale")

            # Armor-scaling damage
            damage = unit.stats.armor * damage_pct_armor
            self._deal_damage(unit, target, damage, DamageType.PHYSICAL, "skarner_impale")

            self.engine.log_event('skarner_grab', target=target.name, from_pos=old_pos)

        unit.stats.mana = 0
        return True

    def _cast_shyvana(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                      ability_vars: Dict) -> bool:
        """Shyvana - Dragon Transformation: Transform with bonus stats."""
        from .combat_engine import DamageType

        transform_hp = self._get_var(ability_vars, 'TransformHP', unit.star_level, 600)
        transform_durability = self._get_var(ability_vars, 'TransformDurability', unit.star_level, 0.2)
        divebomb_damage = self._get_var(ability_vars, 'DivebombADDamage', unit.star_level, 100)
        fire_dps = self._get_var(ability_vars, 'FireDamagePerSecond', unit.star_level, 185)
        duration = self._get_var(ability_vars, 'SpellDuration', unit.star_level, 3)

        # Track dragon form
        if not hasattr(unit, '_shyvana_dragon'):
            unit._shyvana_dragon = False

        if not unit._shyvana_dragon:
            # Transform into dragon
            unit._shyvana_dragon = True
            unit.stats.max_hp += transform_hp
            unit.stats.hp += transform_hp
            unit.stats.damage_reduction += transform_durability

            # Divebomb damage to target
            target = unit.target or self._find_nearest_enemy(unit, enemies)
            if target:
                self._dash_to_position(unit, target.position)
                self._deal_damage(unit, target, divebomb_damage + unit.stats.ad,
                                 DamageType.PHYSICAL, "shyvana_divebomb")

            self.engine.log_event('shyvana_transform', unit=unit.name)
        else:
            # Dragon form fire breath
            nearby = self._get_enemies_in_radius(unit.position, 2, enemies)
            total_fire = fire_dps * duration
            for enemy in nearby:
                self._deal_damage(unit, enemy, total_fire + unit.stats.ap,
                                 DamageType.MAGIC, "shyvana_fire")

        unit.stats.mana = 0
        return True

    # =========================================================================
    # IMMORTAL TRAIT - Resurrection for Zaahen
    # =========================================================================

    def check_immortal_resurrection(self, unit: 'Unit') -> bool:
        """Check if unit should resurrect via Immortal trait."""
        if 'Immortal' not in unit.traits:
            return False

        if hasattr(unit, '_immortal_used'):
            return False

        # Resurrect with 60% HP
        unit._immortal_used = True
        unit.is_alive = True
        unit.stats.hp = unit.stats.max_hp * 0.6
        from .combat_engine import UnitState
        unit.state = UnitState.IDLE

        self.engine.log_event('immortal_resurrect', unit=unit.name,
                             hp=unit.stats.hp)
        return True

    # =========================================================================
    # LUCIAN & SENNA - Soulbound Transition
    # =========================================================================

    def _cast_lucian(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                     ability_vars: Dict) -> bool:
        """Lucian - The Culling: Channel then swap to Senna.

        Soulbound mechanic: Lucian and Senna swap when either casts.
        While Lucian is out: Team gets 7% damage amp
        While Senna is out: Team gets 7% damage reduction
        """
        from .combat_engine import DamageType

        # Get ability variables
        duration = self._get_var(ability_vars, 'Duration', unit.star_level, 3.0)
        ap_damage = self._get_var(ability_vars, 'APDamage', unit.star_level, 12)
        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 120)
        num_shots = int(self._get_var(ability_vars, 'NumShots', unit.star_level, 12))
        armor_reduction = self._get_var(ability_vars, 'FlatArmorReduction', unit.star_level, 3)

        # Fire shots at current target
        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Apply armor reduction
        target.stats.armor = max(0, target.stats.armor - armor_reduction)

        # Deal damage with all shots
        damage_per_shot = ad_damage + unit.stats.ad + ap_damage + unit.stats.ap
        for i in range(num_shots):
            if not target.is_alive:
                target = self._find_nearest_enemy(unit, enemies)
                if not target:
                    break
            self._deal_damage(unit, target, damage_per_shot,
                             DamageType.PHYSICAL, f"lucian_shot_{i+1}")

        # Swap to Senna after casting
        self._soulbound_swap(unit, allies, to_senna=True)

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="The Culling",
                             shots=num_shots)
        return True

    def _cast_senna(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                    ability_vars: Dict) -> bool:
        """Senna - Dawning Shadow: Long-range beam then swap to Lucian.

        Note: Senna shares data with Lucian in combat_data.json.
        Using estimated values based on typical Senna mechanics.
        """
        from .combat_engine import DamageType

        # Senna's ability: Line damage + heal allies
        # Using similar scaling to Lucian
        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 120)
        ap_damage = self._get_var(ability_vars, 'APDamage', unit.star_level, 12)

        # Fire beam across the board (hits all enemies in line)
        unit_row = unit.position[0]
        targets_hit = []

        for enemy in enemies:
            if not enemy.is_alive or not enemy.is_targetable:
                continue
            # Hit enemies in same row or adjacent
            if abs(enemy.position[0] - unit_row) <= 1:
                damage = ad_damage + unit.stats.ad + ap_damage + unit.stats.ap
                self._deal_damage(unit, enemy, damage, DamageType.PHYSICAL, "senna_beam")
                targets_hit.append(enemy.name)

        # Heal allies in beam path
        heal_amount = (ap_damage + unit.stats.ap) * 0.5
        for ally in allies:
            if ally.is_alive and abs(ally.position[0] - unit_row) <= 1:
                self.engine.heal_unit(ally, heal_amount, "senna_heal")

        # Swap back to Lucian after casting
        self._soulbound_swap(unit, allies, to_senna=False)

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Dawning Shadow",
                             targets=targets_hit)
        return True

    def _soulbound_swap(self, unit: 'Unit', allies: List['Unit'], to_senna: bool):
        """Handle Soulbound swap between Lucian and Senna.

        - When swapping to Senna: Remove damage amp, add damage reduction
        - When swapping to Lucian: Remove damage reduction, add damage amp
        """
        damage_amp = 0.07  # 7% from Soulbound trait
        damage_reduction = 0.07

        # Track which form is active
        if not hasattr(unit, '_soulbound_is_senna'):
            unit._soulbound_is_senna = False

        if to_senna and not unit._soulbound_is_senna:
            # Swap to Senna
            unit._soulbound_is_senna = True
            unit.name = "Senna"
            unit.api_name = "TFT16_Senna"

            # Update team buffs: Remove damage amp, add damage reduction
            for ally in allies:
                if ally.is_alive:
                    ally.stats.damage_amp = max(0, ally.stats.damage_amp - damage_amp)
                    ally.stats.damage_reduction += damage_reduction

            self.engine.log_event('soulbound_swap', from_unit="Lucian", to_unit="Senna",
                                 team_buff="7% Damage Reduction")

        elif not to_senna and unit._soulbound_is_senna:
            # Swap to Lucian
            unit._soulbound_is_senna = False
            unit.name = "Lucian & Senna"
            unit.api_name = "TFT16_Lucian"

            # Update team buffs: Remove damage reduction, add damage amp
            for ally in allies:
                if ally.is_alive:
                    ally.stats.damage_reduction = max(0, ally.stats.damage_reduction - damage_reduction)
                    ally.stats.damage_amp += damage_amp

            self.engine.log_event('soulbound_swap', from_unit="Senna", to_unit="Lucian",
                                 team_buff="7% Damage Amp")

    # =========================================================================
    # RYZE - Trait-Dependent Ability
    # =========================================================================

    def _cast_ryze(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                   ability_vars: Dict) -> bool:
        """Ryze - Runic Overload: Ability effect changes based on active team traits.

        25+ trait interactions with different effects.
        """
        from .combat_engine import DamageType

        # Base damage
        base_damage = self._get_var(ability_vars, 'Damage', unit.star_level, 425)
        split_damage_pct = self._get_var(ability_vars, 'SplitPercentDamage', unit.star_level, 0.33)

        # Get active traits on team
        team_traits = self._get_team_traits(unit, allies)

        # Find primary target
        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Base damage to primary target
        damage = base_damage + unit.stats.ap
        actual, _ = self._deal_damage(unit, target, damage, DamageType.MAGIC, "ryze_overload")

        # Secondary damage to nearby enemies
        nearby = self._get_enemies_in_radius(target.position, 2, enemies)
        for enemy in nearby:
            if enemy != target:
                secondary_damage = damage * split_damage_pct
                self._deal_damage(unit, enemy, secondary_damage, DamageType.MAGIC, "ryze_split")

        # Apply trait-specific effects
        effect_applied = self._apply_ryze_trait_effect(unit, target, enemies, allies, ability_vars, team_traits)

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Runic Overload",
                             active_traits=list(team_traits.keys()), effect=effect_applied)
        return True

    def _get_team_traits(self, unit: 'Unit', allies: List['Unit']) -> Dict[str, int]:
        """Get all active traits and their counts on the team."""
        trait_counts = {}
        all_units = [unit] + [a for a in allies if a.is_alive]

        for u in all_units:
            for trait in u.traits:
                trait_counts[trait] = trait_counts.get(trait, 0) + 1

        return trait_counts

    def _apply_ryze_trait_effect(self, unit: 'Unit', target: 'Unit',
                                  enemies: List['Unit'], allies: List['Unit'],
                                  ability_vars: Dict, team_traits: Dict[str, int]) -> str:
        """Apply Ryze's trait-dependent effect based on active traits.

        Returns the name of the effect applied.
        """
        from .combat_engine import DamageType

        # Priority order for trait effects (higher priority first)
        # Each trait gives a unique bonus effect

        # TARGON - 10% heal
        if team_traits.get('Targon', 0) >= 2:
            heal_pct = self._get_var(ability_vars, 'TargonHealPercent', unit.star_level, 0.10)
            heal_amount = unit.stats.max_hp * heal_pct
            self.engine.heal_unit(unit, heal_amount, "ryze_targon")
            return "Targon: 10% HP heal"

        # YORDLE - 12% damage reduction for 4s
        if team_traits.get('Yordle', 0) >= 3:
            dr_pct = self._get_var(ability_vars, 'YordleDamageReductionPercent', unit.star_level, 0.12)
            unit.stats.damage_reduction += dr_pct
            # Note: Duration tracking would need buff system
            return f"Yordle: {dr_pct*100:.0f}% DR"

        # BILGEWATER - 25% explosion damage
        if team_traits.get('Bilgewater', 0) >= 3:
            explosion_pct = self._get_var(ability_vars, 'BilgewaterExplosionPercent', unit.star_level, 0.25)
            base_damage = self._get_var(ability_vars, 'Damage', unit.star_level, 425)
            explosion_damage = (base_damage + unit.stats.ap) * explosion_pct
            nearby = self._get_enemies_in_radius(target.position, 2, enemies)
            for enemy in nearby:
                self._deal_damage(unit, enemy, explosion_damage, DamageType.MAGIC, "ryze_bilgewater")
            return f"Bilgewater: {explosion_pct*100:.0f}% explosion"

        # VOID - 30% resist ignore
        if team_traits.get('Void', 0) >= 2:
            resist_ignore = self._get_var(ability_vars, 'VoidResistIgnore', unit.star_level, 0.30)
            # Apply as MR shred
            mr_shred = target.stats.magic_resist * resist_ignore
            target.stats.magic_resist = max(0, target.stats.magic_resist - mr_shred)
            return f"Void: {resist_ignore*100:.0f}% resist ignore"

        # SHADOW ISLES - 5% + soul scaling
        if team_traits.get('Shadow Isles', 0) >= 2:
            base_pct = self._get_var(ability_vars, 'ShadowIslesBasePercentage', unit.star_level, 0.05)
            souls_per_bonus = self._get_var(ability_vars, 'ShadowIslesSoulsNeededForOnePercentBonusDamage', unit.star_level, 8)
            # Get soul count from trait manager
            soul_count = getattr(self.engine.trait_manager, 'shadow_isles_souls', 0)
            bonus_pct = soul_count / souls_per_bonus / 100  # Convert to percentage
            total_pct = base_pct + bonus_pct
            bonus_damage = (self._get_var(ability_vars, 'Damage', unit.star_level, 425) + unit.stats.ap) * total_pct
            self._deal_damage(unit, target, bonus_damage, DamageType.MAGIC, "ryze_shadow_isles")
            return f"Shadow Isles: {total_pct*100:.1f}% bonus ({soul_count} souls)"

        # PILTOVER - 40% overcharge
        if team_traits.get('Piltover', 0) >= 2:
            overcharge_pct = self._get_var(ability_vars, 'PiltoverOverchargePercentBonus', unit.star_level, 0.40)
            overcharge_damage = (self._get_var(ability_vars, 'Damage', unit.star_level, 425) + unit.stats.ap) * overcharge_pct
            self._deal_damage(unit, target, overcharge_damage, DamageType.MAGIC, "ryze_piltover")
            return f"Piltover: {overcharge_pct*100:.0f}% overcharge"

        # DEMACIA - 12% execute threshold
        if team_traits.get('Demacia', 0) >= 2:
            execute_threshold = self._get_var(ability_vars, 'DemaciaExecuteThreshold', unit.star_level, 0.12)
            if target.is_alive and target.stats.hp / target.stats.max_hp <= execute_threshold:
                self.engine.apply_damage(unit, target, target.stats.hp + 1,
                                        DamageType.TRUE, "ryze_demacia_execute")
                return f"Demacia: Execute at {execute_threshold*100:.0f}%"
            return f"Demacia: {execute_threshold*100:.0f}% execute threshold (not triggered)"

        # FRELJORD - chill + 6% max HP true damage
        if team_traits.get('Freljord', 0) >= 2:
            chill_duration = self._get_var(ability_vars, 'FreljordChillDuration', unit.star_level, 4.0)
            true_damage_pct = self._get_var(ability_vars, 'FreljordTrueDamagePercentHealth', unit.star_level, 0.06)
            # Apply chill (slow attack speed)
            target.stats.attack_speed *= 0.7  # 30% AS slow
            # True damage
            true_damage = target.stats.max_hp * true_damage_pct
            self.engine.apply_damage(unit, target, true_damage, DamageType.TRUE, "ryze_freljord")
            return f"Freljord: Chill + {true_damage_pct*100:.0f}% max HP true damage"

        # ZAUN - poison ticks
        if team_traits.get('Zaun', 0) >= 2:
            poison_damage = self._get_var(ability_vars, 'ZaunDamage', unit.star_level, 30)
            base_ticks = int(self._get_var(ability_vars, 'ZaunBaseTicks', unit.star_level, 3))
            poison_duration = self._get_var(ability_vars, 'ZaunPoisonDuration', unit.star_level, 4.0)
            total_poison = poison_damage * base_ticks
            self._deal_damage(unit, target, total_poison + unit.stats.ap, DamageType.MAGIC, "ryze_zaun_poison")
            return f"Zaun: {base_ticks} poison ticks"

        # SHURIMA - knockup + gold/component chance
        if team_traits.get('Shurima', 0) >= 2:
            knockup_duration = self._get_var(ability_vars, 'ShurimaKnockUpDuration', unit.star_level, 0.5)
            self._apply_stun(target, knockup_duration, "ryze_shurima_knockup")
            # Gold chance (tracked for post-combat)
            coin_chance = self._get_var(ability_vars, 'ShurimaCoinChance', unit.star_level, 0.12)
            if not hasattr(unit, '_ryze_shurima_gold_chances'):
                unit._ryze_shurima_gold_chances = 0
            unit._ryze_shurima_gold_chances += 1
            return f"Shurima: {knockup_duration}s knockup + {coin_chance*100:.0f}% gold chance"

        # NOXUS - damage reduction
        if team_traits.get('Noxus', 0) >= 3:
            dr_pct = self._get_var(ability_vars, 'NoxusPercentDamageReduction', unit.star_level, 0.60)
            # Apply to nearby allies (brief DR)
            nearby_allies = [a for a in allies if a.is_alive and
                           self._hex_distance(unit.position, a.position) <= 2]
            for ally in nearby_allies:
                ally.stats.damage_reduction += dr_pct * 0.25  # Scaled down for balance
            return f"Noxus: {dr_pct*25:.0f}% DR to nearby allies"

        # IONIA - reduced damage taken
        if team_traits.get('Ionia', 0) >= 3:
            dr_pct = self._get_var(ability_vars, 'IoniaDamageReduction', unit.star_level, 0.50)
            unit.stats.damage_reduction += dr_pct * 0.5  # 25% for 1 cast
            return f"Ionia: {dr_pct*50:.0f}% damage reduction"

        # No matching trait - default effect
        return "No trait bonus"

    # =========================================================================
    # SYLAS - Trifold Ability Rotation
    # =========================================================================

    def _cast_sylas(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                    ability_vars: Dict) -> bool:
        """Sylas - Stolen Might: Rotates between 3 stolen abilities.

        1. Jarvan - AoE stun
        2. Garen - Single target execute
        3. Lux - Team shield + line damage

        Cannot cast the same ability twice in a row.
        """
        from .combat_engine import DamageType

        # Track which ability was last used (0=none, 1=jarvan, 2=garen, 3=lux)
        if not hasattr(unit, '_sylas_last_ability'):
            unit._sylas_last_ability = 0

        # Determine which ability to use based on situation
        # Priority: Execute (Garen) if target is low, Stun (Jarvan) if multiple enemies, Shield (Lux) if low HP
        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Get all ability variables
        jarvan_damage = self._get_var(ability_vars, 'JarvanDamage', unit.star_level, 180)
        jarvan_stun = self._get_var(ability_vars, 'JarvanStunDuration', unit.star_level, 1.75)
        jarvan_radius = int(self._get_var(ability_vars, 'JarvanSearchRadius', unit.star_level, 2))

        garen_damage = self._get_var(ability_vars, 'GarenDamage', unit.star_level, 1000)
        garen_execute = self._get_var(ability_vars, 'GarenExecute', unit.star_level, 0.15)

        lux_shield = self._get_var(ability_vars, 'LuxShield', unit.star_level, 450)
        lux_damage = self._get_var(ability_vars, 'LuxDamage', unit.star_level, 475)
        shield_duration = self._get_var(ability_vars, 'ShieldDuration', unit.star_level, 1.25)

        # Determine best ability (cannot repeat last)
        hp_percent = unit.stats.hp / unit.stats.max_hp
        target_hp_percent = target.stats.hp / target.stats.max_hp
        nearby_enemies = self._get_enemies_in_radius(unit.position, jarvan_radius, enemies)

        # Score each ability
        scores = {
            1: 0,  # Jarvan - better with more enemies
            2: 0,  # Garen - better against low HP targets
            3: 0,  # Lux - better when Sylas is low HP
        }

        # Jarvan score: more enemies nearby = better
        if unit._sylas_last_ability != 1:
            scores[1] = len(nearby_enemies) * 2 + (1 if len(nearby_enemies) >= 3 else 0)

        # Garen score: target is low HP = better (execute potential)
        if unit._sylas_last_ability != 2:
            if target_hp_percent <= garen_execute:
                scores[2] = 10  # Guaranteed execute
            else:
                scores[2] = (1 - target_hp_percent) * 5  # Lower HP = higher score

        # Lux score: Sylas is low HP = better (needs shield)
        if unit._sylas_last_ability != 3:
            scores[3] = (1 - hp_percent) * 5 + 1  # Lower HP = higher score

        # Pick highest scoring ability
        best_ability = max(scores.keys(), key=lambda k: scores[k])

        # Execute the chosen ability
        if best_ability == 1:
            # JARVAN - AoE stun
            for enemy in nearby_enemies:
                self._apply_stun(enemy, jarvan_stun, "sylas_jarvan_stun")
                self._deal_damage(unit, enemy, jarvan_damage + unit.stats.ap,
                                 DamageType.MAGIC, "sylas_jarvan")
            unit._sylas_last_ability = 1
            ability_name = "Jarvan (AoE Stun)"
            self.engine.log_event('sylas_ability', unit=unit.name, ability="Jarvan",
                                 targets=[e.name for e in nearby_enemies], stun=jarvan_stun)

        elif best_ability == 2:
            # GAREN - Execute
            if target_hp_percent <= garen_execute:
                # Execute!
                self.engine.apply_damage(unit, target, target.stats.hp + 1,
                                        DamageType.TRUE, "sylas_garen_execute")
                self.engine.log_event('execute', unit=unit.name, target=target.name,
                                     threshold=garen_execute, ability="Garen")
            else:
                # Normal damage
                self._deal_damage(unit, target, garen_damage + unit.stats.ap,
                                 DamageType.MAGIC, "sylas_garen")
            unit._sylas_last_ability = 2
            ability_name = "Garen (Execute)"

        else:
            # LUX - Shield + line damage
            # Shield self and nearby allies
            self.engine.apply_shield(unit, lux_shield + unit.stats.ap * 0.5, "sylas_lux_shield")
            nearby_allies = [a for a in allies if a.is_alive and
                           self._hex_distance(unit.position, a.position) <= 2]
            for ally in nearby_allies:
                self.engine.apply_shield(ally, lux_shield * 0.5, "sylas_lux_shield")

            # Line damage toward target
            unit_row = unit.position[0]
            for enemy in enemies:
                if enemy.is_alive and enemy.is_targetable:
                    if abs(enemy.position[0] - unit_row) <= 1:
                        self._deal_damage(unit, enemy, lux_damage + unit.stats.ap,
                                         DamageType.MAGIC, "sylas_lux_beam")
            unit._sylas_last_ability = 3
            ability_name = "Lux (Shield + Beam)"

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability=f"Stolen Might: {ability_name}",
                             last_ability=unit._sylas_last_ability)
        return True

    # =========================================================================
    # SHADOW ISLES SOUL COLLECTION - Champion Updates
    # =========================================================================

    def _cast_gwen(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                   ability_vars: Dict) -> bool:
        """Gwen - Snip Snip!: Cone damage with extra snips from souls."""
        from .combat_engine import DamageType

        base_snips = int(self._get_var(ability_vars, 'SnipCount', unit.star_level, 5))
        snip_per_soul = self._get_var(ability_vars, 'SnipPerSoulBreakpoint', unit.star_level, 1)
        soul_breakpoint = self._get_var(ability_vars, 'SoulBreakpoint', unit.star_level, 80)
        damage = self._get_var(ability_vars, 'Damage', unit.star_level, 68)
        secondary_damage = self._get_var(ability_vars, 'SecondaryDamage', unit.star_level, 30)

        # Get soul count for bonus snips
        soul_count = getattr(self.engine.trait_manager, 'shadow_isles_souls', 0)
        bonus_snips = int(soul_count / soul_breakpoint * snip_per_soul)
        total_snips = base_snips + bonus_snips

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Snip snip in a cone
        # Primary target gets all snips
        for i in range(total_snips):
            if not target.is_alive:
                target = self._find_nearest_enemy(unit, enemies)
                if not target:
                    break
            self._deal_damage(unit, target, damage + unit.stats.ap,
                             DamageType.MAGIC, f"gwen_snip_{i+1}")

        # Secondary targets in cone get fewer snips
        nearby = self._get_enemies_in_radius(target.position, 2, enemies)
        for enemy in nearby:
            if enemy != target and enemy.is_alive:
                snips_on_secondary = max(1, total_snips // 3)
                for _ in range(snips_on_secondary):
                    self._deal_damage(unit, enemy, secondary_damage + unit.stats.ap * 0.3,
                                     DamageType.MAGIC, "gwen_secondary_snip")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Snip Snip!",
                             snips=total_snips, souls=soul_count)
        return True

    def _cast_kalista(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                      ability_vars: Dict) -> bool:
        """Kalista - Endless Rend: Multi-target spears with soul scaling."""
        from .combat_engine import DamageType

        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 48)
        ap_damage = self._get_var(ability_vars, 'APDamage', unit.star_level, 5)
        num_enemies = int(self._get_var(ability_vars, 'NumberOfEnemies', unit.star_level, 4))
        base_spears = int(self._get_var(ability_vars, 'BaseSpears', unit.star_level, 20))
        souls_per_spear = self._get_var(ability_vars, 'SoulsPerSpearBreakpoint', unit.star_level, 25)
        spears_per_breakpoint = int(self._get_var(ability_vars, 'SpearsPerBreakpoint', unit.star_level, 1))
        armor_reduction = self._get_var(ability_vars, 'ArmorReduction', unit.star_level, 1)
        pct_on_primary = self._get_var(ability_vars, 'PercentMissilesOnPrimaryTarget', unit.star_level, 0.5)

        # Get soul count for bonus spears
        soul_count = getattr(self.engine.trait_manager, 'shadow_isles_souls', 0)
        bonus_spears = int(soul_count / souls_per_spear) * spears_per_breakpoint
        total_spears = base_spears + bonus_spears

        # Get targets
        targets = sorted([e for e in enemies if e.is_alive and e.is_targetable],
                        key=lambda e: self._hex_distance(unit.position, e.position))[:num_enemies]

        if not targets:
            return False

        primary_target = targets[0]
        primary_spears = int(total_spears * pct_on_primary)
        secondary_spears = total_spears - primary_spears

        # Apply armor reduction
        for target in targets:
            target.stats.armor = max(0, target.stats.armor - armor_reduction)

        # Primary target spears
        for i in range(primary_spears):
            if not primary_target.is_alive:
                break
            self._deal_damage(unit, primary_target, ad_damage + unit.stats.ad + ap_damage,
                             DamageType.PHYSICAL, "kalista_spear")

        # Secondary targets
        if len(targets) > 1:
            spears_each = secondary_spears // (len(targets) - 1)
            for target in targets[1:]:
                for _ in range(spears_each):
                    if not target.is_alive:
                        break
                    self._deal_damage(unit, target, ad_damage + unit.stats.ad,
                                     DamageType.PHYSICAL, "kalista_spear_secondary")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Endless Rend",
                             spears=total_spears, souls=soul_count)
        return True

    def _cast_viego(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                    ability_vars: Dict) -> bool:
        """Viego - Blade of the Ruined King: Stacking damage with soul AS scaling."""
        from .combat_engine import DamageType

        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 85)
        stacking_damage = self._get_var(ability_vars, 'StackingDamage', unit.star_level, 27)
        souls_for_as = self._get_var(ability_vars, 'SoulsForAttackSpeed', unit.star_level, 6)
        as_per_breakpoint = self._get_var(ability_vars, 'AttackSpeedPerSoulBreakpoint', unit.star_level, 1)
        base_as = self._get_var(ability_vars, 'BaseAttackSpeed', unit.star_level, 10) / 100  # Convert to decimal

        # Get soul count for bonus attack speed
        soul_count = getattr(self.engine.trait_manager, 'shadow_isles_souls', 0)
        bonus_as = (soul_count / souls_for_as) * as_per_breakpoint / 100  # Percentage

        # Track stacks on unit
        if not hasattr(unit, '_viego_stacks'):
            unit._viego_stacks = 0
        unit._viego_stacks += 1

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Deal damage with stacking bonus
        total_damage = ad_damage + unit.stats.ad + (stacking_damage * unit._viego_stacks)
        self._deal_damage(unit, target, total_damage, DamageType.PHYSICAL, "viego_blade")

        # Apply attack speed from souls (permanent for combat)
        if not hasattr(unit, '_viego_soul_as_applied'):
            unit._viego_soul_as_applied = True
            unit.stats.attack_speed += base_as + bonus_as
            self.engine.log_event('viego_soul_as', unit=unit.name, bonus_as=bonus_as, souls=soul_count)

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Blade of the Ruined King",
                             stacks=unit._viego_stacks, souls=soul_count)
        return True

