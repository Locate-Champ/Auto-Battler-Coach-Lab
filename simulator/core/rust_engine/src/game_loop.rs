use crate::engine::{CombatEngine, UnitSpec};
use crate::python_rng::PyRng;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{BTreeMap, HashMap, HashSet};
use std::fs;
use std::path::Path;

const DEFAULT_NUM_PLAYERS: usize = 8;
const AUGMENT_TAGS: [&str; 3] = ["2-1", "3-2", "4-2"];

#[derive(Clone)]
pub struct GameConfig {
    pub board_rows: i32,
    pub board_cols: i32,
    pub bench_size: usize,
    pub shop_size: usize,
    pub item_bench_size: usize,
    pub max_items_per_unit: usize,
    pub starting_hp: i32,
    pub starting_gold: i32,
    pub starting_level: i32,
    pub max_level: i32,
    pub base_income: i32,
    pub max_interest: i32,
    pub refresh_cost: i32,
    pub xp_cost: i32,
    pub xp_per_buy: i32,
    pub passive_xp_per_round: i32,
    pub level_xp_required: Vec<i32>,
    pub starting_round_gold: Vec<i32>,
    pub pool_sizes: HashMap<i32, i32>,
    pub champions_by_cost: HashMap<i32, HashMap<String, i32>>,
    pub champion_names_by_cost: HashMap<i32, Vec<String>>,
    pub level_odds: Vec<Vec<f64>>,
    pub name_to_api: HashMap<String, String>,
    pub name_to_cost: HashMap<String, i32>,
    pub champion_traits: HashMap<String, Vec<String>>,
    pub item_components: Vec<String>,
    pub pve_item_drops: HashMap<i32, (i32, i32)>,
    pub augment_rounds: HashMap<i32, String>,
    pub carousel_rounds: HashSet<i32>,
    pub carousel_champion_odds: HashMap<i32, Vec<f64>>,
    pub carousel_item_weights: Vec<(String, i32)>,
    pub carousel_size: usize,
    pub round_base_damage: Vec<(i32, i32)>,
    pub damage_per_unit: Vec<i32>,
}

impl GameConfig {
    pub fn from_python(py: Python<'_>) -> PyResult<Self> {
        let constants = py.import("simulator.game.constants")?;

        let carousel_item_weights = {
            let weight_obj = constants.getattr("CAROUSEL_ITEM_WEIGHTS")?;
            let weight_dict = weight_obj.downcast::<PyDict>()?;
            let mut ordered = Vec::with_capacity(weight_dict.len());
            for (item_name, weight) in weight_dict.iter() {
                ordered.push((item_name.extract::<String>()?, weight.extract::<i32>()?));
            }
            ordered
        };

        let champion_names_by_cost = {
            let by_cost_obj = constants.getattr("CHAMPIONS_BY_COST")?;
            let by_cost = by_cost_obj.downcast::<PyDict>()?;
            let mut ordered: HashMap<i32, Vec<String>> = HashMap::new();
            for (cost_obj, champs_obj) in by_cost.iter() {
                let cost = cost_obj.extract::<i32>()?;
                let champs_dict = champs_obj.downcast::<PyDict>()?;
                let mut names = Vec::with_capacity(champs_dict.len());
                for (champ_name, _) in champs_dict.iter() {
                    names.push(champ_name.extract::<String>()?);
                }
                ordered.insert(cost, names);
            }
            ordered
        };

        Ok(Self {
            board_rows: constants.getattr("BOARD_ROWS")?.extract()?,
            board_cols: constants.getattr("BOARD_COLS")?.extract()?,
            bench_size: constants.getattr("BENCH_SIZE")?.extract()?,
            shop_size: constants.getattr("SHOP_SIZE")?.extract()?,
            item_bench_size: constants.getattr("ITEM_BENCH_SIZE")?.extract()?,
            max_items_per_unit: constants.getattr("MAX_ITEMS_PER_UNIT")?.extract()?,
            starting_hp: constants.getattr("STARTING_HP")?.extract()?,
            starting_gold: constants.getattr("STARTING_GOLD")?.extract()?,
            starting_level: constants.getattr("STARTING_LEVEL")?.extract()?,
            max_level: constants.getattr("MAX_LEVEL")?.extract()?,
            base_income: constants.getattr("BASE_INCOME")?.extract()?,
            max_interest: constants.getattr("MAX_INTEREST")?.extract()?,
            refresh_cost: constants.getattr("REFRESH_COST")?.extract()?,
            xp_cost: constants.getattr("XP_COST")?.extract()?,
            xp_per_buy: constants.getattr("XP_PER_BUY")?.extract()?,
            passive_xp_per_round: constants.getattr("PASSIVE_XP_PER_ROUND")?.extract()?,
            level_xp_required: constants.getattr("LEVEL_XP_REQUIRED")?.extract()?,
            starting_round_gold: constants.getattr("STARTING_ROUND_GOLD")?.extract()?,
            pool_sizes: constants.getattr("POOL_SIZES")?.extract()?,
            champions_by_cost: constants.getattr("CHAMPIONS_BY_COST")?.extract()?,
            champion_names_by_cost,
            level_odds: constants.getattr("LEVEL_ODDS")?.extract()?,
            name_to_api: constants.getattr("NAME_TO_API")?.extract()?,
            name_to_cost: constants.getattr("NAME_TO_COST")?.extract()?,
            champion_traits: constants.getattr("CHAMPION_TRAITS")?.extract()?,
            item_components: constants.getattr("ITEM_COMPONENTS_LIST")?.extract()?,
            pve_item_drops: constants.getattr("PVE_ITEM_DROPS")?.extract()?,
            augment_rounds: constants.getattr("AUGMENT_ROUNDS")?.extract()?,
            carousel_rounds: constants.getattr("CAROUSEL_ROUNDS")?.extract()?,
            carousel_champion_odds: constants.getattr("CAROUSEL_CHAMPION_ODDS")?.extract()?,
            carousel_item_weights,
            carousel_size: constants.getattr("CAROUSEL_SIZE")?.extract()?,
            round_base_damage: constants.getattr("ROUND_BASE_DAMAGE")?.extract()?,
            damage_per_unit: constants.getattr("DAMAGE_PER_UNIT")?.extract()?,
        })
    }
}

#[derive(Debug, Deserialize)]
struct RawAugment {
    #[serde(default, rename = "apiName")]
    api_name: String,
    #[serde(default)]
    tags: Vec<String>,
    #[serde(default)]
    disabled: bool,
}

#[derive(Clone, Default)]
pub struct AugmentPools {
    pub by_round: HashMap<String, Vec<String>>,
}

impl AugmentPools {
    pub fn load(path: &Path) -> Result<Self, String> {
        let content =
            fs::read_to_string(path).map_err(|e| format!("Failed to read augment data: {e}"))?;
        let raw: Vec<RawAugment> = serde_json::from_str(&content)
            .map_err(|e| format!("Failed to parse augment data JSON: {e}"))?;

        let mut by_round: HashMap<String, Vec<String>> = HashMap::new();
        for tag in AUGMENT_TAGS {
            by_round.insert(tag.to_string(), Vec::new());
        }

        for augment in raw {
            if augment.disabled || augment.api_name.is_empty() {
                continue;
            }
            for tag in augment.tags {
                if tag == "2-1" || tag == "3-2" || tag == "4-2" {
                    by_round
                        .entry(tag)
                        .or_default()
                        .push(augment.api_name.clone());
                }
            }
        }

        for pool in by_round.values_mut() {
            pool.sort();
            pool.dedup();
        }

        Ok(Self { by_round })
    }
}

#[derive(Clone)]
struct ChampionInstance {
    name: String,
    api_name: String,
    cost: i32,
    star_level: i32,
    items: Vec<String>,
}

#[derive(Clone, Copy)]
enum CopyLoc {
    Board((i32, i32)),
    Bench(usize),
}

struct PlayerState {
    player_id: usize,
    gold: i32,
    hp: i32,
    level: i32,
    xp: i32,
    board: BTreeMap<(i32, i32), ChampionInstance>,
    bench: Vec<Option<ChampionInstance>>,
    item_bench: Vec<String>,
    shop: Vec<Option<String>>,
    win_streak: i32,
    loss_streak: i32,
    alive: bool,
    placement: i32,
    elimination_hp: i32,
}

impl PlayerState {
    fn new(player_id: usize, config: &GameConfig) -> Self {
        Self {
            player_id,
            gold: config.starting_gold,
            hp: config.starting_hp,
            level: config.starting_level,
            xp: 0,
            board: BTreeMap::new(),
            bench: vec![None; config.bench_size],
            item_bench: Vec::new(),
            shop: vec![None; config.shop_size],
            win_streak: 0,
            loss_streak: 0,
            alive: true,
            placement: 0,
            elimination_hp: 0,
        }
    }

    fn board_count(&self) -> usize {
        self.board.len()
    }

    fn max_units(&self) -> i32 {
        self.level
    }

    fn can_afford(&self, amount: i32) -> bool {
        self.gold >= amount
    }

    fn find_empty_bench(&self) -> Option<usize> {
        self.bench.iter().position(|slot| slot.is_none())
    }

    fn first_empty_pos(&self, config: &GameConfig) -> Option<(i32, i32)> {
        for row in 0..config.board_rows {
            for col in 0..config.board_cols {
                let pos = (row, col);
                if !self.board.contains_key(&pos) {
                    return Some(pos);
                }
            }
        }
        None
    }

    fn check_level_up(&mut self, config: &GameConfig) {
        while self.level < config.max_level {
            let required = *config
                .level_xp_required
                .get(self.level as usize)
                .unwrap_or(&i32::MAX);
            if self.xp >= required {
                self.xp -= required;
                self.level += 1;
            } else {
                break;
            }
        }
    }

    fn add_income(&mut self, round_num: i32, config: &GameConfig) {
        self.xp += config.passive_xp_per_round;
        self.check_level_up(config);

        let interest = std::cmp::min(self.gold / 10, config.max_interest);
        if (round_num as usize) < config.starting_round_gold.len() {
            self.gold += config.starting_round_gold[round_num as usize] + interest;
            return;
        }

        let streak = std::cmp::max(self.win_streak, self.loss_streak);
        self.gold += config.base_income + interest + streak_gold(streak);
    }

    fn buy_xp(&mut self, config: &GameConfig) -> bool {
        if !self.can_afford(config.xp_cost) || self.level >= config.max_level {
            return false;
        }
        self.gold -= config.xp_cost;
        self.xp += config.xp_per_buy;
        self.check_level_up(config);
        true
    }

    fn buy_champion(
        &mut self,
        shop_slot: usize,
        pool: &mut ChampionPool,
        config: &GameConfig,
    ) -> bool {
        if shop_slot >= self.shop.len() {
            return false;
        }

        let name = match self.shop[shop_slot].clone() {
            Some(value) => value,
            None => return false,
        };
        let cost = *config.name_to_cost.get(&name).unwrap_or(&1);
        if !self.can_afford(cost) {
            return false;
        }

        let bench_idx = match self.find_empty_bench() {
            Some(idx) => idx,
            None => return false,
        };

        if !pool.take(&name) {
            return false;
        }

        self.gold -= cost;
        self.shop[shop_slot] = None;

        let champ = ChampionInstance {
            name: name.clone(),
            api_name: config
                .name_to_api
                .get(&name)
                .cloned()
                .unwrap_or_else(|| default_api_name(&name)),
            cost,
            star_level: 1,
            items: Vec::new(),
        };
        self.bench[bench_idx] = Some(champ);
        self.check_upgrade(&name, config);
        true
    }

    fn check_upgrade(&mut self, name: &str, config: &GameConfig) {
        let mut star1_copies: Vec<CopyLoc> = Vec::new();
        let mut star2_copies: Vec<CopyLoc> = Vec::new();

        for (pos, champ) in &self.board {
            if champ.name != name {
                continue;
            }
            if champ.star_level == 1 {
                star1_copies.push(CopyLoc::Board(*pos));
            } else if champ.star_level == 2 {
                star2_copies.push(CopyLoc::Board(*pos));
            }
        }

        for (idx, champ) in self.bench.iter().enumerate() {
            let Some(champ) = champ else { continue };
            if champ.name != name {
                continue;
            }
            if champ.star_level == 1 {
                star1_copies.push(CopyLoc::Bench(idx));
            } else if champ.star_level == 2 {
                star2_copies.push(CopyLoc::Bench(idx));
            }
        }

        let mut upgraded_to_two = false;
        if star1_copies.len() >= 3 {
            self.do_upgrade(name, 1, &star1_copies, config);
            upgraded_to_two = true;
        }

        if star2_copies.len() >= 3 {
            self.do_upgrade(name, 2, &star2_copies, config);
            return;
        }

        if upgraded_to_two {
            let copies_after = self.find_copies(name, 2);
            if copies_after.len() >= 3 {
                self.do_upgrade(name, 2, &copies_after, config);
            }
        }
    }

    fn find_copies(&self, name: &str, star_level: i32) -> Vec<CopyLoc> {
        let mut copies = Vec::new();
        for (pos, champ) in &self.board {
            if champ.name == name && champ.star_level == star_level {
                copies.push(CopyLoc::Board(*pos));
            }
        }
        for (idx, champ) in self.bench.iter().enumerate() {
            if let Some(champ) = champ {
                if champ.name == name && champ.star_level == star_level {
                    copies.push(CopyLoc::Bench(idx));
                }
            }
        }
        copies
    }

    fn do_upgrade(&mut self, name: &str, star_level: i32, copies: &[CopyLoc], config: &GameConfig) {
        let new_star = star_level + 1;
        let mut all_items: Vec<String> = Vec::new();

        for copy in copies {
            match copy {
                CopyLoc::Board(pos) => {
                    if let Some(champ) = self.board.get(pos) {
                        all_items.extend(champ.items.iter().cloned());
                    }
                }
                CopyLoc::Bench(idx) => {
                    if let Some(champ) = self.bench.get(*idx).and_then(|c| c.as_ref()) {
                        all_items.extend(champ.items.iter().cloned());
                    }
                }
            }
        }

        let first_loc = copies[0];
        for copy in copies {
            match copy {
                CopyLoc::Board(pos) => {
                    self.board.remove(pos);
                }
                CopyLoc::Bench(idx) => {
                    if *idx < self.bench.len() {
                        self.bench[*idx] = None;
                    }
                }
            }
        }

        let mut kept_items = all_items;
        let overflow = if kept_items.len() > config.max_items_per_unit {
            kept_items.split_off(config.max_items_per_unit)
        } else {
            Vec::new()
        };

        let upgraded = ChampionInstance {
            name: name.to_string(),
            api_name: config
                .name_to_api
                .get(name)
                .cloned()
                .unwrap_or_else(|| default_api_name(name)),
            cost: *config.name_to_cost.get(name).unwrap_or(&1),
            star_level: new_star,
            items: kept_items,
        };

        for item in overflow {
            if self.item_bench.len() < config.item_bench_size {
                self.item_bench.push(item);
            }
        }

        match first_loc {
            CopyLoc::Board(pos) => {
                self.board.insert(pos, upgraded);
            }
            CopyLoc::Bench(idx) => {
                if idx < self.bench.len() {
                    self.bench[idx] = Some(upgraded);
                }
            }
        }
    }

    fn active_traits(&self, config: &GameConfig) -> HashMap<String, i32> {
        let mut trait_counts: HashMap<String, i32> = HashMap::new();
        for champ in self.board.values() {
            if let Some(traits) = config.champion_traits.get(&champ.name) {
                for trait_name in traits {
                    *trait_counts.entry(trait_name.clone()).or_insert(0) += 1;
                }
            }
        }
        trait_counts
    }

    fn auto_fill_board(&mut self, config: &GameConfig) {
        for idx in 0..self.bench.len() {
            if (self.board_count() as i32) >= self.max_units() {
                break;
            }
            let Some(champ) = self.bench[idx].clone() else {
                continue;
            };
            let Some(pos) = self.first_empty_pos(config) else {
                break;
            };
            self.board.insert(pos, champ);
            self.bench[idx] = None;
        }
    }

    fn take_damage(&mut self, amount: i32) {
        let raw_hp = self.hp - amount;
        if raw_hp <= 0 {
            self.elimination_hp = raw_hp;
            self.hp = 0;
            self.alive = false;
            return;
        }
        self.elimination_hp = 0;
        self.hp = raw_hp;
    }

    fn win_round(&mut self) {
        self.win_streak += 1;
        self.loss_streak = 0;
        self.gold += 1;
    }

    fn lose_round(&mut self, damage: i32) {
        self.loss_streak += 1;
        self.win_streak = 0;
        self.take_damage(damage);
    }

    fn all_champions(&self) -> Vec<ChampionInstance> {
        let mut champs: Vec<ChampionInstance> = self.board.values().cloned().collect();
        for slot in &self.bench {
            if let Some(champ) = slot {
                champs.push(champ.clone());
            }
        }
        champs
    }
}

struct ChampionPool {
    pool: HashMap<String, i32>,
    names_by_cost: HashMap<i32, Vec<String>>,
}

impl ChampionPool {
    fn new(config: &GameConfig) -> Self {
        let mut pool: HashMap<String, i32> = HashMap::new();
        for champs in config.champions_by_cost.values() {
            for (name, count) in champs {
                pool.insert(name.clone(), *count);
            }
        }

        let mut names_by_cost: HashMap<i32, Vec<String>> = HashMap::new();
        for cost in [1_i32, 2, 3, 4, 5, 7] {
            let Some(ordered_names) = config.champion_names_by_cost.get(&cost) else {
                continue;
            };
            let tier_cost = if cost == 7 { 5 } else { cost };
            let tier_names = names_by_cost.entry(tier_cost).or_default();
            for name in ordered_names {
                if !tier_names.iter().any(|existing| existing == name) {
                    tier_names.push(name.clone());
                }
            }
        }

        Self {
            pool,
            names_by_cost,
        }
    }

    fn roll_shop(&self, level: i32, config: &GameConfig, rng: &mut PyRng) -> Vec<Option<String>> {
        let level_idx = std::cmp::max(
            0,
            std::cmp::min(level - 1, (config.level_odds.len() as i32) - 1),
        ) as usize;
        let odds = &config.level_odds[level_idx];
        let mut shop = Vec::with_capacity(config.shop_size);

        for _ in 0..config.shop_size {
            let mut cumulative = 0.0;
            let mut chosen_cost = 1_i32;
            let roll = rng.random();
            for (cost_idx, prob) in odds.iter().enumerate() {
                cumulative += if *prob > 0.0 { *prob } else { 0.0 };
                if roll < cumulative {
                    chosen_cost = (cost_idx + 1) as i32;
                    break;
                }
            }
            shop.push(self.pick_from_tier(chosen_cost, rng));
        }

        shop
    }

    fn pick_from_tier(&self, cost: i32, rng: &mut PyRng) -> Option<String> {
        let names = self.names_by_cost.get(&cost)?;
        let total: f64 = names
            .iter()
            .map(|name| std::cmp::max(0, *self.pool.get(name).unwrap_or(&0)) as f64)
            .sum();
        if total <= 0.0 {
            return None;
        }

        let mut cumulative = 0.0_f64;
        let mut last_nonzero: Option<String> = None;
        let roll = rng.random() * total;
        for name in names {
            let weight = std::cmp::max(0, *self.pool.get(name).unwrap_or(&0));
            if weight <= 0 {
                continue;
            }
            cumulative += weight as f64;
            last_nonzero = Some(name.clone());
            if roll < cumulative {
                return Some(name.clone());
            }
        }

        last_nonzero
    }

    fn take(&mut self, name: &str) -> bool {
        let Some(current) = self.pool.get_mut(name) else {
            return false;
        };
        if *current <= 0 {
            return false;
        }
        *current -= 1;
        true
    }

    fn return_champion(&mut self, name: &str, count: i32, config: &GameConfig) {
        let Some(current) = self.pool.get_mut(name) else {
            return;
        };
        let cost = *config.name_to_cost.get(name).unwrap_or(&1);
        let max_count = *config.pool_sizes.get(&cost).unwrap_or(&30);
        *current = std::cmp::min(max_count, *current + count);
    }

    fn return_player_champions(&mut self, champions: &[ChampionInstance], config: &GameConfig) {
        for champ in champions {
            let copies = 3_i32.pow((champ.star_level.saturating_sub(1)) as u32);
            self.return_champion(&champ.name, copies, config);
        }
    }

    fn available(&self, name: &str) -> i32 {
        *self.pool.get(name).unwrap_or(&0)
    }
}

#[derive(Clone, Copy)]
enum AgentStyle {
    Random,
    Econ,
    Slam,
}

#[derive(Clone)]
struct CombatRoundSnapshot {
    p1: usize,
    p2: usize,
    is_ghost: bool,
    winner: usize,
    is_draw: bool,
    damage: i32,
    combat_time: f64,
    team0_survivors: i32,
    team1_survivors: i32,
}

struct RoundOutcome {
    winner_id: usize,
    damage_to_loser: i32,
    is_draw: bool,
    combat_time: f64,
    team0_survivors: i32,
    team1_survivors: i32,
}

#[derive(Clone, Serialize)]
pub struct TrainingUnitSnapshot {
    pub champion_id: String,
    pub star_level: i32,
    pub items: Vec<String>,
    pub position: i32,
}

#[derive(Clone, Serialize)]
pub struct TrainingRow {
    pub game_id: i64,
    pub round: i32,
    pub player_id: i32,
    pub placement: i32,
    pub hp: i32,
    pub gold: i32,
    pub level: i32,
    pub streak: i32,
    pub board_count: i32,
    pub win_streak: i32,
    pub loss_streak: i32,
    pub num_augments: i32,
    pub num_traits: i32,
    pub alive_count: i32,
    pub units: Vec<TrainingUnitSnapshot>,
    pub traits: HashMap<String, i32>,
    pub augments: Vec<String>,
    pub opponent_units: Vec<TrainingUnitSnapshot>,
    pub opponent_traits: HashMap<String, i32>,
    pub opponent_hp: i32,
    pub opponent_gold: i32,
    pub opponent_level: i32,
    pub opponent_streak: i32,
    pub opponent_board_count: i32,
    pub opponent_win_streak: i32,
    pub opponent_loss_streak: i32,
    pub opponent_num_augments: i32,
    pub opponent_num_traits: i32,
    pub opponent_augments: Vec<String>,
    pub combat_result: Option<i32>,
    pub damage_dealt: f64,
    pub damage_taken: f64,
    pub combat_time: f64,
    pub survivors: i32,
    pub is_ghost: bool,
    pub board_names: Vec<String>,
    pub board_stars: Vec<i32>,
    pub trait_names: Vec<String>,
    pub trait_counts: Vec<i32>,
}

pub struct GameRunOutput {
    pub rounds: i32,
    pub placements: Vec<Value>,
    pub training_rows: Vec<TrainingRow>,
    pub analytics: Value,
}

pub fn run_game(
    engine: &mut CombatEngine,
    config: &GameConfig,
    augment_pools: &AugmentPools,
    game_id: i64,
    seed: u64,
    agent_mix: Option<&HashMap<String, i32>>,
    include_training_rows: bool,
) -> Result<GameRunOutput, String> {
    let mut rng = PyRng::seed_from_u64(seed);
    let mut pool = ChampionPool::new(config);
    let mut players: Vec<PlayerState> = (0..DEFAULT_NUM_PLAYERS)
        .map(|player_id| PlayerState::new(player_id, config))
        .collect();
    let mut player_augments: HashMap<usize, Vec<String>> = (0..DEFAULT_NUM_PLAYERS)
        .map(|player_id| (player_id, Vec::new()))
        .collect();
    let player_styles = assign_agent_styles(DEFAULT_NUM_PLAYERS, agent_mix, &mut rng);
    let mut matchmaking_weights = vec![vec![10_i32; DEFAULT_NUM_PLAYERS]; DEFAULT_NUM_PLAYERS];
    for idx in 0..DEFAULT_NUM_PLAYERS {
        matchmaking_weights[idx][idx] = 0;
    }

    let mut round_num: i32 = 0;
    let mut placements: Vec<(usize, i32)> = Vec::new();
    let mut training_rows: Vec<TrainingRow> = Vec::new();

    let pve_rounds = std::cmp::min(4_i32, config.starting_round_gold.len() as i32);
    for round in 0..pve_rounds {
        round_num = round;
        if config.carousel_rounds.contains(&round_num) {
            carousel_phase(round_num, &mut players, &mut pool, config, &mut rng);
        }
        pve_round(
            round_num,
            &mut players,
            &mut pool,
            config,
            &player_styles,
            &mut rng,
        );
    }

    round_num = 4;
    while alive_count(&players) > 1 {
        if config.carousel_rounds.contains(&round_num) {
            carousel_phase(round_num, &mut players, &mut pool, config, &mut rng);
        }
        pvp_round(
            round_num,
            engine,
            &mut players,
            &mut pool,
            config,
            augment_pools,
            &mut player_augments,
            &player_styles,
            &mut matchmaking_weights,
            &mut placements,
            game_id,
            &mut training_rows,
            include_training_rows,
            &mut rng,
        );
        round_num += 1;
        if round_num > 60 {
            break;
        }
    }

    for player_id in alive_ids(&players) {
        players[player_id].placement = 1;
        placements.push((player_id, 1));
    }
    placements.sort_by(|a, b| a.1.cmp(&b.1).then_with(|| a.0.cmp(&b.0)));

    let placement_rows = build_placement_rows(&players, &placements, &player_augments, config);
    if include_training_rows {
        let placement_map: HashMap<usize, i32> = placements.iter().copied().collect();
        for row in &mut training_rows {
            row.placement = placement_map
                .get(&(row.player_id as usize))
                .copied()
                .unwrap_or(0);
        }
    } else {
        training_rows.clear();
    }
    let analytics = build_analytics(&placement_rows);

    Ok(GameRunOutput {
        rounds: round_num,
        placements: placement_rows,
        training_rows,
        analytics,
    })
}

fn pve_round(
    round_num: i32,
    players: &mut [PlayerState],
    pool: &mut ChampionPool,
    config: &GameConfig,
    player_styles: &[AgentStyle],
    rng: &mut PyRng,
) {
    let ids = alive_ids(players);
    for player_id in ids {
        let style = player_styles[player_id];
        let player = &mut players[player_id];
        player.add_income(round_num, config);

        let (min_drop, max_drop) = config
            .pve_item_drops
            .get(&round_num)
            .copied()
            .unwrap_or((0, 0));
        if min_drop <= max_drop && !config.item_components.is_empty() {
            let drops = rng.randint_i32(min_drop, max_drop);
            for _ in 0..drops {
                if player.item_bench.len() >= config.item_bench_size {
                    break;
                }
                let idx = rng.randrange_usize_stop(config.item_components.len());
                player.item_bench.push(config.item_components[idx].clone());
            }
        }

        return_shop_to_pool(player, pool, config);
        player.shop = pool.roll_shop(player.level, config, rng);
        run_agent(player, pool, config, style, rng);
        player.auto_fill_board(config);
    }
}

#[allow(clippy::too_many_arguments)]
fn pvp_round(
    round_num: i32,
    engine: &mut CombatEngine,
    players: &mut [PlayerState],
    pool: &mut ChampionPool,
    config: &GameConfig,
    augment_pools: &AugmentPools,
    player_augments: &mut HashMap<usize, Vec<String>>,
    player_styles: &[AgentStyle],
    matchmaking_weights: &mut [Vec<i32>],
    placements: &mut Vec<(usize, i32)>,
    game_id: i64,
    training_rows: &mut Vec<TrainingRow>,
    include_training_rows: bool,
    rng: &mut PyRng,
) {
    if let Some(tag) = config.augment_rounds.get(&round_num) {
        augment_selection_phase(players, tag, augment_pools, player_augments, rng);
    }

    let ids = alive_ids(players);
    for player_id in ids.iter().copied() {
        players[player_id].add_income(round_num, config);
    }

    for player_id in ids.iter().copied() {
        let style = player_styles[player_id];
        let player = &mut players[player_id];
        return_shop_to_pool(player, pool, config);
        player.shop = pool.roll_shop(player.level, config, rng);
        run_agent(player, pool, config, style, rng);
        player.auto_fill_board(config);
    }

    let matchups = matchmake(&ids, matchmaking_weights, rng);
    let pre_combat_hp: HashMap<usize, i32> = ids
        .iter()
        .copied()
        .map(|player_id| (player_id, players[player_id].hp))
        .collect();
    let mut combat_results: Vec<CombatRoundSnapshot> = Vec::new();

    let row_index_by_player = if include_training_rows {
        collect_training_rows_precombat(
            game_id,
            round_num,
            players,
            player_augments,
            config,
            &matchups,
            training_rows,
        )
    } else {
        HashMap::new()
    };

    for (p1_id, p2_id, is_ghost) in matchups.iter().copied() {
        if !players[p1_id].alive {
            continue;
        }

        let p1_augments: &[String] = player_augments
            .get(&p1_id)
            .map(Vec::as_slice)
            .unwrap_or(&[]);
        let p2_augments: &[String] = player_augments
            .get(&p2_id)
            .map(Vec::as_slice)
            .unwrap_or(&[]);

        let result = resolve_combat(
            round_num,
            &players[p1_id],
            &players[p2_id],
            p1_augments,
            p2_augments,
            engine,
            config,
            rng,
        );

        combat_results.push(CombatRoundSnapshot {
            p1: p1_id,
            p2: p2_id,
            is_ghost,
            winner: result.winner_id,
            is_draw: result.is_draw,
            damage: result.damage_to_loser,
            combat_time: result.combat_time,
            team0_survivors: result.team0_survivors,
            team1_survivors: result.team1_survivors,
        });

        let (p1, p2) = two_players_mut(players, p1_id, p2_id);
        if result.is_draw {
            p1.take_damage(result.damage_to_loser);
            if !is_ghost {
                p2.take_damage(result.damage_to_loser);
            }
        } else if result.winner_id == p1.player_id {
            p1.win_round();
            if !is_ghost {
                p2.lose_round(result.damage_to_loser);
            }
        } else {
            if !is_ghost {
                p2.win_round();
            }
            p1.lose_round(result.damage_to_loser);
        }
    }

    check_eliminations(players, pool, config, placements, &pre_combat_hp, rng);
    if include_training_rows {
        apply_combat_results_to_training_rows(&combat_results, &row_index_by_player, training_rows);
    }
}

fn augment_selection_phase(
    players: &[PlayerState],
    tag: &str,
    augment_pools: &AugmentPools,
    player_augments: &mut HashMap<usize, Vec<String>>,
    rng: &mut PyRng,
) {
    let Some(pool) = augment_pools.by_round.get(tag) else {
        return;
    };
    if pool.is_empty() {
        return;
    }

    for player_id in alive_ids(players) {
        let chosen = player_augments.entry(player_id).or_default();
        let already: HashSet<&str> = chosen.iter().map(String::as_str).collect();
        let mut available: Vec<String> = pool
            .iter()
            .filter(|name| !already.contains(name.as_str()))
            .cloned()
            .collect();
        if available.is_empty() {
            continue;
        }
        rng.shuffle(&mut available);
        let pick_count = std::cmp::min(3, available.len());
        let choice_idx = rng.randrange_usize_stop(pick_count);
        chosen.push(available[choice_idx].clone());
    }
}

fn collect_training_rows_precombat(
    game_id: i64,
    round_num: i32,
    players: &[PlayerState],
    player_augments: &HashMap<usize, Vec<String>>,
    config: &GameConfig,
    matchups: &[(usize, usize, bool)],
    training_rows: &mut Vec<TrainingRow>,
) -> HashMap<usize, usize> {
    let alive_count = alive_count(players) as i32;
    let alive_players = players.iter().filter(|player| player.alive).count();
    let mut players_by_id: HashMap<usize, &PlayerState> = HashMap::with_capacity(alive_players);
    for player in players {
        if player.alive {
            players_by_id.insert(player.player_id, player);
        }
    }

    let mut opponent_by_player: HashMap<usize, usize> = HashMap::with_capacity(matchups.len() * 2);
    let mut is_ghost_by_player: HashMap<usize, bool> = HashMap::with_capacity(matchups.len() * 2);
    for (p1_id, p2_id, is_ghost) in matchups.iter().copied() {
        opponent_by_player.insert(p1_id, p2_id);
        is_ghost_by_player.insert(p1_id, is_ghost);
        if !is_ghost {
            opponent_by_player.insert(p2_id, p1_id);
            is_ghost_by_player.insert(p2_id, false);
        }
    }

    let mut row_index_by_player: HashMap<usize, usize> = HashMap::with_capacity(alive_players);
    training_rows.reserve(alive_players);
    for player in players {
        if !player.alive {
            continue;
        }

        let opponent_state = opponent_by_player
            .get(&player.player_id)
            .and_then(|opponent_id| players_by_id.get(opponent_id).copied());
        let player_traits = player.active_traits(config);

        let board_len = player.board.len();
        let mut units: Vec<TrainingUnitSnapshot> = Vec::with_capacity(board_len);
        let mut board_names: Vec<String> = Vec::with_capacity(board_len);
        let mut board_stars: Vec<i32> = Vec::with_capacity(board_len);
        for (pos, champ) in &player.board {
            let hex_pos = pos.0 * config.board_cols + pos.1;
            units.push(TrainingUnitSnapshot {
                champion_id: champ.api_name.clone(),
                star_level: champ.star_level,
                items: champ.items.clone(),
                position: hex_pos,
            });
            board_names.push(champ.name.clone());
            board_stars.push(champ.star_level);
        }

        let mut opponent_units: Vec<TrainingUnitSnapshot> = Vec::new();
        let mut opponent_traits: HashMap<String, i32> = HashMap::new();
        let mut opponent_hp = 0_i32;
        let mut opponent_gold = 0_i32;
        let mut opponent_level = 0_i32;
        let mut opponent_win_streak = 0_i32;
        let mut opponent_loss_streak = 0_i32;
        let mut opponent_streak = 0_i32;
        let mut opponent_board_count = 0_i32;
        let mut opponent_augments: Vec<String> = Vec::new();
        let mut opponent_num_augments = 0_i32;
        let mut opponent_num_traits = 0_i32;
        if let Some(opponent) = opponent_state {
            opponent_units = Vec::with_capacity(opponent.board.len());
            for (pos, champ) in &opponent.board {
                let hex_pos = pos.0 * config.board_cols + pos.1;
                opponent_units.push(TrainingUnitSnapshot {
                    champion_id: champ.api_name.clone(),
                    star_level: champ.star_level,
                    items: champ.items.clone(),
                    position: hex_pos,
                });
            }
            opponent_traits = opponent.active_traits(config);
            opponent_hp = opponent.hp;
            opponent_gold = opponent.gold;
            opponent_level = opponent.level;
            opponent_win_streak = opponent.win_streak;
            opponent_loss_streak = opponent.loss_streak;
            opponent_streak = opponent_win_streak - opponent_loss_streak;
            opponent_board_count = opponent.board_count() as i32;
            opponent_augments = player_augments
                .get(&opponent.player_id)
                .cloned()
                .unwrap_or_default();
            opponent_num_augments = opponent_augments.len() as i32;
            opponent_num_traits = opponent_traits.len() as i32;
        }

        let streak = player.win_streak - player.loss_streak;
        let mut trait_names = Vec::with_capacity(player_traits.len());
        let mut trait_counts = Vec::with_capacity(player_traits.len());
        for (trait_name, trait_count) in &player_traits {
            trait_names.push(trait_name.clone());
            trait_counts.push(*trait_count);
        }

        let augments = player_augments
            .get(&player.player_id)
            .cloned()
            .unwrap_or_default();

        let row_index = training_rows.len();
        training_rows.push(TrainingRow {
            game_id,
            round: round_num,
            player_id: player.player_id as i32,
            placement: 0,
            hp: player.hp,
            gold: player.gold,
            level: player.level,
            streak,
            board_count: player.board_count() as i32,
            win_streak: player.win_streak,
            loss_streak: player.loss_streak,
            num_augments: augments.len() as i32,
            num_traits: player_traits.len() as i32,
            alive_count,
            units,
            traits: player_traits,
            augments,
            opponent_units,
            opponent_traits,
            opponent_hp,
            opponent_gold,
            opponent_level,
            opponent_streak,
            opponent_board_count,
            opponent_win_streak,
            opponent_loss_streak,
            opponent_num_augments,
            opponent_num_traits,
            opponent_augments,
            combat_result: None,
            damage_dealt: 0.0,
            damage_taken: 0.0,
            combat_time: 0.0,
            survivors: 0,
            is_ghost: is_ghost_by_player
                .get(&player.player_id)
                .copied()
                .unwrap_or(false),
            board_names,
            board_stars,
            trait_names,
            trait_counts,
        });
        row_index_by_player.insert(player.player_id, row_index);
    }
    row_index_by_player
}

fn apply_combat_results_to_training_rows(
    combat_results: &[CombatRoundSnapshot],
    row_index_by_player: &HashMap<usize, usize>,
    training_rows: &mut [TrainingRow],
) {
    for combat in combat_results {
        let update = |training_rows: &mut [TrainingRow], player_id: usize, survivors: i32| {
            let Some(row_idx) = row_index_by_player.get(&player_id).copied() else {
                return;
            };
            let row = &mut training_rows[row_idx];

            let (combat_result, damage_dealt, damage_taken) = if combat.is_draw {
                (2_i32, 0.0_f64, combat.damage as f64)
            } else if combat.winner == player_id {
                (1_i32, combat.damage as f64, 0.0_f64)
            } else {
                (0_i32, 0.0_f64, combat.damage as f64)
            };

            row.combat_result = Some(combat_result);
            row.damage_dealt = damage_dealt;
            row.damage_taken = damage_taken;
            row.combat_time = combat.combat_time;
            row.survivors = survivors;
        };

        update(training_rows, combat.p1, combat.team0_survivors);
        if !combat.is_ghost {
            update(training_rows, combat.p2, combat.team1_survivors);
        }
    }
}

fn check_eliminations(
    players: &mut [PlayerState],
    pool: &mut ChampionPool,
    config: &GameConfig,
    placements: &mut Vec<(usize, i32)>,
    pre_combat_hp: &HashMap<usize, i32>,
    rng: &mut PyRng,
) {
    let newly_dead: Vec<usize> = players
        .iter()
        .filter(|player| !player.alive && player.placement == 0)
        .map(|player| player.player_id)
        .collect();
    if newly_dead.is_empty() {
        return;
    }

    let mut ranked_dead: Vec<(usize, i32, i32, u64)> = newly_dead
        .into_iter()
        .map(|player_id| {
            let elimination_hp = players[player_id].elimination_hp;
            let prior_hp = *pre_combat_hp
                .get(&player_id)
                .unwrap_or(&players[player_id].hp);
            let random_tiebreak = rng.random_u64();
            (player_id, elimination_hp, prior_hp, random_tiebreak)
        })
        .collect();

    ranked_dead.sort_by(|a, b| {
        b.1.cmp(&a.1)
            .then_with(|| b.2.cmp(&a.2))
            .then_with(|| b.3.cmp(&a.3))
    });

    let mut placement = (alive_count(players) as i32) + 1;
    for (player_id, _, _, _) in ranked_dead {
        let champs = players[player_id].all_champions();
        players[player_id].placement = placement;
        placements.push((player_id, placement));
        pool.return_player_champions(&champs, config);
        placement += 1;
    }
}

fn matchmake(
    alive_ids: &[usize],
    matchmaking_weights: &mut [Vec<i32>],
    rng: &mut PyRng,
) -> Vec<(usize, usize, bool)> {
    let mut alive = alive_ids.to_vec();
    rng.shuffle(&mut alive);

    let mut paired: HashSet<usize> = HashSet::new();
    let mut matchups: Vec<(usize, usize, bool)> = Vec::new();

    for player_id in alive.iter().copied() {
        if paired.contains(&player_id) {
            continue;
        }

        let candidates: Vec<usize> = alive
            .iter()
            .copied()
            .filter(|candidate| *candidate != player_id && !paired.contains(candidate))
            .collect();
        if candidates.is_empty() {
            let others: Vec<usize> = alive
                .iter()
                .copied()
                .filter(|candidate| *candidate != player_id)
                .collect();
            if others.is_empty() {
                continue;
            }
            let ghost = others[rng.randrange_usize_stop(others.len())];
            paired.insert(player_id);
            matchups.push((player_id, ghost, true));
            continue;
        }

        let mut weights: Vec<i32> = candidates
            .iter()
            .map(|candidate| matchmaking_weights[player_id][*candidate])
            .collect();
        if weights.iter().all(|w| *w <= 0) {
            weights.fill(1);
        }
        let pick_idx = sample_weighted_i32(&weights, rng)
            .unwrap_or_else(|| rng.randrange_usize_stop(candidates.len()));
        let opponent_id = candidates[pick_idx];

        paired.insert(player_id);
        paired.insert(opponent_id);
        matchups.push((player_id, opponent_id, false));

        matchmaking_weights[player_id][opponent_id] = 0;
        matchmaking_weights[opponent_id][player_id] = 0;
        for other in alive.iter().copied() {
            if other != player_id && other != opponent_id {
                matchmaking_weights[player_id][other] += 3;
                matchmaking_weights[opponent_id][other] += 3;
            }
        }
    }

    matchups
}

fn resolve_combat(
    round_num: i32,
    p1: &PlayerState,
    p2: &PlayerState,
    p1_augments: &[String],
    p2_augments: &[String],
    engine: &mut CombatEngine,
    config: &GameConfig,
    rng: &mut PyRng,
) -> RoundOutcome {
    let team0 = build_team_specs(p1, 0, false, config);
    let team1 = build_team_specs(p2, 1, true, config);

    if team0.is_empty() && team1.is_empty() {
        let damage = round_damage(round_num, 0, config);
        return RoundOutcome {
            winner_id: p1.player_id,
            damage_to_loser: damage,
            is_draw: true,
            combat_time: 0.0,
            team0_survivors: 0,
            team1_survivors: 0,
        };
    }
    if team0.is_empty() {
        let survivors = team1.len() as i32;
        let damage = round_damage(round_num, survivors, config);
        return RoundOutcome {
            winner_id: p2.player_id,
            damage_to_loser: damage,
            is_draw: false,
            combat_time: 0.0,
            team0_survivors: 0,
            team1_survivors: survivors,
        };
    }
    if team1.is_empty() {
        let survivors = team0.len() as i32;
        let damage = round_damage(round_num, survivors, config);
        return RoundOutcome {
            winner_id: p1.player_id,
            damage_to_loser: damage,
            is_draw: false,
            combat_time: 0.0,
            team0_survivors: survivors,
            team1_survivors: 0,
        };
    }

    engine.rng = rng.clone();
    let result = engine.run_combat(
        team0,
        team1,
        if p1_augments.is_empty() {
            None
        } else {
            Some(p1_augments.to_vec())
        },
        if p2_augments.is_empty() {
            None
        } else {
            Some(p2_augments.to_vec())
        },
        None,
    );
    *rng = engine.rng.clone();

    if result.winner == 0 {
        let damage = round_damage(round_num, result.team0_survivors, config);
        RoundOutcome {
            winner_id: p1.player_id,
            damage_to_loser: damage,
            is_draw: false,
            combat_time: result.combat_time,
            team0_survivors: result.team0_survivors,
            team1_survivors: result.team1_survivors,
        }
    } else {
        let damage = round_damage(round_num, result.team1_survivors, config);
        RoundOutcome {
            winner_id: p2.player_id,
            damage_to_loser: damage,
            is_draw: false,
            combat_time: result.combat_time,
            team0_survivors: result.team0_survivors,
            team1_survivors: result.team1_survivors,
        }
    }
}

fn build_team_specs(
    player: &PlayerState,
    team: i32,
    mirror_rows: bool,
    config: &GameConfig,
) -> Vec<UnitSpec> {
    let mut specs: Vec<UnitSpec> = Vec::new();
    for (pos, champ) in &player.board {
        let mut row = pos.0;
        let col = pos.1;
        if mirror_rows {
            row = config.board_rows - 1 - row;
        }

        specs.push(UnitSpec {
            api_name: champ.api_name.clone(),
            star_level: champ.star_level,
            position: vec![row, col],
            team,
            items: champ.items.clone(),
            traits: Vec::new(),
        });
    }
    specs
}

fn run_agent(
    player: &mut PlayerState,
    pool: &mut ChampionPool,
    config: &GameConfig,
    style: AgentStyle,
    rng: &mut PyRng,
) {
    let mut consecutive_fails = 0;
    for _ in 0..10 {
        let action_roll = rng.randrange_i32_stop(100);
        let success = match style {
            AgentStyle::Random => {
                if action_roll < 56 {
                    try_buy(player, pool, config, rng)
                } else if action_roll < 82 {
                    player.buy_xp(config)
                } else {
                    try_refresh(player, pool, config, rng)
                }
            }
            AgentStyle::Econ => {
                if player.gold < 20 {
                    if action_roll < 70 {
                        try_buy(player, pool, config, rng)
                    } else {
                        false
                    }
                } else if action_roll < 45 {
                    player.buy_xp(config)
                } else if action_roll < 65 {
                    try_refresh(player, pool, config, rng)
                } else {
                    try_buy(player, pool, config, rng)
                }
            }
            AgentStyle::Slam => {
                if action_roll < 68 {
                    try_buy(player, pool, config, rng)
                } else if action_roll < 88 {
                    try_refresh(player, pool, config, rng)
                } else {
                    player.buy_xp(config)
                }
            }
        };

        if success {
            consecutive_fails = 0;
        } else {
            consecutive_fails += 1;
            if consecutive_fails >= 5 {
                break;
            }
        }
    }
}

fn try_buy(
    player: &mut PlayerState,
    pool: &mut ChampionPool,
    config: &GameConfig,
    rng: &mut PyRng,
) -> bool {
    if player.find_empty_bench().is_none() {
        return false;
    }
    let mut slots: Vec<usize> = Vec::new();
    for (idx, entry) in player.shop.iter().enumerate() {
        let Some(name) = entry else { continue };
        let cost = *config.name_to_cost.get(name).unwrap_or(&1);
        if player.gold >= cost {
            slots.push(idx);
        }
    }
    if slots.is_empty() {
        return false;
    }
    let slot = slots[rng.randrange_usize_stop(slots.len())];
    player.buy_champion(slot, pool, config)
}

fn try_refresh(
    player: &mut PlayerState,
    pool: &mut ChampionPool,
    config: &GameConfig,
    rng: &mut PyRng,
) -> bool {
    if !player.can_afford(config.refresh_cost) {
        return false;
    }
    return_shop_to_pool(player, pool, config);
    player.gold -= config.refresh_cost;
    player.shop = pool.roll_shop(player.level, config, rng);
    true
}

fn assign_agent_styles(
    num_players: usize,
    mix: Option<&HashMap<String, i32>>,
    rng: &mut PyRng,
) -> Vec<AgentStyle> {
    let Some(mix) = mix else {
        return vec![AgentStyle::Random; num_players];
    };

    let mut entries: Vec<(AgentStyle, i32)> = Vec::new();
    let random_weight = *mix.get("random").unwrap_or(&0);
    let econ_weight = *mix.get("econ").unwrap_or(&0);
    let slam_weight = *mix.get("slam").unwrap_or(&0);
    if random_weight > 0 {
        entries.push((AgentStyle::Random, random_weight));
    }
    if econ_weight > 0 {
        entries.push((AgentStyle::Econ, econ_weight));
    }
    if slam_weight > 0 {
        entries.push((AgentStyle::Slam, slam_weight));
    }
    if entries.is_empty() {
        return vec![AgentStyle::Random; num_players];
    }

    let weights: Vec<i32> = entries.iter().map(|(_, weight)| *weight).collect();
    let mut styles = Vec::with_capacity(num_players);
    for _ in 0..num_players {
        let idx = sample_weighted_i32(&weights, rng).unwrap_or(0);
        styles.push(entries[idx].0);
    }
    styles
}

fn carousel_phase(
    round_num: i32,
    players: &mut [PlayerState],
    pool: &mut ChampionPool,
    config: &GameConfig,
    rng: &mut PyRng,
) {
    let mut pick_order = alive_ids(players);
    pick_order.sort_by(|a, b| {
        let pa = &players[*a];
        let pb = &players[*b];
        pa.hp
            .cmp(&pb.hp)
            .then_with(|| pa.player_id.cmp(&pb.player_id))
    });

    let cost_odds = config
        .carousel_champion_odds
        .get(&round_num)
        .cloned()
        .unwrap_or_else(|| vec![0.5, 0.3, 0.2, 0.0, 0.0]);

    let mut carousel: Vec<(String, i32, String)> = Vec::new();
    for _ in 0..config.carousel_size {
        let cost_idx = sample_weighted_f64(&cost_odds, rng).unwrap_or(0);
        let cost = (cost_idx + 1) as i32;
        let Some(champs) = config.champions_by_cost.get(&cost) else {
            continue;
        };
        let Some(ordered_names) = config.champion_names_by_cost.get(&cost) else {
            continue;
        };
        let available_names: Vec<&String> = ordered_names
            .iter()
            .filter(|name| champs.contains_key(*name) && pool.available(name.as_str()) > 0)
            .collect();
        if available_names.is_empty() {
            continue;
        }
        let champ_name = available_names[rng.randrange_usize_stop(available_names.len())].clone();
        if config.carousel_item_weights.is_empty() {
            continue;
        }
        let item_weights: Vec<i32> = config
            .carousel_item_weights
            .iter()
            .map(|(_, weight)| *weight)
            .collect();
        let item_idx = sample_weighted_i32(&item_weights, rng)
            .unwrap_or_else(|| rng.randrange_usize_stop(config.carousel_item_weights.len()));
        let item = config.carousel_item_weights[item_idx].0.clone();
        carousel.push((champ_name, cost, item));
    }

    if carousel.is_empty() {
        return;
    }

    for player_id in pick_order {
        if carousel.is_empty() {
            break;
        }
        let pick_idx = rng.randrange_usize_stop(carousel.len());
        let (champ_name, cost, item) = carousel.swap_remove(pick_idx);

        let player = &mut players[player_id];
        let Some(bench_idx) = player.find_empty_bench() else {
            continue;
        };
        if !pool.take(&champ_name) {
            continue;
        }

        let mut champ = ChampionInstance {
            name: champ_name.clone(),
            api_name: config
                .name_to_api
                .get(&champ_name)
                .cloned()
                .unwrap_or_else(|| default_api_name(&champ_name)),
            cost,
            star_level: 1,
            items: Vec::new(),
        };
        if champ.items.len() < config.max_items_per_unit {
            champ.items.push(item);
        }

        player.bench[bench_idx] = Some(champ);
        player.check_upgrade(&champ_name, config);
    }
}

fn build_placement_rows(
    players: &[PlayerState],
    placements: &[(usize, i32)],
    player_augments: &HashMap<usize, Vec<String>>,
    config: &GameConfig,
) -> Vec<Value> {
    let mut rows = Vec::with_capacity(placements.len());
    for (player_id, placement) in placements {
        let player = &players[*player_id];
        let mut board: Vec<Value> = Vec::new();
        for champ in player.board.values() {
            board.push(json!({
                "name": champ.name,
                "api_name": champ.api_name,
                "star": champ.star_level,
                "items": champ.items,
            }));
        }
        rows.push(json!({
            "player_id": *player_id,
            "placement": *placement,
            "level": player.level,
            "hp": player.hp,
            "board": board,
            "traits": player.active_traits(config),
            "augments": player_augments.get(player_id).cloned().unwrap_or_default(),
        }));
    }
    rows
}

fn build_analytics(placements: &[Value]) -> Value {
    let mut comp_placements: Vec<Value> = Vec::new();
    let mut augment_placements: Vec<Value> = Vec::new();
    let mut champion_placements: Vec<Value> = Vec::new();

    for entry in placements {
        let placement = entry
            .get("placement")
            .and_then(Value::as_i64)
            .unwrap_or(0_i64) as i32;

        let mut comp: Vec<String> = entry
            .get("board")
            .and_then(Value::as_array)
            .map(|units| {
                units
                    .iter()
                    .filter_map(|unit| unit.get("name").and_then(Value::as_str).map(str::to_string))
                    .collect::<Vec<_>>()
            })
            .unwrap_or_default();
        comp.sort();
        comp_placements.push(json!([comp, placement]));

        if let Some(augs) = entry.get("augments").and_then(Value::as_array) {
            for aug in augs {
                if let Some(name) = aug.as_str() {
                    augment_placements.push(json!([name, placement]));
                }
            }
        }

        if let Some(board) = entry.get("board").and_then(Value::as_array) {
            for unit in board {
                if let Some(name) = unit.get("name").and_then(Value::as_str) {
                    champion_placements.push(json!([name, placement]));
                }
            }
        }
    }

    json!({
        "comp_placements": comp_placements,
        "augment_placements": augment_placements,
        "champion_placements": champion_placements,
    })
}

fn return_shop_to_pool(player: &mut PlayerState, pool: &mut ChampionPool, config: &GameConfig) {
    for slot in &mut player.shop {
        if let Some(name) = slot.take() {
            pool.return_champion(&name, 1, config);
        }
    }
}

fn round_damage(round_num: i32, surviving_units: i32, config: &GameConfig) -> i32 {
    let mut base = 0;
    for (max_round, damage) in &config.round_base_damage {
        if round_num <= *max_round {
            base = *damage;
            break;
        }
    }
    let capped_idx = std::cmp::min(
        std::cmp::max(0, surviving_units) as usize,
        config.damage_per_unit.len().saturating_sub(1),
    );
    base + config.damage_per_unit[capped_idx]
}

fn streak_gold(streak: i32) -> i32 {
    if streak >= 5 {
        3
    } else if streak >= 4 {
        2
    } else if streak >= 2 {
        1
    } else {
        0
    }
}

fn alive_count(players: &[PlayerState]) -> usize {
    players.iter().filter(|player| player.alive).count()
}

fn alive_ids(players: &[PlayerState]) -> Vec<usize> {
    players
        .iter()
        .filter(|player| player.alive)
        .map(|player| player.player_id)
        .collect()
}

fn two_players_mut(
    players: &mut [PlayerState],
    a: usize,
    b: usize,
) -> (&mut PlayerState, &mut PlayerState) {
    assert!(a != b);
    if a < b {
        let (left, right) = players.split_at_mut(b);
        (&mut left[a], &mut right[0])
    } else {
        let (left, right) = players.split_at_mut(a);
        (&mut right[0], &mut left[b])
    }
}

fn sample_weighted_i32(weights: &[i32], rng: &mut PyRng) -> Option<usize> {
    let total: f64 = weights.iter().map(|w| std::cmp::max(0, *w) as f64).sum();
    if total <= 0.0 {
        return None;
    }

    let roll = rng.random() * total;
    let mut cumulative = 0.0_f64;
    let mut last_nonzero: Option<usize> = None;
    for (idx, weight) in weights.iter().enumerate() {
        let clamped = std::cmp::max(0, *weight);
        if clamped == 0 {
            continue;
        }
        cumulative += clamped as f64;
        last_nonzero = Some(idx);
        if roll < cumulative {
            return Some(idx);
        }
    }

    last_nonzero
}

fn sample_weighted_f64(weights: &[f64], rng: &mut PyRng) -> Option<usize> {
    let total: f64 = weights
        .iter()
        .map(|w| if *w > 0.0 { *w } else { 0.0 })
        .sum();
    if total <= 0.0 {
        return None;
    }

    let mut roll = rng.random() * total;
    for (idx, weight) in weights.iter().enumerate() {
        let clamped = if *weight > 0.0 { *weight } else { 0.0 };
        if clamped <= 0.0 {
            continue;
        }
        if roll < clamped {
            return Some(idx);
        }
        roll -= clamped;
    }

    Some(weights.len().saturating_sub(1))
}

fn default_api_name(name: &str) -> String {
    let mut chars = name.chars();
    let Some(first) = chars.next() else {
        return "TFT16_Unknown".to_string();
    };
    let mut value = String::from("TFT16_");
    value.push(first.to_ascii_uppercase());
    value.push_str(chars.as_str());
    value
}
