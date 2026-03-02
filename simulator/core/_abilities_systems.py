"""Systems mixin: named special systems + named passive abilities."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Dict, List

from ._combat_types import DamageType, UnitState
from ._hex_grid import HexGrid

if TYPE_CHECKING:
    from ._combat_types import Unit


class _AbilitiesSystemsMixin:
    """Mixin providing named special systems and passive abilities."""

    # =========================================================================
    # LUCIAN & SENNA - Soulbound Transition
    # =========================================================================

    def _cast_lucian(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Lucian - The Culling: Channel then swap to Senna.

        Soulbound mechanic: Lucian and Senna swap when either casts.
        While Lucian is out: Team gets 7% damage amp
        While Senna is out: Team gets 7% damage reduction
        """

        # Get ability variables
        duration = self._get_var(ability_vars, "Duration", unit.star_level, 3.0)
        ap_damage = self._get_var(ability_vars, "APDamage", unit.star_level, 12)
        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 120)
        num_shots = int(self._get_var(ability_vars, "NumShots", unit.star_level, 12))
        armor_reduction = self._get_var(ability_vars, "FlatArmorReduction", unit.star_level, 3)

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
            self._deal_damage(
                unit, target, damage_per_shot, DamageType.PHYSICAL, f"lucian_shot_{i + 1}"
            )

        # Swap to Senna after casting
        self._soulbound_swap(unit, allies, to_senna=True)

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast", unit=unit.name, ability="The Culling", shots=num_shots
        )
        return True

    def _cast_senna(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Senna - Dawning Shadow: Long-range beam then swap to Lucian.

        Note: Senna shares data with Lucian in combat_data.json.
        Using estimated values based on typical Senna mechanics.
        """

        # Senna's ability: Line damage + heal allies
        # Using similar scaling to Lucian
        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 120)
        ap_damage = self._get_var(ability_vars, "APDamage", unit.star_level, 12)

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
        self.engine.log_event(
            "ability_cast", unit=unit.name, ability="Dawning Shadow", targets=targets_hit
        )
        return True

    def _soulbound_swap(self, unit: "Unit", allies: List["Unit"], to_senna: bool):
        """Handle Soulbound swap between Lucian and Senna.

        - When swapping to Senna: Remove damage amp, add damage reduction
        - When swapping to Lucian: Remove damage reduction, add damage amp
        """
        damage_amp = 0.07  # 7% from Soulbound trait
        damage_reduction = 0.07

        # Track which form is active
        if not hasattr(unit, "_soulbound_is_senna"):
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

            self.engine.log_event(
                "soulbound_swap",
                from_unit="Lucian",
                to_unit="Senna",
                team_buff="7% Damage Reduction",
            )

        elif not to_senna and unit._soulbound_is_senna:
            # Swap to Lucian
            unit._soulbound_is_senna = False
            unit.name = "Lucian & Senna"
            unit.api_name = "TFT16_Lucian"

            # Update team buffs: Remove damage reduction, add damage amp
            for ally in allies:
                if ally.is_alive:
                    ally.stats.damage_reduction = max(
                        0, ally.stats.damage_reduction - damage_reduction
                    )
                    ally.stats.damage_amp += damage_amp

            self.engine.log_event(
                "soulbound_swap", from_unit="Senna", to_unit="Lucian", team_buff="7% Damage Amp"
            )

    # =========================================================================
    # RYZE - Trait-Dependent Ability
    # =========================================================================

    def _cast_ryze(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Ryze - Runic Overload: Ability effect changes based on active team traits.

        25+ trait interactions with different effects.
        """

        # Base damage
        base_damage = self._get_var(ability_vars, "Damage", unit.star_level, 425)
        split_damage_pct = self._get_var(ability_vars, "SplitPercentDamage", unit.star_level, 0.33)

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
        effect_applied = self._apply_ryze_trait_effect(
            unit, target, enemies, allies, ability_vars, team_traits
        )

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability="Runic Overload",
            active_traits=list(team_traits.keys()),
            effect=effect_applied,
        )
        return True

    def _get_team_traits(self, unit: "Unit", allies: List["Unit"]) -> Dict[str, int]:
        """Get all active traits and their counts on the team."""
        trait_counts = {}
        all_units = [unit] + [a for a in allies if a.is_alive]

        for u in all_units:
            for trait in u.traits:
                trait_counts[trait] = trait_counts.get(trait, 0) + 1

        return trait_counts

    def _apply_ryze_trait_effect(
        self,
        unit: "Unit",
        target: "Unit",
        enemies: List["Unit"],
        allies: List["Unit"],
        ability_vars: Dict,
        team_traits: Dict[str, int],
    ) -> str:
        """Apply Ryze's trait-dependent effect based on active traits.

        Returns the name of the effect applied.
        """

        # Priority order for trait effects (higher priority first)
        # Each trait gives a unique bonus effect

        # TARGON - 10% heal
        if team_traits.get("Targon", 0) >= 2:
            heal_pct = self._get_var(ability_vars, "TargonHealPercent", unit.star_level, 0.10)
            heal_amount = unit.stats.max_hp * heal_pct
            self.engine.heal_unit(unit, heal_amount, "ryze_targon")
            return "Targon: 10% HP heal"

        # YORDLE - 12% damage reduction for 4s
        if team_traits.get("Yordle", 0) >= 3:
            dr_pct = self._get_var(
                ability_vars, "YordleDamageReductionPercent", unit.star_level, 0.12
            )
            unit.stats.damage_reduction += dr_pct
            # Note: Duration tracking would need buff system
            return f"Yordle: {dr_pct * 100:.0f}% DR"

        # BILGEWATER - 25% explosion damage
        if team_traits.get("Bilgewater", 0) >= 3:
            explosion_pct = self._get_var(
                ability_vars, "BilgewaterExplosionPercent", unit.star_level, 0.25
            )
            base_damage = self._get_var(ability_vars, "Damage", unit.star_level, 425)
            explosion_damage = (base_damage + unit.stats.ap) * explosion_pct
            nearby = self._get_enemies_in_radius(target.position, 2, enemies)
            for enemy in nearby:
                self._deal_damage(
                    unit, enemy, explosion_damage, DamageType.MAGIC, "ryze_bilgewater"
                )
            return f"Bilgewater: {explosion_pct * 100:.0f}% explosion"

        # VOID - 30% resist ignore
        if team_traits.get("Void", 0) >= 2:
            resist_ignore = self._get_var(ability_vars, "VoidResistIgnore", unit.star_level, 0.30)
            # Apply as MR shred
            mr_shred = target.stats.magic_resist * resist_ignore
            target.stats.magic_resist = max(0, target.stats.magic_resist - mr_shred)
            return f"Void: {resist_ignore * 100:.0f}% resist ignore"

        # SHADOW ISLES - 5% + soul scaling
        if team_traits.get("Shadow Isles", 0) >= 2:
            base_pct = self._get_var(
                ability_vars, "ShadowIslesBasePercentage", unit.star_level, 0.05
            )
            souls_per_bonus = self._get_var(
                ability_vars, "ShadowIslesSoulsNeededForOnePercentBonusDamage", unit.star_level, 8
            )
            # Get soul count from trait manager
            soul_count = self.engine.trait_manager.get_shadow_isles_souls(unit.team)
            bonus_pct = soul_count / souls_per_bonus / 100  # Convert to percentage
            total_pct = base_pct + bonus_pct
            bonus_damage = (
                self._get_var(ability_vars, "Damage", unit.star_level, 425) + unit.stats.ap
            ) * total_pct
            self._deal_damage(unit, target, bonus_damage, DamageType.MAGIC, "ryze_shadow_isles")
            return f"Shadow Isles: {total_pct * 100:.1f}% bonus ({soul_count} souls)"

        # PILTOVER - 40% overcharge
        if team_traits.get("Piltover", 0) >= 2:
            overcharge_pct = self._get_var(
                ability_vars, "PiltoverOverchargePercentBonus", unit.star_level, 0.40
            )
            overcharge_damage = (
                self._get_var(ability_vars, "Damage", unit.star_level, 425) + unit.stats.ap
            ) * overcharge_pct
            self._deal_damage(unit, target, overcharge_damage, DamageType.MAGIC, "ryze_piltover")
            return f"Piltover: {overcharge_pct * 100:.0f}% overcharge"

        # DEMACIA - 12% execute threshold
        if team_traits.get("Demacia", 0) >= 2:
            execute_threshold = self._get_var(
                ability_vars, "DemaciaExecuteThreshold", unit.star_level, 0.12
            )
            if target.is_alive and target.stats.hp / target.stats.max_hp <= execute_threshold:
                self.engine.apply_damage(
                    unit, target, target.stats.hp + 1, DamageType.TRUE, "ryze_demacia_execute"
                )
                return f"Demacia: Execute at {execute_threshold * 100:.0f}%"
            return f"Demacia: {execute_threshold * 100:.0f}% execute threshold (not triggered)"

        # FRELJORD - chill + 6% max HP true damage
        if team_traits.get("Freljord", 0) >= 2:
            chill_duration = self._get_var(
                ability_vars, "FreljordChillDuration", unit.star_level, 4.0
            )
            true_damage_pct = self._get_var(
                ability_vars, "FreljordTrueDamagePercentHealth", unit.star_level, 0.06
            )
            # Apply chill (slow attack speed)
            target.stats.attack_speed *= 0.7  # 30% AS slow
            # True damage
            true_damage = target.stats.max_hp * true_damage_pct
            self.engine.apply_damage(unit, target, true_damage, DamageType.TRUE, "ryze_freljord")
            return f"Freljord: Chill + {true_damage_pct * 100:.0f}% max HP true damage"

        # ZAUN - poison ticks
        if team_traits.get("Zaun", 0) >= 2:
            poison_damage = self._get_var(ability_vars, "ZaunDamage", unit.star_level, 30)
            base_ticks = int(self._get_var(ability_vars, "ZaunBaseTicks", unit.star_level, 3))
            poison_duration = self._get_var(
                ability_vars, "ZaunPoisonDuration", unit.star_level, 4.0
            )
            total_poison = poison_damage * base_ticks
            self._deal_damage(
                unit, target, total_poison + unit.stats.ap, DamageType.MAGIC, "ryze_zaun_poison"
            )
            return f"Zaun: {base_ticks} poison ticks"

        # SHURIMA - knockup + gold/component chance
        if team_traits.get("Shurima", 0) >= 2:
            knockup_duration = self._get_var(
                ability_vars, "ShurimaKnockUpDuration", unit.star_level, 0.5
            )
            self._apply_stun(target, knockup_duration, "ryze_shurima_knockup")
            # Gold chance (tracked for post-combat)
            coin_chance = self._get_var(ability_vars, "ShurimaCoinChance", unit.star_level, 0.12)
            if not hasattr(unit, "_ryze_shurima_gold_chances"):
                unit._ryze_shurima_gold_chances = 0
            unit._ryze_shurima_gold_chances += 1
            return f"Shurima: {knockup_duration}s knockup + {coin_chance * 100:.0f}% gold chance"

        # NOXUS - damage reduction
        if team_traits.get("Noxus", 0) >= 3:
            dr_pct = self._get_var(
                ability_vars, "NoxusPercentDamageReduction", unit.star_level, 0.60
            )
            # Apply to nearby allies (brief DR)
            nearby_allies = [
                a
                for a in allies
                if a.is_alive and self._hex_distance(unit.position, a.position) <= 2
            ]
            for ally in nearby_allies:
                ally.stats.damage_reduction += dr_pct * 0.25  # Scaled down for balance
            return f"Noxus: {dr_pct * 25:.0f}% DR to nearby allies"

        # IONIA - reduced damage taken
        if team_traits.get("Ionia", 0) >= 3:
            dr_pct = self._get_var(ability_vars, "IoniaDamageReduction", unit.star_level, 0.50)
            unit.stats.damage_reduction += dr_pct * 0.5  # 25% for 1 cast
            return f"Ionia: {dr_pct * 50:.0f}% damage reduction"

        # No matching trait - default effect
        return "No trait bonus"

    # =========================================================================
    # SYLAS - Trifold Ability Rotation
    # =========================================================================

    def _cast_sylas(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Sylas - Stolen Might: Rotates between 3 stolen abilities.

        1. Jarvan - AoE stun
        2. Garen - Single target execute
        3. Lux - Team shield + line damage

        Cannot cast the same ability twice in a row.
        """

        # Track which ability was last used (0=none, 1=jarvan, 2=garen, 3=lux)
        if not hasattr(unit, "_sylas_last_ability"):
            unit._sylas_last_ability = 0

        # Determine which ability to use based on situation
        # Priority: Execute (Garen) if target is low, Stun (Jarvan) if multiple enemies, Shield (Lux) if low HP
        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Get all ability variables
        jarvan_damage = self._get_var(ability_vars, "JarvanDamage", unit.star_level, 180)
        jarvan_stun = self._get_var(ability_vars, "JarvanStunDuration", unit.star_level, 1.75)
        jarvan_radius = int(self._get_var(ability_vars, "JarvanSearchRadius", unit.star_level, 2))

        garen_damage = self._get_var(ability_vars, "GarenDamage", unit.star_level, 1000)
        garen_execute = self._get_var(ability_vars, "GarenExecute", unit.star_level, 0.15)

        lux_shield = self._get_var(ability_vars, "LuxShield", unit.star_level, 450)
        lux_damage = self._get_var(ability_vars, "LuxDamage", unit.star_level, 475)
        shield_duration = self._get_var(ability_vars, "ShieldDuration", unit.star_level, 1.25)

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
                self._deal_damage(
                    unit, enemy, jarvan_damage + unit.stats.ap, DamageType.MAGIC, "sylas_jarvan"
                )
            unit._sylas_last_ability = 1
            ability_name = "Jarvan (AoE Stun)"
            self.engine.log_event(
                "sylas_ability",
                unit=unit.name,
                ability="Jarvan",
                targets=[e.name for e in nearby_enemies],
                stun=jarvan_stun,
            )

        elif best_ability == 2:
            # GAREN - Execute
            if target_hp_percent <= garen_execute:
                # Execute!
                self.engine.apply_damage(
                    unit, target, target.stats.hp + 1, DamageType.TRUE, "sylas_garen_execute"
                )
                self.engine.log_event(
                    "execute",
                    unit=unit.name,
                    target=target.name,
                    threshold=garen_execute,
                    ability="Garen",
                )
            else:
                # Normal damage
                self._deal_damage(
                    unit, target, garen_damage + unit.stats.ap, DamageType.MAGIC, "sylas_garen"
                )
            unit._sylas_last_ability = 2
            ability_name = "Garen (Execute)"

        else:
            # LUX - Shield + line damage
            # Shield self and nearby allies
            self.engine.apply_shield(unit, lux_shield + unit.stats.ap * 0.5, "sylas_lux_shield")
            nearby_allies = [
                a
                for a in allies
                if a.is_alive and self._hex_distance(unit.position, a.position) <= 2
            ]
            for ally in nearby_allies:
                self.engine.apply_shield(ally, lux_shield * 0.5, "sylas_lux_shield")

            # Line damage toward target
            unit_row = unit.position[0]
            for enemy in enemies:
                if enemy.is_alive and enemy.is_targetable:
                    if abs(enemy.position[0] - unit_row) <= 1:
                        self._deal_damage(
                            unit,
                            enemy,
                            lux_damage + unit.stats.ap,
                            DamageType.MAGIC,
                            "sylas_lux_beam",
                        )
            unit._sylas_last_ability = 3
            ability_name = "Lux (Shield + Beam)"

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability=f"Stolen Might: {ability_name}",
            last_ability=unit._sylas_last_ability,
        )
        return True

    # =========================================================================
    # SHADOW ISLES SOUL COLLECTION - Champion Updates
    # =========================================================================

    def _cast_gwen(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Gwen - Snip Snip!: Cone damage with extra snips from souls."""

        base_snips = int(self._get_var(ability_vars, "SnipCount", unit.star_level, 5))
        snip_per_soul = self._get_var(ability_vars, "SnipPerSoulBreakpoint", unit.star_level, 1)
        soul_breakpoint = self._get_var(ability_vars, "SoulBreakpoint", unit.star_level, 80)
        # Patch 16.4: primary 45/68/105→50/75/120, secondary 20/30/50→25/35/60
        damage = self._get_var(ability_vars, "Damage", unit.star_level, 50)
        secondary_damage = self._get_var(ability_vars, "SecondaryMagicDamage", unit.star_level, 25)

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
            self._deal_damage(
                unit, target, damage + unit.stats.ap, DamageType.MAGIC, f"gwen_snip_{i + 1}"
            )

        # Secondary targets in cone get fewer snips
        if not target:
            unit.stats.mana = 0
            return True
        nearby = self._get_enemies_in_radius(target.position, 2, enemies)
        for enemy in nearby:
            if enemy != target and enemy.is_alive:
                snips_on_secondary = max(1, total_snips // 3)
                for _ in range(snips_on_secondary):
                    self._deal_damage(
                        unit,
                        enemy,
                        secondary_damage + unit.stats.ap * 0.3,
                        DamageType.MAGIC,
                        "gwen_secondary_snip",
                    )

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability="Snip Snip!",
            snips=total_snips,
            souls=soul_count,
        )
        return True

    def _cast_kalista(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Kalista - Endless Rend: Multi-target spears with soul scaling."""

        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 48)
        ap_damage = self._get_var(ability_vars, "APDamage", unit.star_level, 5)
        num_enemies = int(self._get_var(ability_vars, "NumberOfEnemies", unit.star_level, 4))
        base_spears = int(self._get_var(ability_vars, "BaseSpears", unit.star_level, 20))
        souls_per_spear = self._get_var(
            ability_vars, "SoulsPerSpearBreakpoint", unit.star_level, 25
        )
        spears_per_breakpoint = int(
            self._get_var(ability_vars, "SpearsPerBreakpoint", unit.star_level, 1)
        )
        armor_reduction = self._get_var(ability_vars, "ArmorReduction", unit.star_level, 1)
        pct_on_primary = self._get_var(
            ability_vars, "PercentMissilesOnPrimaryTarget", unit.star_level, 0.5
        )

        # Get soul count for bonus spears
        soul_count = self.engine.trait_manager.get_shadow_isles_souls(unit.team)
        bonus_spears = int(soul_count / souls_per_spear) * spears_per_breakpoint
        total_spears = base_spears + bonus_spears

        # Get targets
        targets = sorted(
            [e for e in enemies if e.is_alive and e.is_targetable],
            key=lambda e: self._hex_distance(unit.position, e.position),
        )[:num_enemies]

        if not targets:
            return False

        primary_target = targets[0]
        primary_spears = int(total_spears * pct_on_primary)
        secondary_spears = total_spears - primary_spears

        # Apply armor reduction
        for target in targets:
            target.stats.armor = max(0, target.stats.armor - armor_reduction)

        # Primary target spears
        for _i in range(primary_spears):
            if not primary_target.is_alive:
                break
            self._deal_damage(
                unit,
                primary_target,
                ad_damage + unit.stats.ad + ap_damage,
                DamageType.PHYSICAL,
                "kalista_spear",
            )

        # Secondary targets
        if len(targets) > 1:
            spears_each = secondary_spears // (len(targets) - 1)
            for target in targets[1:]:
                for _ in range(spears_each):
                    if not target.is_alive:
                        break
                    self._deal_damage(
                        unit,
                        target,
                        ad_damage + unit.stats.ad,
                        DamageType.PHYSICAL,
                        "kalista_spear_secondary",
                    )

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability="Endless Rend",
            spears=total_spears,
            souls=soul_count,
        )
        return True

    def _cast_viego(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Viego - Blade of the Ruined King: Stacking damage with soul AS scaling."""

        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 85)
        stacking_damage = self._get_var(ability_vars, "StackingDamage", unit.star_level, 27)
        souls_for_as = self._get_var(ability_vars, "SoulsForAttackSpeed", unit.star_level, 6)
        as_per_breakpoint = self._get_var(
            ability_vars, "AttackSpeedPerSoulBreakpoint", unit.star_level, 1
        )
        base_as = (
            self._get_var(ability_vars, "BaseAttackSpeed", unit.star_level, 10) / 100
        )  # Convert to decimal

        # Get soul count for bonus attack speed
        soul_count = self.engine.trait_manager.get_shadow_isles_souls(unit.team)
        bonus_as = (soul_count / souls_for_as) * as_per_breakpoint / 100  # Percentage

        # Track stacks on unit
        if not hasattr(unit, "_viego_stacks"):
            unit._viego_stacks = 0
        unit._viego_stacks += 1

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Deal damage with stacking bonus
        total_damage = ad_damage + unit.stats.ad + (stacking_damage * unit._viego_stacks)
        self._deal_damage(unit, target, total_damage, DamageType.PHYSICAL, "viego_blade")

        # Apply attack speed from souls (permanent for combat)
        if not hasattr(unit, "_viego_soul_as_applied"):
            unit._viego_soul_as_applied = True
            unit.stats.attack_speed += base_as + bonus_as
            self.engine.log_event(
                "viego_soul_as", unit=unit.name, bonus_as=bonus_as, souls=soul_count
            )

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability="Blade of the Ruined King",
            stacks=unit._viego_stacks,
            souls=soul_count,
        )
        return True

    def _cast_yorick(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Yorick - Mourning Mist: Mark enemy + deal % HP damage with soul-scaling heal."""

        # Get ability variables
        flat_damage = self._get_var(ability_vars, "FlatDamage", unit.star_level, 80)
        pct_hp_damage = self._get_var(ability_vars, "PercentHealthDamage", unit.star_level, 0.05)
        ap_heal = self._get_var(ability_vars, "APHeal", unit.star_level, 325)
        heal_per_soul_breakpoint = self._get_var(
            ability_vars, "HealPerSoulBreakpoint", unit.star_level, 7
        )
        soul_breakpoint = self._get_var(ability_vars, "SoulBreakpoint", unit.star_level, 10)
        debuff_duration = self._get_var(ability_vars, "DebuffDuration", unit.star_level, 4.0)

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
        if not hasattr(target, "_yorick_mark"):
            target._yorick_mark = 0
        target._yorick_mark = debuff_duration
        self.engine.log_event(
            "debuff",
            unit=unit.name,
            target=target.name,
            debuff="mourning_mist_mark",
            duration=debuff_duration,
        )

        # Heal Yorick based on AP + soul scaling
        total_heal = ap_heal + bonus_heal
        self.engine.heal_unit(unit, total_heal, "yorick_heal")

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability="Mourning Mist",
            damage=total_damage,
            heal=total_heal,
            souls=soul_count,
        )
        return True

    def _cast_ziggs(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Ziggs - Mega Inferno Bomb: Large AOE with distance-based damage falloff."""

        # Auto attack bounce passive
        bounce_count = int(self._get_var(ability_vars, "BABounceNumber", unit.star_level, 1))
        ba_ad_pct = self._get_var(ability_vars, "BAPercentAD", unit.star_level, 1.0)
        ba_ap_pct = self._get_var(ability_vars, "BAPercentAP", unit.star_level, 40) / 100

        # Bomb variables
        aoe_range = int(self._get_var(ability_vars, "BombAOERange", unit.star_level, 4))
        min_damage = self._get_var(ability_vars, "MinAOEDamage", unit.star_level, 70)
        max_damage = self._get_var(ability_vars, "MaxAOEDamage", unit.star_level, 550)

        # Enable auto attack bounce passive on first cast
        if not getattr(unit, "_ziggs_bounce_enabled", False):
            unit._ziggs_bounce_enabled = True
            unit._ziggs_bounce_count = bounce_count
            unit._ziggs_ba_damage = unit.stats.ad * ba_ad_pct + unit.stats.ap * ba_ap_pct
            self.engine.log_event("ziggs_bounce_passive", unit=unit.name, bounces=bounce_count)

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
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability="Mega Inferno Bomb",
            center=bomb_center,
            enemies_hit=len(enemies_in_range),
        )
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
    GLUTTON_HP_ROLES = ["ADTank", "APTank", "Attack Tank", "Magic Tank"]
    GLUTTON_AS_ROLES = [
        "ADAssassin",
        "ADCaster",
        "ADFighter",
        "ADCarry",
        "ADSpecialist",
        "Attack Assassin",
        "Attack Caster",
        "Attack Fighter",
        "Attack Marksman",
        "Attack Specialist",
    ]
    GLUTTON_AP_ROLES = [
        "HFighter",
        "APAssassin",
        "APCaster",
        "APFighter",
        "APCarry",
        "APSpecialist",
        "Hybrid Fighter",
        "Magic Assassin",
        "Magic Caster",
        "Magic Fighter",
        "Magic Marksman",
        "Magic Specialist",
    ]

    def _cast_tahmkench(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Tahm Kench - Devour: Swallow enemy, deal damage over time.

        Glutton trait: Feed champions to Tahm Kench for permanent stats.
        Stat gained depends on fed unit's ROLE:
        - Tank roles -> Health
        - AD roles -> Attack Speed %
        - AP roles -> Ability Power %
        """

        # Get ability variables
        damage = self._get_var(ability_vars, "Damage", unit.star_level, 1800)
        stun_duration = self._get_var(ability_vars, "StunDuration", unit.star_level, 0.5)
        belly_duration = self._get_var(ability_vars, "BellyDuration", unit.star_level, 2.5)
        damage_reduction = self._get_var(ability_vars, "DamageReduction", unit.star_level, 0.30)

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
            if not hasattr(unit, "_tahm_digesting"):
                unit._tahm_digesting = True

            # Deal damage over the belly duration (simplified to instant)
            self._deal_damage(unit, target, damage + unit.stats.ap, DamageType.MAGIC, "tahm_devour")

            self.engine.log_event(
                "tahm_devour",
                unit=unit.name,
                target=target.name,
                duration=belly_duration,
                damage=damage,
            )

            # If target dies while devoured, gain Glutton stats
            if not target.is_alive:
                self._apply_glutton_stats(unit, target)
        else:
            # Can't fully devour - just damage and stun
            self._deal_damage(
                unit, target, damage * 0.5 + unit.stats.ap, DamageType.MAGIC, "tahm_lick"
            )
            self._apply_stun(target, stun_duration, "tahm_stun")

        unit.stats.mana = 0
        return True

    def _get_glutton_stat_type(self, role: str) -> str:
        """Determine which stat Tahm Kench gains from eating a unit based on role."""
        if any(r in role for r in ["Tank"]):
            return "hp"
        elif any(r in role for r in ["AD", "Attack", "Marksman"]):
            return "as"
        elif any(r in role for r in ["AP", "Magic", "Hybrid", "Caster"]):
            return "ap"
        # Default to HP for unknown roles
        return "hp"

    def _apply_glutton_stats(self, tahm: "Unit", eaten_unit: "Unit"):
        """Apply permanent stats from eating a unit (Glutton trait)."""
        eaten_data = self.engine.champions.get(eaten_unit.api_name, {})
        cost = eaten_data.get("cost", 1)
        star = eaten_unit.star_level
        role = eaten_data.get("role", "")

        # Determine stat type from role
        stat_type = self._get_glutton_stat_type(role)

        # Get value from appropriate table
        if stat_type == "hp":
            table = self.GLUTTON_HP_TABLE
            value = table.get(cost, table[1]).get(star, table[1][1])
            stat_name = "hp"
        elif stat_type == "as":
            table = self.GLUTTON_AS_TABLE
            value = table.get(cost, table[1]).get(star, table[1][1])
            stat_name = "attack_speed"
            value = value / 100  # Convert percentage to decimal
        else:  # ap
            table = self.GLUTTON_AP_TABLE
            value = table.get(cost, table[1]).get(star, table[1][1])
            stat_name = "ap"

        # Track stats gained
        if not hasattr(tahm, "_glutton_stats"):
            tahm._glutton_stats = {"hp": 0, "attack_speed": 0, "ap": 0, "units_eaten": 0}

        tahm._glutton_stats[stat_name] += value
        tahm._glutton_stats["units_eaten"] += 1

        # Apply stats
        if stat_name == "hp":
            tahm.stats.max_hp += value
            tahm.stats.hp += value
        elif stat_name == "attack_speed":
            # Cap at 5.0 total AS, convert excess to AP
            current_as = tahm.stats.attack_speed
            if current_as + value > 5.0:
                as_to_add = max(0, 5.0 - current_as)
                excess_as = value - as_to_add
                tahm.stats.attack_speed += as_to_add
                # Convert excess AS to AP (1% AS = 1 AP)
                tahm.stats.ap += excess_as * 100
                tahm._glutton_stats["ap"] += excess_as * 100
            else:
                tahm.stats.attack_speed += value
        else:  # ap
            tahm.stats.ap += value

        self.engine.log_event(
            "glutton_stats",
            unit=tahm.name,
            eaten=eaten_unit.name,
            cost=cost,
            star=star,
            role=role,
            stat_type=stat_type,
            value=value if stat_name != "attack_speed" else value * 100,
        )

    def apply_glutton_feeding(self, tahm: "Unit", fed_units: List[Dict]):
        """Pre-combat: Apply stats from units fed to Tahm Kench.

        Args:
            tahm: Tahm Kench unit
            fed_units: List of dicts with 'cost', 'star', and 'role' keys
        """
        for fed in fed_units:
            cost = fed.get("cost", 1)
            star = fed.get("star", 1)
            role = fed.get("role", "")

            stat_type = self._get_glutton_stat_type(role)

            if stat_type == "hp":
                table = self.GLUTTON_HP_TABLE
                value = table.get(cost, table[1]).get(star, table[1][1])
                stat_name = "hp"
            elif stat_type == "as":
                table = self.GLUTTON_AS_TABLE
                value = table.get(cost, table[1]).get(star, table[1][1])
                stat_name = "attack_speed"
                value = value / 100
            else:
                table = self.GLUTTON_AP_TABLE
                value = table.get(cost, table[1]).get(star, table[1][1])
                stat_name = "ap"

            if not hasattr(tahm, "_glutton_stats"):
                tahm._glutton_stats = {"hp": 0, "attack_speed": 0, "ap": 0, "units_eaten": 0}

            tahm._glutton_stats[stat_name] += value
            tahm._glutton_stats["units_eaten"] += 1

            if stat_name == "hp":
                tahm.stats.max_hp += value
                tahm.stats.hp += value
            elif stat_name == "attack_speed":
                current_as = tahm.stats.attack_speed
                if current_as + value > 5.0:
                    as_to_add = max(0, 5.0 - current_as)
                    excess_as = value - as_to_add
                    tahm.stats.attack_speed += as_to_add
                    tahm.stats.ap += excess_as * 100
                    tahm._glutton_stats["ap"] += excess_as * 100
                else:
                    tahm.stats.attack_speed += value
            else:
                tahm.stats.ap += value

    # =========================================================================
    # GALIO - Bench Mechanic & Demacia Rally
    # =========================================================================

    def _cast_galio(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Galio - Inspirational Might: Shield allies and deal MR-scaled damage.

        Heroic trait: Galio starts on bench, joins fight on first Demacia rally.
        """

        num_attacks = int(self._get_var(ability_vars, "NumAttacks", unit.star_level, 3))
        passive_mr_ratio = self._get_var(ability_vars, "PassiveMRRatio", unit.star_level, 5.7)
        shield_amount = self._get_var(ability_vars, "Shield", unit.star_level, 600)
        active_mr_damage = self._get_var(ability_vars, "ActiveMRDamage", unit.star_level, 5.25)
        active_ar_damage = self._get_var(ability_vars, "ActiveARDamage", unit.star_level, 5.25)

        # Shield all allies
        for ally in allies:
            if ally.is_alive:
                self.engine.apply_shield(ally, shield_amount + unit.stats.ap * 0.3, "galio_shield")

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
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability="Inspirational Might",
            shield=shield_amount,
            damage=total_damage,
        )
        return True

    def trigger_demacia_rally(self, team: List["Unit"], bench_galio: "Unit" = None):
        """Trigger Demacia rally - Galio joins from bench."""
        if not bench_galio:
            return None

        enemies = [u for u in self.engine.units if u.team != bench_galio.team and u.is_alive]
        if not enemies:
            return None

        # Find best slam position

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
            from .combat_engine import DamageType, UnitState

            bench_galio.position = best_pos
            bench_galio.is_alive = True
            bench_galio.state = UnitState.IDLE

            self.engine.units.append(bench_galio)

            # Entry slam damage
            entry_damage = bench_galio.stats.magic_resist * 3 + bench_galio.stats.ap
            nearby = [e for e in enemies if HexGrid.hex_distance(best_pos, e.position) <= 2]
            for enemy in nearby:
                self._deal_damage(
                    bench_galio, enemy, entry_damage, DamageType.MAGIC, "galio_entry_slam"
                )
                self._apply_stun(enemy, 1.5, "galio_entry_stun")

            self.engine.log_event(
                "galio_rally", unit=bench_galio.name, position=best_pos, enemies_hit=len(nearby)
            )

        return bench_galio

    # =========================================================================
    # T-HEX - HexMech Pilot System
    # =========================================================================

    # HexMech pilot bonus stats by role and star level
    # Tank: Omnivamp, Fighter: AD%, Marksman: Damage Amp, Caster: Mana Regen, Assassin: Crit Chance
    HEXMECH_PILOT_BONUSES = {
        "Tank": {"stat": "omnivamp", "values": {1: 0.15, 2: 0.25, 3: 0.40}},
        "Fighter": {"stat": "ad_percent", "values": {1: 0.15, 2: 0.25, 3: 0.40}},
        "Marksman": {"stat": "damage_amp", "values": {1: 0.10, 2: 0.18, 3: 0.30}},
        "Caster": {"stat": "mana_regen", "values": {1: 2, 2: 4, 3: 5}},
        "Assassin": {"stat": "crit_chance", "values": {1: 0.30, 2: 0.60, 3: 1.00}},
    }

    def _cast_thex(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """T-Hex - Hextech Arsenal: Gatling gun + shield.

        HexMech trait: Pilot jumps in at combat start, grants 80% HP + role bonus.
        """

        num_bullets = int(self._get_var(ability_vars, "NumBullets", unit.star_level, 4))
        base_shield = self._get_var(ability_vars, "BaseShield", unit.star_level, 400)
        pct_hp_shield = self._get_var(ability_vars, "PercentHealthShield", unit.star_level, 0.10)
        ap_damage = self._get_var(ability_vars, "APDamage", unit.star_level, 15)
        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 100)

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
            self._deal_damage(unit, target, damage, DamageType.PHYSICAL, f"thex_bullet_{i + 1}")

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability="Hextech Arsenal",
            bullets=num_bullets,
            shield=shield,
        )
        return True

    def _get_pilot_role_category(self, role: str) -> str:
        """Determine HexMech bonus category from pilot's role."""
        role_lower = role.lower()
        if "tank" in role_lower:
            return "Tank"
        elif "fighter" in role_lower:
            return "Fighter"
        elif "carry" in role_lower or "marksman" in role_lower:
            return "Marksman"
        elif "caster" in role_lower or "mage" in role_lower or "invoker" in role_lower:
            return "Caster"
        elif "assassin" in role_lower:
            return "Assassin"
        # Default to Fighter for unknown roles
        return "Fighter"

    def assign_thex_pilot(self, thex: "Unit", pilot: "Unit"):
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
        role = pilot_data.get("role", "Fighter")
        pilot_star = pilot.star_level if hasattr(pilot, "star_level") else 1

        # Store pilot reference
        thex._pilot = pilot
        thex._pilot_role = role

        # Grant 80% of pilot's HP
        pilot_hp = pilot.stats.max_hp if hasattr(pilot, "stats") else 500
        hp_bonus = pilot_hp * 0.80
        thex.stats.max_hp += hp_bonus
        thex.stats.hp += hp_bonus

        # Determine role category and apply bonus
        role_category = self._get_pilot_role_category(role)
        bonus_info = self.HEXMECH_PILOT_BONUSES.get(
            role_category, self.HEXMECH_PILOT_BONUSES["Fighter"]
        )
        stat_type = bonus_info["stat"]
        bonus_value = bonus_info["values"].get(pilot_star, bonus_info["values"][1])

        # Apply the stat bonus
        if stat_type == "omnivamp":
            thex.stats.omnivamp += bonus_value
        elif stat_type == "ad_percent":
            ad_bonus = thex.base_stats.ad * bonus_value
            thex.stats.ad += ad_bonus
        elif stat_type == "damage_amp":
            thex.stats.damage_amp += bonus_value
        elif stat_type == "mana_regen":
            # Mana regen per second - store for tick processing
            if not hasattr(thex, "_mana_regen_bonus"):
                thex._mana_regen_bonus = 0
            thex._mana_regen_bonus += bonus_value
        elif stat_type == "crit_chance":
            thex.stats.crit_chance += bonus_value

        # Track the bonus for logging
        thex._hexmech_bonus = {"stat": stat_type, "value": bonus_value, "role": role_category}

        self.engine.log_event(
            "hexmech_pilot",
            thex=thex.name,
            pilot=pilot.name,
            role=role_category,
            star=pilot_star,
            hp_bonus=hp_bonus,
            stat_bonus=f"{stat_type}: {bonus_value}",
        )

    def trigger_thex_death(self, thex: "Unit", enemies: List["Unit"]):
        """Handle T-Hex death - pilot ejects, knockback + stun nearby enemies.

        On death: Pilot ejects while T-Hex knocks back and Stuns
        nearby enemies for 1.5 seconds.
        """

        # Knockback and stun nearby enemies
        nearby = [
            e
            for e in enemies
            if e.is_alive
            and e.is_targetable
            and HexGrid.hex_distance(thex.position, e.position) <= 2
        ]

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
        pilot = getattr(thex, "_pilot", None)
        if pilot:
            self.engine.log_event("hexmech_eject", pilot=pilot.name, enemies_stunned=len(nearby))

        return pilot

    # =========================================================================
    # BARON NASHOR - Riftscourge
    # =========================================================================

    def _cast_baronnashor(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Baron Nashor - Wrath of the Void: Acid shots + Void Rift.

        Riftscourge: +2 Void trait, 30% damage amp after 8s.
        """

        ap_damage = self._get_var(ability_vars, "APDamage", unit.star_level, 45)
        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 375)
        acid_pct = self._get_var(ability_vars, "AcidPercentDamage", unit.star_level, 0.45)
        num_acid = int(self._get_var(ability_vars, "NumAcidToShoot", unit.star_level, 10))
        knockup_duration = self._get_var(ability_vars, "KnockupDuration", unit.star_level, 1.5)

        # Track Void Rift timer
        if not hasattr(unit, "_void_rift_active"):
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
            self._deal_damage(
                unit,
                acid_target,
                acid_damage + unit.stats.ap * 0.2,
                DamageType.MAGIC,
                f"baron_acid_{i + 1}",
            )

        # Void Rift tick
        if unit._void_rift_active:
            self._void_rift_tick(unit, enemies)

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability="Wrath of the Void",
            acid_shots=num_acid,
            rift_active=unit._void_rift_active,
        )
        return True

    def _activate_void_rift(self, baron: "Unit", allies: List["Unit"]):
        """Activate Void Rift - 30% damage amp for Void units."""
        baron._void_rift_active = True
        void_amp = 0.30

        for ally in allies:
            if "Void" in ally.traits:
                ally.stats.damage_amp += void_amp
                ally._void_rift_amp = True

        if "Void" in baron.traits:
            baron.stats.damage_amp += void_amp

        self.engine.log_event("void_rift_active", baron=baron.name, damage_amp=void_amp)

    def _void_rift_tick(self, baron: "Unit", enemies: List["Unit"]):
        """Apply Void Rift plasma bolt damage (5% max HP)."""

        for enemy in enemies:
            if enemy.is_alive and enemy.is_targetable:
                plasma_damage = enemy.stats.max_hp * 0.05
                self.engine.apply_damage(
                    baron, enemy, plasma_damage, DamageType.MAGIC, "void_rift_plasma"
                )

    def setup_baron_riftscourge(self, baron: "Unit", team: List["Unit"]):
        """Set up Baron's Riftscourge trait at combat start."""
        baron._void_rift_active = False
        baron._void_rift_timer = self.engine.time + 8.0

        if not hasattr(self.engine.trait_manager, "riftscourge_void_bonus"):
            self.engine.trait_manager.riftscourge_void_bonus = 0
        self.engine.trait_manager.riftscourge_void_bonus = 2

        self.engine.log_event("riftscourge_setup", baron=baron.name, void_bonus=2, rift_timer=8.0)

    # =========================================================================
    # RIFT HERALD - Durability Passive
    # =========================================================================

    def _cast_riftherald(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Rift Herald - Warp Armor: Gain durability based on nearby enemies."""

        ap_damage = self._get_var(ability_vars, "APDamage", unit.star_level, 150)
        bonus_durability = self._get_var(ability_vars, "BonusDurability", unit.star_level, 0.25)
        durability_per_enemy = self._get_var(
            ability_vars, "DurabilityPerEnemy", unit.star_level, 0.01
        )
        bonus_health = self._get_var(ability_vars, "BonusHealth", unit.star_level, 350)

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
            self._deal_damage(
                unit, enemy, ap_damage + unit.stats.ap, DamageType.MAGIC, "riftherald_warp"
            )

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability="Warp Armor",
            durability=total_dr,
            enemies_nearby=enemy_count,
        )
        return True

    # =========================================================================
    # LEONA - Flat Damage Reduction Passive
    # =========================================================================

    def _cast_leona(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Leona - Solar Flare: Stun enemies and gain flat damage reduction."""

        flat_dr = self._get_var(ability_vars, "FlatDR", unit.star_level, 30)
        num_enemies = int(self._get_var(ability_vars, "NumEnemies", unit.star_level, 3))
        stun_duration = self._get_var(ability_vars, "StunDuration", unit.star_level, 1.0)
        damage = self._get_var(ability_vars, "Damage", unit.star_level, 120)

        # Apply flat damage reduction as a passive (stacks)
        if not hasattr(unit, "_leona_flat_dr"):
            unit._leona_flat_dr = 0
        unit._leona_flat_dr += flat_dr

        # Stun and damage nearest enemies
        targets = sorted(
            [e for e in enemies if e.is_alive and e.is_targetable],
            key=lambda e: self._hex_distance(unit.position, e.position),
        )[:num_enemies]

        for target in targets:
            self._deal_damage(
                unit, target, damage + unit.stats.ap, DamageType.MAGIC, "leona_solar_flare"
            )
            self._apply_stun(target, stun_duration, "leona_stun")

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability="Solar Flare",
            flat_dr=unit._leona_flat_dr,
            targets=[t.name for t in targets],
        )
        return True

    def apply_leona_flat_dr(self, unit: "Unit", incoming_damage: float) -> float:
        """Apply Leona's flat damage reduction to incoming damage."""
        flat_dr = getattr(unit, "_leona_flat_dr", 0)
        if flat_dr > 0:
            return max(0, incoming_damage - flat_dr)
        return incoming_damage

    # =========================================================================
    # TARIC - Passive MR Aura + Heal at 35% HP
    # =========================================================================

    def _cast_taric(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Taric - Starlight's Touch: Shield self + 2 lowest health allies, empowered attacks.

        Passive (always active at combat start): All allies gain 10/20/100 MR.
        Passive (once per combat): At 35% HP, restore 300/700/2500 health over 2s.
        Active: Shield self (600/700/2500) + 2 lowest health allies (125/150/1000).
        Empowered: Next 2/2/10 attacks deal 200/300/3000 bonus magic damage.
        """
        # Get ability variables
        taric_shield = self._get_var(ability_vars, "TaricShield", unit.star_level, 600)
        ally_shield = self._get_var(ability_vars, "AllyShield", unit.star_level, 125)
        num_empowered_attacks = int(
            self._get_var(ability_vars, "NumEmpoweredAttacks", unit.star_level, 2)
        )
        bonus_damage = self._get_var(ability_vars, "BonusDamage", unit.star_level, 200)

        # Shield self
        self.engine.apply_shield(unit, taric_shield + unit.stats.ap * 0.5, "taric_starlight_shield")

        # Shield 2 LOWEST HEALTH allies (not nearest!)
        living_allies = [a for a in allies if a.is_alive and a != unit]
        if living_allies:
            # Sort by HP (lowest first)
            living_allies.sort(key=lambda a: a.stats.hp)
            for ally in living_allies[:2]:
                self.engine.apply_shield(
                    ally, ally_shield + unit.stats.ap * 0.3, "taric_ally_shield"
                )

        # Grant empowered attacks (deal bonus MAGIC damage)
        unit._taric_empowered_attacks = num_empowered_attacks
        unit._taric_bonus_damage = bonus_damage

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability="Starlight's Touch",
            self_shield=taric_shield,
            ally_shield=ally_shield,
            empowered_attacks=num_empowered_attacks,
        )
        return True

    def apply_taric_passive_mr(self, taric: "Unit", allies: List["Unit"], ability_vars: Dict):
        """Apply Taric's passive MR aura at combat start."""
        mr_for_allies = self._get_var(ability_vars, "MRForAllies", taric.star_level, 10)
        for ally in allies:
            if ally.is_alive:
                ally.stats.magic_resist += mr_for_allies
        self.engine.log_event("taric_passive_mr", unit=taric.name, mr_granted=mr_for_allies)

    def check_taric_empowered_attack(self, unit: "Unit") -> float:
        """Check if Taric has empowered attacks remaining and return bonus MAGIC damage."""
        if unit.api_name != "TFT16_Taric":
            return 0

        if hasattr(unit, "_taric_empowered_attacks") and unit._taric_empowered_attacks > 0:
            unit._taric_empowered_attacks -= 1
            return getattr(unit, "_taric_bonus_damage", 200)
        return 0

    def check_taric_low_hp_heal(self, unit: "Unit", ability_vars: Dict) -> bool:
        """Check if Taric should heal at 35% HP (once per combat, heals over 2 seconds)."""
        if unit.api_name != "TFT16_Taric":
            return False

        if hasattr(unit, "_taric_heal_used"):
            return False

        hp_percent = unit.stats.hp / unit.stats.max_hp
        if hp_percent <= 0.35:
            unit._taric_heal_used = True
            passive_heal = self._get_var(ability_vars, "PassiveHeal", unit.star_level, 300)
            # Heal over 2 seconds (simplified: instant heal for simulator)
            self.engine.heal_unit(unit, passive_heal, "taric_35_percent_heal")
            self.engine.log_event(
                "taric_low_hp_heal", unit=unit.name, hp_percent=hp_percent, heal=passive_heal
            )
            return True
        return False

    # Legacy function name for backwards compatibility
    def check_taric_invulnerability(self, unit: "Unit") -> bool:
        """DEPRECATED: Taric doesn't have invulnerability - he has a heal at 35% HP."""
        # Delegate to the correct function
        ability_vars = {}  # Would need to pass actual vars
        return (
            self.check_taric_low_hp_heal(unit, ability_vars)
            if unit.api_name == "TFT16_Taric"
            else False
        )

    # =========================================================================
    # SKARNER - Armor Aura + Impale
    # =========================================================================

    def _cast_skarner(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Skarner - Impale: Grant armor aura, grab and stun target."""

        armor_for_allies = self._get_var(ability_vars, "ArmorForAllies", unit.star_level, 20)
        shield_amount = self._get_var(ability_vars, "ShieldAmount", unit.star_level, 950)
        shield_duration = self._get_var(ability_vars, "ShieldDuration", unit.star_level, 4.0)
        impale_duration = self._get_var(ability_vars, "ImpaleDuration", unit.star_level, 1.75)

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
                self.engine.log_event(
                    "skarner_grab", unit=unit.name, target=target.name, new_position=target.position
                )

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability="Impale",
            armor_granted=armor_for_allies,
            shield=shield_amount,
        )
        return True

    # =========================================================================
    # XERATH - Ascendant Trait (Store Items)
    # =========================================================================

    def _cast_xerath(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Xerath - Eye of the Ascendant: Multiple blasts at random enemies.

        Ascendant trait: After combat, Charm appears in shop (handled externally).
        """

        num_blasts = int(self._get_var(ability_vars, "NumberOfBlasts", unit.star_level, 10))
        damage = self._get_var(ability_vars, "Damage", unit.star_level, 650)
        spell_range = int(self._get_var(ability_vars, "SpellRangeInEnemies", unit.star_level, 4))

        # Get targets in range
        targets = [e for e in enemies if e.is_alive and e.is_targetable]

        # Fire blasts at random targets
        for i in range(num_blasts):
            if not targets:
                break
            target = random.choice(targets)
            self._deal_damage(
                unit, target, damage + unit.stats.ap, DamageType.MAGIC, f"xerath_blast_{i + 1}"
            )
            # Remove dead targets
            targets = [t for t in targets if t.is_alive]

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast", unit=unit.name, ability="Eye of the Ascendant", blasts=num_blasts
        )
        return True

    # =========================================================================
    # ZILEAN - Time Bomb Chaining
    # =========================================================================

    def _cast_zilean(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Zilean - Visions of the End: Place time bombs that chain and explode.

        Double bomb: If 2 bombs on same target, instant explosion with bonus damage.
        """

        magic_damage = self._get_var(ability_vars, "MagicDamage", unit.star_level, 115)
        explosion_damage = self._get_var(ability_vars, "ExplosionDamage", unit.star_level, 225)
        mana_on_kill = self._get_var(ability_vars, "ManaOnKill", unit.star_level, 15)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Track bombs on target
        if not hasattr(target, "_zilean_bombs"):
            target._zilean_bombs = 0

        target._zilean_bombs += 1

        # Apply initial damage
        self._deal_damage(
            unit, target, magic_damage + unit.stats.ap, DamageType.MAGIC, "zilean_bomb"
        )

        # Double bomb check - if 2+ bombs, instant massive explosion
        if target._zilean_bombs >= 2:
            # Double bomb explosion - deals to target and nearby
            self._deal_damage(
                unit,
                target,
                explosion_damage + unit.stats.ap,
                DamageType.MAGIC,
                "zilean_double_bomb",
            )

            # Splash to nearby
            nearby = self._get_enemies_in_radius(target.position, 1, enemies)
            for enemy in nearby:
                if enemy != target:
                    self._deal_damage(
                        unit,
                        enemy,
                        explosion_damage * 0.5 + unit.stats.ap,
                        DamageType.MAGIC,
                        "zilean_bomb_splash",
                    )

            target._zilean_bombs = 0  # Reset bombs
            self.engine.log_event("zilean_double_bomb", unit=unit.name, target=target.name)

        unit.stats.mana = 0
        # Mana refund on kill (refund after spending mana)
        if not target.is_alive:
            self.engine.gain_mana(unit, mana_on_kill, source="zilean_kill_refund")
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability="Visions of the End",
            bombs_on_target=target._zilean_bombs if target.is_alive else 0,
        )
        return True

    # =========================================================================
    # MEL - Mana Drain + Radiant Eclipse
    # =========================================================================

    def _cast_mel(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Mel - Radiant Eclipse: Orbs that damage + mana drain passive.

        Passive: Drains 1 mana/sec from nearby enemies.
        Trait: Can generate radiant items (handled externally).
        """

        num_orbs = int(self._get_var(ability_vars, "NumOfOrbs", unit.star_level, 2))
        passive_damage = self._get_var(ability_vars, "PassiveDamage", unit.star_level, 60)
        target_damage = self._get_var(ability_vars, "TargetDamage", unit.star_level, 1500)
        explosion_damage = self._get_var(ability_vars, "ExplosionDamage", unit.star_level, 600)

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
            self._deal_damage(
                unit,
                target,
                target_damage / num_orbs + unit.stats.ap,
                DamageType.MAGIC,
                f"mel_orb_{i + 1}",
            )

        # Final explosion
        nearby = self._get_enemies_in_radius(
            target.position if target else unit.position, 2, enemies
        )
        for enemy in nearby:
            self._deal_damage(
                unit, enemy, explosion_damage + unit.stats.ap, DamageType.MAGIC, "mel_explosion"
            )

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast", unit=unit.name, ability="Radiant Eclipse", orbs=num_orbs
        )
        return True

    def mel_mana_drain_tick(self, unit: "Unit", enemies: List["Unit"]):
        """Mel's passive: Drain 1 mana/sec from nearby enemies."""
        if unit.api_name != "TFT16_Mel" or not unit.is_alive:
            return

        nearby = self._get_enemies_in_radius(unit.position, 2, enemies)
        for enemy in nearby:
            if enemy.is_alive:
                enemy.stats.mana = max(0, enemy.stats.mana - 1)

    # =========================================================================
    # SETT - The Show Stopper (Multi-dash)
    # =========================================================================

    def _cast_sett(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Sett - The Show Stopper: Dash to target, slam for %HP damage."""

        aoe_radius = int(self._get_var(ability_vars, "AoERadius", unit.star_level, 3))
        flat_damage = self._get_var(ability_vars, "FlatAPDamage", unit.star_level, 350)
        pct_max_hp = self._get_var(ability_vars, "PercentOfTargetMaxHealth", unit.star_level, 0.09)
        aoe_damage_pct = self._get_var(ability_vars, "PercentAoEDamage", unit.star_level, 0.5)

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
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability="The Show Stopper",
            primary_target=target.name,
            aoe_radius=aoe_radius,
        )
        return True

    # =========================================================================
    # BROCK - Board-wide Seismic Passive
    # =========================================================================

    def _cast_brock(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Brock - Seismic Slam: Board-wide slam with falloff.

        Passive: Attacks deal 50% damage to nearby enemies.
        Active: Slam all enemies, damage/stun reduced by distance.
        """

        passive_aoe = self._get_var(ability_vars, "PassivePercentAoE", unit.star_level, 0.5)
        slam_base = self._get_var(ability_vars, "SlamDamageBase", unit.star_level, 200)
        slam_hp_pct = self._get_var(ability_vars, "SlamDamageHealth", unit.star_level, 0.02)
        stun_duration = self._get_var(ability_vars, "StunDuration", unit.star_level, 1.75)
        reduction_per_hex = self._get_var(
            ability_vars, "EffectReductionPerHex", unit.star_level, 0.15
        )
        reduction_minimum = self._get_var(
            ability_vars, "EffectReductionMinimum", unit.star_level, 0.40
        )

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
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability="Seismic Slam",
            enemies_hit=len([e for e in enemies if e.is_alive]),
        )
        return True

    def brock_passive_aoe(self, unit: "Unit", target: "Unit", damage: float, enemies: List["Unit"]):
        """Brock's passive: Attacks deal 50% damage to nearby enemies."""
        if unit.api_name != "TFT16_Brock":
            return

        nearby = self._get_enemies_in_radius(target.position, 1, enemies)
        for enemy in nearby:
            if enemy != target and enemy.is_alive:
                splash = damage * 0.5
                self.engine.apply_damage(
                    unit, enemy, splash, DamageType.PHYSICAL, "brock_passive_splash"
                )
