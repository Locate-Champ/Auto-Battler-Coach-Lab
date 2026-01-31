"""Set 16 role definitions and combat-facing metadata."""

from __future__ import annotations

from typing import Dict

ROLE_ALIASES = {
    "ADCasterFormSwapper": "ADCaster",
}

ROLE_RULES: Dict[str, Dict[str, object]] = {
    "ADCaster": {
        "label": "Attack Caster",
        "damage_type": "attack",
        "role_group": "caster",
        "lane": "backline",
        "mana_on_attack": 7,
        "mana_regen": 2,
        "notes": "Attacks grant 7 Mana; +2 Mana Regen.",
    },
    "APCaster": {
        "label": "Magic Caster",
        "damage_type": "magic",
        "role_group": "caster",
        "lane": "backline",
        "mana_on_attack": 7,
        "mana_regen": 2,
        "notes": "Attacks grant 7 Mana; +2 Mana Regen.",
    },
    "ADFighter": {
        "label": "Attack Fighter",
        "damage_type": "attack",
        "role_group": "fighter",
        "lane": "frontline",
        "mana_on_attack": 10,
        "attack_speed_stage_bonus": "5-30% (by stage)",
        "notes": "Attacks grant 10 Mana; gain stage-scaled Attack Speed.",
    },
    "APFighter": {
        "label": "Magic Fighter",
        "damage_type": "magic",
        "role_group": "fighter",
        "lane": "frontline",
        "mana_on_attack": 10,
        "attack_speed_stage_bonus": "5-30% (by stage)",
        "notes": "Attacks grant 10 Mana; gain stage-scaled Attack Speed.",
    },
    "HFighter": {
        "label": "Hybrid Fighter",
        "damage_type": "hybrid",
        "role_group": "fighter",
        "lane": "frontline",
        "mana_on_attack": 10,
        "attack_speed_stage_bonus": "5-30% (by stage)",
        "notes": "Hybrid fighter with stage-scaled Attack Speed.",
    },
    "ADReaper": {
        "label": "Attack Assassin",
        "damage_type": "attack",
        "role_group": "assassin",
        "lane": "backline",
        "mana_on_attack": 10,
        "damage_reduction_non_target": 0.15,
        "notes": "Takes 15% less damage from non-targets.",
    },
    "APReaper": {
        "label": "Magic Assassin",
        "damage_type": "magic",
        "role_group": "assassin",
        "lane": "backline",
        "mana_on_attack": 10,
        "damage_reduction_non_target": 0.15,
        "notes": "Takes 15% less damage from non-targets.",
    },
    "ADCarry": {
        "label": "Attack Marksman",
        "damage_type": "attack",
        "role_group": "marksman",
        "lane": "backline",
        "mana_on_attack": 10,
        "notes": "Backline marksman; attacks grant 10 Mana.",
    },
    "APCarry": {
        "label": "Magic Marksman",
        "damage_type": "magic",
        "role_group": "marksman",
        "lane": "backline",
        "mana_on_attack": 10,
        "notes": "Backline marksman; attacks grant 10 Mana.",
    },
    "ADSpecialist": {
        "label": "Attack Specialist",
        "damage_type": "attack",
        "role_group": "specialist",
        "lane": "flex",
        "notes": "Specialists generate resources in a unique way.",
    },
    "APSpecialist": {
        "label": "Magic Specialist",
        "damage_type": "magic",
        "role_group": "specialist",
        "lane": "flex",
        "notes": "Specialists generate resources in a unique way.",
    },
    "ADTank": {
        "label": "Attack Tank",
        "damage_type": "attack",
        "role_group": "tank",
        "lane": "frontline",
        "mana_on_attack": 5,
        "mana_from_damage": True,
        "targeting_bias": "high",
        "notes": "More likely to be targeted; gains Mana from damage.",
    },
    "APTank": {
        "label": "Magic Tank",
        "damage_type": "magic",
        "role_group": "tank",
        "lane": "frontline",
        "mana_on_attack": 5,
        "mana_from_damage": True,
        "targeting_bias": "high",
        "notes": "More likely to be targeted; gains Mana from damage.",
    },
}


def normalize_role(role: str) -> str:
    if not role:
        return "Unknown"
    return ROLE_ALIASES.get(role, role)


def get_role_profile(role: str) -> Dict[str, object]:
    normalized = normalize_role(role)
    return ROLE_RULES.get(
        normalized,
        {
            "label": normalized,
            "damage_type": "unknown",
            "role_group": "unknown",
            "lane": "unknown",
            "notes": "Role not found in Set 16 mapping.",
        },
    )


def is_ap_role(role: str) -> bool:
    return get_role_profile(role).get("damage_type") == "magic"


def is_ad_role(role: str) -> bool:
    return get_role_profile(role).get("damage_type") == "attack"


def is_frontline_role(role: str) -> bool:
    return get_role_profile(role).get("lane") == "frontline"


def is_carry_role(role: str) -> bool:
    role_group = get_role_profile(role).get("role_group")
    return role_group in {"marksman", "caster", "assassin", "specialist"}
