"""Hero augment mixin: hero augment ability handlers and tick dispatcher."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Dict, List

from ._combat_types import DamageType

if TYPE_CHECKING:
    from ._combat_types import Unit


class _AbilitiesHeroAugmentsMixin:
    """Mixin providing hero augment ability handlers."""

    # =========================================================================
    # HERO AUGMENT ABILITY HANDLERS
    # =========================================================================

    # -------------------------------------------------------------------------
    # XIN ZHAO - Trials of Twilight
    # -------------------------------------------------------------------------

    def _cast_xinzhao(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Xin Zhao - Three Talon Strike: Knockup + enhanced attacks.

        Hero Augment (Trials of Twilight):
        - Constantly strikes nearby enemies
        - Executes enemies below 15% HP
        - Transforms to Zaahen after 5 rounds as 3-star
        """

        base_damage = self._get_var(ability_vars, "Damage", unit.star_level, 200)
        knockup_duration = self._get_var(ability_vars, "KnockupDuration", unit.star_level, 1.5)
        enhanced_attacks = int(self._get_var(ability_vars, "EnhancedAttacks", unit.star_level, 3))

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Check for hero augment
        hero_effects = getattr(unit, "_hero_augment_effects", {})
        has_hero_augment = hero_effects.get("constant_strikes", False)
        execute_threshold = hero_effects.get("execute_threshold", 0)

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
                        self.engine.apply_damage(
                            unit, enemy, enemy.stats.hp + 1, DamageType.TRUE, "xinzhao_execute"
                        )
                        self.engine.log_event(
                            "execute",
                            unit=unit.name,
                            target=enemy.name,
                            threshold=execute_threshold,
                            source="Trials of Twilight",
                        )

        # Grant enhanced attacks
        unit.enhanced_attacks_remaining = enhanced_attacks
        unit.enhanced_attack_bonus_ad = base_damage * 0.3

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability="Three Talon Strike",
            hero_augment=has_hero_augment,
        )
        return True

    def xinzhao_hero_tick(self, unit: "Unit", enemies: List["Unit"], dt: float):
        """Xin Zhao hero augment: Constantly strike nearby enemies.

        Called each combat tick when Trials of Twilight is active.
        """
        hero_effects = getattr(unit, "_hero_augment_effects", {})
        if not hero_effects.get("constant_strikes"):
            return

        # Track strike cooldown (strikes every 0.5s based on attack speed)
        if not hasattr(unit, "_hero_strike_timer"):
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
                    self._deal_damage(
                        unit, enemy, damage, DamageType.PHYSICAL, "xinzhao_hero_strike"
                    )

                # Check for executes
                execute_threshold = hero_effects.get("execute_threshold", 0.15)
                for enemy in nearby:
                    if enemy.is_alive:
                        hp_pct = enemy.stats.hp / enemy.stats.max_hp
                        if hp_pct <= execute_threshold:
                            self.engine.apply_damage(
                                unit, enemy, enemy.stats.hp + 1, DamageType.TRUE, "xinzhao_execute"
                            )

    # -------------------------------------------------------------------------
    # RUMBLE - Artillery Barrage
    # -------------------------------------------------------------------------

    def _cast_rumble(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Rumble - Flamespitter: Cone damage.

        Hero Augment (Artillery Barrage):
        - +7 Range
        - Constantly fires missiles at enemies
        - Missile rate scales with attack speed
        """

        base_damage = self._get_var(ability_vars, "Damage", unit.star_level, 180)
        burn_damage = self._get_var(ability_vars, "BurnDamage", unit.star_level, 50)
        burn_duration = self._get_var(ability_vars, "BurnDuration", unit.star_level, 3.0)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Check for hero augment
        hero_effects = getattr(unit, "_hero_augment_effects", {})
        has_hero_augment = hero_effects.get("constant_missiles", False)

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
                    self._deal_damage(
                        unit, missile_target, missile_damage, DamageType.MAGIC, "rumble_missile"
                    )

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast", unit=unit.name, ability="Flamespitter", hero_augment=has_hero_augment
        )
        return True

    def rumble_hero_tick(self, unit: "Unit", enemies: List["Unit"], dt: float):
        """Rumble hero augment: Constantly fire missiles.

        Called each combat tick when Artillery Barrage is active.
        """
        hero_effects = getattr(unit, "_hero_augment_effects", {})
        if not hero_effects.get("constant_missiles"):
            return

        # Track missile cooldown (fires every 0.75s, faster with AS)
        if not hasattr(unit, "_hero_missile_timer"):
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
                self._deal_damage(
                    unit, target, missile_damage, DamageType.MAGIC, "rumble_hero_missile"
                )

    # -------------------------------------------------------------------------
    # ILLAOI - Leap of Faith
    # -------------------------------------------------------------------------

    def _cast_illaoi(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Illaoi - Harsh Lesson: Slam target.

        Hero Augment (Leap of Faith):
        - Becomes a Fighter
        - Ability replaced with airborne slam
        - Recast immediately when kills target
        """

        base_damage = self._get_var(ability_vars, "Damage", unit.star_level, 250)
        heal_per_enemy = self._get_var(ability_vars, "HealPerEnemy", unit.star_level, 100)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Check for hero augment
        hero_effects = getattr(unit, "_hero_augment_effects", {})
        has_hero_augment = hero_effects.get("slam_ability", False)

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
            if not target.is_alive and hero_effects.get("recast_on_kill"):
                # Find next target and recast (up to 3 times)
                recast_count = getattr(unit, "_illaoi_recast_count", 0)
                if recast_count < 3:
                    unit._illaoi_recast_count = recast_count + 1
                    # Queue another cast (mana stays at 0)
                    unit._illaoi_pending_recast = True
                    self.engine.log_event(
                        "illaoi_recast", unit=unit.name, recast_num=recast_count + 1
                    )

            # Heal based on enemies in range
            nearby = self._get_enemies_in_radius(unit.position, 2, enemies)
            heal = heal_per_enemy * len(nearby)
            self.engine.heal_unit(unit, heal, "illaoi_tentacle_heal")

            self.engine.log_event(
                "ability_cast",
                unit=unit.name,
                ability="Leap of Faith",
                target=target.name,
                recast=has_hero_augment,
            )
        else:
            # Normal ability: Slam + heal
            damage = base_damage + unit.stats.ad + unit.stats.ap
            self._deal_damage(unit, target, damage, DamageType.PHYSICAL, "illaoi_slam")

            # Heal per enemy hit
            nearby = self._get_enemies_in_radius(target.position, 2, enemies)
            for enemy in nearby:
                if enemy != target:
                    self._deal_damage(
                        unit, enemy, damage * 0.5, DamageType.PHYSICAL, "illaoi_splash"
                    )

            heal = heal_per_enemy * len(nearby)
            self.engine.heal_unit(unit, heal, "illaoi_heal")

            self.engine.log_event(
                "ability_cast", unit=unit.name, ability="Harsh Lesson", targets_hit=len(nearby)
            )

        unit.stats.mana = 0
        return True

    def check_illaoi_recast(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Check if Illaoi should recast due to Leap of Faith kill."""
        if getattr(unit, "_illaoi_pending_recast", False):
            unit._illaoi_pending_recast = False
            return self._cast_illaoi(unit, enemies, allies, ability_vars)
        return False

    def _cast_jhin(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Jhin - Curtain Call: 4 cannon shots, 4th shot does bonus damage.

        Regular attacks use normal attack speed. During Curtain Call,
        attack speed is capped at 1.0 (1 shot per second).
        ADDamage/APDamage are per-shot scaling percentages.
        4th shot deals FourthShotDamageMult (1.44x) more damage.
        """

        ad_pct = self._get_var(ability_vars, "ADDamage", unit.star_level, 145)
        ap_pct = self._get_var(ability_vars, "APDamage", unit.star_level, 15)
        fourth_mult = self._get_var(ability_vars, "FourthShotDamageMult", unit.star_level, 1.44)

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
        self.engine.log_event(
            "ability_cast", unit=unit.name, ability="Curtain Call", shots=shots_fired
        )
        return True

    # -------------------------------------------------------------------------
    # VIEGO - The Ruined King (Hero Augment Modifier)
    # -------------------------------------------------------------------------

    def viego_hero_augment_check(self, unit: "Unit", allies: List["Unit"]):
        """Check and apply Viego's hero augment effects.

        The Ruined King:
        - Shares 30% of passive with Shadow Isles allies
        - Ability upgrades after 100 souls
        """
        hero_effects = getattr(unit, "_hero_augment_effects", {})
        if not hero_effects:
            return

        # Check for ability upgrade at 100 souls
        soul_req = hero_effects.get("soul_req_upgrade", 100)
        soul_count = self.engine.trait_manager.get_shadow_isles_souls(unit.team)

        if soul_count >= soul_req and not getattr(unit, "_viego_ability_upgraded", False):
            unit._viego_ability_upgraded = True
            # Upgrade: Double the stacking damage
            unit._viego_upgrade_damage_mult = 2.0
            self.engine.log_event(
                "viego_upgrade", unit=unit.name, souls=soul_count, effect="Ability damage doubled"
            )

        # Share passive with SI allies (applied at combat start via AugmentManager)
        share_pct = hero_effects.get("passive_share_percent", 0.30)
        viego_stacks = getattr(unit, "_viego_stacks", 0)

        if viego_stacks > 0:
            shared_damage = viego_stacks * share_pct
            for ally in allies:
                if ally != unit and ally.is_alive and "Shadow Isles" in ally.traits:
                    if getattr(ally, "_viego_passive_share", 0) > 0:
                        # Apply shared stacking damage bonus
                        ally.stats.ad += shared_damage * 0.1  # 10% of shared per tick

    # -------------------------------------------------------------------------
    # HERO AUGMENT TICK DISPATCHER
    # -------------------------------------------------------------------------

    def process_hero_augment_ticks(
        self, units: List["Unit"], enemies: List["Unit"], allies: List["Unit"], dt: float
    ):
        """Process all hero augment tick effects for active units.

        Called each combat tick by the engine.
        """
        for unit in units:
            if not unit.is_alive:
                continue

            hero_augment = getattr(unit, "_hero_augment", None)
            if not hero_augment:
                continue

            if hero_augment == "TFT16_Augment_XinZhaoCarry":
                self.xinzhao_hero_tick(unit, enemies, dt)
            elif hero_augment == "TFT16_Augment_RumbleCarry":
                self.rumble_hero_tick(unit, enemies, dt)
            elif hero_augment == "TFT16_Augment_ShadowIsles_RuinedKing":
                self.viego_hero_augment_check(unit, allies)

            # Check Illaoi recast
            if unit.api_name == "TFT16_Illaoi":
                ability_vars = self.engine.get_ability_vars(unit)
                self.check_illaoi_recast(unit, enemies, allies, ability_vars)
