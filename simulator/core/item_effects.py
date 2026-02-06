"""
TFT Set 16 Item Effects

Implements on-hit, on-attack, on-ability, and passive effects for items.
These are called by the combat engine during combat.

Effect function signatures:
- on_hit(engine, attacker, target): Called after each auto attack hits
- on_attack(engine, attacker): Called when starting an attack
- on_damage_dealt(engine, attacker, target, damage, damage_type): Called after dealing damage
- on_damage_taken(engine, defender, attacker, damage, damage_type): Called after taking damage
- on_ability_cast(engine, caster): Called when ability is cast
- passive(engine, unit): Called each tick for passive effects
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .combat_engine import CombatEngine, Unit, DamageType


# =============================================================================
# TRACKING DATA (stored on units during combat)
# =============================================================================

def get_item_data(unit: 'Unit', item_name: str, key: str, default=None):
    """Get item-specific tracking data from a unit."""
    if not hasattr(unit, '_item_data'):
        unit._item_data = {}
    return unit._item_data.get(f"{item_name}_{key}", default)


def set_item_data(unit: 'Unit', item_name: str, key: str, value):
    """Set item-specific tracking data on a unit."""
    if not hasattr(unit, '_item_data'):
        unit._item_data = {}
    unit._item_data[f"{item_name}_{key}"] = value


# =============================================================================
# ON-HIT EFFECTS
# =============================================================================

def giant_slayer_on_hit(engine: 'CombatEngine', attacker: 'Unit', target: 'Unit'):
    """Giant Slayer: Deal 15% bonus damage to targets with more max HP than you."""
    if target.stats.max_hp > attacker.stats.max_hp:
        # Already handled via damage_amp stat, but can add extra vs high HP
        pass  # The 15% damage amp is passive via stats


def last_whisper_on_hit(engine: 'CombatEngine', attacker: 'Unit', target: 'Unit'):
    """Last Whisper: Attacks reduce target's armor by 30% for 5 seconds."""
    # Apply armor shred
    armor_reduction = target.base_stats.armor * 0.30
    current_reduction = get_item_data(target, 'LastWhisper', 'armor_shred', 0)

    if current_reduction == 0:
        # First application
        target.stats.armor = max(0, target.stats.armor - armor_reduction)
        set_item_data(target, 'LastWhisper', 'armor_shred', armor_reduction)


def titans_resolve_on_hit(engine: 'CombatEngine', attacker: 'Unit', target: 'Unit'):
    """Titan's Resolve: Gain 2 AD and 2 armor on attack, stacks up to 25 times."""
    stacks = get_item_data(attacker, 'TitansResolve', 'stacks', 0)

    if stacks < 25:
        stacks += 1
        set_item_data(attacker, 'TitansResolve', 'stacks', stacks)

        # Add stats (AD is flat, not percentage here)
        attacker.stats.ad += 2
        attacker.stats.armor += 2


def guinsoos_on_hit(engine: 'CombatEngine', attacker: 'Unit', target: 'Unit'):
    """Guinsoo's Rageblade: Gain 6% attack speed on attack, stacks infinitely."""
    stacks = get_item_data(attacker, 'GuinsoosRageblade', 'stacks', 0)
    stacks += 1
    set_item_data(attacker, 'GuinsoosRageblade', 'stacks', stacks)

    attacker.stats.attack_speed += 0.06


def statikk_shiv_on_hit(engine: 'CombatEngine', attacker: 'Unit', target: 'Unit'):
    """Statikk Shiv: Every 3rd attack, deal magic damage to 4 enemies."""
    from .combat_engine import DamageType

    attack_count = get_item_data(attacker, 'StatikkShiv', 'attacks', 0) + 1
    set_item_data(attacker, 'StatikkShiv', 'attacks', attack_count)

    if attack_count >= 3:
        set_item_data(attacker, 'StatikkShiv', 'attacks', 0)

        # Deal 50 + 30% AP magic damage to 4 enemies
        base_damage = 50 + (attacker.stats.ap * 0.30)
        enemies = [u for u in engine.units if u.team != attacker.team and u.is_alive]

        # Sort by distance and take closest 4
        from .combat_engine import HexGrid
        enemies.sort(key=lambda e: HexGrid.hex_distance(attacker.position, e.position))

        for enemy in enemies[:4]:
            damage, _ = engine.calculate_damage(attacker, enemy, base_damage,
                                                DamageType.MAGIC, can_crit=False)
            engine.apply_damage(attacker, enemy, damage, DamageType.MAGIC, "statikk_shiv")


def nashors_tooth_on_hit(engine: 'CombatEngine', attacker: 'Unit', target: 'Unit'):
    """Nashor's Tooth: Deal 15 + 20% AP magic damage on hit."""
    from .combat_engine import DamageType

    on_hit_damage = 15 + (attacker.stats.ap * 0.20)
    damage, _ = engine.calculate_damage(attacker, target, on_hit_damage,
                                        DamageType.MAGIC, can_crit=False)
    engine.apply_damage(attacker, target, damage, DamageType.MAGIC, "nashors_tooth")


def krakens_fury_on_hit(engine: 'CombatEngine', attacker: 'Unit', target: 'Unit'):
    """Kraken's Fury (Runaan's): Gain 3 AD on attack, stacks up to 10 times."""
    stacks = get_item_data(attacker, 'KrakensFury', 'stacks', 0)

    if stacks < 10:
        stacks += 1
        set_item_data(attacker, 'KrakensFury', 'stacks', stacks)
        attacker.stats.ad += 3


def madreds_bloodrazor_on_hit(engine: 'CombatEngine', attacker: 'Unit', target: 'Unit'):
    """Madred's Bloodrazor: Deal 3% target max HP as magic damage on hit."""
    from .combat_engine import DamageType

    percent_hp_damage = target.stats.max_hp * 0.03
    damage, _ = engine.calculate_damage(attacker, target, percent_hp_damage,
                                        DamageType.MAGIC, can_crit=False)
    engine.apply_damage(attacker, target, damage, DamageType.MAGIC, "madreds")


def wits_end_on_hit(engine: 'CombatEngine', attacker: 'Unit', target: 'Unit'):
    """Wit's End (Artifact): Deal 42 magic damage on hit and heal for that amount."""
    from .combat_engine import DamageType

    on_hit_damage = 42 + (attacker.stats.ap * 0.20)
    damage, _ = engine.calculate_damage(attacker, target, on_hit_damage,
                                        DamageType.MAGIC, can_crit=False)
    engine.apply_damage(attacker, target, damage, DamageType.MAGIC, "wits_end")

    # Heal
    attacker.stats.hp = min(attacker.stats.max_hp, attacker.stats.hp + damage)
    attacker.total_healing += damage


# =============================================================================
# ON-ABILITY EFFECTS
# =============================================================================

def shojin_on_ability(engine: 'CombatEngine', caster: 'Unit'):
    """Spear of Shojin: Gain 5 mana after casting ability."""
    caster.stats.mana = min(caster.stats.max_mana, caster.stats.mana + 5)


def blue_buff_on_ability(engine: 'CombatEngine', caster: 'Unit'):
    """Blue Buff: Gain 20 mana after casting ability."""
    caster.stats.mana = min(caster.stats.max_mana, caster.stats.mana + 20)


def archangels_on_ability(engine: 'CombatEngine', caster: 'Unit'):
    """Archangel's Staff: Gain 25 AP after casting ability."""
    caster.stats.ap += 25


def crownguard_on_ability(engine: 'CombatEngine', caster: 'Unit'):
    """Crownguard: Gain 30% max HP shield after casting first ability."""
    casts = get_item_data(caster, 'Crownguard', 'casts', 0) + 1
    set_item_data(caster, 'Crownguard', 'casts', casts)

    if casts == 1:
        shield_amount = caster.stats.max_hp * 0.30
        caster.stats.shield += shield_amount


def leviathan_on_ability(engine: 'CombatEngine', caster: 'Unit'):
    """Leviathan: Deal 4% max HP magic damage to ability targets."""
    # This is handled during ability damage calculation via damage_amp
    # But we can add extra tracking here if needed
    pass


# =============================================================================
# ON-DAMAGE-DEALT EFFECTS
# =============================================================================

def hextech_gunblade_on_damage(engine: 'CombatEngine', attacker: 'Unit', target: 'Unit',
                                damage: float, damage_type):
    """Hextech Gunblade: Heal for 25% of damage dealt."""
    heal_amount = damage * 0.25
    attacker.stats.hp = min(attacker.stats.max_hp, attacker.stats.hp + heal_amount)
    attacker.total_healing += heal_amount


def morellonomicon_on_damage(engine: 'CombatEngine', attacker: 'Unit', target: 'Unit',
                              damage: float, damage_type):
    """Morellonomicon: Ability damage applies 1% max HP burn and 50% healing reduction."""
    from .combat_engine import DamageType

    # Apply burn (10% max HP over 10s = 1% per second, simplified to instant)
    burn_damage = target.stats.max_hp * 0.10
    engine.apply_damage(attacker, target, burn_damage, DamageType.TRUE, "morello_burn")


# =============================================================================
# ON-DAMAGE-TAKEN EFFECTS
# =============================================================================

def bramble_vest_on_damage(engine: 'CombatEngine', defender: 'Unit', attacker: 'Unit',
                            damage: float, damage_type):
    """Bramble Vest: When hit by attack, deal 75 + 10% bonus armor magic damage."""
    from .combat_engine import DamageType

    bonus_armor = defender.stats.armor - defender.base_stats.armor
    reflect_damage = 75 + (bonus_armor * 0.10)

    damage, _ = engine.calculate_damage(defender, attacker, reflect_damage,
                                        DamageType.MAGIC, can_crit=False)
    engine.apply_damage(defender, attacker, damage, DamageType.MAGIC, "bramble_reflect")


def gargoyle_on_damage(engine: 'CombatEngine', defender: 'Unit', attacker: 'Unit',
                        damage: float, damage_type):
    """Gargoyle Stoneplate: Gain 15 armor and MR per enemy targeting you."""
    # Count enemies targeting this unit
    targeting_count = sum(1 for u in engine.units
                          if u.team != defender.team and u.is_alive and u.target == defender)

    # Recalculate bonus (remove old, add new)
    old_bonus = get_item_data(defender, 'Gargoyle', 'bonus', 0)
    new_bonus = targeting_count * 15

    if new_bonus != old_bonus:
        defender.stats.armor += (new_bonus - old_bonus)
        defender.stats.magic_resist += (new_bonus - old_bonus)
        set_item_data(defender, 'Gargoyle', 'bonus', new_bonus)


def steraks_gage_on_damage(engine: 'CombatEngine', defender: 'Unit', attacker: 'Unit',
                            damage: float, damage_type):
    """Sterak's Gage: At 50% HP, gain 25% max HP shield."""
    triggered = get_item_data(defender, 'SteraksGage', 'triggered', False)

    if not triggered and defender.stats.hp <= defender.stats.max_hp * 0.50:
        set_item_data(defender, 'SteraksGage', 'triggered', True)
        shield_amount = defender.stats.max_hp * 0.25
        defender.stats.shield += shield_amount


def edge_of_night_on_damage(engine: 'CombatEngine', defender: 'Unit', attacker: 'Unit',
                             damage: float, damage_type):
    """Edge of Night: At 50% HP, become untargetable briefly and stealth."""
    triggered = get_item_data(defender, 'EdgeOfNight', 'triggered', False)

    if not triggered and defender.stats.hp <= defender.stats.max_hp * 0.50:
        set_item_data(defender, 'EdgeOfNight', 'triggered', True)
        defender.is_targetable = False
        defender.untargetable_duration = 1.0  # 1 second untargetable


# =============================================================================
# ITEM EFFECT REGISTRY
# =============================================================================

# Map item names to their effect functions
ITEM_ON_HIT = {
    "GiantSlayer": giant_slayer_on_hit,
    "LastWhisper": last_whisper_on_hit,
    "TitansResolve": titans_resolve_on_hit,
    "GuinsoosRageblade": guinsoos_on_hit,
    "Artifact_StatikkShiv": statikk_shiv_on_hit,
    "NashorsTooth": nashors_tooth_on_hit,
    "KrakensFury": krakens_fury_on_hit,
    "MadredsBloodrazor": madreds_bloodrazor_on_hit,
    "Artifact_WitsEnd": wits_end_on_hit,
}

ITEM_ON_ABILITY = {
    "SpearOfShojin": shojin_on_ability,
    "BlueBuff": blue_buff_on_ability,
    "ArchangelsStaff": archangels_on_ability,
    "Crownguard": crownguard_on_ability,
    "Leviathan": leviathan_on_ability,
}

ITEM_ON_DAMAGE_DEALT = {
    "HextechGunblade": hextech_gunblade_on_damage,
    "Morellonomicon": morellonomicon_on_damage,
}

ITEM_ON_DAMAGE_TAKEN = {
    "BrambleVest": bramble_vest_on_damage,
    "GargoyleStoneplate": gargoyle_on_damage,
    "SteraksGage": steraks_gage_on_damage,
    "EdgeOfNight": edge_of_night_on_damage,
}


def get_item_on_hit(item_name: str):
    """Get on-hit effect function for an item."""
    return ITEM_ON_HIT.get(item_name)


def get_item_on_ability(item_name: str):
    """Get on-ability effect function for an item."""
    return ITEM_ON_ABILITY.get(item_name)


def get_item_on_damage_dealt(item_name: str):
    """Get on-damage-dealt effect function for an item."""
    return ITEM_ON_DAMAGE_DEALT.get(item_name)


def get_item_on_damage_taken(item_name: str):
    """Get on-damage-taken effect function for an item."""
    return ITEM_ON_DAMAGE_TAKEN.get(item_name)
