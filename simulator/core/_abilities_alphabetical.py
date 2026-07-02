"""Alphabetical mixin: main champion ability handlers (aatrox through shyvana)."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Dict, List

from ._combat_types import DamageType
from ._hex_grid import HexGrid

if TYPE_CHECKING:
    from ._combat_types import Unit


class _AbilitiesAlphabeticalMixin:
    """Mixin providing main alphabetical champion ability handlers."""

    def _cast_aatrox(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Aatrox - The Darkin Blade: 3-hit combo with execute on 3rd hit."""

        # Track cast count for combo
        if not hasattr(unit, "_aatrox_combo"):
            unit._aatrox_combo = 0

        unit._aatrox_combo += 1
        combo_hit = unit._aatrox_combo

        # Get damage values
        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 95)

        # Apply damage multipliers for 2nd and 3rd hits
        if combo_hit == 2:
            multiplier = self._get_var(
                ability_vars, "SecondCastPercentDamage", unit.star_level, 1.2
            )
            ad_damage *= multiplier
            # Stun on 2nd cast
            stun_duration = self._get_var(
                ability_vars, "SecondCastStunDuration", unit.star_level, 1.0
            )
            if unit.target and unit.target.is_alive:
                self._apply_stun(unit.target, stun_duration, "aatrox_stun")
        elif combo_hit >= 3:
            multiplier = self._get_var(ability_vars, "ThirdCastPercentDamage", unit.star_level, 1.6)
            ad_damage *= multiplier
            unit._aatrox_combo = 0  # Reset combo

            # Execute mechanic on 3rd hit
            execute_threshold = self._get_var(
                ability_vars, "ThirdCastExecute", unit.star_level, 0.15
            )
            if unit.target and unit.target.is_alive:
                if unit.target.stats.hp / unit.target.stats.max_hp <= execute_threshold:
                    # Execute!
                    self.engine.apply_damage(
                        unit,
                        unit.target,
                        unit.target.stats.hp + 1,
                        DamageType.TRUE,
                        "aatrox_execute",
                    )
                    self.engine.log_event(
                        "execute",
                        unit=unit.name,
                        target=unit.target.name,
                        threshold=execute_threshold,
                    )
                    unit.stats.mana = 0
                    return True

        # Normal damage
        if unit.target and unit.target.is_alive:
            self._deal_damage(
                unit,
                unit.target,
                ad_damage + unit.stats.ad,
                DamageType.PHYSICAL,
                f"aatrox_hit{combo_hit}",
            )

        # World Ender: Brief untargetable + AD from omnivamp
        # Patch 16.4: conversion 100% → 150%
        if combo_hit == 1 and unit.stats.omnivamp > 0:
            bonus_ad = unit.stats.omnivamp * 150  # Convert to AD bonus (150% per 16.4)
            unit.stats.ad += bonus_ad
            unit.is_targetable = False
            unit.untargetable_duration = 0.5
            self.engine.log_event("world_ender", unit=unit.name, bonus_ad=bonus_ad)

        unit.stats.mana = 0
        return True

    def _cast_atakhan(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Atakhan - Punish the Unworthy: Cleave + scaling Noxus effects.

        Atakhan is summoned by the Noxus trait. His abilities scale with
        Noxus breakpoints and star level:
          1-star: 30% omnivamp, cleave every 2 attacks (150% AP)
          2-star: + 3% damage amp to Noxians, cleave (225% AP)
          3-star: + DOT ability (750 AP over 2.5s in 3 hex radius)
          4-star: 100% omnivamp, cleave (500% AP), DOT over 30s,
                  after 10s BRING RUIN (handled in combat_engine)
        """

        noxus_count = getattr(unit, "_atakhan_noxus_count", 3)
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
                if "Noxus" in ally.traits and ally.is_alive:
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
                    self._deal_damage(
                        unit, target, per_target, DamageType.MAGIC, "atakhan_soul_drain"
                    )

        unit.stats.mana = 0
        return True

    def _cast_ambessa(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Ambessa - Lacerate: Dash + damage with kill reset."""

        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 45)
        slam_mult = self._get_var(ability_vars, "SlamDamageMultiplier", unit.star_level, 3.15)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Dash to target
        self._dash_to_position(unit, target.position)

        # Deal slam damage
        total_damage = (ad_damage + unit.stats.ad) * slam_mult
        actual, excess = self._deal_damage(
            unit, target, total_damage, DamageType.PHYSICAL, "ambessa_slam"
        )

        # Kill reset - if target died, reset mana for another cast
        # Patch 16.4: reset 100% → 80%
        unit.stats.mana = 0
        if not target.is_alive:
            # Refund after spending mana so Invoker scaling applies consistently.
            self.engine.gain_mana(unit, unit.stats.max_mana * 0.80, source="ambessa_kill_refund")
            self.engine.log_event("ambessa_reset", unit=unit.name)

        return True

    def _cast_aphelios(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Aphelios - Incendiary Onslaught: Dual weapons, Infernum hits 3 targets."""

        num_targets = int(self._get_var(ability_vars, "NumTargets", unit.star_level, 3))
        num_attacks = int(self._get_var(ability_vars, "NumAttacks", unit.star_level, 8))
        attack_speed = self._get_var(ability_vars, "AttackSpeed", unit.star_level, 2.0)
        severum_damage = self._get_var(ability_vars, "SeverumADDamage", unit.star_level, 70)
        omnivamp = self._get_var(ability_vars, "Omnivamp", unit.star_level, 0.1)

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
                actual, _ = self._deal_damage(
                    unit, target, damage, DamageType.PHYSICAL, "aphelios_infernum"
                )
                # Omnivamp healing
                heal = actual * omnivamp
                self.engine.heal_unit(unit, heal, "aphelios_omnivamp")

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability="Incendiary Onslaught",
            targets=[t.name for t in targets],
        )
        return True

    def _cast_aurelionsol(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Aurelion Sol - The Skies Descend: Upgradable via stardust thresholds."""

        # Track stardust accumulation
        if not hasattr(unit, "_stardust"):
            unit._stardust = 0

        # Get damage based on stardust threshold
        base_damage = self._get_var(ability_vars, "Damage", unit.star_level, 480)

        # Check thresholds for upgrades
        thresholds = []
        for i in range(1, 9):
            thresh = self._get_var(ability_vars, f"StardustThreshold{i}", unit.star_level, i * 200)
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
                actual, _ = self._deal_damage(
                    unit, enemy, damage + unit.stats.ap, DamageType.MAGIC, "aurelion_stars"
                )
                # Accumulate stardust from damage dealt
                unit._stardust += actual * 0.1

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability="The Skies Descend",
            stardust=unit._stardust,
            upgrade_level=upgrade_level,
        )
        return True

    def _cast_caitlyn(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Caitlyn - Ace in the Hole: Excess damage overflows to next target."""

        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 475)
        ap_damage = self._get_var(ability_vars, "APDamage", unit.star_level, 40)

        total_damage = ad_damage + unit.stats.ad + ap_damage + unit.stats.ap

        # Get sorted targets by distance
        targets = sorted(
            [e for e in enemies if e.is_alive and e.is_targetable], key=lambda e: -e.stats.hp
        )  # Target lowest HP first for execute feel

        remaining_damage = total_damage
        targets_hit = []

        for target in targets:
            if remaining_damage <= 0:
                break

            actual, excess = self._deal_damage(
                unit, target, remaining_damage, DamageType.PHYSICAL, "caitlyn_ace"
            )
            targets_hit.append(target.name)
            remaining_damage = excess  # Carry over excess

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability="Ace in the Hole",
            targets=targets_hit,
            excess_used=total_damage - remaining_damage > ad_damage,
        )
        return True

    def _cast_darius(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Darius - Decimate: Bleed stacking with execute threshold."""

        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 90)
        heal_amount = self._get_var(ability_vars, "APHealing", unit.star_level, 180)
        # Patch 16.4: bleed DPS 15/25/40→12/18/30, duration 4s→5s
        bleed_dps = self._get_var(ability_vars, "PhysicalDamagePerSecond", unit.star_level, 12)
        execute_per_stack = self._get_var(
            ability_vars, "ExecutePercentPerHemorrhage", unit.star_level, 0.08
        )
        bleed_duration = self._get_var(ability_vars, "BleedDuration", unit.star_level, 5.0)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Track bleed stacks on target
        if not hasattr(target, "_darius_bleed"):
            target._darius_bleed = 0
        target._darius_bleed = min(5, target._darius_bleed + 1)

        # Apply bleed damage (total = dps * duration)
        bleed_total = bleed_dps * bleed_duration
        self.engine.apply_damage(unit, target, bleed_total, DamageType.TRUE, "darius_bleed")

        # Check execute threshold
        execute_threshold = execute_per_stack * target._darius_bleed
        if target.stats.hp / target.stats.max_hp <= execute_threshold:
            self.engine.apply_damage(
                unit, target, target.stats.hp + 1, DamageType.TRUE, "darius_execute"
            )
            self.engine.log_event(
                "execute", unit=unit.name, target=target.name, stacks=target._darius_bleed
            )
        else:
            # Normal damage
            self._deal_damage(
                unit, target, ad_damage + unit.stats.ad, DamageType.PHYSICAL, "darius_decimate"
            )

        # Heal
        self.engine.heal_unit(unit, heal_amount + unit.stats.ap, "darius_heal")

        unit.stats.mana = 0
        return True

    def _cast_draven(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Draven - Spinning Axes: Axe cycling with gold on takedown."""

        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 120)
        gold_amount = int(self._get_var(ability_vars, "GoldAmount", unit.star_level, 1))

        # Track axes
        if not hasattr(unit, "_draven_axes"):
            unit._draven_axes = 2  # Start with 2 axes

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Throw axes (damage per axe)
        for i in range(unit._draven_axes):
            if not target.is_alive:
                break
            actual, _ = self._deal_damage(
                unit, target, ad_damage + unit.stats.ad, DamageType.PHYSICAL, f"draven_axe_{i + 1}"
            )

            # Gold on takedown
            if not target.is_alive:
                if not hasattr(unit, "_draven_gold"):
                    unit._draven_gold = 0
                unit._draven_gold += gold_amount
                self.engine.log_event(
                    "draven_gold", unit=unit.name, gold=gold_amount, total=unit._draven_gold
                )

        unit.stats.mana = 0
        return True

    def _cast_lissandra(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Lissandra - Frozen Tomb: Stun with excess damage to nearby enemies."""

        target_damage = self._get_var(
            ability_vars, "TargetDamage", unit.star_level, 315
        )  # 16.4: 275→315
        secondary_damage = self._get_var(ability_vars, "SecondaryDamage", unit.star_level, 415)
        stun_duration = self._get_var(ability_vars, "StunDuration", unit.star_level, 1.0)
        num_overkill = int(self._get_var(ability_vars, "NumOverkillEnemies", unit.star_level, 2))
        chill_amp = self._get_var(ability_vars, "DamageAmpChilledTargets", unit.star_level, 0.12)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Stun primary target
        self._apply_stun(target, stun_duration, "lissandra_tomb")

        # Deal damage to primary target
        actual, excess = self._deal_damage(
            unit, target, target_damage + unit.stats.ap, DamageType.MAGIC, "lissandra_tomb"
        )

        # Excess damage overflows to nearby enemies
        if excess > 0:
            nearby = self._get_enemies_in_radius(target.position, 2, enemies)
            nearby = [e for e in nearby if e != target and e.is_alive][:num_overkill]

            for secondary in nearby:
                overflow_damage = min(excess, secondary_damage + unit.stats.ap)
                self._deal_damage(
                    unit, secondary, overflow_damage, DamageType.MAGIC, "lissandra_overflow"
                )
                excess -= overflow_damage
                if excess <= 0:
                    break

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast", unit=unit.name, ability="Frozen Tomb", excess_used=excess > 0
        )
        return True

    def _cast_lux(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Lux - Final Spark: Line laser toward target, width ~200 game units.

        The laser fires in a LINE toward Lux's target (not board-wide).
        Width of 200 game units translates to hitting enemies in the same hex
        column as the beam travels, or very slightly adjacent.
        """

        primary_damage = self._get_var(ability_vars, "PrimaryDamage", unit.star_level, 330)
        secondary_damage = self._get_var(ability_vars, "SecondaryDamage", unit.star_level, 90)
        q_damage = self._get_var(ability_vars, "QDamage", unit.star_level, 30)
        stun_duration = self._get_var(ability_vars, "StunDuration", unit.star_level, 1.0)

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
                self._deal_damage(
                    unit, enemy, primary_damage + unit.stats.ap, DamageType.MAGIC, "lux_laser"
                )
                targets_hit.append(enemy.name)
            elif in_beam_path and row_diff == 1:
                # Edge of beam - reduced damage
                self._deal_damage(
                    unit,
                    enemy,
                    secondary_damage + unit.stats.ap,
                    DamageType.MAGIC,
                    "lux_laser_edge",
                )
                targets_hit.append(enemy.name)

        # Q hits closest 2 enemies with stun
        q_targets = sorted(
            [e for e in enemies if e.is_alive and e.is_targetable],
            key=lambda e: HexGrid.hex_distance(unit.position, e.position),
        )[:2]
        for q_target in q_targets:
            self._apply_stun(q_target, stun_duration, "lux_q")
            self._deal_damage(unit, q_target, q_damage + unit.stats.ap, DamageType.MAGIC, "lux_q")

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability="Final Spark",
            targets=targets_hit,
            direction="toward_target",
        )
        return True

    def _cast_malzahar(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Malzahar - Void Swarm: Summon untargetable voidlings."""

        num_minions = int(self._get_var(ability_vars, "NumMinions", unit.star_level, 2))
        num_attacks = int(self._get_var(ability_vars, "NumAttacks", unit.star_level, 8))
        damage_per_attack = self._get_var(ability_vars, "Damage", unit.star_level, 29)

        # Simulate voidling attacks (they're untargetable so we just deal damage over time)
        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        total_damage = damage_per_attack * num_attacks * num_minions

        # Deal damage over multiple hits
        for _i in range(num_minions * num_attacks):
            if not target.is_alive:
                target = self._find_nearest_enemy(unit, enemies)
                if not target:
                    break
            self._deal_damage(
                unit,
                target,
                damage_per_attack + unit.stats.ap * 0.1,
                DamageType.MAGIC,
                "voidling_attack",
            )

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability="Void Swarm",
            minions=num_minions,
            attacks=num_attacks,
        )
        return True

    def _cast_renekton(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Renekton - Slice and Dice: Dash through enemies with multi-slash."""

        dash_damage = self._get_var(ability_vars, "DashADDamage", unit.star_level, 80)
        slash_damage = self._get_var(ability_vars, "SlashADDamage", unit.star_level, 50)
        dash_range = int(self._get_var(ability_vars, "DashRange", unit.star_level, 2))

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Dash to target
        old_pos = unit.position
        self._dash_to_position(unit, target.position)

        # Damage enemies along the dash path
        path_enemies = [
            e
            for e in enemies
            if e.is_alive
            and e.is_targetable
            and HexGrid.hex_distance(old_pos, e.position) <= dash_range
        ]

        for enemy in path_enemies:
            self._deal_damage(
                unit, enemy, dash_damage + unit.stats.ad, DamageType.PHYSICAL, "renekton_dash"
            )

        # Slash damage to nearby enemies
        nearby = self._get_enemies_in_radius(unit.position, 1, enemies)
        for enemy in nearby:
            self._deal_damage(
                unit, enemy, slash_damage + unit.stats.ad, DamageType.PHYSICAL, "renekton_slash"
            )

        unit.stats.mana = 0
        return True

    def _cast_seraphine(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Seraphine - Grand Encore: Crystal accumulation to super-cast."""

        damage_per_crystal = self._get_var(ability_vars, "DamagePerCrystal", unit.star_level, 35)
        cast_breakpoint = int(self._get_var(ability_vars, "CastBreakpoint", unit.star_level, 12))
        big_cast_damage = self._get_var(ability_vars, "BigCastDamage", unit.star_level, 270)
        big_cast_heal = self._get_var(ability_vars, "BigCastHeal", unit.star_level, 40)
        crystals_per_cast = int(self._get_var(ability_vars, "CrystalsPerCast", unit.star_level, 3))
        falloff = self._get_var(ability_vars, "BigCastDamageFalloff", unit.star_level, 0.3)

        # Track casts for big cast
        if not hasattr(unit, "_seraphine_casts"):
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
                    self._deal_damage(
                        unit, enemy, damage + unit.stats.ap, DamageType.MAGIC, "seraphine_big_cast"
                    )
                    targets_hit.append(enemy.name)

            # Heal allies
            for ally in allies:
                if ally.is_alive:
                    self.engine.heal_unit(
                        ally, big_cast_heal + unit.stats.ap * 0.5, "seraphine_heal"
                    )

            self.engine.log_event("seraphine_big_cast", unit=unit.name, targets=targets_hit)
        else:
            # Normal cast - crystal damage
            crystals = crystals_per_cast
            targets = sorted(
                [e for e in enemies if e.is_alive and e.is_targetable], key=lambda e: e.stats.hp
            )[:2]

            for target in targets:
                damage = damage_per_crystal * crystals
                self._deal_damage(
                    unit, target, damage + unit.stats.ap, DamageType.MAGIC, "seraphine_crystal"
                )

        unit.stats.mana = 0
        return True

    def _cast_swain(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Swain - Nevermove: AoE stun with passive drain."""

        passive_damage = self._get_var(ability_vars, "PassiveDamage", unit.star_level, 20)
        stun_duration = self._get_var(ability_vars, "StunDuration", unit.star_level, 1.5)
        heal_percent = self._get_var(
            ability_vars, "PercentMaximumHealthHealing", unit.star_level, 0.015
        )

        # AoE stun
        nearby = self._get_enemies_in_radius(unit.position, 2, enemies)

        for enemy in nearby:
            # Stun
            self._apply_stun(enemy, stun_duration, "swain_nevermove")
            # Damage
            self._deal_damage(
                unit, enemy, passive_damage + unit.stats.ap, DamageType.MAGIC, "swain_aoe"
            )

        # Self heal
        heal = unit.stats.max_hp * heal_percent
        self.engine.heal_unit(unit, heal, "swain_drain")

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast", unit=unit.name, ability="Nevermove", targets=[e.name for e in nearby]
        )
        return True

    def _cast_vayne(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Vayne - Tumble: Dash + Silver Bolts true damage."""

        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 100)
        dash_range = int(self._get_var(ability_vars, "HexDashRange", unit.star_level, 3))

        # Track silver bolts stacks
        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        if not hasattr(target, "_vayne_bolts"):
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
                dist = min(HexGrid.hex_distance(pos, e.position) for e in enemies if e.is_alive)
                if dist > best_dist and HexGrid.hex_distance(old_pos, pos) <= dash_range:
                    best_dist = dist
                    best_hex = pos

        if best_hex:
            self.engine.set_unit_position(unit, best_hex)
            self.engine.log_event("vayne_tumble", unit=unit.name, from_pos=old_pos, to_pos=best_hex)

        # Deal damage
        self._deal_damage(
            unit, target, ad_damage + unit.stats.ad, DamageType.PHYSICAL, "vayne_tumble"
        )

        # Silver Bolts proc on 3rd hit
        if target._vayne_bolts >= 3:
            target._vayne_bolts = 0
            true_damage = target.stats.max_hp * 0.14  # 14% max HP true damage
            self.engine.apply_damage(
                unit, target, true_damage, DamageType.TRUE, "vayne_silver_bolts"
            )
            self.engine.log_event(
                "silver_bolts", unit=unit.name, target=target.name, damage=true_damage
            )

        unit.stats.mana = 0
        return True

    def _cast_veigar(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Veigar - Dark Storm: Permanent AP stacking with innate AP scaling."""

        damage = self._get_var(ability_vars, "Damage", unit.star_level, 62)
        num_meteors = int(self._get_var(ability_vars, "NumMeteors", unit.star_level, 12))
        ap_per_kill = self._get_var(ability_vars, "APPerKill", unit.star_level, 1)
        percent_on_primary = self._get_var(
            ability_vars, "PercentOnPrimaryTarget", unit.star_level, 0.7
        )
        increased_ap_ratio = self._get_var(ability_vars, "IncreasedAPRatio", unit.star_level, 0.5)

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
            self.engine.log_event(
                "veigar_ap_stack",
                unit=unit.name,
                kills=kills,
                ap_gain=ap_gain,
                total_ap=unit.stats.ap,
            )

        unit.stats.mana = 0
        return True

    def _cast_wukong(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Wukong - Diverting Trickster: Summon clone."""

        clone_hp_pct = self._get_var(ability_vars, "SummonMaxHealthPercent", unit.star_level, 0.4)
        clone_flat_hp = self._get_var(ability_vars, "SummonFlatHealth", unit.star_level, 150)
        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 100)
        resists = self._get_var(ability_vars, "Resists", unit.star_level, 100)
        duration = self._get_var(ability_vars, "Duration", unit.star_level, 4)

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
            self._deal_damage(
                unit, target, ad_damage + unit.stats.ad, DamageType.PHYSICAL, "wukong_strike"
            )

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast", unit=unit.name, ability="Diverting Trickster", clone_hp=clone_hp
        )
        return True

    def _cast_yasuo(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Yasuo - Sweeping Blade: Dash with Yone synergy."""

        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 85)
        yasuo_ad_pct = self._get_var(ability_vars, "YasuoADPercent", unit.star_level, 1.0)
        brother_damage = self._get_var(
            ability_vars, "AttributeBrothersDamageToYasuo", unit.star_level, 1.0
        )

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Check for Yone synergy
        yone_present = any(
            u.api_name == "TFT16_Yone" and u.is_alive
            for u in self.engine.units
            if u.team == unit.team
        )

        damage = ad_damage + unit.stats.ad * yasuo_ad_pct
        if yone_present:
            damage *= 1 + brother_damage
            self.engine.log_event("yasuo_yone_synergy", unit=unit.name, bonus_mult=brother_damage)

        # Dash to target
        self._dash_to_position(unit, target.position)

        # Deal damage
        self._deal_damage(unit, target, damage, DamageType.PHYSICAL, "yasuo_sweep")

        unit.stats.mana = 0
        return True

    def _cast_yone(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Yone - Kin of the Stained Blade: Yasuo synergy with dual scaling."""

        ad_damage = self._get_var(ability_vars, "StrikeADDamage", unit.star_level, 160)
        ap_damage = self._get_var(ability_vars, "StrikeAPDamage", unit.star_level, 160)
        knockup_duration = self._get_var(ability_vars, "KnockupDuration", unit.star_level, 1.5)
        yasuo_mult = self._get_var(ability_vars, "YasuoADPercent", unit.star_level, 2.5)
        dash_range = self._get_var(ability_vars, "DashHexRange", unit.star_level, 2.5)

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
            self.engine.log_event("yone_yasuo_synergy", unit=unit.name, yasuo=yasuo.name)

        # Dash and damage
        self._dash_to_position(unit, target.position)

        # Dual damage type
        self._deal_damage(unit, target, total_ad, DamageType.PHYSICAL, "yone_strike_ad")
        self._deal_damage(unit, target, total_ap, DamageType.MAGIC, "yone_strike_ap")

        # Knockup (stun)
        self._apply_stun(target, knockup_duration, "yone_knockup")

        unit.stats.mana = 0
        return True

    def _cast_yunara(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Yunara - Transcendent State: Infinite range + piercing attacks."""

        buff_duration = self._get_var(ability_vars, "BuffDuration", unit.star_level, 4)
        attack_speed = self._get_var(ability_vars, "AttackSpeed", unit.star_level, 0.75)
        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 80)
        bonus_crit = self._get_var(ability_vars, "BonusCritDamage", unit.star_level, 0.33)
        damage_reduction = self._get_var(
            ability_vars, "DamageReductionPerEnemyHit", unit.star_level, 0.75
        )

        # Grant infinite range temporarily
        old_range = unit.stats.range
        unit.stats.range = 99  # Infinite range

        # Grant attack speed
        unit.stats.attack_speed += attack_speed

        # Grant crit damage
        unit.stats.crit_multiplier += bonus_crit

        # Track buff expiration
        if not hasattr(unit, "_yunara_buff_end"):
            unit._yunara_buff_end = 0
        unit._yunara_buff_end = self.engine.time + buff_duration

        # Deal piercing damage to all enemies in a line
        unit_row = unit.position[0]
        enemies_hit = 0
        current_damage = ad_damage + unit.stats.ad

        # Sort enemies by column (left to right)
        line_enemies = sorted(
            [e for e in enemies if e.is_alive and e.is_targetable], key=lambda e: e.position[1]
        )

        for enemy in line_enemies:
            if enemies_hit > 0:
                current_damage *= damage_reduction  # Reduced damage per enemy hit
            self._deal_damage(unit, enemy, current_damage, DamageType.PHYSICAL, "yunara_pierce")
            enemies_hit += 1

        unit.stats.mana = 0
        self.engine.log_event(
            "yunara_transcendent", unit=unit.name, enemies_hit=enemies_hit, duration=buff_duration
        )
        return True

    def _cast_zaahen(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Zaahen - Divine Challenge: AoE damage with execute after 22 casts."""

        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 90)
        ap_damage = self._get_var(ability_vars, "APDamage", unit.star_level, 20)
        aoe_mult = self._get_var(ability_vars, "AOEDamageMultiplier", unit.star_level, 0.4)
        casts_to_ult = int(self._get_var(ability_vars, "CastsToUlt", unit.star_level, 22))
        big_aoe_mult = self._get_var(ability_vars, "BigAOEDamageMultiplier", unit.star_level, 2.0)

        # Track casts
        if not hasattr(unit, "_zaahen_casts"):
            unit._zaahen_casts = 0
        unit._zaahen_casts += 1

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Check for ultimate (Divine Challenge instant kill)
        if unit._zaahen_casts >= casts_to_ult:
            unit._zaahen_casts = 0

            # Execute primary target
            self.engine.apply_damage(
                unit, target, target.stats.hp + 1, DamageType.TRUE, "zaahen_execute"
            )
            self.engine.log_event("zaahen_divine_challenge", unit=unit.name, target=target.name)

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

    def _cast_annie(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Annie - Enraged Inferno: Board-wide AOE magic damage.

        First cast: Deals massive AOE damage to all enemies.
        Subsequent casts: Reduced mana cost (140 -> 20), deals single target damage.

        Note: Tibbers is a SEPARATE unit (TFT16_AnnieTibbers) that the player fields
        independently via the Dark Child trait. He has his own attacks and ability.
        """

        aoe_damage = self._get_var(ability_vars, "Damage", unit.star_level, 1500)
        single_target_damage = self._get_var(
            ability_vars, "SingleTargetDamage", unit.star_level, 240
        )
        mana_reduction = self._get_var(ability_vars, "ManaCostReduction", unit.star_level, 140)

        # Track if this is first cast (for mana cost reduction)
        if not hasattr(unit, "_annie_first_cast_done"):
            unit._annie_first_cast_done = False

        if not unit._annie_first_cast_done:
            # First cast: Board-wide AOE damage
            unit._annie_first_cast_done = True
            total_damage = 0
            for enemy in enemies:
                if enemy.is_alive and enemy.is_targetable:
                    damage = aoe_damage + unit.stats.ap
                    self._deal_damage(
                        unit, enemy, damage, DamageType.MAGIC, "annie_enraged_inferno"
                    )
                    total_damage += damage

            # Combat uses max_mana as cast threshold, so reduce that for later casts.
            unit.stats.max_mana = max(20, unit.stats.max_mana - mana_reduction)
            self.engine.log_event(
                "ability_cast",
                unit=unit.name,
                ability="Enraged Inferno",
                damage=total_damage,
                first_cast=True,
                new_mana_cost=unit.stats.max_mana,
            )
        else:
            # Subsequent casts: Single target damage (Annie continues attacking)
            target = unit.target or self._find_nearest_enemy(unit, enemies)
            if target:
                damage = single_target_damage + unit.stats.ap
                self._deal_damage(unit, target, damage, DamageType.MAGIC, "annie_inferno_blast")
                self.engine.log_event(
                    "ability_cast",
                    unit=unit.name,
                    ability="Enraged Inferno",
                    damage=damage,
                    target=target.name,
                )

        unit.stats.mana = 0
        return True

    def _cast_annietibbers(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Tibbers - Rage of Embers: Self-buff with shield, attack speed, and healing.

        Tibbers AUTOMATICALLY APPEARS on bench when you buy Annie (Dark Child trait).
        Cannot sell separately - selling Annie removes Tibbers.
        Can equip items and field independently. Has own mana pool and attacks.
        """
        shield_amount = self._get_var(ability_vars, "Shield", unit.star_level, 1000)
        attack_speed_buff = self._get_var(ability_vars, "AttackSpeed", unit.star_level, 2.0)
        heal_percent = self._get_var(ability_vars, "HealPercentHealth", unit.star_level, 0.025)
        duration = self._get_var(ability_vars, "Duration", unit.star_level, 4.0)

        # Apply shield
        self.engine.apply_shield(unit, shield_amount + unit.stats.ap * 0.5, "tibbers_rage_shield")

        # Apply attack speed buff
        if not hasattr(unit, "_tibbers_as_buff_active"):
            unit._tibbers_as_buff_active = False

        if not unit._tibbers_as_buff_active:
            unit._tibbers_as_buff_active = True
            unit._tibbers_original_as = unit.stats.attack_speed
            unit.stats.attack_speed += attack_speed_buff
            self.engine.log_event(
                "tibbers_rage_buff", unit=unit.name, as_buff=attack_speed_buff, duration=duration
            )

        # Heal based on max HP
        heal_amount = unit.stats.max_hp * heal_percent
        self.engine.heal_unit(unit, heal_amount, "tibbers_rage_heal")

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability="Rage of Embers",
            shield=shield_amount,
            heal=heal_amount,
            as_buff=attack_speed_buff,
        )
        return True

    def _cast_bard(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Bard - Traveler's Call: Meeps attack multiple enemies."""

        damage = self._get_var(ability_vars, "Damage", unit.star_level, 130)  # 16.4: 120→130
        num_missiles = int(self._get_var(ability_vars, "NumMissilesBase", unit.star_level, 6))
        pct_on_current = self._get_var(
            ability_vars, "PercentDamageOnCurrentTarget", unit.star_level, 0.75
        )
        search_radius = int(self._get_var(ability_vars, "EnemyHexSearchRadius", unit.star_level, 3))

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
            self._deal_damage(unit, target, damage + unit.stats.ap, DamageType.MAGIC, "bard_meep")

        # Spread remaining to nearby enemies
        nearby = self._get_enemies_in_radius(target.position, search_radius, enemies)
        nearby = [e for e in nearby if e != target and e.is_alive]

        missiles_remaining = other_missiles
        for enemy in nearby:
            if missiles_remaining <= 0:
                break
            self._deal_damage(unit, enemy, damage + unit.stats.ap, DamageType.MAGIC, "bard_meep")
            missiles_remaining -= 1

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast", unit=unit.name, ability="Traveler's Call", missiles=num_missiles
        )
        return True

    def _cast_diana(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Diana - Lunar Rush: Dash + shield + pull enemies."""

        shield_amount = self._get_var(ability_vars, "Shield", unit.star_level, 100)
        damage = self._get_var(ability_vars, "TargetDamage", unit.star_level, 125)
        hex_limit = int(self._get_var(ability_vars, "HexLimit", unit.star_level, 4))
        leona_ap = self._get_var(ability_vars, "DianaAP", unit.star_level, 3)

        # Check for Leona synergy
        has_leona = any(
            u.api_name == "TFT16_Leona" and u.is_alive
            for u in self.engine.units
            if u.team == unit.team
        )
        if has_leona:
            unit.stats.ap += leona_ap  # Bonus AP from Leona
            self.engine.log_event("diana_leona_synergy", unit=unit.name, bonus_ap=leona_ap)

        # Apply shield
        self.engine.apply_shield(unit, shield_amount + unit.stats.ap * 0.5, "diana_shield")

        # Dash to farthest enemy within range
        enemies_in_range = [
            e
            for e in enemies
            if e.is_alive
            and e.is_targetable
            and HexGrid.hex_distance(unit.position, e.position) <= hex_limit
        ]

        if enemies_in_range:
            target = max(
                enemies_in_range, key=lambda e: HexGrid.hex_distance(unit.position, e.position)
            )
            self._dash_to_position(unit, target.position)

            # Damage and pull nearby enemies together
            nearby = self._get_enemies_in_radius(target.position, 2, enemies)
            for enemy in nearby:
                self._deal_damage(
                    unit, enemy, damage + unit.stats.ap, DamageType.MAGIC, "diana_lunar_rush"
                )

        unit.stats.mana = 0
        return True

    def _cast_fiddlesticks(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Fiddlesticks - Crowstorm: AoE damage with fear + mana drain."""

        fear_duration = self._get_var(ability_vars, "FearDuration", unit.star_level, 1.25)
        mana_drain = self._get_var(ability_vars, "ManaLossPerSecond", unit.star_level, 22)
        dps = self._get_var(ability_vars, "DamagePerSecond", unit.star_level, 100)
        bonus_damage_pct = self._get_var(ability_vars, "NearestBonusDamage", unit.star_level, 0.33)
        aoe_radius = int(self._get_var(ability_vars, "AOERadius", unit.star_level, 2))

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
                total_damage *= 1 + bonus_damage_pct

            self._deal_damage(
                unit,
                enemy,
                total_damage + unit.stats.ap,
                DamageType.MAGIC,
                "fiddlesticks_crowstorm",
            )

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast", unit=unit.name, ability="Crowstorm", enemies_hit=len(nearby)
        )
        return True

    def _cast_gangplank(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Gangplank - Powder Kegs: Barrel chain explosion with armor shred."""

        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 190)
        num_barrels = int(self._get_var(ability_vars, "NumofBarrels", unit.star_level, 3))
        falloff = self._get_var(ability_vars, "FalloffDamage", unit.star_level, 0.25)
        armor_reduction = self._get_var(ability_vars, "ArmorReduction", unit.star_level, 10)

        # Place barrels on enemies (simplified)
        targets = sorted(
            [e for e in enemies if e.is_alive and e.is_targetable], key=lambda e: e.stats.hp
        )[:num_barrels]

        for i, target in enumerate(targets):
            # Falloff damage for each barrel in chain
            damage_mult = 1.0 - (falloff * i)
            final_damage = (ad_damage + unit.stats.ad) * damage_mult

            # Apply armor reduction
            target.stats.armor = max(0, target.stats.armor - armor_reduction)

            self._deal_damage(unit, target, final_damage, DamageType.PHYSICAL, "gangplank_barrel")

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast", unit=unit.name, ability="Powder Kegs", barrels=num_barrels
        )
        return True

    def _cast_kindred(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Kindred - Lamb's Respite: 2-hex radius zone with shield + double AS."""

        shield_amount = self._get_var(ability_vars, "ShieldAmount", unit.star_level, 350)
        duration = self._get_var(ability_vars, "Duration", unit.star_level, 2.5)
        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 25)
        heal_pct = self._get_var(ability_vars, "HealPercentage", unit.star_level, 0.08)
        extra_arrows = int(self._get_var(ability_vars, "NumExtraArrows", unit.star_level, 1))

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
            self._deal_damage(
                unit, target, ad_damage + unit.stats.ad, DamageType.PHYSICAL, "kindred_attack"
            )

            # Heal on attack
            heal = target.stats.max_hp * heal_pct
            self.engine.heal_unit(unit, heal, "kindred_heal")

            # Extra arrows to nearby enemies (within zone radius)
            nearby = self._get_enemies_in_radius(unit.position, zone_radius, enemies)
            nearby = [e for e in nearby if e != target and e.is_alive][:extra_arrows]
            for enemy in nearby:
                self._deal_damage(
                    unit, enemy, ad_damage * 0.5, DamageType.PHYSICAL, "kindred_arrow"
                )

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability="Lamb's Respite",
            zone_radius=zone_radius,
            allies_shielded=allies_in_zone,
        )
        return True

    def _cast_leblanc(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """LeBlanc - Distortions: Multi-target dash + stun."""

        num_targets = int(self._get_var(ability_vars, "NumTargets", unit.star_level, 3))
        damage = self._get_var(ability_vars, "Damage", unit.star_level, 300)
        secondary_damage = self._get_var(ability_vars, "SecondaryDamage", unit.star_level, 180)
        stun_duration = self._get_var(ability_vars, "StunDuration", unit.star_level, 1.0)
        search_radius = int(self._get_var(ability_vars, "NearbyEnemyHexRadius", unit.star_level, 3))

        # Get targets
        targets = sorted(
            [e for e in enemies if e.is_alive and e.is_targetable], key=lambda e: e.stats.hp
        )[:num_targets]

        for i, target in enumerate(targets):
            # Dash to target
            self._dash_to_position(unit, target.position)

            # Primary or secondary damage
            dmg = damage if i == 0 else secondary_damage
            self._deal_damage(
                unit, target, dmg + unit.stats.ap, DamageType.MAGIC, "leblanc_distortion"
            )

            # Stun
            self._apply_stun(target, stun_duration, "leblanc_stun")

        unit.stats.mana = 0
        return True

    def _cast_milio(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Milio - Ultra Mega Fire Kick: Bouncing fireball."""

        num_bounces = int(self._get_var(ability_vars, "NumBounces", unit.star_level, 3))
        damage = self._get_var(ability_vars, "MagicDamage", unit.star_level, 190)
        aoe_damage = self._get_var(ability_vars, "MagicDamageAOE", unit.star_level, 160)
        bounce_range = int(self._get_var(ability_vars, "BounceSearchRange", unit.star_level, 2))

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
            self._deal_damage(
                unit,
                current_target,
                damage + unit.stats.ap,
                DamageType.MAGIC,
                f"milio_bounce_{bounce + 1}",
            )

            # AoE damage to nearby
            nearby = self._get_enemies_in_radius(current_target.position, 1, enemies)
            for enemy in nearby:
                if enemy != current_target and enemy not in hit_enemies:
                    self._deal_damage(
                        unit,
                        enemy,
                        aoe_damage + unit.stats.ap * 0.5,
                        DamageType.MAGIC,
                        "milio_splash",
                    )

            # Find next bounce target
            next_targets = [
                e
                for e in self._get_enemies_in_radius(current_target.position, bounce_range, enemies)
                if e not in hit_enemies and e.is_alive
            ]
            current_target = next_targets[0] if next_targets else None

        unit.stats.mana = 0
        return True

    def _cast_missfortune(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Miss Fortune - Heartbreaker: Multi-wave AOE + ricochet autos passive."""

        ricochet_mult = self._get_var(ability_vars, "AutoRicochetMutliplier", unit.star_level, 0.5)
        base_waves = int(self._get_var(ability_vars, "BaseNumWaves", unit.star_level, 2))
        casts_per_wave = int(
            self._get_var(ability_vars, "NumCaststoGainExtraWave", unit.star_level, 3)
        )
        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 145)
        ap_damage = self._get_var(ability_vars, "APDamage", unit.star_level, 15)
        secondary_pct = self._get_var(
            ability_vars, "PercentDamageOfSecondaryWaves", unit.star_level, 0.5
        )

        # Track casts for extra waves
        if not hasattr(unit, "_mf_casts"):
            unit._mf_casts = 0
        unit._mf_casts += 1

        extra_waves = unit._mf_casts // casts_per_wave
        total_waves = base_waves + extra_waves

        # Enable ricochet passive
        if not getattr(unit, "_mf_ricochet_enabled", False):
            unit._mf_ricochet_enabled = True
            unit._mf_ricochet_mult = ricochet_mult
            self.engine.log_event("mf_ricochet_passive", unit=unit.name, mult=ricochet_mult)

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
                    self._deal_damage(
                        unit, enemy, wave_damage, DamageType.PHYSICAL, f"mf_wave_{wave + 1}"
                    )
                    targets_hit.add(enemy.name)

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability="Heartbreaker",
            waves=total_waves,
            targets=len(targets_hit),
            casts=unit._mf_casts,
        )
        return True

    def _cast_nidalee(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Nidalee - Javelin Toss / Takedown: Huntress execute with role-based damage."""

        target_damage = self._get_var(ability_vars, "TargetDamage", unit.star_level, 320)
        secondary_damage = self._get_var(ability_vars, "SecondaryDamage", unit.star_level, 100)
        tank_mult = self._get_var(ability_vars, "TankDamageMult", unit.star_level, 0.6)
        fighter_mult = self._get_var(ability_vars, "FighterDamageMult", unit.star_level, 0.3)
        reduction_per_cast = self._get_var(
            ability_vars, "DamageReductionPerCast", unit.star_level, 0.7
        )

        # Track casts for damage reduction
        if not hasattr(unit, "_nidalee_casts"):
            unit._nidalee_casts = 0
        unit._nidalee_casts += 1

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Calculate damage with role-based reduction
        damage = target_damage + unit.stats.ap

        if "Tank" in target.role:
            damage *= tank_mult
        elif "Fighter" in target.role:
            damage *= fighter_mult

        # Reduction per prior cast
        if unit._nidalee_casts > 1:
            damage *= reduction_per_cast ** (unit._nidalee_casts - 1)

        self._deal_damage(unit, target, damage, DamageType.MAGIC, "nidalee_javelin")

        # Secondary damage to nearby
        nearby = self._get_enemies_in_radius(target.position, 1, enemies)
        for enemy in nearby:
            if enemy != target:
                self._deal_damage(
                    unit,
                    enemy,
                    secondary_damage + unit.stats.ap * 0.3,
                    DamageType.MAGIC,
                    "nidalee_pounce",
                )

        unit.stats.mana = 0
        return True

    def _cast_singed(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Singed - Poison Trail: Walk through enemies, drawing aggro."""

        dps = self._get_var(ability_vars, "DamagePerSecond", unit.star_level, 8)
        armor_mr_reduction = self._get_var(ability_vars, "ArmorMR", unit.star_level, 20)
        heal_per_sec = self._get_var(ability_vars, "HealPerSecond", unit.star_level, 15)
        duration = self._get_var(ability_vars, "PoisonCloudDuration", unit.star_level, 4)

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
                self._deal_damage(
                    unit, enemy, total_damage + unit.stats.ap, DamageType.MAGIC, "singed_poison"
                )

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

    def _cast_thresh(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Thresh - The Box: Hook enemies, drain health based on team's Shadow Isles souls."""

        # Get soul count from centralized TraitManager
        soul_count = self.engine.trait_manager.get_shadow_isles_souls(unit.team)

        # Get damage variables
        health_drain_per_soul = self._get_var(
            ability_vars, "HealthDrainPerSoul", unit.star_level, 5
        )
        box_damage = self._get_var(ability_vars, "APPassiveDamage", unit.star_level, 50)

        # Hook nearest enemy
        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if target:
            # Pull target towards Thresh
            old_pos = target.position
            self._dash_to_position(target, unit.position)
            self.engine.log_event(
                "thresh_hook", unit=unit.name, target=target.name, from_pos=old_pos
            )

            # Box damage
            self._deal_damage(
                unit, target, box_damage + unit.stats.ap, DamageType.MAGIC, "thresh_box"
            )

            # Drain based on team's Shadow Isles souls
            if soul_count > 0:
                drain_damage = health_drain_per_soul * soul_count
                self._deal_damage(unit, target, drain_damage, DamageType.MAGIC, "thresh_soul_drain")
                self.engine.heal_unit(unit, drain_damage * 0.5, "thresh_soul_heal")

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability="The Box",
            souls=soul_count,
            drain=health_drain_per_soul * soul_count if soul_count > 0 else 0,
        )
        return True

    def _cast_warwick(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Warwick - Eternal Hunger: Single cast, self buff + ally AS buff."""

        # Track if already cast (single cast only)
        if hasattr(unit, "_warwick_cast"):
            return False

        unit._warwick_cast = True

        attack_speed = self._get_var(ability_vars, "AttackSpeed", unit.star_level, 1.0)
        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 45)
        omnivamp = self._get_var(ability_vars, "Omnivamp", unit.star_level, 0.15)
        ally_as = self._get_var(ability_vars, "AllyAttackSpeed", unit.star_level, 0.2)
        ally_duration = self._get_var(ability_vars, "AllyBuffDuration", unit.star_level, 3)

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

        self.engine.log_event(
            "warwick_eternal_hunger",
            unit=unit.name,
            self_as=attack_speed,
            self_ad=ad_damage,
            self_omnivamp=omnivamp,
            ally_as_buff=ally_as,
            ally_count=len(unit._warwick_buffed_allies),
        )

        unit.stats.mana = 0
        return True

    def _cast_loris(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Loris - Piltover Tussle: Dash + taunt + knockup."""

        shield_amount = self._get_var(ability_vars, "Shield", unit.star_level, 700)
        damage = self._get_var(ability_vars, "Damage", unit.star_level, 150)
        knockup_duration = self._get_var(ability_vars, "KnockupDuration", unit.star_level, 1.25)

        # Apply shield
        self.engine.apply_shield(unit, shield_amount, "loris_shield")

        # Dash to target
        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if target:
            self._dash_to_position(unit, target.position)

            # Knockup (stun) and damage
            self._apply_stun(target, knockup_duration, "loris_knockup")
            self._deal_damage(
                unit, target, damage + unit.stats.armor * 0.5, DamageType.PHYSICAL, "loris_slam"
            )

            # Taunt nearby enemies
            nearby = self._get_enemies_in_radius(unit.position, 2, enemies)
            for enemy in nearby:
                enemy.target = unit

        unit.stats.mana = 0
        return True

    def _cast_shyvana(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Shyvana - Dragon Transformation: Transform with bonus stats."""

        transform_hp = self._get_var(ability_vars, "TransformHP", unit.star_level, 600)
        transform_durability = self._get_var(
            ability_vars, "TransformDurability", unit.star_level, 0.2
        )
        divebomb_damage = self._get_var(ability_vars, "DivebombADDamage", unit.star_level, 100)
        fire_dps = self._get_var(ability_vars, "FireDamagePerSecond", unit.star_level, 185)
        duration = self._get_var(ability_vars, "SpellDuration", unit.star_level, 3)

        # Track dragon form
        if not hasattr(unit, "_shyvana_dragon"):
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
                self._deal_damage(
                    unit,
                    target,
                    divebomb_damage + unit.stats.ad,
                    DamageType.PHYSICAL,
                    "shyvana_divebomb",
                )

            self.engine.log_event("shyvana_transform", unit=unit.name, aura_allies=len(allies))
        else:
            # Dragon form fire breath
            nearby = self._get_enemies_in_radius(unit.position, 2, enemies)
            total_fire = fire_dps * duration
            for enemy in nearby:
                self._deal_damage(
                    unit, enemy, total_fire + unit.stats.ap, DamageType.MAGIC, "shyvana_fire"
                )

        unit.stats.mana = 0
        return True
