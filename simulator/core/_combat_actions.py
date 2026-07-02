"""Combat action methods: damage, heal, shield, CC, debuffs."""

from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING, Optional, Tuple

from ._combat_types import DamageType, DotEffect, UnitState
from ._hex_grid import HexGrid

if TYPE_CHECKING:
    from ._combat_types import Unit

# Optionally accelerate damage math with Cython (built separately)
try:
    from .combat_fast import (
        CYTHON_AVAILABLE as _CYTHON_OK,
    )
    from .combat_fast import (
        calculate_damage_fast as _cy_calculate_damage,
    )
except ImportError:
    _cy_calculate_damage = None
    _CYTHON_OK = False

_log = logging.getLogger(__name__)


class _CombatActionsMixin:
    """Mixin providing damage/heal/shield/CC methods for CombatEngine."""

    def calculate_damage(
        self,
        attacker: Unit,
        defender: Unit,
        base_damage: float,
        damage_type: DamageType,
        can_crit: bool = True,
        is_ability: bool = False,
    ) -> Tuple[float, bool]:
        """Calculate final damage after all modifiers.

        Uses Cython-accelerated math when available (~5-10x faster).
        """
        # Compute Longshot bonus (needs position LUT)
        longshot_per_hex = getattr(attacker, "_longshot_per_hex", 0)
        longshot_bonus = 0.0
        if longshot_per_hex > 0:
            distance = HexGrid._DISTANCE_LUT[attacker.position][defender.position]
            longshot_bonus = longshot_per_hex * distance

        # Map damage type to int for Cython: 0=physical, 1=magic, 2=true
        if damage_type == DamageType.PHYSICAL:
            dtype_int = 0
        elif damage_type == DamageType.MAGIC:
            dtype_int = 1
        else:
            dtype_int = 2

        # Vanquisher lets abilities crit too
        has_vanquisher = getattr(attacker, "_vanquisher_ability_crit", False)
        jg_or_vanq = attacker._has_jeweled_gauntlet or has_vanquisher

        if _CYTHON_OK:
            # Only consume RNG when a crit check would actually execute,
            # matching the Python fallback path to preserve RNG parity.
            if can_crit and (not is_ability or jg_or_vanq):
                rng_roll = random.random()
            else:
                rng_roll = 1.0  # No crit possible; don't consume RNG
            return _cy_calculate_damage(
                base_damage,
                attacker.stats.damage_amp,
                attacker.stats.crit_chance,
                attacker.stats.crit_multiplier,
                defender.stats.armor,
                defender.stats.magic_resist,
                defender.stats.damage_reduction,
                defender.stats.max_hp,
                dtype_int,
                can_crit,
                is_ability,
                jg_or_vanq,
                attacker._has_giant_slayer,
                getattr(defender, "_dragonborn_protected", False),
                longshot_bonus,
                rng_roll,
            )

        # Pure-Python fallback
        damage = base_damage
        damage *= 1 + attacker.stats.damage_amp + longshot_bonus

        did_crit = False
        if can_crit:
            if not is_ability or jg_or_vanq:
                if random.random() < attacker.stats.crit_chance:
                    damage *= attacker.stats.crit_multiplier
                    did_crit = True

        if damage_type == DamageType.PHYSICAL:
            resist = max(0, defender.stats.armor)
            damage *= 100 / (100 + resist)
        elif damage_type == DamageType.MAGIC:
            resist = max(0, defender.stats.magic_resist)
            damage *= 100 / (100 + resist)

        if defender.stats.damage_reduction > 0:
            damage *= 1 - defender.stats.damage_reduction

        if is_ability and getattr(defender, "_dragonborn_protected", False):
            damage *= 0.90

        if attacker._has_giant_slayer and defender.stats.max_hp > 1750:
            damage *= 1.15

        return max(0, damage), did_crit

    def check_hp_threshold_effects(self, unit: Unit):
        """Check for item effects that trigger at HP thresholds.

        - Edge of Night: At 60% HP, become untargetable briefly, cleanse negative effects
        - Zhonya's Paradox: At HP threshold, become invulnerable
        """
        hp_percent = unit.stats.hp / unit.stats.max_hp

        # Edge of Night - triggers at 60% HP (one time per combat)
        # Effect: untargetable, shed negative effects, heal 30% missing HP
        has_edge_of_night = any(
            i.name in ["EdgeOfNight", "TFT_Item_EdgeOfNight"] for i in unit.items
        )
        if has_edge_of_night and hp_percent <= 0.60:
            if not hasattr(unit, "_edge_of_night_triggered"):
                unit._edge_of_night_triggered = True

                # Become untargetable for 1.5 seconds
                unit.is_targetable = False
                unit.untargetable_duration = 1.5
                unit.state = UnitState.UNTARGETABLE

                # Cleanse negative effects (remove stun, debuffs)
                unit.stun_duration = 0
                unit.buffs = [b for b in unit.buffs if b.stacks > 0]

                # Heal 30% of missing HP
                missing_hp = unit.stats.max_hp - unit.stats.hp
                self.heal_unit(unit, missing_hp * 0.30, "edge_of_night")

                self.log_event(
                    "edge_of_night_proc", unit=unit.name, hp_percent=round(hp_percent * 100, 1)
                )

        # Zhonya's Paradox - triggers at HP threshold
        has_zhonyas = any(
            i.name in ["ZhonyasParadox", "TFT16_Item_ZhonyasParadox"] for i in unit.items
        )
        if has_zhonyas and hp_percent <= 0.50:
            if not hasattr(unit, "_zhonyas_triggered"):
                unit._zhonyas_triggered = True

                # Become untargetable and invulnerable for 2.5 seconds
                unit.is_targetable = False
                unit.untargetable_duration = 2.5
                unit.state = UnitState.UNTARGETABLE

                self.log_event(
                    "zhonyas_proc", unit=unit.name, hp_percent=round(hp_percent * 100, 1)
                )

        # Radiant Edge of Night - triggers at 60% HP with full heal
        has_radiant_edge = any(i.name in ["RadiantEdgeOfNight"] for i in unit.items)
        if has_radiant_edge and hp_percent <= 0.60:
            if not hasattr(unit, "_radiant_edge_triggered"):
                unit._radiant_edge_triggered = True

                # Become untargetable for 1.5 seconds
                unit.is_targetable = False
                unit.untargetable_duration = 1.5
                unit.state = UnitState.UNTARGETABLE

                # Cleanse and heal to full HP
                unit.stun_duration = 0
                missing_hp = unit.stats.max_hp - unit.stats.hp
                self.heal_unit(unit, missing_hp, "radiant_edge_of_night")

                self.log_event(
                    "radiant_edge_proc", unit=unit.name, hp_percent=round(hp_percent * 100, 1)
                )

    def gain_mana(self, unit: Unit, amount: float, source: str = "mana") -> float:
        """Gain mana for a unit, respecting Invoker and max mana cap.

        Returns the actual mana gained (after cap).
        """
        if amount <= 0 or unit.stats.max_mana <= 0:
            return 0.0

        invoker_increase = getattr(unit, "_invoker_mana_increase", 0.0)
        if invoker_increase:
            amount *= 1.0 + float(invoker_increase)

        before = unit.stats.mana
        unit.stats.mana = min(unit.stats.mana + amount, unit.stats.max_mana)
        return unit.stats.mana - before

    def apply_damage(
        self,
        attacker: Optional[Unit],
        defender: Unit,
        damage: float,
        damage_type: DamageType,
        source: str = "attack",
    ) -> float:
        """Apply damage to a unit and return actual damage dealt."""
        if not defender.is_alive:
            return 0

        # Check if defender is untargetable (shouldn't take damage)
        if not defender.is_targetable:
            return 0

        attacker_name = attacker.name if attacker is not None else "system"

        # Damage shield first
        if defender.stats.shield > 0:
            if damage <= defender.stats.shield:
                defender.stats.shield -= damage
                self.log_event(
                    "shield_absorb", attacker=attacker_name, defender=defender.name, damage=damage
                )
                return 0
            else:
                damage -= defender.stats.shield
                defender.stats.shield = 0

        # Mana on damage taken (1% pre-mitigation + 3% post-mitigation, capped)
        pre_mit_mana = damage * 0.01  # 1% of pre-mitigation damage
        post_mit_mana = min(damage, defender.stats.hp) * 0.03  # 3% of actual damage
        mana_gain = min(pre_mit_mana + post_mit_mana, self.MANA_ON_DAMAGE_TAKEN_CAP)
        self.gain_mana(defender, mana_gain, source="damage_taken")

        # Apply damage
        actual_damage = min(damage, defender.stats.hp)
        defender.stats.hp -= actual_damage
        defender.total_damage_taken += actual_damage
        if attacker is not None:
            attacker.total_damage_dealt += actual_damage

        # Omnivamp healing
        if attacker is not None and attacker.stats.omnivamp > 0:
            heal_amount = actual_damage * attacker.stats.omnivamp
            self.heal_unit(attacker, heal_amount, "omnivamp")

        # Check for death
        if defender.stats.hp <= 0:
            defender.stats.hp = 0
            defender.is_alive = False
            defender.state = UnitState.DEAD
            self._alive_dirty = True
            self._occupied_dirty = True

            # Freljord Ice Block: stun enemies on death
            if self.trait_manager:
                self.trait_manager.check_freljord_on_death(defender, self.units)

            # Check for Immortal resurrection (Zaahen)
            if self.champion_abilities and self.champion_abilities.check_immortal_resurrection(
                defender
            ):
                # Unit was resurrected - don't award takedown
                pass
            else:
                if attacker is not None:
                    self._debug_takedowns.append(
                        {
                            "killer_team": int(attacker.team),
                            "killer_api_name": attacker.api_name,
                            "victim_team": int(defender.team),
                            "victim_api_name": defender.api_name,
                        }
                    )
                # Award Bilgewater serpents for takedown (attacker's team)
                if attacker is not None and attacker.team != defender.team:
                    bg_state = self.trait_manager.get_team_state(attacker.team)
                    if "Bilgewater" in attacker.traits and bg_state.bilgewater_count >= 3:
                        player = getattr(self, "_round_persistent_players", {}).get(attacker.team)
                        if player is not None:
                            serpents = self.trait_manager.BILGEWATER_SERPENTS_PER_TAKEDOWN
                            player.add_bilgewater_serpents(serpents)
                            if serpents > 0:
                                self.log_event(
                                    "bilgewater_takedown",
                                    killer=attacker.name,
                                    victim=defender.name,
                                    serpents=serpents,
                                    total=getattr(player, "bilgewater_serpents", None),
                                )

                # Harvester: grant mana to Harvester units on enemy death
                if attacker is not None:
                    allies_team = self._alive_team0 if attacker.team == 0 else self._alive_team1
                    for ally in allies_team:
                        harvest_mana = getattr(ally, "_harvester_mana_per_kill", 0)
                        if harvest_mana > 0 and ally.is_alive:
                            self.gain_mana(ally, harvest_mana, source="harvester_kill")

                # Award Shadow Isles souls for takedown
                if attacker is not None and attacker.team != defender.team:
                    si_state = self.trait_manager.get_team_state(attacker.team)
                    if "Shadow Isles" in attacker.traits and si_state.shadow_isles_count >= 2:
                        # Get victim's cost (from champion data)
                        victim_data = self.champions.get(defender.api_name, {})
                        victim_cost = victim_data.get("cost", 1)
                        victim_star = defender.star_level

                        souls = self.trait_manager.award_soul(
                            attacker.team, victim_cost, victim_star
                        )
                        if souls > 0:
                            self.log_event(
                                "shadow_isles_soul",
                                killer=attacker.name,
                                victim=defender.name,
                                souls=souls,
                                total=si_state.shadow_isles_souls,
                                victim_cost=victim_cost,
                                victim_star=victim_star,
                            )

        if self.logging_enabled:
            self.log_event(
                "damage",
                source=source,
                attacker=attacker_name,
                defender=defender.name,
                damage=round(actual_damage, 1),
                damage_type=damage_type.value,
                defender_hp=round(defender.stats.hp, 1),
                defender_alive=defender.is_alive,
            )

        # Juggernaut: heal allies for % of damage taken
        if defender.is_alive and hasattr(defender, "_juggernaut_heal_ratio") and actual_damage > 0:
            heal_amt = actual_damage * defender._juggernaut_heal_ratio
            if heal_amt > 0:
                allies = [
                    u
                    for u in (self._alive_team0 if defender.team == 0 else self._alive_team1)
                    if u.is_alive and u is not defender
                ]
                for ally in allies:
                    self.heal_unit(ally, heal_amt, "juggernaut")

        # Check for HP threshold effects (Edge of Night, Zhonya's)
        if defender.is_alive:
            self.check_hp_threshold_effects(defender)

        # Trigger item on-damage-dealt effects for attacker
        if attacker is not None:
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
        """Heal a unit. Reduced by 33% if Wounded."""
        if not unit.is_alive:
            return

        # Check Wound debuff (33% healing reduction)
        wound_until = getattr(unit, "_wound_until", 0)
        if self.time < wound_until:
            amount *= 0.67

        actual_heal = min(amount, unit.stats.max_hp - unit.stats.hp)
        unit.stats.hp += actual_heal
        unit.total_healing += actual_heal

        if actual_heal > 0 and self.logging_enabled:
            self.log_event(
                "heal",
                unit=unit.name,
                amount=round(actual_heal, 1),
                source=source,
                hp=round(unit.stats.hp, 1),
            )

    def apply_shield(self, unit: Unit, amount: float, source: str = "shield"):
        """Apply shield to a unit."""
        if not unit.is_alive:
            return

        unit.stats.shield += amount
        self.log_event(
            "shield",
            unit=unit.name,
            amount=round(amount, 1),
            source=source,
            total_shield=round(unit.stats.shield, 1),
        )

    def apply_burn(
        self, attacker: Unit, target: Unit, burn_pct: float, duration: float, source: str = "burn"
    ):
        """Apply Burn debuff: X% max HP as true damage per second for duration.

        Damage ticks once per second over the full duration.
        """
        if not target.is_alive:
            return
        damage_per_tick = target.stats.max_hp * burn_pct
        dot = DotEffect(
            source_unit=attacker,
            damage_per_tick=damage_per_tick,
            tick_interval=1.0,
            remaining_duration=duration,
            damage_type=DamageType.TRUE,
            source_name=source,
            time_since_last_tick=0.0,
        )
        target.dot_effects.append(dot)
        self.log_event(
            "burn_applied",
            target=target.name,
            dps=round(damage_per_tick, 1),
            duration=duration,
            source=source,
        )

    def apply_cc(
        self,
        target: Unit,
        cc_type: str,
        duration: float,
        source: str = "cc",
        source_unit: "Unit" = None,
    ):
        """Apply crowd control effect to a unit.

        Args:
            target: Unit to CC
            cc_type: 'stun', 'fear', 'taunt', 'root'
            duration: Duration in seconds
            source: Source name for logging
            source_unit: For taunt, the unit that taunted
        """
        if not target.is_alive:
            return
        # Check CC immunity
        if hasattr(target, "immune_until") and self.time < target.immune_until:
            return
        # Apply tenacity
        tenacity = getattr(target, "_tenacity", 0)
        if tenacity > 0:
            duration *= 1 - tenacity
        if duration <= 0:
            return

        if cc_type == "fear":
            target.state = UnitState.FEARED
            target.stun_duration = max(target.stun_duration, duration)
        elif cc_type == "taunt":
            target.state = UnitState.TAUNTED
            target.stun_duration = max(target.stun_duration, duration)
            target._taunt_source = source_unit
        elif cc_type == "root":
            target.state = UnitState.ROOTED
            target.stun_duration = max(target.stun_duration, duration)
        else:  # stun
            target.state = UnitState.STUNNED
            target.stun_duration = max(target.stun_duration, duration)

        self.log_event(
            "cc_applied",
            target=target.name,
            cc_type=cc_type,
            duration=round(duration, 2),
            source=source,
        )

    def apply_wound(self, target: Unit, duration: float, source: str = "wound"):
        """Apply Wound debuff: reduce healing received by 33% for duration.

        Simplified: sets a marker on the unit; heal_unit checks it.
        """
        if not target.is_alive:
            return
        target._wound_until = self.time + duration
        self.log_event("wound", target=target.name, duration=duration, source=source)

    def apply_sunder(self, target: Unit, pct: float, duration: float, source: str = "sunder"):
        """Apply Sunder debuff: reduce armor by X% for duration.

        Stacks are tracked; armor is restored when the debuff expires.
        Re-applying refreshes the duration but does not double-stack from same source.
        """
        if not target.is_alive:
            return
        # Track active sunders: list of (reduction_amount, expiry_time, source)
        if not hasattr(target, "_sunder_stacks"):
            target._sunder_stacks = []
        expiry = self.time + duration
        # Refresh existing sunder from same source instead of stacking
        for i, (red, _exp, src) in enumerate(target._sunder_stacks):
            if src == source:
                target._sunder_stacks[i] = (red, expiry, src)
                self.log_event("sunder_refresh", target=target.name, source=source)
                return
        # New sunder from this source
        reduction = target.stats.armor * pct
        target.stats.armor = max(0, target.stats.armor - reduction)
        target._sunder_stacks.append((reduction, expiry, source))
        self.log_event("sunder", target=target.name, reduction=round(reduction, 1), source=source)

    def apply_shred(self, target: Unit, pct: float, duration: float, source: str = "shred"):
        """Apply Shred debuff: reduce magic resist by X% for duration.

        Stacks are tracked; MR is restored when the debuff expires.
        Re-applying refreshes the duration but does not double-stack from same source.
        """
        if not target.is_alive:
            return
        if not hasattr(target, "_shred_stacks"):
            target._shred_stacks = []
        expiry = self.time + duration
        # Refresh existing shred from same source
        for i, (red, _exp, src) in enumerate(target._shred_stacks):
            if src == source:
                target._shred_stacks[i] = (red, expiry, src)
                self.log_event("shred_refresh", target=target.name, source=source)
                return
        # New shred from this source
        reduction = target.stats.magic_resist * pct
        target.stats.magic_resist = max(0, target.stats.magic_resist - reduction)
        target._shred_stacks.append((reduction, expiry, source))
        self.log_event("shred", target=target.name, reduction=round(reduction, 1), source=source)
