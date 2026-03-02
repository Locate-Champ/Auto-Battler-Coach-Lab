"""Cost tier mixin: champion abilities organized by gold cost (1-5)."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Dict, List

from ._combat_types import DamageType
from ._hex_grid import HexGrid

if TYPE_CHECKING:
    from ._combat_types import Unit


class _AbilitiesCostTiersMixin:
    """Mixin providing cost-tier champion abilities (Cost 1 through Cost 5)."""

    # =========================================================================
    # COST 1 CHAMPION ABILITIES
    # =========================================================================

    def _cast_anivia(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Anivia - Frostbite: Damage current target, refund mana on kill."""

        damage = self._get_var(ability_vars, "Damage", unit.star_level, 325)
        mana_refund = self._get_var(ability_vars, "ManaRefund", unit.star_level, 10)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        actual, _ = self._deal_damage(
            unit, target, damage + unit.stats.ap, DamageType.MAGIC, "anivia_frostbite"
        )

        unit.stats.mana = 0
        if not target.is_alive:
            self.engine.gain_mana(unit, mana_refund, source="anivia_kill_refund")
        self.engine.log_event("ability_cast", unit=unit.name, ability="Frostbite")
        return True

    def _cast_blitzcrank(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Blitzcrank - Static Field: Shield self, deal MR-scaled damage in area."""

        shield = self._get_var(ability_vars, "Shield", unit.star_level, 400)
        duration = self._get_var(ability_vars, "Duration", unit.star_level, 4)
        radius = int(self._get_var(ability_vars, "HexRadius", unit.star_level, 1))
        mr_ratio = self._get_var(ability_vars, "MRDamageRatio", unit.star_level, 1.4)

        self.engine.apply_shield(unit, shield, "blitzcrank_static_field")

        nearby = self._get_enemies_in_radius(unit.position, radius, enemies)
        for enemy in nearby:
            damage = unit.stats.magic_resist * mr_ratio
            self._deal_damage(unit, enemy, damage, DamageType.MAGIC, "blitzcrank_static_field")

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast", unit=unit.name, ability="Static Field", targets_hit=len(nearby)
        )
        return True

    def _cast_briar(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Briar - Blood Frenzy: Buff AD and grant decaying attack speed."""
        bonus_ad_pct = self._get_var(ability_vars, "BonusAD", unit.star_level, 0.25)
        decaying_as = self._get_var(ability_vars, "DecayingAttackSpeed", unit.star_level, 3.0)
        duration = self._get_var(ability_vars, "Duration", unit.star_level, 4.0)

        unit.stats.ad *= 1 + bonus_ad_pct
        # Average of decaying AS over duration (half the peak)
        unit.stats.attack_speed += decaying_as * 0.5

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability="Blood Frenzy",
            bonus_ad_pct=bonus_ad_pct,
            as_boost=decaying_as,
        )
        return True

    def _cast_jarvaniv(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Jarvan IV - Demacian Standard: Shield self and grant attack speed to nearby allies."""
        shield = self._get_var(ability_vars, "Shield", unit.star_level, 350)
        as_buff = self._get_var(ability_vars, "AttackSpeed", unit.star_level, 0.20)
        as_duration = self._get_var(ability_vars, "AttackSpeedDuration", unit.star_level, 4.0)

        self.engine.apply_shield(unit, shield, "jarvan_standard")

        # Buff nearby allies' attack speed
        buffed = 0
        for ally in allies:
            if ally.is_alive and ally != unit:
                ally.stats.attack_speed += as_buff
                buffed += 1

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability="Demacian Standard",
            shield=shield,
            allies_buffed=buffed,
        )
        return True

    def _cast_kogmaw(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Kog'Maw - Caustic Spittle: Damage target + splash to secondary, reduce armor."""

        damage = self._get_var(ability_vars, "Damage", unit.star_level, 140)
        armor_red = self._get_var(ability_vars, "ArmorReduction", unit.star_level, 8)
        splash_pct = self._get_var(ability_vars, "PercentToSecondaryEnemies", unit.star_level, 0.5)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        target.stats.armor = max(0, target.stats.armor - armor_red)
        self._deal_damage(
            unit, target, damage + unit.stats.ap, DamageType.MAGIC, "kogmaw_caustic_spittle"
        )

        # Splash damage to nearby enemies
        nearby = self._get_enemies_in_radius(target.position, 1, enemies)
        for enemy in nearby:
            if enemy != target:
                self._deal_damage(
                    unit,
                    enemy,
                    (damage + unit.stats.ap) * splash_pct,
                    DamageType.MAGIC,
                    "kogmaw_splash",
                )

        unit.stats.mana = 0
        self.engine.log_event("ability_cast", unit=unit.name, ability="Caustic Spittle")
        return True

    def _cast_lulu(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Lulu - Whimsy: Polymorph target (stun) + damage, secondary damage to another."""

        damage = self._get_var(ability_vars, "Damage", unit.star_level, 285)
        stun_dur = self._get_var(ability_vars, "StunDuration", unit.star_level, 2.0)
        secondary = self._get_var(ability_vars, "SecondaryDamage", unit.star_level, 120)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        self._deal_damage(unit, target, damage + unit.stats.ap, DamageType.MAGIC, "lulu_whimsy")
        self._apply_stun(target, stun_dur, "lulu_polymorph")

        # Secondary damage to another enemy
        others = [e for e in enemies if e.is_alive and e.is_targetable and e != target]
        if others and secondary > 0:
            sec_target = random.choice(others)
            self._deal_damage(
                unit,
                sec_target,
                secondary + unit.stats.ap,
                DamageType.MAGIC,
                "lulu_whimsy_secondary",
            )

        unit.stats.mana = 0
        self.engine.log_event("ability_cast", unit=unit.name, ability="Whimsy")
        return True

    def _cast_qiyana(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Qiyana - Clear The Brush: Dash and deal AD+AP damage to target."""

        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 160)
        ap_damage = self._get_var(ability_vars, "APDamage", unit.star_level, 20)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Dash toward target
        self._dash_to_position(unit, target.position)

        total = ad_damage + unit.stats.ad + ap_damage + unit.stats.ap
        self._deal_damage(unit, target, total, DamageType.PHYSICAL, "qiyana_clear_brush")

        unit.stats.mana = 0
        self.engine.log_event("ability_cast", unit=unit.name, ability="Clear The Brush")
        return True

    def _cast_shen(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Shen - Stand United: Shield the lowest HP ally."""
        shield = self._get_var(ability_vars, "Shield", unit.star_level, 250)
        duration = self._get_var(ability_vars, "Duration", unit.star_level, 4.0)

        # Find lowest HP ally
        valid_allies = [a for a in allies if a.is_alive and a != unit]
        if valid_allies:
            target = min(valid_allies, key=lambda a: a.stats.hp / max(a.stats.max_hp, 1))
            self.engine.apply_shield(target, shield, "shen_stand_united")
        else:
            self.engine.apply_shield(unit, shield, "shen_stand_united")

        unit.stats.mana = 0
        self.engine.log_event("ability_cast", unit=unit.name, ability="Stand United")
        return True

    def _cast_sona(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Sona - Power Chord: Damage enemies and heal lowest HP allies."""

        damage = self._get_var(ability_vars, "Damage", unit.star_level, 130)
        heal_amt = self._get_var(ability_vars, "HealAmount", unit.star_level, 30)
        num_enemies = int(self._get_var(ability_vars, "NumEnemies", unit.star_level, 2))

        # Damage random enemies
        targets = [e for e in enemies if e.is_alive and e.is_targetable]
        hit_targets = random.sample(targets, min(num_enemies, len(targets))) if targets else []
        for target in hit_targets:
            self._deal_damage(
                unit, target, damage + unit.stats.ap, DamageType.MAGIC, "sona_power_chord"
            )

        # Heal lowest HP allies
        hurt_allies = sorted(
            [a for a in allies if a.is_alive], key=lambda a: a.stats.hp / max(a.stats.max_hp, 1)
        )
        for ally in hurt_allies[:num_enemies]:
            self.engine.heal_unit(ally, heal_amt + unit.stats.ap, "sona_heal")

        unit.stats.mana = 0
        self.engine.log_event("ability_cast", unit=unit.name, ability="Power Chord")
        return True

    # =========================================================================
    # COST 2 CHAMPION ABILITIES
    # =========================================================================

    def _cast_ashe(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Ashe - True Ice Arrow: Long-range stun + AoE damage, execute below 30% HP."""

        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 135)
        ap_damage = self._get_var(ability_vars, "APDamage", unit.star_level, 20)
        aoe_pct = self._get_var(ability_vars, "AOEPercent", unit.star_level, 0.33)
        duration = self._get_var(ability_vars, "Duration", unit.star_level, 3.0)
        execute_threshold = self._get_var(
            ability_vars, "TrueDamageHealthBreakpoint", unit.star_level, 0.30
        )

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
                self._deal_damage(
                    unit, enemy, total * aoe_pct, DamageType.PHYSICAL, "ashe_arrow_aoe"
                )

        unit.stats.mana = 0
        self.engine.log_event("ability_cast", unit=unit.name, ability="True Ice Arrow")
        return True

    def _cast_chogath(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Cho'Gath - Rupture: AoE knockup + %max HP damage + heal on hit."""

        ap_damage = self._get_var(ability_vars, "APDamage", unit.star_level, 45)
        pct_hp = self._get_var(ability_vars, "PercentMaximumHealthDamage", unit.star_level, 0.05)
        knockup = self._get_var(ability_vars, "KnockupDuration", unit.star_level, 1.5)
        heal = self._get_var(ability_vars, "Heal", unit.star_level, 200)

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
        self.engine.log_event(
            "ability_cast", unit=unit.name, ability="Rupture", targets_hit=len(hit)
        )
        return True

    def _cast_ekko(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Ekko - Parallel Convergence: AoE damage + bonus on-hit magic damage buff."""

        base_damage = self._get_var(ability_vars, "BaseMagicDamage", unit.star_level, 130)
        bonus_damage = self._get_var(ability_vars, "BaseBonusMagicDamage", unit.star_level, 150)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # AoE damage
        hit = self._get_enemies_in_radius(target.position, 1, enemies)
        for enemy in hit:
            self._deal_damage(
                unit, enemy, base_damage + unit.stats.ap, DamageType.MAGIC, "ekko_convergence"
            )

        # Buff on-hit magic damage
        unit.stats.ap += bonus_damage * 0.1  # Amortized on-hit bonus

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast", unit=unit.name, ability="Parallel Convergence", targets_hit=len(hit)
        )
        return True

    def _cast_graves(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Graves - Collateral Damage: AD+AP cone damage with falloff."""

        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 180)
        ap_damage = self._get_var(ability_vars, "APDamage", unit.star_level, 20)
        falloff = self._get_var(ability_vars, "AttackDamageMultiplier", unit.star_level, 0.45)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        total = ad_damage + unit.stats.ad + ap_damage + unit.stats.ap
        self._deal_damage(unit, target, total, DamageType.PHYSICAL, "graves_collateral")

        # Falloff damage to enemies behind target
        behind = [e for e in enemies if e.is_alive and e.is_targetable and e != target]
        for enemy in behind[:2]:
            self._deal_damage(
                unit, enemy, total * falloff, DamageType.PHYSICAL, "graves_collateral_falloff"
            )

        unit.stats.mana = 0
        self.engine.log_event("ability_cast", unit=unit.name, ability="Collateral Damage")
        return True

    def _cast_neeko(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Neeko - Pop Blossom: Shield self, AoE damage + chill."""

        shield = self._get_var(ability_vars, "Shield", unit.star_level, 400)
        damage = self._get_var(ability_vars, "Damage", unit.star_level, 80)
        chill_dur = self._get_var(ability_vars, "ChillDuration", unit.star_level, 2.0)

        self.engine.apply_shield(unit, shield, "neeko_pop_blossom")

        # AoE damage around self
        hit = self._get_enemies_in_radius(unit.position, 2, enemies)
        for enemy in hit:
            self._deal_damage(
                unit, enemy, damage + unit.stats.ap, DamageType.MAGIC, "neeko_pop_blossom"
            )
            # Chill = slow (reduce AS)
            enemy.stats.attack_speed = max(0.2, enemy.stats.attack_speed * 0.7)

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast", unit=unit.name, ability="Pop Blossom", targets_hit=len(hit)
        )
        return True

    def _cast_orianna(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Orianna - Command: Protect: Shield ally, damage nearby enemies."""

        shield = self._get_var(ability_vars, "Shield", unit.star_level, 60)
        target_dmg = self._get_var(ability_vars, "TargetDamage", unit.star_level, 220)
        explosion_dmg = self._get_var(ability_vars, "ExplosionDamage", unit.star_level, 120)

        # Shield lowest HP ally
        valid_allies = [a for a in allies if a.is_alive]
        if valid_allies:
            shield_target = min(valid_allies, key=lambda a: a.stats.hp / max(a.stats.max_hp, 1))
            self.engine.apply_shield(shield_target, shield + unit.stats.ap, "orianna_protect")

            # Damage enemies near shielded ally
            hit = self._get_enemies_in_radius(shield_target.position, 2, enemies)
            for enemy in hit:
                self._deal_damage(
                    unit,
                    enemy,
                    explosion_dmg + unit.stats.ap,
                    DamageType.MAGIC,
                    "orianna_explosion",
                )

        # Also damage current target
        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if target:
            self._deal_damage(
                unit, target, target_dmg + unit.stats.ap, DamageType.MAGIC, "orianna_command"
            )

        unit.stats.mana = 0
        self.engine.log_event("ability_cast", unit=unit.name, ability="Command: Protect")
        return True

    def _cast_poppy(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Poppy - Hammer Shock: Damage + knockup target, shield nearby allies."""

        damage = self._get_var(ability_vars, "PrimaryDamage", unit.star_level, 70)
        knockup = self._get_var(ability_vars, "KnockupDuration", unit.star_level, 0.5)
        shield_amt = self._get_var(ability_vars, "ShieldAmt", unit.star_level, 330)
        num_shielded = int(self._get_var(ability_vars, "NumShieldedAllies", unit.star_level, 2))
        ally_shield_pct = self._get_var(ability_vars, "AllyShieldAmount", unit.star_level, 0.30)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        self._deal_damage(
            unit, target, damage + unit.stats.ap, DamageType.MAGIC, "poppy_hammer_shock"
        )
        self._apply_stun(target, knockup, "poppy_knockup")

        # Shield self
        self.engine.apply_shield(unit, shield_amt, "poppy_shield")

        # Shield nearby allies (30% of self shield)
        ally_shield = shield_amt * ally_shield_pct
        valid_allies = [a for a in allies if a.is_alive and a != unit]
        for ally in valid_allies[:num_shielded]:
            self.engine.apply_shield(ally, ally_shield, "poppy_ally_shield")

        unit.stats.mana = 0
        self.engine.log_event("ability_cast", unit=unit.name, ability="Hammer Shock")
        return True

    def _cast_reksai(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Rek'Sai - Burrow: Dash to target, deal multiple attacks with AD+AP scaling."""

        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 140)
        ap_damage = self._get_var(ability_vars, "APDamage", unit.star_level, 20)
        num_attacks = int(self._get_var(ability_vars, "NumAttacks", unit.star_level, 3))

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
        self.engine.log_event("ability_cast", unit=unit.name, ability="Burrow")
        return True

    def _cast_sion(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Sion - Soul Furnace: Shield based on HP + AP, explode for %HP damage on break."""

        ap_shield = self._get_var(ability_vars, "APShield", unit.star_level, 200)
        pct_hp_shield = self._get_var(ability_vars, "PercentHealthShield", unit.star_level, 0.04)
        pct_hp_damage = self._get_var(ability_vars, "DamagePercentHealth", unit.star_level, 0.04)
        hp_per_takedown = self._get_var(ability_vars, "HealthPerTakedown", unit.star_level, 18)

        shield_val = ap_shield + unit.stats.max_hp * pct_hp_shield
        self.engine.apply_shield(unit, shield_val, "sion_soul_furnace")

        # Track takedown bonus
        if not hasattr(unit, "_sion_bonus_hp"):
            unit._sion_bonus_hp = 0

        # Deal %HP damage to nearby enemies
        hit = self._get_enemies_in_radius(unit.position, 1, enemies)
        for enemy in hit:
            damage = enemy.stats.max_hp * pct_hp_damage + unit.stats.ap
            self._deal_damage(unit, enemy, damage, DamageType.MAGIC, "sion_furnace_explode")

        unit.stats.mana = 0
        self.engine.log_event("ability_cast", unit=unit.name, ability="Soul Furnace")
        return True

    def _cast_teemo(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Teemo - Toxic Dart: Damage target + poison DoT."""

        primary = self._get_var(ability_vars, "PrimaryDamage", unit.star_level, 130)
        dot_dps = self._get_var(ability_vars, "DamagePerSecond", unit.star_level, 35)
        dot_dur = self._get_var(ability_vars, "DOtDuration", unit.star_level, 8)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        self._deal_damage(
            unit, target, primary + unit.stats.ap, DamageType.MAGIC, "teemo_toxic_dart"
        )

        # Apply poison DoT as upfront damage (simplified)
        total_dot = dot_dps * dot_dur
        self._deal_damage(unit, target, total_dot, DamageType.MAGIC, "teemo_poison")

        unit.stats.mana = 0
        self.engine.log_event("ability_cast", unit=unit.name, ability="Toxic Dart")
        return True

    def _cast_tristana(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Tristana - Buster Shot: Heavy AD+AP damage, knockback + stun."""

        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 250)
        ap_damage = self._get_var(ability_vars, "APDamage", unit.star_level, 30)
        stun_dur = self._get_var(ability_vars, "StunDuration", unit.star_level, 0.75)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        total = ad_damage + unit.stats.ad + ap_damage + unit.stats.ap
        self._deal_damage(unit, target, total, DamageType.PHYSICAL, "tristana_buster_shot")
        self._apply_stun(target, stun_dur, "tristana_knockback")

        unit.stats.mana = 0
        self.engine.log_event("ability_cast", unit=unit.name, ability="Buster Shot")
        return True

    def _cast_tryndamere(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Tryndamere - Undying Rage: Become unkillable, gain AD, DR, and armor ignore."""

        ad_bonus = self._get_var(ability_vars, "ADDamage", unit.star_level, 110)
        duration = self._get_var(ability_vars, "Duration", unit.star_level, 5.0)
        dr = self._get_var(ability_vars, "DR", unit.star_level, 0.15)
        armor_ignore = self._get_var(ability_vars, "ArmorIgnore", unit.star_level, 0.30)

        # Unkillable: set minimum HP
        unit._tryndamere_undying = True
        unit._tryndamere_min_hp = 1.0
        unit.stats.ad += ad_bonus
        unit.stats.damage_reduction = getattr(unit.stats, "damage_reduction", 0) + dr

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast", unit=unit.name, ability="Undying Rage", ad_bonus=ad_bonus, dr=dr
        )
        return True

    def _cast_twistedfate(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Twisted Fate - Stacked Deck: Every 3rd attack fires a piercing card."""

        base_damage = self._get_var(ability_vars, "BaseDamage", unit.star_level, 70)
        bonus_ap = self._get_var(ability_vars, "BonusAPDamage", unit.star_level, 50)
        falloff = self._get_var(ability_vars, "FalloffDamage", unit.star_level, 0.5)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        total = base_damage + bonus_ap + unit.stats.ap
        self._deal_damage(unit, target, total, DamageType.MAGIC, "tf_stacked_deck")

        # Pierce through to enemies behind
        behind = [e for e in enemies if e.is_alive and e.is_targetable and e != target]
        for enemy in behind[:2]:
            self._deal_damage(
                unit, enemy, total * falloff, DamageType.MAGIC, "tf_stacked_deck_pierce"
            )

        unit.stats.mana = 0
        self.engine.log_event("ability_cast", unit=unit.name, ability="Stacked Deck")
        return True

    def _cast_vi(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Vi - Relentless Force: Dash to target, shield self, knockup + damage."""

        shield = self._get_var(ability_vars, "Shield", unit.star_level, 125)
        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 120)
        knockup = self._get_var(ability_vars, "KnockupDuration", unit.star_level, 1.0)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        self.engine.apply_shield(unit, shield, "vi_shield")
        self._dash_to_position(unit, target.position)

        total = ad_damage + unit.stats.ad
        self._deal_damage(unit, target, total, DamageType.PHYSICAL, "vi_relentless_force")
        self._apply_stun(target, knockup, "vi_knockup")

        unit.stats.mana = 0
        self.engine.log_event("ability_cast", unit=unit.name, ability="Relentless Force")
        return True

    # =========================================================================
    # COST 3 CHAMPION ABILITIES
    # =========================================================================

    def _cast_ahri(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Ahri - Fox-Fire: Fire bolts at nearby enemies, dash away."""

        damage = self._get_var(ability_vars, "Damage", unit.star_level, 82)
        num_bolts = int(self._get_var(ability_vars, "NormalNumBolts", unit.star_level, 3))

        targets = [e for e in enemies if e.is_alive and e.is_targetable]
        if not targets:
            return False

        # Fire bolts at nearest enemies
        targets_sorted = sorted(
            targets,
            key=lambda e: (
                self.engine.hex_grid.hex_distance(unit.position, e.position)
                if hasattr(self.engine, "hex_grid")
                else 0
            ),
        )

        targets_sorted = sorted(
            targets, key=lambda e: HexGrid.hex_distance(unit.position, e.position)
        )

        for i in range(min(num_bolts, len(targets_sorted))):
            self._deal_damage(
                unit, targets_sorted[i], damage + unit.stats.ap, DamageType.MAGIC, "ahri_foxfire"
            )

        unit.stats.mana = 0
        self.engine.log_event("ability_cast", unit=unit.name, ability="Fox-Fire", bolts=num_bolts)
        return True

    def _cast_drmundo(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Dr. Mundo - Maximum Dosage: Heal over time + deal AD + %HP damage on hit."""

        duration = self._get_var(ability_vars, "Duration", unit.star_level, 5.0)
        pct_hp_heal = self._get_var(
            ability_vars, "PercentHealthHealingPerSecond", unit.star_level, 0.06
        )
        ap_heal = self._get_var(ability_vars, "APHealPerSecond", unit.star_level, 60)
        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 60)
        pct_hp_damage = self._get_var(
            ability_vars, "PercentMaximumHealthDamage", unit.star_level, 0.05
        )

        # Total healing over duration
        total_heal = (unit.stats.max_hp * pct_hp_heal + ap_heal) * duration
        self.engine.heal_unit(unit, total_heal, "mundo_maximum_dosage")

        # Bonus AD damage on hit (simplified: immediate burst)
        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if target:
            damage = ad_damage + unit.stats.ad + target.stats.max_hp * pct_hp_damage
            self._deal_damage(unit, target, damage, DamageType.PHYSICAL, "mundo_cleaver")

        unit.stats.mana = 0
        self.engine.log_event("ability_cast", unit=unit.name, ability="Maximum Dosage")
        return True

    def _cast_jinx(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Jinx - Switcheroo!: Fire many attacks that deal AD+AP per missile."""

        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 50)
        ap_damage = self._get_var(ability_vars, "APDamage", unit.star_level, 4)
        num_attacks = int(self._get_var(ability_vars, "NumAttacks", unit.star_level, 18))
        num_missiles = int(self._get_var(ability_vars, "NumMissiles", unit.star_level, 3))

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
                self._deal_damage(
                    unit, missile_target, per_missile, DamageType.PHYSICAL, "jinx_switcheroo"
                )

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast", unit=unit.name, ability="Switcheroo!", attacks=num_attacks
        )
        return True

    def _cast_kennen(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Kennen - Slicing Maelstrom: Shield self, AoE lightning bolts with stun."""

        shield = self._get_var(ability_vars, "Shield", unit.star_level, 600)
        damage = self._get_var(ability_vars, "Damage", unit.star_level, 120)
        num_bolts = int(self._get_var(ability_vars, "NumBolts", unit.star_level, 6))
        stun_dur = self._get_var(ability_vars, "StunDuration", unit.star_level, 1.5)
        max_stuns = int(self._get_var(ability_vars, "MaxStuns", unit.star_level, 3))
        radius = int(self._get_var(ability_vars, "HexRadius", unit.star_level, 2))

        self.engine.apply_shield(unit, shield, "kennen_maelstrom")

        targets = self._get_enemies_in_radius(unit.position, radius, enemies)
        stuns_applied = 0

        for i in range(min(num_bolts, max(1, len(targets)))):
            if not targets:
                break
            target = targets[i % len(targets)]
            if not target.is_alive:
                continue

            self._deal_damage(unit, target, damage + unit.stats.ap, DamageType.MAGIC, "kennen_bolt")

            if stuns_applied < max_stuns:
                self._apply_stun(target, stun_dur, "kennen_stun")
                stuns_applied += 1

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast", unit=unit.name, ability="Slicing Maelstrom", bolts=num_bolts
        )
        return True

    def _cast_kobuko(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Kobuko - You & Me!: Heal self and ally, grant attack speed to ally."""
        heal_ally = self._get_var(ability_vars, "AllyHealAP", unit.star_level, 80)
        self_heal = self._get_var(ability_vars, "SelfHealAP", unit.star_level, 180)
        self_heal_hp_pct = self._get_var(
            ability_vars, "SelfHealHealthPercent", unit.star_level, 0.12
        )
        ally_as = self._get_var(ability_vars, "YuumiAS", unit.star_level, 25)
        as_duration = self._get_var(ability_vars, "ASDuration", unit.star_level, 4.0)

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
        self.engine.log_event("ability_cast", unit=unit.name, ability="You & Me!")
        return True

    def _cast_nautilus(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Nautilus - Titan's Wrath: Shield (AP + %HP), deal MR-scaled damage on hit."""

        ap_shield = self._get_var(ability_vars, "APShield", unit.star_level, 375)
        pct_hp_shield = self._get_var(ability_vars, "PercentHealthShield", unit.star_level, 0.10)
        mr_ratio = self._get_var(ability_vars, "MRDamageRatio", unit.star_level, 0.9)

        shield_val = ap_shield + unit.stats.max_hp * pct_hp_shield
        self.engine.apply_shield(unit, shield_val, "nautilus_titans_wrath")

        # MR-scaled damage to current target
        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if target:
            damage = unit.stats.magic_resist * mr_ratio + unit.stats.ap
            self._deal_damage(unit, target, damage, DamageType.MAGIC, "nautilus_wrath")

        unit.stats.mana = 0
        self.engine.log_event("ability_cast", unit=unit.name, ability="Titan's Wrath")
        return True

    def _cast_sejuani(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Sejuani - Winter's Wrath: Shield self, AoE damage + stun in front."""

        shield = self._get_var(ability_vars, "Shield", unit.star_level, 525)
        damage = self._get_var(ability_vars, "Damage", unit.star_level, 70)
        stun_dur = self._get_var(ability_vars, "StunDuration", unit.star_level, 1.0)

        self.engine.apply_shield(unit, shield, "sejuani_winters_wrath")

        # AoE damage in front
        hit = self._get_enemies_in_radius(unit.position, 2, enemies)
        for enemy in hit:
            self._deal_damage(
                unit, enemy, damage + unit.stats.ap, DamageType.MAGIC, "sejuani_wrath"
            )
            self._apply_stun(enemy, stun_dur, "sejuani_freeze")

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast", unit=unit.name, ability="Winter's Wrath", targets_hit=len(hit)
        )
        return True

    def _cast_zoe(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Zoe - Double Trouble Bubble: Hit 2 enemies with heavy damage + slow."""

        damage = self._get_var(ability_vars, "Damage", unit.star_level, 330)
        num_targets = int(self._get_var(ability_vars, "NumEnemies", unit.star_level, 2))
        slow_dur = self._get_var(ability_vars, "SlowDuration", unit.star_level, 2.0)

        targets = [e for e in enemies if e.is_alive and e.is_targetable]
        if not targets:
            return False

        hit_targets = random.sample(targets, min(num_targets, len(targets)))
        for target in hit_targets:
            self._deal_damage(unit, target, damage + unit.stats.ap, DamageType.MAGIC, "zoe_bubble")
            target.stats.attack_speed = max(0.2, target.stats.attack_speed * 0.6)

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast",
            unit=unit.name,
            ability="Double Trouble Bubble",
            targets_hit=len(hit_targets),
        )
        return True

    # =========================================================================
    # COST 4 CHAMPION ABILITIES
    # =========================================================================

    def _cast_belveth(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Bel'Veth - Endless Banquet: Heavy damage + AS on takedown + true damage passive."""

        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 150)
        true_dmg_base = self._get_var(ability_vars, "TrueDamageBase", unit.star_level, 15)
        true_dmg_stack = self._get_var(ability_vars, "TrueDamagePerStack", unit.star_level, 3)
        as_on_transform = self._get_var(
            ability_vars, "AttackSpeedOnTransform", unit.star_level, 0.33
        )

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Track stacks
        if not hasattr(unit, "_belveth_stacks"):
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
        self.engine.log_event(
            "ability_cast", unit=unit.name, ability="Endless Banquet", stacks=unit._belveth_stacks
        )
        return True

    def _cast_braum(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Braum - Unbreakable Frost: Damage reduction buff + chill nearby enemies."""

        dr = self._get_var(ability_vars, "DamageReduction", unit.star_level, 0.55)
        duration = self._get_var(ability_vars, "Duration", unit.star_level, 4.0)
        ap_damage = self._get_var(ability_vars, "APDamage", unit.star_level, 15)
        armor_damage = self._get_var(ability_vars, "ArmorDamage", unit.star_level, 0.2)

        # Massive damage reduction
        unit.stats.damage_reduction = getattr(unit.stats, "damage_reduction", 0) + dr

        # Damage nearby enemies
        hit = self._get_enemies_in_radius(unit.position, 2, enemies)
        for enemy in hit:
            damage = ap_damage + unit.stats.armor * armor_damage + unit.stats.ap
            self._deal_damage(unit, enemy, damage, DamageType.MAGIC, "braum_frost")
            enemy.stats.attack_speed = max(0.2, enemy.stats.attack_speed * 0.7)

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast", unit=unit.name, ability="Unbreakable Frost", dr=dr, targets_hit=len(hit)
        )
        return True

    def _cast_fizz(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Fizz - Playful Trickster: Become untargetable, dash, deal damage + empowered attacks."""

        damage = self._get_var(ability_vars, "Damage", unit.star_level, 75)
        on_hit_dmg = self._get_var(ability_vars, "DamageOnHit", unit.star_level, 50)
        num_attacks = int(self._get_var(ability_vars, "NumAttacks", unit.star_level, 4))
        as_boost = self._get_var(ability_vars, "ASBoost", unit.star_level, 1.0)

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Splash damage on landing
        self._dash_to_position(unit, target.position)
        hit = self._get_enemies_in_radius(target.position, 1, enemies)
        for enemy in hit:
            self._deal_damage(unit, enemy, damage + unit.stats.ap, DamageType.MAGIC, "fizz_splash")

        # Empowered attacks (bonus on-hit + AS)
        unit.stats.attack_speed += as_boost
        unit.stats.ad += on_hit_dmg * 0.25  # Amortized over attacks

        unit.stats.mana = 0
        self.engine.log_event("ability_cast", unit=unit.name, ability="Playful Trickster")
        return True

    def _cast_garen(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Garen - Judgment: Spin dealing AD damage, reduce armor/MR, heal self."""

        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 100)
        spin_dur = self._get_var(ability_vars, "SpinDuration", unit.star_level, 3.0)
        durability = self._get_var(ability_vars, "Durability", unit.star_level, 0.5)
        armor_mr_red = self._get_var(ability_vars, "ArmorMRReduction", unit.star_level, 5)
        ap_heal = self._get_var(ability_vars, "APHeal", unit.star_level, 250)
        pct_hp_heal = self._get_var(ability_vars, "PercentHealthHeal", unit.star_level, 0.1)

        # Damage reduction during spin
        unit.stats.damage_reduction = getattr(unit.stats, "damage_reduction", 0) + durability

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
        self.engine.log_event(
            "ability_cast", unit=unit.name, ability="Judgment", targets_hit=len(hit)
        )
        return True

    def _cast_kaisa(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Kai'Sa - Icathian Rain: Fire missiles split across targets, 60% on current."""

        num_missiles = int(self._get_var(ability_vars, "NumMissiles", unit.star_level, 15))
        ad_damage = self._get_var(ability_vars, "ADDamage", unit.star_level, 39)
        ap_damage = self._get_var(ability_vars, "APDamage", unit.star_level, 6)
        num_targets = int(self._get_var(ability_vars, "NumTargets", unit.star_level, 4))
        primary_pct = self._get_var(
            ability_vars, "PercentMissilesOnCurrentTarget", unit.star_level, 0.6
        )

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
        secondary = others[: num_targets - 1] if others else []

        if secondary:
            per_secondary = remaining // len(secondary) if secondary else 0
            for sec_target in secondary:
                for _ in range(per_secondary):
                    if not sec_target.is_alive:
                        break
                    self._deal_damage(
                        unit, sec_target, per_missile, DamageType.PHYSICAL, "kaisa_rain_secondary"
                    )

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast", unit=unit.name, ability="Icathian Rain", missiles=num_missiles
        )
        return True

    def _cast_nasus(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Nasus - Fury of the Sands: Steal HP from enemies, gain resists."""

        health_steal = self._get_var(ability_vars, "HealthSteal", unit.star_level, 485)
        duration = self._get_var(ability_vars, "Duration", unit.star_level, 8)
        num_enemies = int(self._get_var(ability_vars, "NumEnemies", unit.star_level, 4))
        resists = self._get_var(ability_vars, "Resists", unit.star_level, 30)
        pct_hp_dps = self._get_var(
            ability_vars, "PercentHealthDamagePerSecond", unit.star_level, 0.015
        )

        # Gain resists
        unit.stats.armor += resists
        unit.stats.magic_resist += resists

        # Drain HP from nearby enemies
        targets = sorted(
            [e for e in enemies if e.is_alive and e.is_targetable],
            key=lambda e: (
                self.engine.hex_grid.hex_distance(unit.position, e.position)
                if hasattr(self.engine, "hex_grid")
                else 0
            ),
        )[:num_enemies]

        targets = self._get_enemies_in_radius(unit.position, 3, enemies)[:num_enemies]

        total_drain = health_steal + pct_hp_dps * duration * unit.stats.max_hp
        per_target_drain = total_drain / max(1, len(targets)) if targets else 0

        for enemy in targets:
            self._deal_damage(unit, enemy, per_target_drain, DamageType.MAGIC, "nasus_fury")

        self.engine.heal_unit(unit, total_drain * 0.5, "nasus_lifesteal")

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast", unit=unit.name, ability="Fury of the Sands", targets=len(targets)
        )
        return True

    # =========================================================================
    # COST 5 CHAMPION ABILITIES
    # =========================================================================

    def _cast_azir(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Azir - Arise!: Summon soldiers that deal magic damage on-hit."""

        base_damage = self._get_var(ability_vars, "BaseMagicDamage", unit.star_level, 100)
        max_summons = int(self._get_var(ability_vars, "MaxSummons", unit.star_level, 2))
        summon_damage = self._get_var(ability_vars, "MaxSummonsDamage", unit.star_level, 70)

        # Track summon count
        if not hasattr(unit, "_azir_soldiers"):
            unit._azir_soldiers = 0

        unit._azir_soldiers = min(unit._azir_soldiers + 1, max_summons)

        # Soldiers deal damage to nearby enemies (simplified)
        targets = self._get_enemies_in_radius(unit.position, 3, enemies)
        for target in targets[: unit._azir_soldiers]:
            damage = base_damage + summon_damage + unit.stats.ap
            self._deal_damage(unit, target, damage, DamageType.MAGIC, "azir_soldier")

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast", unit=unit.name, ability="Arise!", soldiers=unit._azir_soldiers
        )
        return True

    def _cast_ornn(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Ornn - Call of the Forge: AoE damage + secondary damage + slow."""

        damage = self._get_var(ability_vars, "Damage", unit.star_level, 100)
        secondary = self._get_var(ability_vars, "SecondaryDamage", unit.star_level, 150)

        # AoE damage
        hit = self._get_enemies_in_radius(unit.position, 2, enemies)
        for enemy in hit:
            self._deal_damage(
                unit, enemy, damage + unit.stats.ap, DamageType.MAGIC, "ornn_forge_primary"
            )
            self._deal_damage(
                unit, enemy, secondary + unit.stats.ap, DamageType.MAGIC, "ornn_forge_secondary"
            )
            # Slow
            enemy.stats.attack_speed = max(0.2, enemy.stats.attack_speed * 0.7)

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast", unit=unit.name, ability="Call of the Forge", targets_hit=len(hit)
        )
        return True

    def _cast_volibear(
        self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict
    ) -> bool:
        """Volibear - The Relentless Storm: Bite damage (base + %HP), transform after 5 casts."""

        bite_base = self._get_var(ability_vars, "BiteDamageBase", unit.star_level, 100)
        bite_hp_pct = self._get_var(ability_vars, "BiteDamageHealth", unit.star_level, 0.03)
        casts_to_transform = int(
            self._get_var(ability_vars, "CastsToTransform", unit.star_level, 5)
        )
        bonus_hp = self._get_var(ability_vars, "StormbringerBonusHealth", unit.star_level, 400)
        bonus_as = self._get_var(ability_vars, "StormbringerAS", unit.star_level, 0.5)
        bolt_base = self._get_var(ability_vars, "StormbringerBoltBase", unit.star_level, 50)
        bolt_hp_pct = self._get_var(ability_vars, "StormbringerBoltHealth", unit.star_level, 0.04)

        if not hasattr(unit, "_voli_casts"):
            unit._voli_casts = 0
        unit._voli_casts += 1

        target = unit.target or self._find_nearest_enemy(unit, enemies)
        if not target:
            return False

        # Bite damage
        damage = bite_base + unit.stats.ap + target.stats.max_hp * bite_hp_pct
        self._deal_damage(unit, target, damage, DamageType.MAGIC, "volibear_bite")

        # Transform at threshold
        if unit._voli_casts >= casts_to_transform and not getattr(unit, "_voli_transformed", False):
            unit._voli_transformed = True
            unit.stats.max_hp += bonus_hp
            unit.stats.hp += bonus_hp
            unit.stats.attack_speed += bonus_as

            # Lightning bolt AoE
            hit = self._get_enemies_in_radius(unit.position, 3, enemies)
            for enemy in hit:
                bolt_dmg = bolt_base + unit.stats.ap + enemy.stats.max_hp * bolt_hp_pct
                self._deal_damage(unit, enemy, bolt_dmg, DamageType.MAGIC, "volibear_bolt")

            self.engine.log_event(
                "volibear_transform", unit=unit.name, bonus_hp=bonus_hp, bonus_as=bonus_as
            )

        unit.stats.mana = 0
        self.engine.log_event(
            "ability_cast", unit=unit.name, ability="The Relentless Storm", casts=unit._voli_casts
        )
        return True
