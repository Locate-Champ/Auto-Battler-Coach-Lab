/// Item stat application and combat-time hooks.
use crate::damage;
use crate::engine::CombatEngine;
use crate::hex_grid;
use crate::types::{DamageType, UnitId};
use crate::unit::{DotEffect, Item, Unit};
use std::borrow::Cow;

fn data_key(item_name: &str, field: &str) -> String {
    format!("{}:{}", item_name, field)
}

fn get_item_data(unit: &Unit, item_name: &str, field: &str, default: f64) -> f64 {
    let key = data_key(item_name, field);
    unit.item_data.get(&key).copied().unwrap_or(default)
}

fn set_item_data(unit: &mut Unit, item_name: &str, field: &str, value: f64) {
    let key = data_key(item_name, field);
    unit.item_data.insert(key, value);
}

fn add_ad_pct(unit: &mut Unit, pct: f64) {
    unit.stats.ad += unit.base_stats.ad * pct;
}

fn add_hp_flat(unit: &mut Unit, hp: f64) {
    unit.stats.hp += hp;
    unit.stats.max_hp += hp;
}

fn add_bonus_hp_pct(unit: &mut Unit, pct: f64) {
    let bonus = unit.base_stats.max_hp * pct;
    add_hp_flat(unit, bonus);
}

pub fn resolve_item_name(item_name: &str) -> Cow<'_, str> {
    if let Some(stripped) = item_name.strip_prefix("Radiant") {
        return Cow::Borrowed(stripped);
    }
    match item_name {
        "TFT_Item_Leviathan" => Cow::Borrowed("NashorsTooth"),
        "TFT_Item_MadredsBloodrazor" => Cow::Borrowed("GiantSlayer"),
        "TFT_Item_UnstableConcoction" => Cow::Borrowed("HandOfJustice"),
        "TFT_Item_NightHarvester" => Cow::Borrowed("SteadfastHeart"),
        "TFT_Item_SpectralGauntlet" => Cow::Borrowed("Evenshroud"),
        "TFT_Item_StatikkShiv" => Cow::Borrowed("Artifact_StatikkShiv"),
        "Gargoyle" => Cow::Borrowed("GargoyleStoneplate"),
        "RunaansHurricane" => Cow::Borrowed("KrakensFury"),
        _ => Cow::Borrowed(item_name),
    }
}

pub fn unit_has_item(unit: &Unit, item_name: &str) -> bool {
    unit.items
        .iter()
        .any(|item| resolve_item_name(item.name.as_str()).as_ref() == item_name)
}

pub fn apply_item_stats(unit: &mut Unit, item_name: &str, as_cap: f64) {
    let resolved = resolve_item_name(item_name);
    unit.items.push(Item {
        name: item_name.to_string(),
        stats: Vec::new(),
    });

    match resolved.as_ref() {
        // AD / AS / crit items
        "Deathblade" => {
            add_ad_pct(unit, 0.55);
            unit.stats.damage_amp += 0.10;
        }
        "InfinityEdge" => {
            add_ad_pct(unit, 0.35);
            unit.stats.crit_chance += 0.35;
            unit.stats.crit_multiplier += 0.10;
        }
        "GiantSlayer" => {
            add_ad_pct(unit, 0.15);
            unit.stats.ap += 15.0;
            unit.stats.attack_speed += 0.15;
            unit.stats.damage_amp += 0.15;
        }
        "LastWhisper" => {
            add_ad_pct(unit, 0.15);
            unit.stats.attack_speed += 0.20;
            unit.stats.crit_chance += 0.20;
        }
        "Bloodthirster" => {
            add_ad_pct(unit, 0.15);
            unit.stats.ap += 15.0;
            unit.stats.magic_resist += 20.0;
            unit.stats.omnivamp += 0.20;
        }
        "SteraksGage" => {
            add_ad_pct(unit, 0.40);
            add_hp_flat(unit, 300.0);
        }
        "EdgeOfNight" => {
            add_ad_pct(unit, 0.10);
            unit.stats.ap += 10.0;
            unit.stats.attack_speed += 0.15;
            unit.stats.armor += 20.0;
        }
        "RedBuff" => {
            unit.stats.attack_speed += 0.45;
            unit.stats.damage_amp += 0.06;
        }
        "GuinsoosRageblade" => {
            unit.stats.ap += 10.0;
            unit.stats.attack_speed += 0.10;
        }
        "KrakensFury" => {
            add_ad_pct(unit, 0.10);
            unit.stats.attack_speed += 0.10;
            unit.stats.magic_resist += 20.0;
        }
        "TitansResolve" => {
            unit.stats.attack_speed += 0.10;
            unit.stats.armor += 20.0;
        }
        "NashorsTooth" => {
            unit.stats.ap += 18.0;
            unit.stats.attack_speed += 0.10;
            unit.stats.crit_chance += 0.20;
            add_hp_flat(unit, 150.0);
        }

        // AP / mana items
        "RabadonsDeathcap" => {
            unit.stats.ap += 50.0;
            unit.stats.damage_amp += 0.15;
        }
        "JeweledGauntlet" => {
            unit.stats.ap += 35.0;
            unit.stats.crit_chance += 0.35;
            unit.stats.crit_multiplier += 0.10;
        }
        "HextechGunblade" => {
            add_ad_pct(unit, 0.20);
            unit.stats.ap += 20.0;
            unit.stats.omnivamp += 0.15;
        }
        "SpearOfShojin" => {
            add_ad_pct(unit, 0.15);
            unit.stats.ap += 15.0;
        }
        "BlueBuff" => {
            add_ad_pct(unit, 0.15);
            unit.stats.ap += 15.0;
            unit.stats.max_mana = (unit.stats.max_mana - 10.0).max(10.0);
        }
        "Morellonomicon" => {
            unit.stats.ap += 20.0;
            add_hp_flat(unit, 150.0);
        }
        "ArchangelsStaff" => {
            unit.stats.ap += 30.0;
        }
        "IonicSpark" => {
            unit.stats.ap += 15.0;
            add_hp_flat(unit, 250.0);
            unit.stats.magic_resist += 35.0;
        }
        "VoidStaff" => {
            unit.stats.ap += 35.0;
            unit.stats.attack_speed += 0.15;
        }

        // Tank / utility
        "WarmogsArmor" => {
            add_hp_flat(unit, 500.0);
            add_bonus_hp_pct(unit, 0.18);
        }
        "GargoyleStoneplate" => {
            unit.stats.armor += 30.0;
            unit.stats.magic_resist += 30.0;
            add_hp_flat(unit, 100.0);
        }
        "SunfireCape" => {
            unit.stats.armor += 20.0;
            add_hp_flat(unit, 150.0);
            add_bonus_hp_pct(unit, 0.08);
        }
        "DragonsClaw" => {
            unit.stats.magic_resist += 75.0;
            add_bonus_hp_pct(unit, 0.09);
        }
        "BrambleVest" => {
            unit.stats.armor += 65.0;
            add_bonus_hp_pct(unit, 0.09);
        }
        "SpiritVisage" => {
            add_hp_flat(unit, 300.0);
        }
        "SteadfastHeart" => {
            unit.stats.armor += 20.0;
            unit.stats.crit_chance += 0.20;
            add_hp_flat(unit, 250.0);
        }
        "ProtectorsVow" => {
            unit.stats.armor += 25.0;
            unit.stats.magic_resist += 25.0;
        }
        "Evenshroud" => {
            add_hp_flat(unit, 250.0);
            unit.stats.magic_resist += 20.0;
        }
        "Quicksilver" => {
            unit.stats.attack_speed += 0.15;
            unit.stats.crit_chance += 0.20;
            unit.stats.magic_resist += 20.0;
        }
        "Crownguard" => {
            unit.stats.ap += 20.0;
            unit.stats.armor += 20.0;
            add_hp_flat(unit, 100.0);
        }
        "HandOfJustice" => {
            unit.stats.crit_chance += 0.20;
        }
        "AdaptiveHelm" => {
            unit.stats.magic_resist += 20.0;
        }
        "StrikersFlail" => {
            unit.stats.attack_speed += 0.10;
            unit.stats.crit_chance += 0.20;
            add_hp_flat(unit, 150.0);
        }

        // Common artifacts
        "Artifact_StatikkShiv" => {
            unit.stats.ap += 15.0;
            unit.stats.attack_speed += 0.50;
        }
        "Artifact_WitsEnd" => {
            add_hp_flat(unit, 400.0);
            unit.stats.armor += 20.0;
            unit.stats.magic_resist += 20.0;
            unit.stats.attack_speed += 0.25;
        }
        "Artifact_DeathfireGrasp" => {
            unit.stats.ap += 50.0;
        }
        _ => {}
    }

    unit.stats.attack_speed = unit.stats.attack_speed.min(as_cap);
}

fn refresh_or_apply_burn(
    engine: &mut CombatEngine,
    attacker_idx: Option<UnitId>,
    target_idx: UnitId,
    hp_pct_per_sec: f64,
    duration: f64,
    source: &str,
) {
    if !engine.units[target_idx].is_alive {
        return;
    }

    let damage_per_tick = engine.units[target_idx].stats.max_hp * hp_pct_per_sec;
    let target = &mut engine.units[target_idx];

    for dot in &mut target.dot_effects {
        if dot.source_name == source {
            dot.damage_per_tick = damage_per_tick;
            dot.remaining_duration = duration;
            dot.tick_interval = 1.0;
            dot.damage_type = DamageType::True;
            return;
        }
    }

    target.dot_effects.push(DotEffect {
        source_unit: attacker_idx,
        damage_per_tick,
        tick_interval: 1.0,
        remaining_duration: duration,
        damage_type: DamageType::True,
        source_name: source.to_string(),
        time_since_last_tick: 0.0,
    });
}

pub fn on_combat_start(engine: &mut CombatEngine, unit_idx: UnitId) {
    if !engine.units[unit_idx].is_alive {
        return;
    }

    if unit_has_item(&engine.units[unit_idx], "BlueBuff") {
        let max_mana = engine.units[unit_idx].stats.max_mana;
        engine.units[unit_idx].stats.mana =
            (engine.units[unit_idx].stats.mana + 15.0).min(max_mana);
    }
    if unit_has_item(&engine.units[unit_idx], "Quicksilver") {
        let until = engine.time + 18.0;
        set_item_data(
            &mut engine.units[unit_idx],
            "Quicksilver",
            "immune_until",
            until,
        );
    }
    if unit_has_item(&engine.units[unit_idx], "Evenshroud") {
        engine.units[unit_idx].stats.armor += 25.0;
        engine.units[unit_idx].stats.magic_resist += 25.0;
        set_item_data(
            &mut engine.units[unit_idx],
            "Evenshroud",
            "bonus_start",
            engine.time,
        );
        set_item_data(
            &mut engine.units[unit_idx],
            "Evenshroud",
            "bonus_expired",
            0.0,
        );
    }
    if unit_has_item(&engine.units[unit_idx], "Crownguard") {
        let shield = engine.units[unit_idx].stats.max_hp * 0.20;
        engine.units[unit_idx].stats.shield += shield;
    }
    if unit_has_item(&engine.units[unit_idx], "HandOfJustice") {
        let roll = engine.rng.randrange_usize_stop(2);
        if roll == 0 {
            engine.units[unit_idx].stats.damage_amp += 0.15;
            set_item_data(&mut engine.units[unit_idx], "HandOfJustice", "mode", 0.0);
        } else {
            engine.units[unit_idx].stats.omnivamp += 0.15;
            set_item_data(&mut engine.units[unit_idx], "HandOfJustice", "mode", 1.0);
        }
    }
}

pub fn passive_tick(engine: &mut CombatEngine, unit_idx: UnitId) {
    if !engine.units[unit_idx].is_alive {
        return;
    }

    if unit_has_item(&engine.units[unit_idx], "GuinsoosRageblade") {
        let last = get_item_data(&engine.units[unit_idx], "Guinsoos", "last_tick", -1.0);
        if engine.time - last >= 1.0 {
            let stacks = get_item_data(&engine.units[unit_idx], "Guinsoos", "stacks", 0.0);
            if stacks < 20.0 {
                engine.units[unit_idx].stats.attack_speed += 0.07;
                set_item_data(
                    &mut engine.units[unit_idx],
                    "Guinsoos",
                    "stacks",
                    stacks + 1.0,
                );
            }
            set_item_data(
                &mut engine.units[unit_idx],
                "Guinsoos",
                "last_tick",
                engine.time,
            );
        }
    }

    if unit_has_item(&engine.units[unit_idx], "ArchangelsStaff") {
        let last = get_item_data(&engine.units[unit_idx], "Archangels", "last_tick", -5.0);
        if engine.time - last >= 5.0 {
            let ap_gain = if engine.units[unit_idx].base_stats.ap > 0.0 {
                engine.units[unit_idx].base_stats.ap * 0.20
            } else {
                engine.units[unit_idx].stats.ap * 0.20
            };
            engine.units[unit_idx].stats.ap += ap_gain;
            set_item_data(
                &mut engine.units[unit_idx],
                "Archangels",
                "last_tick",
                engine.time,
            );
        }
    }

    if unit_has_item(&engine.units[unit_idx], "DragonsClaw") {
        let last = get_item_data(&engine.units[unit_idx], "DragonsClaw", "last_tick", -2.0);
        if engine.time - last >= 2.0 {
            let heal = engine.units[unit_idx].stats.max_hp * 0.025;
            damage::heal_unit(&mut engine.units[unit_idx], heal);
            set_item_data(
                &mut engine.units[unit_idx],
                "DragonsClaw",
                "last_tick",
                engine.time,
            );
        }
    }

    if unit_has_item(&engine.units[unit_idx], "SpiritVisage") {
        let last = get_item_data(&engine.units[unit_idx], "SpiritVisage", "last_tick", -1.0);
        if engine.time - last >= 1.0 {
            let missing = engine.units[unit_idx].stats.max_hp - engine.units[unit_idx].stats.hp;
            damage::heal_unit(&mut engine.units[unit_idx], missing * 0.025);
            set_item_data(
                &mut engine.units[unit_idx],
                "SpiritVisage",
                "last_tick",
                engine.time,
            );
        }
    }

    if unit_has_item(&engine.units[unit_idx], "Quicksilver") {
        let last = get_item_data(&engine.units[unit_idx], "Quicksilver", "last_as_tick", -1.0);
        if engine.time - last >= 1.0 {
            engine.units[unit_idx].stats.attack_speed += 0.03;
            set_item_data(
                &mut engine.units[unit_idx],
                "Quicksilver",
                "last_as_tick",
                engine.time,
            );
        }
    }

    if unit_has_item(&engine.units[unit_idx], "SunfireCape") {
        let last = get_item_data(&engine.units[unit_idx], "SunfireCape", "last_tick", -2.0);
        if engine.time - last >= 2.0 {
            set_item_data(
                &mut engine.units[unit_idx],
                "SunfireCape",
                "last_tick",
                engine.time,
            );
            let team = engine.units[unit_idx].team;
            let center = engine.units[unit_idx].position;
            let mut nearest: Option<(UnitId, i32)> = None;
            for (idx, enemy) in engine.units.iter().enumerate() {
                if !enemy.is_alive || enemy.team == team {
                    continue;
                }
                let dist = hex_grid::hex_distance(center, enemy.position);
                if dist <= 2 {
                    match nearest {
                        None => nearest = Some((idx, dist)),
                        Some((_, best_dist)) if dist < best_dist => nearest = Some((idx, dist)),
                        _ => {}
                    }
                }
            }
            if let Some((target_idx, _)) = nearest {
                refresh_or_apply_burn(
                    engine,
                    Some(unit_idx),
                    target_idx,
                    0.01,
                    10.0,
                    "sunfire_cape",
                );
            }
        }
    }

    if unit_has_item(&engine.units[unit_idx], "IonicSpark") {
        let last = get_item_data(&engine.units[unit_idx], "IonicSpark", "last_tick", -1.0);
        if engine.time - last >= 1.0 {
            set_item_data(
                &mut engine.units[unit_idx],
                "IonicSpark",
                "last_tick",
                engine.time,
            );
            let team = engine.units[unit_idx].team;
            let center = engine.units[unit_idx].position;
            let targets: Vec<UnitId> = engine
                .units
                .iter()
                .enumerate()
                .filter(|(_, u)| {
                    u.is_alive && u.team != team && hex_grid::hex_distance(center, u.position) <= 2
                })
                .map(|(idx, _)| idx)
                .collect();
            for target_idx in targets {
                damage::apply_shred(
                    &mut engine.units[target_idx],
                    0.30,
                    5.0,
                    engine.time,
                    "ionic_spark",
                );
            }
        }
    }

    if unit_has_item(&engine.units[unit_idx], "Evenshroud") {
        if get_item_data(&engine.units[unit_idx], "Evenshroud", "bonus_expired", 0.0) == 0.0 {
            let started = get_item_data(
                &engine.units[unit_idx],
                "Evenshroud",
                "bonus_start",
                engine.time,
            );
            if engine.time - started >= 15.0 {
                engine.units[unit_idx].stats.armor -= 25.0;
                engine.units[unit_idx].stats.magic_resist -= 25.0;
                set_item_data(
                    &mut engine.units[unit_idx],
                    "Evenshroud",
                    "bonus_expired",
                    1.0,
                );
            }
        }

        let last = get_item_data(&engine.units[unit_idx], "Evenshroud", "last_tick", -1.0);
        if engine.time - last >= 1.0 {
            set_item_data(
                &mut engine.units[unit_idx],
                "Evenshroud",
                "last_tick",
                engine.time,
            );
            let team = engine.units[unit_idx].team;
            let center = engine.units[unit_idx].position;
            let targets: Vec<UnitId> = engine
                .units
                .iter()
                .enumerate()
                .filter(|(_, u)| {
                    u.is_alive && u.team != team && hex_grid::hex_distance(center, u.position) <= 2
                })
                .map(|(idx, _)| idx)
                .collect();
            for target_idx in targets {
                damage::apply_sunder(
                    &mut engine.units[target_idx],
                    0.30,
                    5.0,
                    engine.time,
                    "evenshroud",
                );
            }
        }
    }
}

pub fn on_attack_hit(
    engine: &mut CombatEngine,
    attacker_idx: UnitId,
    target_idx: UnitId,
    did_crit: bool,
    hp_damage: f64,
) {
    if !engine.units[attacker_idx].is_alive || hp_damage <= 0.0 {
        return;
    }

    if unit_has_item(&engine.units[attacker_idx], "SpearOfShojin") {
        let max_mana = engine.units[attacker_idx].stats.max_mana;
        engine.units[attacker_idx].stats.mana =
            (engine.units[attacker_idx].stats.mana + 5.0).min(max_mana);
    }

    if unit_has_item(&engine.units[attacker_idx], "NashorsTooth") {
        let gain = if did_crit { 4.0 } else { 2.0 };
        let max_mana = engine.units[attacker_idx].stats.max_mana;
        engine.units[attacker_idx].stats.mana =
            (engine.units[attacker_idx].stats.mana + gain).min(max_mana);
    }

    if unit_has_item(&engine.units[attacker_idx], "LastWhisper") {
        damage::apply_sunder(
            &mut engine.units[target_idx],
            0.30,
            3.0,
            engine.time,
            "last_whisper",
        );
    }

    if unit_has_item(&engine.units[attacker_idx], "VoidStaff") {
        damage::apply_shred(
            &mut engine.units[target_idx],
            0.30,
            5.0,
            engine.time,
            "void_staff",
        );
    }

    if unit_has_item(&engine.units[attacker_idx], "RedBuff") {
        refresh_or_apply_burn(
            engine,
            Some(attacker_idx),
            target_idx,
            0.01,
            5.0,
            "red_buff",
        );
    }

    if unit_has_item(&engine.units[attacker_idx], "TitansResolve") {
        let stacks = get_item_data(&engine.units[attacker_idx], "TitansResolve", "stacks", 0.0);
        if stacks < 25.0 {
            let new_stacks = stacks + 1.0;
            set_item_data(
                &mut engine.units[attacker_idx],
                "TitansResolve",
                "stacks",
                new_stacks,
            );
            let base_ad = engine.units[attacker_idx].base_stats.ad;
            engine.units[attacker_idx].stats.ad += base_ad * 0.02;
            engine.units[attacker_idx].stats.ap += 1.0;
            if new_stacks >= 25.0 {
                engine.units[attacker_idx].stats.damage_amp += 0.10;
                set_item_data(
                    &mut engine.units[attacker_idx],
                    "TitansResolve",
                    "cc_immune",
                    1.0,
                );
            }
        }
    }

    if unit_has_item(&engine.units[attacker_idx], "KrakensFury") {
        let stacks = get_item_data(&engine.units[attacker_idx], "KrakensFury", "stacks", 0.0);
        if stacks < 15.0 {
            let new_stacks = stacks + 1.0;
            set_item_data(
                &mut engine.units[attacker_idx],
                "KrakensFury",
                "stacks",
                new_stacks,
            );
            let base_ad = engine.units[attacker_idx].base_stats.ad;
            engine.units[attacker_idx].stats.ad += base_ad * 0.035;
            if new_stacks >= 15.0 {
                engine.units[attacker_idx].stats.attack_speed += 0.15;
            }
        }
    }

    if unit_has_item(&engine.units[attacker_idx], "StrikersFlail") && did_crit {
        let stacks = get_item_data(&engine.units[attacker_idx], "StrikersFlail", "stacks", 0.0);
        if stacks < 4.0 {
            set_item_data(
                &mut engine.units[attacker_idx],
                "StrikersFlail",
                "stacks",
                stacks + 1.0,
            );
            engine.units[attacker_idx].stats.damage_amp += 0.05;
        }
    }

    if unit_has_item(&engine.units[attacker_idx], "Artifact_StatikkShiv") {
        let count = get_item_data(
            &engine.units[attacker_idx],
            "Artifact_StatikkShiv",
            "attacks",
            0.0,
        ) + 1.0;
        if count >= 3.0 {
            set_item_data(
                &mut engine.units[attacker_idx],
                "Artifact_StatikkShiv",
                "attacks",
                0.0,
            );

            let team = engine.units[attacker_idx].team;
            let center = engine.units[attacker_idx].position;
            let mut targets: Vec<(UnitId, i32)> = engine
                .units
                .iter()
                .enumerate()
                .filter(|(_, u)| u.is_alive && u.team != team)
                .map(|(idx, u)| (idx, hex_grid::hex_distance(center, u.position)))
                .collect();
            targets.sort_by_key(|(_, dist)| *dist);
            let target_ids: Vec<UnitId> = targets.into_iter().take(4).map(|(idx, _)| idx).collect();
            let base = 30.0 + engine.units[attacker_idx].stats.ap * 0.40;
            for enemy_idx in target_ids {
                let _ = engine.deal_damage(
                    Some(attacker_idx),
                    enemy_idx,
                    base,
                    DamageType::Magic,
                    false,
                    false,
                    "artifact_statikk_shiv",
                );
            }
        } else {
            set_item_data(
                &mut engine.units[attacker_idx],
                "Artifact_StatikkShiv",
                "attacks",
                count,
            );
        }
    }
}

pub fn on_damage_dealt(
    engine: &mut CombatEngine,
    attacker_idx: UnitId,
    target_idx: UnitId,
    hp_damage: f64,
    _damage_type: DamageType,
    is_ability: bool,
) {
    if hp_damage <= 0.0 || !engine.units[attacker_idx].is_alive {
        return;
    }

    if unit_has_item(&engine.units[attacker_idx], "HextechGunblade") {
        let heal_amount = hp_damage * 0.20;
        let team = engine.units[attacker_idx].team;
        let mut lowest_idx: Option<UnitId> = None;
        let mut lowest_hp_pct = 2.0;
        for (idx, ally) in engine.units.iter().enumerate() {
            if !ally.is_alive || ally.team != team {
                continue;
            }
            let hp_pct = if ally.stats.max_hp > 0.0 {
                ally.stats.hp / ally.stats.max_hp
            } else {
                1.0
            };
            if hp_pct < lowest_hp_pct {
                lowest_hp_pct = hp_pct;
                lowest_idx = Some(idx);
            }
        }
        if let Some(idx) = lowest_idx {
            damage::heal_unit(&mut engine.units[idx], heal_amount);
        }
    }

    if unit_has_item(&engine.units[attacker_idx], "Morellonomicon")
        || (is_ability && unit_has_item(&engine.units[attacker_idx], "RedBuff"))
    {
        refresh_or_apply_burn(
            engine,
            Some(attacker_idx),
            target_idx,
            0.01,
            10.0,
            "morello_burn",
        );
    }
}

pub fn on_damage_taken(
    engine: &mut CombatEngine,
    defender_idx: UnitId,
    _attacker_idx: Option<UnitId>,
    hp_damage: f64,
    _damage_type: DamageType,
) {
    if hp_damage <= 0.0 || !engine.units[defender_idx].is_alive {
        return;
    }

    if unit_has_item(&engine.units[defender_idx], "TitansResolve") {
        let stacks = get_item_data(&engine.units[defender_idx], "TitansResolve", "stacks", 0.0);
        if stacks < 25.0 {
            let new_stacks = stacks + 1.0;
            set_item_data(
                &mut engine.units[defender_idx],
                "TitansResolve",
                "stacks",
                new_stacks,
            );
            let base_ad = engine.units[defender_idx].base_stats.ad;
            engine.units[defender_idx].stats.ad += base_ad * 0.02;
            engine.units[defender_idx].stats.ap += 1.0;
            if new_stacks >= 25.0 {
                engine.units[defender_idx].stats.damage_amp += 0.10;
                set_item_data(
                    &mut engine.units[defender_idx],
                    "TitansResolve",
                    "cc_immune",
                    1.0,
                );
            }
        }
    }

    if unit_has_item(&engine.units[defender_idx], "BrambleVest") {
        let last = get_item_data(
            &engine.units[defender_idx],
            "BrambleVest",
            "last_proc",
            -2.0,
        );
        if engine.time - last >= 2.0 {
            set_item_data(
                &mut engine.units[defender_idx],
                "BrambleVest",
                "last_proc",
                engine.time,
            );
            let team = engine.units[defender_idx].team;
            let center = engine.units[defender_idx].position;
            let targets: Vec<UnitId> = engine
                .units
                .iter()
                .enumerate()
                .filter(|(_, u)| {
                    u.is_alive && u.team != team && hex_grid::hex_distance(center, u.position) <= 1
                })
                .map(|(idx, _)| idx)
                .collect();
            for idx in targets {
                let _ = engine.deal_damage(
                    Some(defender_idx),
                    idx,
                    100.0,
                    DamageType::Magic,
                    false,
                    false,
                    "bramble_vest",
                );
            }
        }
    }

    if unit_has_item(&engine.units[defender_idx], "ProtectorsVow") {
        let triggered = get_item_data(
            &engine.units[defender_idx],
            "ProtectorsVow",
            "triggered",
            0.0,
        );
        let hp_pct = if engine.units[defender_idx].stats.max_hp > 0.0 {
            engine.units[defender_idx].stats.hp / engine.units[defender_idx].stats.max_hp
        } else {
            1.0
        };
        if triggered < 0.5 && hp_pct <= 0.40 {
            set_item_data(
                &mut engine.units[defender_idx],
                "ProtectorsVow",
                "triggered",
                1.0,
            );
            let max_mana = engine.units[defender_idx].stats.max_mana;
            engine.units[defender_idx].stats.mana =
                (engine.units[defender_idx].stats.mana + 15.0).min(max_mana);
            engine.units[defender_idx].stats.shield +=
                engine.units[defender_idx].stats.max_hp * 0.20;
        }
    }

    if unit_has_item(&engine.units[defender_idx], "Bloodthirster") {
        let triggered = get_item_data(
            &engine.units[defender_idx],
            "Bloodthirster",
            "triggered",
            0.0,
        );
        let hp_pct = if engine.units[defender_idx].stats.max_hp > 0.0 {
            engine.units[defender_idx].stats.hp / engine.units[defender_idx].stats.max_hp
        } else {
            1.0
        };
        if triggered < 0.5 && hp_pct <= 0.40 {
            set_item_data(
                &mut engine.units[defender_idx],
                "Bloodthirster",
                "triggered",
                1.0,
            );
            engine.units[defender_idx].stats.shield +=
                engine.units[defender_idx].stats.max_hp * 0.25;
        }
    }

    if unit_has_item(&engine.units[defender_idx], "SteadfastHeart") {
        let above = get_item_data(
            &engine.units[defender_idx],
            "SteadfastHeart",
            "above50",
            1.0,
        );
        let hp_pct = if engine.units[defender_idx].stats.max_hp > 0.0 {
            engine.units[defender_idx].stats.hp / engine.units[defender_idx].stats.max_hp
        } else {
            1.0
        };
        if above > 0.5 && hp_pct < 0.5 {
            engine.units[defender_idx].stats.damage_reduction -= 0.08;
            set_item_data(
                &mut engine.units[defender_idx],
                "SteadfastHeart",
                "above50",
                0.0,
            );
        } else if above <= 0.5 && hp_pct >= 0.5 {
            engine.units[defender_idx].stats.damage_reduction += 0.08;
            set_item_data(
                &mut engine.units[defender_idx],
                "SteadfastHeart",
                "above50",
                1.0,
            );
        }
    }
}

pub fn on_ability_cast(engine: &mut CombatEngine, caster_idx: UnitId) {
    if !engine.units[caster_idx].is_alive {
        return;
    }

    if unit_has_item(&engine.units[caster_idx], "VoidStaff") {
        if let Some(target_idx) = engine.units[caster_idx].target_idx {
            if engine.units[target_idx].is_alive {
                damage::apply_shred(
                    &mut engine.units[target_idx],
                    0.30,
                    5.0,
                    engine.time,
                    "void_staff_ability",
                );
            }
        }
    }

    // Ionic Spark reactive damage: enemy holders within 2 hexes punish ability casts.
    let caster_team = engine.units[caster_idx].team;
    let caster_pos = engine.units[caster_idx].position;
    let caster_max_mana = engine.units[caster_idx].stats.max_mana;
    let spark_holders: Vec<UnitId> = engine
        .units
        .iter()
        .enumerate()
        .filter(|(_, u)| {
            u.is_alive
                && u.team != caster_team
                && unit_has_item(u, "IonicSpark")
                && hex_grid::hex_distance(u.position, caster_pos) <= 2
        })
        .map(|(idx, _)| idx)
        .collect();

    for enemy_idx in spark_holders {
        let _ = engine.deal_damage(
            Some(enemy_idx),
            caster_idx,
            caster_max_mana * 1.50,
            DamageType::Magic,
            false,
            false,
            "ionic_spark_reactive",
        );
    }

    if unit_has_item(&engine.units[caster_idx], "Artifact_Dawncore") {
        engine.units[caster_idx].stats.max_mana =
            (engine.units[caster_idx].stats.max_mana * 0.90).max(10.0);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::unit::CombatStats;

    fn dummy_unit(name: &str, team: i32) -> Unit {
        let mut stats = CombatStats::default();
        stats.hp = 1000.0;
        stats.max_hp = 1000.0;
        Unit::new(
            name.to_string(),
            format!("TFT16_{}", name),
            1,
            1,
            "ADCarry".to_string(),
            stats.clone(),
            stats,
            (0, 0),
            team,
        )
    }

    #[test]
    fn test_resolve_item_name_radiant() {
        assert_eq!(
            resolve_item_name("RadiantJeweledGauntlet").as_ref(),
            "JeweledGauntlet"
        );
    }

    #[test]
    fn test_apply_item_stats_spear_of_shojin() {
        let mut unit = dummy_unit("Tester", 0);
        let base_ad = unit.base_stats.ad;
        apply_item_stats(&mut unit, "SpearOfShojin", 5.0);
        assert!((unit.stats.ad - (base_ad + base_ad * 0.15)).abs() < 1e-9);
        assert!((unit.stats.ap - 15.0).abs() < 1e-9);
    }
}
