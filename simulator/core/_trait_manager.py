"""Trait manager: trait activation and application for TFT combat."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from ._combat_types import UnitState
from ._item_database import _ITEMS_LOADED

if TYPE_CHECKING:
    from ._combat_types import Unit


@dataclass(slots=True)
class TeamTraitState:
    bilgewater_count: int = 0
    shadow_isles_count: int = 0
    shadow_isles_souls: int = 0


class TraitManager:
    """Manages trait effects and mechanics.

    Key traits with special mechanics:
    - Piltover: T-Hex modules at 2/4/6 trait count
    - Shadow Isles: Soul collection from enemy deaths
    """

    BILGEWATER_SERPENTS_PER_TAKEDOWN = 1  # Patch 16.3: nerfed from 2 to 1

    # Shadow Isles soul multipliers by trait count
    SHADOW_ISLES_SOUL_MULTIPLIER = {
        2: 1.0,
        3: 1.3,
        4: 1.6,
        5: 1.9,
    }

    # Shadow Isles AD/AP bonus by trait count
    SHADOW_ISLES_STAT_BONUS = {
        2: 0.18,  # 18% AD/AP
        3: 0.20,  # 20% AD/AP
        4: 0.25,  # 25% AD/AP
        5: 0.33,  # 33% AD/AP
    }

    def __init__(self):
        self.team_state: Dict[int, TeamTraitState] = {}
        self.piltover_modules: List[str] = []

    def get_team_state(self, team_id: int) -> TeamTraitState:
        """Get (and create if needed) per-team trait state."""
        state = self.team_state.get(team_id)
        if state is None:
            state = TeamTraitState()
            self.team_state[team_id] = state
        return state

    def set_bilgewater_count(self, team_id: int, count: int):
        """Set the current Bilgewater trait count for a team."""
        state = self.get_team_state(team_id)
        state.bilgewater_count = count

    def assign_piltover_modules(self, piltover_count: int) -> List[str]:
        """Assign Piltover modules based on trait count.

        Args:
            piltover_count: Number of Piltover champions active

        Returns:
            List of module names that can be used
        """
        if not _ITEMS_LOADED:
            return []

        available_modules = []

        # Tier 1: 2 Piltover
        if piltover_count >= 2:
            tier1_modules = [
                "AccelerationGate",
                "BlastShield",
                "ContinuumCogs",
                "EMP",
                "KineticBarrier",
                "OverclockedCapacitors",
            ]
            available_modules.extend(tier1_modules)

        # Tier 2: 4 Piltover
        if piltover_count >= 4:
            tier2_modules = [
                "ArmorNullifier",
                "GigantificationRay",
                "MagnetronCoil",
                "MomentumDrive",
                "TunedOscillator",
                "ElectricalOverload",
            ]
            available_modules.extend(tier2_modules)

        # Tier 3: 6 Piltover
        if piltover_count >= 6:
            tier3_modules = [
                "MicroRockets",
                "MiningDrill",
                "90CaliberNets",
                "SuperiorLifeform",
                "UnstableCurrent",
            ]
            available_modules.extend(tier3_modules)

        return available_modules

    # =========================================================================
    # SHADOW ISLES SOUL COLLECTION
    # =========================================================================

    def set_shadow_isles_count(self, team_id: int, count: int):
        """Set the current Shadow Isles trait count for a team."""
        state = self.get_team_state(team_id)
        state.shadow_isles_count = count

    def award_soul(self, team_id: int, victim_cost: int = 1, victim_star: int = 1) -> int:
        """Award souls when an enemy dies.

        Soul value is based on victim's cost and star level.
        Higher cost/star units are worth more souls.

        Args:
            team_id: Team to award souls to
            victim_cost: Champion cost (1-5)
            victim_star: Star level (1-3)

        Returns:
            Number of souls awarded
        """
        state = self.get_team_state(team_id)
        if state.shadow_isles_count < 2:
            return 0

        # Base souls by cost
        cost_souls = {1: 1, 2: 2, 3: 3, 4: 5, 5: 8}
        base_souls = cost_souls.get(victim_cost, 1)

        # Star level multiplier
        star_mult = {1: 1.0, 2: 1.5, 3: 2.0}
        souls = int(base_souls * star_mult.get(victim_star, 1.0))

        # Apply trait count multiplier
        soul_mult = 1.0
        for tier in sorted(self.SHADOW_ISLES_SOUL_MULTIPLIER.keys(), reverse=True):
            if state.shadow_isles_count >= tier:
                soul_mult = self.SHADOW_ISLES_SOUL_MULTIPLIER[tier]
                break

        souls = int(souls * soul_mult)
        state.shadow_isles_souls += souls

        return souls

    def get_shadow_isles_stat_bonus(self, team_id: int) -> float:
        """Get the AD/AP bonus percentage for Shadow Isles units.

        Returns:
            Stat bonus as a decimal (0.18 = 18%)
        """
        state = self.get_team_state(team_id)
        if state.shadow_isles_count < 2:
            return 0.0

        for tier in sorted(self.SHADOW_ISLES_STAT_BONUS.keys(), reverse=True):
            if state.shadow_isles_count >= tier:
                return self.SHADOW_ISLES_STAT_BONUS[tier]

        return 0.0

    def apply_shadow_isles_stats(self, team_id: int, units: List["Unit"]):
        """Apply Shadow Isles stat bonuses to units with the trait.

        Called at combat start to give AD/AP bonus based on trait count.
        """
        state = self.get_team_state(team_id)
        if state.shadow_isles_count < 2:
            return

        bonus = self.get_shadow_isles_stat_bonus(team_id)

        for unit in units:
            if "Shadow Isles" in unit.traits:
                # Apply AD/AP bonus (percentage of base stats)
                ad_bonus = unit.base_stats.ad * bonus
                ap_bonus = unit.stats.ap * bonus if unit.stats.ap > 0 else 10 * bonus

                unit.stats.ad += ad_bonus
                unit.stats.ap += ap_bonus

    def get_shadow_isles_souls(self, team_id: int) -> int:
        """Get current Shadow Isles soul count for a team."""
        state = self.get_team_state(team_id)
        return state.shadow_isles_souls

    def reset_shadow_isles(self):
        """Reset Shadow Isles state for new combat."""
        for state in self.team_state.values():
            state.shadow_isles_souls = 0

    # =========================================================================
    # HUNTRESS TRAIT (Neeko + Nidalee synergy)
    # =========================================================================

    # Huntress - While Neeko is alive, Nidalee can't be targeted by basic attacks + gains Durability
    HUNTRESS_DURABILITY = 0.5  # 50% damage reduction

    def apply_huntress_synergy(self, units: List["Unit"]) -> bool:
        """Apply Huntress synergy if both Neeko and Nidalee are on the team.

        While Neeko is alive, Nidalee:
        - Cannot be targeted by basic attacks (is_basic_attack_immune)
        - Gains 50% Durability (damage reduction)

        Args:
            units: List of units on the team

        Returns:
            True if synergy was applied, False otherwise
        """
        # Find strongest Neeko and Nidalee
        neekos = [u for u in units if u.api_name == "TFT16_Neeko" and u.is_alive]
        nidalees = [u for u in units if u.api_name == "TFT16_Nidalee" and u.is_alive]

        if not neekos or not nidalees:
            return False

        # Sort by star level (descending) to find "strongest"
        strongest_neeko = max(neekos, key=lambda u: (u.star_level, u.stats.hp))
        strongest_nidalee = max(nidalees, key=lambda u: (u.star_level, u.stats.hp))

        # Mark Nidalee as protected by Neeko
        if not hasattr(strongest_nidalee, "_huntress_active"):
            strongest_nidalee._huntress_active = True
            strongest_nidalee._huntress_neeko_id = id(strongest_neeko)
            strongest_nidalee.is_basic_attack_immune = True
            strongest_nidalee.stats.damage_reduction += self.HUNTRESS_DURABILITY

        return True

    def check_huntress_on_death(self, dead_unit: "Unit", units: List["Unit"]):
        """Check if Huntress synergy should be removed when a unit dies.

        If Neeko dies, Nidalee loses her Huntress buffs.

        Args:
            dead_unit: The unit that just died
            units: List of all units
        """
        if dead_unit.api_name != "TFT16_Neeko":
            return

        # Find the Nidalee linked to this Neeko
        for unit in units:
            if (
                unit.api_name == "TFT16_Nidalee"
                and hasattr(unit, "_huntress_active")
                and hasattr(unit, "_huntress_neeko_id")
                and unit._huntress_neeko_id == id(dead_unit)
            ):
                # Remove Huntress buffs
                unit._huntress_active = False
                unit.is_basic_attack_immune = False
                unit.stats.damage_reduction = max(
                    0, unit.stats.damage_reduction - self.HUNTRESS_DURABILITY
                )

    def check_freljord_on_death(self, dead_unit: "Unit", all_units: List["Unit"]):
        """Freljord Tower destruction: stun enemies ONLY at 7 Freljord.

        At 3/5 Freljord: no stun on tower break (stats only).
        At 7 Freljord: stun the ENTIRE enemy team for 1.5s.

        Args:
            dead_unit: The unit that just died (only triggers for tower)
            all_units: All units in combat
        """
        # Only trigger when a Freljord tower is destroyed
        if not (
            getattr(dead_unit, "_is_tower", False) and dead_unit.api_name == "TFT16_FreljordProp"
        ):
            return

        by_team = getattr(self, "_freljord_by_team", {})
        freljord_count = by_team.get(dead_unit.team, 0)

        # Stun only triggers at 7 Freljord
        if freljord_count < 7:
            return

        effects = self.get_trait_tier(freljord_count, self.FRELJORD_EFFECTS)
        if not effects or "StunDuration" not in effects:
            return

        stun_duration = effects["StunDuration"]

        # 7 Freljord: stun entire enemy team
        enemies = [u for u in all_units if u.team != dead_unit.team and u.is_alive]
        for enemy in enemies:
            enemy.stun_timer = max(getattr(enemy, "stun_timer", 0), stun_duration)
            enemy.state = UnitState.STUNNED

    # =========================================================================
    # STAT-BUFFING TRAITS
    # =========================================================================

    # Arcanist (Sorcerer) - Team AP + bonus for Arcanists
    ARCANIST_EFFECTS = {
        2: {"AllyAP": 18, "BonusAP": 25},
        4: {"AllyAP": 25, "BonusAP": 40},
        6: {"AllyAP": 40, "BonusAP": 60},
    }

    # Defender - Team armor/MR + bonus for Defenders
    DEFENDER_EFFECTS = {
        2: {"TeamwideArmorMR": 12, "BonusArmorMR": 30},
        4: {"TeamwideArmorMR": 12, "BonusArmorMR": 55},
        6: {"TeamwideArmorMR": 12, "BonusArmorMR": 80},
    }

    # Bruiser (Brawler) - Team flat HP + bonus % HP for Bruisers
    BRUISER_EFFECTS = {
        2: {"TeamFlatHealth": 150, "BonusPercentHealth": 0.25},
        4: {"TeamFlatHealth": 150, "BonusPercentHealth": 0.45},
        6: {"TeamFlatHealth": 150, "BonusPercentHealth": 0.65},
    }

    # Slayer - AD + Omnivamp (scaling with missing HP handled in combat)
    SLAYER_EFFECTS = {
        2: {"BonusAD": 0.22, "BonusOmnivamp": 0.10, "AmountIncrease": 0.5},
        4: {"BonusAD": 0.33, "BonusOmnivamp": 0.16, "AmountIncrease": 0.5},
        6: {"BonusAD": 0.44, "BonusOmnivamp": 0.20, "AmountIncrease": 0.5},
    }

    # Juggernaut - Durability (more when above 50% HP) + heal allies on death
    JUGGERNAUT_EFFECTS = {
        2: {"BaseDR": 0.18, "IncreasedDR": 0.25, "HealRatio": 0.05},
        4: {"BaseDR": 0.20, "IncreasedDR": 0.30, "HealRatio": 0.05},
        6: {"BaseDR": 0.26, "IncreasedDR": 0.36, "HealRatio": 0.05},
    }

    # Invoker - Team mana regen + % mana increase for Invokers
    INVOKER_EFFECTS = {
        2: {"TeamBonusMana": 1, "PercentManaIncrease": 0.25},
        4: {"TeamBonusMana": 1, "PercentManaIncrease": 0.40},
    }

    # Vanquisher - Crit chance + crit damage (abilities can crit)
    VANQUISHER_EFFECTS = {
        2: {"BaseCritChance": 15, "CritDmg": 15},
        3: {"BaseCritChance": 20, "CritDmg": 20},
        4: {"BaseCritChance": 25, "CritDmg": 25},
        5: {"BaseCritChance": 30, "CritDmg": 30},
    }

    # Longshot - Damage amp + per-hex bonus
    LONGSHOT_EFFECTS = {
        2: {"BaseDamageAmp": 0.18, "PercentDamageIncrease": 0.02},
        3: {"BaseDamageAmp": 0.24, "PercentDamageIncrease": 0.03},
        4: {"BaseDamageAmp": 0.28, "PercentDamageIncrease": 0.04},
        5: {"BaseDamageAmp": 0.32, "PercentDamageIncrease": 0.05},
    }

    # Quickstriker (Rapidfire) - Team AS + bonus AS based on target's missing HP
    QUICKSTRIKER_EFFECTS = {
        2: {"TeamwideAS": 0.15, "MinBonusAS": 0.10, "MaxBonusAS": 0.30},
        3: {"TeamwideAS": 0.15, "MinBonusAS": 0.20, "MaxBonusAS": 0.45},
        4: {"TeamwideAS": 0.15, "MinBonusAS": 0.30, "MaxBonusAS": 0.60},
        5: {"TeamwideAS": 0.15, "MinBonusAS": 0.40, "MaxBonusAS": 0.80},
    }

    # Gunslinger - AD + every 4th attack bonus damage
    # Patch 16.4: AD 20/35% → 22/40%
    GUNSLINGER_EFFECTS = {
        2: {"AD": 0.22, "BonusDamage": 100, "NumAttacks": 4},
        4: {"AD": 0.40, "BonusDamage": 200, "NumAttacks": 4},
    }

    # Warden - Shields at HP thresholds (75% and 25%)
    WARDEN_EFFECTS = {
        2: {"PercentHealthShield": 0.16, "FirstThreshold": 0.75, "SecondThreshold": 0.25},
        3: {"PercentHealthShield": 0.20, "FirstThreshold": 0.75, "SecondThreshold": 0.25},
        4: {"PercentHealthShield": 0.26, "FirstThreshold": 0.75, "SecondThreshold": 0.25},
        5: {"PercentHealthShield": 0.33, "FirstThreshold": 0.75, "SecondThreshold": 0.25},
    }

    # =====================================================================
    # REGION TRAITS
    # =====================================================================

    # Demacia - Armor/MR for Demacia units
    DEMACIA_EFFECTS = {
        3: {"ArmorMR": 12},
        5: {"ArmorMR": 35},
        7: {"ArmorMR": 35},
        11: {"ArmorMR": 150},
    }

    # Freljord - Tower-based area buffs
    # A Frozen Tower is placed on the board before combat.
    # Units in front of the tower (toward row 0) get HP buff.
    # Units behind the tower (toward row 3) get damage buff.
    # The tower's area follows a 3-2-3-2 width pattern per row.
    # 3 Freljord: one tower, stats only (no stun)
    # 5 Freljord: second tower + increased stats (no stun)
    # 7 Freljord: stun ENTIRE enemy team when ANY tower is destroyed
    FRELJORD_EFFECTS = {
        3: {"HealthPercent": 0.08, "DA": 0.10},
        5: {"HealthPercent": 0.12, "DA": 0.16},
        7: {"HealthPercent": 0.16, "DA": 0.22, "StunDuration": 1.5},
    }

    # Void - AS for Void units
    VOID_EFFECTS = {
        2: {"BonusAS": 0.08},
        4: {"BonusAS": 0.18},
        6: {"BonusAS": 0.33},
        9: {"BonusAS": 0.40},
    }

    # Shurima - HP% + heal/sec + ArmorMR at higher tiers
    SHURIMA_EFFECTS = {
        2: {"BonusHealth": 0.20, "HealthRestorePerSecond": 20, "ASPerSecond": 0.02, "ArmorMR": 0},
        3: {"BonusHealth": 0.20, "HealthRestorePerSecond": 20, "ASPerSecond": 0.02, "ArmorMR": 50},
        4: {"BonusHealth": 0.20, "HealthRestorePerSecond": 20, "ASPerSecond": 0.02, "ArmorMR": 50},
    }

    # Yordle - flat HP + AS for Yordle units
    YORDLE_EFFECTS = {
        2: {"AS": 0.05, "BonusHealth": 40},
        4: {"AS": 0.05, "BonusHealth": 40},
        6: {"AS": 0.05, "BonusHealth": 40},
        8: {"AS": 0.05, "BonusHealth": 40},
        10: {"AS": 0.05, "BonusHealth": 40},
    }

    # Ixtal - HP for pairs + healing
    IXTAL_EFFECTS = {
        5: {"BonusHealthPairs": 250, "Heal": 2.0},
        7: {"BonusHealthPairs": 250, "Heal": 2.0},
    }

    # Zaun - Shimmer Fuse: delayed AS + durability burst (combat-time mechanic)
    ZAUN_EFFECTS = {
        3: {
            "ShimmerAS": 0.90,
            "ShimmerDurability": 0.15,
            "ShimmerDuration": 4.0,
            "InitialDelay": 4.0,
            "HealThreshold": 0.60,
        },
        5: {
            "ShimmerAS": 0.90,
            "ShimmerDurability": 0.15,
            "ShimmerDuration": 4.0,
            "InitialDelay": 4.0,
            "HealThreshold": 0.60,
            "MaxHealthHeal": 0.30,
        },
        7: {
            "ShimmerAS": 0.90,
            "ShimmerDurability": 0.15,
            "ShimmerDuration": 4.0,
            "InitialDelay": 4.0,
            "HealThreshold": 0.60,
            "MaxHealthHeal": 0.30,
        },
    }

    # Noxus - Atakhan summoning trait
    # After enemy team loses 15% total HP, Atakhan is summoned.
    # Atakhan's star level = sum of all Noxian star levels on the team.
    # Noxus breakpoints unlock different Atakhan abilities:
    #   3: Cleave (slash enemies dealing magic damage)
    #   5: Damage amp (Noxians get stacking damage amp while Atakhan alive)
    #   7: Soul drain (DOT ability on cast)
    #  10: Bring Ruin (after 10s, devour ALL enemy units)
    # Health multiplier scales by Noxus count and game stage.
    NOXUS_EFFECTS = {
        3: {"HPLostTrigger": 0.15, "RuinTimer": 10},
        5: {"HPLostTrigger": 0.15, "RuinTimer": 10},
        7: {"HPLostTrigger": 0.15, "RuinTimer": 10},
        10: {"HPLostTrigger": 0.15, "RuinTimer": 10},
    }

    # Atakhan base stats by star level (from combat_data.json)
    # Star level is determined by total Noxian star levels on team
    # Index: [_, 1-star, 2-star, 3-star, 4-star, ...]
    ATAKHAN_STATS = {
        1: {
            "hp": 320,
            "ad": 50,
            "as": 0.75,
            "armor": 45,
            "mr": 45,
            "omnivamp": 0.30,
            "cleave_damage": 150,
            "per_star_hp": 112,
            "per_star_ad_pct": 0.07,
            "per_star_ap_pct": 0.07,
            "damage_amp": 0.0,
            "dot_damage": 0,
            "dot_duration": 0,
        },
        2: {
            "hp": 560,
            "ad": 50,
            "as": 0.90,
            "armor": 60,
            "mr": 60,
            "omnivamp": 0.30,
            "cleave_damage": 225,
            "per_star_hp": 112,
            "per_star_ad_pct": 0.07,
            "per_star_ap_pct": 0.07,
            "damage_amp": 0.03,
            "dot_damage": 0,
            "dot_duration": 0,
        },
        3: {
            "hp": 800,
            "ad": 50,
            "as": 1.01,
            "armor": 75,
            "mr": 75,
            "omnivamp": 0.30,
            "cleave_damage": 340,
            "per_star_hp": 112,
            "per_star_ad_pct": 0.11,
            "per_star_ap_pct": 0.11,
            "damage_amp": 0.03,
            "dot_damage": 750,
            "dot_duration": 2.5,
        },
        4: {
            "hp": 16640,
            "ad": 50,
            "as": 1.61,
            "armor": 150,
            "mr": 150,
            "omnivamp": 1.0,
            "cleave_damage": 500,
            "per_star_hp": 112,
            "per_star_ad_pct": 0.20,
            "per_star_ap_pct": 0.20,
            "damage_amp": 0.03,
            "dot_damage": 750,
            "dot_duration": 30.0,
        },
    }

    # Atakhan star thresholds: total Noxian stars needed for each Atakhan tier
    # 3 Noxians all 1-star = 3 total => 1-star Atakhan
    # Typical 5 Noxians at 2-star = 10 total => 2-star
    # Typical 7 Noxians at 2-star = 14 total => 3-star
    # 10 Noxians at high stars = 4-star
    ATAKHAN_STAR_THRESHOLDS = [0, 3, 8, 14, 22]  # [_, 1*, 2*, 3*, 4*]

    # Noxus health multiplier by stage (patch 16.2 values)
    NOXUS_HP_MULTIPLIER = {
        5: {4: 4.5, 5: 5.25, 6: 6.5},
        7: {4: 5.75, 5: 7.25, 6: 9.25},
    }

    # Ionia - multiple sub-effects (simplified: use Determination path stats)
    IONIA_EFFECTS = {
        3: {"FlatDamage": 20, "Resists": 15, "ADAP": 10, "HealthPercent": 0.25},
        5: {"FlatDamage": 40, "Resists": 25, "ADAP": 15, "HealthPercent": 0.30},
        7: {"FlatDamage": 60, "Resists": 40, "ADAP": 20, "HealthPercent": 0.35},
        10: {"FlatDamage": 100, "Resists": 75, "ADAP": 100, "HealthPercent": 0.75},
    }

    # =====================================================================
    # CLASS TRAITS (missing)
    # =====================================================================

    # Disruptor - Damage amp + DR for Disruptor units
    DISRUPTOR_EFFECTS = {
        2: {"DamageAmp": 0.18, "DamageReduction": 0.10},
        4: {"DamageAmp": 0.40, "DamageReduction": 0.10},
    }

    # =====================================================================
    # UNIQUE / SPECIAL TRAITS
    # =====================================================================

    # Darkin - Omnivamp for Darkin units
    DARKIN_EFFECTS = {
        1: {"Vamp": 0.15},
        2: {"Vamp": 0.15},
        3: {"Vamp": 0.15},
    }

    # World Ender (Aatrox) - Durability + mana reduction
    WORLD_ENDER_EFFECTS = {
        1: {"Durability": 0.20, "ManaReduction": 10},
    }

    # Harvester (Fiddlesticks) - Enemy resist reduction + mana on kill
    HARVESTER_EFFECTS = {
        1: {"EnemyArmorMRReduction": 10, "ManaPerEnemyDeath": 10},
    }

    # Dragonborn (Shyvana) - Ability damage reduction
    DRAGONBORN_EFFECTS = {
        1: {"AbilityDamageReduction": 0.08},
    }

    # Soulbound (Lucian) - Damage amp for Lucian, DR for Senna
    SOULBOUND_EFFECTS = {
        1: {"LucianDA": 0.07, "SennaDR": 0.07},
    }

    # Eternal (Kindred) - Percent damage multiplier
    ETERNAL_EFFECTS = {
        1: {"PercentDamageMult": 3.25},
    }

    # The Boss (Sett) - Transform below HP threshold
    THE_BOSS_EFFECTS = {
        1: {"AttackSpeedPercent": 0.60, "HealPercent": 0.15, "MaxHealthThreshold": 0.45},
    }

    # Chosen Wolves (Ambessa + Kindred pair)
    CHOSEN_WOLVES_EFFECTS = {
        2: {"AmbessaBonusAD": 0.40, "WolfDamage": 0.30},
    }

    # Dragonguards (Jarvan + Shyvana pair)
    DRAGONGUARDS_EFFECTS = {
        2: {"JarvanShieldShare": 1.0},
    }

    # Sentinels of Light (Lucian + Vayne pair)
    SENTINELS_EFFECTS = {
        2: {"LucianSennaAS": 0.50, "NumBonusBolts": 2, "BoltEffectiveness": 0.25},
    }

    # Poison Pals (Singed + Teemo pair)
    POISON_PALS_EFFECTS = {
        2: {"SingedAPGain": 2, "TeemoDamageReq": 100},
    }

    # Timewinders (Ekko + Zilean)
    TIMEWINDERS_EFFECTS = {
        1: {"DamageShare": 0.10},
        2: {"DamageShare": 0.10},
    }

    def get_trait_tier(self, trait_count: int, effects_dict: Dict) -> Optional[Dict]:
        """Get the appropriate effect tier for a trait count.

        Args:
            trait_count: Number of units with the trait
            effects_dict: The trait's effect dictionary (e.g., ARCANIST_EFFECTS)

        Returns:
            The effect values for that tier, or None if not enough units
        """
        if trait_count < min(effects_dict.keys()):
            return None

        # Find highest qualifying tier
        for tier in sorted(effects_dict.keys(), reverse=True):
            if trait_count >= tier:
                return effects_dict[tier]
        return None

    def apply_stat_traits(
        self, team: List["Unit"], trait_counts: Dict[str, int], enemy_team: List["Unit"] = None
    ):
        """Apply all stat-buffing traits to a team at combat start.

        Args:
            team: List of units on this team
            trait_counts: Dict of trait name -> count for this team
            enemy_team: Enemy team (needed for Harvester resist reduction)
        """
        # --- CLASS TRAITS ---
        self._apply_arcanist(team, trait_counts.get("Arcanist", 0))
        self._apply_defender(team, trait_counts.get("Defender", 0))
        self._apply_bruiser(team, trait_counts.get("Bruiser", 0))
        self._apply_slayer(team, trait_counts.get("Slayer", 0))
        self._apply_juggernaut(team, trait_counts.get("Juggernaut", 0))
        self._apply_invoker(team, trait_counts.get("Invoker", 0))
        self._apply_vanquisher(team, trait_counts.get("Vanquisher", 0))
        self._apply_longshot(team, trait_counts.get("Longshot", 0))
        self._apply_quickstriker(team, trait_counts.get("Quickstriker", 0))
        self._apply_gunslinger(team, trait_counts.get("Gunslinger", 0))
        self._apply_warden(team, trait_counts.get("Warden", 0))
        self._apply_disruptor(team, trait_counts.get("Disruptor", 0))

        # --- REGION TRAITS ---
        self._apply_demacia(team, trait_counts.get("Demacia", 0))
        self._apply_freljord(team, trait_counts.get("Freljord", 0))
        self._apply_void(team, trait_counts.get("Void", 0))
        self._apply_shurima(team, trait_counts.get("Shurima", 0))
        self._apply_yordle(team, trait_counts.get("Yordle", 0))
        self._apply_ixtal(team, trait_counts.get("Ixtal", 0))
        self._apply_zaun(team, trait_counts.get("Zaun", 0))
        self._apply_noxus(team, trait_counts.get("Noxus", 0))
        self._apply_ionia(team, trait_counts.get("Ionia", 0))

        # --- UNIQUE TRAITS ---
        self._apply_darkin(team, trait_counts.get("Darkin", 0))
        self._apply_world_ender(team, trait_counts.get("World Ender", 0))
        self._apply_dragonborn(team, trait_counts.get("Dragonborn", 0))
        self._apply_soulbound(team, trait_counts.get("Soulbound", 0))
        self._apply_eternal(team, trait_counts.get("Eternal", 0))
        self._apply_the_boss(team, trait_counts.get("The Boss", 0))

        # Harvester needs enemy team reference
        if enemy_team is not None:
            self._apply_harvester(team, [team, enemy_team], trait_counts.get("Harvester", 0))
        else:
            self._apply_harvester(team, [team], trait_counts.get("Harvester", 0))

        # Huntress: Neeko + Nidalee synergy
        self.apply_huntress_synergy(team)

        # --- PAIR SYNERGIES ---
        self._apply_pair_synergies(team, trait_counts)

    def _apply_arcanist(self, team: List["Unit"], count: int):
        """Apply Arcanist trait: Team AP + bonus for Arcanists."""
        effects = self.get_trait_tier(count, self.ARCANIST_EFFECTS)
        if not effects:
            return

        ally_ap = effects["AllyAP"]
        bonus_ap = effects["BonusAP"]

        for unit in team:
            # All allies get base AP
            unit.stats.ap += ally_ap

            # Arcanists get additional bonus
            if "Arcanist" in unit.traits:
                unit.stats.ap += bonus_ap

    def _apply_defender(self, team: List["Unit"], count: int):
        """Apply Defender trait: Team armor/MR + bonus for Defenders."""
        effects = self.get_trait_tier(count, self.DEFENDER_EFFECTS)
        if not effects:
            return

        teamwide = effects["TeamwideArmorMR"]
        bonus = effects["BonusArmorMR"]

        for unit in team:
            # All allies get base armor/MR
            unit.stats.armor += teamwide
            unit.stats.magic_resist += teamwide

            # Defenders get additional bonus
            if "Defender" in unit.traits:
                unit.stats.armor += bonus
                unit.stats.magic_resist += bonus

    def _apply_bruiser(self, team: List["Unit"], count: int):
        """Apply Bruiser trait: Team flat HP + bonus % HP for Bruisers."""
        effects = self.get_trait_tier(count, self.BRUISER_EFFECTS)
        if not effects:
            return

        flat_hp = effects["TeamFlatHealth"]
        bonus_percent = effects["BonusPercentHealth"]

        for unit in team:
            # All allies get flat HP
            unit.stats.max_hp += flat_hp
            unit.stats.hp += flat_hp

            # Bruisers get additional % HP
            if "Bruiser" in unit.traits:
                bonus_hp = unit.base_stats.max_hp * bonus_percent
                unit.stats.max_hp += bonus_hp
                unit.stats.hp += bonus_hp

    def _apply_slayer(self, team: List["Unit"], count: int):
        """Apply Slayer trait: AD + Omnivamp for Slayers.

        Note: The missing HP AD scaling is handled during combat ticks.
        """
        effects = self.get_trait_tier(count, self.SLAYER_EFFECTS)
        if not effects:
            return

        bonus_ad_percent = effects["BonusAD"]
        bonus_omnivamp = effects["BonusOmnivamp"]

        for unit in team:
            if "Slayer" in unit.traits:
                # AD bonus (percentage of base)
                ad_bonus = unit.base_stats.ad * bonus_ad_percent
                unit.stats.ad += ad_bonus
                # Omnivamp
                unit.stats.omnivamp += bonus_omnivamp
                # Store the scaling factor for combat calculations
                unit._slayer_ad_increase = effects["AmountIncrease"]

    def _apply_juggernaut(self, team: List["Unit"], count: int):
        """Apply Juggernaut trait: Durability for Juggernauts.

        Note: The HP-conditional durability is handled during combat.
        """
        effects = self.get_trait_tier(count, self.JUGGERNAUT_EFFECTS)
        if not effects:
            return

        for unit in team:
            if "Juggernaut" in unit.traits:
                # Store Juggernaut data for combat calculations
                unit._juggernaut_base_dr = effects["BaseDR"]
                unit._juggernaut_increased_dr = effects["IncreasedDR"]
                unit._juggernaut_heal_ratio = effects["HealRatio"]
                # Apply base DR
                unit.stats.damage_reduction += effects["BaseDR"]

    def _apply_invoker(self, team: List["Unit"], count: int):
        """Apply Invoker trait: Team mana regen + % mana increase for Invokers."""
        effects = self.get_trait_tier(count, self.INVOKER_EFFECTS)
        if not effects:
            return

        team_mana = effects["TeamBonusMana"]
        percent_mana = effects["PercentManaIncrease"]

        for unit in team:
            # All allies get mana regen
            unit.stats.mana_regen += team_mana

            # Invokers get % increased mana gain
            if "Invoker" in unit.traits:
                unit._invoker_mana_increase = percent_mana

    def _apply_vanquisher(self, team: List["Unit"], count: int):
        """Apply Vanquisher trait: Crit chance + crit damage (abilities can crit)."""
        effects = self.get_trait_tier(count, self.VANQUISHER_EFFECTS)
        if not effects:
            return

        crit_chance = effects["BaseCritChance"] / 100  # Convert to decimal
        crit_dmg = effects["CritDmg"] / 100  # Convert to decimal

        for unit in team:
            if "Vanquisher" in unit.traits:
                unit.stats.crit_chance += crit_chance
                unit.stats.crit_multiplier += crit_dmg
                # Mark that abilities can crit
                unit._vanquisher_ability_crit = True

    def _apply_longshot(self, team: List["Unit"], count: int):
        """Apply Longshot trait: Damage amp + per-hex bonus for Longshots."""
        effects = self.get_trait_tier(count, self.LONGSHOT_EFFECTS)
        if not effects:
            return

        base_amp = effects["BaseDamageAmp"]
        per_hex = effects["PercentDamageIncrease"]

        for unit in team:
            if "Longshot" in unit.traits:
                unit.stats.damage_amp += base_amp
                # Store per-hex bonus for combat calculations
                unit._longshot_per_hex = per_hex

    def _apply_quickstriker(self, team: List["Unit"], count: int):
        """Apply Quickstriker trait: Team AS + bonus AS for Quickstrikers.

        Note: The target-missing-HP AS scaling is handled during combat.
        """
        effects = self.get_trait_tier(count, self.QUICKSTRIKER_EFFECTS)
        if not effects:
            return

        teamwide_as = effects["TeamwideAS"]
        min_as = effects["MinBonusAS"]
        max_as = effects["MaxBonusAS"]

        for unit in team:
            # All allies get teamwide AS
            unit.stats.attack_speed += teamwide_as

            # Quickstrikers get additional scaling (stored for combat)
            if "Quickstriker" in unit.traits:
                unit._quickstriker_min_as = min_as
                unit._quickstriker_max_as = max_as

    def _apply_gunslinger(self, team: List["Unit"], count: int):
        """Apply Gunslinger trait: AD + every Nth attack bonus damage."""
        effects = self.get_trait_tier(count, self.GUNSLINGER_EFFECTS)
        if not effects:
            return

        ad_percent = effects["AD"]
        bonus_damage = effects["BonusDamage"]
        num_attacks = effects["NumAttacks"]

        for unit in team:
            if "Gunslinger" in unit.traits:
                # AD bonus
                ad_bonus = unit.base_stats.ad * ad_percent
                unit.stats.ad += ad_bonus
                # Store bonus damage info for combat
                unit._gunslinger_bonus_damage = bonus_damage
                unit._gunslinger_attack_interval = num_attacks
                unit._gunslinger_attack_counter = 0

    def _apply_warden(self, team: List["Unit"], count: int):
        """Apply Warden trait: Setup shield thresholds for Wardens.

        Wardens gain shields when dropping below HP thresholds.
        """
        effects = self.get_trait_tier(count, self.WARDEN_EFFECTS)
        if not effects:
            return

        shield_percent = effects["PercentHealthShield"]
        first_threshold = effects["FirstThreshold"]
        second_threshold = effects["SecondThreshold"]

        for unit in team:
            if "Warden" in unit.traits:
                unit._warden_shield_percent = shield_percent
                unit._warden_first_threshold = first_threshold
                unit._warden_second_threshold = second_threshold
                unit._warden_first_triggered = False
                unit._warden_second_triggered = False

    # =====================================================================
    # REGION TRAIT METHODS
    # =====================================================================

    def _apply_demacia(self, team: List["Unit"], count: int):
        """Apply Demacia trait: Armor/MR for Demacia units."""
        effects = self.get_trait_tier(count, self.DEMACIA_EFFECTS)
        if not effects:
            return

        armor_mr = effects["ArmorMR"]

        for unit in team:
            if "Demacia" in unit.traits:
                unit.stats.armor += armor_mr
                unit.stats.magic_resist += armor_mr

    @staticmethod
    def _get_tower_zone(tower_pos: Tuple[int, int]) -> dict:
        """Compute the Freljord tower's area-of-effect zones.

        The tower affects hexes in a 3-2-3-2 width pattern:
        - At the tower's row: 3 wide (tower + 1 left + 1 right)
        - 1 row away: 2 wide
        - 2 rows away: 3 wide
        - 3 rows away: 2 wide

        Units in front of the tower (lower row = closer to enemy) get HP buff.
        Units directly beside the tower (same row) also get HP buff.
        Units behind the tower (higher row = toward back) get damage buff.

        Returns:
            {'hp': set of (row, col), 'damage': set of (row, col)}
        """
        t_row, t_col = tower_pos
        hp_hexes = set()
        damage_hexes = set()

        # Width pattern per row offset: 0→3, 1→2, 2→3, 3→2
        width_pattern = {0: 3, 1: 2, 2: 3, 3: 2}

        for row_offset in range(-3, 4):  # -3 to +3 rows from tower
            target_row = t_row + row_offset
            if target_row < 0 or target_row >= 4:
                continue

            abs_offset = abs(row_offset)
            if abs_offset > 3:
                continue

            width = width_pattern.get(abs_offset, 0)

            # Calculate which columns are in range
            # Width 3: col-1, col, col+1
            # Width 2: col, col+1 (or col-1, col depending on hex parity)
            if width == 3:
                cols = [t_col - 1, t_col, t_col + 1]
            elif width == 2:
                # For even offset rows: center on tower col
                cols = [t_col, t_col + 1] if t_col % 2 == 0 else [t_col - 1, t_col]
            else:
                cols = [t_col]

            valid_cols = [c for c in cols if 0 <= c < 7]

            for col in valid_cols:
                pos = (target_row, col)
                if pos == tower_pos:
                    continue  # Tower hex itself

                if row_offset < 0:
                    # In front of tower (lower row = toward front/enemy side)
                    hp_hexes.add(pos)
                elif row_offset > 0:
                    # Behind tower (higher row = toward back)
                    damage_hexes.add(pos)
                else:
                    # Same row as tower (beside it) = HP buff
                    hp_hexes.add(pos)

        return {"hp": hp_hexes, "damage": damage_hexes}

    def _apply_freljord(self, team: List["Unit"], count: int):
        """Apply Freljord trait via the Frozen Tower's area buffs.

        The tower provides directional buffs based on unit position:
        - HP buff to units in front of / beside the tower
        - Damage buff to units behind the tower
        Both scale with Freljord count (3/5/7 breakpoints).

        Also stores the count per team for tower destruction stun.
        """
        if not hasattr(self, "_freljord_by_team"):
            self._freljord_by_team = {}
        if team:
            team_id = team[0].team
            self._freljord_by_team[team_id] = count

        effects = self.get_trait_tier(count, self.FRELJORD_EFFECTS)
        if not effects:
            return

        hp_percent = effects["HealthPercent"]
        damage_amp = effects["DA"]

        # Find the Freljord tower on this team
        tower = None
        for unit in team:
            if getattr(unit, "_is_tower", False) and unit.api_name == "TFT16_FreljordProp":
                tower = unit
                break

        if tower:
            # Use tower position for directional buffs
            zones = self._get_tower_zone(tower.position)
            hp_zone = zones["hp"]
            damage_zone = zones["damage"]

            for unit in team:
                if unit == tower:
                    continue
                if unit.position in hp_zone:
                    bonus_hp = unit.base_stats.max_hp * hp_percent
                    unit.stats.max_hp += bonus_hp
                    unit.stats.hp += bonus_hp
                elif unit.position in damage_zone:
                    unit.stats.damage_amp += damage_amp
        else:
            # No tower placed - fall back to basic Freljord buff on Freljord units
            for unit in team:
                if "Freljord" in unit.traits:
                    bonus_hp = unit.base_stats.max_hp * hp_percent
                    unit.stats.max_hp += bonus_hp
                    unit.stats.hp += bonus_hp
                    unit.stats.damage_amp += damage_amp

    def _apply_void(self, team: List["Unit"], count: int):
        """Apply Void trait: Attack speed for Void units."""
        effects = self.get_trait_tier(count, self.VOID_EFFECTS)
        if not effects:
            return

        bonus_as = effects["BonusAS"]

        for unit in team:
            if "Void" in unit.traits:
                unit.stats.attack_speed += bonus_as

    def _apply_shurima(self, team: List["Unit"], count: int):
        """Apply Shurima trait: HP% + heal/sec + armor/MR at higher tiers."""
        effects = self.get_trait_tier(count, self.SHURIMA_EFFECTS)
        if not effects:
            return

        hp_percent = effects["BonusHealth"]
        heal_per_sec = effects["HealthRestorePerSecond"]
        armor_mr = effects.get("ArmorMR", 0)

        for unit in team:
            if "Shurima" in unit.traits:
                bonus_hp = unit.base_stats.max_hp * hp_percent
                unit.stats.max_hp += bonus_hp
                unit.stats.hp += bonus_hp
                # Store heal per second for combat-time application
                unit._shurima_heal_per_sec = heal_per_sec
                if armor_mr:
                    unit.stats.armor += armor_mr
                    unit.stats.magic_resist += armor_mr

    def _apply_yordle(self, team: List["Unit"], count: int):
        """Apply Yordle trait: AS + flat HP for Yordle units."""
        effects = self.get_trait_tier(count, self.YORDLE_EFFECTS)
        if not effects:
            return

        bonus_as = effects["AS"]
        bonus_hp = effects["BonusHealth"]

        for unit in team:
            if "Yordle" in unit.traits:
                unit.stats.attack_speed += bonus_as
                unit.stats.max_hp += bonus_hp
                unit.stats.hp += bonus_hp

    def _apply_ixtal(self, team: List["Unit"], count: int):
        """Apply Ixtal trait: Flat HP per pair of Ixtal units + healing."""
        effects = self.get_trait_tier(count, self.IXTAL_EFFECTS)
        if not effects:
            return

        hp_per_pair = effects["BonusHealthPairs"]
        heal = effects["Heal"]
        num_pairs = count // 2

        for unit in team:
            if "Ixtal" in unit.traits:
                bonus_hp = hp_per_pair * num_pairs
                unit.stats.max_hp += bonus_hp
                unit.stats.hp += bonus_hp
                # Store heal rate for combat-time
                unit._ixtal_heal_per_sec = heal

    def _apply_zaun(self, team: List["Unit"], count: int):
        """Apply Zaun trait: Setup Shimmer Fuse data for combat-time activation.

        Zaun units gain a delayed AS + durability burst during combat.
        """
        effects = self.get_trait_tier(count, self.ZAUN_EFFECTS)
        if not effects:
            return

        for unit in team:
            if "Zaun" in unit.traits:
                unit._zaun_shimmer_as = effects["ShimmerAS"]
                unit._zaun_shimmer_durability = effects["ShimmerDurability"]
                unit._zaun_shimmer_duration = effects["ShimmerDuration"]
                unit._zaun_initial_delay = effects["InitialDelay"]
                unit._zaun_shimmer_active = False
                unit._zaun_shimmer_triggered = False
                unit._zaun_heal_threshold = effects["HealThreshold"]
                unit._zaun_max_health_heal = effects.get("MaxHealthHeal", 0)

    def _apply_noxus(self, team: List["Unit"], count: int):
        """Apply Noxus trait: Set up Atakhan summoning for combat.

        After the enemy team loses 15% of total HP, Atakhan is summoned.
        Atakhan's star level = sum of all Noxian star levels.
        Noxus breakpoints (3/5/7/10) unlock different Atakhan abilities.
        """
        effects = self.get_trait_tier(count, self.NOXUS_EFFECTS)
        if not effects:
            return

        # Calculate total Noxian star levels for Atakhan's power
        total_noxian_stars = 0
        for unit in team:
            if "Noxus" in unit.traits:
                total_noxian_stars += unit.star_level

        # Determine Atakhan's star level from thresholds
        atakhan_star = 1
        for star, threshold in enumerate(self.ATAKHAN_STAR_THRESHOLDS):
            if star == 0:
                continue
            if total_noxian_stars >= threshold:
                atakhan_star = star

        # Store Noxus data on the team for mid-combat summoning
        if not hasattr(self, "_noxus_team_data"):
            self._noxus_team_data = {}

        team_id = team[0].team if team else 0
        self._noxus_team_data[team_id] = {
            "count": count,
            "total_stars": total_noxian_stars,
            "atakhan_star": atakhan_star,
            "hp_trigger": effects["HPLostTrigger"],
            "ruin_timer": effects.get("RuinTimer", 10),
            "summoned": False,
            "team": team,
        }

    def _apply_ionia(self, team: List["Unit"], count: int):
        """Apply Ionia trait: Simplified stat buffs for Ionia units.

        In the real game, each Ionia unit picks a random 'path' (Spirit,
        Determination, Enlightenment, etc.). Simplified to average stat buffs.
        """
        effects = self.get_trait_tier(count, self.IONIA_EFFECTS)
        if not effects:
            return

        resists = effects["Resists"]
        adap = effects["ADAP"]
        hp_percent = effects["HealthPercent"]

        for unit in team:
            if "Ionia" in unit.traits:
                unit.stats.armor += resists
                unit.stats.magic_resist += resists
                unit.stats.ad += adap
                unit.stats.ap += adap
                bonus_hp = unit.base_stats.max_hp * hp_percent
                unit.stats.max_hp += bonus_hp
                unit.stats.hp += bonus_hp

    # =====================================================================
    # MISSING CLASS TRAIT METHODS
    # =====================================================================

    def _apply_disruptor(self, team: List["Unit"], count: int):
        """Apply Disruptor trait: Damage amp + DR for Disruptor units."""
        effects = self.get_trait_tier(count, self.DISRUPTOR_EFFECTS)
        if not effects:
            return

        damage_amp = effects["DamageAmp"]
        damage_reduction = effects["DamageReduction"]

        for unit in team:
            if "Disruptor" in unit.traits:
                unit.stats.damage_amp += damage_amp
                unit.stats.damage_reduction += damage_reduction

    # =====================================================================
    # UNIQUE / SPECIAL TRAIT METHODS
    # =====================================================================

    def _apply_darkin(self, team: List["Unit"], count: int):
        """Apply Darkin trait: Omnivamp for Darkin units."""
        effects = self.get_trait_tier(count, self.DARKIN_EFFECTS)
        if not effects:
            return

        vamp = effects["Vamp"]

        for unit in team:
            if "Darkin" in unit.traits:
                unit.stats.omnivamp += vamp

    def _apply_world_ender(self, team: List["Unit"], count: int):
        """Apply World Ender trait: Durability + mana reduction for Aatrox."""
        effects = self.get_trait_tier(count, self.WORLD_ENDER_EFFECTS)
        if not effects:
            return

        durability = effects["Durability"]
        mana_reduction = effects["ManaReduction"]

        for unit in team:
            if "World Ender" in unit.traits:
                unit.stats.damage_reduction += durability
                unit.stats.mana = max(0, unit.stats.mana - mana_reduction)

    def _apply_harvester(self, team: List["Unit"], all_teams: List[List["Unit"]], count: int):
        """Apply Harvester trait: Reduce enemy resists + mana on kill.

        Args:
            team: Friendly team
            all_teams: All teams (to apply resist reduction to enemies)
            count: Number of Harvester units
        """
        effects = self.get_trait_tier(count, self.HARVESTER_EFFECTS)
        if not effects:
            return

        resist_reduction = effects["EnemyArmorMRReduction"]
        mana_per_kill = effects["ManaPerEnemyDeath"]

        # Apply resist reduction to enemy team
        for other_team in all_teams:
            if other_team is not team:
                for enemy in other_team:
                    enemy.stats.armor = max(0, enemy.stats.armor - resist_reduction)
                    enemy.stats.magic_resist = max(0, enemy.stats.magic_resist - resist_reduction)

        # Store mana-on-kill for combat-time
        for unit in team:
            if "Harvester" in unit.traits:
                unit._harvester_mana_per_kill = mana_per_kill

    def _apply_dragonborn(self, team: List["Unit"], count: int):
        """Apply Dragonborn trait: Ability damage reduction for Shyvana."""
        effects = self.get_trait_tier(count, self.DRAGONBORN_EFFECTS)
        if not effects:
            return

        ability_dr = effects["AbilityDamageReduction"]

        for unit in team:
            if "Dragonborn" in unit.traits:
                unit._dragonborn_ability_dr = ability_dr

    def _apply_soulbound(self, team: List["Unit"], count: int):
        """Apply Soulbound trait: Damage amp for Lucian."""
        effects = self.get_trait_tier(count, self.SOULBOUND_EFFECTS)
        if not effects:
            return

        lucian_da = effects["LucianDA"]

        for unit in team:
            if "Soulbound" in unit.traits:
                unit.stats.damage_amp += lucian_da

    def _apply_eternal(self, team: List["Unit"], count: int):
        """Apply Eternal trait: Increased damage multiplier for Kindred."""
        effects = self.get_trait_tier(count, self.ETERNAL_EFFECTS)
        if not effects:
            return

        damage_mult = effects["PercentDamageMult"]

        for unit in team:
            if "Eternal" in unit.traits:
                unit._eternal_damage_mult = damage_mult

    def _apply_the_boss(self, team: List["Unit"], count: int):
        """Apply The Boss trait: Transform data for Sett below HP threshold."""
        effects = self.get_trait_tier(count, self.THE_BOSS_EFFECTS)
        if not effects:
            return

        for unit in team:
            if "The Boss" in unit.traits:
                unit._boss_as_bonus = effects["AttackSpeedPercent"]
                unit._boss_heal_percent = effects["HealPercent"]
                unit._boss_hp_threshold = effects["MaxHealthThreshold"]
                unit._boss_transformed = False

    def _apply_pair_synergies(self, team: List["Unit"], trait_counts: Dict[str, int]):
        """Apply pair synergies that require specific champion combinations."""
        # Build name lookup
        team_api_names = {u.api_name for u in team}
        team_by_api = {u.api_name: u for u in team}

        # Chosen Wolves: Ambessa + Kindred
        if "TFT16_Ambessa" in team_api_names and "TFT16_Kindred" in team_api_names:
            effects = self.CHOSEN_WOLVES_EFFECTS[2]
            ambessa = team_by_api["TFT16_Ambessa"]
            ad_bonus = ambessa.base_stats.ad * effects["AmbessaBonusAD"]
            ambessa.stats.ad += ad_bonus
            kindred = team_by_api["TFT16_Kindred"]
            kindred._wolf_bonus_damage = effects["WolfDamage"]

        # Dragonguards: Jarvan IV + Shyvana
        if "TFT16_JarvanIV" in team_api_names and "TFT16_Shyvana" in team_api_names:
            effects = self.DRAGONGUARDS_EFFECTS[2]
            jarvan = team_by_api["TFT16_JarvanIV"]
            jarvan._dragonguard_shield_share = effects["JarvanShieldShare"]

        # Sentinels of Light: Lucian + Vayne
        if "TFT16_Lucian" in team_api_names and "TFT16_Vayne" in team_api_names:
            effects = self.SENTINELS_EFFECTS[2]
            lucian = team_by_api["TFT16_Lucian"]
            lucian.stats.attack_speed += effects["LucianSennaAS"]
            lucian._sentinel_bonus_bolts = effects["NumBonusBolts"]
            lucian._sentinel_bolt_effectiveness = effects["BoltEffectiveness"]

        # Poison Pals: Singed + Teemo
        if "TFT16_Singed" in team_api_names and "TFT16_Teemo" in team_api_names:
            effects = self.POISON_PALS_EFFECTS[2]
            singed = team_by_api["TFT16_Singed"]
            singed._poison_pals_ap_gain = effects["SingedAPGain"]
            singed._poison_pals_damage_req = effects["TeemoDamageReq"]

        # Timewinders: Ekko + Zilean
        if "TFT16_Ekko" in team_api_names and "TFT16_Zilean" in team_api_names:
            effects = self.TIMEWINDERS_EFFECTS[2]
            for api_name in ["TFT16_Ekko", "TFT16_Zilean"]:
                unit = team_by_api[api_name]
                unit._timewinder_damage_share = effects["DamageShare"]
