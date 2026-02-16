use crate::abilities;
use crate::damage;
/// TFT Combat Engine - core simulation loop.
use crate::data::{get_f64, get_i64, get_str, star_val, CombatData};
use crate::hex_grid;
use crate::items;
use crate::python_rng::PyRng;
use crate::targeting;
use crate::types::*;
use crate::unit::*;

use std::collections::{HashMap, HashSet};

const TICK_RATE: f64 = 0.033; // ~30 FPS
const MAX_COMBAT_TIME: f64 = 60.0;
const AS_CAP: f64 = 5.0;

/// Star-level scaling multipliers (matching Python engine).
const HP_SCALING: [f64; 4] = [1.0, 1.0, 1.8, 3.24];
const AD_SCALING: [f64; 4] = [1.0, 1.0, 1.5, 2.25];

/// The main combat engine.
pub struct CombatEngine {
    pub units: Vec<Unit>,
    pub time: f64,
    pub rng: PyRng,
    pub combat_data: CombatData,
    pub alive_dirty: bool,

    // Combat-scope trait counters used for parity/debug visibility.
    bilgewater_count_by_team: [i32; 2],
    shadow_isles_count_by_team: [i32; 2],
    bilgewater_serpents_by_team: [i32; 2],
    shadow_isles_souls_by_team: [i32; 2],
    debug_takedowns: Vec<TakedownAttribution>,

    // Cached alive indices per team
    alive_team0: Vec<UnitId>,
    alive_team1: Vec<UnitId>,
    process_order: Vec<UnitId>,

    // Occupied hexes cache
    occupied_hexes: HashSet<HexPos>,
}

impl CombatEngine {
    /// Create a new engine with loaded combat data.
    pub fn new(combat_data: CombatData) -> Self {
        Self {
            units: Vec::new(),
            time: 0.0,
            rng: PyRng::seed_from_u64(0),
            combat_data,
            alive_dirty: false,
            bilgewater_count_by_team: [0, 0],
            shadow_isles_count_by_team: [0, 0],
            bilgewater_serpents_by_team: [0, 0],
            shadow_isles_souls_by_team: [0, 0],
            debug_takedowns: Vec::new(),
            alive_team0: Vec::new(),
            alive_team1: Vec::new(),
            process_order: Vec::new(),
            occupied_hexes: HashSet::new(),
        }
    }

    /// Create a unit from combat data.
    pub fn create_unit(
        &self,
        api_name: &str,
        star_level: i32,
        position: HexPos,
        team: i32,
        items: &[String],
        traits: &[String],
    ) -> Option<Unit> {
        let champ_data = self.combat_data.get_champion(api_name)?;

        let stats_data = champ_data.get("stats").unwrap_or(&serde_json::Value::Null);
        let timing = champ_data.get("timing").unwrap_or(&serde_json::Value::Null);

        let hp_mult = HP_SCALING.get(star_level as usize).copied().unwrap_or(1.0);
        let ad_mult = AD_SCALING.get(star_level as usize).copied().unwrap_or(1.0);

        let base_hp = get_f64(stats_data, "hp", 500.0) * hp_mult;
        let base_ad = get_f64(stats_data, "ad", 50.0) * ad_mult;

        let base_stats = CombatStats {
            hp: base_hp,
            max_hp: base_hp,
            ad: base_ad,
            ap: 0.0,
            attack_speed: get_f64(stats_data, "attackSpeed", 0.7),
            armor: get_f64(stats_data, "armor", 20.0),
            magic_resist: get_f64(stats_data, "magicResist", 20.0),
            range: get_i64(stats_data, "range", 1) as i32,
            mana: get_f64(stats_data, "startMana", 0.0),
            max_mana: get_f64(stats_data, "mana", 100.0),
            crit_chance: get_f64(stats_data, "critChance", 0.25),
            crit_multiplier: get_f64(stats_data, "critMultiplier", 1.4),
            ..Default::default()
        };

        let name = get_str(champ_data, "name", api_name).trim().to_string();
        let role = get_str(champ_data, "role", "").to_string();
        let cost = get_i64(champ_data, "cost", 1) as i32;

        // Create ability from champion data
        let ability = self.create_ability(api_name, champ_data, star_level);

        let current_stats = base_stats.copy();
        let mut unit = Unit::new(
            name,
            api_name.to_string(),
            star_level,
            cost,
            role,
            current_stats,
            base_stats,
            position,
            team,
        );

        unit.attack_windup = get_f64(timing, "attackWindup", 0.3);
        let ms = get_i64(timing, "missileSpeed", 0);
        unit.missile_speed = if ms > 0 { Some(ms as i32) } else { None };

        // Set traits
        if traits.is_empty() {
            // Use traits from combat data if not provided
            if let Some(t) = champ_data.get("traits") {
                if let Some(arr) = t.as_array() {
                    unit.traits = arr
                        .iter()
                        .filter_map(|v| v.as_str().map(|s| s.to_string()))
                        .collect();
                }
            }
        } else {
            unit.traits = traits.to_vec();
        }

        unit.ability = ability;

        // Apply items
        for item_name in items {
            self.apply_item_stats(&mut unit, item_name);
        }

        // Pre-compute item flags
        unit.has_jeweled_gauntlet = unit
            .items
            .iter()
            .any(|i| items::resolve_item_name(i.name.as_str()).as_ref() == "JeweledGauntlet");
        unit.has_giant_slayer = unit
            .items
            .iter()
            .any(|i| items::resolve_item_name(i.name.as_str()).as_ref() == "GiantSlayer");

        Some(unit)
    }

    /// Create an ability definition from champion data.
    fn create_ability(
        &self,
        _api_name: &str,
        champ_data: &serde_json::Value,
        _star_level: i32,
    ) -> Option<Ability> {
        let ability_data = champ_data.get("ability")?;

        let name = get_str(ability_data, "name", "").to_string();
        if name.is_empty() {
            return None;
        }

        let variables = ability_data
            .get("variables")
            .unwrap_or(&serde_json::Value::Null);

        // Try to get base damage from common variable names
        let mut base_damage = [0.0f64; 4];
        for key in &[
            "Damage",
            "MagicDamage",
            "BaseDamage",
            "TotalDamage",
            "AbilityDamage",
        ] {
            if let Some(dmg_var) = variables.get(*key) {
                for star in 0..4 {
                    let val = star_val(dmg_var, star as i32, 0.0);
                    if val > 0.0 {
                        base_damage[star] = val;
                    }
                }
                if base_damage[1] > 0.0 {
                    break;
                }
            }
        }

        let cast_time = get_f64(ability_data, "castTime", 0.5);
        let _mana_cost = get_f64(ability_data, "manaCost", 0.0);
        let mut variable_map: HashMap<String, serde_json::Value> = HashMap::new();
        if let Some(obj) = variables.as_object() {
            for (key, value) in obj {
                variable_map.insert(key.clone(), value.clone());
            }
        }

        Some(Ability {
            name,
            ability_type: AbilityType::Damage, // Default; champion handlers override
            damage_type: DamageType::Magic,    // Most abilities are magic
            targeting: TargetingType::CurrentTarget,
            base_damage,
            ap_scaling: 1.0,
            ad_scaling: 0.0,
            cast_time,
            aoe_radius: 0,
            num_targets: 1,
            variables: variable_map,
        })
    }

    /// Apply item stats to a unit.
    fn apply_item_stats(&self, unit: &mut Unit, item_name: &str) {
        items::apply_item_stats(unit, item_name, AS_CAP);
    }

    fn count_traits(&self, team_indices: &[UnitId]) -> HashMap<String, i32> {
        let mut counts: HashMap<String, i32> = HashMap::new();
        for unit_idx in team_indices {
            let mut seen: HashSet<&str> = HashSet::new();
            for trait_name in &self.units[*unit_idx].traits {
                let trait_key = trait_name.as_str();
                if seen.insert(trait_key) {
                    *counts.entry(trait_name.clone()).or_insert(0) += 1;
                }
            }
        }
        counts
    }

    fn apply_trait_effects(&mut self) {
        let team0_indices: Vec<UnitId> = self
            .units
            .iter()
            .enumerate()
            .filter(|(_, u)| u.team == 0)
            .map(|(idx, _)| idx)
            .collect();
        let team1_indices: Vec<UnitId> = self
            .units
            .iter()
            .enumerate()
            .filter(|(_, u)| u.team == 1)
            .map(|(idx, _)| idx)
            .collect();

        let team0_traits = self.count_traits(&team0_indices);
        let team1_traits = self.count_traits(&team1_indices);

        // Cache counts for takedown-triggered trait currencies (parity/debug).
        self.bilgewater_count_by_team[0] = *team0_traits.get("Bilgewater").unwrap_or(&0);
        self.bilgewater_count_by_team[1] = *team1_traits.get("Bilgewater").unwrap_or(&0);
        self.shadow_isles_count_by_team[0] = *team0_traits.get("Shadow Isles").unwrap_or(&0);
        self.shadow_isles_count_by_team[1] = *team1_traits.get("Shadow Isles").unwrap_or(&0);

        self.apply_stat_traits_for_team(&team0_indices, &team1_indices, &team0_traits);
        self.apply_stat_traits_for_team(&team1_indices, &team0_indices, &team1_traits);
        self.apply_pair_synergies(&team0_indices);
        self.apply_pair_synergies(&team1_indices);

        for unit in &mut self.units {
            unit.stats.attack_speed = unit.stats.attack_speed.min(AS_CAP);
        }
    }

    fn apply_stat_traits_for_team(
        &mut self,
        team_indices: &[UnitId],
        enemy_indices: &[UnitId],
        trait_counts: &HashMap<String, i32>,
    ) {
        let count = |trait_name: &str| -> i32 { *trait_counts.get(trait_name).unwrap_or(&0) };

        // -- Class traits --------------------------------------------------------
        if let Some((ally_ap, bonus_ap)) = if count("Arcanist") >= 6 {
            Some((40.0, 60.0))
        } else if count("Arcanist") >= 4 {
            Some((25.0, 40.0))
        } else if count("Arcanist") >= 2 {
            Some((18.0, 25.0))
        } else {
            None
        } {
            for unit_idx in team_indices {
                let unit = &mut self.units[*unit_idx];
                unit.stats.ap += ally_ap;
                if unit.traits.iter().any(|t| t == "Arcanist") {
                    unit.stats.ap += bonus_ap;
                }
            }
        }

        if let Some((teamwide, bonus)) = if count("Defender") >= 6 {
            Some((12.0, 80.0))
        } else if count("Defender") >= 4 {
            Some((12.0, 55.0))
        } else if count("Defender") >= 2 {
            Some((12.0, 30.0))
        } else {
            None
        } {
            for unit_idx in team_indices {
                let unit = &mut self.units[*unit_idx];
                unit.stats.armor += teamwide;
                unit.stats.magic_resist += teamwide;
                if unit.traits.iter().any(|t| t == "Defender") {
                    unit.stats.armor += bonus;
                    unit.stats.magic_resist += bonus;
                }
            }
        }

        if let Some((flat_hp, bonus_hp_pct)) = if count("Bruiser") >= 6 {
            Some((150.0, 0.65))
        } else if count("Bruiser") >= 4 {
            Some((150.0, 0.45))
        } else if count("Bruiser") >= 2 {
            Some((150.0, 0.25))
        } else {
            None
        } {
            for unit_idx in team_indices {
                let unit = &mut self.units[*unit_idx];
                unit.stats.max_hp += flat_hp;
                unit.stats.hp += flat_hp;
                if unit.traits.iter().any(|t| t == "Bruiser") {
                    let bonus = unit.base_stats.max_hp * bonus_hp_pct;
                    unit.stats.max_hp += bonus;
                    unit.stats.hp += bonus;
                }
            }
        }

        if let Some((ad_pct, omnivamp, amount_increase)) = if count("Slayer") >= 6 {
            Some((0.44, 0.20, 0.50))
        } else if count("Slayer") >= 4 {
            Some((0.33, 0.16, 0.50))
        } else if count("Slayer") >= 2 {
            Some((0.22, 0.10, 0.50))
        } else {
            None
        } {
            for unit_idx in team_indices {
                let unit = &mut self.units[*unit_idx];
                if unit.traits.iter().any(|t| t == "Slayer") {
                    unit.stats.ad += unit.base_stats.ad * ad_pct;
                    unit.stats.omnivamp += omnivamp;
                    unit.slayer_ad_increase = amount_increase;
                }
            }
        }

        if let Some((base_dr, increased_dr)) = if count("Juggernaut") >= 6 {
            Some((0.26, 0.36))
        } else if count("Juggernaut") >= 4 {
            Some((0.20, 0.30))
        } else if count("Juggernaut") >= 2 {
            Some((0.18, 0.25))
        } else {
            None
        } {
            for unit_idx in team_indices {
                let unit = &mut self.units[*unit_idx];
                if unit.traits.iter().any(|t| t == "Juggernaut") {
                    unit.stats.damage_reduction += base_dr;
                    unit.juggernaut_increased_dr = increased_dr;
                }
            }
        }

        if let Some((crit_chance, crit_dmg)) = if count("Vanquisher") >= 5 {
            Some((0.30, 0.30))
        } else if count("Vanquisher") >= 4 {
            Some((0.25, 0.25))
        } else if count("Vanquisher") >= 3 {
            Some((0.20, 0.20))
        } else if count("Vanquisher") >= 2 {
            Some((0.15, 0.15))
        } else {
            None
        } {
            for unit_idx in team_indices {
                let unit = &mut self.units[*unit_idx];
                if unit.traits.iter().any(|t| t == "Vanquisher") {
                    unit.stats.crit_chance += crit_chance;
                    unit.stats.crit_multiplier += crit_dmg;
                    unit.vanquisher_ability_crit = true;
                }
            }
        }

        if let Some((base_amp, per_hex)) = if count("Longshot") >= 5 {
            Some((0.32, 0.05))
        } else if count("Longshot") >= 4 {
            Some((0.28, 0.04))
        } else if count("Longshot") >= 3 {
            Some((0.24, 0.03))
        } else if count("Longshot") >= 2 {
            Some((0.18, 0.02))
        } else {
            None
        } {
            for unit_idx in team_indices {
                let unit = &mut self.units[*unit_idx];
                if unit.traits.iter().any(|t| t == "Longshot") {
                    unit.stats.damage_amp += base_amp;
                    unit.longshot_per_hex = per_hex;
                }
            }
        }

        if let Some((team_as, min_bonus_as, max_bonus_as)) = if count("Quickstriker") >= 5 {
            Some((0.15, 0.40, 0.80))
        } else if count("Quickstriker") >= 4 {
            Some((0.15, 0.30, 0.60))
        } else if count("Quickstriker") >= 3 {
            Some((0.15, 0.20, 0.45))
        } else if count("Quickstriker") >= 2 {
            Some((0.15, 0.10, 0.30))
        } else {
            None
        } {
            for unit_idx in team_indices {
                let unit = &mut self.units[*unit_idx];
                unit.stats.attack_speed += team_as;
                if unit.traits.iter().any(|t| t == "Quickstriker") {
                    unit.quickstriker_min_as = min_bonus_as;
                    unit.quickstriker_max_as = max_bonus_as;
                }
            }
        }

        if let Some((ad_pct, bonus_damage, interval)) = if count("Gunslinger") >= 4 {
            Some((0.40, 200.0, 4))
        } else if count("Gunslinger") >= 2 {
            Some((0.22, 100.0, 4))
        } else {
            None
        } {
            for unit_idx in team_indices {
                let unit = &mut self.units[*unit_idx];
                if unit.traits.iter().any(|t| t == "Gunslinger") {
                    unit.stats.ad += unit.base_stats.ad * ad_pct;
                    unit.gunslinger_bonus_damage = bonus_damage;
                    unit.gunslinger_attack_interval = interval;
                    unit.gunslinger_attack_counter = 0;
                }
            }
        }

        if let Some((shield_pct, first_threshold, second_threshold)) = if count("Warden") >= 5 {
            Some((0.33, 0.75, 0.25))
        } else if count("Warden") >= 4 {
            Some((0.26, 0.75, 0.25))
        } else if count("Warden") >= 3 {
            Some((0.20, 0.75, 0.25))
        } else if count("Warden") >= 2 {
            Some((0.16, 0.75, 0.25))
        } else {
            None
        } {
            for unit_idx in team_indices {
                let unit = &mut self.units[*unit_idx];
                if unit.traits.iter().any(|t| t == "Warden") {
                    unit.warden_shield_percent = shield_pct;
                    unit.warden_first_threshold = first_threshold;
                    unit.warden_second_threshold = second_threshold;
                    unit.warden_first_triggered = false;
                    unit.warden_second_triggered = false;
                }
            }
        }

        if let Some((damage_amp, damage_reduction)) = if count("Disruptor") >= 4 {
            Some((0.40, 0.10))
        } else if count("Disruptor") >= 2 {
            Some((0.18, 0.10))
        } else {
            None
        } {
            for unit_idx in team_indices {
                let unit = &mut self.units[*unit_idx];
                if unit.traits.iter().any(|t| t == "Disruptor") {
                    unit.stats.damage_amp += damage_amp;
                    unit.stats.damage_reduction += damage_reduction;
                }
            }
        }

        // -- Region traits -------------------------------------------------------
        if let Some(armor_mr) = if count("Demacia") >= 11 {
            Some(150.0)
        } else if count("Demacia") >= 5 {
            Some(35.0)
        } else if count("Demacia") >= 3 {
            Some(12.0)
        } else {
            None
        } {
            for unit_idx in team_indices {
                let unit = &mut self.units[*unit_idx];
                if unit.traits.iter().any(|t| t == "Demacia") {
                    unit.stats.armor += armor_mr;
                    unit.stats.magic_resist += armor_mr;
                }
            }
        }

        if let Some(bonus_as) = if count("Void") >= 9 {
            Some(0.40)
        } else if count("Void") >= 6 {
            Some(0.33)
        } else if count("Void") >= 4 {
            Some(0.18)
        } else if count("Void") >= 2 {
            Some(0.08)
        } else {
            None
        } {
            for unit_idx in team_indices {
                let unit = &mut self.units[*unit_idx];
                if unit.traits.iter().any(|t| t == "Void") {
                    unit.stats.attack_speed += bonus_as;
                }
            }
        }

        if let Some((hp_pct, heal_per_sec, armor_mr)) = if count("Shurima") >= 3 {
            Some((0.20, 20.0, 50.0))
        } else if count("Shurima") >= 2 {
            Some((0.20, 20.0, 0.0))
        } else {
            None
        } {
            for unit_idx in team_indices {
                let unit = &mut self.units[*unit_idx];
                if unit.traits.iter().any(|t| t == "Shurima") {
                    let bonus_hp = unit.base_stats.max_hp * hp_pct;
                    unit.stats.max_hp += bonus_hp;
                    unit.stats.hp += bonus_hp;
                    unit.shurima_heal_per_sec = heal_per_sec;
                    if armor_mr > 0.0 {
                        unit.stats.armor += armor_mr;
                        unit.stats.magic_resist += armor_mr;
                    }
                }
            }
        }

        if count("Yordle") >= 2 {
            for unit_idx in team_indices {
                let unit = &mut self.units[*unit_idx];
                if unit.traits.iter().any(|t| t == "Yordle") {
                    unit.stats.attack_speed += 0.05;
                    unit.stats.max_hp += 40.0;
                    unit.stats.hp += 40.0;
                }
            }
        }

        if let Some((hp_per_pair, heal)) = if count("Ixtal") >= 5 {
            Some((250.0, 2.0))
        } else {
            None
        } {
            let pairs = (count("Ixtal") / 2) as f64;
            for unit_idx in team_indices {
                let unit = &mut self.units[*unit_idx];
                if unit.traits.iter().any(|t| t == "Ixtal") {
                    let bonus_hp = hp_per_pair * pairs;
                    unit.stats.max_hp += bonus_hp;
                    unit.stats.hp += bonus_hp;
                    unit.ixtal_heal_per_sec = heal;
                }
            }
        }

        if let Some((shimmer_as, shimmer_dr, shimmer_duration, initial_delay, max_hp_heal)) =
            if count("Zaun") >= 5 {
                Some((0.90, 0.15, 4.0, 4.0, 0.30))
            } else if count("Zaun") >= 3 {
                Some((0.90, 0.15, 4.0, 4.0, 0.0))
            } else {
                None
            }
        {
            for unit_idx in team_indices {
                let unit = &mut self.units[*unit_idx];
                if unit.traits.iter().any(|t| t == "Zaun") {
                    unit.zaun_shimmer_as = shimmer_as;
                    unit.zaun_shimmer_durability = shimmer_dr;
                    unit.zaun_shimmer_duration = shimmer_duration;
                    unit.zaun_initial_delay = initial_delay;
                    unit.zaun_shimmer_active = false;
                    unit.zaun_shimmer_triggered = false;
                    unit.zaun_max_health_heal = max_hp_heal;
                }
            }
        }

        if let Some((resists, adap, hp_pct)) = if count("Ionia") >= 10 {
            Some((75.0, 100.0, 0.75))
        } else if count("Ionia") >= 7 {
            Some((40.0, 20.0, 0.35))
        } else if count("Ionia") >= 5 {
            Some((25.0, 15.0, 0.30))
        } else if count("Ionia") >= 3 {
            Some((15.0, 10.0, 0.25))
        } else {
            None
        } {
            for unit_idx in team_indices {
                let unit = &mut self.units[*unit_idx];
                if unit.traits.iter().any(|t| t == "Ionia") {
                    unit.stats.armor += resists;
                    unit.stats.magic_resist += resists;
                    unit.stats.ad += adap;
                    unit.stats.ap += adap;
                    let bonus_hp = unit.base_stats.max_hp * hp_pct;
                    unit.stats.max_hp += bonus_hp;
                    unit.stats.hp += bonus_hp;
                }
            }
        }

        // -- Unique / special traits --------------------------------------------
        if count("Darkin") >= 1 {
            for unit_idx in team_indices {
                let unit = &mut self.units[*unit_idx];
                if unit.traits.iter().any(|t| t == "Darkin") {
                    unit.stats.omnivamp += 0.15;
                }
            }
        }

        if count("World Ender") >= 1 {
            for unit_idx in team_indices {
                let unit = &mut self.units[*unit_idx];
                if unit.traits.iter().any(|t| t == "World Ender") {
                    unit.stats.damage_reduction += 0.20;
                    unit.stats.mana = (unit.stats.mana - 10.0).max(0.0);
                }
            }
        }

        if count("Dragonborn") >= 1 {
            for unit_idx in team_indices {
                let unit = &mut self.units[*unit_idx];
                if unit.traits.iter().any(|t| t == "Dragonborn") {
                    unit.dragonborn_protected = true;
                }
            }
        }

        if count("Soulbound") >= 1 {
            for unit_idx in team_indices {
                let unit = &mut self.units[*unit_idx];
                if unit.traits.iter().any(|t| t == "Soulbound") {
                    unit.stats.damage_amp += 0.07;
                }
            }
        }

        if count("Eternal") >= 1 {
            for unit_idx in team_indices {
                let unit = &mut self.units[*unit_idx];
                if unit.traits.iter().any(|t| t == "Eternal") {
                    unit.item_data
                        .insert("trait:eternal_damage_mult".to_string(), 3.25);
                }
            }
        }

        if count("The Boss") >= 1 {
            for unit_idx in team_indices {
                let unit = &mut self.units[*unit_idx];
                if unit.traits.iter().any(|t| t == "The Boss") {
                    unit.item_data
                        .insert("trait:boss_as_bonus".to_string(), 0.60);
                    unit.item_data
                        .insert("trait:boss_heal_percent".to_string(), 0.15);
                    unit.item_data
                        .insert("trait:boss_hp_threshold".to_string(), 0.45);
                    unit.item_data
                        .insert("trait:boss_transformed".to_string(), 0.0);
                }
            }
        }

        if count("Harvester") >= 1 {
            for enemy_idx in enemy_indices {
                self.units[*enemy_idx].stats.armor =
                    (self.units[*enemy_idx].stats.armor - 10.0).max(0.0);
                self.units[*enemy_idx].stats.magic_resist =
                    (self.units[*enemy_idx].stats.magic_resist - 10.0).max(0.0);
            }
            for unit_idx in team_indices {
                let unit = &mut self.units[*unit_idx];
                if unit.traits.iter().any(|t| t == "Harvester") {
                    unit.item_data
                        .insert("trait:harvester_mana_per_kill".to_string(), 10.0);
                }
            }
        }
    }

    fn apply_pair_synergies(&mut self, team_indices: &[UnitId]) {
        let mut by_api: HashMap<String, UnitId> = HashMap::new();
        for unit_idx in team_indices {
            by_api.insert(self.units[*unit_idx].api_name.clone(), *unit_idx);
        }

        if let (Some(&ambessa_idx), Some(&kindred_idx)) =
            (by_api.get("TFT16_Ambessa"), by_api.get("TFT16_Kindred"))
        {
            let ad_bonus = self.units[ambessa_idx].base_stats.ad * 0.40;
            self.units[ambessa_idx].stats.ad += ad_bonus;
            self.units[kindred_idx]
                .item_data
                .insert("trait:chosen_wolves_bonus_damage".to_string(), 0.30);
        }

        if let Some(&jarvan_idx) = by_api.get("TFT16_JarvanIV") {
            if by_api.contains_key("TFT16_Shyvana") {
                self.units[jarvan_idx]
                    .item_data
                    .insert("trait:dragonguard_shield_share".to_string(), 1.0);
            }
        }

        if let Some(&lucian_idx) = by_api.get("TFT16_Lucian") {
            if by_api.contains_key("TFT16_Vayne") {
                self.units[lucian_idx].stats.attack_speed += 0.50;
                self.units[lucian_idx]
                    .item_data
                    .insert("trait:sentinel_bonus_bolts".to_string(), 2.0);
                self.units[lucian_idx]
                    .item_data
                    .insert("trait:sentinel_bolt_effectiveness".to_string(), 0.25);
            }
        }

        if let Some(&singed_idx) = by_api.get("TFT16_Singed") {
            if by_api.contains_key("TFT16_Teemo") {
                self.units[singed_idx]
                    .item_data
                    .insert("trait:poison_pals_ap_gain".to_string(), 2.0);
                self.units[singed_idx]
                    .item_data
                    .insert("trait:poison_pals_damage_req".to_string(), 100.0);
            }
        }

        if let (Some(&ekko_idx), Some(&zilean_idx)) =
            (by_api.get("TFT16_Ekko"), by_api.get("TFT16_Zilean"))
        {
            self.units[ekko_idx]
                .item_data
                .insert("trait:timewinder_damage_share".to_string(), 0.10);
            self.units[zilean_idx]
                .item_data
                .insert("trait:timewinder_damage_share".to_string(), 0.10);
        }
    }

    /// Run a full combat simulation.
    pub fn run_combat(
        &mut self,
        team0_specs: Vec<UnitSpec>,
        team1_specs: Vec<UnitSpec>,
        _team0_augments: Option<Vec<String>>,
        _team1_augments: Option<Vec<String>>,
        seed: Option<u64>,
    ) -> CombatResult {
        // Reset state
        self.units.clear();
        self.time = 0.0;
        self.alive_dirty = false;
        self.bilgewater_count_by_team = [0, 0];
        self.shadow_isles_count_by_team = [0, 0];
        self.bilgewater_serpents_by_team = [0, 0];
        self.shadow_isles_souls_by_team = [0, 0];
        self.debug_takedowns.clear();

        // Set RNG seed
        if let Some(s) = seed {
            self.rng.reseed_from_u64(s);
        }

        // Create units from specs
        for spec in &team0_specs {
            if let Some(unit) = self.create_unit(
                &spec.api_name,
                spec.star_level,
                (spec.position[0], spec.position[1]),
                0,
                &spec.items,
                &spec.traits,
            ) {
                self.units.push(unit);
            }
        }

        for spec in &team1_specs {
            if let Some(unit) = self.create_unit(
                &spec.api_name,
                spec.star_level,
                (spec.position[0], spec.position[1]),
                1,
                &spec.items,
                &spec.traits,
            ) {
                self.units.push(unit);
            }
        }

        if self.units.is_empty() {
            return CombatResult::draw();
        }

        // Build initial alive lists and occupied hexes
        self.rebuild_alive_lists();
        self.rebuild_occupied_hexes();
        self.apply_trait_effects();
        for unit_idx in 0..self.units.len() {
            items::on_combat_start(self, unit_idx);
        }

        // Main combat loop
        while self.time < MAX_COMBAT_TIME {
            if self.alive_team0.is_empty() || self.alive_team1.is_empty() {
                break;
            }
            self.tick();
        }

        // Determine winner
        self.build_result()
    }

    /// Process one simulation tick.
    fn tick(&mut self) {
        self.time += TICK_RATE;

        // Refresh alive lists if dirty
        if self.alive_dirty {
            self.rebuild_alive_lists();
            self.rebuild_occupied_hexes();
            self.alive_dirty = false;
        }

        // Process DOT effects
        self.process_dots();

        // Expire sunder/shred debuffs
        self.expire_resist_reductions();

        // Process trait combat-time effects
        self.process_trait_combat_effects();

        // Process units in random order
        self.process_order.clear();
        self.process_order.extend_from_slice(&self.alive_team0);
        self.process_order.extend_from_slice(&self.alive_team1);

        // Fisher-Yates shuffle
        let len = self.process_order.len();
        for i in (1..len).rev() {
            let j = self.rng.randbelow(i + 1);
            self.process_order.swap(i, j);
        }

        let team0_indices = self.alive_team0.clone();
        let team1_indices = self.alive_team1.clone();

        for i in 0..len {
            let unit_idx = self.process_order[i];
            if !self.units[unit_idx].is_alive {
                continue;
            }
            items::passive_tick(self, unit_idx);

            let team = self.units[unit_idx].team;
            self.process_unit_tick(unit_idx, team, &team0_indices, &team1_indices);
        }
    }

    /// Process a single unit's tick.
    fn process_unit_tick(
        &mut self,
        unit_idx: UnitId,
        team: i32,
        team0_indices: &[UnitId],
        team1_indices: &[UnitId],
    ) {
        // Update buffs
        {
            let unit = &mut self.units[unit_idx];
            unit.buffs.retain_mut(|b| {
                b.duration -= TICK_RATE;
                b.duration > 0.0
            });
        }

        // Handle stun
        if self.units[unit_idx].stun_duration > 0.0 {
            self.units[unit_idx].stun_duration -= TICK_RATE;
            if self.units[unit_idx].stun_duration <= 0.0 {
                self.units[unit_idx].stun_duration = 0.0;
                self.units[unit_idx].state = UnitState::Idle;
                self.units[unit_idx].cc_type = None;
            }
            return;
        }

        // Handle untargetable
        if !self.units[unit_idx].is_targetable {
            self.units[unit_idx].untargetable_duration -= TICK_RATE;
            if self.units[unit_idx].untargetable_duration <= 0.0 {
                self.units[unit_idx].is_targetable = true;
            }
            return;
        }

        // Find/update target
        let needs_target = self.units[unit_idx].target_idx.is_none()
            || self.units[unit_idx]
                .target_idx
                .map(|t| !self.units[t].is_alive || !self.units[t].is_targetable)
                .unwrap_or(true);

        if needs_target {
            let enemies = if team == 0 {
                team1_indices
            } else {
                team0_indices
            };
            let target = targeting::find_target(unit_idx, &self.units, enemies, &mut self.rng);
            self.units[unit_idx].target_idx = target;
        }

        let target_idx = match self.units[unit_idx].target_idx {
            Some(t) => t,
            None => return, // No valid targets
        };

        // Check if in range
        let distance = hex_grid::hex_distance(
            self.units[unit_idx].position,
            self.units[target_idx].position,
        );
        let range = self.units[unit_idx].stats.range;

        if distance > range {
            // Move toward target
            let move_goal = self.choose_move_goal(unit_idx, target_idx);
            self.move_unit(unit_idx, move_goal);
        } else {
            // In range - try to cast ability or auto-attack
            self.units[unit_idx].state = UnitState::Attacking;

            // Check if can cast ability (full mana)
            let can_cast = self.units[unit_idx].ability.is_some()
                && self.units[unit_idx].stats.mana >= self.units[unit_idx].stats.max_mana;

            if can_cast {
                self.cast_ability(unit_idx, team, team0_indices, team1_indices);
            } else {
                // Auto-attack
                self.process_attack(unit_idx, target_idx);
            }
        }
    }

    /// Move a unit one step toward the target position.
    fn move_unit(&mut self, unit_idx: UnitId, target_pos: HexPos) {
        self.units[unit_idx].state = UnitState::Moving;

        let current_pos = self.units[unit_idx].position;
        if let Some(next_pos) =
            hex_grid::find_next_step(current_pos, target_pos, &self.occupied_hexes)
        {
            if next_pos != current_pos && self.occupied_hexes.contains(&next_pos) {
                return;
            }
            self.occupied_hexes.remove(&current_pos);
            self.units[unit_idx].position = next_pos;
            self.occupied_hexes.insert(next_pos);
        }
    }

    /// Pick the best open hex to move toward for attacking `target_idx`.
    /// Preference order:
    /// 1) Any open hex within attack range of target that is closest to current position.
    /// 2) Otherwise, the open hex closest to target.
    fn choose_move_goal(&self, unit_idx: UnitId, target_idx: UnitId) -> HexPos {
        let unit = &self.units[unit_idx];
        let current_pos = unit.position;
        let target_pos = self.units[target_idx].position;
        let attack_range = unit.stats.range.max(1);

        let mut best_in_range: Option<(HexPos, i32, i32)> = None;
        let mut best_open: Option<(HexPos, i32, i32)> = None;

        for row in 0..hex_grid::BOARD_ROWS {
            for col in 0..hex_grid::BOARD_COLS {
                let pos = (row, col);
                if pos != current_pos && self.occupied_hexes.contains(&pos) {
                    continue;
                }

                let travel_dist = hex_grid::hex_distance(current_pos, pos);
                if travel_dist == 0 {
                    continue;
                }

                let target_dist = hex_grid::hex_distance(pos, target_pos);

                if target_dist <= attack_range {
                    match best_in_range {
                        None => best_in_range = Some((pos, travel_dist, target_dist)),
                        Some((_, best_travel, best_target)) => {
                            if travel_dist < best_travel
                                || (travel_dist == best_travel && target_dist < best_target)
                            {
                                best_in_range = Some((pos, travel_dist, target_dist));
                            }
                        }
                    }
                }

                match best_open {
                    None => best_open = Some((pos, target_dist, travel_dist)),
                    Some((_, best_target_dist, best_travel)) => {
                        if target_dist < best_target_dist
                            || (target_dist == best_target_dist && travel_dist < best_travel)
                        {
                            best_open = Some((pos, target_dist, travel_dist));
                        }
                    }
                }
            }
        }

        if let Some((pos, _, _)) = best_in_range {
            return pos;
        }
        if let Some((pos, _, _)) = best_open {
            return pos;
        }
        target_pos
    }

    pub(crate) fn deal_damage(
        &mut self,
        attacker_idx: Option<UnitId>,
        target_idx: UnitId,
        base_damage: f64,
        damage_type: DamageType,
        can_crit: bool,
        is_ability: bool,
        source: &str,
    ) -> (f64, bool) {
        if !self.units[target_idx].is_alive || !self.units[target_idx].is_targetable {
            return (0.0, false);
        }

        let (final_damage, did_crit) = if let Some(attacker) = attacker_idx {
            let result = damage::calculate_damage(
                &self.units[attacker],
                &self.units[target_idx],
                base_damage,
                damage_type,
                can_crit,
                is_ability,
                &mut self.rng,
            );
            (result.final_damage, result.did_crit)
        } else {
            (base_damage.max(0.0), false)
        };

        let (_, hp_damage) = damage::apply_damage_to_unit(
            &mut self.units[target_idx],
            final_damage,
            damage_type,
            source,
        );

        if let Some(attacker) = attacker_idx {
            self.units[attacker].total_damage_dealt += hp_damage;
            let omnivamp = self.units[attacker].stats.omnivamp;
            if omnivamp > 0.0 && hp_damage > 0.0 {
                damage::heal_unit(&mut self.units[attacker], hp_damage * omnivamp);
            }
            items::on_damage_dealt(
                self,
                attacker,
                target_idx,
                hp_damage,
                damage_type,
                is_ability,
            );
        }

        items::on_damage_taken(self, target_idx, attacker_idx, hp_damage, damage_type);

        if !self.units[target_idx].is_alive {
            self.alive_dirty = true;
            if let Some(attacker) = attacker_idx {
                self.on_takedown(attacker, target_idx);
                self.units[attacker].target_idx = None;
            }
        }

        (hp_damage, did_crit)
    }

    fn on_takedown(&mut self, attacker_idx: UnitId, target_idx: UnitId) {
        let attacker_team = self.units[attacker_idx].team;
        let target_team = self.units[target_idx].team;
        if attacker_team == target_team {
            return;
        }
        let team = attacker_team as usize;
        if team > 1 {
            return;
        }

        self.debug_takedowns.push(TakedownAttribution {
            killer_team: attacker_team,
            killer_api_name: self.units[attacker_idx].api_name.clone(),
            victim_team: target_team,
            victim_api_name: self.units[target_idx].api_name.clone(),
        });

        // Bilgewater: +1 serpent per takedown when 3+ Bilgewater is active.
        if self.bilgewater_count_by_team[team] >= 3
            && self.units[attacker_idx]
                .traits
                .iter()
                .any(|t| t == "Bilgewater")
        {
            self.bilgewater_serpents_by_team[team] += 1;
        }

        // Shadow Isles: gain souls on takedown when 2+ Shadow Isles is active.
        if self.shadow_isles_count_by_team[team] >= 2
            && self.units[attacker_idx]
                .traits
                .iter()
                .any(|t| t == "Shadow Isles")
        {
            let victim_cost = self.units[target_idx].cost;
            let victim_star = self.units[target_idx].star_level;

            let base_souls: f64 = match victim_cost {
                1 => 1.0,
                2 => 2.0,
                3 => 3.0,
                4 => 5.0,
                5 => 8.0,
                _ => 1.0,
            };
            let star_mult: f64 = match victim_star {
                1 => 1.0,
                2 => 1.5,
                3 => 2.0,
                _ => 1.0,
            };

            let base = (base_souls * star_mult).floor() as i32;
            let soul_mult = if self.shadow_isles_count_by_team[team] >= 5 {
                1.9
            } else if self.shadow_isles_count_by_team[team] >= 4 {
                1.6
            } else if self.shadow_isles_count_by_team[team] >= 3 {
                1.3
            } else {
                1.0
            };
            let awarded = ((base as f64) * soul_mult).floor() as i32;
            if awarded > 0 {
                self.shadow_isles_souls_by_team[team] += awarded;
            }
        }
    }

    /// Process an auto-attack.
    fn process_attack(&mut self, attacker_idx: UnitId, target_idx: UnitId) {
        // Check attack cooldown
        if self.units[attacker_idx].attack_cooldown > 0.0 {
            self.units[attacker_idx].attack_cooldown -= TICK_RATE;
            return;
        }

        let attack_speed = self.units[attacker_idx].stats.attack_speed.min(AS_CAP);
        let cooldown = 1.0 / attack_speed;

        let base_damage = self.units[attacker_idx].stats.ad;
        let (hp_damage, did_crit) = self.deal_damage(
            Some(attacker_idx),
            target_idx,
            base_damage,
            DamageType::Physical,
            true,
            false,
            "basic_attack",
        );

        self.units[attacker_idx].attacks_performed += 1;

        // Mana on attack
        let mana_gain = self.units[attacker_idx].mana_per_attack;
        let max_mana = self.units[attacker_idx].stats.max_mana;
        self.units[attacker_idx].stats.mana =
            (self.units[attacker_idx].stats.mana + mana_gain).min(max_mana);

        items::on_attack_hit(self, attacker_idx, target_idx, did_crit, hp_damage);

        // Gunslinger: every Nth attack deals bonus physical damage.
        let mut gunslinger_proc = None;
        {
            let attacker = &mut self.units[attacker_idx];
            if attacker.gunslinger_attack_interval > 0 {
                attacker.gunslinger_attack_counter += 1;
                if attacker.gunslinger_attack_counter >= attacker.gunslinger_attack_interval {
                    attacker.gunslinger_attack_counter = 0;
                    if attacker.gunslinger_bonus_damage > 0.0 {
                        gunslinger_proc = Some(attacker.gunslinger_bonus_damage);
                    }
                }
            }
        }
        if let Some(proc_damage) = gunslinger_proc {
            if self.units[target_idx].is_alive {
                let _ = self.deal_damage(
                    Some(attacker_idx),
                    target_idx,
                    proc_damage,
                    DamageType::Physical,
                    false,
                    true,
                    "gunslinger_proc",
                );
            }
        }

        // Reset cooldown
        self.units[attacker_idx].attack_cooldown = cooldown;
    }

    /// Cast an ability.
    fn cast_ability(
        &mut self,
        caster_idx: UnitId,
        caster_team: i32,
        team0_indices: &[UnitId],
        team1_indices: &[UnitId],
    ) {
        self.units[caster_idx].state = UnitState::Casting;

        let (enemies, allies) = if caster_team == 0 {
            (team1_indices, team0_indices)
        } else {
            (team0_indices, team1_indices)
        };

        // Call ability dispatch
        let _ = abilities::cast_ability(self, caster_idx, enemies, allies);
        items::on_ability_cast(self, caster_idx);

        // Reset mana
        self.units[caster_idx].stats.mana = 0.0;
        self.units[caster_idx].abilities_cast += 1;

        // Cast lockout
        let cast_time = self.units[caster_idx]
            .ability
            .as_ref()
            .map(|a| a.cast_time)
            .unwrap_or(0.5);
        self.units[caster_idx].attack_cooldown = cast_time;
        self.units[caster_idx].state = UnitState::Idle;
    }

    /// Process DOT effects on all alive units.
    fn process_dots(&mut self) {
        for i in 0..self.units.len() {
            if !self.units[i].is_alive || self.units[i].dot_effects.is_empty() {
                continue;
            }

            let mut j = 0;
            while j < self.units[i].dot_effects.len() {
                self.units[i].dot_effects[j].remaining_duration -= TICK_RATE;
                self.units[i].dot_effects[j].time_since_last_tick += TICK_RATE;

                let should_tick = self.units[i].dot_effects[j].time_since_last_tick
                    >= self.units[i].dot_effects[j].tick_interval;

                if should_tick && self.units[i].is_alive {
                    self.units[i].dot_effects[j].time_since_last_tick -=
                        self.units[i].dot_effects[j].tick_interval;
                    let dmg = self.units[i].dot_effects[j].damage_per_tick;
                    let dmg_type = self.units[i].dot_effects[j].damage_type;

                    damage::apply_damage_to_unit(&mut self.units[i], dmg, dmg_type, "dot");

                    if !self.units[i].is_alive {
                        self.alive_dirty = true;
                    }
                }

                if self.units[i].dot_effects[j].remaining_duration <= 0.0 {
                    self.units[i].dot_effects.swap_remove(j);
                } else {
                    j += 1;
                }
            }
        }
    }

    /// Expire sunder/shred debuffs and restore armor/MR.
    fn expire_resist_reductions(&mut self) {
        let time = self.time;
        for i in 0..self.units.len() {
            if !self.units[i].is_alive {
                continue;
            }

            // Expire sunder stacks
            let mut j = 0;
            while j < self.units[i].sunder_stacks.len() {
                if time >= self.units[i].sunder_stacks[j].expiry {
                    let reduction = self.units[i].sunder_stacks[j].reduction;
                    self.units[i].stats.armor += reduction;
                    self.units[i].sunder_stacks.swap_remove(j);
                } else {
                    j += 1;
                }
            }

            // Expire shred stacks
            let mut j = 0;
            while j < self.units[i].shred_stacks.len() {
                if time >= self.units[i].shred_stacks[j].expiry {
                    let reduction = self.units[i].shred_stacks[j].reduction;
                    self.units[i].stats.magic_resist += reduction;
                    self.units[i].shred_stacks.swap_remove(j);
                } else {
                    j += 1;
                }
            }
        }
    }

    /// Process combat-time trait effects (Shurima heal, Warden shields, etc.).
    fn process_trait_combat_effects(&mut self) {
        let time = self.time;

        for i in 0..self.units.len() {
            if !self.units[i].is_alive {
                continue;
            }

            // Shurima: heal over time (1s interval)
            if self.units[i].shurima_heal_per_sec > 0.0 {
                if time - self.units[i].shurima_last_tick >= 1.0 {
                    self.units[i].shurima_last_tick = time;
                    let heal = self.units[i].shurima_heal_per_sec;
                    damage::heal_unit(&mut self.units[i], heal);
                }
            }

            // Ixtal: heal over time
            if self.units[i].ixtal_heal_per_sec > 0.0 {
                if time - self.units[i].ixtal_last_tick >= 1.0 {
                    self.units[i].ixtal_last_tick = time;
                    let heal = self.units[i].ixtal_heal_per_sec;
                    damage::heal_unit(&mut self.units[i], heal);
                }
            }

            // Warden: shield at HP thresholds
            if self.units[i].warden_shield_percent > 0.0 {
                let hp_pct = if self.units[i].stats.max_hp > 0.0 {
                    self.units[i].stats.hp / self.units[i].stats.max_hp
                } else {
                    1.0
                };
                if !self.units[i].warden_first_triggered
                    && hp_pct < self.units[i].warden_first_threshold
                {
                    self.units[i].warden_first_triggered = true;
                    let shield = self.units[i].stats.max_hp * self.units[i].warden_shield_percent;
                    self.units[i].stats.shield += shield;
                }
                if !self.units[i].warden_second_triggered
                    && hp_pct < self.units[i].warden_second_threshold
                {
                    self.units[i].warden_second_triggered = true;
                    let shield = self.units[i].stats.max_hp * self.units[i].warden_shield_percent;
                    self.units[i].stats.shield += shield;
                }
            }

            // Slayer: bonus AD scaling with missing HP
            if self.units[i].slayer_ad_increase > 0.0 {
                if time - self.units[i].slayer_last_tick >= 1.0 {
                    self.units[i].slayer_last_tick = time;
                    let hp_pct = if self.units[i].stats.max_hp > 0.0 {
                        self.units[i].stats.hp / self.units[i].stats.max_hp
                    } else {
                        1.0
                    };
                    let missing_pct = 1.0 - hp_pct;
                    let new_bonus = self.units[i].base_stats.ad
                        * self.units[i].slayer_ad_increase
                        * missing_pct;
                    let old_bonus = self.units[i].slayer_current_bonus;
                    self.units[i].stats.ad += new_bonus - old_bonus;
                    self.units[i].slayer_current_bonus = new_bonus;
                }
            }

            // Juggernaut: increased DR below 50% HP
            if self.units[i].juggernaut_increased_dr > 0.0 {
                let hp_pct = if self.units[i].stats.max_hp > 0.0 {
                    self.units[i].stats.hp / self.units[i].stats.max_hp
                } else {
                    1.0
                };
                let was_below = self.units[i].juggernaut_below_50;
                if hp_pct < 0.5 && !was_below {
                    self.units[i].juggernaut_below_50 = true;
                    self.units[i].stats.damage_reduction += self.units[i].juggernaut_increased_dr;
                } else if hp_pct >= 0.5 && was_below {
                    self.units[i].juggernaut_below_50 = false;
                    self.units[i].stats.damage_reduction -= self.units[i].juggernaut_increased_dr;
                }
            }

            // Zaun shimmer
            if self.units[i].zaun_shimmer_as > 0.0 && !self.units[i].zaun_shimmer_triggered {
                if time >= self.units[i].zaun_initial_delay {
                    let hp_pct = if self.units[i].stats.max_hp > 0.0 {
                        self.units[i].stats.hp / self.units[i].stats.max_hp
                    } else {
                        1.0
                    };
                    if hp_pct < 0.60 {
                        self.units[i].zaun_shimmer_triggered = true;
                        self.units[i].zaun_shimmer_active = true;
                        self.units[i].zaun_shimmer_end = time + self.units[i].zaun_shimmer_duration;
                        self.units[i].stats.attack_speed += self.units[i].zaun_shimmer_as;
                        self.units[i].stats.damage_reduction +=
                            self.units[i].zaun_shimmer_durability;

                        if self.units[i].zaun_max_health_heal > 0.0 {
                            let heal =
                                self.units[i].stats.max_hp * self.units[i].zaun_max_health_heal;
                            damage::heal_unit(&mut self.units[i], heal);
                        }
                    }
                }
            }
            // Zaun shimmer expiry
            if self.units[i].zaun_shimmer_active && time >= self.units[i].zaun_shimmer_end {
                self.units[i].zaun_shimmer_active = false;
                self.units[i].stats.attack_speed -= self.units[i].zaun_shimmer_as;
                self.units[i].stats.damage_reduction -= self.units[i].zaun_shimmer_durability;
            }

            // Quickstriker: bonus AS based on target's missing HP
            if self.units[i].quickstriker_min_as > 0.0 {
                if let Some(target_idx) = self.units[i].target_idx {
                    if self.units[target_idx].is_alive {
                        if time - self.units[i].qs_last_tick >= 1.0 {
                            self.units[i].qs_last_tick = time;
                            let t_hp_pct = if self.units[target_idx].stats.max_hp > 0.0 {
                                self.units[target_idx].stats.hp
                                    / self.units[target_idx].stats.max_hp
                            } else {
                                1.0
                            };
                            let t_missing = 1.0 - t_hp_pct;
                            let new_bonus = self.units[i].quickstriker_min_as
                                + (self.units[i].quickstriker_max_as
                                    - self.units[i].quickstriker_min_as)
                                    * t_missing;
                            let old_bonus = self.units[i].qs_current_bonus;
                            self.units[i].stats.attack_speed += new_bonus - old_bonus;
                            self.units[i].qs_current_bonus = new_bonus;
                        }
                    }
                }
            }
        }
    }

    /// Rebuild cached alive lists.
    fn rebuild_alive_lists(&mut self) {
        self.alive_team0.clear();
        self.alive_team1.clear();
        for (i, unit) in self.units.iter().enumerate() {
            if unit.is_alive {
                if unit.team == 0 {
                    self.alive_team0.push(i);
                } else {
                    self.alive_team1.push(i);
                }
            }
        }
    }

    /// Rebuild occupied hexes cache.
    fn rebuild_occupied_hexes(&mut self) {
        self.occupied_hexes.clear();
        for unit in &self.units {
            if unit.is_alive {
                self.occupied_hexes.insert(unit.position);
            }
        }
    }

    /// Build the combat result.
    fn build_result(&self) -> CombatResult {
        let team0_alive: Vec<&Unit> = self
            .units
            .iter()
            .filter(|u| u.team == 0 && u.is_alive)
            .collect();
        let team1_alive: Vec<&Unit> = self
            .units
            .iter()
            .filter(|u| u.team == 1 && u.is_alive)
            .collect();

        let team0_survivors = team0_alive.len() as i32;
        let team1_survivors = team1_alive.len() as i32;

        let team0_alive_hp: f64 = team0_alive.iter().map(|u| u.stats.hp).sum();
        let team1_alive_hp: f64 = team1_alive.iter().map(|u| u.stats.hp).sum();

        let winner = if team0_survivors > 0 && team1_survivors == 0 {
            0
        } else if team1_survivors > 0 && team0_survivors == 0 {
            1
        } else {
            // Draw or timeout - team with more remaining HP wins, else team0.
            if team0_alive_hp >= team1_alive_hp {
                0
            } else {
                1
            }
        };

        let team0_damage: f64 = self
            .units
            .iter()
            .filter(|u| u.team == 0)
            .map(|u| u.total_damage_dealt)
            .sum();
        let team1_damage: f64 = self
            .units
            .iter()
            .filter(|u| u.team == 1)
            .map(|u| u.total_damage_dealt)
            .sum();

        let team0_abilities: i32 = self
            .units
            .iter()
            .filter(|u| u.team == 0)
            .map(|u| u.abilities_cast)
            .sum();
        let team1_abilities: i32 = self
            .units
            .iter()
            .filter(|u| u.team == 1)
            .map(|u| u.abilities_cast)
            .sum();

        CombatResult {
            winner,
            combat_time: (self.time * 100.0).round() / 100.0,
            team0_survivors,
            team1_survivors,
            team0_total_damage: team0_damage,
            team1_total_damage: team1_damage,
            team0_abilities_cast: team0_abilities,
            team1_abilities_cast: team1_abilities,
            team0_bilgewater_serpents: self.bilgewater_serpents_by_team[0],
            team1_bilgewater_serpents: self.bilgewater_serpents_by_team[1],
            team0_shadow_isles_souls: self.shadow_isles_souls_by_team[0],
            team1_shadow_isles_souls: self.shadow_isles_souls_by_team[1],
            debug_takedowns: self.debug_takedowns.clone(),
        }
    }
}

/// Unit specification passed from Python.
#[derive(Debug, Clone)]
pub struct UnitSpec {
    pub api_name: String,
    pub star_level: i32,
    pub position: Vec<i32>,
    pub team: i32,
    pub items: Vec<String>,
    pub traits: Vec<String>,
}

/// Combat result returned to Python.
#[derive(Debug, Clone, PartialEq)]
pub struct CombatResult {
    pub winner: i32,
    pub combat_time: f64,
    pub team0_survivors: i32,
    pub team1_survivors: i32,
    pub team0_total_damage: f64,
    pub team1_total_damage: f64,
    pub team0_abilities_cast: i32,
    pub team1_abilities_cast: i32,
    pub team0_bilgewater_serpents: i32,
    pub team1_bilgewater_serpents: i32,
    pub team0_shadow_isles_souls: i32,
    pub team1_shadow_isles_souls: i32,
    pub debug_takedowns: Vec<TakedownAttribution>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct TakedownAttribution {
    pub killer_team: i32,
    pub killer_api_name: String,
    pub victim_team: i32,
    pub victim_api_name: String,
}

impl CombatResult {
    pub fn draw() -> Self {
        Self {
            winner: 0,
            combat_time: 0.0,
            team0_survivors: 0,
            team1_survivors: 0,
            team0_total_damage: 0.0,
            team1_total_damage: 0.0,
            team0_abilities_cast: 0,
            team1_abilities_cast: 0,
            team0_bilgewater_serpents: 0,
            team1_bilgewater_serpents: 0,
            team0_shadow_isles_souls: 0,
            team1_shadow_isles_souls: 0,
            debug_takedowns: Vec::new(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use std::collections::{HashMap, HashSet};
    use std::sync::Arc;

    fn champion_json(
        api_name: &str,
        hp: f64,
        ad: f64,
        attack_speed: f64,
        range: i32,
        role: &str,
    ) -> serde_json::Value {
        json!({
            "apiName": api_name,
            "name": api_name,
            "cost": 1,
            "role": role,
            "traits": [],
            "stats": {
                "hp": hp,
                "ad": ad,
                "attackSpeed": attack_speed,
                "armor": 20.0,
                "magicResist": 20.0,
                "range": range,
                "mana": 100.0,
                "startMana": 0.0,
                "critChance": 0.0,
                "critMultiplier": 1.4
            },
            "timing": {
                "attackWindup": 0.3,
                "missileSpeed": 0
            },
            "ability": {
                "name": "Test Ability",
                "variables": {
                    "Damage": [0.0, 0.0, 0.0, 0.0]
                }
            }
        })
    }

    fn test_combat_data() -> CombatData {
        let mut champions: HashMap<String, serde_json::Value> = HashMap::new();
        champions.insert(
            "TFT16_Attacker".to_string(),
            champion_json("TFT16_Attacker", 500.0, 5000.0, 1.0, 1, "ADCarry"),
        );
        champions.insert(
            "TFT16_Defender".to_string(),
            champion_json("TFT16_Defender", 100.0, 1.0, 0.5, 1, "Tank"),
        );
        champions.insert(
            "TFT16_MoverA".to_string(),
            champion_json("TFT16_MoverA", 2500.0, 10.0, 0.6, 1, "Tank"),
        );
        champions.insert(
            "TFT16_MoverB".to_string(),
            champion_json("TFT16_MoverB", 2500.0, 10.0, 0.6, 1, "Tank"),
        );
        CombatData {
            champions: Arc::new(champions),
        }
    }

    #[test]
    fn test_run_combat_is_deterministic_with_seed() {
        let mut engine = CombatEngine::new(test_combat_data());
        let team0 = vec![UnitSpec {
            api_name: "TFT16_Attacker".to_string(),
            star_level: 1,
            position: vec![0, 0],
            team: 0,
            items: vec![],
            traits: vec![],
        }];
        let team1 = vec![UnitSpec {
            api_name: "TFT16_Defender".to_string(),
            star_level: 1,
            position: vec![0, 1],
            team: 1,
            items: vec![],
            traits: vec![],
        }];

        let r1 = engine.run_combat(team0.clone(), team1.clone(), None, None, Some(12345));
        let r2 = engine.run_combat(team0, team1, None, None, Some(12345));
        assert_eq!(r1, r2);
    }

    #[test]
    fn test_damage_dealt_does_not_exceed_target_hp_pool() {
        let mut engine = CombatEngine::new(test_combat_data());
        let result = engine.run_combat(
            vec![UnitSpec {
                api_name: "TFT16_Attacker".to_string(),
                star_level: 1,
                position: vec![0, 0],
                team: 0,
                items: vec![],
                traits: vec![],
            }],
            vec![UnitSpec {
                api_name: "TFT16_Defender".to_string(),
                star_level: 1,
                position: vec![0, 1],
                team: 1,
                items: vec![],
                traits: vec![],
            }],
            None,
            None,
            Some(7),
        );

        assert!(result.team0_total_damage <= 100.0 + 1e-9);
    }

    #[test]
    fn test_units_do_not_overlap_while_moving() {
        let mut engine = CombatEngine::new(test_combat_data());
        let mover_a = engine
            .create_unit("TFT16_MoverA", 1, (0, 0), 0, &[], &[])
            .expect("missing mover A");
        let mover_b = engine
            .create_unit("TFT16_MoverB", 1, (3, 6), 1, &[], &[])
            .expect("missing mover B");

        engine.units.push(mover_a);
        engine.units.push(mover_b);
        engine.rebuild_alive_lists();
        engine.rebuild_occupied_hexes();

        for _ in 0..120 {
            if engine.alive_team0.is_empty() || engine.alive_team1.is_empty() {
                break;
            }
            engine.tick();
            let alive_positions: Vec<HexPos> = engine
                .units
                .iter()
                .filter(|u| u.is_alive)
                .map(|u| u.position)
                .collect();
            let unique: HashSet<HexPos> = alive_positions.iter().copied().collect();
            assert_eq!(alive_positions.len(), unique.len());
        }
    }

    fn make_unit_with_traits(api_name: &str, team: i32, traits: &[&str]) -> Unit {
        let mut stats = CombatStats::default();
        stats.hp = 1000.0;
        stats.max_hp = 1000.0;
        let mut unit = Unit::new(
            api_name.to_string(),
            api_name.to_string(),
            2,
            2,
            "ADCarry".to_string(),
            stats.clone(),
            stats,
            (0, 0),
            team,
        );
        unit.traits = traits.iter().map(|t| (*t).to_string()).collect();
        unit
    }

    #[test]
    fn test_trait_markers_are_applied_at_combat_start() {
        let mut engine = CombatEngine::new(test_combat_data());
        let mut u0 = make_unit_with_traits(
            "TFT16_TestA",
            0,
            &[
                "Quickstriker",
                "Warden",
                "Zaun",
                "Shurima",
                "Gunslinger",
                "Longshot",
                "Vanquisher",
                "Slayer",
            ],
        );
        u0.base_stats.ad = 100.0;
        u0.stats.ad = 100.0;
        let mut u1 = make_unit_with_traits(
            "TFT16_TestB",
            0,
            &[
                "Quickstriker",
                "Warden",
                "Zaun",
                "Shurima",
                "Gunslinger",
                "Longshot",
                "Vanquisher",
                "Slayer",
            ],
        );
        u1.base_stats.ad = 100.0;
        u1.stats.ad = 100.0;
        let u2 = make_unit_with_traits("TFT16_TestC", 0, &["Zaun"]);
        let enemy = make_unit_with_traits("TFT16_Enemy", 1, &[]);

        engine.units.push(u0);
        engine.units.push(u1);
        engine.units.push(u2);
        engine.units.push(enemy);
        engine.apply_trait_effects();

        let unit = &engine.units[0];
        assert!(unit.quickstriker_min_as > 0.0);
        assert!(unit.warden_shield_percent > 0.0);
        assert!(unit.zaun_shimmer_as > 0.0);
        assert!(unit.shurima_heal_per_sec > 0.0);
        assert!(unit.gunslinger_attack_interval > 0);
        assert!(unit.longshot_per_hex > 0.0);
        assert!(unit.vanquisher_ability_crit);
        assert!(unit.slayer_ad_increase > 0.0);
    }

    #[test]
    fn test_pair_synergy_applies_ambessa_kindred_bonus() {
        let mut engine = CombatEngine::new(test_combat_data());
        let ambessa = make_unit_with_traits("TFT16_Ambessa", 0, &[]);
        let kindred = make_unit_with_traits("TFT16_Kindred", 0, &[]);
        let enemy = make_unit_with_traits("TFT16_Enemy", 1, &[]);
        let ambessa_base_ad = ambessa.base_stats.ad;

        engine.units.push(ambessa);
        engine.units.push(kindred);
        engine.units.push(enemy);
        engine.apply_trait_effects();

        assert!(engine.units[0].stats.ad > ambessa_base_ad);
        assert!(engine.units[1]
            .item_data
            .contains_key("trait:chosen_wolves_bonus_damage"));
    }
}
