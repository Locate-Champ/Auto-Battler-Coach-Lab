use crate::engine::{CombatEngine, UnitSpec};
use pyo3::prelude::*;
use rand::rngs::StdRng;
use rand::seq::SliceRandom;
use rand::{Rng, SeedableRng};
use serde::Deserialize;
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

        let mut carousel_item_weights: Vec<(String, i32)> = constants
            .getattr("CAROUSEL_ITEM_WEIGHTS")?
            .extract::<HashMap<String, i32>>()?
            .into_iter()
            .collect();
        carousel_item_weights.sort_by(|a, b| a.0.cmp(&b.0));

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
        self.hp = std::cmp::max(0, self.hp - amount);
        if self.hp <= 0 {
            self.alive = false;
        }
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
        for (cost, champs) in &config.champions_by_cost {
            if *cost == 7 {
                names_by_cost
                    .entry(5)
                    .or_default()
                    .extend(champs.keys().cloned());
            } else {
                names_by_cost
                    .entry(*cost)
                    .or_default()
                    .extend(champs.keys().cloned());
            }
        }
        for names in names_by_cost.values_mut() {
            names.sort();
            names.dedup();
        }

        Self { pool, names_by_cost }
    }

    fn roll_shop(&self, level: i32, config: &GameConfig, rng: &mut StdRng) -> Vec<Option<String>> {
        let level_idx = std::cmp::max(
            0,
            std::cmp::min(level - 1, (config.level_odds.len() as i32) - 1),
        ) as usize;
        let odds = &config.level_odds[level_idx];
        let mut shop = Vec::with_capacity(config.shop_size);

        for _ in 0..config.shop_size {
            let cost_idx = sample_weighted_f64(odds, rng).unwrap_or(0);
            let cost = (cost_idx + 1) as i32;
            shop.push(self.pick_from_tier(cost, rng));
        }

        shop
    }

    fn pick_from_tier(&self, cost: i32, rng: &mut StdRng) -> Option<String> {
        let names = self.names_by_cost.get(&cost)?;
        let total: i32 = names
            .iter()
            .map(|name| std::cmp::max(0, *self.pool.get(name).unwrap_or(&0)))
            .sum();
        if total <= 0 {
            return None;
        }

        let mut roll = rng.gen_range(0..total);
        for name in names {
            let weight = std::cmp::max(0, *self.pool.get(name).unwrap_or(&0));
            if weight <= 0 {
                continue;
            }
            if roll < weight {
                return Some(name.clone());
            }
            roll -= weight;
        }

        None
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
}

#[derive(Clone, Copy)]
enum AgentStyle {
    Random,
    Econ,
    Slam,
}

#[derive(Clone)]
struct BoardUnitSnapshot {
    name: String,
    api_name: String,
    star: i32,
    items: Vec<String>,
    pos: (i32, i32),
}

#[derive(Clone)]
struct PlayerRoundSnapshot {
    id: usize,
    hp: i32,
    gold: i32,
    level: i32,
    board: Vec<BoardUnitSnapshot>,
    board_count: i32,
    traits: HashMap<String, i32>,
    augments: Vec<String>,
    win_streak: i32,
    loss_streak: i32,
}

#[derive(Clone)]
struct CombatRoundSnapshot {
    p1: usize,
    p2: usize,
    winner: usize,
    damage: i32,
    survivors: i32,
    time: f64,
}

struct RoundSnapshot {
    round: i32,
    alive_count: i32,
    players: Vec<PlayerRoundSnapshot>,
    combats: Vec<CombatRoundSnapshot>,
}

struct RoundOutcome {
    winner_id: usize,
    loser_id: usize,
    survivors: i32,
    combat_time: f64,
    damage_to_loser: i32,
    is_draw: bool,
}

pub struct GameRunOutput {
    pub rounds: i32,
    pub placements: Vec<Value>,
    pub training_rows: Vec<Value>,
    pub analytics: Value,
}

pub fn run_game(
    engine: &mut CombatEngine,
    config: &GameConfig,
    augment_pools: &AugmentPools,
    game_id: i64,
    seed: u64,
    agent_mix: Option<HashMap<String, i32>>,
    include_training_rows: bool,
) -> Result<GameRunOutput, String> {
    let mut rng = StdRng::seed_from_u64(seed);
    let mut pool = ChampionPool::new(config);
    let mut players: Vec<PlayerState> = (0..DEFAULT_NUM_PLAYERS)
        .map(|player_id| PlayerState::new(player_id, config))
        .collect();
    let mut player_augments: HashMap<usize, Vec<String>> = (0..DEFAULT_NUM_PLAYERS)
        .map(|player_id| (player_id, Vec::new()))
        .collect();
    let player_styles = assign_agent_styles(DEFAULT_NUM_PLAYERS, agent_mix.as_ref(), &mut rng);
    let mut matchmaking_weights = vec![vec![10_i32; DEFAULT_NUM_PLAYERS]; DEFAULT_NUM_PLAYERS];
    for idx in 0..DEFAULT_NUM_PLAYERS {
        matchmaking_weights[idx][idx] = 0;
    }

    let mut round_num: i32 = 0;
    let mut placements: Vec<(usize, i32)> = Vec::new();
    let mut round_snapshots: Vec<RoundSnapshot> = Vec::new();

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
            &mut round_snapshots,
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
    let training_rows = if include_training_rows {
        let placement_map: HashMap<usize, i32> = placements.iter().copied().collect();
        build_training_rows(game_id, &round_snapshots, &placement_map, config)
    } else {
        Vec::new()
    };
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
    rng: &mut StdRng,
) {
    let ids = alive_ids(players);
    for player_id in ids {
        let style = player_styles[player_id];
        let player = &mut players[player_id];
        player.add_income(round_num, config);

        let (min_drop, max_drop) = config.pve_item_drops.get(&round_num).copied().unwrap_or((0, 0));
        if min_drop <= max_drop && !config.item_components.is_empty() {
            let drops = rng.gen_range(min_drop..=max_drop);
            for _ in 0..drops {
                if player.item_bench.len() >= config.item_bench_size {
                    break;
                }
                let idx = rng.gen_range(0..config.item_components.len());
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
    round_snapshots: &mut Vec<RoundSnapshot>,
    include_training_rows: bool,
    rng: &mut StdRng,
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
    let mut combat_results: Vec<CombatRoundSnapshot> = Vec::new();

    for (p1_id, p2_id, is_ghost) in matchups {
        if !players[p1_id].alive {
            continue;
        }

        let p1_augments = player_augments.get(&p1_id).cloned().unwrap_or_default();
        let p2_augments = player_augments.get(&p2_id).cloned().unwrap_or_default();

        let combat_seed = rng.gen::<u64>();
        let result = resolve_combat(
            round_num,
            &players[p1_id],
            &players[p2_id],
            &p1_augments,
            &p2_augments,
            combat_seed,
            engine,
            config,
        );

        combat_results.push(CombatRoundSnapshot {
            p1: p1_id,
            p2: p2_id,
            winner: result.winner_id,
            damage: result.damage_to_loser,
            survivors: result.survivors,
            time: result.combat_time,
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

    check_eliminations(players, pool, config, placements);
    if include_training_rows {
        collect_round_snapshot(
            round_num,
            players,
            player_augments,
            config,
            combat_results,
            round_snapshots,
        );
    }
}

fn augment_selection_phase(
    players: &[PlayerState],
    tag: &str,
    augment_pools: &AugmentPools,
    player_augments: &mut HashMap<usize, Vec<String>>,
    rng: &mut StdRng,
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
        available.shuffle(rng);
        let pick_count = std::cmp::min(3, available.len());
        let choice_idx = rng.gen_range(0..pick_count);
        chosen.push(available[choice_idx].clone());
    }
}

fn collect_round_snapshot(
    round_num: i32,
    players: &[PlayerState],
    player_augments: &HashMap<usize, Vec<String>>,
    config: &GameConfig,
    combat_results: Vec<CombatRoundSnapshot>,
    snapshots: &mut Vec<RoundSnapshot>,
) {
    let alive_count = alive_count(players) as i32;
    let mut player_snapshots: Vec<PlayerRoundSnapshot> = Vec::new();

    for player in players {
        if !player.alive {
            continue;
        }
        let mut board_units: Vec<BoardUnitSnapshot> = Vec::new();
        for (pos, champ) in &player.board {
            board_units.push(BoardUnitSnapshot {
                name: champ.name.clone(),
                api_name: champ.api_name.clone(),
                star: champ.star_level,
                items: champ.items.clone(),
                pos: *pos,
            });
        }

        player_snapshots.push(PlayerRoundSnapshot {
            id: player.player_id,
            hp: player.hp,
            gold: player.gold,
            level: player.level,
            board: board_units,
            board_count: player.board_count() as i32,
            traits: player.active_traits(config),
            augments: player_augments
                .get(&player.player_id)
                .cloned()
                .unwrap_or_default(),
            win_streak: player.win_streak,
            loss_streak: player.loss_streak,
        });
    }

    snapshots.push(RoundSnapshot {
        round: round_num,
        alive_count,
        players: player_snapshots,
        combats: combat_results,
    });
}

fn check_eliminations(
    players: &mut [PlayerState],
    pool: &mut ChampionPool,
    config: &GameConfig,
    placements: &mut Vec<(usize, i32)>,
) {
    let newly_dead: Vec<usize> = players
        .iter()
        .filter(|player| !player.alive && player.placement == 0)
        .map(|player| player.player_id)
        .collect();
    if newly_dead.is_empty() {
        return;
    }

    let placement = (alive_count(players) as i32) + 1;
    for player_id in newly_dead {
        let champs = players[player_id].all_champions();
        players[player_id].placement = placement;
        placements.push((player_id, placement));
        pool.return_player_champions(&champs, config);
    }
}

fn matchmake(
    alive_ids: &[usize],
    matchmaking_weights: &mut [Vec<i32>],
    rng: &mut StdRng,
) -> Vec<(usize, usize, bool)> {
    let mut alive = alive_ids.to_vec();
    alive.shuffle(rng);

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
            let ghost = others[rng.gen_range(0..others.len())];
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
            .unwrap_or_else(|| rng.gen_range(0..candidates.len()));
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
    seed: u64,
    engine: &mut CombatEngine,
    config: &GameConfig,
) -> RoundOutcome {
    let team0 = build_team_specs(p1, 0, false, config);
    let team1 = build_team_specs(p2, 1, true, config);

    if team0.is_empty() && team1.is_empty() {
        let damage = round_damage(round_num, 0, config);
        return RoundOutcome {
            winner_id: p1.player_id,
            loser_id: p2.player_id,
            survivors: 0,
            combat_time: 0.0,
            damage_to_loser: damage,
            is_draw: true,
        };
    }
    if team0.is_empty() {
        let survivors = team1.len() as i32;
        let damage = round_damage(round_num, survivors, config);
        return RoundOutcome {
            winner_id: p2.player_id,
            loser_id: p1.player_id,
            survivors,
            combat_time: 0.0,
            damage_to_loser: damage,
            is_draw: false,
        };
    }
    if team1.is_empty() {
        let survivors = team0.len() as i32;
        let damage = round_damage(round_num, survivors, config);
        return RoundOutcome {
            winner_id: p1.player_id,
            loser_id: p2.player_id,
            survivors,
            combat_time: 0.0,
            damage_to_loser: damage,
            is_draw: false,
        };
    }

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
        Some(seed),
    );

    if result.winner == 0 {
        let damage = round_damage(round_num, result.team0_survivors, config);
        RoundOutcome {
            winner_id: p1.player_id,
            loser_id: p2.player_id,
            survivors: result.team0_survivors,
            combat_time: result.combat_time,
            damage_to_loser: damage,
            is_draw: false,
        }
    } else {
        let damage = round_damage(round_num, result.team1_survivors, config);
        RoundOutcome {
            winner_id: p2.player_id,
            loser_id: p1.player_id,
            survivors: result.team1_survivors,
            combat_time: result.combat_time,
            damage_to_loser: damage,
            is_draw: false,
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
    rng: &mut StdRng,
) {
    let mut consecutive_fails = 0;
    for _ in 0..10 {
        let action_roll = rng.gen_range(0..100);
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
    rng: &mut StdRng,
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
    let slot = slots[rng.gen_range(0..slots.len())];
    player.buy_champion(slot, pool, config)
}

fn try_refresh(
    player: &mut PlayerState,
    pool: &mut ChampionPool,
    config: &GameConfig,
    rng: &mut StdRng,
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
    rng: &mut StdRng,
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
    rng: &mut StdRng,
) {
    let mut pick_order = alive_ids(players);
    pick_order.sort_by(|a, b| {
        let pa = &players[*a];
        let pb = &players[*b];
        pa.hp.cmp(&pb.hp).then_with(|| pa.player_id.cmp(&pb.player_id))
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
        if champs.is_empty() {
            continue;
        }
        let mut names: Vec<&String> = champs.keys().collect();
        names.sort();
        let champ_name = names[rng.gen_range(0..names.len())].clone().to_string();
        if config.carousel_item_weights.is_empty() {
            continue;
        }
        let item_weights: Vec<i32> = config
            .carousel_item_weights
            .iter()
            .map(|(_, weight)| *weight)
            .collect();
        let item_idx = sample_weighted_i32(&item_weights, rng)
            .unwrap_or_else(|| rng.gen_range(0..config.carousel_item_weights.len()));
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
        let pick_idx = rng.gen_range(0..carousel.len());
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

fn build_training_rows(
    game_id: i64,
    rounds: &[RoundSnapshot],
    placement_map: &HashMap<usize, i32>,
    config: &GameConfig,
) -> Vec<Value> {
    let mut rows: Vec<Value> = Vec::new();

    for round_data in rounds {
        let mut players_by_id: HashMap<usize, &PlayerRoundSnapshot> = HashMap::new();
        for player in &round_data.players {
            players_by_id.insert(player.id, player);
        }

        let mut combat_by_player: HashMap<usize, Value> = HashMap::new();
        for combat in &round_data.combats {
            let is_draw = combat.winner != combat.p1 && combat.winner != combat.p2;
            for (player_id, opponent_id) in [(combat.p1, combat.p2), (combat.p2, combat.p1)] {
                let (combat_result, damage_dealt, damage_taken) = if is_draw {
                    (2_i32, 0.0_f64, combat.damage as f64)
                } else if combat.winner == player_id {
                    (1_i32, combat.damage as f64, 0.0_f64)
                } else {
                    (0_i32, 0.0_f64, combat.damage as f64)
                };

                combat_by_player.insert(
                    player_id,
                    json!({
                        "opponent_id": opponent_id,
                        "combat_result": combat_result,
                        "damage_dealt": damage_dealt,
                        "damage_taken": damage_taken,
                    }),
                );
            }
        }

        for player in &round_data.players {
            let matchup = combat_by_player.get(&player.id);
            let opponent_id = matchup
                .and_then(|m| m.get("opponent_id"))
                .and_then(Value::as_u64)
                .map(|v| v as usize);
            let opponent_state = opponent_id.and_then(|id| players_by_id.get(&id).copied());

            let mut units: Vec<Value> = Vec::new();
            for unit in &player.board {
                let hex_pos = unit.pos.0 * config.board_cols + unit.pos.1;
                units.push(json!({
                    "champion_id": unit.api_name,
                    "star_level": unit.star,
                    "items": unit.items,
                    "position": hex_pos,
                }));
            }

            let mut opponent_units: Vec<Value> = Vec::new();
            let mut opponent_traits: HashMap<String, i32> = HashMap::new();
            let mut opponent_hp = 0_i32;
            if let Some(opponent) = opponent_state {
                for unit in &opponent.board {
                    let hex_pos = unit.pos.0 * config.board_cols + unit.pos.1;
                    opponent_units.push(json!({
                        "champion_id": unit.api_name,
                        "star_level": unit.star,
                        "items": unit.items,
                        "position": hex_pos,
                    }));
                }
                opponent_traits = opponent.traits.clone();
                opponent_hp = opponent.hp;
            }

            let streak = player.win_streak - player.loss_streak;
            rows.push(json!({
                "game_id": game_id,
                "round": round_data.round,
                "player_id": player.id,
                "placement": placement_map.get(&player.id).copied().unwrap_or(0),
                "hp": player.hp,
                "gold": player.gold,
                "level": player.level,
                "streak": streak,
                "board_count": player.board_count,
                "win_streak": player.win_streak,
                "loss_streak": player.loss_streak,
                "num_augments": player.augments.len(),
                "num_traits": player.traits.len(),
                "alive_count": round_data.alive_count,
                "units": units,
                "traits": player.traits,
                "augments": player.augments,
                "opponent_units": opponent_units,
                "opponent_traits": opponent_traits,
                "opponent_hp": opponent_hp,
                "combat_result": matchup.and_then(|m| m.get("combat_result")).cloned().unwrap_or(Value::Null),
                "damage_dealt": matchup.and_then(|m| m.get("damage_dealt")).cloned().unwrap_or_else(|| json!(0.0)),
                "damage_taken": matchup.and_then(|m| m.get("damage_taken")).cloned().unwrap_or_else(|| json!(0.0)),
                "board_names": player.board.iter().map(|unit| unit.name.clone()).collect::<Vec<_>>(),
                "board_stars": player.board.iter().map(|unit| unit.star).collect::<Vec<_>>(),
                "trait_names": player.traits.keys().cloned().collect::<Vec<_>>(),
                "trait_counts": player.traits.values().copied().collect::<Vec<_>>(),
            }));
        }
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

fn sample_weighted_i32(weights: &[i32], rng: &mut StdRng) -> Option<usize> {
    let total: i32 = weights.iter().map(|w| std::cmp::max(0, *w)).sum();
    if total <= 0 {
        return None;
    }

    let mut roll = rng.gen_range(0..total);
    for (idx, weight) in weights.iter().enumerate() {
        let clamped = std::cmp::max(0, *weight);
        if clamped == 0 {
            continue;
        }
        if roll < clamped {
            return Some(idx);
        }
        roll -= clamped;
    }

    Some(weights.len().saturating_sub(1))
}

fn sample_weighted_f64(weights: &[f64], rng: &mut StdRng) -> Option<usize> {
    let total: f64 = weights
        .iter()
        .map(|w| if *w > 0.0 { *w } else { 0.0 })
        .sum();
    if total <= 0.0 {
        return None;
    }

    let mut roll = rng.gen::<f64>() * total;
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
