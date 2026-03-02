"""Combat runners: combat simulation loops, round management, trait helpers."""

from __future__ import annotations

import logging
import random
from copy import deepcopy
from typing import Dict, List, Tuple

from ._combat_types import (
    Ability,
    AbilityType,
    CombatStats,
    DamageType,
    TargetingType,
    Unit,
    UnitState,
)

_log = logging.getLogger(__name__)


class _CombatRunnersMixin:
    """Mixin providing combat simulation and round management for CombatEngine."""

    def tick(self):
        """Process one simulation tick."""
        self.time += self.tick_rate
        tick_rate = self.tick_rate  # Local var for tight loops

        # Refresh cached alive lists only when a unit has died
        if self._alive_dirty:
            self._alive_team0 = [u for u in self._alive_team0 if u.is_alive]
            self._alive_team1 = [u for u in self._alive_team1 if u.is_alive]
            self._alive_dirty = False

        team0 = self._alive_team0
        team1 = self._alive_team1

        # Build combined list once for this tick (reused below)
        all_alive = team0 + team1

        # Process DOT effects on all alive units
        for unit in all_alive:
            if not unit.dot_effects:
                continue
            remaining_dots = []
            for dot in unit.dot_effects:
                dot.remaining_duration -= tick_rate
                dot.time_since_last_tick += tick_rate
                if dot.time_since_last_tick >= dot.tick_interval:
                    dot.time_since_last_tick -= dot.tick_interval
                    if unit.is_alive:
                        self.apply_damage(
                            dot.source_unit,
                            unit,
                            dot.damage_per_tick,
                            dot.damage_type,
                            dot.source_name,
                        )
                if dot.remaining_duration > 0:
                    remaining_dots.append(dot)
            unit.dot_effects = remaining_dots

        # Expire sunder/shred debuffs and restore armor/MR
        current_time = self.time
        logging_on = self.logging_enabled
        for unit in all_alive:
            if not unit.is_alive:
                continue
            sunder = getattr(unit, "_sunder_stacks", None)
            if sunder:
                remaining = []
                for reduction, expiry, src in sunder:
                    if current_time >= expiry:
                        unit.stats.armor += reduction
                        if logging_on:
                            self.log_event(
                                "sunder_expired",
                                target=unit.name,
                                restored=round(reduction, 1),
                                source=src,
                            )
                    else:
                        remaining.append((reduction, expiry, src))
                unit._sunder_stacks = remaining
            shred = getattr(unit, "_shred_stacks", None)
            if shred:
                remaining = []
                for reduction, expiry, src in shred:
                    if current_time >= expiry:
                        unit.stats.magic_resist += reduction
                        if logging_on:
                            self.log_event(
                                "shred_expired",
                                target=unit.name,
                                restored=round(reduction, 1),
                                source=src,
                            )
                    else:
                        remaining.append((reduction, expiry, src))
                unit._shred_stacks = remaining

        # Piltover module fire at 8 seconds
        if self._piltover_data and current_time >= 8.0:
            for _team_id, pdata in self._piltover_data.items():
                if not pdata["fired"]:
                    pdata["fired"] = True
                    self._fire_piltover_module(pdata, team0, team1)

        # Check Noxus Atakhan summoning (only when Noxus is active)
        if self._has_noxus:
            self._check_noxus_atakhan_summon(team0, team1)
            self._check_atakhan_ruin()

        # Process units in random order to avoid bias.
        # Shuffle in-place on the already-built list (avoids extra allocation).
        random.shuffle(all_alive)

        for unit in all_alive:
            enemies = team1 if unit.team == 0 else team0
            allies = team0 if unit.team == 0 else team1
            self.process_unit_tick(unit, enemies, allies)

    def _fire_piltover_module(self, pdata: Dict, team0: List[Unit], team1: List[Unit]):
        """Apply Piltover module effects at 8 seconds into combat."""
        module = pdata["module"]
        team = [u for u in pdata["team"] if u.is_alive]
        piltover_units = [u for u in pdata["piltover_units"] if u.is_alive]
        team_id = pdata.get("team", [None])[0].team if team else 0
        enemies = team1 if team_id == 0 else team0

        self.log_event("piltover_module_fire", module=module)

        if module == "BlastShield":
            for u in team:
                shield = u.stats.max_hp * 0.18
                self.apply_shield(u, shield, "piltover_blast_shield")

        elif module == "ContinuumCogs":
            for u in team:
                u.stats.ap += 15

        elif module == "EMP":
            for e in enemies:
                if e.is_alive:
                    e.stats.max_mana += 15

        elif module == "KineticBarrier":
            for u in piltover_units:
                u.stats.armor += 65
                u.stats.magic_resist += 30

        elif module == "OverclockedCapacitors":
            for u in team:
                u.stats.attack_speed += 0.25

        elif module == "AccelerationGate":
            # Mark Piltover units for mana restore after cast
            for u in piltover_units:
                u._piltover_accel_gate = True

        elif module == "ArmorNullifier":
            for u in piltover_units:
                u.stats.damage_amp += 0.25

        elif module == "GigantificationRay":
            for u in piltover_units:
                hp_bonus = u.stats.max_hp * 0.28
                u.stats.hp += hp_bonus
                u.stats.max_hp += hp_bonus

        elif module == "MagnetronCoil":
            for u in piltover_units:
                u.stats.damage_amp += 0.18

        elif module == "MomentumDrive":
            # Cleanse CC and grant tenacity (50% stun duration reduction)
            for u in team:
                if u.state == UnitState.STUNNED:
                    u.state = UnitState.IDLE
                    u.stun_duration = 0
                u._tenacity = 0.50

        elif module == "TunedOscillator":
            # Increase healing/shielding by 28% (mark for heal_unit to check)
            for u in team:
                u._healing_amp = getattr(u, "_healing_amp", 0) + 0.28

        elif module == "ElectricalOverload":
            for e in enemies:
                if e.is_alive:
                    dmg = 100 + e.stats.max_hp * 0.10
                    self.apply_damage(None, e, dmg, DamageType.TRUE, "piltover_electrical_overload")

        elif module == "90CaliberNets":
            # Stun 3 highest DPS enemies for 2s
            alive_enemies = [e for e in enemies if e.is_alive]
            alive_enemies.sort(key=lambda e: e.total_damage_dealt, reverse=True)
            for e in alive_enemies[:3]:
                e.state = UnitState.STUNNED
                e.stun_duration = 2.0

    def _check_noxus_atakhan_summon(self, team0: List[Unit], team1: List[Unit]):
        """Check if enemy team has lost enough HP to trigger Atakhan summon.

        For each team with Noxus active, check if the ENEMY team has lost
        15% of their total starting HP. If so, summon Atakhan.
        """
        noxus_data = getattr(self, "_noxus_team_data", {})
        if not noxus_data:
            return

        for team_id, data in noxus_data.items():
            if data["summoned"]:
                continue

            # Enemy team is the opposite
            enemy_team = team1 if team_id == 0 else team0
            ally_team = team0 if team_id == 0 else team1

            # Calculate enemy total HP loss
            if not hasattr(data, "_enemy_starting_hp"):
                # Cache starting HP on first check
                total_max_hp = sum(u.stats.max_hp for u in enemy_team)
                # Include dead enemies (they lost all HP)
                all_enemies = [u for u in self.units if u.team != team_id]
                total_max_hp = sum(u.stats.max_hp for u in all_enemies)
                data["_enemy_starting_hp"] = total_max_hp

            starting_hp = data.get("_enemy_starting_hp", 0)
            if starting_hp <= 0:
                continue

            # Current enemy HP (alive units only)
            current_hp = sum(u.stats.hp for u in self.units if u.team != team_id and u.is_alive)
            hp_lost_pct = (starting_hp - current_hp) / starting_hp

            if hp_lost_pct >= data["hp_trigger"]:
                # Summon Atakhan!
                self._summon_atakhan(team_id, data, ally_team)
                data["summoned"] = True

    def _summon_atakhan(self, team_id: int, noxus_data: Dict, ally_team: List[Unit]):
        """Summon Atakhan onto the board for the given team.

        Creates Atakhan as a combat unit with stats scaled by:
        - Total Noxian star levels -> Atakhan's star level
        - Noxus count -> ability tier (3/5/7/10)
        """
        atakhan_star = noxus_data["atakhan_star"]
        noxus_count = noxus_data["count"]
        total_stars = noxus_data["total_stars"]

        # Get Atakhan stats for this star level
        stats = self.trait_manager.ATAKHAN_STATS.get(
            min(atakhan_star, 4), self.trait_manager.ATAKHAN_STATS[1]
        )

        # Calculate HP with per-star scaling
        base_hp = stats["hp"] + stats["per_star_hp"] * total_stars
        base_ad = stats["ad"] * (1.0 + stats["per_star_ad_pct"] * total_stars)
        base_ap_pct = stats["per_star_ap_pct"] * total_stars

        atakhan_stats = CombatStats(
            hp=base_hp,
            max_hp=base_hp,
            ad=base_ad,
            ap=base_ap_pct * 100,  # AP as flat value
            attack_speed=stats["as"],
            armor=stats["armor"],
            magic_resist=stats["mr"],
            range=1,
            mana=40 if atakhan_star >= 3 else 0,
            max_mana=85 if atakhan_star >= 3 else 0,
            crit_chance=0.25,
            crit_multiplier=1.4,
            omnivamp=stats["omnivamp"],
        )

        # Find a position to spawn (left side of board, behind allies)
        spawn_pos = self._find_atakhan_spawn(team_id, ally_team)

        atakhan = Unit(
            name="Atakhan",
            api_name="TFT16_Atakhan",
            star_level=atakhan_star,
            stats=atakhan_stats,
            base_stats=deepcopy(atakhan_stats),
            position=spawn_pos,
            team=team_id,
            traits=[],
            ability=Ability(
                name="Punish the Unworthy",
                ability_type=AbilityType.DAMAGE,
                damage_type=DamageType.MAGIC,
                targeting=TargetingType.CURRENT_TARGET,
                base_damage={1: stats["cleave_damage"]},
                ap_scaling=1.0,
                cast_time=0.5,
                aoe_radius=1,
                effects={
                    "noxus_count": noxus_count,
                    "damage_amp": stats["damage_amp"],
                    "dot_damage": stats["dot_damage"],
                    "dot_duration": stats["dot_duration"],
                },
            ),
            role="APTank",
            attack_windup=0.4,
        )

        # Mark as Atakhan for special handling
        atakhan._is_atakhan = True
        atakhan._atakhan_summon_time = self.time
        atakhan._atakhan_noxus_count = noxus_count
        atakhan._atakhan_ruin_timer = noxus_data["ruin_timer"]
        atakhan._atakhan_attacks_since_cleave = 0

        # Add to combat
        self.units.append(atakhan)
        ally_team.append(atakhan)
        self._invalidate_occupied_cache()

        # At 5+ Noxus: grant Noxians damage amp while Atakhan is alive
        if noxus_count >= 5 and stats["damage_amp"] > 0:
            for unit in ally_team:
                if "Noxus" in unit.traits:
                    unit.stats.damage_amp += stats["damage_amp"]

        self.log_event(
            "atakhan_summoned",
            team=team_id,
            star=atakhan_star,
            noxus_count=noxus_count,
            total_stars=total_stars,
            hp=round(base_hp),
            ad=round(base_ad, 1),
        )

    def _find_atakhan_spawn(self, team_id: int, ally_team: List[Unit]) -> Tuple[int, int]:
        """Find a spawn position for Atakhan (left side of board)."""
        occupied = {u.position for u in self.units if u.is_alive}

        # Atakhan spawns from the left side -- prefer back row for the team
        if team_id == 0:
            preferred_rows = [3, 2, 1, 0]  # Back rows for team 0
        else:
            preferred_rows = [0, 1, 2, 3]  # Back rows for team 1

        for row in preferred_rows:
            for col in [0, 1, 2, 3, 4, 5, 6]:
                pos = (row, col)
                if pos not in occupied:
                    return pos

        # Fallback: just find any open position
        for row in range(4):
            for col in range(7):
                if (row, col) not in occupied:
                    return (row, col)
        return (0, 0)  # Absolute fallback

    def _check_atakhan_ruin(self):
        """Check if a 4-star Atakhan at 10 Noxus should BRING RUIN.

        At 10 Noxus with 4-star Atakhan, after 10 seconds from summoning,
        Atakhan devours ALL enemy units.
        """
        for unit in self.units:
            if not (unit.is_alive and getattr(unit, "_is_atakhan", False)):
                continue

            noxus_count = getattr(unit, "_atakhan_noxus_count", 0)
            if noxus_count < 10 or unit.star_level < 4:
                continue

            summon_time = getattr(unit, "_atakhan_summon_time", 0)
            ruin_timer = getattr(unit, "_atakhan_ruin_timer", 10)

            if self.time - summon_time >= ruin_timer:
                if not getattr(unit, "_ruin_triggered", False):
                    unit._ruin_triggered = True
                    # BRING RUIN: kill all enemy units
                    enemies = [u for u in self.units if u.team != unit.team and u.is_alive]
                    for enemy in enemies:
                        enemy.stats.hp = 0
                        enemy.is_alive = False
                        enemy.state = UnitState.DEAD
                    self._alive_dirty = True
                    self.log_event(
                        "atakhan_bring_ruin", team=unit.team, enemies_devoured=len(enemies)
                    )

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
        - Set per-combat trait counts for combat-time triggers
        - Check Piltover module availability
        """
        team_id = team[0].team if team else 0

        # Count trait occurrences
        trait_counts = {}
        for unit in team:
            for trait in unit.traits:
                trait_counts[trait] = trait_counts.get(trait, 0) + 1

        # Log trait info
        self.log_event("round_start", trait_counts=trait_counts)

        # Bilgewater count is used for combat-time takedown rewards (currency stored in game layer).
        bilgewater_count = trait_counts.get("Bilgewater", 0)
        self.trait_manager.set_bilgewater_count(team_id, bilgewater_count)

        # Piltover module selection and storage
        piltover_count = trait_counts.get("Piltover", 0)
        if piltover_count >= 2:
            available_modules = self.trait_manager.assign_piltover_modules(piltover_count)
            if available_modules:
                selected = random.choice(available_modules)
                if not hasattr(self, "_piltover_data"):
                    self._piltover_data = {}
                piltover_units = [u for u in team if "Piltover" in u.traits]
                self._piltover_data[team_id] = {
                    "module": selected,
                    "fired": False,
                    "team": team,
                    "piltover_units": piltover_units,
                    "count": piltover_count,
                }
                self.log_event(
                    "piltover_module_selected", count=piltover_count, module=selected, team=team_id
                )

        # Shadow Isles soul collection setup
        shadow_isles_count = trait_counts.get("Shadow Isles", 0)
        self.trait_manager.set_shadow_isles_count(team_id, shadow_isles_count)
        if shadow_isles_count >= 2:
            shadow_isles_units = [u for u in team if "Shadow Isles" in u.traits]
            self.log_event(
                "shadow_isles_setup",
                count=shadow_isles_count,
                units=[u.name for u in shadow_isles_units],
                stat_bonus=self.trait_manager.get_shadow_isles_stat_bonus(team_id),
            )

    def _apply_combat_start_items(self, all_units: List[Unit]):
        """Apply combat-start item effects for all units."""
        try:
            from .item_effects import ITEM_ON_COMBAT_START, _resolve_item_name
        except ImportError:
            return
        for unit in all_units:
            if not unit.is_alive:
                continue
            for item in unit.items:
                handler = ITEM_ON_COMBAT_START.get(item.name) or ITEM_ON_COMBAT_START.get(
                    _resolve_item_name(item.name)
                )
                if handler:
                    handler(self, unit, all_units)

    def run_combat(
        self,
        team0: List[Unit],
        team1: List[Unit],
        max_time: float = 60.0,
        verbose: bool = False,
        team0_augments: List[str] = None,
        team1_augments: List[str] = None,
        seed: int = None,
    ) -> Dict:
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
        saved_random_state = None
        if seed is not None:
            saved_random_state = random.getstate()
            random.seed(seed)

        try:
            # Reset state
            self.time = 0.0
            self.combat_log = []
            self.units = team0 + team1
            self.projectiles = []
            self._debug_takedowns = []

            # Reset Shadow Isles souls for new combat
            self.trait_manager.reset_shadow_isles()

            # Reset Noxus Atakhan state for new combat
            self._noxus_team_data = {}

            # Reset Piltover module state for new combat
            self._piltover_data = {}

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

            # Shadow Isles stat bonus should be applied once per team (post-traits)
            team0_id = team0[0].team if team0 else 0
            team1_id = team1[0].team if team1 else 1
            self.trait_manager.apply_shadow_isles_stats(team0_id, team0)
            self.trait_manager.apply_shadow_isles_stats(team1_id, team1)

            # Apply augments if provided (after traits so they can stack)
            if team0_augments:
                self.augment_manager.set_augments(team0_augments)
                self.augment_manager.apply_augments(
                    team0,
                    team0_traits,
                    round_persistent_player=self._round_persistent_players.get(0),
                )
                self.log_event("augments_applied", team=0, augments=team0_augments)

            if team1_augments:
                self.augment_manager.set_augments(team1_augments)
                self.augment_manager.apply_augments(
                    team1,
                    team1_traits,
                    round_persistent_player=self._round_persistent_players.get(1),
                )
                self.log_event("augments_applied", team=1, augments=team1_augments)

            # Cache enemy starting HP for Noxus Atakhan trigger (after all buffs)
            noxus_data = getattr(self, "_noxus_team_data", {})
            for team_id, data in noxus_data.items():
                enemy_hp = sum(u.stats.max_hp for u in self.units if u.team != team_id)
                data["_enemy_starting_hp"] = enemy_hp

            # Initialize cached alive lists for tick() optimization
            self._alive_team0 = list(team0)
            self._alive_team1 = list(team1)
            self._alive_dirty = False  # Set True when a unit dies
            self._occupied_dirty = True  # Rebuild occupied hex cache
            self._has_noxus = bool(noxus_data)  # Skip Atakhan checks when no Noxus

            # Cache units with Ionic Spark for fast ability-cast reaction checks
            self._ionic_spark_units = [u for u in self.units if u._has_ionic_spark]

            # Apply combat-start item effects (Crownguard, Quicksilver, SteadfastHeart, etc.)
            self._apply_combat_start_items(team0 + team1)

            # Combat loop
            while self.time < max_time:
                if not self._alive_team0 or not self._alive_team1:
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
                "winner": winner,
                "combat_time": round(self.time, 2),
                "team0_survivors": len(team0_survivors),
                "team1_survivors": len(team1_survivors),
                "team0_total_damage": round(sum(u.total_damage_dealt for u in team0), 1),
                "team1_total_damage": round(sum(u.total_damage_dealt for u in team1), 1),
                "total_damage_dealt": {
                    "team0": round(sum(u.total_damage_dealt for u in team0), 1),
                    "team1": round(sum(u.total_damage_dealt for u in team1), 1),
                },
                "team0_abilities_cast": sum(u.abilities_cast for u in team0),
                "team1_abilities_cast": sum(u.abilities_cast for u in team1),
                "combat_log": self.combat_log if verbose else [],
                "debug_takedowns": list(self._debug_takedowns),
            }

            return results
        finally:
            if saved_random_state is not None:
                random.setstate(saved_random_state)

    def _next_event_dt(self, all_alive: List[Unit]) -> float:
        """Compute the time delta to the next meaningful event.

        Scans all alive units for the minimum cooldown remaining, then
        clamps to the tick rate so we never skip past a partial tick.
        Returns a delta >= tick_rate.
        """
        dt = 999.0
        tick = self.tick_rate

        for u in all_alive:
            # Attack cooldown
            if u.attack_cooldown > tick:
                dt = min(dt, u.attack_cooldown)
            else:
                return tick  # At least one unit can act now

            # Stun duration
            if u.stun_duration > tick:
                dt = min(dt, u.stun_duration)
            else:
                if u.stun_duration > 0:
                    return tick

            # Untargetable duration
            if not u.is_targetable and u.untargetable_duration > tick:
                dt = min(dt, u.untargetable_duration)
            elif not u.is_targetable:
                return tick

            # DOT ticks
            for dot in u.dot_effects:
                remaining_to_tick = dot.tick_interval - dot.time_since_last_tick
                if remaining_to_tick <= tick:
                    return tick
                dt = min(dt, remaining_to_tick)

        # Piltover fires at 8s
        if self._piltover_data:
            for pdata in self._piltover_data.values():
                if not pdata["fired"]:
                    time_to_8 = 8.0 - self.time
                    if time_to_8 <= tick:
                        return tick
                    dt = min(dt, time_to_8)

        # Never skip past tick_rate granularity -- snap to tick boundary
        # Round down to nearest tick multiple
        if dt > tick:
            dt = max(tick, (dt // tick) * tick)

        return dt

    def run_combat_adaptive_tick(
        self,
        team0: List[Unit],
        team1: List[Unit],
        max_time: float = 60.0,
        team0_augments: List[str] = None,
        team1_augments: List[str] = None,
        seed: int = None,
    ) -> Dict:
        """Run combat with adaptive tick skipping (experimental).

        Skips some idle ticks by fast-forwarding a subset of timers.
        Not guaranteed to exactly match run_combat() because many effects
        are evaluated via per-tick hooks.
        Logging is always disabled for this fast path.
        """
        saved_logging = self.logging_enabled
        self.logging_enabled = False
        saved_random_state = None

        try:
            # Use the same initialization as run_combat
            if seed is not None:
                saved_random_state = random.getstate()
                random.seed(seed)

            self.time = 0.0
            self.combat_log = []
            self.units = team0 + team1
            self.projectiles = []
            self._debug_takedowns = []
            self.trait_manager.reset_shadow_isles()
            self._noxus_team_data = {}
            self._piltover_data = {}
            self.augment_manager.reset()

            self.process_round_start(team0)
            self.process_round_start(team1)

            team0_traits = self._count_traits(team0)
            team1_traits = self._count_traits(team1)
            self.trait_manager.apply_stat_traits(team0, team0_traits, enemy_team=team1)
            self.trait_manager.apply_stat_traits(team1, team1_traits, enemy_team=team0)

            team0_id = team0[0].team if team0 else 0
            team1_id = team1[0].team if team1 else 1
            self.trait_manager.apply_shadow_isles_stats(team0_id, team0)
            self.trait_manager.apply_shadow_isles_stats(team1_id, team1)

            if team0_augments:
                self.augment_manager.set_augments(team0_augments)
                self.augment_manager.apply_augments(
                    team0,
                    team0_traits,
                    round_persistent_player=self._round_persistent_players.get(0),
                )
            if team1_augments:
                self.augment_manager.set_augments(team1_augments)
                self.augment_manager.apply_augments(
                    team1,
                    team1_traits,
                    round_persistent_player=self._round_persistent_players.get(1),
                )

            noxus_data = getattr(self, "_noxus_team_data", {})
            for team_id, data in noxus_data.items():
                enemy_hp = sum(u.stats.max_hp for u in self.units if u.team != team_id)
                data["_enemy_starting_hp"] = enemy_hp

            self._alive_team0 = list(team0)
            self._alive_team1 = list(team1)
            self._alive_dirty = False
            self._occupied_dirty = True
            self._has_noxus = bool(noxus_data)
            self._ionic_spark_units = [u for u in self.units if u._has_ionic_spark]

            self._apply_combat_start_items(team0 + team1)

            # Adaptive tick loop
            while self.time < max_time:
                if not self._alive_team0 or not self._alive_team1:
                    break

                # Compute time to next event and multi-step if possible
                all_alive = self._alive_team0 + self._alive_team1
                dt = self._next_event_dt(all_alive)

                # If we can skip ahead, fast-forward cooldowns
                if dt > self.tick_rate:
                    skip = dt - self.tick_rate
                    for u in all_alive:
                        if u.attack_cooldown > 0:
                            u.attack_cooldown -= skip
                        if u.stun_duration > 0:
                            u.stun_duration -= skip
                        if not u.is_targetable and u.untargetable_duration > 0:
                            u.untargetable_duration -= skip
                        for dot in u.dot_effects:
                            dot.remaining_duration -= skip
                            dot.time_since_last_tick += skip
                    self.time += skip

                self.tick()

            # Build result (same as run_combat)
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

            return {
                "winner": winner,
                "combat_time": round(self.time, 2),
                "team0_survivors": len(team0_survivors),
                "team1_survivors": len(team1_survivors),
                "team0_total_damage": round(sum(u.total_damage_dealt for u in team0), 1),
                "team1_total_damage": round(sum(u.total_damage_dealt for u in team1), 1),
                "total_damage_dealt": {
                    "team0": round(sum(u.total_damage_dealt for u in team0), 1),
                    "team1": round(sum(u.total_damage_dealt for u in team1), 1),
                },
                "team0_abilities_cast": sum(u.abilities_cast for u in team0),
                "team1_abilities_cast": sum(u.abilities_cast for u in team1),
                "combat_log": [],
                "debug_takedowns": list(self._debug_takedowns),
            }
        finally:
            if saved_random_state is not None:
                random.setstate(saved_random_state)
            self.logging_enabled = saved_logging

    def simulate_1v1(
        self,
        champ1: str,
        champ2: str,
        star1: int = 1,
        star2: int = 1,
        items1: List[str] = None,
        items2: List[str] = None,
        augments1: List[str] = None,
        augments2: List[str] = None,
        num_simulations: int = 100,
        seed: int = None,
    ) -> Dict:
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
                return {"error": "Invalid champion names"}

            result = self.run_combat(
                [unit1], [unit2], team0_augments=augments1, team1_augments=augments2, seed=sim_seed
            )

            if result["winner"] == 0:
                wins[champ1] += 1
            else:
                wins[champ2] += 1

            total_damage[champ1] += result["team0_total_damage"]
            total_damage[champ2] += result["team1_total_damage"]
            abilities_cast[champ1] += result["team0_abilities_cast"]
            abilities_cast[champ2] += result["team1_abilities_cast"]
            combat_times.append(result["combat_time"])

        return {
            "simulations": num_simulations,
            "win_rate": {
                champ1: round(wins[champ1] / num_simulations * 100, 1),
                champ2: round(wins[champ2] / num_simulations * 100, 1),
            },
            "avg_damage": {
                champ1: round(total_damage[champ1] / num_simulations, 1),
                champ2: round(total_damage[champ2] / num_simulations, 1),
            },
            "avg_abilities_cast": {
                champ1: round(abilities_cast[champ1] / num_simulations, 2),
                champ2: round(abilities_cast[champ2] / num_simulations, 2),
            },
            "avg_combat_time": round(sum(combat_times) / len(combat_times), 2),
        }
