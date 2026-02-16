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
            return var_data.get(f'{star_level}star', default) or default
        # Scalar value
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
            self.engine.set_unit_position(unit, target_pos)
            self.engine.log_event('dash', unit=unit.name, from_pos=old_pos, to_pos=target_pos)
            return True

        # Find adjacent hex
        neighbors = HexGrid.get_neighbors(target_pos)
        valid = [n for n in neighbors if n not in occupied]
        if valid:
            old_pos = unit.position
            self.engine.set_unit_position(unit, valid[0])
            self.engine.log_event('dash', unit=unit.name, from_pos=old_pos, to_pos=valid[0])
            return True
        return False

    def _apply_stun(self, target: 'Unit', duration: float, source: str):
        """Apply stun to a target. Blocked by Quicksilver or Titan's Resolve (25 stacks)."""
        from .combat_engine import UnitState
        from .item_effects import get_item_data

        # Quicksilver CC immunity (18s from combat start)
        qs_until = get_item_data(target, 'Quicksilver', 'immune_until', 0)
        if qs_until and self.engine.time < qs_until:
            self.engine.log_event('cc_immune', target=target.name, source='Quicksilver')
            return

        # Titan's Resolve CC immunity (at 25 stacks)
        if get_item_data(target, 'TitansResolve', 'cc_immune', False):
            self.engine.log_event('cc_immune', target=target.name, source='TitansResolve')
            return

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
        # Patch 16.4: conversion 100% → 150%
        if combo_hit == 1 and unit.stats.omnivamp > 0:
            bonus_ad = unit.stats.omnivamp * 150  # Convert to AD bonus (150% per 16.4)
            unit.stats.ad += bonus_ad
            unit.is_targetable = False
            unit.untargetable_duration = 0.5
            self.engine.log_event('world_ender', unit=unit.name, bonus_ad=bonus_ad)

        unit.stats.mana = 0
        return True

    def _cast_atakhan(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                      ability_vars: Dict) -> bool:
        """Atakhan - Punish the Unworthy: Cleave + scaling Noxus effects.

        Atakhan is summoned by the Noxus trait. His abilities scale with
        Noxus breakpoints and star level:
          1-star: 30% omnivamp, cleave every 2 attacks (150% AP)
          2-star: + 3% damage amp to Noxians, cleave (225% AP)
          3-star: + DOT ability (750 AP over 2.5s in 3 hex radius)
          4-star: 100% omnivamp, cleave (500% AP), DOT over 30s,
                  after 10s BRING RUIN (handled in combat_engine)
        """
        from .combat_engine import DamageType

        noxus_count = getattr(unit, '_atakhan_noxus_count', 3)
        star = unit.star_level

        # Cleave damage (AP-scaled magic damage to enemies within 1 hex)
        cleave_dmg_map = {1: 150, 2: 225, 3: 340, 4: 500}
        cleave_damage = cleave_dmg_map.get(star, 150)

        # Scale by AP
        total_cleave = cleave_damage * (1 + unit.stats.ap / 100)

        # Hit enemies within 1 hex
        nearby_enemies = self._get_enemies_in_radius(unit.position, 1, enemies)
        for enemy in nearby_enemies:
            self._deal_damage(unit, enemy, total_cleave, DamageType.MAGIC, "atakhan_cleave")

        # At 5+ Noxus: grant stacking damage amp to Noxians
        if noxus_count >= 5:
            for ally in allies:
                if 'Noxus' in ally.traits and ally.is_alive:
                    ally.stats.damage_amp += 0.03  # 3% stacking damage amp

        # At 7+ Noxus: soul drain DOT (3-star+ ability)
        if noxus_count >= 7 and star >= 3:
            dot_damage = 750 * (1 + unit.stats.ap / 100)
            dot_duration = 30.0 if star >= 4 else 2.5
            # Split DOT damage between enemies in 3 hex radius
            dot_targets = self._get_enemies_in_radius(unit.position, 3, enemies)
            if dot_targets:
                per_target = dot_damage / len(dot_targets)
                for target in dot_targets:
                    self._deal_damage(unit, target, per_target,
                                     DamageType.MAGIC, "atakhan_soul_drain")

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
        # Patch 16.4: reset 100% → 80%
        unit.stats.mana = 0
        if not target.is_alive:
            # Refund after spending mana so Invoker scaling applies consistently.
            self.engine.gain_mana(unit, unit.stats.max_mana * 0.80, source="ambessa_kill_refund")
            self.engine.log_event('ambessa_reset', unit=unit.name)

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
        # Patch 16.4: bleed DPS 15/25/40→12/18/30, duration 4s→5s
        bleed_dps = self._get_var(ability_vars, 'PhysicalDamagePerSecond', unit.star_level, 12)
        execute_per_stack = self._get_var(ability_vars, 'ExecutePercentPerHemorrhage', unit.star_level, 0.08)
        bleed_duration = self._get_var(ability_vars, 'BleedDuration', unit.star_level, 5.0)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Track bleed stacks on target
        if not hasattr(target, '_darius_bleed'):
            target._darius_bleed = 0
        target._darius_bleed = min(5, target._darius_bleed + 1)

        # Apply bleed damage (total = dps * duration)
        bleed_total = bleed_dps * bleed_duration
        self.engine.apply_damage(unit, target, bleed_total, DamageType.TRUE, "darius_bleed")

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

    def _cast_diana(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                    ability_vars: Dict) -> bool:
        """Diana - Lunar Rush: Dash to target, deal damage, shield self. Leona synergy."""
        from .combat_engine import DamageType, HexGrid

        shield_amount = self._get_var(ability_vars, 'Shield', unit.star_level, 100)
        shield_duration = self._get_var(ability_vars, 'ShieldDuration', unit.star_level, 2.0)
        hex_limit = int(self._get_var(ability_vars, 'HexLimit', unit.star_level, 4))
        target_damage = self._get_var(ability_vars, 'TargetDamage', unit.star_level, 125)
        secondary_damage = self._get_var(ability_vars, 'SecondaryDamage', unit.star_level, 140)
        moonlight_dr = self._get_var(ability_vars, 'MoonlightDamageReduction', unit.star_level, 0.1)

        # Check for Leona synergy - if Leona is on team, Diana gets bonus damage reduction
        has_leona = any(a.api_name == 'TFT16_Leona' and a.is_alive for a in allies)
        if has_leona and not getattr(unit, '_diana_leona_dr_applied', False):
            unit._diana_leona_dr_applied = True
            unit.stats.damage_reduction += moonlight_dr
            self.engine.log_event('diana_leona_synergy', unit=unit.name, dr_bonus=moonlight_dr)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Check range limit
        distance = HexGrid.hex_distance(unit.position, target.position)
        if distance > hex_limit:
            # Find nearest enemy within range
            valid = [e for e in enemies if e.is_alive and e.is_targetable and
                    HexGrid.hex_distance(unit.position, e.position) <= hex_limit]
            if not valid:
                return False
            target = min(valid, key=lambda e: HexGrid.hex_distance(unit.position, e.position))

        # Dash to target
        self._dash_to_position(unit, target.position)

        # Apply shield
        unit.stats.shield += shield_amount + unit.stats.ap
        if not hasattr(unit, '_diana_shield_timer'):
            unit._diana_shield_timer = 0
        unit._diana_shield_timer = shield_duration
        self.engine.log_event('shield', unit=unit.name, amount=shield_amount + unit.stats.ap)

        # Deal damage to primary target
        self._deal_damage(unit, target, target_damage + unit.stats.ap, DamageType.MAGIC, "diana_lunar_rush")

        # Deal secondary damage to enemies around target (pull effect)
        nearby = self._get_enemies_in_radius(target.position, 2, enemies)
        for enemy in nearby:
            if enemy != target and enemy.is_alive:
                self._deal_damage(unit, enemy, secondary_damage + unit.stats.ap * 0.5,
                                 DamageType.MAGIC, "diana_moonfall")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Lunar Rush",
                             has_leona=has_leona, nearby_hit=len(nearby) - 1)
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

        target_damage = self._get_var(ability_vars, 'TargetDamage', unit.star_level, 315)  # 16.4: 275→315
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

    def _cast_leona(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                    ability_vars: Dict) -> bool:
        """Leona - Solar Flare: AOE stun + damage, passive flat DR. Diana synergy."""
        from .combat_engine import DamageType, UnitState

        flat_dr = self._get_var(ability_vars, 'FlatDR', unit.star_level, 15)
        num_enemies = int(self._get_var(ability_vars, 'NumEnemies', unit.star_level, 3))
        stun_duration = self._get_var(ability_vars, 'StunDuration', unit.star_level, 1.0)
        damage = self._get_var(ability_vars, 'Damage', unit.star_level, 80)
        ignite_duration = self._get_var(ability_vars, 'IgniteDuration', unit.star_level, 4.0)
        passive_timer = self._get_var(ability_vars, 'PassiveTimer', unit.star_level, 4.0)
        diana_ap = self._get_var(ability_vars, 'DianaAP', unit.star_level, 3)

        # Apply passive flat DR on first cast
        if not getattr(unit, '_leona_dr_applied', False):
            unit._leona_dr_applied = True
            unit._leona_flat_dr = flat_dr
            self.engine.log_event('leona_passive', unit=unit.name, flat_dr=flat_dr)

        # Check for Diana synergy - if Diana is on team, grant her bonus AP
        diana = next((a for a in allies if a.api_name == 'TFT16_Diana' and a.is_alive), None)
        if diana and not getattr(unit, '_leona_diana_ap_applied', False):
            unit._leona_diana_ap_applied = True
            diana.stats.ap += diana_ap
            self.engine.log_event('leona_diana_synergy', unit=unit.name, diana=diana.name, ap_bonus=diana_ap)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Solar Flare: AOE damage + stun centered on target
        targets_hit = self._get_enemies_in_radius(target.position, 2, enemies)[:num_enemies]

        for enemy in targets_hit:
            # Deal damage
            self._deal_damage(unit, enemy, damage + unit.stats.ap, DamageType.MAGIC, "leona_solar_flare")
            # Apply stun
            self._apply_stun(enemy, stun_duration, "leona_stun")
            # Apply ignite (burn damage, total = dps * duration)
            ignite_total = damage * 0.25 * ignite_duration
            self.engine.apply_damage(unit, enemy, ignite_total, DamageType.TRUE, "leona_ignite")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Solar Flare",
                             targets=len(targets_hit), has_diana=diana is not None)
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
            self.engine.set_unit_position(unit, best_hex)
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
        if target and target.is_alive:
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
        """Annie - Enraged Inferno: Board-wide AOE magic damage.

        First cast: Deals massive AOE damage to all enemies.
        Subsequent casts: Reduced mana cost (140 -> 20), deals single target damage.

        Note: Tibbers is a SEPARATE unit (TFT16_AnnieTibbers) that the player fields
        independently via the Dark Child trait. He has his own attacks and ability.
        """
        from .combat_engine import DamageType

        aoe_damage = self._get_var(ability_vars, 'Damage', unit.star_level, 1500)
        single_target_damage = self._get_var(ability_vars, 'SingleTargetDamage', unit.star_level, 240)
        mana_reduction = self._get_var(ability_vars, 'ManaCostReduction', unit.star_level, 140)

        # Track if this is first cast (for mana cost reduction)
        if not hasattr(unit, '_annie_first_cast_done'):
            unit._annie_first_cast_done = False

        if not unit._annie_first_cast_done:
            # First cast: Board-wide AOE damage
            unit._annie_first_cast_done = True
            total_damage = 0
            for enemy in enemies:
                if enemy.is_alive and enemy.is_targetable:
                    damage = aoe_damage + unit.stats.ap
                    self._deal_damage(unit, enemy, damage, DamageType.MAGIC, "annie_enraged_inferno")
                    total_damage += damage

            # Combat uses max_mana as cast threshold, so reduce that for later casts.
            unit.stats.max_mana = max(20, unit.stats.max_mana - mana_reduction)
            self.engine.log_event('ability_cast', unit=unit.name, ability="Enraged Inferno",
                                 damage=total_damage, first_cast=True,
                                 new_mana_cost=unit.stats.max_mana)
        else:
            # Subsequent casts: Single target damage (Annie continues attacking)
            target = unit.target or self._find_nearest_enemy(unit, enemies)
            if target:
                damage = single_target_damage + unit.stats.ap
                self._deal_damage(unit, target, damage, DamageType.MAGIC, "annie_inferno_blast")
                self.engine.log_event('ability_cast', unit=unit.name, ability="Enraged Inferno",
                                     damage=damage, target=target.name)

        unit.stats.mana = 0
        return True

    def _cast_annietibbers(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                           ability_vars: Dict) -> bool:
        """Tibbers - Rage of Embers: Self-buff with shield, attack speed, and healing.

        Tibbers AUTOMATICALLY APPEARS on bench when you buy Annie (Dark Child trait).
        Cannot sell separately - selling Annie removes Tibbers.
        Can equip items and field independently. Has own mana pool and attacks.
        """
        shield_amount = self._get_var(ability_vars, 'Shield', unit.star_level, 1000)
        attack_speed_buff = self._get_var(ability_vars, 'AttackSpeed', unit.star_level, 2.0)
        heal_percent = self._get_var(ability_vars, 'HealPercentHealth', unit.star_level, 0.025)
        duration = self._get_var(ability_vars, 'Duration', unit.star_level, 4.0)

        # Apply shield
        self.engine.apply_shield(unit, shield_amount + unit.stats.ap * 0.5, "tibbers_rage_shield")

        # Apply attack speed buff
        if not hasattr(unit, '_tibbers_as_buff_active'):
            unit._tibbers_as_buff_active = False

        if not unit._tibbers_as_buff_active:
            unit._tibbers_as_buff_active = True
            unit._tibbers_original_as = unit.stats.attack_speed
            unit.stats.attack_speed += attack_speed_buff
            self.engine.log_event('tibbers_rage_buff', unit=unit.name,
                                 as_buff=attack_speed_buff, duration=duration)

        # Heal based on max HP
        heal_amount = unit.stats.max_hp * heal_percent
        self.engine.heal_unit(unit, heal_amount, "tibbers_rage_heal")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Rage of Embers",
                             shield=shield_amount, heal=heal_amount, as_buff=attack_speed_buff)
        return True

    def _cast_bard(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                   ability_vars: Dict) -> bool:
        """Bard - Traveler's Call: Meeps attack multiple enemies."""
        from .combat_engine import DamageType, HexGrid

        damage = self._get_var(ability_vars, 'Damage', unit.star_level, 130)  # 16.4: 120→130
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
        """Miss Fortune - Heartbreaker: Multi-wave AOE + ricochet autos passive."""
        from .combat_engine import DamageType

        ricochet_mult = self._get_var(ability_vars, 'AutoRicochetMutliplier', unit.star_level, 0.5)
        base_waves = int(self._get_var(ability_vars, 'BaseNumWaves', unit.star_level, 2))
        casts_per_wave = int(self._get_var(ability_vars, 'NumCaststoGainExtraWave', unit.star_level, 3))
        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 145)
        ap_damage = self._get_var(ability_vars, 'APDamage', unit.star_level, 15)
        secondary_pct = self._get_var(ability_vars, 'PercentDamageOfSecondaryWaves', unit.star_level, 0.5)

        # Track casts for extra waves
        if not hasattr(unit, '_mf_casts'):
            unit._mf_casts = 0
        unit._mf_casts += 1

        extra_waves = unit._mf_casts // casts_per_wave
        total_waves = base_waves + extra_waves

        # Enable ricochet passive
        if not getattr(unit, '_mf_ricochet_enabled', False):
            unit._mf_ricochet_enabled = True
            unit._mf_ricochet_mult = ricochet_mult
            self.engine.log_event('mf_ricochet_passive', unit=unit.name, mult=ricochet_mult)

        # Fire waves in a cone
        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Get direction to target for cone
        targets_hit = set()
        total_damage = ad_damage + unit.stats.ad + ap_damage + unit.stats.ap

        for wave in range(total_waves):
            wave_damage = total_damage if wave == 0 else total_damage * secondary_pct
            # First wave hits primary target hard, subsequent waves spread
            for enemy in enemies:
                if not enemy.is_alive or not enemy.is_targetable:
                    continue

                # Simplified cone: enemies in front of MF toward target direction
                dist_to_target = self._hex_distance(unit.position, enemy.position)
                if dist_to_target <= 4:  # Range limit
                    self._deal_damage(unit, enemy, wave_damage,
                                     DamageType.PHYSICAL, f"mf_wave_{wave+1}")
                    targets_hit.add(enemy.name)

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Heartbreaker",
                             waves=total_waves, targets=len(targets_hit), casts=unit._mf_casts)
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

    # Note: Taric's main implementation is in the TARIC section below (line ~3200)
    # with check_taric_invulnerability() for HP threshold checking

    def _cast_thresh(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                     ability_vars: Dict) -> bool:
        """Thresh - The Box: Hook enemies, drain health based on team's Shadow Isles souls."""
        from .combat_engine import DamageType

        # Get soul count from centralized TraitManager
        soul_count = self.engine.trait_manager.get_shadow_isles_souls(unit.team)

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
        """Warwick - Eternal Hunger: Single cast, self buff + ally AS buff."""
        from .combat_engine import DamageType

        # Track if already cast (single cast only)
        if hasattr(unit, '_warwick_cast'):
            return False

        unit._warwick_cast = True

        attack_speed = self._get_var(ability_vars, 'AttackSpeed', unit.star_level, 1.0)
        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 45)
        omnivamp = self._get_var(ability_vars, 'Omnivamp', unit.star_level, 0.15)
        ally_as = self._get_var(ability_vars, 'AllyAttackSpeed', unit.star_level, 0.2)
        ally_duration = self._get_var(ability_vars, 'AllyBuffDuration', unit.star_level, 3)

        # Buff self - permanent for combat
        unit.stats.attack_speed += attack_speed
        unit.stats.omnivamp += omnivamp
        unit.stats.ad += ad_damage  # Bonus AD on attacks

        # Track ally buff for duration
        unit._warwick_ally_buff_duration = ally_duration
        unit._warwick_buffed_allies = []

        # Buff allies
        for ally in allies:
            if ally.is_alive and ally != unit:
                ally.stats.attack_speed += ally_as
                unit._warwick_buffed_allies.append((ally, ally_as))

        self.engine.log_event('warwick_eternal_hunger', unit=unit.name,
                             self_as=attack_speed, self_ad=ad_damage, self_omnivamp=omnivamp,
                             ally_as_buff=ally_as, ally_count=len(unit._warwick_buffed_allies))

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

        unit.stats.mana = 0
        # Mana on kill (refund after spending mana)
        if not target.is_alive:
            self.engine.gain_mana(unit, mana_on_kill, source="zilean_kill_refund")
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

            # Dragonborn aura: all allies take 10% less ability damage
            # This persists even after Shyvana dies (never removed)
            for ally in allies:
                if ally.is_alive and ally.team == unit.team:
                    ally._dragonborn_protected = True
            unit._dragonborn_protected = True  # Shyvana herself too

            # Divebomb damage to target
            target = unit.target or self._find_nearest_enemy(unit, enemies)
            if target:
                self._dash_to_position(unit, target.position)
                self._deal_damage(unit, target, divebomb_damage + unit.stats.ad,
                                 DamageType.PHYSICAL, "shyvana_divebomb")

            self.engine.log_event('shyvana_transform', unit=unit.name, aura_allies=len(allies))
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
            soul_count = self.engine.trait_manager.get_shadow_isles_souls(unit.team)
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
        # Patch 16.4: primary 45/68/105→50/75/120, secondary 20/30/50→25/35/60
        damage = self._get_var(ability_vars, 'Damage', unit.star_level, 50)
        secondary_damage = self._get_var(ability_vars, 'SecondaryMagicDamage', unit.star_level, 25)

        # Get soul count for bonus snips
        soul_count = self.engine.trait_manager.get_shadow_isles_souls(unit.team)
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
        if not target:
            unit.stats.mana = 0
            return True
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
        soul_count = self.engine.trait_manager.get_shadow_isles_souls(unit.team)
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
        soul_count = self.engine.trait_manager.get_shadow_isles_souls(unit.team)
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

    def _cast_yorick(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                     ability_vars: Dict) -> bool:
        """Yorick - Mourning Mist: Mark enemy + deal % HP damage with soul-scaling heal."""
        from .combat_engine import DamageType

        # Get ability variables
        flat_damage = self._get_var(ability_vars, 'FlatDamage', unit.star_level, 80)
        pct_hp_damage = self._get_var(ability_vars, 'PercentHealthDamage', unit.star_level, 0.05)
        ap_heal = self._get_var(ability_vars, 'APHeal', unit.star_level, 325)
        heal_per_soul_breakpoint = self._get_var(ability_vars, 'HealPerSoulBreakpoint', unit.star_level, 7)
        soul_breakpoint = self._get_var(ability_vars, 'SoulBreakpoint', unit.star_level, 10)
        debuff_duration = self._get_var(ability_vars, 'DebuffDuration', unit.star_level, 4.0)

        # Get soul count for bonus healing
        soul_count = self.engine.trait_manager.get_shadow_isles_souls(unit.team)
        bonus_heal = int(soul_count / soul_breakpoint) * heal_per_soul_breakpoint

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Deal damage: flat + % max HP
        max_hp_damage = target.stats.max_hp * pct_hp_damage
        total_damage = flat_damage + max_hp_damage + unit.stats.ap
        self._deal_damage(unit, target, total_damage, DamageType.MAGIC, "yorick_mourning_mist")

        # Mark the target (debuff - increases damage taken from Yorick's ghouls/allies)
        if not hasattr(target, '_yorick_mark'):
            target._yorick_mark = 0
        target._yorick_mark = debuff_duration
        self.engine.log_event('debuff', unit=unit.name, target=target.name,
                             debuff="mourning_mist_mark", duration=debuff_duration)

        # Heal Yorick based on AP + soul scaling
        total_heal = ap_heal + bonus_heal
        self.engine.heal_unit(unit, total_heal, "yorick_heal")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Mourning Mist",
                             damage=total_damage, heal=total_heal, souls=soul_count)
        return True

    def _cast_ziggs(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                    ability_vars: Dict) -> bool:
        """Ziggs - Mega Inferno Bomb: Large AOE with distance-based damage falloff."""
        from .combat_engine import DamageType, HexGrid

        # Auto attack bounce passive
        bounce_count = int(self._get_var(ability_vars, 'BABounceNumber', unit.star_level, 1))
        ba_ad_pct = self._get_var(ability_vars, 'BAPercentAD', unit.star_level, 1.0)
        ba_ap_pct = self._get_var(ability_vars, 'BAPercentAP', unit.star_level, 40) / 100

        # Bomb variables
        aoe_range = int(self._get_var(ability_vars, 'BombAOERange', unit.star_level, 4))
        min_damage = self._get_var(ability_vars, 'MinAOEDamage', unit.star_level, 70)
        max_damage = self._get_var(ability_vars, 'MaxAOEDamage', unit.star_level, 550)

        # Enable auto attack bounce passive on first cast
        if not getattr(unit, '_ziggs_bounce_enabled', False):
            unit._ziggs_bounce_enabled = True
            unit._ziggs_bounce_count = bounce_count
            unit._ziggs_ba_damage = unit.stats.ad * ba_ad_pct + unit.stats.ap * ba_ap_pct
            self.engine.log_event('ziggs_bounce_passive', unit=unit.name, bounces=bounce_count)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Throw bomb at target position
        bomb_center = target.position
        enemies_in_range = self._get_enemies_in_radius(bomb_center, aoe_range, enemies)

        for enemy in enemies_in_range:
            # Calculate distance-based damage (closer = more damage)
            distance = HexGrid.hex_distance(bomb_center, enemy.position)
            if distance == 0:
                damage = max_damage
            else:
                # Linear interpolation from max (center) to min (edge)
                damage_ratio = 1 - (distance / aoe_range)
                damage = min_damage + (max_damage - min_damage) * damage_ratio

            total_damage = damage + unit.stats.ap
            self._deal_damage(unit, enemy, total_damage, DamageType.MAGIC, "ziggs_bomb")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Mega Inferno Bomb",
                             center=bomb_center, enemies_hit=len(enemies_in_range))
        return True

    # =========================================================================
    # TAHM KENCH - Glutton Feeding System
    # =========================================================================

    # Glutton stat tables from game data
    # Stat type depends on champion ROLE:
    # - Health: Attack Tank, Magic Tank
    # - Attack Speed (%): Attack Assassin, Attack Caster, Attack Fighter, Attack Marksman, Attack Specialist
    # - Ability Power (%): Hybrid Fighter, Magic Assassin, Magic Caster, Magic Fighter, Magic Marksman, Magic Specialist

    GLUTTON_HP_TABLE = {
        # cost: {star: value}
        1: {1: 55, 2: 125, 3: 330},
        2: {1: 85, 2: 190, 3: 530},
        3: {1: 115, 2: 295, 3: 815},
        4: {1: 140, 2: 325, 3: 9810},
        5: {1: 170, 2: 505, 3: 70915},
        7: {1: 200, 2: 600, 3: 99999},
    }

    GLUTTON_AS_TABLE = {
        # cost: {star: % value}
        1: {1: 16, 2: 36, 3: 80},
        2: {1: 22, 2: 52, 3: 115},
        3: {1: 28, 2: 63, 3: 216},
        4: {1: 34, 2: 75, 3: 4444},
        5: {1: 40, 2: 102, 3: 55555},
        7: {1: 50, 2: 127, 3: 69444},
    }

    GLUTTON_AP_TABLE = {
        # cost: {star: % value}
        1: {1: 10, 2: 24, 3: 62},
        2: {1: 12, 2: 32, 3: 92},
        3: {1: 14, 2: 40, 3: 144},
        4: {1: 16, 2: 58, 3: 4444},
        5: {1: 18, 2: 84, 3: 55555},
        7: {1: 23, 2: 105, 3: 69444},
    }

    # Roles that grant each stat type
    GLUTTON_HP_ROLES = ['ADTank', 'APTank', 'Attack Tank', 'Magic Tank']
    GLUTTON_AS_ROLES = ['ADAssassin', 'ADCaster', 'ADFighter', 'ADCarry', 'ADSpecialist',
                        'Attack Assassin', 'Attack Caster', 'Attack Fighter', 'Attack Marksman', 'Attack Specialist']
    GLUTTON_AP_ROLES = ['HFighter', 'APAssassin', 'APCaster', 'APFighter', 'APCarry', 'APSpecialist',
                        'Hybrid Fighter', 'Magic Assassin', 'Magic Caster', 'Magic Fighter', 'Magic Marksman', 'Magic Specialist']

    def _cast_tahmkench(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                        ability_vars: Dict) -> bool:
        """Tahm Kench - Devour: Swallow enemy, deal damage over time.

        Glutton trait: Feed champions to Tahm Kench for permanent stats.
        Stat gained depends on fed unit's ROLE:
        - Tank roles -> Health
        - AD roles -> Attack Speed %
        - AP roles -> Ability Power %
        """
        from .combat_engine import DamageType, UnitState

        # Get ability variables
        damage = self._get_var(ability_vars, 'Damage', unit.star_level, 1800)
        stun_duration = self._get_var(ability_vars, 'StunDuration', unit.star_level, 0.5)
        belly_duration = self._get_var(ability_vars, 'BellyDuration', unit.star_level, 2.5)
        damage_reduction = self._get_var(ability_vars, 'DamageReduction', unit.star_level, 0.30)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Check if target can be devoured (not too large/tanky for non-3-star)
        can_devour = unit.star_level >= 3 or target.stats.hp <= damage

        if can_devour:
            # Swallow the target (make them untargetable)
            target.is_targetable = False
            target.untargetable_duration = belly_duration
            target.state = UnitState.UNTARGETABLE

            # Tahm Kench gains damage reduction while digesting
            unit.stats.damage_reduction += damage_reduction
            if not hasattr(unit, '_tahm_digesting'):
                unit._tahm_digesting = True

            # Deal damage over the belly duration (simplified to instant)
            self._deal_damage(unit, target, damage + unit.stats.ap,
                             DamageType.MAGIC, "tahm_devour")

            self.engine.log_event('tahm_devour', unit=unit.name, target=target.name,
                                 duration=belly_duration, damage=damage)

            # If target dies while devoured, gain Glutton stats
            if not target.is_alive:
                self._apply_glutton_stats(unit, target)
        else:
            # Can't fully devour - just damage and stun
            self._deal_damage(unit, target, damage * 0.5 + unit.stats.ap,
                             DamageType.MAGIC, "tahm_lick")
            self._apply_stun(target, stun_duration, "tahm_stun")

        unit.stats.mana = 0
        return True

    def _get_glutton_stat_type(self, role: str) -> str:
        """Determine which stat Tahm Kench gains from eating a unit based on role."""
        if any(r in role for r in ['Tank']):
            return 'hp'
        elif any(r in role for r in ['AD', 'Attack', 'Marksman']):
            return 'as'
        elif any(r in role for r in ['AP', 'Magic', 'Hybrid', 'Caster']):
            return 'ap'
        # Default to HP for unknown roles
        return 'hp'

    def _apply_glutton_stats(self, tahm: 'Unit', eaten_unit: 'Unit'):
        """Apply permanent stats from eating a unit (Glutton trait)."""
        eaten_data = self.engine.champions.get(eaten_unit.api_name, {})
        cost = eaten_data.get('cost', 1)
        star = eaten_unit.star_level
        role = eaten_data.get('role', '')

        # Determine stat type from role
        stat_type = self._get_glutton_stat_type(role)

        # Get value from appropriate table
        if stat_type == 'hp':
            table = self.GLUTTON_HP_TABLE
            value = table.get(cost, table[1]).get(star, table[1][1])
            stat_name = 'hp'
        elif stat_type == 'as':
            table = self.GLUTTON_AS_TABLE
            value = table.get(cost, table[1]).get(star, table[1][1])
            stat_name = 'attack_speed'
            value = value / 100  # Convert percentage to decimal
        else:  # ap
            table = self.GLUTTON_AP_TABLE
            value = table.get(cost, table[1]).get(star, table[1][1])
            stat_name = 'ap'

        # Track stats gained
        if not hasattr(tahm, '_glutton_stats'):
            tahm._glutton_stats = {'hp': 0, 'attack_speed': 0, 'ap': 0, 'units_eaten': 0}

        tahm._glutton_stats[stat_name] += value
        tahm._glutton_stats['units_eaten'] += 1

        # Apply stats
        if stat_name == 'hp':
            tahm.stats.max_hp += value
            tahm.stats.hp += value
        elif stat_name == 'attack_speed':
            # Cap at 5.0 total AS, convert excess to AP
            current_as = tahm.stats.attack_speed
            if current_as + value > 5.0:
                as_to_add = max(0, 5.0 - current_as)
                excess_as = value - as_to_add
                tahm.stats.attack_speed += as_to_add
                # Convert excess AS to AP (1% AS = 1 AP)
                tahm.stats.ap += excess_as * 100
                tahm._glutton_stats['ap'] += excess_as * 100
            else:
                tahm.stats.attack_speed += value
        else:  # ap
            tahm.stats.ap += value

        self.engine.log_event('glutton_stats', unit=tahm.name, eaten=eaten_unit.name,
                             cost=cost, star=star, role=role, stat_type=stat_type,
                             value=value if stat_name != 'attack_speed' else value * 100)

    def apply_glutton_feeding(self, tahm: 'Unit', fed_units: List[Dict]):
        """Pre-combat: Apply stats from units fed to Tahm Kench.

        Args:
            tahm: Tahm Kench unit
            fed_units: List of dicts with 'cost', 'star', and 'role' keys
        """
        for fed in fed_units:
            cost = fed.get('cost', 1)
            star = fed.get('star', 1)
            role = fed.get('role', '')

            stat_type = self._get_glutton_stat_type(role)

            if stat_type == 'hp':
                table = self.GLUTTON_HP_TABLE
                value = table.get(cost, table[1]).get(star, table[1][1])
                stat_name = 'hp'
            elif stat_type == 'as':
                table = self.GLUTTON_AS_TABLE
                value = table.get(cost, table[1]).get(star, table[1][1])
                stat_name = 'attack_speed'
                value = value / 100
            else:
                table = self.GLUTTON_AP_TABLE
                value = table.get(cost, table[1]).get(star, table[1][1])
                stat_name = 'ap'

            if not hasattr(tahm, '_glutton_stats'):
                tahm._glutton_stats = {'hp': 0, 'attack_speed': 0, 'ap': 0, 'units_eaten': 0}

            tahm._glutton_stats[stat_name] += value
            tahm._glutton_stats['units_eaten'] += 1

            if stat_name == 'hp':
                tahm.stats.max_hp += value
                tahm.stats.hp += value
            elif stat_name == 'attack_speed':
                current_as = tahm.stats.attack_speed
                if current_as + value > 5.0:
                    as_to_add = max(0, 5.0 - current_as)
                    excess_as = value - as_to_add
                    tahm.stats.attack_speed += as_to_add
                    tahm.stats.ap += excess_as * 100
                    tahm._glutton_stats['ap'] += excess_as * 100
                else:
                    tahm.stats.attack_speed += value
            else:
                tahm.stats.ap += value

    # =========================================================================
    # GALIO - Bench Mechanic & Demacia Rally
    # =========================================================================

    def _cast_galio(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                    ability_vars: Dict) -> bool:
        """Galio - Inspirational Might: Shield allies and deal MR-scaled damage.

        Heroic trait: Galio starts on bench, joins fight on first Demacia rally.
        """
        from .combat_engine import DamageType

        num_attacks = int(self._get_var(ability_vars, 'NumAttacks', unit.star_level, 3))
        passive_mr_ratio = self._get_var(ability_vars, 'PassiveMRRatio', unit.star_level, 5.7)
        shield_amount = self._get_var(ability_vars, 'Shield', unit.star_level, 600)
        active_mr_damage = self._get_var(ability_vars, 'ActiveMRDamage', unit.star_level, 5.25)
        active_ar_damage = self._get_var(ability_vars, 'ActiveARDamage', unit.star_level, 5.25)

        # Shield all allies
        for ally in allies:
            if ally.is_alive:
                self.engine.apply_shield(ally, shield_amount + unit.stats.ap * 0.3,
                                        "galio_shield")

        # Deal damage based on Galio's MR and Armor
        mr_damage = unit.stats.magic_resist * active_mr_damage
        ar_damage = unit.stats.armor * active_ar_damage
        total_damage = mr_damage + ar_damage + unit.stats.ap

        # Slam damage to nearby enemies
        nearby = self._get_enemies_in_radius(unit.position, 2, enemies)
        for enemy in nearby:
            self._deal_damage(unit, enemy, total_damage, DamageType.MAGIC, "galio_slam")

        # Enhanced attacks
        unit.enhanced_attacks_remaining = num_attacks
        unit.enhanced_attack_on_hit_dmg = unit.stats.magic_resist * passive_mr_ratio

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Inspirational Might",
                             shield=shield_amount, damage=total_damage)
        return True

    def trigger_demacia_rally(self, team: List['Unit'], bench_galio: 'Unit' = None):
        """Trigger Demacia rally - Galio joins from bench."""
        if not bench_galio:
            return None

        enemies = [u for u in self.engine.units if u.team != bench_galio.team and u.is_alive]
        if not enemies:
            return None

        # Find best slam position
        from .combat_engine import HexGrid
        best_pos = None
        best_count = 0

        for row in range(HexGrid.ROWS):
            for col in range(HexGrid.COLS):
                pos = (row, col)
                if pos in self.engine.get_occupied_hexes():
                    continue

                count = sum(1 for e in enemies if HexGrid.hex_distance(pos, e.position) <= 2)
                if count > best_count:
                    best_count = count
                    best_pos = pos

        if best_pos:
            from .combat_engine import UnitState, DamageType
            bench_galio.position = best_pos
            bench_galio.is_alive = True
            bench_galio.state = UnitState.IDLE

            self.engine.units.append(bench_galio)

            # Entry slam damage
            entry_damage = bench_galio.stats.magic_resist * 3 + bench_galio.stats.ap
            nearby = [e for e in enemies if HexGrid.hex_distance(best_pos, e.position) <= 2]
            for enemy in nearby:
                self._deal_damage(bench_galio, enemy, entry_damage,
                                 DamageType.MAGIC, "galio_entry_slam")
                self._apply_stun(enemy, 1.5, "galio_entry_stun")

            self.engine.log_event('galio_rally', unit=bench_galio.name,
                                 position=best_pos, enemies_hit=len(nearby))

        return bench_galio

    # =========================================================================
    # T-HEX - HexMech Pilot System
    # =========================================================================

    # HexMech pilot bonus stats by role and star level
    # Tank: Omnivamp, Fighter: AD%, Marksman: Damage Amp, Caster: Mana Regen, Assassin: Crit Chance
    HEXMECH_PILOT_BONUSES = {
        'Tank': {'stat': 'omnivamp', 'values': {1: 0.15, 2: 0.25, 3: 0.40}},
        'Fighter': {'stat': 'ad_percent', 'values': {1: 0.15, 2: 0.25, 3: 0.40}},
        'Marksman': {'stat': 'damage_amp', 'values': {1: 0.10, 2: 0.18, 3: 0.30}},
        'Caster': {'stat': 'mana_regen', 'values': {1: 2, 2: 4, 3: 5}},
        'Assassin': {'stat': 'crit_chance', 'values': {1: 0.30, 2: 0.60, 3: 1.00}},
    }

    def _cast_thex(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                   ability_vars: Dict) -> bool:
        """T-Hex - Hextech Arsenal: Gatling gun + shield.

        HexMech trait: Pilot jumps in at combat start, grants 80% HP + role bonus.
        """
        from .combat_engine import DamageType

        num_bullets = int(self._get_var(ability_vars, 'NumBullets', unit.star_level, 4))
        base_shield = self._get_var(ability_vars, 'BaseShield', unit.star_level, 400)
        pct_hp_shield = self._get_var(ability_vars, 'PercentHealthShield', unit.star_level, 0.10)
        ap_damage = self._get_var(ability_vars, 'APDamage', unit.star_level, 15)
        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 100)

        # Apply shield
        shield = base_shield + (unit.stats.max_hp * pct_hp_shield) + unit.stats.ap * 0.5
        self.engine.apply_shield(unit, shield, "thex_shield")

        # Fire bullets at random enemies
        targets = [e for e in enemies if e.is_alive and e.is_targetable]
        for i in range(num_bullets):
            if not targets:
                break
            target = random.choice(targets)
            damage = ad_damage + unit.stats.ad + ap_damage + unit.stats.ap
            self._deal_damage(unit, target, damage, DamageType.PHYSICAL, f"thex_bullet_{i+1}")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Hextech Arsenal",
                             bullets=num_bullets, shield=shield)
        return True

    def _get_pilot_role_category(self, role: str) -> str:
        """Determine HexMech bonus category from pilot's role."""
        role_lower = role.lower()
        if 'tank' in role_lower:
            return 'Tank'
        elif 'fighter' in role_lower:
            return 'Fighter'
        elif 'carry' in role_lower or 'marksman' in role_lower:
            return 'Marksman'
        elif 'caster' in role_lower or 'mage' in role_lower or 'invoker' in role_lower:
            return 'Caster'
        elif 'assassin' in role_lower:
            return 'Assassin'
        # Default to Fighter for unknown roles
        return 'Fighter'

    def assign_thex_pilot(self, thex: 'Unit', pilot: 'Unit'):
        """Assign a pilot to T-Hex (HexMech trait).

        Combat Start: Pilot jumps into T-Hex, granting:
        - 80% of pilot's Health
        - Bonus stats based on pilot's role and star level:
          - Tank: +15/25/40% Omnivamp
          - Fighter: +15/25/40% Attack Damage
          - Marksman: +10/18/30% Damage Amp
          - Caster: +2/4/5 Mana Regen
          - Assassin: +30/60/100% Crit Chance

        On T-Hex death: Pilot ejects, knockback + 1.5s stun to nearby enemies.
        """
        pilot_data = self.engine.champions.get(pilot.api_name, {})
        role = pilot_data.get('role', 'Fighter')
        pilot_star = pilot.star_level if hasattr(pilot, 'star_level') else 1

        # Store pilot reference
        thex._pilot = pilot
        thex._pilot_role = role

        # Grant 80% of pilot's HP
        pilot_hp = pilot.stats.max_hp if hasattr(pilot, 'stats') else 500
        hp_bonus = pilot_hp * 0.80
        thex.stats.max_hp += hp_bonus
        thex.stats.hp += hp_bonus

        # Determine role category and apply bonus
        role_category = self._get_pilot_role_category(role)
        bonus_info = self.HEXMECH_PILOT_BONUSES.get(role_category, self.HEXMECH_PILOT_BONUSES['Fighter'])
        stat_type = bonus_info['stat']
        bonus_value = bonus_info['values'].get(pilot_star, bonus_info['values'][1])

        # Apply the stat bonus
        if stat_type == 'omnivamp':
            thex.stats.omnivamp += bonus_value
        elif stat_type == 'ad_percent':
            ad_bonus = thex.base_stats.ad * bonus_value
            thex.stats.ad += ad_bonus
        elif stat_type == 'damage_amp':
            thex.stats.damage_amp += bonus_value
        elif stat_type == 'mana_regen':
            # Mana regen per second - store for tick processing
            if not hasattr(thex, '_mana_regen_bonus'):
                thex._mana_regen_bonus = 0
            thex._mana_regen_bonus += bonus_value
        elif stat_type == 'crit_chance':
            thex.stats.crit_chance += bonus_value

        # Track the bonus for logging
        thex._hexmech_bonus = {'stat': stat_type, 'value': bonus_value, 'role': role_category}

        self.engine.log_event('hexmech_pilot', thex=thex.name, pilot=pilot.name,
                             role=role_category, star=pilot_star,
                             hp_bonus=hp_bonus, stat_bonus=f"{stat_type}: {bonus_value}")

    def trigger_thex_death(self, thex: 'Unit', enemies: List['Unit']):
        """Handle T-Hex death - pilot ejects, knockback + stun nearby enemies.

        On death: Pilot ejects while T-Hex knocks back and Stuns
        nearby enemies for 1.5 seconds.
        """
        from .combat_engine import HexGrid

        # Knockback and stun nearby enemies
        nearby = [e for e in enemies if e.is_alive and e.is_targetable and
                  HexGrid.hex_distance(thex.position, e.position) <= 2]

        for enemy in nearby:
            # Stun for 1.5 seconds
            self._apply_stun(enemy, 1.5, "thex_death_stun")

            # Knockback - push 1 hex away from T-Hex
            dx = enemy.position[0] - thex.position[0]
            dy = enemy.position[1] - thex.position[1]

            # Normalize and push
            if dx != 0 or dy != 0:
                new_row = enemy.position[0] + (1 if dx > 0 else -1 if dx < 0 else 0)
                new_col = enemy.position[1] + (1 if dy > 0 else -1 if dy < 0 else 0)

                # Clamp to board bounds
                new_row = max(0, min(HexGrid.ROWS - 1, new_row))
                new_col = max(0, min(HexGrid.COLS - 1, new_col))

                new_pos = (new_row, new_col)
                if new_pos not in self.engine.get_occupied_hexes():
                    enemy.position = new_pos

        # Eject pilot (if exists) - pilot survives but T-Hex is destroyed
        pilot = getattr(thex, '_pilot', None)
        if pilot:
            self.engine.log_event('hexmech_eject', pilot=pilot.name,
                                 enemies_stunned=len(nearby))

        return pilot

    # =========================================================================
    # BARON NASHOR - Riftscourge
    # =========================================================================

    def _cast_baronnashor(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                          ability_vars: Dict) -> bool:
        """Baron Nashor - Wrath of the Void: Acid shots + Void Rift.

        Riftscourge: +2 Void trait, 30% damage amp after 8s.
        """
        from .combat_engine import DamageType

        ap_damage = self._get_var(ability_vars, 'APDamage', unit.star_level, 45)
        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 375)
        acid_pct = self._get_var(ability_vars, 'AcidPercentDamage', unit.star_level, 0.45)
        num_acid = int(self._get_var(ability_vars, 'NumAcidToShoot', unit.star_level, 10))
        knockup_duration = self._get_var(ability_vars, 'KnockupDuration', unit.star_level, 1.5)

        # Track Void Rift timer
        if not hasattr(unit, '_void_rift_active'):
            unit._void_rift_active = False
            unit._void_rift_timer = 8.0

        # Check if Void Rift should activate
        if not unit._void_rift_active and self.engine.time >= unit._void_rift_timer:
            self._activate_void_rift(unit, allies)

        # Primary slam
        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if target:
            main_damage = ad_damage + unit.stats.ad + ap_damage + unit.stats.ap
            self._deal_damage(unit, target, main_damage, DamageType.PHYSICAL, "baron_slam")
            self._apply_stun(target, knockup_duration, "baron_knockup")

        # Acid shots
        targets = [e for e in enemies if e.is_alive and e.is_targetable]
        for i in range(num_acid):
            if not targets:
                break
            acid_target = random.choice(targets)
            acid_damage = acid_target.stats.max_hp * acid_pct
            self._deal_damage(unit, acid_target, acid_damage + unit.stats.ap * 0.2,
                             DamageType.MAGIC, f"baron_acid_{i+1}")

        # Void Rift tick
        if unit._void_rift_active:
            self._void_rift_tick(unit, enemies)

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Wrath of the Void",
                             acid_shots=num_acid, rift_active=unit._void_rift_active)
        return True

    def _activate_void_rift(self, baron: 'Unit', allies: List['Unit']):
        """Activate Void Rift - 30% damage amp for Void units."""
        baron._void_rift_active = True
        void_amp = 0.30

        for ally in allies:
            if 'Void' in ally.traits:
                ally.stats.damage_amp += void_amp
                ally._void_rift_amp = True

        if 'Void' in baron.traits:
            baron.stats.damage_amp += void_amp

        self.engine.log_event('void_rift_active', baron=baron.name, damage_amp=void_amp)

    def _void_rift_tick(self, baron: 'Unit', enemies: List['Unit']):
        """Apply Void Rift plasma bolt damage (5% max HP)."""
        from .combat_engine import DamageType

        for enemy in enemies:
            if enemy.is_alive and enemy.is_targetable:
                plasma_damage = enemy.stats.max_hp * 0.05
                self.engine.apply_damage(baron, enemy, plasma_damage,
                                        DamageType.MAGIC, "void_rift_plasma")

    def setup_baron_riftscourge(self, baron: 'Unit', team: List['Unit']):
        """Set up Baron's Riftscourge trait at combat start."""
        baron._void_rift_active = False
        baron._void_rift_timer = self.engine.time + 8.0

        if not hasattr(self.engine.trait_manager, 'riftscourge_void_bonus'):
            self.engine.trait_manager.riftscourge_void_bonus = 0
        self.engine.trait_manager.riftscourge_void_bonus = 2

        self.engine.log_event('riftscourge_setup', baron=baron.name,
                             void_bonus=2, rift_timer=8.0)

    # =========================================================================
    # RIFT HERALD - Durability Passive
    # =========================================================================

    def _cast_riftherald(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                         ability_vars: Dict) -> bool:
        """Rift Herald - Warp Armor: Gain durability based on nearby enemies."""
        from .combat_engine import DamageType

        ap_damage = self._get_var(ability_vars, 'APDamage', unit.star_level, 150)
        bonus_durability = self._get_var(ability_vars, 'BonusDurability', unit.star_level, 0.25)
        durability_per_enemy = self._get_var(ability_vars, 'DurabilityPerEnemy', unit.star_level, 0.01)
        bonus_health = self._get_var(ability_vars, 'BonusHealth', unit.star_level, 350)

        # Count nearby enemies for durability scaling
        nearby_enemies = self._get_enemies_in_radius(unit.position, 3, enemies)
        enemy_count = len(nearby_enemies)

        # Apply durability (damage reduction)
        total_dr = bonus_durability + (durability_per_enemy * enemy_count)
        unit.stats.damage_reduction += total_dr

        # Grant bonus health
        unit.stats.max_hp += bonus_health
        unit.stats.hp += bonus_health

        # Deal damage to nearby enemies
        for enemy in nearby_enemies:
            self._deal_damage(unit, enemy, ap_damage + unit.stats.ap,
                             DamageType.MAGIC, "riftherald_warp")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Warp Armor",
                             durability=total_dr, enemies_nearby=enemy_count)
        return True

    # =========================================================================
    # LEONA - Flat Damage Reduction Passive
    # =========================================================================

    def _cast_leona(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                    ability_vars: Dict) -> bool:
        """Leona - Solar Flare: Stun enemies and gain flat damage reduction."""
        from .combat_engine import DamageType

        flat_dr = self._get_var(ability_vars, 'FlatDR', unit.star_level, 30)
        num_enemies = int(self._get_var(ability_vars, 'NumEnemies', unit.star_level, 3))
        stun_duration = self._get_var(ability_vars, 'StunDuration', unit.star_level, 1.0)
        damage = self._get_var(ability_vars, 'Damage', unit.star_level, 120)

        # Apply flat damage reduction as a passive (stacks)
        if not hasattr(unit, '_leona_flat_dr'):
            unit._leona_flat_dr = 0
        unit._leona_flat_dr += flat_dr

        # Stun and damage nearest enemies
        targets = sorted([e for e in enemies if e.is_alive and e.is_targetable],
                        key=lambda e: self._hex_distance(unit.position, e.position))[:num_enemies]

        for target in targets:
            self._deal_damage(unit, target, damage + unit.stats.ap,
                             DamageType.MAGIC, "leona_solar_flare")
            self._apply_stun(target, stun_duration, "leona_stun")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Solar Flare",
                             flat_dr=unit._leona_flat_dr, targets=[t.name for t in targets])
        return True

    def apply_leona_flat_dr(self, unit: 'Unit', incoming_damage: float) -> float:
        """Apply Leona's flat damage reduction to incoming damage."""
        flat_dr = getattr(unit, '_leona_flat_dr', 0)
        if flat_dr > 0:
            return max(0, incoming_damage - flat_dr)
        return incoming_damage

    # =========================================================================
    # TARIC - Passive MR Aura + Heal at 35% HP
    # =========================================================================

    def _cast_taric(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                    ability_vars: Dict) -> bool:
        """Taric - Starlight's Touch: Shield self + 2 lowest health allies, empowered attacks.

        Passive (always active at combat start): All allies gain 10/20/100 MR.
        Passive (once per combat): At 35% HP, restore 300/700/2500 health over 2s.
        Active: Shield self (600/700/2500) + 2 lowest health allies (125/150/1000).
        Empowered: Next 2/2/10 attacks deal 200/300/3000 bonus magic damage.
        """
        # Get ability variables
        taric_shield = self._get_var(ability_vars, 'TaricShield', unit.star_level, 600)
        ally_shield = self._get_var(ability_vars, 'AllyShield', unit.star_level, 125)
        num_empowered_attacks = int(self._get_var(ability_vars, 'NumEmpoweredAttacks', unit.star_level, 2))
        bonus_damage = self._get_var(ability_vars, 'BonusDamage', unit.star_level, 200)

        # Shield self
        self.engine.apply_shield(unit, taric_shield + unit.stats.ap * 0.5, "taric_starlight_shield")

        # Shield 2 LOWEST HEALTH allies (not nearest!)
        living_allies = [a for a in allies if a.is_alive and a != unit]
        if living_allies:
            # Sort by HP (lowest first)
            living_allies.sort(key=lambda a: a.stats.hp)
            for ally in living_allies[:2]:
                self.engine.apply_shield(ally, ally_shield + unit.stats.ap * 0.3, "taric_ally_shield")

        # Grant empowered attacks (deal bonus MAGIC damage)
        unit._taric_empowered_attacks = num_empowered_attacks
        unit._taric_bonus_damage = bonus_damage

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Starlight's Touch",
                             self_shield=taric_shield, ally_shield=ally_shield,
                             empowered_attacks=num_empowered_attacks)
        return True

    def apply_taric_passive_mr(self, taric: 'Unit', allies: List['Unit'], ability_vars: Dict):
        """Apply Taric's passive MR aura at combat start."""
        mr_for_allies = self._get_var(ability_vars, 'MRForAllies', taric.star_level, 10)
        for ally in allies:
            if ally.is_alive:
                ally.stats.magic_resist += mr_for_allies
        self.engine.log_event('taric_passive_mr', unit=taric.name, mr_granted=mr_for_allies)

    def check_taric_empowered_attack(self, unit: 'Unit') -> float:
        """Check if Taric has empowered attacks remaining and return bonus MAGIC damage."""
        if unit.api_name != 'TFT16_Taric':
            return 0

        if hasattr(unit, '_taric_empowered_attacks') and unit._taric_empowered_attacks > 0:
            unit._taric_empowered_attacks -= 1
            return getattr(unit, '_taric_bonus_damage', 200)
        return 0

    def check_taric_low_hp_heal(self, unit: 'Unit', ability_vars: Dict) -> bool:
        """Check if Taric should heal at 35% HP (once per combat, heals over 2 seconds)."""
        if unit.api_name != 'TFT16_Taric':
            return False

        if hasattr(unit, '_taric_heal_used'):
            return False

        hp_percent = unit.stats.hp / unit.stats.max_hp
        if hp_percent <= 0.35:
            unit._taric_heal_used = True
            passive_heal = self._get_var(ability_vars, 'PassiveHeal', unit.star_level, 300)
            # Heal over 2 seconds (simplified: instant heal for simulator)
            self.engine.heal_unit(unit, passive_heal, "taric_35_percent_heal")
            self.engine.log_event('taric_low_hp_heal', unit=unit.name,
                                 hp_percent=hp_percent, heal=passive_heal)
            return True
        return False

    # Legacy function name for backwards compatibility
    def check_taric_invulnerability(self, unit: 'Unit') -> bool:
        """DEPRECATED: Taric doesn't have invulnerability - he has a heal at 35% HP."""
        # Delegate to the correct function
        ability_vars = {}  # Would need to pass actual vars
        return self.check_taric_low_hp_heal(unit, ability_vars) if unit.api_name == 'TFT16_Taric' else False

    # =========================================================================
    # SKARNER - Armor Aura + Impale
    # =========================================================================

    def _cast_skarner(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                      ability_vars: Dict) -> bool:
        """Skarner - Impale: Grant armor aura, grab and stun target."""
        from .combat_engine import DamageType

        armor_for_allies = self._get_var(ability_vars, 'ArmorForAllies', unit.star_level, 20)
        shield_amount = self._get_var(ability_vars, 'ShieldAmount', unit.star_level, 950)
        shield_duration = self._get_var(ability_vars, 'ShieldDuration', unit.star_level, 4.0)
        impale_duration = self._get_var(ability_vars, 'ImpaleDuration', unit.star_level, 1.75)

        # Grant armor aura to all allies
        for ally in allies:
            if ally.is_alive:
                ally.stats.armor += armor_for_allies

        # Shield self
        self.engine.apply_shield(unit, shield_amount + unit.stats.ap * 0.3, "skarner_shield")

        # Impale nearest enemy - grab and drag them
        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if target:
            # Stun during impale
            self._apply_stun(target, impale_duration, "skarner_impale")

            # Drag target to adjacent hex (pull towards Skarner)
            from .combat_engine import HexGrid
            neighbors = HexGrid.get_neighbors(unit.position)
            valid_spots = [n for n in neighbors if n not in self.engine.get_occupied_hexes()]
            if valid_spots:
                target.position = valid_spots[0]
                self.engine.log_event('skarner_grab', unit=unit.name, target=target.name,
                                     new_position=target.position)

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Impale",
                             armor_granted=armor_for_allies, shield=shield_amount)
        return True

    # =========================================================================
    # XERATH - Ascendant Trait (Store Items)
    # =========================================================================

    def _cast_xerath(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                     ability_vars: Dict) -> bool:
        """Xerath - Eye of the Ascendant: Multiple blasts at random enemies.

        Ascendant trait: After combat, Charm appears in shop (handled externally).
        """
        from .combat_engine import DamageType

        num_blasts = int(self._get_var(ability_vars, 'NumberOfBlasts', unit.star_level, 10))
        damage = self._get_var(ability_vars, 'Damage', unit.star_level, 650)
        spell_range = int(self._get_var(ability_vars, 'SpellRangeInEnemies', unit.star_level, 4))

        # Get targets in range
        targets = [e for e in enemies if e.is_alive and e.is_targetable]

        # Fire blasts at random targets
        for i in range(num_blasts):
            if not targets:
                break
            target = random.choice(targets)
            self._deal_damage(unit, target, damage + unit.stats.ap,
                             DamageType.MAGIC, f"xerath_blast_{i+1}")
            # Remove dead targets
            targets = [t for t in targets if t.is_alive]

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Eye of the Ascendant",
                             blasts=num_blasts)
        return True

    # =========================================================================
    # ZILEAN - Time Bomb Chaining
    # =========================================================================

    def _cast_zilean(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                     ability_vars: Dict) -> bool:
        """Zilean - Visions of the End: Place time bombs that chain and explode.

        Double bomb: If 2 bombs on same target, instant explosion with bonus damage.
        """
        from .combat_engine import DamageType

        magic_damage = self._get_var(ability_vars, 'MagicDamage', unit.star_level, 115)
        explosion_damage = self._get_var(ability_vars, 'ExplosionDamage', unit.star_level, 225)
        mana_on_kill = self._get_var(ability_vars, 'ManaOnKill', unit.star_level, 15)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Track bombs on target
        if not hasattr(target, '_zilean_bombs'):
            target._zilean_bombs = 0

        target._zilean_bombs += 1

        # Apply initial damage
        self._deal_damage(unit, target, magic_damage + unit.stats.ap,
                         DamageType.MAGIC, "zilean_bomb")

        # Double bomb check - if 2+ bombs, instant massive explosion
        if target._zilean_bombs >= 2:
            # Double bomb explosion - deals to target and nearby
            self._deal_damage(unit, target, explosion_damage + unit.stats.ap,
                             DamageType.MAGIC, "zilean_double_bomb")

            # Splash to nearby
            nearby = self._get_enemies_in_radius(target.position, 1, enemies)
            for enemy in nearby:
                if enemy != target:
                    self._deal_damage(unit, enemy, explosion_damage * 0.5 + unit.stats.ap,
                                     DamageType.MAGIC, "zilean_bomb_splash")

            target._zilean_bombs = 0  # Reset bombs
            self.engine.log_event('zilean_double_bomb', unit=unit.name, target=target.name)

        unit.stats.mana = 0
        # Mana refund on kill (refund after spending mana)
        if not target.is_alive:
            self.engine.gain_mana(unit, mana_on_kill, source="zilean_kill_refund")
        self.engine.log_event('ability_cast', unit=unit.name, ability="Visions of the End",
                             bombs_on_target=target._zilean_bombs if target.is_alive else 0)
        return True

    # =========================================================================
    # MEL - Mana Drain + Radiant Eclipse
    # =========================================================================

    def _cast_mel(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                  ability_vars: Dict) -> bool:
        """Mel - Radiant Eclipse: Orbs that damage + mana drain passive.

        Passive: Drains 1 mana/sec from nearby enemies.
        Trait: Can generate radiant items (handled externally).
        """
        from .combat_engine import DamageType

        num_orbs = int(self._get_var(ability_vars, 'NumOfOrbs', unit.star_level, 2))
        passive_damage = self._get_var(ability_vars, 'PassiveDamage', unit.star_level, 60)
        target_damage = self._get_var(ability_vars, 'TargetDamage', unit.star_level, 1500)
        explosion_damage = self._get_var(ability_vars, 'ExplosionDamage', unit.star_level, 600)

        # Primary target
        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Fire orbs at target
        for i in range(num_orbs):
            if not target.is_alive:
                target = self._find_nearest_enemy(unit, enemies)
                if not target:
                    break
            self._deal_damage(unit, target, target_damage / num_orbs + unit.stats.ap,
                             DamageType.MAGIC, f"mel_orb_{i+1}")

        # Final explosion
        nearby = self._get_enemies_in_radius(target.position if target else unit.position, 2, enemies)
        for enemy in nearby:
            self._deal_damage(unit, enemy, explosion_damage + unit.stats.ap,
                             DamageType.MAGIC, "mel_explosion")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Radiant Eclipse",
                             orbs=num_orbs)
        return True

    def mel_mana_drain_tick(self, unit: 'Unit', enemies: List['Unit']):
        """Mel's passive: Drain 1 mana/sec from nearby enemies."""
        if unit.api_name != 'TFT16_Mel' or not unit.is_alive:
            return

        nearby = self._get_enemies_in_radius(unit.position, 2, enemies)
        for enemy in nearby:
            if enemy.is_alive:
                enemy.stats.mana = max(0, enemy.stats.mana - 1)

    # =========================================================================
    # SETT - The Show Stopper (Multi-dash)
    # =========================================================================

    def _cast_sett(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                   ability_vars: Dict) -> bool:
        """Sett - The Show Stopper: Dash to target, slam for %HP damage."""
        from .combat_engine import DamageType

        aoe_radius = int(self._get_var(ability_vars, 'AoERadius', unit.star_level, 3))
        flat_damage = self._get_var(ability_vars, 'FlatAPDamage', unit.star_level, 350)
        pct_max_hp = self._get_var(ability_vars, 'PercentOfTargetMaxHealth', unit.star_level, 0.09)
        aoe_damage_pct = self._get_var(ability_vars, 'PercentAoEDamage', unit.star_level, 0.5)

        # Find farthest enemy for slam
        target = self._find_farthest_enemy(unit, enemies, 99)
        if not target:
            target = self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Dash to target position
        self._dash_to_position(unit, target.position)

        # Calculate slam damage: flat + %maxHP
        slam_damage = flat_damage + unit.stats.ap + (target.stats.max_hp * pct_max_hp)

        # Primary target takes full damage
        self._deal_damage(unit, target, slam_damage, DamageType.MAGIC, "sett_slam_primary")

        # AoE damage to nearby enemies (50% of primary damage)
        nearby = self._get_enemies_in_radius(target.position, aoe_radius, enemies)
        for enemy in nearby:
            if enemy != target:
                aoe_damage = slam_damage * aoe_damage_pct
                self._deal_damage(unit, enemy, aoe_damage, DamageType.MAGIC, "sett_slam_aoe")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="The Show Stopper",
                             primary_target=target.name, aoe_radius=aoe_radius)
        return True

    # =========================================================================
    # BROCK - Board-wide Seismic Passive
    # =========================================================================

    def _cast_brock(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                    ability_vars: Dict) -> bool:
        """Brock - Seismic Slam: Board-wide slam with falloff.

        Passive: Attacks deal 50% damage to nearby enemies.
        Active: Slam all enemies, damage/stun reduced by distance.
        """
        from .combat_engine import DamageType, HexGrid

        passive_aoe = self._get_var(ability_vars, 'PassivePercentAoE', unit.star_level, 0.5)
        slam_base = self._get_var(ability_vars, 'SlamDamageBase', unit.star_level, 200)
        slam_hp_pct = self._get_var(ability_vars, 'SlamDamageHealth', unit.star_level, 0.02)
        stun_duration = self._get_var(ability_vars, 'StunDuration', unit.star_level, 1.75)
        reduction_per_hex = self._get_var(ability_vars, 'EffectReductionPerHex', unit.star_level, 0.15)
        reduction_minimum = self._get_var(ability_vars, 'EffectReductionMinimum', unit.star_level, 0.40)

        # Board-wide slam with distance falloff
        for enemy in enemies:
            if not enemy.is_alive or not enemy.is_targetable:
                continue

            distance = HexGrid.hex_distance(unit.position, enemy.position)

            # Calculate falloff: 15% reduction per hex, minimum 40% effectiveness
            effectiveness = max(reduction_minimum, 1.0 - (distance * reduction_per_hex))

            # Damage: base + 2% enemy max HP
            base_damage = slam_base + unit.stats.ad + (enemy.stats.max_hp * slam_hp_pct)
            final_damage = base_damage * effectiveness

            self._deal_damage(unit, enemy, final_damage, DamageType.PHYSICAL, "brock_slam")

            # Stun with falloff
            effective_stun = stun_duration * effectiveness
            if effective_stun > 0.5:  # Only stun if meaningful
                self._apply_stun(enemy, effective_stun, "brock_stun")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Seismic Slam",
                             enemies_hit=len([e for e in enemies if e.is_alive]))
        return True

    def brock_passive_aoe(self, unit: 'Unit', target: 'Unit', damage: float, enemies: List['Unit']):
        """Brock's passive: Attacks deal 50% damage to nearby enemies."""
        if unit.api_name != 'TFT16_Brock':
            return

        from .combat_engine import DamageType

        nearby = self._get_enemies_in_radius(target.position, 1, enemies)
        for enemy in nearby:
            if enemy != target and enemy.is_alive:
                splash = damage * 0.5
                self.engine.apply_damage(unit, enemy, splash, DamageType.PHYSICAL, "brock_passive_splash")

    # =========================================================================
    # HERO AUGMENT ABILITY HANDLERS
    # =========================================================================

    # -------------------------------------------------------------------------
    # XIN ZHAO - Trials of Twilight
    # -------------------------------------------------------------------------

    def _cast_xinzhao(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                      ability_vars: Dict) -> bool:
        """Xin Zhao - Three Talon Strike: Knockup + enhanced attacks.

        Hero Augment (Trials of Twilight):
        - Constantly strikes nearby enemies
        - Executes enemies below 15% HP
        - Transforms to Zaahen after 5 rounds as 3-star
        """
        from .combat_engine import DamageType

        base_damage = self._get_var(ability_vars, 'Damage', unit.star_level, 200)
        knockup_duration = self._get_var(ability_vars, 'KnockupDuration', unit.star_level, 1.5)
        enhanced_attacks = int(self._get_var(ability_vars, 'EnhancedAttacks', unit.star_level, 3))

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Check for hero augment
        hero_effects = getattr(unit, '_hero_augment_effects', {})
        has_hero_augment = hero_effects.get('constant_strikes', False)
        execute_threshold = hero_effects.get('execute_threshold', 0)

        # Base ability: Knockup + damage
        damage = base_damage + unit.stats.ad + unit.stats.ap
        self._deal_damage(unit, target, damage, DamageType.PHYSICAL, "xinzhao_strike")
        self._apply_stun(target, knockup_duration, "xinzhao_knockup")

        # Hero Augment: Execute low HP enemies
        if has_hero_augment and execute_threshold > 0:
            for enemy in enemies:
                if enemy.is_alive and enemy.is_targetable:
                    hp_pct = enemy.stats.hp / enemy.stats.max_hp
                    if hp_pct <= execute_threshold:
                        self.engine.apply_damage(unit, enemy, enemy.stats.hp + 1,
                                                DamageType.TRUE, "xinzhao_execute")
                        self.engine.log_event('execute', unit=unit.name, target=enemy.name,
                                             threshold=execute_threshold, source="Trials of Twilight")

        # Grant enhanced attacks
        unit.enhanced_attacks_remaining = enhanced_attacks
        unit.enhanced_attack_bonus_ad = base_damage * 0.3

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Three Talon Strike",
                             hero_augment=has_hero_augment)
        return True

    def xinzhao_hero_tick(self, unit: 'Unit', enemies: List['Unit'], dt: float):
        """Xin Zhao hero augment: Constantly strike nearby enemies.

        Called each combat tick when Trials of Twilight is active.
        """
        hero_effects = getattr(unit, '_hero_augment_effects', {})
        if not hero_effects.get('constant_strikes'):
            return

        from .combat_engine import DamageType

        # Track strike cooldown (strikes every 0.5s based on attack speed)
        if not hasattr(unit, '_hero_strike_timer'):
            unit._hero_strike_timer = 0

        unit._hero_strike_timer += dt
        strike_interval = 0.5 / max(0.5, unit.stats.attack_speed)

        if unit._hero_strike_timer >= strike_interval:
            unit._hero_strike_timer = 0

            # Strike all enemies within 2 hexes
            nearby = self._get_enemies_in_radius(unit.position, 2, enemies)
            if nearby:
                damage = unit.stats.ad * 0.4  # 40% AD per strike
                for enemy in nearby:
                    self._deal_damage(unit, enemy, damage, DamageType.PHYSICAL, "xinzhao_hero_strike")

                # Check for executes
                execute_threshold = hero_effects.get('execute_threshold', 0.15)
                for enemy in nearby:
                    if enemy.is_alive:
                        hp_pct = enemy.stats.hp / enemy.stats.max_hp
                        if hp_pct <= execute_threshold:
                            self.engine.apply_damage(unit, enemy, enemy.stats.hp + 1,
                                                    DamageType.TRUE, "xinzhao_execute")

    # -------------------------------------------------------------------------
    # RUMBLE - Artillery Barrage
    # -------------------------------------------------------------------------

    def _cast_rumble(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                     ability_vars: Dict) -> bool:
        """Rumble - Flamespitter: Cone damage.

        Hero Augment (Artillery Barrage):
        - +7 Range
        - Constantly fires missiles at enemies
        - Missile rate scales with attack speed
        """
        from .combat_engine import DamageType

        base_damage = self._get_var(ability_vars, 'Damage', unit.star_level, 180)
        burn_damage = self._get_var(ability_vars, 'BurnDamage', unit.star_level, 50)
        burn_duration = self._get_var(ability_vars, 'BurnDuration', unit.star_level, 3.0)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Check for hero augment
        hero_effects = getattr(unit, '_hero_augment_effects', {})
        has_hero_augment = hero_effects.get('constant_missiles', False)

        # Base ability: Cone flame damage
        damage = base_damage + unit.stats.ap
        nearby = self._get_enemies_in_radius(target.position, 2, enemies)

        for enemy in nearby:
            self._deal_damage(unit, enemy, damage, DamageType.MAGIC, "rumble_flame")
            # Apply burn DoT marker
            enemy._rumble_burn = burn_damage + unit.stats.ap * 0.2
            enemy._rumble_burn_duration = burn_duration

        # Hero Augment: Fire bonus missiles
        if has_hero_augment:
            # Fire missiles at random enemies (scales with AS)
            missile_count = int(2 + unit.stats.attack_speed)
            missile_damage = (base_damage + unit.stats.ap) * 0.3
            targets = [e for e in enemies if e.is_alive and e.is_targetable]

            for _ in range(missile_count):
                if targets:
                    missile_target = random.choice(targets)
                    self._deal_damage(unit, missile_target, missile_damage,
                                     DamageType.MAGIC, "rumble_missile")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Flamespitter",
                             hero_augment=has_hero_augment)
        return True

    def rumble_hero_tick(self, unit: 'Unit', enemies: List['Unit'], dt: float):
        """Rumble hero augment: Constantly fire missiles.

        Called each combat tick when Artillery Barrage is active.
        """
        hero_effects = getattr(unit, '_hero_augment_effects', {})
        if not hero_effects.get('constant_missiles'):
            return

        from .combat_engine import DamageType

        # Track missile cooldown (fires every 0.75s, faster with AS)
        if not hasattr(unit, '_hero_missile_timer'):
            unit._hero_missile_timer = 0

        unit._hero_missile_timer += dt
        missile_interval = 0.75 / max(0.5, unit.stats.attack_speed)

        if unit._hero_missile_timer >= missile_interval:
            unit._hero_missile_timer = 0

            # Fire missile at random enemy
            targets = [e for e in enemies if e.is_alive and e.is_targetable]
            if targets:
                target = random.choice(targets)
                missile_damage = unit.stats.ad * 0.5 + unit.stats.ap * 0.3
                self._deal_damage(unit, target, missile_damage, DamageType.MAGIC, "rumble_hero_missile")

    # -------------------------------------------------------------------------
    # ILLAOI - Leap of Faith
    # -------------------------------------------------------------------------

    def _cast_illaoi(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                     ability_vars: Dict) -> bool:
        """Illaoi - Harsh Lesson: Slam target.

        Hero Augment (Leap of Faith):
        - Becomes a Fighter
        - Ability replaced with airborne slam
        - Recast immediately when kills target
        """
        from .combat_engine import DamageType

        base_damage = self._get_var(ability_vars, 'Damage', unit.star_level, 250)
        heal_per_enemy = self._get_var(ability_vars, 'HealPerEnemy', unit.star_level, 100)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Check for hero augment
        hero_effects = getattr(unit, '_hero_augment_effects', {})
        has_hero_augment = hero_effects.get('slam_ability', False)

        if has_hero_augment:
            # Leap of Faith: Airborne slam with recast on kill
            damage = base_damage + unit.stats.ad * 1.5 + unit.stats.ap

            # Dash to target
            self._dash_to_position(unit, target.position)

            # Apply stun (airborne)
            self._apply_stun(target, 1.5, "illaoi_airborne")

            # Deal damage
            self._deal_damage(unit, target, damage, DamageType.PHYSICAL, "illaoi_slam")

            # Check for recast on kill
            if not target.is_alive and hero_effects.get('recast_on_kill'):
                # Find next target and recast (up to 3 times)
                recast_count = getattr(unit, '_illaoi_recast_count', 0)
                if recast_count < 3:
                    unit._illaoi_recast_count = recast_count + 1
                    # Queue another cast (mana stays at 0)
                    unit._illaoi_pending_recast = True
                    self.engine.log_event('illaoi_recast', unit=unit.name,
                                         recast_num=recast_count + 1)

            # Heal based on enemies in range
            nearby = self._get_enemies_in_radius(unit.position, 2, enemies)
            heal = heal_per_enemy * len(nearby)
            self.engine.heal_unit(unit, heal, "illaoi_tentacle_heal")

            self.engine.log_event('ability_cast', unit=unit.name, ability="Leap of Faith",
                                 target=target.name, recast=has_hero_augment)
        else:
            # Normal ability: Slam + heal
            damage = base_damage + unit.stats.ad + unit.stats.ap
            self._deal_damage(unit, target, damage, DamageType.PHYSICAL, "illaoi_slam")

            # Heal per enemy hit
            nearby = self._get_enemies_in_radius(target.position, 2, enemies)
            for enemy in nearby:
                if enemy != target:
                    self._deal_damage(unit, enemy, damage * 0.5, DamageType.PHYSICAL, "illaoi_splash")

            heal = heal_per_enemy * len(nearby)
            self.engine.heal_unit(unit, heal, "illaoi_heal")

            self.engine.log_event('ability_cast', unit=unit.name, ability="Harsh Lesson",
                                 targets_hit=len(nearby))

        unit.stats.mana = 0
        return True

    def check_illaoi_recast(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                            ability_vars: Dict) -> bool:
        """Check if Illaoi should recast due to Leap of Faith kill."""
        if getattr(unit, '_illaoi_pending_recast', False):
            unit._illaoi_pending_recast = False
            return self._cast_illaoi(unit, enemies, allies, ability_vars)
        return False

    def _cast_jhin(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                   ability_vars: Dict) -> bool:
        """Jhin - Curtain Call: 4 cannon shots, 4th shot does bonus damage.

        Regular attacks use normal attack speed. During Curtain Call,
        attack speed is capped at 1.0 (1 shot per second).
        ADDamage/APDamage are per-shot scaling percentages.
        4th shot deals FourthShotDamageMult (1.44x) more damage.
        """
        from .combat_engine import DamageType

        ad_pct = self._get_var(ability_vars, 'ADDamage', unit.star_level, 145)
        ap_pct = self._get_var(ability_vars, 'APDamage', unit.star_level, 15)
        fourth_mult = self._get_var(ability_vars, 'FourthShotDamageMult', unit.star_level, 1.44)

        # Per-shot damage: AD scaling + AP scaling
        per_shot = (ad_pct / 100.0) * unit.stats.ad + (ap_pct / 100.0) * unit.stats.ap

        # 4 shots: 3 normal + 1 boosted (4th shot)
        targets = [e for e in enemies if e.is_alive and e.is_targetable]
        if not targets:
            return False

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        shots_fired = 0
        for i in range(4):
            if not target or not target.is_alive:
                # Retarget
                targets = [e for e in enemies if e.is_alive and e.is_targetable]
                if not targets:
                    break
                target = self._find_nearest_enemy(unit, targets)
                if not target:
                    break

            damage = per_shot * fourth_mult if i == 3 else per_shot
            self._deal_damage(unit, target, damage, DamageType.PHYSICAL, "jhin_curtain_call")
            shots_fired += 1

        # Curtain Call fires at capped 1.0 AS regardless of Jhin's actual AS.
        # 4 shots at 1.0 AS = 3 intervals of 1.0s each = 3.0s channel time.
        unit.attack_cooldown = 3.0
        unit._custom_cast_time = True

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Curtain Call",
                             shots=shots_fired)
        return True

    # -------------------------------------------------------------------------
    # VIEGO - The Ruined King (Hero Augment Modifier)
    # -------------------------------------------------------------------------

    def viego_hero_augment_check(self, unit: 'Unit', allies: List['Unit']):
        """Check and apply Viego's hero augment effects.

        The Ruined King:
        - Shares 30% of passive with Shadow Isles allies
        - Ability upgrades after 100 souls
        """
        hero_effects = getattr(unit, '_hero_augment_effects', {})
        if not hero_effects:
            return

        # Check for ability upgrade at 100 souls
        soul_req = hero_effects.get('soul_req_upgrade', 100)
        soul_count = self.engine.trait_manager.get_shadow_isles_souls(unit.team)

        if soul_count >= soul_req and not getattr(unit, '_viego_ability_upgraded', False):
            unit._viego_ability_upgraded = True
            # Upgrade: Double the stacking damage
            unit._viego_upgrade_damage_mult = 2.0
            self.engine.log_event('viego_upgrade', unit=unit.name, souls=soul_count,
                                 effect="Ability damage doubled")

        # Share passive with SI allies (applied at combat start via AugmentManager)
        share_pct = hero_effects.get('passive_share_percent', 0.30)
        viego_stacks = getattr(unit, '_viego_stacks', 0)

        if viego_stacks > 0:
            shared_damage = viego_stacks * share_pct
            for ally in allies:
                if ally != unit and ally.is_alive and 'Shadow Isles' in ally.traits:
                    if getattr(ally, '_viego_passive_share', 0) > 0:
                        # Apply shared stacking damage bonus
                        ally.stats.ad += shared_damage * 0.1  # 10% of shared per tick

    # =========================================================================
    # COST 1 CHAMPION ABILITIES
    # =========================================================================

    def _cast_anivia(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                     ability_vars: Dict) -> bool:
        """Anivia - Frostbite: Damage current target, refund mana on kill."""
        from .combat_engine import DamageType

        damage = self._get_var(ability_vars, 'Damage', unit.star_level, 325)
        mana_refund = self._get_var(ability_vars, 'ManaRefund', unit.star_level, 10)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        actual, _ = self._deal_damage(unit, target, damage + unit.stats.ap,
                                      DamageType.MAGIC, "anivia_frostbite")

        unit.stats.mana = 0
        if not target.is_alive:
            self.engine.gain_mana(unit, mana_refund, source="anivia_kill_refund")
        self.engine.log_event('ability_cast', unit=unit.name, ability="Frostbite")
        return True

    def _cast_blitzcrank(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                         ability_vars: Dict) -> bool:
        """Blitzcrank - Static Field: Shield self, deal MR-scaled damage in area."""
        from .combat_engine import DamageType

        shield = self._get_var(ability_vars, 'Shield', unit.star_level, 400)
        duration = self._get_var(ability_vars, 'Duration', unit.star_level, 4)
        radius = int(self._get_var(ability_vars, 'HexRadius', unit.star_level, 1))
        mr_ratio = self._get_var(ability_vars, 'MRDamageRatio', unit.star_level, 1.4)

        self.engine.apply_shield(unit, shield, "blitzcrank_static_field")

        nearby = self._get_enemies_in_radius(unit.position, radius, enemies)
        for enemy in nearby:
            damage = unit.stats.magic_resist * mr_ratio
            self._deal_damage(unit, enemy, damage, DamageType.MAGIC, "blitzcrank_static_field")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Static Field",
                             targets_hit=len(nearby))
        return True

    def _cast_briar(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                    ability_vars: Dict) -> bool:
        """Briar - Blood Frenzy: Buff AD and grant decaying attack speed."""
        bonus_ad_pct = self._get_var(ability_vars, 'BonusAD', unit.star_level, 0.25)
        decaying_as = self._get_var(ability_vars, 'DecayingAttackSpeed', unit.star_level, 3.0)
        duration = self._get_var(ability_vars, 'Duration', unit.star_level, 4.0)

        unit.stats.ad *= (1 + bonus_ad_pct)
        # Average of decaying AS over duration (half the peak)
        unit.stats.attack_speed += decaying_as * 0.5

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Blood Frenzy",
                             bonus_ad_pct=bonus_ad_pct, as_boost=decaying_as)
        return True

    def _cast_jarvaniv(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                       ability_vars: Dict) -> bool:
        """Jarvan IV - Demacian Standard: Shield self and grant attack speed to nearby allies."""
        shield = self._get_var(ability_vars, 'Shield', unit.star_level, 350)
        as_buff = self._get_var(ability_vars, 'AttackSpeed', unit.star_level, 0.20)
        as_duration = self._get_var(ability_vars, 'AttackSpeedDuration', unit.star_level, 4.0)

        self.engine.apply_shield(unit, shield, "jarvan_standard")

        # Buff nearby allies' attack speed
        buffed = 0
        for ally in allies:
            if ally.is_alive and ally != unit:
                ally.stats.attack_speed += as_buff
                buffed += 1

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Demacian Standard",
                             shield=shield, allies_buffed=buffed)
        return True

    def _cast_kogmaw(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                     ability_vars: Dict) -> bool:
        """Kog'Maw - Caustic Spittle: Damage target + splash to secondary, reduce armor."""
        from .combat_engine import DamageType

        damage = self._get_var(ability_vars, 'Damage', unit.star_level, 140)
        armor_red = self._get_var(ability_vars, 'ArmorReduction', unit.star_level, 8)
        splash_pct = self._get_var(ability_vars, 'PercentToSecondaryEnemies', unit.star_level, 0.5)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        target.stats.armor = max(0, target.stats.armor - armor_red)
        self._deal_damage(unit, target, damage + unit.stats.ap,
                         DamageType.MAGIC, "kogmaw_caustic_spittle")

        # Splash damage to nearby enemies
        nearby = self._get_enemies_in_radius(target.position, 1, enemies)
        for enemy in nearby:
            if enemy != target:
                self._deal_damage(unit, enemy, (damage + unit.stats.ap) * splash_pct,
                                 DamageType.MAGIC, "kogmaw_splash")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Caustic Spittle")
        return True

    def _cast_lulu(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                   ability_vars: Dict) -> bool:
        """Lulu - Whimsy: Polymorph target (stun) + damage, secondary damage to another."""
        from .combat_engine import DamageType

        damage = self._get_var(ability_vars, 'Damage', unit.star_level, 285)
        stun_dur = self._get_var(ability_vars, 'StunDuration', unit.star_level, 2.0)
        secondary = self._get_var(ability_vars, 'SecondaryDamage', unit.star_level, 120)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        self._deal_damage(unit, target, damage + unit.stats.ap,
                         DamageType.MAGIC, "lulu_whimsy")
        self._apply_stun(target, stun_dur, "lulu_polymorph")

        # Secondary damage to another enemy
        others = [e for e in enemies if e.is_alive and e.is_targetable and e != target]
        if others and secondary > 0:
            sec_target = random.choice(others)
            self._deal_damage(unit, sec_target, secondary + unit.stats.ap,
                             DamageType.MAGIC, "lulu_whimsy_secondary")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Whimsy")
        return True

    def _cast_qiyana(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                     ability_vars: Dict) -> bool:
        """Qiyana - Clear The Brush: Dash and deal AD+AP damage to target."""
        from .combat_engine import DamageType, HexGrid

        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 160)
        ap_damage = self._get_var(ability_vars, 'APDamage', unit.star_level, 20)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Dash toward target
        self._dash_to_position(unit, target.position)

        total = ad_damage + unit.stats.ad + ap_damage + unit.stats.ap
        self._deal_damage(unit, target, total, DamageType.PHYSICAL, "qiyana_clear_brush")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Clear The Brush")
        return True

    def _cast_shen(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                   ability_vars: Dict) -> bool:
        """Shen - Stand United: Shield the lowest HP ally."""
        shield = self._get_var(ability_vars, 'Shield', unit.star_level, 250)
        duration = self._get_var(ability_vars, 'Duration', unit.star_level, 4.0)

        # Find lowest HP ally
        valid_allies = [a for a in allies if a.is_alive and a != unit]
        if valid_allies:
            target = min(valid_allies, key=lambda a: a.stats.hp / max(a.stats.max_hp, 1))
            self.engine.apply_shield(target, shield, "shen_stand_united")
        else:
            self.engine.apply_shield(unit, shield, "shen_stand_united")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Stand United")
        return True

    def _cast_sona(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                   ability_vars: Dict) -> bool:
        """Sona - Power Chord: Damage enemies and heal lowest HP allies."""
        from .combat_engine import DamageType

        damage = self._get_var(ability_vars, 'Damage', unit.star_level, 130)
        heal_amt = self._get_var(ability_vars, 'HealAmount', unit.star_level, 30)
        num_enemies = int(self._get_var(ability_vars, 'NumEnemies', unit.star_level, 2))

        # Damage random enemies
        targets = [e for e in enemies if e.is_alive and e.is_targetable]
        hit_targets = random.sample(targets, min(num_enemies, len(targets))) if targets else []
        for target in hit_targets:
            self._deal_damage(unit, target, damage + unit.stats.ap,
                             DamageType.MAGIC, "sona_power_chord")

        # Heal lowest HP allies
        hurt_allies = sorted([a for a in allies if a.is_alive],
                            key=lambda a: a.stats.hp / max(a.stats.max_hp, 1))
        for ally in hurt_allies[:num_enemies]:
            self.engine.heal_unit(ally, heal_amt + unit.stats.ap, "sona_heal")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Power Chord")
        return True

    # =========================================================================
    # COST 2 CHAMPION ABILITIES
    # =========================================================================

    def _cast_ashe(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                   ability_vars: Dict) -> bool:
        """Ashe - True Ice Arrow: Long-range stun + AoE damage, execute below 30% HP."""
        from .combat_engine import DamageType

        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 135)
        ap_damage = self._get_var(ability_vars, 'APDamage', unit.star_level, 20)
        aoe_pct = self._get_var(ability_vars, 'AOEPercent', unit.star_level, 0.33)
        duration = self._get_var(ability_vars, 'Duration', unit.star_level, 3.0)
        execute_threshold = self._get_var(ability_vars, 'TrueDamageHealthBreakpoint', unit.star_level, 0.30)

        target = self._find_farthest_enemy(unit, enemies)
        if not target:
            return False

        total = ad_damage + unit.stats.ad + ap_damage + unit.stats.ap

        # Execute: true damage if below threshold
        if target.stats.hp / max(target.stats.max_hp, 1) < execute_threshold:
            self._deal_damage(unit, target, total, DamageType.TRUE, "ashe_execute")
        else:
            self._deal_damage(unit, target, total, DamageType.PHYSICAL, "ashe_arrow")

        self._apply_stun(target, duration, "ashe_arrow_stun")

        # AoE splash around target
        nearby = self._get_enemies_in_radius(target.position, 1, enemies)
        for enemy in nearby:
            if enemy != target:
                self._deal_damage(unit, enemy, total * aoe_pct,
                                 DamageType.PHYSICAL, "ashe_arrow_aoe")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="True Ice Arrow")
        return True

    def _cast_chogath(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                      ability_vars: Dict) -> bool:
        """Cho'Gath - Rupture: AoE knockup + %max HP damage + heal on hit."""
        from .combat_engine import DamageType

        ap_damage = self._get_var(ability_vars, 'APDamage', unit.star_level, 45)
        pct_hp = self._get_var(ability_vars, 'PercentMaximumHealthDamage', unit.star_level, 0.05)
        knockup = self._get_var(ability_vars, 'KnockupDuration', unit.star_level, 1.5)
        heal = self._get_var(ability_vars, 'Heal', unit.star_level, 200)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # AoE around target
        hit = self._get_enemies_in_radius(target.position, 1, enemies)
        for enemy in hit:
            damage = ap_damage + unit.stats.ap + enemy.stats.max_hp * pct_hp
            self._deal_damage(unit, enemy, damage, DamageType.MAGIC, "chogath_rupture")
            self._apply_stun(enemy, knockup, "chogath_knockup")

        if hit:
            self.engine.heal_unit(unit, heal, "chogath_feast")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Rupture",
                             targets_hit=len(hit))
        return True

    def _cast_ekko(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                   ability_vars: Dict) -> bool:
        """Ekko - Parallel Convergence: AoE damage + bonus on-hit magic damage buff."""
        from .combat_engine import DamageType

        base_damage = self._get_var(ability_vars, 'BaseMagicDamage', unit.star_level, 130)
        bonus_damage = self._get_var(ability_vars, 'BaseBonusMagicDamage', unit.star_level, 150)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # AoE damage
        hit = self._get_enemies_in_radius(target.position, 1, enemies)
        for enemy in hit:
            self._deal_damage(unit, enemy, base_damage + unit.stats.ap,
                             DamageType.MAGIC, "ekko_convergence")

        # Buff on-hit magic damage
        unit.stats.ap += bonus_damage * 0.1  # Amortized on-hit bonus

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Parallel Convergence",
                             targets_hit=len(hit))
        return True

    def _cast_graves(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                     ability_vars: Dict) -> bool:
        """Graves - Collateral Damage: AD+AP cone damage with falloff."""
        from .combat_engine import DamageType

        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 180)
        ap_damage = self._get_var(ability_vars, 'APDamage', unit.star_level, 20)
        falloff = self._get_var(ability_vars, 'AttackDamageMultiplier', unit.star_level, 0.45)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        total = ad_damage + unit.stats.ad + ap_damage + unit.stats.ap
        self._deal_damage(unit, target, total, DamageType.PHYSICAL, "graves_collateral")

        # Falloff damage to enemies behind target
        behind = [e for e in enemies if e.is_alive and e.is_targetable and e != target]
        for enemy in behind[:2]:
            self._deal_damage(unit, enemy, total * falloff,
                             DamageType.PHYSICAL, "graves_collateral_falloff")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Collateral Damage")
        return True

    def _cast_neeko(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                    ability_vars: Dict) -> bool:
        """Neeko - Pop Blossom: Shield self, AoE damage + chill."""
        from .combat_engine import DamageType

        shield = self._get_var(ability_vars, 'Shield', unit.star_level, 400)
        damage = self._get_var(ability_vars, 'Damage', unit.star_level, 80)
        chill_dur = self._get_var(ability_vars, 'ChillDuration', unit.star_level, 2.0)

        self.engine.apply_shield(unit, shield, "neeko_pop_blossom")

        # AoE damage around self
        hit = self._get_enemies_in_radius(unit.position, 2, enemies)
        for enemy in hit:
            self._deal_damage(unit, enemy, damage + unit.stats.ap,
                             DamageType.MAGIC, "neeko_pop_blossom")
            # Chill = slow (reduce AS)
            enemy.stats.attack_speed = max(0.2, enemy.stats.attack_speed * 0.7)

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Pop Blossom",
                             targets_hit=len(hit))
        return True

    def _cast_orianna(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                      ability_vars: Dict) -> bool:
        """Orianna - Command: Protect: Shield ally, damage nearby enemies."""
        from .combat_engine import DamageType

        shield = self._get_var(ability_vars, 'Shield', unit.star_level, 60)
        target_dmg = self._get_var(ability_vars, 'TargetDamage', unit.star_level, 220)
        explosion_dmg = self._get_var(ability_vars, 'ExplosionDamage', unit.star_level, 120)

        # Shield lowest HP ally
        valid_allies = [a for a in allies if a.is_alive]
        if valid_allies:
            shield_target = min(valid_allies, key=lambda a: a.stats.hp / max(a.stats.max_hp, 1))
            self.engine.apply_shield(shield_target, shield + unit.stats.ap, "orianna_protect")

            # Damage enemies near shielded ally
            hit = self._get_enemies_in_radius(shield_target.position, 2, enemies)
            for enemy in hit:
                self._deal_damage(unit, enemy, explosion_dmg + unit.stats.ap,
                                 DamageType.MAGIC, "orianna_explosion")

        # Also damage current target
        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if target:
            self._deal_damage(unit, target, target_dmg + unit.stats.ap,
                             DamageType.MAGIC, "orianna_command")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Command: Protect")
        return True

    def _cast_poppy(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                    ability_vars: Dict) -> bool:
        """Poppy - Hammer Shock: Damage + knockup target, shield nearby allies."""
        from .combat_engine import DamageType

        damage = self._get_var(ability_vars, 'PrimaryDamage', unit.star_level, 70)
        knockup = self._get_var(ability_vars, 'KnockupDuration', unit.star_level, 0.5)
        shield_amt = self._get_var(ability_vars, 'ShieldAmt', unit.star_level, 330)
        num_shielded = int(self._get_var(ability_vars, 'NumShieldedAllies', unit.star_level, 2))
        ally_shield_pct = self._get_var(ability_vars, 'AllyShieldAmount', unit.star_level, 0.30)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        self._deal_damage(unit, target, damage + unit.stats.ap,
                         DamageType.MAGIC, "poppy_hammer_shock")
        self._apply_stun(target, knockup, "poppy_knockup")

        # Shield self
        self.engine.apply_shield(unit, shield_amt, "poppy_shield")

        # Shield nearby allies (30% of self shield)
        ally_shield = shield_amt * ally_shield_pct
        valid_allies = [a for a in allies if a.is_alive and a != unit]
        for ally in valid_allies[:num_shielded]:
            self.engine.apply_shield(ally, ally_shield, "poppy_ally_shield")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Hammer Shock")
        return True

    def _cast_reksai(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                     ability_vars: Dict) -> bool:
        """Rek'Sai - Burrow: Dash to target, deal multiple attacks with AD+AP scaling."""
        from .combat_engine import DamageType

        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 140)
        ap_damage = self._get_var(ability_vars, 'APDamage', unit.star_level, 20)
        num_attacks = int(self._get_var(ability_vars, 'NumAttacks', unit.star_level, 3))

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        self._dash_to_position(unit, target.position)

        for _ in range(num_attacks):
            if not target.is_alive:
                target = self._find_nearest_enemy(unit, enemies)
                if not target:
                    break
            total = ad_damage + unit.stats.ad + ap_damage + unit.stats.ap
            self._deal_damage(unit, target, total, DamageType.PHYSICAL, "reksai_burrow")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Burrow")
        return True

    def _cast_sion(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                   ability_vars: Dict) -> bool:
        """Sion - Soul Furnace: Shield based on HP + AP, explode for %HP damage on break."""
        from .combat_engine import DamageType

        ap_shield = self._get_var(ability_vars, 'APShield', unit.star_level, 200)
        pct_hp_shield = self._get_var(ability_vars, 'PercentHealthShield', unit.star_level, 0.04)
        pct_hp_damage = self._get_var(ability_vars, 'DamagePercentHealth', unit.star_level, 0.04)
        hp_per_takedown = self._get_var(ability_vars, 'HealthPerTakedown', unit.star_level, 18)

        shield_val = ap_shield + unit.stats.max_hp * pct_hp_shield
        self.engine.apply_shield(unit, shield_val, "sion_soul_furnace")

        # Track takedown bonus
        if not hasattr(unit, '_sion_bonus_hp'):
            unit._sion_bonus_hp = 0

        # Deal %HP damage to nearby enemies
        hit = self._get_enemies_in_radius(unit.position, 1, enemies)
        for enemy in hit:
            damage = enemy.stats.max_hp * pct_hp_damage + unit.stats.ap
            self._deal_damage(unit, enemy, damage, DamageType.MAGIC, "sion_furnace_explode")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Soul Furnace")
        return True

    def _cast_teemo(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                    ability_vars: Dict) -> bool:
        """Teemo - Toxic Dart: Damage target + poison DoT."""
        from .combat_engine import DamageType

        primary = self._get_var(ability_vars, 'PrimaryDamage', unit.star_level, 130)
        dot_dps = self._get_var(ability_vars, 'DamagePerSecond', unit.star_level, 35)
        dot_dur = self._get_var(ability_vars, 'DOtDuration', unit.star_level, 8)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        self._deal_damage(unit, target, primary + unit.stats.ap,
                         DamageType.MAGIC, "teemo_toxic_dart")

        # Apply poison DoT as upfront damage (simplified)
        total_dot = dot_dps * dot_dur
        self._deal_damage(unit, target, total_dot, DamageType.MAGIC, "teemo_poison")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Toxic Dart")
        return True

    def _cast_tristana(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                       ability_vars: Dict) -> bool:
        """Tristana - Buster Shot: Heavy AD+AP damage, knockback + stun."""
        from .combat_engine import DamageType

        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 250)
        ap_damage = self._get_var(ability_vars, 'APDamage', unit.star_level, 30)
        stun_dur = self._get_var(ability_vars, 'StunDuration', unit.star_level, 0.75)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        total = ad_damage + unit.stats.ad + ap_damage + unit.stats.ap
        self._deal_damage(unit, target, total, DamageType.PHYSICAL, "tristana_buster_shot")
        self._apply_stun(target, stun_dur, "tristana_knockback")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Buster Shot")
        return True

    def _cast_tryndamere(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                         ability_vars: Dict) -> bool:
        """Tryndamere - Undying Rage: Become unkillable, gain AD, DR, and armor ignore."""
        from .combat_engine import DamageType

        ad_bonus = self._get_var(ability_vars, 'ADDamage', unit.star_level, 110)
        duration = self._get_var(ability_vars, 'Duration', unit.star_level, 5.0)
        dr = self._get_var(ability_vars, 'DR', unit.star_level, 0.15)
        armor_ignore = self._get_var(ability_vars, 'ArmorIgnore', unit.star_level, 0.30)

        # Unkillable: set minimum HP
        unit._tryndamere_undying = True
        unit._tryndamere_min_hp = 1.0
        unit.stats.ad += ad_bonus
        unit.stats.damage_reduction = getattr(unit.stats, 'damage_reduction', 0) + dr

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Undying Rage",
                             ad_bonus=ad_bonus, dr=dr)
        return True

    def _cast_twistedfate(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                          ability_vars: Dict) -> bool:
        """Twisted Fate - Stacked Deck: Every 3rd attack fires a piercing card."""
        from .combat_engine import DamageType

        base_damage = self._get_var(ability_vars, 'BaseDamage', unit.star_level, 70)
        bonus_ap = self._get_var(ability_vars, 'BonusAPDamage', unit.star_level, 50)
        falloff = self._get_var(ability_vars, 'FalloffDamage', unit.star_level, 0.5)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        total = base_damage + bonus_ap + unit.stats.ap
        self._deal_damage(unit, target, total, DamageType.MAGIC, "tf_stacked_deck")

        # Pierce through to enemies behind
        behind = [e for e in enemies if e.is_alive and e.is_targetable and e != target]
        for enemy in behind[:2]:
            self._deal_damage(unit, enemy, total * falloff,
                             DamageType.MAGIC, "tf_stacked_deck_pierce")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Stacked Deck")
        return True

    def _cast_vi(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                 ability_vars: Dict) -> bool:
        """Vi - Relentless Force: Dash to target, shield self, knockup + damage."""
        from .combat_engine import DamageType

        shield = self._get_var(ability_vars, 'Shield', unit.star_level, 125)
        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 120)
        knockup = self._get_var(ability_vars, 'KnockupDuration', unit.star_level, 1.0)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        self.engine.apply_shield(unit, shield, "vi_shield")
        self._dash_to_position(unit, target.position)

        total = ad_damage + unit.stats.ad
        self._deal_damage(unit, target, total, DamageType.PHYSICAL, "vi_relentless_force")
        self._apply_stun(target, knockup, "vi_knockup")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Relentless Force")
        return True

    # =========================================================================
    # COST 3 CHAMPION ABILITIES
    # =========================================================================

    def _cast_ahri(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                   ability_vars: Dict) -> bool:
        """Ahri - Fox-Fire: Fire bolts at nearby enemies, dash away."""
        from .combat_engine import DamageType

        damage = self._get_var(ability_vars, 'Damage', unit.star_level, 82)
        num_bolts = int(self._get_var(ability_vars, 'NormalNumBolts', unit.star_level, 3))

        targets = [e for e in enemies if e.is_alive and e.is_targetable]
        if not targets:
            return False

        # Fire bolts at nearest enemies
        targets_sorted = sorted(targets,
                               key=lambda e: self.engine.hex_grid.hex_distance(unit.position, e.position)
                               if hasattr(self.engine, 'hex_grid') else 0)

        from .combat_engine import HexGrid
        targets_sorted = sorted(targets,
                               key=lambda e: HexGrid.hex_distance(unit.position, e.position))

        for i in range(min(num_bolts, len(targets_sorted))):
            self._deal_damage(unit, targets_sorted[i], damage + unit.stats.ap,
                             DamageType.MAGIC, "ahri_foxfire")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Fox-Fire",
                             bolts=num_bolts)
        return True

    def _cast_drmundo(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                      ability_vars: Dict) -> bool:
        """Dr. Mundo - Maximum Dosage: Heal over time + deal AD + %HP damage on hit."""
        from .combat_engine import DamageType

        duration = self._get_var(ability_vars, 'Duration', unit.star_level, 5.0)
        pct_hp_heal = self._get_var(ability_vars, 'PercentHealthHealingPerSecond', unit.star_level, 0.06)
        ap_heal = self._get_var(ability_vars, 'APHealPerSecond', unit.star_level, 60)
        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 60)
        pct_hp_damage = self._get_var(ability_vars, 'PercentMaximumHealthDamage', unit.star_level, 0.05)

        # Total healing over duration
        total_heal = (unit.stats.max_hp * pct_hp_heal + ap_heal) * duration
        self.engine.heal_unit(unit, total_heal, "mundo_maximum_dosage")

        # Bonus AD damage on hit (simplified: immediate burst)
        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if target:
            damage = ad_damage + unit.stats.ad + target.stats.max_hp * pct_hp_damage
            self._deal_damage(unit, target, damage, DamageType.PHYSICAL, "mundo_cleaver")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Maximum Dosage")
        return True

    def _cast_jinx(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                   ability_vars: Dict) -> bool:
        """Jinx - Switcheroo!: Fire many attacks that deal AD+AP per missile."""
        from .combat_engine import DamageType

        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 50)
        ap_damage = self._get_var(ability_vars, 'APDamage', unit.star_level, 4)
        num_attacks = int(self._get_var(ability_vars, 'NumAttacks', unit.star_level, 18))
        num_missiles = int(self._get_var(ability_vars, 'NumMissiles', unit.star_level, 3))

        targets = [e for e in enemies if e.is_alive and e.is_targetable]
        if not targets:
            return False

        per_missile = ad_damage + unit.stats.ad * 0.1 + ap_damage + unit.stats.ap * 0.1

        for _ in range(num_attacks):
            target = unit.target or random.choice(targets)
            if not target or not target.is_alive:
                targets = [e for e in enemies if e.is_alive and e.is_targetable]
                if not targets:
                    break
                target = random.choice(targets)

            # Each attack fires multiple missiles, spread across nearby enemies
            hit_targets = self._get_enemies_in_radius(target.position, 1, enemies)
            if not hit_targets:
                hit_targets = [target]
            for missile_target in hit_targets[:num_missiles]:
                self._deal_damage(unit, missile_target, per_missile,
                                 DamageType.PHYSICAL, "jinx_switcheroo")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Switcheroo!",
                             attacks=num_attacks)
        return True

    def _cast_kennen(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                     ability_vars: Dict) -> bool:
        """Kennen - Slicing Maelstrom: Shield self, AoE lightning bolts with stun."""
        from .combat_engine import DamageType

        shield = self._get_var(ability_vars, 'Shield', unit.star_level, 600)
        damage = self._get_var(ability_vars, 'Damage', unit.star_level, 120)
        num_bolts = int(self._get_var(ability_vars, 'NumBolts', unit.star_level, 6))
        stun_dur = self._get_var(ability_vars, 'StunDuration', unit.star_level, 1.5)
        max_stuns = int(self._get_var(ability_vars, 'MaxStuns', unit.star_level, 3))
        radius = int(self._get_var(ability_vars, 'HexRadius', unit.star_level, 2))

        self.engine.apply_shield(unit, shield, "kennen_maelstrom")

        targets = self._get_enemies_in_radius(unit.position, radius, enemies)
        stuns_applied = 0

        for i in range(min(num_bolts, max(1, len(targets)))):
            if not targets:
                break
            target = targets[i % len(targets)]
            if not target.is_alive:
                continue

            self._deal_damage(unit, target, damage + unit.stats.ap,
                             DamageType.MAGIC, "kennen_bolt")

            if stuns_applied < max_stuns:
                self._apply_stun(target, stun_dur, "kennen_stun")
                stuns_applied += 1

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Slicing Maelstrom",
                             bolts=num_bolts)
        return True

    def _cast_kobuko(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                     ability_vars: Dict) -> bool:
        """Kobuko - You & Me!: Heal self and ally, grant attack speed to ally."""
        heal_ally = self._get_var(ability_vars, 'AllyHealAP', unit.star_level, 80)
        self_heal = self._get_var(ability_vars, 'SelfHealAP', unit.star_level, 180)
        self_heal_hp_pct = self._get_var(ability_vars, 'SelfHealHealthPercent', unit.star_level, 0.12)
        ally_as = self._get_var(ability_vars, 'YuumiAS', unit.star_level, 25)
        as_duration = self._get_var(ability_vars, 'ASDuration', unit.star_level, 4.0)

        # Heal self
        total_self_heal = self_heal + unit.stats.ap + unit.stats.max_hp * self_heal_hp_pct
        self.engine.heal_unit(unit, total_self_heal, "kobuko_self_heal")

        # Find lowest HP ally and heal + buff
        valid_allies = [a for a in allies if a.is_alive and a != unit]
        if valid_allies:
            target = min(valid_allies, key=lambda a: a.stats.hp / max(a.stats.max_hp, 1))
            self.engine.heal_unit(target, heal_ally + unit.stats.ap, "kobuko_ally_heal")
            target.stats.attack_speed += ally_as / 100.0

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="You & Me!")
        return True

    def _cast_nautilus(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                      ability_vars: Dict) -> bool:
        """Nautilus - Titan's Wrath: Shield (AP + %HP), deal MR-scaled damage on hit."""
        from .combat_engine import DamageType

        ap_shield = self._get_var(ability_vars, 'APShield', unit.star_level, 375)
        pct_hp_shield = self._get_var(ability_vars, 'PercentHealthShield', unit.star_level, 0.10)
        mr_ratio = self._get_var(ability_vars, 'MRDamageRatio', unit.star_level, 0.9)

        shield_val = ap_shield + unit.stats.max_hp * pct_hp_shield
        self.engine.apply_shield(unit, shield_val, "nautilus_titans_wrath")

        # MR-scaled damage to current target
        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if target:
            damage = unit.stats.magic_resist * mr_ratio + unit.stats.ap
            self._deal_damage(unit, target, damage, DamageType.MAGIC, "nautilus_wrath")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Titan's Wrath")
        return True

    def _cast_sejuani(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                      ability_vars: Dict) -> bool:
        """Sejuani - Winter's Wrath: Shield self, AoE damage + stun in front."""
        from .combat_engine import DamageType

        shield = self._get_var(ability_vars, 'Shield', unit.star_level, 525)
        damage = self._get_var(ability_vars, 'Damage', unit.star_level, 70)
        stun_dur = self._get_var(ability_vars, 'StunDuration', unit.star_level, 1.0)

        self.engine.apply_shield(unit, shield, "sejuani_winters_wrath")

        # AoE damage in front
        hit = self._get_enemies_in_radius(unit.position, 2, enemies)
        for enemy in hit:
            self._deal_damage(unit, enemy, damage + unit.stats.ap,
                             DamageType.MAGIC, "sejuani_wrath")
            self._apply_stun(enemy, stun_dur, "sejuani_freeze")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Winter's Wrath",
                             targets_hit=len(hit))
        return True

    def _cast_zoe(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                  ability_vars: Dict) -> bool:
        """Zoe - Double Trouble Bubble: Hit 2 enemies with heavy damage + slow."""
        from .combat_engine import DamageType

        damage = self._get_var(ability_vars, 'Damage', unit.star_level, 330)
        num_targets = int(self._get_var(ability_vars, 'NumEnemies', unit.star_level, 2))
        slow_dur = self._get_var(ability_vars, 'SlowDuration', unit.star_level, 2.0)

        targets = [e for e in enemies if e.is_alive and e.is_targetable]
        if not targets:
            return False

        hit_targets = random.sample(targets, min(num_targets, len(targets)))
        for target in hit_targets:
            self._deal_damage(unit, target, damage + unit.stats.ap,
                             DamageType.MAGIC, "zoe_bubble")
            target.stats.attack_speed = max(0.2, target.stats.attack_speed * 0.6)

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Double Trouble Bubble",
                             targets_hit=len(hit_targets))
        return True

    # =========================================================================
    # COST 4 CHAMPION ABILITIES
    # =========================================================================

    def _cast_belveth(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                      ability_vars: Dict) -> bool:
        """Bel'Veth - Endless Banquet: Heavy damage + AS on takedown + true damage passive."""
        from .combat_engine import DamageType

        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 150)
        true_dmg_base = self._get_var(ability_vars, 'TrueDamageBase', unit.star_level, 15)
        true_dmg_stack = self._get_var(ability_vars, 'TrueDamagePerStack', unit.star_level, 3)
        as_on_transform = self._get_var(ability_vars, 'AttackSpeedOnTransform', unit.star_level, 0.33)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Track stacks
        if not hasattr(unit, '_belveth_stacks'):
            unit._belveth_stacks = 0

        total = ad_damage + unit.stats.ad
        self._deal_damage(unit, target, total, DamageType.PHYSICAL, "belveth_feast")

        # True damage passive
        true_damage = true_dmg_base + true_dmg_stack * unit._belveth_stacks
        self._deal_damage(unit, target, true_damage, DamageType.TRUE, "belveth_true")

        if not target.is_alive:
            unit._belveth_stacks += 1

        # Attack speed boost
        unit.stats.attack_speed += as_on_transform

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Endless Banquet",
                             stacks=unit._belveth_stacks)
        return True

    def _cast_braum(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                    ability_vars: Dict) -> bool:
        """Braum - Unbreakable Frost: Damage reduction buff + chill nearby enemies."""
        from .combat_engine import DamageType

        dr = self._get_var(ability_vars, 'DamageReduction', unit.star_level, 0.55)
        duration = self._get_var(ability_vars, 'Duration', unit.star_level, 4.0)
        ap_damage = self._get_var(ability_vars, 'APDamage', unit.star_level, 15)
        armor_damage = self._get_var(ability_vars, 'ArmorDamage', unit.star_level, 0.2)

        # Massive damage reduction
        unit.stats.damage_reduction = getattr(unit.stats, 'damage_reduction', 0) + dr

        # Damage nearby enemies
        hit = self._get_enemies_in_radius(unit.position, 2, enemies)
        for enemy in hit:
            damage = ap_damage + unit.stats.armor * armor_damage + unit.stats.ap
            self._deal_damage(unit, enemy, damage, DamageType.MAGIC, "braum_frost")
            enemy.stats.attack_speed = max(0.2, enemy.stats.attack_speed * 0.7)

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Unbreakable Frost",
                             dr=dr, targets_hit=len(hit))
        return True

    def _cast_fizz(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                   ability_vars: Dict) -> bool:
        """Fizz - Playful Trickster: Become untargetable, dash, deal damage + empowered attacks."""
        from .combat_engine import DamageType

        damage = self._get_var(ability_vars, 'Damage', unit.star_level, 75)
        on_hit_dmg = self._get_var(ability_vars, 'DamageOnHit', unit.star_level, 50)
        num_attacks = int(self._get_var(ability_vars, 'NumAttacks', unit.star_level, 4))
        as_boost = self._get_var(ability_vars, 'ASBoost', unit.star_level, 1.0)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Splash damage on landing
        self._dash_to_position(unit, target.position)
        hit = self._get_enemies_in_radius(target.position, 1, enemies)
        for enemy in hit:
            self._deal_damage(unit, enemy, damage + unit.stats.ap,
                             DamageType.MAGIC, "fizz_splash")

        # Empowered attacks (bonus on-hit + AS)
        unit.stats.attack_speed += as_boost
        unit.stats.ad += on_hit_dmg * 0.25  # Amortized over attacks

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Playful Trickster")
        return True

    def _cast_garen(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                    ability_vars: Dict) -> bool:
        """Garen - Judgment: Spin dealing AD damage, reduce armor/MR, heal self."""
        from .combat_engine import DamageType

        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 100)
        spin_dur = self._get_var(ability_vars, 'SpinDuration', unit.star_level, 3.0)
        durability = self._get_var(ability_vars, 'Durability', unit.star_level, 0.5)
        armor_mr_red = self._get_var(ability_vars, 'ArmorMRReduction', unit.star_level, 5)
        ap_heal = self._get_var(ability_vars, 'APHeal', unit.star_level, 250)
        pct_hp_heal = self._get_var(ability_vars, 'PercentHealthHeal', unit.star_level, 0.1)

        # Damage reduction during spin
        unit.stats.damage_reduction = getattr(unit.stats, 'damage_reduction', 0) + durability

        # AoE spin damage
        hit = self._get_enemies_in_radius(unit.position, 1, enemies)
        total_damage = ad_damage + unit.stats.ad
        for enemy in hit:
            self._deal_damage(unit, enemy, total_damage, DamageType.PHYSICAL, "garen_spin")
            enemy.stats.armor = max(0, enemy.stats.armor - armor_mr_red)
            enemy.stats.magic_resist = max(0, enemy.stats.magic_resist - armor_mr_red)

        # Heal
        heal = ap_heal + unit.stats.ap + unit.stats.max_hp * pct_hp_heal
        self.engine.heal_unit(unit, heal, "garen_judgment_heal")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Judgment",
                             targets_hit=len(hit))
        return True

    def _cast_kaisa(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                    ability_vars: Dict) -> bool:
        """Kai'Sa - Icathian Rain: Fire missiles split across targets, 60% on current."""
        from .combat_engine import DamageType

        num_missiles = int(self._get_var(ability_vars, 'NumMissiles', unit.star_level, 15))
        ad_damage = self._get_var(ability_vars, 'ADDamage', unit.star_level, 39)
        ap_damage = self._get_var(ability_vars, 'APDamage', unit.star_level, 6)
        num_targets = int(self._get_var(ability_vars, 'NumTargets', unit.star_level, 4))
        primary_pct = self._get_var(ability_vars, 'PercentMissilesOnCurrentTarget', unit.star_level, 0.6)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        per_missile = ad_damage + ap_damage + unit.stats.ap * 0.1

        # 60% missiles on primary target
        primary_missiles = int(num_missiles * primary_pct)
        for _ in range(primary_missiles):
            if not target.is_alive:
                break
            self._deal_damage(unit, target, per_missile, DamageType.PHYSICAL, "kaisa_rain")

        # Remaining missiles spread to secondary targets
        remaining = num_missiles - primary_missiles
        others = [e for e in enemies if e.is_alive and e.is_targetable and e != target]
        secondary = others[:num_targets - 1] if others else []

        if secondary:
            per_secondary = remaining // len(secondary) if secondary else 0
            for sec_target in secondary:
                for _ in range(per_secondary):
                    if not sec_target.is_alive:
                        break
                    self._deal_damage(unit, sec_target, per_missile,
                                     DamageType.PHYSICAL, "kaisa_rain_secondary")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Icathian Rain",
                             missiles=num_missiles)
        return True

    def _cast_nasus(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                    ability_vars: Dict) -> bool:
        """Nasus - Fury of the Sands: Steal HP from enemies, gain resists."""
        from .combat_engine import DamageType

        health_steal = self._get_var(ability_vars, 'HealthSteal', unit.star_level, 485)
        duration = self._get_var(ability_vars, 'Duration', unit.star_level, 8)
        num_enemies = int(self._get_var(ability_vars, 'NumEnemies', unit.star_level, 4))
        resists = self._get_var(ability_vars, 'Resists', unit.star_level, 30)
        pct_hp_dps = self._get_var(ability_vars, 'PercentHealthDamagePerSecond', unit.star_level, 0.015)

        # Gain resists
        unit.stats.armor += resists
        unit.stats.magic_resist += resists

        # Drain HP from nearby enemies
        targets = sorted([e for e in enemies if e.is_alive and e.is_targetable],
                        key=lambda e: self.engine.hex_grid.hex_distance(unit.position, e.position)
                        if hasattr(self.engine, 'hex_grid') else 0)[:num_enemies]

        from .combat_engine import HexGrid
        targets = self._get_enemies_in_radius(unit.position, 3, enemies)[:num_enemies]

        total_drain = health_steal + pct_hp_dps * duration * unit.stats.max_hp
        per_target_drain = total_drain / max(1, len(targets)) if targets else 0

        for enemy in targets:
            self._deal_damage(unit, enemy, per_target_drain,
                             DamageType.MAGIC, "nasus_fury")

        self.engine.heal_unit(unit, total_drain * 0.5, "nasus_lifesteal")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Fury of the Sands",
                             targets=len(targets))
        return True

    # =========================================================================
    # COST 5 CHAMPION ABILITIES
    # =========================================================================

    def _cast_azir(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                   ability_vars: Dict) -> bool:
        """Azir - Arise!: Summon soldiers that deal magic damage on-hit."""
        from .combat_engine import DamageType

        base_damage = self._get_var(ability_vars, 'BaseMagicDamage', unit.star_level, 100)
        max_summons = int(self._get_var(ability_vars, 'MaxSummons', unit.star_level, 2))
        summon_damage = self._get_var(ability_vars, 'MaxSummonsDamage', unit.star_level, 70)

        # Track summon count
        if not hasattr(unit, '_azir_soldiers'):
            unit._azir_soldiers = 0

        unit._azir_soldiers = min(unit._azir_soldiers + 1, max_summons)

        # Soldiers deal damage to nearby enemies (simplified)
        targets = self._get_enemies_in_radius(unit.position, 3, enemies)
        for target in targets[:unit._azir_soldiers]:
            damage = base_damage + summon_damage + unit.stats.ap
            self._deal_damage(unit, target, damage, DamageType.MAGIC, "azir_soldier")

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Arise!",
                             soldiers=unit._azir_soldiers)
        return True

    def _cast_ornn(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                   ability_vars: Dict) -> bool:
        """Ornn - Call of the Forge: AoE damage + secondary damage + slow."""
        from .combat_engine import DamageType

        damage = self._get_var(ability_vars, 'Damage', unit.star_level, 100)
        secondary = self._get_var(ability_vars, 'SecondaryDamage', unit.star_level, 150)

        # AoE damage
        hit = self._get_enemies_in_radius(unit.position, 2, enemies)
        for enemy in hit:
            self._deal_damage(unit, enemy, damage + unit.stats.ap,
                             DamageType.MAGIC, "ornn_forge_primary")
            self._deal_damage(unit, enemy, secondary + unit.stats.ap,
                             DamageType.MAGIC, "ornn_forge_secondary")
            # Slow
            enemy.stats.attack_speed = max(0.2, enemy.stats.attack_speed * 0.7)

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="Call of the Forge",
                             targets_hit=len(hit))
        return True

    def _cast_volibear(self, unit: 'Unit', enemies: List['Unit'], allies: List['Unit'],
                       ability_vars: Dict) -> bool:
        """Volibear - The Relentless Storm: Bite damage (base + %HP), transform after 5 casts."""
        from .combat_engine import DamageType

        bite_base = self._get_var(ability_vars, 'BiteDamageBase', unit.star_level, 100)
        bite_hp_pct = self._get_var(ability_vars, 'BiteDamageHealth', unit.star_level, 0.03)
        casts_to_transform = int(self._get_var(ability_vars, 'CastsToTransform', unit.star_level, 5))
        bonus_hp = self._get_var(ability_vars, 'StormbringerBonusHealth', unit.star_level, 400)
        bonus_as = self._get_var(ability_vars, 'StormbringerAS', unit.star_level, 0.5)
        bolt_base = self._get_var(ability_vars, 'StormbringerBoltBase', unit.star_level, 50)
        bolt_hp_pct = self._get_var(ability_vars, 'StormbringerBoltHealth', unit.star_level, 0.04)

        if not hasattr(unit, '_voli_casts'):
            unit._voli_casts = 0
        unit._voli_casts += 1

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Bite damage
        damage = bite_base + unit.stats.ap + target.stats.max_hp * bite_hp_pct
        self._deal_damage(unit, target, damage, DamageType.MAGIC, "volibear_bite")

        # Transform at threshold
        if unit._voli_casts >= casts_to_transform and not getattr(unit, '_voli_transformed', False):
            unit._voli_transformed = True
            unit.stats.max_hp += bonus_hp
            unit.stats.hp += bonus_hp
            unit.stats.attack_speed += bonus_as

            # Lightning bolt AoE
            hit = self._get_enemies_in_radius(unit.position, 3, enemies)
            for enemy in hit:
                bolt_dmg = bolt_base + unit.stats.ap + enemy.stats.max_hp * bolt_hp_pct
                self._deal_damage(unit, enemy, bolt_dmg, DamageType.MAGIC, "volibear_bolt")

            self.engine.log_event('volibear_transform', unit=unit.name,
                                 bonus_hp=bonus_hp, bonus_as=bonus_as)

        unit.stats.mana = 0
        self.engine.log_event('ability_cast', unit=unit.name, ability="The Relentless Storm",
                             casts=unit._voli_casts)
        return True

    # -------------------------------------------------------------------------
    # HERO AUGMENT TICK DISPATCHER
    # -------------------------------------------------------------------------

    def process_hero_augment_ticks(self, units: List['Unit'], enemies: List['Unit'],
                                    allies: List['Unit'], dt: float):
        """Process all hero augment tick effects for active units.

        Called each combat tick by the engine.
        """
        for unit in units:
            if not unit.is_alive:
                continue

            hero_augment = getattr(unit, '_hero_augment', None)
            if not hero_augment:
                continue

            if hero_augment == 'TFT16_Augment_XinZhaoCarry':
                self.xinzhao_hero_tick(unit, enemies, dt)
            elif hero_augment == 'TFT16_Augment_RumbleCarry':
                self.rumble_hero_tick(unit, enemies, dt)
            elif hero_augment == 'TFT16_Augment_ShadowIsles_RuinedKing':
                self.viego_hero_augment_check(unit, allies)

            # Check Illaoi recast
            if unit.api_name == 'TFT16_Illaoi':
                ability_vars = self.engine.get_ability_vars(unit)
                self.check_illaoi_recast(unit, enemies, allies, ability_vars)
