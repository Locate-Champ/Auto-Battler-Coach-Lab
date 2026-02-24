"""
TFT Set 16 Item Effects — Lore & Legends

All item effects updated to match Set 16 in-game mechanics.
Sources: vntft.com, wiki.leagueoflegends.com, metasrc.com

Effect function signatures:
- on_hit(engine, attacker, target): Called after each auto attack hits
- on_damage_dealt(engine, attacker, target, damage, damage_type): Called after dealing damage
- on_damage_taken(engine, defender, attacker, damage, damage_type): Called after taking damage
- on_ability_cast(engine, caster): Called when ability is cast
- passive(engine, unit): Called each tick for passive effects
- combat_start(engine, unit, all_units): Called once at start of combat
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .combat_engine import CombatEngine, Unit


# =============================================================================
# TRACKING DATA (stored on units during combat)
# =============================================================================


def get_item_data(unit: "Unit", item_name: str, key: str, default=None):
    """Get item-specific tracking data from a unit."""
    if not hasattr(unit, "_item_data"):
        unit._item_data = {}
    return unit._item_data.get(f"{item_name}_{key}", default)


def set_item_data(unit: "Unit", item_name: str, key: str, value):
    """Set item-specific tracking data on a unit."""
    if not hasattr(unit, "_item_data"):
        unit._item_data = {}
    unit._item_data[f"{item_name}_{key}"] = value


# =============================================================================
# ON-HIT EFFECTS
# =============================================================================


def spear_of_shojin_on_hit(engine: "CombatEngine", attacker: "Unit", target: "Unit"):
    """Spear of Shojin: Attacks grant 5 bonus Mana."""
    engine.gain_mana(attacker, 5, source="spear_of_shojin")


def giant_slayer_on_hit(engine: "CombatEngine", attacker: "Unit", target: "Unit"):
    """Giant Slayer: 15% additional Damage Amp against Tanks.

    Check target role; if tank-like, apply bonus damage via temporary amp.
    """
    # Tanks/Defenders have tank-like roles
    role = getattr(target, "role", "")
    if role in ("APTank", "ADTank", "Tank", "Defender"):
        # Already has 15% base damage_amp from stats; grant extra 15% vs tanks
        # We track so we don't double-apply
        pass  # Handled via the item's 15% damage_amp stat + engine's calculate_damage


def last_whisper_on_hit(engine: "CombatEngine", attacker: "Unit", target: "Unit"):
    """Last Whisper: Attacks and abilities 30% Sunder target for 3 seconds."""
    engine.apply_sunder(target, 0.30, 3.0, "last_whisper")


def titans_resolve_on_hit(engine: "CombatEngine", attacker: "Unit", target: "Unit"):
    """Titan's Resolve: Gain 2% AD and 2% AP per attack, stacking up to 25 times.
    At full stacks, gain 10% Damage Amp and CC immunity.
    """
    stacks = get_item_data(attacker, "TitansResolve", "stacks", 0)

    if stacks < 25:
        stacks += 1
        set_item_data(attacker, "TitansResolve", "stacks", stacks)

        # +2% of base AD and +2% of base AP
        attacker.stats.ad += attacker.base_stats.ad * 0.02
        attacker.stats.ap += (
            2 * 0.02 * (attacker.base_stats.ap if attacker.base_stats.ap > 0 else 50)
        )

        # At 25 stacks: 10% damage amp + CC immunity
        if stacks == 25:
            attacker.stats.damage_amp += 0.10
            set_item_data(attacker, "TitansResolve", "cc_immune", True)


def titans_resolve_on_damage_taken(
    engine: "CombatEngine", defender: "Unit", attacker: "Unit", damage: float, damage_type
):
    """Titan's Resolve: Also stacks when taking damage."""
    stacks = get_item_data(defender, "TitansResolve", "stacks", 0)
    if stacks < 25:
        stacks += 1
        set_item_data(defender, "TitansResolve", "stacks", stacks)
        defender.stats.ad += defender.base_stats.ad * 0.02
        defender.stats.ap += (
            2 * 0.02 * (defender.base_stats.ap if defender.base_stats.ap > 0 else 50)
        )
        if stacks == 25:
            defender.stats.damage_amp += 0.10
            set_item_data(defender, "TitansResolve", "cc_immune", True)


def nashors_tooth_on_hit(engine: "CombatEngine", attacker: "Unit", target: "Unit"):
    """Nashor's Tooth: Attacks grant 2 bonus Mana, increased to 4 if they crit."""
    # Check if last attack was a crit (use tracking data set by process_attack)
    last_crit = getattr(attacker, "_last_attack_crit", False)
    mana_gain = 4 if last_crit else 2
    engine.gain_mana(attacker, mana_gain, source="nashors_tooth")


def krakens_fury_on_hit(engine: "CombatEngine", attacker: "Unit", target: "Unit"):
    """Kraken's Fury: +3.5% stacking AD per attack, up to 15 attacks.
    After 15 attacks, gain 15% Attack Speed.
    """
    stacks = get_item_data(attacker, "KrakensFury", "stacks", 0)

    if stacks < 15:
        stacks += 1
        set_item_data(attacker, "KrakensFury", "stacks", stacks)
        attacker.stats.ad += attacker.base_stats.ad * 0.035

        if stacks == 15:
            attacker.stats.attack_speed += 0.15


def red_buff_on_hit(engine: "CombatEngine", attacker: "Unit", target: "Unit"):
    """Red Buff: Attacks apply 1% Burn and 33% Wound for 5 seconds."""
    engine.apply_burn(attacker, target, 0.01, 5.0, "red_buff")
    engine.apply_wound(target, 5.0, "red_buff")


def void_staff_on_hit(engine: "CombatEngine", attacker: "Unit", target: "Unit"):
    """Void Staff: Attacks and abilities 30% Shred target for 5 seconds."""
    engine.apply_shred(target, 0.30, 5.0, "void_staff")


def strikers_flail_on_hit(engine: "CombatEngine", attacker: "Unit", target: "Unit"):
    """Striker's Flail: Crits grant 5% Damage Amp for 5s, stacking up to 4 times."""
    last_crit = getattr(attacker, "_last_attack_crit", False)
    if last_crit:
        stacks = get_item_data(attacker, "StrikersFlail", "stacks", 0)
        if stacks < 4:
            stacks += 1
            set_item_data(attacker, "StrikersFlail", "stacks", stacks)
            attacker.stats.damage_amp += 0.05


def wits_end_on_hit(engine: "CombatEngine", attacker: "Unit", target: "Unit"):
    """Wit's End (Artifact): Deal 42 + 20% AP magic damage on hit and heal."""
    from .combat_engine import DamageType

    on_hit_damage = 42 + (attacker.stats.ap * 0.20)
    damage, _ = engine.calculate_damage(
        attacker, target, on_hit_damage, DamageType.MAGIC, can_crit=False
    )
    engine.apply_damage(attacker, target, damage, DamageType.MAGIC, "wits_end")
    attacker.stats.hp = min(attacker.stats.max_hp, attacker.stats.hp + damage)
    attacker.total_healing += damage


def statikk_shiv_on_hit(engine: "CombatEngine", attacker: "Unit", target: "Unit"):
    """Artifact Statikk Shiv: Every 3rd attack, deal magic damage to 4 enemies."""
    from .combat_engine import DamageType, HexGrid

    attack_count = get_item_data(attacker, "StatikkShiv", "attacks", 0) + 1
    set_item_data(attacker, "StatikkShiv", "attacks", attack_count)

    if attack_count >= 3:
        set_item_data(attacker, "StatikkShiv", "attacks", 0)
        base_damage = 50 + (attacker.stats.ap * 0.30)
        enemies = [u for u in engine.units if u.team != attacker.team and u.is_alive]
        enemies.sort(key=lambda e: HexGrid.hex_distance(attacker.position, e.position))
        for enemy in enemies[:4]:
            damage, _ = engine.calculate_damage(
                attacker, enemy, base_damage, DamageType.MAGIC, can_crit=False
            )
            engine.apply_damage(attacker, enemy, damage, DamageType.MAGIC, "statikk_shiv")


def lich_bane_on_hit(engine: "CombatEngine", attacker: "Unit", target: "Unit"):
    """Lich Bane (Artifact): If empowered from ability cast, deal 200% AP magic damage."""
    from .combat_engine import DamageType

    empowered = get_item_data(attacker, "LichBane", "empowered", False)
    if empowered:
        set_item_data(attacker, "LichBane", "empowered", False)
        bonus = attacker.stats.ap * 2.0
        damage, _ = engine.calculate_damage(
            attacker, target, bonus, DamageType.MAGIC, can_crit=False
        )
        engine.apply_damage(attacker, target, damage, DamageType.MAGIC, "lich_bane")


# =============================================================================
# ON-ABILITY EFFECTS
# =============================================================================


def void_staff_on_ability(engine: "CombatEngine", caster: "Unit"):
    """Void Staff: Abilities also Shred (handled on next attack target)."""
    if caster.target and caster.target.is_alive:
        engine.apply_shred(caster.target, 0.30, 5.0, "void_staff_ability")


def adaptive_helm_on_ability(engine: "CombatEngine", caster: "Unit"):
    """Adaptive Helm: +15% Mana from all sources (passive). No on-ability effect."""
    pass  # The mana bonus is handled at combat start


def lich_bane_on_ability(engine: "CombatEngine", caster: "Unit"):
    """Lich Bane (Artifact): Empower next auto after ability."""
    set_item_data(caster, "LichBane", "empowered", True)


# =============================================================================
# ON-DAMAGE-DEALT EFFECTS
# =============================================================================


def hextech_gunblade_on_damage(
    engine: "CombatEngine", attacker: "Unit", target: "Unit", damage: float, damage_type
):
    """Hextech Gunblade: Heal the lowest % HP ally for 20% of damage dealt."""
    heal_amount = damage * 0.20
    if heal_amount <= 0:
        return

    # Find lowest % HP ally
    allies = [u for u in engine.units if u.team == attacker.team and u.is_alive]
    if not allies:
        return
    lowest_ally = min(allies, key=lambda u: u.stats.hp / u.stats.max_hp)
    engine.heal_unit(lowest_ally, heal_amount, "hextech_gunblade")


def morellonomicon_on_damage(
    engine: "CombatEngine", attacker: "Unit", target: "Unit", damage: float, damage_type
):
    """Morellonomicon: Attacks and abilities apply 1% Burn + 33% Wound for 10 seconds."""
    engine.apply_burn(attacker, target, 0.01, 10.0, "morellonomicon")
    engine.apply_wound(target, 10.0, "morellonomicon")


# =============================================================================
# ON-DAMAGE-TAKEN EFFECTS
# =============================================================================


def steraks_gage_on_damage(
    engine: "CombatEngine", defender: "Unit", attacker: "Unit", damage: float, damage_type
):
    """Sterak's Gage: At 60% HP, gain a 50% max HP shield that decays over 4 seconds."""
    triggered = get_item_data(defender, "SteraksGage", "triggered", False)
    if not triggered and defender.stats.hp <= defender.stats.max_hp * 0.60:
        set_item_data(defender, "SteraksGage", "triggered", True)
        shield_amount = defender.stats.max_hp * 0.50
        defender.stats.shield += shield_amount


def bramble_vest_on_damage(
    engine: "CombatEngine", defender: "Unit", attacker: "Unit", damage: float, damage_type
):
    """Bramble Vest: When hit, deal 100 magic damage to all adjacent enemies (2s CD).
    Also grants 5% attack damage reduction (handled via stats).
    """
    from .combat_engine import DamageType, HexGrid

    last_proc = get_item_data(defender, "BrambleVest", "last_proc", -2.0)
    if engine.time - last_proc < 2.0:
        return
    set_item_data(defender, "BrambleVest", "last_proc", engine.time)

    enemies = [
        u
        for u in engine.units
        if u.team != defender.team
        and u.is_alive
        and HexGrid.hex_distance(defender.position, u.position) <= 1
    ]
    for enemy in enemies:
        dmg, _ = engine.calculate_damage(defender, enemy, 100, DamageType.MAGIC, can_crit=False)
        engine.apply_damage(defender, enemy, dmg, DamageType.MAGIC, "bramble_vest")


def gargoyle_on_damage(
    engine: "CombatEngine", defender: "Unit", attacker: "Unit", damage: float, damage_type
):
    """Gargoyle Stoneplate: Gain 10 Armor and MR per enemy targeting you."""
    targeting_count = sum(
        1 for u in engine.units if u.team != defender.team and u.is_alive and u.target == defender
    )
    old_bonus = get_item_data(defender, "Gargoyle", "bonus", 0)
    new_bonus = targeting_count * 10
    if new_bonus != old_bonus:
        defender.stats.armor += new_bonus - old_bonus
        defender.stats.magic_resist += new_bonus - old_bonus
        set_item_data(defender, "Gargoyle", "bonus", new_bonus)


def bloodthirster_on_damage(
    engine: "CombatEngine", defender: "Unit", attacker: "Unit", damage: float, damage_type
):
    """Bloodthirster: At 40% HP, gain a 25% max HP shield for 5 seconds."""
    triggered = get_item_data(defender, "Bloodthirster", "triggered", False)
    if not triggered and defender.stats.hp <= defender.stats.max_hp * 0.40:
        set_item_data(defender, "Bloodthirster", "triggered", True)
        shield_amount = defender.stats.max_hp * 0.25
        defender.stats.shield += shield_amount


def protectors_vow_on_damage(
    engine: "CombatEngine", defender: "Unit", attacker: "Unit", damage: float, damage_type
):
    """Protector's Vow: At 40% HP, gain 15 Mana and a 20% max HP shield."""
    triggered = get_item_data(defender, "ProtectorsVow", "shield_triggered", False)
    if not triggered and defender.stats.hp <= defender.stats.max_hp * 0.40:
        set_item_data(defender, "ProtectorsVow", "shield_triggered", True)
        engine.gain_mana(defender, 15, source="protectors_vow")
        shield_amount = defender.stats.max_hp * 0.20
        defender.stats.shield += shield_amount


def steadfast_heart_on_damage(
    engine: "CombatEngine", defender: "Unit", attacker: "Unit", damage: float, damage_type
):
    """Steadfast Heart: 18% Durability above 50% HP, 10% below. Switches both ways."""
    above50 = get_item_data(defender, "SteadfastHeart", "above50", True)
    hp_pct = defender.stats.hp / defender.stats.max_hp if defender.stats.max_hp > 0 else 1.0
    if above50 and hp_pct < 0.50:
        set_item_data(defender, "SteadfastHeart", "above50", False)
        defender.stats.damage_reduction -= 0.08  # 18% → 10%
    elif not above50 and hp_pct >= 0.50:
        set_item_data(defender, "SteadfastHeart", "above50", True)
        defender.stats.damage_reduction += 0.08  # 10% → 18%


# =============================================================================
# PASSIVE EFFECTS (called every tick, must self-throttle)
# =============================================================================


def guinsoos_passive(engine: "CombatEngine", unit: "Unit"):
    """Guinsoo's Rageblade: Gain 7% stacking Attack Speed every second (max 20 stacks)."""
    last = get_item_data(unit, "Guinsoos", "last_tick", -1.0)
    if engine.time - last < 1.0:
        return
    set_item_data(unit, "Guinsoos", "last_tick", engine.time)
    stacks = get_item_data(unit, "Guinsoos", "stacks", 0)
    if stacks < 20:
        unit.stats.attack_speed += 0.07
        set_item_data(unit, "Guinsoos", "stacks", stacks + 1)


def archangels_passive(engine: "CombatEngine", unit: "Unit"):
    """Archangel's Staff: Gain 20% AP every 5 seconds."""
    last = get_item_data(unit, "Archangels", "last_tick", -5.0)
    if engine.time - last < 5.0:
        return
    set_item_data(unit, "Archangels", "last_tick", engine.time)
    ap_gain = unit.base_stats.ap * 0.20 if unit.base_stats.ap > 0 else unit.stats.ap * 0.20
    unit.stats.ap += ap_gain


def quicksilver_passive(engine: "CombatEngine", unit: "Unit"):
    """Quicksilver: Gain 3% stacking Attack Speed every second."""
    last = get_item_data(unit, "Quicksilver", "last_as_tick", -1.0)
    if engine.time - last < 1.0:
        return
    set_item_data(unit, "Quicksilver", "last_as_tick", engine.time)
    unit.stats.attack_speed += 0.03


def dragons_claw_passive(engine: "CombatEngine", unit: "Unit"):
    """Dragon's Claw: Every 2 seconds, heal 2.5% max HP."""
    last = get_item_data(unit, "DragonsClaw", "last_tick", -2.0)
    if engine.time - last < 2.0:
        return
    set_item_data(unit, "DragonsClaw", "last_tick", engine.time)
    engine.heal_unit(unit, unit.stats.max_hp * 0.025, "dragons_claw")


def spirit_visage_passive(engine: "CombatEngine", unit: "Unit"):
    """Spirit Visage: Restore 2.5% of missing HP each second."""
    last = get_item_data(unit, "SpiritVisage", "last_tick", -1.0)
    if engine.time - last < 1.0:
        return
    set_item_data(unit, "SpiritVisage", "last_tick", engine.time)
    missing = unit.stats.max_hp - unit.stats.hp
    engine.heal_unit(unit, missing * 0.025, "spirit_visage")


def sunfire_cape_passive(engine: "CombatEngine", unit: "Unit"):
    """Sunfire Cape: Every 2s, deal 1% Burn and 33% Wound to an enemy within 2 hexes for 10s."""
    from .combat_engine import HexGrid

    last = get_item_data(unit, "SunfireCape", "last_tick", -2.0)
    if engine.time - last < 2.0:
        return
    set_item_data(unit, "SunfireCape", "last_tick", engine.time)

    enemies = [
        u
        for u in engine.units
        if u.team != unit.team
        and u.is_alive
        and HexGrid.hex_distance(unit.position, u.position) <= 2
    ]
    if enemies:
        target = enemies[0]  # Closest
        engine.apply_burn(unit, target, 0.01, 10.0, "sunfire_cape")
        engine.apply_wound(target, 10.0, "sunfire_cape")


def ionic_spark_passive(engine: "CombatEngine", unit: "Unit"):
    """Ionic Spark: 30% Shred enemies within 2 hexes.
    When enemies cast, deal 150% of mana spent as magic damage.
    (Simplified: apply shred aura every 1s)
    """
    from .combat_engine import HexGrid

    last = get_item_data(unit, "IonicSpark", "last_tick", -1.0)
    if engine.time - last < 1.0:
        return
    set_item_data(unit, "IonicSpark", "last_tick", engine.time)

    enemies = [
        u
        for u in engine.units
        if u.team != unit.team
        and u.is_alive
        and HexGrid.hex_distance(unit.position, u.position) <= 2
    ]
    for enemy in enemies:
        engine.apply_shred(enemy, 0.30, 5.0, "ionic_spark")


def evenshroud_passive(engine: "CombatEngine", unit: "Unit"):
    """Evenshroud: 30% Sunder enemies within 2 hexes. +25 Armor/MR expires at 15s."""
    from .combat_engine import HexGrid

    # Expire the +25 Armor/MR bonus after 15 seconds
    bonus_expired = get_item_data(unit, "Evenshroud", "bonus_expired", False)
    if not bonus_expired:
        bonus_start = get_item_data(unit, "Evenshroud", "bonus_start", 0)
        if engine.time - bonus_start >= 15.0:
            set_item_data(unit, "Evenshroud", "bonus_expired", True)
            unit.stats.armor -= 25
            unit.stats.magic_resist -= 25

    last = get_item_data(unit, "Evenshroud", "last_tick", -1.0)
    if engine.time - last < 1.0:
        return
    set_item_data(unit, "Evenshroud", "last_tick", engine.time)

    enemies = [
        u
        for u in engine.units
        if u.team != unit.team
        and u.is_alive
        and HexGrid.hex_distance(unit.position, u.position) <= 2
    ]
    for enemy in enemies:
        engine.apply_sunder(enemy, 0.30, 5.0, "evenshroud")


# =============================================================================
# COMBAT-START EFFECTS
# =============================================================================


def crownguard_combat_start(engine: "CombatEngine", unit: "Unit", all_units: list):
    """Crownguard: Combat Start: 25% max HP shield for 8s. When expires, gain 25% AP.

    Simplified: grant shield immediately, grant AP after 8s handled by passive.
    """
    shield_amount = unit.stats.max_hp * 0.25
    engine.apply_shield(unit, shield_amount, "crownguard")
    set_item_data(unit, "Crownguard", "shield_start", engine.time)
    set_item_data(unit, "Crownguard", "ap_granted", False)


def crownguard_passive(engine: "CombatEngine", unit: "Unit"):
    """Crownguard: Shield expires after 8s, then gain 25% AP (one-time)."""
    granted = get_item_data(unit, "Crownguard", "ap_granted", False)
    if granted:
        return
    start = get_item_data(unit, "Crownguard", "shield_start", 0)
    if engine.time - start >= 8.0:
        set_item_data(unit, "Crownguard", "ap_granted", True)
        # Expire remaining Crownguard shield
        unit.stats.shield = max(0, unit.stats.shield)  # Don't increase, just ensure non-negative
        # Grant AP bonus
        ap_bonus = unit.base_stats.ap * 0.25 if unit.base_stats.ap > 0 else 25
        unit.stats.ap += ap_bonus


def blue_buff_combat_start(engine: "CombatEngine", unit: "Unit", all_units: list):
    """Blue Buff: Gain 10% additional AD and AP from all sources. Reduce max mana by 10."""
    ad_bonus = unit.stats.ad * 0.10
    ap_bonus = unit.stats.ap * 0.10
    unit.stats.ad += ad_bonus
    unit.stats.ap += ap_bonus
    # Reduce max mana by 10 (minimum 10)
    unit.stats.max_mana = max(10, unit.stats.max_mana - 10)


def quicksilver_combat_start(engine: "CombatEngine", unit: "Unit", all_units: list):
    """Quicksilver: CC immunity for 18 seconds."""
    set_item_data(unit, "Quicksilver", "immune_until", engine.time + 18.0)


def steadfast_heart_combat_start(engine: "CombatEngine", unit: "Unit", all_units: list):
    """Steadfast Heart: 18% Durability (above 50% HP), 10% below.
    Start with 18% since units begin at full HP.
    """
    unit.stats.damage_reduction += 0.18
    set_item_data(unit, "SteadfastHeart", "above50", True)


def evenshroud_combat_start(engine: "CombatEngine", unit: "Unit", all_units: list):
    """Evenshroud: Gain 25 Armor and MR for the first 15 seconds."""
    unit.stats.armor += 25
    unit.stats.magic_resist += 25
    set_item_data(unit, "Evenshroud", "bonus_start", engine.time)


def hand_of_justice_combat_start(engine: "CombatEngine", unit: "Unit", all_units: list):
    """Hand of Justice: Above 50%: +15% AD/AP. Below 50%: +12% omnivamp.
    Both double while active. Start above 50%, so grant AD/AP.
    """
    # Start with damage mode (above 50%)
    ad_bonus = unit.stats.ad * 0.15
    ap_bonus = unit.stats.ap * 0.15
    unit.stats.ad += ad_bonus
    unit.stats.ap += ap_bonus
    set_item_data(unit, "HandOfJustice", "mode", "damage")
    set_item_data(unit, "HandOfJustice", "ad_bonus", ad_bonus)
    set_item_data(unit, "HandOfJustice", "ap_bonus", ap_bonus)


def hand_of_justice_passive(engine: "CombatEngine", unit: "Unit"):
    """Hand of Justice: Switch between damage mode (above 50% HP) and omnivamp mode (below 50%)."""
    hp_pct = unit.stats.hp / unit.stats.max_hp if unit.stats.max_hp > 0 else 1.0
    current_mode = get_item_data(unit, "HandOfJustice", "mode", "damage")

    if hp_pct >= 0.5 and current_mode != "damage":
        # Switch to damage mode: remove omnivamp, add AD/AP
        unit.stats.omnivamp -= 0.12
        ad_bonus = get_item_data(unit, "HandOfJustice", "ad_bonus", 0)
        ap_bonus = get_item_data(unit, "HandOfJustice", "ap_bonus", 0)
        unit.stats.ad += ad_bonus
        unit.stats.ap += ap_bonus
        set_item_data(unit, "HandOfJustice", "mode", "damage")
    elif hp_pct < 0.5 and current_mode != "omnivamp":
        # Switch to omnivamp mode: remove AD/AP, add omnivamp
        ad_bonus = get_item_data(unit, "HandOfJustice", "ad_bonus", 0)
        ap_bonus = get_item_data(unit, "HandOfJustice", "ap_bonus", 0)
        unit.stats.ad -= ad_bonus
        unit.stats.ap -= ap_bonus
        unit.stats.omnivamp += 0.12
        set_item_data(unit, "HandOfJustice", "mode", "omnivamp")


def adaptive_helm_combat_start(engine: "CombatEngine", unit: "Unit", all_units: list):
    """Adaptive Helm: +15% Mana from all sources.
    Tanks/Fighters: +45 Armor/MR. Others: +10% AD/AP.
    """
    role = getattr(unit, "role", "")
    if role in ("APTank", "ADTank", "Tank", "ADFighter", "Defender"):
        unit.stats.armor += 45
        unit.stats.magic_resist += 45
    else:
        unit.stats.ad += unit.stats.ad * 0.10
        unit.stats.ap += unit.stats.ap * 0.10


def protectors_vow_combat_start(engine: "CombatEngine", unit: "Unit", all_units: list):
    """Protector's Vow: Combat Start: gain 20 Mana."""
    engine.gain_mana(unit, 20, source="protectors_vow_start")


# =============================================================================
# BILGEWATER ITEM EFFECTS
# =============================================================================


def captains_brew_on_hit(engine: "CombatEngine", attacker: "Unit", target: "Unit"):
    """Captain's Brew: Attacks Burn and Chill enemies for 2 seconds."""
    engine.apply_burn(attacker, target, 0.01, 2.0, "captains_brew")
    # Chill: reduce attack speed by 25% for 2s
    if not hasattr(target, "_chill_until") or engine.time > target._chill_until:
        target.stats.attack_speed *= 0.75
        target._chill_until = engine.time + 2.0
        target._chill_as_reduction = target.stats.attack_speed * 0.25 / 0.75


def captains_brew_passive(engine: "CombatEngine", unit: "Unit"):
    """Captain's Brew: Expire chill effect on targets."""
    # Chill expiry handled on target side — check all enemies
    for enemy in engine.units:
        if enemy.team == unit.team or not enemy.is_alive:
            continue
        if hasattr(enemy, "_chill_until") and engine.time >= enemy._chill_until:
            if hasattr(enemy, "_chill_as_reduction"):
                enemy.stats.attack_speed /= 0.75
                del enemy._chill_as_reduction
                enemy._chill_until = float("inf")


def freebooters_frock_passive(engine: "CombatEngine", unit: "Unit"):
    """Barknuckles: Above 50% HP double Armor/MR. Every 4s deal 50% resists magic damage to 2 nearest."""
    from .combat_engine import DamageType, HexGrid

    # Double resists while above 50% HP
    above50 = get_item_data(unit, "Barknuckles", "above50", True)
    hp_pct = unit.stats.hp / unit.stats.max_hp if unit.stats.max_hp > 0 else 1.0
    if above50 and hp_pct < 0.50:
        set_item_data(unit, "Barknuckles", "above50", False)
        unit.stats.armor -= get_item_data(unit, "Barknuckles", "bonus_armor", 0)
        unit.stats.magic_resist -= get_item_data(unit, "Barknuckles", "bonus_mr", 0)
    elif not above50 and hp_pct >= 0.50:
        set_item_data(unit, "Barknuckles", "above50", True)
        bonus_armor = unit.stats.armor  # Double = add current
        bonus_mr = unit.stats.magic_resist
        unit.stats.armor += bonus_armor
        unit.stats.magic_resist += bonus_mr
        set_item_data(unit, "Barknuckles", "bonus_armor", bonus_armor)
        set_item_data(unit, "Barknuckles", "bonus_mr", bonus_mr)

    # Damage aura every 4s
    last = get_item_data(unit, "Barknuckles", "last_aura", -4.0)
    if engine.time - last < 4.0:
        return
    set_item_data(unit, "Barknuckles", "last_aura", engine.time)
    aura_damage = (unit.stats.armor + unit.stats.magic_resist) * 0.50
    enemies = [u for u in engine.units if u.team != unit.team and u.is_alive]
    enemies.sort(key=lambda e: HexGrid.hex_distance(unit.position, e.position))
    for enemy in enemies[:2]:
        dmg, _ = engine.calculate_damage(unit, enemy, aura_damage, DamageType.MAGIC, can_crit=False)
        engine.apply_damage(unit, enemy, dmg, DamageType.MAGIC, "barknuckles")


def freebooters_frock_combat_start(engine: "CombatEngine", unit: "Unit", all_units: list):
    """Barknuckles: Start with doubled resists if above 50% HP (always true at start)."""
    bonus_armor = unit.stats.armor
    bonus_mr = unit.stats.magic_resist
    unit.stats.armor += bonus_armor
    unit.stats.magic_resist += bonus_mr
    set_item_data(unit, "Barknuckles", "bonus_armor", bonus_armor)
    set_item_data(unit, "Barknuckles", "bonus_mr", bonus_mr)
    set_item_data(unit, "Barknuckles", "above50", True)


def blackmarket_explosives_passive(engine: "CombatEngine", unit: "Unit"):
    """Blackmarket Explosives: Every 5s deal 15 + 12% damage dealt as magic damage to target + 2 nearest."""
    from .combat_engine import DamageType, HexGrid

    last = get_item_data(unit, "BlackmarketExplosives", "last_tick", -5.0)
    if engine.time - last < 5.0:
        return
    set_item_data(unit, "BlackmarketExplosives", "last_tick", engine.time)

    tracked_damage = get_item_data(unit, "BlackmarketExplosives", "damage_dealt", 0)
    explosion_damage = 15 + tracked_damage * 0.12
    set_item_data(unit, "BlackmarketExplosives", "damage_dealt", 0)

    if unit.target and unit.target.is_alive:
        enemies = [
            u for u in engine.units if u.team != unit.team and u.is_alive and u != unit.target
        ]
        enemies.sort(key=lambda e: HexGrid.hex_distance(unit.target.position, e.position))
        targets = [unit.target] + enemies[:2]
        for t in targets:
            dmg, _ = engine.calculate_damage(
                unit, t, explosion_damage, DamageType.MAGIC, can_crit=False
            )
            engine.apply_damage(unit, t, dmg, DamageType.MAGIC, "blackmarket_explosives")


def blackmarket_explosives_on_damage(
    engine: "CombatEngine", attacker: "Unit", target: "Unit", damage: float, damage_type
):
    """Blackmarket Explosives: Track damage dealt for explosion calculation."""
    tracked = get_item_data(attacker, "BlackmarketExplosives", "damage_dealt", 0)
    set_item_data(attacker, "BlackmarketExplosives", "damage_dealt", tracked + damage)


def bilgerat_cutlass_on_damage(
    engine: "CombatEngine", attacker: "Unit", target: "Unit", damage: float, damage_type
):
    """Cutthroat's Cutlass: Damaging enemies causes 35% bleed over 4s."""
    from .combat_engine import DamageType as DT
    from .combat_engine import DotEffect

    bleed_total = damage * 0.35
    # 4 ticks over 4 seconds
    dot = DotEffect(
        source_unit=attacker,
        damage_per_tick=bleed_total / 4.0,
        tick_interval=1.0,
        remaining_duration=4.0,
        damage_type=DT.PHYSICAL,
        source_name="cutthroat_bleed",
    )
    target.dot_effects.append(dot)


def deadmans_dagger_on_damage(
    engine: "CombatEngine", attacker: "Unit", target: "Unit", damage: float, damage_type
):
    """Dead Man's Dagger: Execute below 12% HP."""
    if target.is_alive and target.stats.hp > 0:
        hp_pct = target.stats.hp / target.stats.max_hp
        if hp_pct < 0.12:
            engine.apply_damage(
                attacker, target, target.stats.hp + 1, damage_type, "deadmans_execute"
            )
            # On kill bonus (stacking)
            kills = get_item_data(attacker, "DeadmansDagger", "kills", 0)
            kills += 1
            set_item_data(attacker, "DeadmansDagger", "kills", kills)
            attacker.stats.ad += attacker.base_stats.ad * 0.10
            attacker.stats.ap += 15


def first_mates_flintlock_passive(engine: "CombatEngine", unit: "Unit"):
    """First Mate's Flintlock: Every second gain +3% AD and +3% AS."""
    last = get_item_data(unit, "FirstMatesFlintlock", "last_tick", -1.0)
    if engine.time - last < 1.0:
        return
    set_item_data(unit, "FirstMatesFlintlock", "last_tick", engine.time)
    unit.stats.ad += unit.base_stats.ad * 0.03
    unit.stats.attack_speed += 0.03


def pile_o_citrus_passive(engine: "CombatEngine", unit: "Unit"):
    """Pile O' Citrus: Every 15s heal 15% max HP and cleanse CC."""
    last = get_item_data(unit, "PileOCitrus", "last_heal", -15.0)
    if engine.time - last < 15.0:
        return
    set_item_data(unit, "PileOCitrus", "last_heal", engine.time)
    engine.heal_unit(unit, unit.stats.max_hp * 0.15, "pile_o_citrus")
    # Cleanse: remove stun
    from .combat_engine import UnitState

    if unit.state == UnitState.STUNNED:
        unit.state = UnitState.IDLE
        unit.stun_duration = 0


# =============================================================================
# ARTIFACT ITEM EFFECTS
# =============================================================================


def deathfire_grasp_combat_start(engine: "CombatEngine", unit: "Unit", all_units: list):
    """Deathfire Grasp: Deal 20% max HP magic damage to nearest enemy. +25% damage amp 10s."""
    from .combat_engine import DamageType, HexGrid

    enemies = [u for u in all_units if u.team != unit.team and u.is_alive]
    if enemies:
        enemies.sort(key=lambda e: HexGrid.hex_distance(unit.position, e.position))
        target = enemies[0]
        dmg = target.stats.max_hp * 0.20
        final_dmg, _ = engine.calculate_damage(unit, target, dmg, DamageType.MAGIC, can_crit=False)
        engine.apply_damage(unit, target, final_dmg, DamageType.MAGIC, "deathfire_grasp")
        # +35% damage amp vs that target, +25% vs others
        unit.stats.damage_amp += 0.25
        set_item_data(unit, "DeathfireGrasp", "bonus_target", id(target))
        set_item_data(unit, "DeathfireGrasp", "expire_time", engine.time + 10.0)


def deathfire_grasp_passive(engine: "CombatEngine", unit: "Unit"):
    """Deathfire Grasp: Expire the damage amp after 10s."""
    expire = get_item_data(unit, "DeathfireGrasp", "expire_time", float("inf"))
    if engine.time >= expire and not get_item_data(unit, "DeathfireGrasp", "expired", False):
        unit.stats.damage_amp -= 0.25
        set_item_data(unit, "DeathfireGrasp", "expired", True)


def rapid_firecannon_combat_start(engine: "CombatEngine", unit: "Unit", all_units: list):
    """Rapid Firecannon: +1 attack range, +1 more per kill."""
    unit.stats.range += 1
    unit._rfc_kills = 0


def gold_collector_on_damage(
    engine: "CombatEngine", attacker: "Unit", target: "Unit", damage: float, damage_type
):
    """Gold Collector: Execute targets below 12% HP."""
    if target.is_alive and target.stats.hp > 0:
        hp_pct = target.stats.hp / target.stats.max_hp
        if hp_pct < 0.12:
            engine.apply_damage(
                attacker, target, target.stats.hp + 1, damage_type, "gold_collector_exec"
            )


def snipers_focus_combat_start(engine: "CombatEngine", unit: "Unit", all_units: list):
    """Sniper's Focus: +2 attack range. +9% damage amp per hex distance."""
    unit.stats.range += 2
    unit._snipers_focus = True


def snipers_focus_on_damage(
    engine: "CombatEngine", attacker: "Unit", target: "Unit", damage: float, damage_type
):
    """Sniper's Focus: Bonus damage based on hex distance (handled via damage_amp at attack time)."""
    pass  # Damage amp is applied dynamically in the passive


def snipers_focus_passive(engine: "CombatEngine", unit: "Unit"):
    """Sniper's Focus: Recalculate damage amp based on distance to target."""
    from .combat_engine import HexGrid

    old_bonus = get_item_data(unit, "SnipersFocus", "dist_bonus", 0)
    unit.stats.damage_amp -= old_bonus
    if unit.target and unit.target.is_alive:
        dist = HexGrid.hex_distance(unit.position, unit.target.position)
        new_bonus = 0.09 * dist
    else:
        new_bonus = 0
    unit.stats.damage_amp += new_bonus
    set_item_data(unit, "SnipersFocus", "dist_bonus", new_bonus)


def hullcrusher_combat_start(engine: "CombatEngine", unit: "Unit", all_units: list):
    """Hullcrusher: If no adjacent allies, gain +400 HP, +10% AD, +10% AP."""
    from .combat_engine import HexGrid

    allies_adj = [
        u
        for u in all_units
        if u.team == unit.team
        and u != unit
        and u.is_alive
        and HexGrid.hex_distance(unit.position, u.position) <= 1
    ]
    if not allies_adj:
        unit.stats.hp += 400
        unit.stats.max_hp += 400
        unit.stats.ad += unit.stats.ad * 0.10
        unit.stats.ap += unit.stats.ap * 0.10


def infinity_force_combat_start(engine: "CombatEngine", unit: "Unit", all_units: list):
    """Infinity Force: +30% AD, +30 AP, +30 Armor, +30 MR, +30% AS."""
    unit.stats.ad += unit.stats.ad * 0.30
    unit.stats.ap += 30
    unit.stats.armor += 30
    unit.stats.magic_resist += 30
    unit.stats.attack_speed += 0.30


def manazane_passive(engine: "CombatEngine", unit: "Unit"):
    """Manazane: After first cast, restore +120 mana over 5s (24 mana/s)."""
    if not get_item_data(unit, "Manazane", "activated", False):
        if unit.abilities_cast >= 1:
            set_item_data(unit, "Manazane", "activated", True)
            set_item_data(unit, "Manazane", "start_time", engine.time)
        return
    start = get_item_data(unit, "Manazane", "start_time", 0)
    elapsed = engine.time - start
    if elapsed > 5.0:
        return
    last = get_item_data(unit, "Manazane", "last_tick", start - 1.0)
    if engine.time - last >= 1.0:
        set_item_data(unit, "Manazane", "last_tick", engine.time)
        engine.gain_mana(unit, 24, source="manazane")


def moguls_mail_on_damage_taken(
    engine: "CombatEngine", defender: "Unit", attacker: "Unit", damage: float, damage_type
):
    """Mogul's Mail: +1 Armor, +1 MR, +5 HP per hit taken (max 35 stacks)."""
    stacks = get_item_data(defender, "MogulsMail", "stacks", 0)
    if stacks < 35:
        stacks += 1
        set_item_data(defender, "MogulsMail", "stacks", stacks)
        defender.stats.armor += 1
        defender.stats.magic_resist += 1
        defender.stats.hp += 5
        defender.stats.max_hp += 5


def seekers_armguard_on_damage(
    engine: "CombatEngine", attacker: "Unit", target: "Unit", damage: float, damage_type
):
    """Seeker's Armguard: On takedown gain +20 Armor, +20 MR, +20 AP."""
    if target.is_alive:
        return
    attacker.stats.armor += 20
    attacker.stats.magic_resist += 20
    attacker.stats.ap += 20


def zhonyas_paradox_on_damage_taken(
    engine: "CombatEngine", defender: "Unit", attacker: "Unit", damage: float, damage_type
):
    """Zhonya's Paradox: At 40% HP become invulnerable for 3s (once)."""
    triggered = get_item_data(defender, "ZhonyasParadox", "triggered", False)
    if not triggered and defender.stats.hp <= defender.stats.max_hp * 0.40:
        set_item_data(defender, "ZhonyasParadox", "triggered", True)
        defender.is_targetable = False
        defender.untargetable_duration = 3.0
        set_item_data(defender, "ZhonyasParadox", "expire", engine.time + 3.0)


def zhonyas_paradox_passive(engine: "CombatEngine", unit: "Unit"):
    """Zhonya's Paradox: Re-enable targeting when invuln expires."""
    expire = get_item_data(unit, "ZhonyasParadox", "expire", float("inf"))
    if engine.time >= expire and not unit.is_targetable:
        unit.is_targetable = True


def silvermere_dawn_on_hit(engine: "CombatEngine", attacker: "Unit", target: "Unit"):
    """Silvermere Dawn: Attacks stun for 0.8s. AS locked at 0.5."""
    from .combat_engine import UnitState

    if target.is_alive and target.state != UnitState.STUNNED:
        target.state = UnitState.STUNNED
        target.stun_duration = 0.8


def silvermere_dawn_combat_start(engine: "CombatEngine", unit: "Unit", all_units: list):
    """Silvermere Dawn: Stun immune, AS locked at 0.5."""
    unit.stats.attack_speed = 0.5
    unit.immune_until = float("inf")  # Permanent stun immunity


def talisman_passive(engine: "CombatEngine", unit: "Unit"):
    """Talisman of Ascension: After 22s gain +100% max HP and +120% damage amp."""
    if engine.time >= 22.0 and not get_item_data(unit, "Talisman", "activated", False):
        set_item_data(unit, "Talisman", "activated", True)
        hp_bonus = unit.stats.max_hp
        unit.stats.hp += hp_bonus
        unit.stats.max_hp += hp_bonus
        unit.stats.damage_amp += 1.20


def titanic_hydra_on_hit(engine: "CombatEngine", attacker: "Unit", target: "Unit"):
    """Titanic Hydra: 3% max HP + 8% AD as bonus phys damage to target + adjacent enemies."""
    from .combat_engine import DamageType, HexGrid

    bonus = attacker.stats.max_hp * 0.03 + attacker.stats.ad * 0.08
    # Also hit adjacent enemies
    enemies = [
        u
        for u in engine.units
        if u.team != attacker.team
        and u.is_alive
        and HexGrid.hex_distance(target.position, u.position) <= 1
    ]
    for enemy in enemies:
        dmg, _ = engine.calculate_damage(
            attacker, enemy, bonus, DamageType.PHYSICAL, can_crit=False
        )
        engine.apply_damage(attacker, enemy, dmg, DamageType.PHYSICAL, "titanic_hydra")


def dawncore_combat_start(engine: "CombatEngine", unit: "Unit", all_units: list):
    """Dawncore: Reduce max mana by 10. Subsequent casts reduce by 10% (min 10)."""
    unit.stats.max_mana = max(10, unit.stats.max_mana - 10)
    unit._dawncore = True


def dawncore_on_ability(engine: "CombatEngine", caster: "Unit"):
    """Dawncore: After each cast, reduce max mana by 10% (min 10)."""
    if getattr(caster, "_dawncore", False):
        caster.stats.max_mana = max(10, caster.stats.max_mana * 0.90)


def flickerblade_passive(engine: "CombatEngine", unit: "Unit"):
    """Flickerblade: +6% stacking AS per second, every 5 attacks +2% AD/AP."""
    last = get_item_data(unit, "Flickerblade", "last_tick", -1.0)
    if engine.time - last >= 1.0:
        set_item_data(unit, "Flickerblade", "last_tick", engine.time)
        unit.stats.attack_speed += 0.06


def flickerblade_on_hit(engine: "CombatEngine", attacker: "Unit", target: "Unit"):
    """Flickerblade: Every 5 attacks gain +2% AD and AP."""
    count = get_item_data(attacker, "Flickerblade", "attacks", 0) + 1
    set_item_data(attacker, "Flickerblade", "attacks", count)
    if count >= 5:
        set_item_data(attacker, "Flickerblade", "attacks", 0)
        attacker.stats.ad += attacker.base_stats.ad * 0.02
        attacker.stats.ap += 2


def prowlers_claw_on_damage(
    engine: "CombatEngine", attacker: "Unit", target: "Unit", damage: float, damage_type
):
    """Prowler's Claw: On kill, cleanse + next 2 crits deal +50% crit damage."""
    if target.is_alive:
        return
    # Cleanse
    from .combat_engine import UnitState

    if attacker.state == UnitState.STUNNED:
        attacker.state = UnitState.IDLE
        attacker.stun_duration = 0
    # Empower next 2 crits
    attacker._prowlers_empowered = 2
    attacker.stats.crit_multiplier += 0.50


def hellfire_hatchet_on_hit(engine: "CombatEngine", attacker: "Unit", target: "Unit"):
    """Hellfire Hatchet: 2% max HP bonus physical damage on attacks."""
    from .combat_engine import DamageType

    bonus = attacker.stats.max_hp * 0.02
    dmg, _ = engine.calculate_damage(attacker, target, bonus, DamageType.PHYSICAL, can_crit=False)
    engine.apply_damage(attacker, target, dmg, DamageType.PHYSICAL, "hellfire_hatchet")


def hellfire_hatchet_passive(engine: "CombatEngine", unit: "Unit"):
    """Hellfire Hatchet: +1% AS per 1% missing HP."""
    last = get_item_data(unit, "HellfireHatchet", "last_tick", -1.0)
    if engine.time - last < 1.0:
        return
    set_item_data(unit, "HellfireHatchet", "last_tick", engine.time)
    old_bonus = get_item_data(unit, "HellfireHatchet", "as_bonus", 0)
    unit.stats.attack_speed -= old_bonus
    missing_pct = 1.0 - (unit.stats.hp / unit.stats.max_hp) if unit.stats.max_hp > 0 else 0
    new_bonus = missing_pct  # 1% AS per 1% missing HP = missing_pct as decimal
    unit.stats.attack_speed += new_bonus
    set_item_data(unit, "HellfireHatchet", "as_bonus", new_bonus)


def darkin_aegis_passive(engine: "CombatEngine", unit: "Unit"):
    """The Darkin Aegis: 1% max HP/s aura damage, 2% heal on nearby deaths."""
    from .combat_engine import DamageType, HexGrid

    last = get_item_data(unit, "DarkinAegis", "last_tick", -1.0)
    if engine.time - last < 1.0:
        return
    set_item_data(unit, "DarkinAegis", "last_tick", engine.time)
    aura_damage = unit.stats.max_hp * 0.01
    enemies = [
        u
        for u in engine.units
        if u.team != unit.team
        and u.is_alive
        and HexGrid.hex_distance(unit.position, u.position) <= 2
    ]
    for enemy in enemies:
        engine.apply_damage(unit, enemy, aura_damage, DamageType.MAGIC, "darkin_aegis")


def darkin_bow_on_hit(engine: "CombatEngine", attacker: "Unit", target: "Unit"):
    """The Darkin Bow: Every 10 attacks fire 500% AD arrow."""
    from .combat_engine import DamageType

    count = get_item_data(attacker, "DarkinBow", "attacks", 0) + 1
    set_item_data(attacker, "DarkinBow", "attacks", count)
    if count >= 10:
        set_item_data(attacker, "DarkinBow", "attacks", 0)
        bonus = attacker.stats.ad * 5.0
        dmg, _ = engine.calculate_damage(
            attacker, target, bonus, DamageType.PHYSICAL, can_crit=True
        )
        engine.apply_damage(attacker, target, dmg, DamageType.PHYSICAL, "darkin_bow_arrow")


def darkin_scythe_passive(engine: "CombatEngine", unit: "Unit"):
    """The Darkin Scythe: Every 4s deal 200% AD slash to adjacent enemies."""
    from .combat_engine import DamageType, HexGrid

    last = get_item_data(unit, "DarkinScythe", "last_tick", -4.0)
    if engine.time - last < 4.0:
        return
    set_item_data(unit, "DarkinScythe", "last_tick", engine.time)
    slash_dmg = unit.stats.ad * 2.0
    enemies = [
        u
        for u in engine.units
        if u.team != unit.team
        and u.is_alive
        and HexGrid.hex_distance(unit.position, u.position) <= 1
    ]
    for enemy in enemies:
        dmg, _ = engine.calculate_damage(
            unit, enemy, slash_dmg, DamageType.PHYSICAL, can_crit=False
        )
        engine.apply_damage(unit, enemy, dmg, DamageType.PHYSICAL, "darkin_scythe")


def darkin_staff_passive(engine: "CombatEngine", unit: "Unit"):
    """The Darkin Staff: Per 20 mana spent, fire tendril dealing 50 magic damage."""
    from .combat_engine import DamageType

    # Track mana spent (mana resets to 0 on cast, so abilities_cast * max_mana = total spent)
    total_spent = unit.abilities_cast * unit.stats.max_mana
    last_spent = get_item_data(unit, "DarkinStaff", "last_spent", 0)
    tendrils = int((total_spent - last_spent) / 20)
    if tendrils > 0:
        set_item_data(unit, "DarkinStaff", "last_spent", last_spent + tendrils * 20)
        enemies = [u for u in engine.units if u.team != unit.team and u.is_alive]
        if enemies:
            import random as _rand

            for _ in range(tendrils):
                target = _rand.choice(enemies)
                dmg, _ = engine.calculate_damage(unit, target, 50, DamageType.MAGIC, can_crit=False)
                engine.apply_damage(unit, target, dmg, DamageType.MAGIC, "darkin_staff_tendril")


def lightshield_crest_passive(engine: "CombatEngine", unit: "Unit"):
    """Lightshield Crest: Every 3s shield lowest HP ally for 70% combined resists."""
    last = get_item_data(unit, "LightshieldCrest", "last_tick", -3.0)
    if engine.time - last < 3.0:
        return
    set_item_data(unit, "LightshieldCrest", "last_tick", engine.time)
    shield_amount = (unit.stats.armor + unit.stats.magic_resist) * 0.70
    allies = [u for u in engine.units if u.team == unit.team and u.is_alive]
    if allies:
        lowest = min(allies, key=lambda u: u.stats.hp / u.stats.max_hp)
        engine.apply_shield(lowest, shield_amount, "lightshield_crest")


def ludens_tempest_on_damage(
    engine: "CombatEngine", attacker: "Unit", target: "Unit", damage: float, damage_type
):
    """Luden's Tempest: 100% overkill + 100 as magic damage to 3 nearest enemies on kill."""
    from .combat_engine import DamageType, HexGrid

    if target.is_alive:
        return
    overkill = abs(target.stats.hp)  # HP goes negative
    splash = overkill + 100
    enemies = [u for u in engine.units if u.team != attacker.team and u.is_alive and u != target]
    enemies.sort(key=lambda e: HexGrid.hex_distance(target.position, e.position))
    for enemy in enemies[:3]:
        dmg, _ = engine.calculate_damage(attacker, enemy, splash, DamageType.MAGIC, can_crit=False)
        engine.apply_damage(attacker, enemy, dmg, DamageType.MAGIC, "ludens_tempest")


def deaths_defiance_on_damage_taken(
    engine: "CombatEngine", defender: "Unit", attacker: "Unit", damage: float, damage_type
):
    """Death's Defiance: 50% of damage taken is dealt over 4s instead (non-lethal)."""
    from .combat_engine import DamageType as DT
    from .combat_engine import DotEffect

    # Heal back 50% of the damage (it was already applied)
    deferred = damage * 0.50
    defender.stats.hp = min(defender.stats.max_hp, defender.stats.hp + deferred)
    # Apply as DOT over 4s (non-lethal: DOT won't kill)
    dot = DotEffect(
        source_unit=attacker,
        damage_per_tick=deferred / 4.0,
        tick_interval=1.0,
        remaining_duration=4.0,
        damage_type=DT.TRUE,
        source_name="deaths_defiance_bleed",
    )
    defender.dot_effects.append(dot)


def gamblers_blade_passive(engine: "CombatEngine", unit: "Unit"):
    """Gambler's Blade: +1% AS per gold (up to 30%)."""
    gold = getattr(unit, "_player_gold", 0)
    old_bonus = get_item_data(unit, "GamblersBlade", "as_bonus", 0)
    unit.stats.attack_speed -= old_bonus
    new_bonus = min(0.30, gold * 0.01)
    unit.stats.attack_speed += new_bonus
    set_item_data(unit, "GamblersBlade", "as_bonus", new_bonus)


def blighting_jewel_on_damage(
    engine: "CombatEngine", attacker: "Unit", target: "Unit", damage: float, damage_type
):
    """Blighting Jewel: Magic damage reduces target MR by 2. If MR=0, grant 2 mana."""
    from .combat_engine import DamageType as DT

    if damage_type == DT.MAGIC:
        if target.stats.magic_resist > 0:
            target.stats.magic_resist = max(0, target.stats.magic_resist - 2)
        else:
            engine.gain_mana(attacker, 2, source="blighting_jewel")


# =============================================================================
# ITEM EFFECT REGISTRIES
# =============================================================================

ITEM_ON_HIT = {
    # Base craftable
    "SpearOfShojin": spear_of_shojin_on_hit,
    "GiantSlayer": giant_slayer_on_hit,
    "LastWhisper": last_whisper_on_hit,
    "TitansResolve": titans_resolve_on_hit,
    "NashorsTooth": nashors_tooth_on_hit,
    "KrakensFury": krakens_fury_on_hit,
    "RedBuff": red_buff_on_hit,
    "VoidStaff": void_staff_on_hit,
    "StrikersFlail": strikers_flail_on_hit,
    # Artifacts
    "Artifact_WitsEnd": wits_end_on_hit,
    "Artifact_StatikkShiv": statikk_shiv_on_hit,
    "Artifact_LichBane": lich_bane_on_hit,
    "Artifact_SilvermereDawn": silvermere_dawn_on_hit,
    "Artifact_TitanicHydra": titanic_hydra_on_hit,
    "Artifact_Flickerblade": flickerblade_on_hit,
    "Artifact_HellfireHatchet": hellfire_hatchet_on_hit,
    "Artifact_TheDarkinBow": darkin_bow_on_hit,
    # Bilgewater
    "Bilgewater_CaptainsBrew": captains_brew_on_hit,
}

ITEM_ON_ABILITY = {
    "VoidStaff": void_staff_on_ability,
    "Artifact_LichBane": lich_bane_on_ability,
    "Artifact_Dawncore": dawncore_on_ability,
}

ITEM_ON_DAMAGE_DEALT = {
    # Base craftable
    "HextechGunblade": hextech_gunblade_on_damage,
    "Morellonomicon": morellonomicon_on_damage,
    "RedBuff": morellonomicon_on_damage,
    # Artifacts
    "Artifact_GoldCollector": gold_collector_on_damage,
    "Artifact_SeekersArmguard": seekers_armguard_on_damage,
    "Artifact_ProwlersClaw": prowlers_claw_on_damage,
    "Artifact_LudensTempest": ludens_tempest_on_damage,
    "Artifact_BlightingJewel": blighting_jewel_on_damage,
    # Bilgewater
    "Bilgewater_BlackmarketExplosives": blackmarket_explosives_on_damage,
    "Bilgewater_BilgeratCutlass": bilgerat_cutlass_on_damage,
    "Bilgewater_DeadmansDagger": deadmans_dagger_on_damage,
}

ITEM_ON_DAMAGE_TAKEN = {
    # Base craftable
    "SteraksGage": steraks_gage_on_damage,
    "BrambleVest": bramble_vest_on_damage,
    "GargoyleStoneplate": gargoyle_on_damage,
    "Bloodthirster": bloodthirster_on_damage,
    "ProtectorsVow": protectors_vow_on_damage,
    "SteadfastHeart": steadfast_heart_on_damage,
    "TitansResolve": titans_resolve_on_damage_taken,
    # Artifacts
    "Artifact_ZhonyasParadox": zhonyas_paradox_on_damage_taken,
    "Artifact_MogulsMail": moguls_mail_on_damage_taken,
    "Artifact_DeathsDefiance": deaths_defiance_on_damage_taken,
}

ITEM_PASSIVE = {
    # Base craftable
    "GuinsoosRageblade": guinsoos_passive,
    "ArchangelsStaff": archangels_passive,
    "Quicksilver": quicksilver_passive,
    "DragonsClaw": dragons_claw_passive,
    "SpiritVisage": spirit_visage_passive,
    "SunfireCape": sunfire_cape_passive,
    "IonicSpark": ionic_spark_passive,
    "Evenshroud": evenshroud_passive,
    "Crownguard": crownguard_passive,
    "HandOfJustice": hand_of_justice_passive,
    # Artifacts
    "Artifact_DeathfireGrasp": deathfire_grasp_passive,
    "Artifact_ZhonyasParadox": zhonyas_paradox_passive,
    "Artifact_TalismanOfAscension": talisman_passive,
    "Artifact_Flickerblade": flickerblade_passive,
    "Artifact_HellfireHatchet": hellfire_hatchet_passive,
    "Artifact_GamblersBlade": gamblers_blade_passive,
    "Artifact_Manazane": manazane_passive,
    "Artifact_SnipersFocus": snipers_focus_passive,
    "Artifact_TheDarkinAegis": darkin_aegis_passive,
    "Artifact_TheDarkinScythe": darkin_scythe_passive,
    "Artifact_TheDarkinStaff": darkin_staff_passive,
    "Artifact_LightshieldCrest": lightshield_crest_passive,
    # Bilgewater
    "Bilgewater_FreebootersFrock": freebooters_frock_passive,
    "Bilgewater_BlackmarketExplosives": blackmarket_explosives_passive,
    "Bilgewater_FirstMatesFlintlock": first_mates_flintlock_passive,
    "Bilgewater_PileOCitrus": pile_o_citrus_passive,
    "Bilgewater_CaptainsBrew": captains_brew_passive,
}

ITEM_ON_COMBAT_START = {
    # Base craftable
    "Crownguard": crownguard_combat_start,
    "BlueBuff": blue_buff_combat_start,
    "Quicksilver": quicksilver_combat_start,
    "SteadfastHeart": steadfast_heart_combat_start,
    "Evenshroud": evenshroud_combat_start,
    "HandOfJustice": hand_of_justice_combat_start,
    "AdaptiveHelm": adaptive_helm_combat_start,
    "ProtectorsVow": protectors_vow_combat_start,
    # Artifacts
    "Artifact_DeathfireGrasp": deathfire_grasp_combat_start,
    "Artifact_RapidFirecannon": rapid_firecannon_combat_start,
    "Artifact_SilvermereDawn": silvermere_dawn_combat_start,
    "Artifact_Hullcrusher": hullcrusher_combat_start,
    "Artifact_InfinityForce": infinity_force_combat_start,
    "Artifact_Dawncore": dawncore_combat_start,
    "Artifact_SnipersFocus": snipers_focus_combat_start,
    # Bilgewater
    "Bilgewater_FreebootersFrock": freebooters_frock_combat_start,
}


# =============================================================================
# ACCESSOR FUNCTIONS
# =============================================================================


def _resolve_item_name(item_name: str) -> str:
    """Resolve item name, falling back from Radiant to base version."""
    if item_name.startswith("Radiant") and len(item_name) > 7:
        return item_name[7:]  # Strip "Radiant" prefix
    return item_name


def get_item_on_hit(item_name: str):
    """Get on-hit effect function for an item (Radiant inherits base)."""
    return ITEM_ON_HIT.get(item_name) or ITEM_ON_HIT.get(_resolve_item_name(item_name))


def get_item_on_ability(item_name: str):
    """Get on-ability effect function for an item (Radiant inherits base)."""
    return ITEM_ON_ABILITY.get(item_name) or ITEM_ON_ABILITY.get(_resolve_item_name(item_name))


def get_item_on_damage_dealt(item_name: str):
    """Get on-damage-dealt effect function for an item (Radiant inherits base)."""
    return ITEM_ON_DAMAGE_DEALT.get(item_name) or ITEM_ON_DAMAGE_DEALT.get(
        _resolve_item_name(item_name)
    )


def get_item_on_damage_taken(item_name: str):
    """Get on-damage-taken effect function for an item (Radiant inherits base)."""
    return ITEM_ON_DAMAGE_TAKEN.get(item_name) or ITEM_ON_DAMAGE_TAKEN.get(
        _resolve_item_name(item_name)
    )


def get_item_passive(item_name: str):
    """Get passive tick effect function for an item (Radiant inherits base)."""
    return ITEM_PASSIVE.get(item_name) or ITEM_PASSIVE.get(_resolve_item_name(item_name))
