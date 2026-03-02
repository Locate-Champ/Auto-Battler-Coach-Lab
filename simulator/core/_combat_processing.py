"""Combat processing: attack execution, ability casting, movement, unit ticks."""

from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING, List, Optional, Tuple

from ._combat_types import AbilityType, DamageType, TargetingType, UnitState, _star_val
from ._hex_grid import HexGrid

if TYPE_CHECKING:
    from ._combat_types import Unit

_log = logging.getLogger(__name__)


class _CombatProcessingMixin:
    """Mixin providing attack/ability/movement/tick methods for CombatEngine."""

    def find_target(
        self,
        unit: Unit,
        enemies: List[Unit],
        targeting: TargetingType = TargetingType.NEAREST,
        include_untargetable: bool = False,
    ) -> Optional[Unit]:
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
            dist_row = HexGrid._DISTANCE_LUT[unit.position]
            min_dist = 999
            for e in valid_enemies:
                d = dist_row[e.position]
                if d < min_dist:
                    min_dist = d

            # Single pass: find closest frontline, and closest overall
            best_frontline = None
            best_frontline_dist = 999
            best_any = None
            best_any_dist = 999
            threshold = min_dist + 1

            for e in valid_enemies:
                d = dist_row[e.position]
                if d <= threshold and e.is_frontline:
                    if d < best_frontline_dist:
                        best_frontline_dist = d
                        best_frontline = e
                if d < best_any_dist:
                    best_any_dist = d
                    best_any = e

            return best_frontline if best_frontline is not None else best_any

        elif targeting == TargetingType.LOWEST_HP:
            return min(valid_enemies, key=lambda e: e.stats.hp)
        elif targeting == TargetingType.LOWEST_HP_PERCENT:
            return min(valid_enemies, key=lambda e: e.stats.hp / e.stats.max_hp)
        elif targeting == TargetingType.HIGHEST_HP:
            return max(valid_enemies, key=lambda e: e.stats.hp)
        elif targeting == TargetingType.FARTHEST:
            dist_row = HexGrid._DISTANCE_LUT[unit.position]
            return max(valid_enemies, key=lambda e: dist_row[e.position])
        elif targeting == TargetingType.RANDOM:
            return random.choice(valid_enemies)

        return valid_enemies[0]

    def get_enemies_in_range(
        self, unit: Unit, radius: int, enemies: List[Unit], include_untargetable: bool = False
    ) -> List[Unit]:
        """Get all enemies within radius of unit.

        Args:
            include_untargetable: If True, include untargetable units (for positioning/AoE checks)
        """
        dist_row = HexGrid._DISTANCE_LUT[unit.position]
        if include_untargetable:
            return [e for e in enemies if e.is_alive and dist_row[e.position] <= radius]
        return [
            e for e in enemies if e.is_alive and e.is_targetable and dist_row[e.position] <= radius
        ]

    def can_attack(self, unit: Unit, target: Unit) -> bool:
        """Check if unit can attack target (in range)."""
        return HexGrid._DISTANCE_LUT[unit.position][target.position] <= unit.stats.range

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
            ability_vars = champ_data.get("ability", {}).get("variables", {})
            num_attacks_data = ability_vars.get("NumAttacks")
            threshold = _star_val(num_attacks_data, unit.star_level, 18)

            if unit.attacks_performed > threshold:
                is_jinx_rockets = True
                # Rocket form: Gets AD bonus from ability
                ad_bonus_data = ability_vars.get("ADDamage")
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
            splash_targets = self.get_enemies_in_range(
                unit,
                1,
                [u for u in self.units if u.team != unit.team and u.is_alive and u != unit.target],
            )
            for splash_target in splash_targets[:2]:  # Max 2 splash targets
                splash_damage = final_damage * 0.5  # 50% splash
                self.apply_damage(
                    unit, splash_target, splash_damage, DamageType.PHYSICAL, "jinx_splash"
                )

        # Handle enhanced attacks (from Fizz ability or items)
        if unit.enhanced_attacks_remaining > 0:
            unit.enhanced_attacks_remaining -= 1

            # Apply on-hit magic damage
            if unit.enhanced_attack_on_hit_dmg > 0:
                on_hit_damage, _ = self.calculate_damage(
                    unit,
                    unit.target,
                    unit.enhanced_attack_on_hit_dmg,
                    DamageType.MAGIC,
                    can_crit=False,
                    is_ability=True,
                )
                self.apply_damage(
                    unit, unit.target, on_hit_damage, DamageType.MAGIC, "enhanced_on_hit"
                )

            # Reset bonus AS when enhanced attacks run out
            if unit.enhanced_attacks_remaining == 0:
                unit.stats.attack_speed -= unit.enhanced_attack_bonus_as
                unit.enhanced_attack_bonus_as = 0
                unit.enhanced_attack_on_hit_dmg = 0
                self.log_event("enhanced_attacks_ended", unit=unit.name)

        # Gunslinger: every Nth attack deals bonus physical damage
        if hasattr(unit, "_gunslinger_attack_counter"):
            unit._gunslinger_attack_counter += 1
            if unit._gunslinger_attack_counter >= unit._gunslinger_attack_interval:
                unit._gunslinger_attack_counter = 0
                bonus = unit._gunslinger_bonus_damage
                if bonus > 0 and unit.target and unit.target.is_alive:
                    self.apply_damage(
                        unit, unit.target, bonus, DamageType.PHYSICAL, "gunslinger_proc"
                    )

        # Gain mana (role-based)
        base_mana = self.MANA_PER_ATTACK_BY_ROLE.get(unit.role, self.MANA_PER_ATTACK_DEFAULT)
        mana_per_attack = base_mana + unit.stats.mana_regen
        self.gain_mana(unit, mana_per_attack, source="attack")

        # Item on-hit effects
        for item in unit.items:
            if item.on_hit:
                item.on_hit(self, unit, unit.target)

        # Red Buff / Morellonomicon burn now handled via item_effects.py on_hit/on_damage_dealt

    def _post_ability_cast(self, unit: Unit):
        """Shared post-ability-cast logic: item on-ability effects + Ionic Spark reaction."""
        # Trigger item on-ability effects
        for item in unit.items:
            if item.on_ability_cast:
                item.on_ability_cast(self, unit)

        # Ionic Spark reactive damage: enemies with Ionic Spark within 2 hexes
        # deal 150% of caster's max mana as magic damage to the caster.
        # Only check units with the cached _has_ionic_spark flag.
        if self._ionic_spark_units:
            dist_lut = HexGrid._DISTANCE_LUT
            spark_damage = unit.stats.max_mana * 1.50
            for enemy in self._ionic_spark_units:
                if not enemy.is_alive or enemy.team == unit.team:
                    continue
                if dist_lut[enemy.position][unit.position] <= 2:
                    final_dmg, _ = self.calculate_damage(
                        enemy, unit, spark_damage, DamageType.MAGIC, can_crit=False
                    )
                    self.apply_damage(enemy, unit, final_dmg, DamageType.MAGIC, "ionic_spark_react")

    def cast_ability(self, unit: Unit, enemies: List[Unit], allies: List[Unit]):
        """Cast unit's ability."""
        if not unit.ability:
            return

        ability = unit.ability
        unit.abilities_cast += 1

        # Get champion data for special ability handling
        champ_data = self.champions.get(unit.api_name, {})
        ability_vars = champ_data.get("ability", {}).get("variables", {})

        # Try champion-specific ability handler first
        if self.champion_abilities:
            if self.champion_abilities.cast(unit, enemies, allies, ability_vars):
                self._post_ability_cast(unit)
                self.log_event("ability_cast", unit=unit.name, ability=ability.name, targets=[])
                return  # Ability fully handled by champion-specific code

        # ==========================
        # FIZZ - Playful Trickster
        # ==========================
        # Fizz becomes UNTARGETABLE, leaps to farthest enemy within 4 hexes,
        # deals AoE damage on landing, then gains attack speed + on-hit magic damage for 4 attacks
        if unit.api_name == "TFT16_Fizz":
            # Find farthest enemy within 4 hexes
            enemies_in_range = [
                e
                for e in enemies
                if e.is_alive
                and e.is_targetable
                and HexGrid.hex_distance(unit.position, e.position) <= 4
            ]

            if not enemies_in_range:
                # No enemies in range - find closest enemy instead
                enemies_in_range = [e for e in enemies if e.is_alive and e.is_targetable]

            if enemies_in_range:
                # Target the farthest enemy in range
                target = max(
                    enemies_in_range, key=lambda e: HexGrid.hex_distance(unit.position, e.position)
                )

                # Become untargetable during leap (brief moment)
                unit.is_targetable = False
                unit.untargetable_duration = 0.3  # Brief untargetable during leap

                # Get ability damage values
                ap_dmg_data = ability_vars.get("APDamage")
                base_damage = _star_val(ap_dmg_data, unit.star_level, 150)

                # Get enhanced attack values
                as_bonus_data = ability_vars.get("ASBonus") or ability_vars.get("AttackSpeed")
                as_bonus = (
                    _star_val(as_bonus_data, unit.star_level, 100) / 100
                )  # Convert to decimal
                on_hit_data = ability_vars.get("OnHitDamage") or ability_vars.get("APOnHit")
                on_hit_dmg = _star_val(on_hit_data, unit.star_level, 50)
                num_attacks_data = ability_vars.get("NumAttacks")
                num_enhanced = int(_star_val(num_attacks_data, unit.star_level, 4))

                # Find position adjacent to target
                target_neighbors = HexGrid.get_neighbors(target.position)
                valid_spots = [n for n in target_neighbors if n not in self.get_occupied_hexes()]

                if valid_spots:
                    # Teleport to position adjacent to target
                    old_pos = unit.position
                    self.set_unit_position(unit, valid_spots[0])
                    self.log_event(
                        "fizz_leap",
                        unit=unit.name,
                        from_pos=old_pos,
                        to_pos=unit.position,
                        target=target.name,
                    )

                # Deal AoE damage on landing
                landing_targets = self.get_enemies_in_range(unit, 1, enemies)
                for enemy in landing_targets:
                    final_damage, _ = self.calculate_damage(
                        unit,
                        enemy,
                        base_damage + unit.stats.ap,
                        DamageType.MAGIC,
                        can_crit=True,
                        is_ability=True,
                    )
                    self.apply_damage(unit, enemy, final_damage, DamageType.MAGIC, "fizz_landing")

                # Grant enhanced attacks
                unit.enhanced_attacks_remaining = num_enhanced
                unit.enhanced_attack_bonus_as = as_bonus
                unit.enhanced_attack_on_hit_dmg = on_hit_dmg + (
                    unit.stats.ap * 0.5
                )  # Scales with AP
                unit.stats.attack_speed += as_bonus

                self.log_event(
                    "fizz_enhanced",
                    unit=unit.name,
                    bonus_as=as_bonus,
                    on_hit=unit.enhanced_attack_on_hit_dmg,
                    attacks=num_enhanced,
                )

            # Reset mana
            unit.stats.mana = 0

            # Shared post-cast logic (item effects + Ionic Spark reaction)
            self._post_ability_cast(unit)

            self.log_event(
                "ability_cast",
                unit=unit.name,
                ability=ability.name,
                targets=[t.name for t in enemies_in_range[:1]],
            )
            return  # Fizz ability fully handled

        # Handle Kai'Sa (and other FormSwapper champions) - uses higher of AD or AP damage
        if "FormSwapper" in unit.role:
            ad_dmg_data = ability_vars.get("ADDamage")
            ap_dmg_data = ability_vars.get("APDamage")

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
            num_targets_data = ability_vars.get("NumTargets")
            num_targets = int(_star_val(num_targets_data, unit.star_level, 4))
            num_missiles_data = ability_vars.get("NumMissiles")
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
        if "Tank" in unit.role:
            # Check for armor scaling (e.g., Braum's ArmorDamage)
            armor_dmg_data = ability_vars.get("ArmorDamage")
            if armor_dmg_data:
                armor_scaling = _star_val(armor_dmg_data, unit.star_level, 0)
                total_damage += unit.stats.armor * armor_scaling

            # Check for HP scaling (e.g., percentage of max HP damage)
            hp_pct_data = ability_vars.get("HealthPercent") or ability_vars.get(
                "PercentHealthDamage"
            )
            if hp_pct_data:
                hp_scaling = _star_val(hp_pct_data, unit.star_level, 0)
                total_damage += unit.stats.max_hp * hp_scaling

            # Check for shield abilities (Galio, Nautilus, Shen, Poppy)
            shield_data = (
                ability_vars.get("Shield")
                or ability_vars.get("ShieldAmt")
                or ability_vars.get("APShield")
            )
            if shield_data:
                shield_amount = _star_val(shield_data, unit.star_level, 0)
                # Nautilus also has percent HP shield
                pct_hp_shield = ability_vars.get("PercentHealthShield")
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
            center = unit.target.position if unit.target else unit.position  # noqa: F841
            targets = self.get_enemies_in_range(unit, ability.aoe_radius, enemies)
            targets = targets[: ability.num_targets]

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
                    unit, target, total_damage, ability.damage_type, can_crit=True, is_ability=True
                )
                self.apply_damage(
                    unit, target, final_damage, ability.damage_type, f"ability:{ability.name}"
                )

            elif ability.ability_type == AbilityType.HEAL:
                self.heal_unit(target, total_damage, f"ability:{ability.name}")

            elif ability.ability_type == AbilityType.SHIELD:
                self.apply_shield(target, total_damage, f"ability:{ability.name}")

        # Reset mana
        unit.stats.mana = 0

        # Shared post-cast logic (item effects + Ionic Spark reaction)
        self._post_ability_cast(unit)

        self.log_event(
            "ability_cast", unit=unit.name, ability=ability.name, targets=[t.name for t in targets]
        )

    def move_unit_towards(self, unit: Unit, target_pos: Tuple[int, int]):
        """Move unit one step towards target position."""
        if unit.position == target_pos:
            return

        occupied = self.get_occupied_hexes()
        occupied.discard(unit.position)  # Current pos is fine

        # Use A* pathfinding (matches Rust engine for parity)
        path = HexGrid.find_path(unit.position, target_pos, occupied)
        if path:
            old_pos = unit.position
            self.set_unit_position(unit, path[0])
            if self.logging_enabled:
                self.log_event("move", unit=unit.name, from_pos=old_pos, to_pos=path[0])

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
                    self.set_unit_position(unit, unit.untargetable_return_pos)
                    unit.untargetable_return_pos = None
                    self.log_event("teleport_return", unit=unit.name, position=unit.position)
            return  # Cannot act while untargetable (unless it's Fizz mid-leap)

        # Handle stun/fear (both fully disable)
        if unit.stun_duration > 0:
            unit.stun_duration -= self.tick_rate
            # Apply tenacity to reduce remaining duration
            tenacity = getattr(unit, "_tenacity", 0)
            if tenacity > 0:
                unit.stun_duration -= self.tick_rate * tenacity
            if unit.state not in (UnitState.FEARED, UnitState.TAUNTED, UnitState.ROOTED):
                unit.state = UnitState.STUNNED
            # Fear: random movement away (treated like stun but moves)
            if unit.state == UnitState.FEARED and unit.stun_duration > 0:
                neighbors = HexGrid.get_neighbors(unit.position)
                occupied = self.get_occupied_hexes()
                valid = [n for n in neighbors if n not in occupied]
                if valid:
                    self.set_unit_position(unit, random.choice(valid))
                return
            # Taunt: forced to attack taunter (can attack, not move freely)
            if unit.state == UnitState.TAUNTED:
                taunt_src = getattr(unit, "_taunt_source", None)
                if taunt_src and taunt_src.is_alive:
                    unit.target = taunt_src
                    # Fall through to attack logic below
                else:
                    unit.state = UnitState.IDLE
                    unit.stun_duration = 0
            # Root: can't move but can attack/cast in range
            elif unit.state == UnitState.ROOTED:
                pass  # Fall through but skip movement
            else:
                return  # Regular stun: fully disabled

        # Update buffs
        unit.buffs = [b for b in unit.buffs if b.duration > 0]
        for buff in unit.buffs:
            buff.duration -= self.tick_rate

        # Passive item effects (Guinsoo's, Archangel's, Quicksilver, Dragon's Claw, etc.)
        for item in unit.items:
            if item.passive:
                item.passive(self, unit)

        # --- Trait combat-time effects ---

        # Shurima: heal over time
        if hasattr(unit, "_shurima_heal_per_sec"):
            shurima_last = getattr(unit, "_shurima_last_tick", -1.0)
            if self.time - shurima_last >= 1.0:
                unit._shurima_last_tick = self.time
                self.heal_unit(unit, unit._shurima_heal_per_sec, "shurima")

        # Ixtal: heal over time
        if hasattr(unit, "_ixtal_heal_per_sec"):
            ixtal_last = getattr(unit, "_ixtal_last_tick", -1.0)
            if self.time - ixtal_last >= 1.0:
                unit._ixtal_last_tick = self.time
                self.heal_unit(unit, unit._ixtal_heal_per_sec, "ixtal")

        # Warden: shield at HP thresholds
        if hasattr(unit, "_warden_shield_percent"):
            hp_pct = unit.stats.hp / unit.stats.max_hp if unit.stats.max_hp > 0 else 1.0
            if not unit._warden_first_triggered and hp_pct < unit._warden_first_threshold:
                unit._warden_first_triggered = True
                shield = unit.stats.max_hp * unit._warden_shield_percent
                unit.stats.shield += shield
                self.log_event(
                    "warden_shield", unit=unit.name, shield=round(shield, 1), threshold="first"
                )
            if not unit._warden_second_triggered and hp_pct < unit._warden_second_threshold:
                unit._warden_second_triggered = True
                shield = unit.stats.max_hp * unit._warden_shield_percent
                unit.stats.shield += shield
                self.log_event(
                    "warden_shield", unit=unit.name, shield=round(shield, 1), threshold="second"
                )

        # Slayer: bonus AD scaling with missing HP (checked once per second)
        if hasattr(unit, "_slayer_ad_increase"):
            slayer_last = getattr(unit, "_slayer_last_tick", -1.0)
            if self.time - slayer_last >= 1.0:
                unit._slayer_last_tick = self.time
                hp_pct = unit.stats.hp / unit.stats.max_hp if unit.stats.max_hp > 0 else 1.0
                missing_pct = 1.0 - hp_pct
                # AD bonus = base_ad * ad_increase * missing_hp_percent
                new_bonus = unit.base_stats.ad * unit._slayer_ad_increase * missing_pct
                old_bonus = getattr(unit, "_slayer_current_bonus", 0.0)
                unit.stats.ad += new_bonus - old_bonus
                unit._slayer_current_bonus = new_bonus

        # Juggernaut: increased DR below 50% HP
        if hasattr(unit, "_juggernaut_increased_dr"):
            hp_pct = unit.stats.hp / unit.stats.max_hp if unit.stats.max_hp > 0 else 1.0
            was_below = getattr(unit, "_juggernaut_below_50", False)
            if hp_pct < 0.5 and not was_below:
                unit._juggernaut_below_50 = True
                unit.stats.damage_reduction += unit._juggernaut_increased_dr
            elif hp_pct >= 0.5 and was_below:
                unit._juggernaut_below_50 = False
                unit.stats.damage_reduction -= unit._juggernaut_increased_dr

        # Zaun: shimmer fuse - delayed AS + durability burst
        if hasattr(unit, "_zaun_shimmer_as") and not getattr(
            unit, "_zaun_shimmer_triggered", False
        ):
            if self.time >= unit._zaun_initial_delay:
                hp_pct = unit.stats.hp / unit.stats.max_hp if unit.stats.max_hp > 0 else 1.0
                heal_threshold = getattr(unit, "_zaun_heal_threshold", 0.60)
                if hp_pct < heal_threshold:
                    unit._zaun_shimmer_triggered = True
                    unit._zaun_shimmer_active = True
                    unit._zaun_shimmer_end = self.time + unit._zaun_shimmer_duration
                    unit.stats.attack_speed += unit._zaun_shimmer_as
                    unit.stats.damage_reduction += unit._zaun_shimmer_durability
                    # Tier 5+: heal on activation
                    max_heal = getattr(unit, "_zaun_max_health_heal", 0)
                    if max_heal > 0:
                        self.heal_unit(unit, unit.stats.max_hp * max_heal, "zaun_shimmer")
                    self.log_event(
                        "zaun_shimmer_activate",
                        unit=unit.name,
                        as_bonus=unit._zaun_shimmer_as,
                        dr_bonus=unit._zaun_shimmer_durability,
                    )
        # Zaun shimmer expiry
        if getattr(unit, "_zaun_shimmer_active", False):
            if self.time >= unit._zaun_shimmer_end:
                unit._zaun_shimmer_active = False
                unit.stats.attack_speed -= unit._zaun_shimmer_as
                unit.stats.damage_reduction -= unit._zaun_shimmer_durability
                self.log_event("zaun_shimmer_expire", unit=unit.name)

        # Quickstriker: bonus AS based on target's missing HP (checked once per second)
        if hasattr(unit, "_quickstriker_min_as") and unit.target and unit.target.is_alive:
            qs_last = getattr(unit, "_qs_last_tick", -1.0)
            if self.time - qs_last >= 1.0:
                unit._qs_last_tick = self.time
                t_hp_pct = (
                    unit.target.stats.hp / unit.target.stats.max_hp
                    if unit.target.stats.max_hp > 0
                    else 1.0
                )
                t_missing = 1.0 - t_hp_pct
                new_bonus = (
                    unit._quickstriker_min_as
                    + (unit._quickstriker_max_as - unit._quickstriker_min_as) * t_missing
                )
                old_bonus = getattr(unit, "_qs_current_bonus", 0.0)
                unit.stats.attack_speed += new_bonus - old_bonus
                unit._qs_current_bonus = new_bonus

        # Find/update target
        if not unit.target or not unit.target.is_alive:
            unit.target = self.find_target(unit, enemies)

        if not unit.target:
            unit.state = UnitState.IDLE
            return

        # Check if in range
        in_range = self.can_attack(unit, unit.target)

        # Movement if not in range (rooted units cannot move)
        if not in_range:
            if unit.state == UnitState.ROOTED:
                return  # Rooted: can't move to get in range, just wait
            unit.state = UnitState.MOVING

            # Move towards target (simplified - one hex per 0.5s)
            if unit.attack_cooldown <= 0:
                # Find adjacent hex to target that's in range
                target_neighbors = HexGrid._NEIGHBOR_LUT[unit.target.position]
                occupied = self.get_occupied_hexes()
                dist_lut = HexGrid._DISTANCE_LUT[unit.position]

                best_spot = None
                best_dist = 999
                for n in target_neighbors:
                    if n not in occupied:
                        d = dist_lut[n]
                        if d < best_dist:
                            best_dist = d
                            best_spot = n

                if best_spot is not None:
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
            # Allow champion-specific handlers to override the cast lockout
            if getattr(unit, "_custom_cast_time", False):
                unit._custom_cast_time = False
            else:
                unit.attack_cooldown = unit.ability.cast_time
            return

        # Auto attack
        unit.state = UnitState.ATTACKING
        unit.attack_cooldown -= self.tick_rate

        if unit.attack_cooldown <= 0:
            # Enforce attack speed hard cap
            effective_as = min(unit.stats.attack_speed, self.ATTACK_SPEED_CAP)
            attack_interval = 1.0 / effective_as
            unit.attack_cooldown = attack_interval
            self.process_attack(unit)
