/// Core data structures for TFT combat units.
use crate::types::*;
use std::collections::HashMap;

/// Combat stats for a unit (mutable during combat).
#[derive(Debug, Clone)]
pub struct CombatStats {
    pub hp: f64,
    pub max_hp: f64,
    pub ad: f64,
    pub ap: f64,
    pub attack_speed: f64,
    pub armor: f64,
    pub magic_resist: f64,
    pub range: i32,
    pub mana: f64,
    pub max_mana: f64,
    pub crit_chance: f64,
    pub crit_multiplier: f64,
    pub damage_amp: f64,
    pub damage_reduction: f64,
    pub omnivamp: f64,
    pub shield: f64,
    pub move_speed: f64,
}

impl Default for CombatStats {
    fn default() -> Self {
        Self {
            hp: 500.0,
            max_hp: 500.0,
            ad: 50.0,
            ap: 0.0,
            attack_speed: 0.7,
            armor: 20.0,
            magic_resist: 20.0,
            range: 1,
            mana: 0.0,
            max_mana: 100.0,
            crit_chance: 0.25,
            crit_multiplier: 1.4,
            damage_amp: 0.0,
            damage_reduction: 0.0,
            omnivamp: 0.0,
            shield: 0.0,
            move_speed: 550.0,
        }
    }
}

impl CombatStats {
    /// Create a copy (all fields are Copy, so this is cheap).
    pub fn copy(&self) -> Self {
        self.clone()
    }
}

/// Champion ability definition.
#[derive(Debug, Clone)]
pub struct Ability {
    pub name: String,
    pub ability_type: AbilityType,
    pub damage_type: DamageType,
    pub targeting: TargetingType,
    pub base_damage: [f64; 4], // [0, 1star, 2star, 3star]
    pub ap_scaling: f64,
    pub ad_scaling: f64,
    pub cast_time: f64,
    pub aoe_radius: i32,
    pub num_targets: i32,
    pub variables: HashMap<String, serde_json::Value>,
}

impl Default for Ability {
    fn default() -> Self {
        Self {
            name: String::new(),
            ability_type: AbilityType::Damage,
            damage_type: DamageType::Magic,
            targeting: TargetingType::CurrentTarget,
            base_damage: [0.0; 4],
            ap_scaling: 1.0,
            ad_scaling: 0.0,
            cast_time: 0.5,
            aoe_radius: 0,
            num_targets: 1,
            variables: HashMap::new(),
        }
    }
}

/// Item equipped on a unit.
#[derive(Debug, Clone)]
pub struct Item {
    pub name: String,
    pub stats: Vec<(String, f64)>, // (stat_name, value) pairs
}

/// Temporary buff/debuff on a unit.
#[derive(Debug, Clone)]
pub struct Buff {
    pub name: String,
    pub duration: f64,
    pub stat_modifiers: Vec<(String, f64)>,
    pub stacks: i32,
    pub max_stacks: i32,
}

/// Damage-over-time effect.
#[derive(Debug, Clone)]
pub struct DotEffect {
    pub source_unit: Option<UnitId>,
    pub damage_per_tick: f64,
    pub tick_interval: f64,
    pub remaining_duration: f64,
    pub damage_type: DamageType,
    pub source_name: String,
    pub time_since_last_tick: f64,
}

/// Sunder/shred debuff tracking: (reduction_amount, expiry_time, source_name).
#[derive(Debug, Clone)]
pub struct ResistReduction {
    pub reduction: f64,
    pub expiry: f64,
    pub source: String,
}

/// A unit in combat.
#[derive(Debug, Clone)]
pub struct Unit {
    // Identity
    pub name: String,
    pub api_name: String,
    pub star_level: i32,
    pub cost: i32,
    pub role: String,

    // Stats
    pub stats: CombatStats,
    pub base_stats: CombatStats,

    // Position & team
    pub position: HexPos,
    pub team: i32,

    // Equipment & traits
    pub items: Vec<Item>,
    pub traits: Vec<String>,
    pub ability: Option<Ability>,

    // Combat state
    pub state: UnitState,
    pub target_idx: Option<UnitId>,
    pub attack_cooldown: f64,
    pub cast_progress: f64,
    pub stun_duration: f64,
    pub is_alive: bool,
    pub buffs: Vec<Buff>,
    pub dot_effects: Vec<DotEffect>,

    // CC state
    pub cc_type: Option<CcType>,
    pub taunt_source: Option<UnitId>,

    // Movement
    pub move_target: Option<HexPos>,

    // Untargetable
    pub is_targetable: bool,
    pub untargetable_duration: f64,

    // Basic attack immunity (Huntress trait)
    pub is_basic_attack_immune: bool,

    // Enhanced attacks (Fizz etc.)
    pub enhanced_attacks_remaining: i32,
    pub enhanced_attack_bonus_as: f64,
    pub enhanced_attack_on_hit_dmg: f64,

    // Analytics
    pub total_damage_dealt: f64,
    pub total_damage_taken: f64,
    pub total_healing: f64,
    pub abilities_cast: i32,
    pub attacks_performed: i32,

    // Timing
    pub attack_windup: f64,
    pub missile_speed: Option<i32>,

    // Sunder/shred stacks
    pub sunder_stacks: Vec<ResistReduction>,
    pub shred_stacks: Vec<ResistReduction>,

    // Trait combat markers (pre-initialized to None/0 for fast checks)
    pub shurima_heal_per_sec: f64,
    pub shurima_last_tick: f64,
    pub ixtal_heal_per_sec: f64,
    pub ixtal_last_tick: f64,
    pub warden_shield_percent: f64,
    pub warden_first_threshold: f64,
    pub warden_second_threshold: f64,
    pub warden_first_triggered: bool,
    pub warden_second_triggered: bool,
    pub slayer_ad_increase: f64,
    pub slayer_last_tick: f64,
    pub slayer_current_bonus: f64,
    pub juggernaut_increased_dr: f64,
    pub juggernaut_below_50: bool,
    pub zaun_shimmer_as: f64,
    pub zaun_shimmer_durability: f64,
    pub zaun_shimmer_duration: f64,
    pub zaun_initial_delay: f64,
    pub zaun_shimmer_triggered: bool,
    pub zaun_shimmer_active: bool,
    pub zaun_shimmer_end: f64,
    pub zaun_max_health_heal: f64,
    pub quickstriker_min_as: f64,
    pub quickstriker_max_as: f64,
    pub qs_last_tick: f64,
    pub qs_current_bonus: f64,
    pub longshot_per_hex: f64,
    pub vanquisher_ability_crit: bool,
    pub dragonborn_protected: bool,

    // Item combat flags (pre-computed at combat start)
    pub has_jeweled_gauntlet: bool,
    pub has_giant_slayer: bool,
    pub gunslinger_bonus_damage: f64,
    pub gunslinger_attack_interval: i32,
    pub gunslinger_attack_counter: i32,

    // Mana gain per attack (role-based)
    pub mana_per_attack: f64,

    // Summon flags
    pub is_summon: bool,

    // Generic per-item runtime state (counters, timestamps, toggles as 0/1).
    pub item_data: HashMap<String, f64>,
}

impl Unit {
    /// Create a new unit with default combat state.
    pub fn new(
        name: String,
        api_name: String,
        star_level: i32,
        cost: i32,
        role: String,
        stats: CombatStats,
        base_stats: CombatStats,
        position: HexPos,
        team: i32,
    ) -> Self {
        // Role-based mana per attack
        let mana_per_attack = match role.as_str() {
            "ADCarry" => 10.0,
            "APCaster" => 7.0,
            "Tank" | "Defender" => 5.0,
            "ADFighter" | "APFighter" => 8.0,
            _ => 10.0,
        };

        Self {
            name,
            api_name,
            star_level,
            cost,
            role,
            stats,
            base_stats,
            position,
            team,
            items: Vec::new(),
            traits: Vec::new(),
            ability: None,
            state: UnitState::Idle,
            target_idx: None,
            attack_cooldown: 0.0,
            cast_progress: 0.0,
            stun_duration: 0.0,
            is_alive: true,
            buffs: Vec::new(),
            dot_effects: Vec::new(),
            cc_type: None,
            taunt_source: None,
            move_target: None,
            is_targetable: true,
            untargetable_duration: 0.0,
            is_basic_attack_immune: false,
            enhanced_attacks_remaining: 0,
            enhanced_attack_bonus_as: 0.0,
            enhanced_attack_on_hit_dmg: 0.0,
            total_damage_dealt: 0.0,
            total_damage_taken: 0.0,
            total_healing: 0.0,
            abilities_cast: 0,
            attacks_performed: 0,
            attack_windup: 0.3,
            missile_speed: None,
            sunder_stacks: Vec::new(),
            shred_stacks: Vec::new(),
            shurima_heal_per_sec: 0.0,
            shurima_last_tick: -1.0,
            ixtal_heal_per_sec: 0.0,
            ixtal_last_tick: -1.0,
            warden_shield_percent: 0.0,
            warden_first_threshold: 0.5,
            warden_second_threshold: 0.25,
            warden_first_triggered: false,
            warden_second_triggered: false,
            slayer_ad_increase: 0.0,
            slayer_last_tick: -1.0,
            slayer_current_bonus: 0.0,
            juggernaut_increased_dr: 0.0,
            juggernaut_below_50: false,
            zaun_shimmer_as: 0.0,
            zaun_shimmer_durability: 0.0,
            zaun_shimmer_duration: 0.0,
            zaun_initial_delay: 0.0,
            zaun_shimmer_triggered: false,
            zaun_shimmer_active: false,
            zaun_shimmer_end: 0.0,
            zaun_max_health_heal: 0.0,
            quickstriker_min_as: 0.0,
            quickstriker_max_as: 0.0,
            qs_last_tick: -1.0,
            qs_current_bonus: 0.0,
            longshot_per_hex: 0.0,
            vanquisher_ability_crit: false,
            dragonborn_protected: false,
            has_jeweled_gauntlet: false,
            has_giant_slayer: false,
            gunslinger_bonus_damage: 0.0,
            gunslinger_attack_interval: 0,
            gunslinger_attack_counter: 0,
            mana_per_attack: mana_per_attack,
            is_summon: false,
            item_data: HashMap::new(),
        }
    }
}
