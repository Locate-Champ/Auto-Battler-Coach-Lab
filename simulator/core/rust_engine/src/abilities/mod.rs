/// Champion ability dispatch and shared helpers.
///
/// Phase 3 keeps complete API-name coverage and routes champions through:
/// - explicit custom handlers for complex/melee CC patterns
/// - a generic variable-driven fallback that reads `combat_data.json` ability variables
use crate::engine::CombatEngine;
use crate::hex_grid;
use crate::targeting;
use crate::types::{CcType, DamageType, HexPos, UnitId, UnitState};
use crate::unit::{Ability, Unit};

fn star_index(star_level: i32) -> usize {
    star_level.clamp(1, 3) as usize
}

fn ability_var(ability: &Ability, key: &str, star: usize, default: f64) -> f64 {
    let Some(raw) = ability.variables.get(key) else {
        return default;
    };
    if let Some(arr) = raw.as_array() {
        return arr.get(star).and_then(|v| v.as_f64()).unwrap_or(default);
    }
    if let Some(obj) = raw.as_object() {
        let star_key = format!("{star}star");
        return obj
            .get(&star_key)
            .and_then(|v| v.as_f64())
            .unwrap_or(default);
    }
    raw.as_f64().unwrap_or(default)
}

fn ability_var_any(ability: &Ability, keys: &[&str], star: usize, default: f64) -> f64 {
    for key in keys {
        if ability.variables.contains_key(*key) {
            return ability_var(ability, key, star, default);
        }
    }
    default
}

fn is_physical_profile(api_name: &str) -> bool {
    matches!(
        api_name,
        "TFT16_Aatrox"
            | "TFT16_Ambessa"
            | "TFT16_Aphelios"
            | "TFT16_Ashe"
            | "TFT16_BelVeth"
            | "TFT16_Brock"
            | "TFT16_Caitlyn"
            | "TFT16_Darius"
            | "TFT16_Draven"
            | "TFT16_Ekko"
            | "TFT16_Fizz"
            | "TFT16_Gangplank"
            | "TFT16_Graves"
            | "TFT16_Illaoi"
            | "TFT16_JarvanIV"
            | "TFT16_Jhin"
            | "TFT16_Jinx"
            | "TFT16_Kaisa"
            | "TFT16_Kalista"
            | "TFT16_Kindred"
            | "TFT16_KogMaw"
            | "TFT16_Lucian"
            | "TFT16_MissFortune"
            | "TFT16_Nidalee"
            | "TFT16_Poppy"
            | "TFT16_Qiyana"
            | "TFT16_RekSai"
            | "TFT16_Renekton"
            | "TFT16_Rumble"
            | "TFT16_Sett"
            | "TFT16_Shyvana"
            | "TFT16_Singed"
            | "TFT16_Sion"
            | "TFT16_Tryndamere"
            | "TFT16_Tristana"
            | "TFT16_Vayne"
            | "TFT16_Vi"
            | "TFT16_Viego"
            | "TFT16_Volibear"
            | "TFT16_Warwick"
            | "TFT16_Wukong"
            | "TFT16_XinZhao"
            | "TFT16_Yasuo"
            | "TFT16_Yone"
            | "TFT16_Yorick"
    )
}

fn infer_damage_type(api_name: &str, ability: &Ability) -> DamageType {
    if ability.variables.contains_key("TrueDamage")
        || ability.variables.contains_key("ExecuteDamage")
        || ability.variables.contains_key("TrueDamagePerTick")
    {
        return DamageType::True;
    }
    let has_ad = ability.variables.contains_key("ADDamage")
        || ability.variables.contains_key("PhysicalDamage")
        || ability.variables.contains_key("AttackDamage");
    let has_ap = ability.variables.contains_key("APDamage")
        || ability.variables.contains_key("MagicDamage")
        || ability.variables.contains_key("SpellDamage");

    if has_ad && !has_ap {
        DamageType::Physical
    } else if has_ap && !has_ad {
        DamageType::Magic
    } else if is_physical_profile(api_name) {
        DamageType::Physical
    } else {
        ability.damage_type
    }
}

fn infer_aoe_radius(ability: &Ability, star: usize) -> i32 {
    let from_vars = ability_var_any(
        ability,
        &[
            "HexRadius",
            "HexRange",
            "Radius",
            "AOERadius",
            "ExplosionRadius",
            "NearbyEnemyHexRadius",
        ],
        star,
        ability.aoe_radius as f64,
    )
    .round() as i32;
    if from_vars > 0 {
        from_vars
    } else {
        ability.aoe_radius.max(0)
    }
}

fn infer_num_targets(ability: &Ability, star: usize) -> usize {
    let n = ability_var_any(
        ability,
        &["NumTargets", "NumEnemies", "NumMissiles"],
        star,
        ability.num_targets.max(1) as f64,
    )
    .round() as i32;
    n.max(1) as usize
}

fn estimate_ability_damage(
    caster: &Unit,
    api_name: &str,
    ability: &Ability,
    star: usize,
    damage_type: DamageType,
) -> f64 {
    let fallback = ability.base_damage.get(star).copied().unwrap_or(0.0);
    let base = ability_var_any(
        ability,
        &[
            "Damage",
            "MagicDamage",
            "APDamage",
            "ADDamage",
            "PhysicalDamage",
            "TargetDamage",
            "PrimaryDamage",
            "BaseDamage",
            "TotalDamage",
            "AbilityDamage",
            "ExplosionDamage",
            "SecondaryDamage",
        ],
        star,
        fallback,
    );

    let mut ap_scaling = ability_var_any(
        ability,
        &["APScaling", "APRatio", "APMultiplier"],
        star,
        ability.ap_scaling,
    );
    let mut ad_scaling = ability_var_any(
        ability,
        &[
            "ADScaling",
            "ADRatio",
            "YasuoADPercent",
            "ADDamageMultiplier",
        ],
        star,
        ability.ad_scaling,
    );

    if ap_scaling > 10.0 {
        ap_scaling /= 100.0;
    }
    if ad_scaling > 10.0 {
        ad_scaling /= 100.0;
    }

    let mut damage =
        base * (1.0 + caster.stats.ap * ap_scaling / 100.0) + caster.stats.ad * ad_scaling;

    if matches!(damage_type, DamageType::Physical) && is_physical_profile(api_name) {
        let ad_mult = if ad_scaling > 0.0 { ad_scaling } else { 1.0 };
        damage = base.max(0.0) + caster.stats.ad * ad_mult;
    }

    if damage <= 0.0 {
        damage = caster.stats.ad.max(caster.stats.ap).max(1.0);
    }
    damage
}

fn current_target_or_nearest(
    engine: &CombatEngine,
    caster_idx: UnitId,
    enemy_indices: &[UnitId],
) -> Option<UnitId> {
    if let Some(target_idx) = engine.units[caster_idx].target_idx {
        if enemy_indices.contains(&target_idx)
            && engine.units[target_idx].is_alive
            && engine.units[target_idx].is_targetable
        {
            return Some(target_idx);
        }
    }

    let caster_pos = engine.units[caster_idx].position;
    enemy_indices
        .iter()
        .copied()
        .filter(|&idx| engine.units[idx].is_alive && engine.units[idx].is_targetable)
        .min_by_key(|&idx| hex_grid::hex_distance(caster_pos, engine.units[idx].position))
}

fn apply_stun(engine: &mut CombatEngine, target_idx: UnitId, duration: f64) {
    if duration <= 0.0 || !engine.units[target_idx].is_alive {
        return;
    }

    let qs_until = engine.units[target_idx]
        .item_data
        .get("Quicksilver:immune_until")
        .copied()
        .unwrap_or(0.0);
    let titans_immune = engine.units[target_idx]
        .item_data
        .get("TitansResolve:cc_immune")
        .copied()
        .unwrap_or(0.0);
    if engine.time < qs_until || titans_immune > 0.5 {
        return;
    }

    if duration > engine.units[target_idx].stun_duration {
        engine.units[target_idx].stun_duration = duration;
        engine.units[target_idx].state = UnitState::Stunned;
        engine.units[target_idx].cc_type = Some(CcType::Stunned);
    }
}

fn apply_self_shield(
    engine: &mut CombatEngine,
    caster_idx: UnitId,
    ability: &Ability,
    star: usize,
) -> bool {
    let flat_shield = ability_var_any(
        ability,
        &["Shield", "APShield", "ShieldAmount", "FlatShield"],
        star,
        0.0,
    );
    let percent_shield = ability_var_any(
        ability,
        &["PercentHealthShield", "MaxHealthShieldPercent"],
        star,
        0.0,
    );

    let max_hp = engine.units[caster_idx].stats.max_hp.max(0.0);
    let mut shield = 0.0_f64;

    if flat_shield > 0.0 {
        if flat_shield <= 1.0 && percent_shield <= 0.0 {
            shield += flat_shield * max_hp;
        } else {
            shield += flat_shield;
        }
    }
    if percent_shield > 0.0 {
        shield += percent_shield * max_hp;
    }

    if shield <= 0.0 {
        return false;
    }
    engine.units[caster_idx].stats.shield += shield.max(0.0);
    true
}

fn apply_self_heal(
    engine: &mut CombatEngine,
    caster_idx: UnitId,
    ability: &Ability,
    star: usize,
) -> bool {
    let flat_heal = ability_var_any(
        ability,
        &["Heal", "APHeal", "HealAmount", "FlatHeal"],
        star,
        0.0,
    );
    let percent_heal = ability_var_any(
        ability,
        &["PercentHealthHeal", "MaxHealthHealPercent"],
        star,
        0.0,
    );

    let max_hp = engine.units[caster_idx].stats.max_hp.max(0.0);
    let mut heal = 0.0_f64;

    if flat_heal > 0.0 {
        if flat_heal <= 1.0 && percent_heal <= 0.0 {
            heal += flat_heal * max_hp;
        } else {
            heal += flat_heal;
        }
    }
    if percent_heal > 0.0 {
        heal += percent_heal * max_hp;
    }

    if heal <= 0.0 {
        return false;
    }
    crate::damage::heal_unit(&mut engine.units[caster_idx], heal.max(0.0));
    true
}

fn apply_lowest_ally_heal(
    engine: &mut CombatEngine,
    caster_idx: UnitId,
    ally_indices: &[UnitId],
    ability: &Ability,
    star: usize,
) -> bool {
    let mut heal = ability_var_any(
        ability,
        &["Heal", "APHeal", "HealAmount", "PercentHealthHeal"],
        star,
        0.0,
    );
    if heal <= 0.0 {
        return false;
    }

    let team = engine.units[caster_idx].team;
    let mut lowest_idx = caster_idx;
    let mut lowest_pct = if engine.units[caster_idx].stats.max_hp > 0.0 {
        engine.units[caster_idx].stats.hp / engine.units[caster_idx].stats.max_hp
    } else {
        1.0
    };

    for idx in ally_indices.iter().copied() {
        let ally = &engine.units[idx];
        if !ally.is_alive || ally.team != team || ally.stats.max_hp <= 0.0 {
            continue;
        }
        let hp_pct = ally.stats.hp / ally.stats.max_hp;
        if hp_pct < lowest_pct {
            lowest_pct = hp_pct;
            lowest_idx = idx;
        }
    }

    if ability.variables.contains_key("PercentHealthHeal") || heal <= 1.0 {
        heal *= engine.units[lowest_idx].stats.max_hp;
    }
    crate::damage::heal_unit(&mut engine.units[lowest_idx], heal.max(0.0));
    true
}

fn dash_adjacent_to_target(engine: &mut CombatEngine, caster_idx: UnitId, target_idx: UnitId) {
    let caster_pos = engine.units[caster_idx].position;
    let target_pos = engine.units[target_idx].position;
    let mut candidates: Vec<HexPos> = hex_grid::hex_neighbors(target_pos).to_vec();
    candidates.sort_by_key(|pos| hex_grid::hex_distance(*pos, caster_pos));

    for pos in candidates {
        let occupied = engine
            .units
            .iter()
            .enumerate()
            .any(|(idx, unit)| idx != caster_idx && unit.is_alive && unit.position == pos);
        if !occupied {
            engine.units[caster_idx].position = pos;
            engine.alive_dirty = true;
            return;
        }
    }
}

fn cast_dash_strike(
    engine: &mut CombatEngine,
    caster_idx: UnitId,
    enemy_indices: &[UnitId],
) -> bool {
    let (ability, star, api_name) = {
        let caster = &engine.units[caster_idx];
        let Some(ability) = caster.ability.clone() else {
            return false;
        };
        (
            ability,
            star_index(caster.star_level),
            caster.api_name.clone(),
        )
    };

    let Some(target_idx) = current_target_or_nearest(engine, caster_idx, enemy_indices) else {
        return false;
    };

    dash_adjacent_to_target(engine, caster_idx, target_idx);

    let caster_snapshot = engine.units[caster_idx].clone();
    let damage_type = infer_damage_type(api_name.as_str(), &ability);
    let damage = estimate_ability_damage(
        &caster_snapshot,
        api_name.as_str(),
        &ability,
        star,
        damage_type,
    );
    let _ = engine.deal_damage(
        Some(caster_idx),
        target_idx,
        damage,
        damage_type,
        true,
        true,
        "dash_strike",
    );

    let stun = ability_var_any(
        &ability,
        &[
            "StunDuration",
            "KnockupDuration",
            "TauntDuration",
            "RootDuration",
        ],
        star,
        0.0,
    );
    if stun > 0.0 {
        apply_stun(engine, target_idx, stun);
    }

    true
}

fn cast_frontline_cc(
    engine: &mut CombatEngine,
    caster_idx: UnitId,
    enemy_indices: &[UnitId],
) -> bool {
    let (ability, star, api_name, caster_pos) = {
        let caster = &engine.units[caster_idx];
        let Some(ability) = caster.ability.clone() else {
            return false;
        };
        (
            ability,
            star_index(caster.star_level),
            caster.api_name.clone(),
            caster.position,
        )
    };

    let primary_target = current_target_or_nearest(engine, caster_idx, enemy_indices);
    let center = primary_target
        .map(|idx| engine.units[idx].position)
        .unwrap_or(caster_pos);

    let caster_snapshot = engine.units[caster_idx].clone();
    let damage_type = infer_damage_type(api_name.as_str(), &ability);
    let damage = estimate_ability_damage(
        &caster_snapshot,
        api_name.as_str(),
        &ability,
        star,
        damage_type,
    );
    let radius = infer_aoe_radius(&ability, star).max(1);

    let mut targets = targeting::get_enemies_in_range(center, radius, enemy_indices, &engine.units);
    if targets.is_empty() {
        if let Some(target_idx) = primary_target {
            targets.push(target_idx);
        }
    }

    let stun = ability_var_any(
        &ability,
        &[
            "StunDuration",
            "KnockupDuration",
            "TauntDuration",
            "RootDuration",
        ],
        star,
        0.0,
    );

    for target_idx in targets {
        let _ = engine.deal_damage(
            Some(caster_idx),
            target_idx,
            damage,
            damage_type,
            true,
            true,
            "frontline_cc",
        );
        if stun > 0.0 {
            apply_stun(engine, target_idx, stun);
        }
    }

    let _ = apply_self_shield(engine, caster_idx, &ability, star);
    true
}

fn cast_supportive(
    engine: &mut CombatEngine,
    caster_idx: UnitId,
    enemy_indices: &[UnitId],
    ally_indices: &[UnitId],
) -> bool {
    let (ability, star) = {
        let caster = &engine.units[caster_idx];
        let Some(ability) = caster.ability.clone() else {
            return false;
        };
        (ability, star_index(caster.star_level))
    };

    let shielded = apply_self_shield(engine, caster_idx, &ability, star);
    let healed = apply_lowest_ally_heal(engine, caster_idx, ally_indices, &ability, star);
    let damaged = default_ability_cast(engine, caster_idx, enemy_indices);

    shielded || healed || damaged
}

fn cast_execute_spell(
    engine: &mut CombatEngine,
    caster_idx: UnitId,
    enemy_indices: &[UnitId],
) -> bool {
    let (ability, star, api_name) = {
        let caster = &engine.units[caster_idx];
        let Some(ability) = caster.ability.clone() else {
            return false;
        };
        (
            ability,
            star_index(caster.star_level),
            caster.api_name.clone(),
        )
    };

    let Some(target_idx) = current_target_or_nearest(engine, caster_idx, enemy_indices) else {
        return false;
    };

    let execute_threshold = ability_var_any(
        &ability,
        &[
            "Execute",
            "ExecuteThreshold",
            "KillThreshold",
            "HealthThreshold",
            "ThirdCastExecute",
        ],
        star,
        0.0,
    )
    .clamp(0.0, 1.0);

    if execute_threshold > 0.0 && engine.units[target_idx].stats.max_hp > 0.0 {
        let hp_pct = engine.units[target_idx].stats.hp / engine.units[target_idx].stats.max_hp;
        if hp_pct <= execute_threshold {
            let hp = engine.units[target_idx].stats.hp;
            let _ = engine.deal_damage(
                None,
                target_idx,
                hp + 1.0,
                DamageType::True,
                false,
                true,
                "execute",
            );
            return true;
        }
    }

    let caster_snapshot = engine.units[caster_idx].clone();
    let damage_type = infer_damage_type(api_name.as_str(), &ability);
    let damage = estimate_ability_damage(
        &caster_snapshot,
        api_name.as_str(),
        &ability,
        star,
        damage_type,
    );
    let _ = engine.deal_damage(
        Some(caster_idx),
        target_idx,
        damage,
        damage_type,
        true,
        true,
        "execute_spell",
    );
    true
}

fn cast_aatrox_combo(
    engine: &mut CombatEngine,
    caster_idx: UnitId,
    enemy_indices: &[UnitId],
) -> bool {
    let (ability, star) = {
        let caster = &engine.units[caster_idx];
        let Some(ability) = caster.ability.clone() else {
            return false;
        };
        (ability, star_index(caster.star_level))
    };

    let Some(target_idx) = current_target_or_nearest(engine, caster_idx, enemy_indices) else {
        return false;
    };

    let combo_key = "ability:aatrox_combo".to_string();
    let mut combo = engine.units[caster_idx]
        .item_data
        .get(&combo_key)
        .copied()
        .unwrap_or(0.0) as i32
        + 1;
    if combo > 3 {
        combo = 1;
    }

    let caster_snapshot = engine.units[caster_idx].clone();
    let mut damage = estimate_ability_damage(
        &caster_snapshot,
        "TFT16_Aatrox",
        &ability,
        star,
        DamageType::Physical,
    );

    if combo == 2 {
        let mult = ability_var(&ability, "SecondCastPercentDamage", star, 1.2);
        damage *= mult.max(0.5);
        let stun = ability_var(&ability, "SecondCastStunDuration", star, 0.0);
        if stun > 0.0 {
            apply_stun(engine, target_idx, stun);
        }
    } else if combo == 3 {
        let mult = ability_var(&ability, "ThirdCastPercentDamage", star, 1.6);
        damage *= mult.max(0.5);
        let execute_threshold =
            ability_var(&ability, "ThirdCastExecute", star, 0.0).clamp(0.0, 1.0);
        if execute_threshold > 0.0 && engine.units[target_idx].stats.max_hp > 0.0 {
            let hp_pct = engine.units[target_idx].stats.hp / engine.units[target_idx].stats.max_hp;
            if hp_pct <= execute_threshold {
                let hp = engine.units[target_idx].stats.hp;
                let _ = engine.deal_damage(
                    None,
                    target_idx,
                    hp + 1.0,
                    DamageType::True,
                    false,
                    true,
                    "aatrox_execute",
                );
                engine.units[caster_idx].item_data.insert(combo_key, 0.0);
                return true;
            }
        }
        engine.units[caster_idx].item_data.insert(combo_key, 0.0);
    } else {
        engine.units[caster_idx]
            .item_data
            .insert(combo_key, combo as f64);
    }

    let _ = engine.deal_damage(
        Some(caster_idx),
        target_idx,
        damage,
        DamageType::Physical,
        true,
        true,
        "aatrox_combo",
    );

    true
}

/// Dispatch a champion's ability cast.
/// Returns true if the ability was handled, false for fallback.
pub fn cast_ability(
    engine: &mut CombatEngine,
    caster_idx: UnitId,
    enemy_indices: &[UnitId],
    ally_indices: &[UnitId],
) -> bool {
    let api_name = engine.units[caster_idx].api_name.clone();

    if !is_supported_champion(api_name.as_str()) {
        return false;
    }

    match api_name.as_str() {
        "TFT16_Aatrox" => cast_aatrox_combo(engine, caster_idx, enemy_indices),
        "TFT16_Ambessa" | "TFT16_Ekko" | "TFT16_Fizz" | "TFT16_Qiyana" | "TFT16_Vi"
        | "TFT16_Viego" | "TFT16_Warwick" | "TFT16_Yasuo" | "TFT16_Yone" => {
            cast_dash_strike(engine, caster_idx, enemy_indices)
        }
        "TFT16_Blitzcrank" | "TFT16_Braum" | "TFT16_ChoGath" | "TFT16_Kobuko" | "TFT16_Leona"
        | "TFT16_Nautilus" | "TFT16_Sejuani" | "TFT16_Sion" | "TFT16_Taric" => {
            cast_frontline_cc(engine, caster_idx, enemy_indices)
        }
        "TFT16_Lulu" | "TFT16_Milio" | "TFT16_Orianna" | "TFT16_Seraphine" | "TFT16_Sona" => {
            cast_supportive(engine, caster_idx, enemy_indices, ally_indices)
        }
        "TFT16_Vayne" | "TFT16_Veigar" => cast_execute_spell(engine, caster_idx, enemy_indices),
        _ => default_ability_cast(engine, caster_idx, enemy_indices),
    }
}

fn is_supported_champion(api_name: &str) -> bool {
    matches!(
        api_name,
        "TFT16_Aatrox"
            | "TFT16_Ahri"
            | "TFT16_Ambessa"
            | "TFT16_Anivia"
            | "TFT16_Annie"
            | "TFT16_AnnieTibbers"
            | "TFT16_Aphelios"
            | "TFT16_Ashe"
            | "TFT16_Atakhan"
            | "TFT16_AurelionSol"
            | "TFT16_Azir"
            | "TFT16_AzirSoldier"
            | "TFT16_Bard"
            | "TFT16_BaronNashor"
            | "TFT16_BelVeth"
            | "TFT16_Blitzcrank"
            | "TFT16_Braum"
            | "TFT16_Briar"
            | "TFT16_Brock"
            | "TFT16_Caitlyn"
            | "TFT16_ChoGath"
            | "TFT16_Darius"
            | "TFT16_Diana"
            | "TFT16_DrMundo"
            | "TFT16_Draven"
            | "TFT16_Ekko"
            | "TFT16_Fiddlesticks"
            | "TFT16_Fizz"
            | "TFT16_FreljordProp"
            | "TFT16_Galio"
            | "TFT16_Gangplank"
            | "TFT16_Garen"
            | "TFT16_Graves"
            | "TFT16_Gwen"
            | "TFT16_Illaoi"
            | "TFT16_JarvanIV"
            | "TFT16_Jhin"
            | "TFT16_Jinx"
            | "TFT16_Kaisa"
            | "TFT16_Kalista"
            | "TFT16_Kennen"
            | "TFT16_Kindred"
            | "TFT16_Kobuko"
            | "TFT16_KogMaw"
            | "TFT16_Leblanc"
            | "TFT16_Leona"
            | "TFT16_Lissandra"
            | "TFT16_Loris"
            | "TFT16_Lucian"
            | "TFT16_Lulu"
            | "TFT16_Lux"
            | "TFT16_Malzahar"
            | "TFT16_MalzaharVoidling"
            | "TFT16_Mel"
            | "TFT16_Milio"
            | "TFT16_MissFortune"
            | "TFT16_Nasus"
            | "TFT16_Nautilus"
            | "TFT16_Neeko"
            | "TFT16_Nidalee"
            | "TFT16_Orianna"
            | "TFT16_Ornn"
            | "TFT16_PiltoverInvention"
            | "TFT16_Poppy"
            | "TFT16_Qiyana"
            | "TFT16_RekSai"
            | "TFT16_Renekton"
            | "TFT16_RiftHerald"
            | "TFT16_Rumble"
            | "TFT16_Ryze"
            | "TFT16_Sejuani"
            | "TFT16_Seraphine"
            | "TFT16_Sett"
            | "TFT16_Shen"
            | "TFT16_Shyvana"
            | "TFT16_Singed"
            | "TFT16_Sion"
            | "TFT16_Skarner"
            | "TFT16_Sona"
            | "TFT16_Swain"
            | "TFT16_Sylas"
            | "TFT16_THex"
            | "TFT16_TahmKench"
            | "TFT16_Taric"
            | "TFT16_Teemo"
            | "TFT16_Thresh"
            | "TFT16_Tristana"
            | "TFT16_Tryndamere"
            | "TFT16_TwistedFate"
            | "TFT16_Vayne"
            | "TFT16_Veigar"
            | "TFT16_Vi"
            | "TFT16_Viego"
            | "TFT16_Volibear"
            | "TFT16_Warwick"
            | "TFT16_Wukong"
            | "TFT16_Xerath"
            | "TFT16_XinZhao"
            | "TFT16_Yasuo"
            | "TFT16_Yone"
            | "TFT16_Yorick"
            | "TFT16_Yunara"
            | "TFT16_Zaahen"
            | "TFT16_Ziggs"
            | "TFT16_Zilean"
            | "TFT16_Zoe"
    )
}

/// Generic variable-driven ability cast: applies damage, optional AOE, optional stun,
/// and self shield/heal if those variables are present.
fn default_ability_cast(
    engine: &mut CombatEngine,
    caster_idx: UnitId,
    enemy_indices: &[UnitId],
) -> bool {
    let (ability, star, api_name, caster_pos, caster_snapshot) = {
        let unit = &engine.units[caster_idx];
        let ability = match &unit.ability {
            Some(a) => a.clone(),
            None => return false,
        };
        (
            ability,
            star_index(unit.star_level),
            unit.api_name.clone(),
            unit.position,
            unit.clone(),
        )
    };

    let shielded = apply_self_shield(engine, caster_idx, &ability, star);
    let healed = apply_self_heal(engine, caster_idx, &ability, star);

    let damage_type = infer_damage_type(api_name.as_str(), &ability);
    let total_damage = estimate_ability_damage(
        &caster_snapshot,
        api_name.as_str(),
        &ability,
        star,
        damage_type,
    );

    let radius = infer_aoe_radius(&ability, star);
    let max_targets = infer_num_targets(&ability, star);
    let stun = ability_var_any(
        &ability,
        &[
            "StunDuration",
            "KnockupDuration",
            "TauntDuration",
            "RootDuration",
        ],
        star,
        0.0,
    );

    let mut targets: Vec<UnitId> = if radius > 0 {
        let center = current_target_or_nearest(engine, caster_idx, enemy_indices)
            .map(|idx| engine.units[idx].position)
            .unwrap_or(caster_pos);
        targeting::get_enemies_in_range(center, radius, enemy_indices, &engine.units)
    } else {
        current_target_or_nearest(engine, caster_idx, enemy_indices)
            .map(|idx| vec![idx])
            .unwrap_or_default()
    };

    if targets.len() > max_targets {
        let caster_pos = engine.units[caster_idx].position;
        targets.sort_by_key(|idx| hex_grid::hex_distance(caster_pos, engine.units[*idx].position));
        targets.truncate(max_targets);
    }

    for target_idx in &targets {
        let _ = engine.deal_damage(
            Some(caster_idx),
            *target_idx,
            total_damage,
            damage_type,
            true,
            true,
            "ability",
        );
        if stun > 0.0 {
            apply_stun(engine, *target_idx, stun);
        }
    }

    !targets.is_empty() || shielded || healed
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::data::CombatData;
    use crate::engine::CombatEngine;
    use crate::unit::{CombatStats, Unit};
    use std::collections::HashMap;
    use std::fs;
    use std::path::PathBuf;
    use std::sync::Arc;

    #[test]
    fn test_supported_champion_coverage_matches_combat_data() {
        let combat_data_path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("..")
            .join("data")
            .join("combat_data.json");

        let content = fs::read_to_string(&combat_data_path)
            .expect("failed to read simulator/data/combat_data.json");
        let parsed: serde_json::Value =
            serde_json::from_str(&content).expect("failed to parse combat_data.json");

        let champions = parsed
            .get("champions")
            .and_then(|v| v.as_object())
            .expect("combat_data.json missing champions object");

        let mut missing = Vec::new();
        for api_name in champions.keys() {
            if !is_supported_champion(api_name.as_str()) {
                missing.push(api_name.clone());
            }
        }

        assert!(
            missing.is_empty(),
            "ability dispatch missing champion API names: {:?}",
            missing
        );
    }

    #[test]
    fn test_apply_self_shield_combines_flat_and_percent_components() {
        let combat_data = CombatData {
            champions: Arc::new(HashMap::new()),
        };
        let mut engine = CombatEngine::new(combat_data);

        let mut stats = CombatStats::default();
        stats.hp = 1000.0;
        stats.max_hp = 1000.0;
        let unit = Unit::new(
            "Sion".to_string(),
            "TFT16_Sion".to_string(),
            2,
            4,
            "Tank".to_string(),
            stats.clone(),
            stats,
            (0, 0),
            0,
        );
        engine.units.push(unit);

        let ability = Ability {
            name: "Soul Furnace".to_string(),
            ability_type: crate::types::AbilityType::Shield,
            damage_type: DamageType::Magic,
            targeting: crate::types::TargetingType::Nearest,
            base_damage: [0.0, 0.0, 0.0, 0.0],
            ap_scaling: 0.0,
            ad_scaling: 0.0,
            cast_time: 0.0,
            aoe_radius: 0,
            num_targets: 1,
            variables: HashMap::from([
                ("APShield".to_string(), serde_json::json!(225.0)),
                ("PercentHealthShield".to_string(), serde_json::json!(0.04)),
            ]),
        };

        let applied = apply_self_shield(&mut engine, 0, &ability, 2);
        assert!(applied);
        assert!((engine.units[0].stats.shield - 265.0).abs() < 1e-9);
    }
}
