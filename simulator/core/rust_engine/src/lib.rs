mod abilities;
mod damage;
mod data;
mod engine;
mod game_loop;
mod hex_grid;
mod items;
mod python_rng;
mod targeting;
/// TFT Combat Engine - Rust implementation with PyO3 bindings.
///
/// This module provides a high-performance combat simulator for Teamfight Tactics,
/// callable from Python via PyO3/maturin.
mod types;
mod unit;

use arrow_array::builder::{BooleanBuilder, Float64Builder, Int64Builder, StringBuilder};
use arrow_array::{ArrayRef, RecordBatch};
use arrow_schema::{DataType, Field, Schema};
use parquet::arrow::ArrowWriter;
use parquet::basic::Compression;
use parquet::file::properties::{EnabledStatistics, WriterProperties};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyList};
use rayon::prelude::*;
use rayon::{ThreadPool, ThreadPoolBuilder};
use serde_json::Value;
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex, OnceLock};
use std::time::Instant;

use data::CombatData;
use engine::{CombatEngine, CombatResult, UnitSpec};
use game_loop::{AugmentPools, CombatDebugRound, GameConfig, TrainingRow};

/// Python-facing combat engine wrapper.
#[pyclass]
struct RustCombatEngine {
    engine: CombatEngine,
}

#[pymethods]
impl RustCombatEngine {
    /// Create a new combat engine, loading champion data from the given path.
    #[new]
    fn new(combat_data_path: &str) -> PyResult<Self> {
        let path = Path::new(combat_data_path);
        let combat_data =
            CombatData::load(path).map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e))?;

        Ok(Self {
            engine: CombatEngine::new(combat_data),
        })
    }

    /// Run a combat simulation.
    ///
    /// Args:
    ///     team0: List of unit spec dicts for team 0.
    ///     team1: List of unit spec dicts for team 1.
    ///     team0_augments: Optional list of augment names for team 0.
    ///     team1_augments: Optional list of augment names for team 1.
    ///     seed: Optional RNG seed for determinism.
    ///
    /// Returns:
    ///     Dict with combat results (winner, combat_time, survivors, damage, etc.)
    #[pyo3(signature = (team0, team1, team0_augments=None, team1_augments=None, seed=None))]
    fn run_combat<'py>(
        &mut self,
        py: Python<'py>,
        team0: &Bound<'py, PyList>,
        team1: &Bound<'py, PyList>,
        team0_augments: Option<Vec<String>>,
        team1_augments: Option<Vec<String>>,
        seed: Option<u64>,
    ) -> PyResult<Bound<'py, PyDict>> {
        let team0_specs = parse_unit_specs(team0)?;
        let team1_specs = parse_unit_specs(team1)?;

        let result = self.engine.run_combat(
            team0_specs,
            team1_specs,
            team0_augments,
            team1_augments,
            seed,
        );

        result_to_dict(py, &result)
    }

    /// Get the number of champions loaded in the combat data.
    fn num_champions(&self) -> usize {
        self.engine.combat_data.champions.len()
    }
}

/// Python-facing full game simulator wrapper.
#[pyclass]
struct RustGameSimulator {
    engine: CombatEngine,
    config: GameConfig,
    augment_pools: AugmentPools,
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum BatchOutputMode {
    Rows,
    Jsonl,
    Parquet,
}

impl BatchOutputMode {
    fn parse(value: &str) -> Result<Self, String> {
        match value {
            "rows" => Ok(Self::Rows),
            "jsonl" => Ok(Self::Jsonl),
            "parquet" => Ok(Self::Parquet),
            _ => Err(format!(
                "Invalid output_mode '{value}'. Expected one of: rows, jsonl, parquet."
            )),
        }
    }
}

struct BatchGameRun {
    game_id: i64,
    seed: i64,
    elapsed: f64,
    output: Result<game_loop::GameRunOutput, String>,
}

static RAYON_POOL_CACHE: OnceLock<Mutex<HashMap<usize, Arc<ThreadPool>>>> = OnceLock::new();

#[pymethods]
impl RustGameSimulator {
    #[new]
    #[pyo3(signature = (combat_data_path, augment_data_path=None))]
    fn new(
        py: Python<'_>,
        combat_data_path: &str,
        augment_data_path: Option<&str>,
    ) -> PyResult<Self> {
        let path = Path::new(combat_data_path);
        let combat_data =
            CombatData::load(path).map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e))?;

        let config = GameConfig::from_python(py)?;
        let augment_path = augment_data_path
            .map(PathBuf::from)
            .unwrap_or_else(|| default_augment_path(path));
        let augment_pools = AugmentPools::load(&augment_path)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e))?;

        Ok(Self {
            engine: CombatEngine::new(combat_data),
            config,
            augment_pools,
        })
    }

    #[pyo3(signature = (game_id, seed, agent_mix=None, include_training_rows=true))]
    fn run_game<'py>(
        &mut self,
        py: Python<'py>,
        game_id: i64,
        seed: i64,
        agent_mix: Option<HashMap<String, i32>>,
        include_training_rows: bool,
    ) -> PyResult<Bound<'py, PyDict>> {
        let result = game_loop::run_game(
            &mut self.engine,
            &self.config,
            &self.augment_pools,
            game_id,
            seed as u64,
            agent_mix.as_ref(),
            include_training_rows,
        )
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?;

        let placements_value = Value::Array(result.placements);
        let training_rows_value = Value::Array(
            result
                .training_rows
                .iter()
                .map(training_row_to_value)
                .collect(),
        );
        let combat_debug_value = Value::Array(
            result
                .combat_debug
                .iter()
                .map(combat_debug_to_value)
                .collect(),
        );

        let dict = PyDict::new(py);
        dict.set_item("rounds", result.rounds)?;
        dict.set_item("placements", json_to_py(py, &placements_value)?)?;
        dict.set_item("training_rows", json_to_py(py, &training_rows_value)?)?;
        dict.set_item("combat_debug", json_to_py(py, &combat_debug_value)?)?;
        dict.set_item("analytics", json_to_py(py, &result.analytics)?)?;
        Ok(dict)
    }

    #[pyo3(signature = (game_id, seed, agent_mix=None))]
    fn run_game_jsonl<'py>(
        &mut self,
        py: Python<'py>,
        game_id: i64,
        seed: i64,
        agent_mix: Option<HashMap<String, i32>>,
    ) -> PyResult<Bound<'py, PyDict>> {
        let result = game_loop::run_game(
            &mut self.engine,
            &self.config,
            &self.augment_pools,
            game_id,
            seed as u64,
            agent_mix.as_ref(),
            true,
        )
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?;

        let placements_value = Value::Array(result.placements);
        let training_rows_jsonl = training_rows_to_jsonl(&result.training_rows)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?;

        let dict = PyDict::new(py);
        dict.set_item("rounds", result.rounds)?;
        dict.set_item("placements", json_to_py(py, &placements_value)?)?;
        dict.set_item("training_rows_jsonl", training_rows_jsonl)?;
        dict.set_item("training_row_count", result.training_rows.len())?;
        dict.set_item("analytics", json_to_py(py, &result.analytics)?)?;
        Ok(dict)
    }

    #[pyo3(signature = (game_id, seed, agent_mix=None))]
    fn run_game_parquet<'py>(
        &mut self,
        py: Python<'py>,
        game_id: i64,
        seed: i64,
        agent_mix: Option<HashMap<String, i32>>,
    ) -> PyResult<Bound<'py, PyDict>> {
        let result = game_loop::run_game(
            &mut self.engine,
            &self.config,
            &self.augment_pools,
            game_id,
            seed as u64,
            agent_mix.as_ref(),
            true,
        )
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?;

        let placements_value = Value::Array(result.placements);
        let training_rows_parquet = rows_to_parquet_bytes(&result.training_rows)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?;

        let dict = PyDict::new(py);
        dict.set_item("rounds", result.rounds)?;
        dict.set_item("placements", json_to_py(py, &placements_value)?)?;
        dict.set_item(
            "training_rows_parquet",
            PyBytes::new(py, &training_rows_parquet),
        )?;
        dict.set_item("training_row_count", result.training_rows.len())?;
        dict.set_item("analytics", json_to_py(py, &result.analytics)?)?;
        Ok(dict)
    }

    #[pyo3(signature = (game_ids, seeds, agent_mix=None, include_training_rows=true, output_mode="rows", rayon_threads=None))]
    fn run_games_batch<'py>(
        &self,
        py: Python<'py>,
        game_ids: Vec<i64>,
        seeds: Vec<i64>,
        agent_mix: Option<HashMap<String, i32>>,
        include_training_rows: bool,
        output_mode: &str,
        rayon_threads: Option<usize>,
    ) -> PyResult<Bound<'py, PyList>> {
        if game_ids.len() != seeds.len() {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "game_ids and seeds must have the same length",
            ));
        }
        if let Some(thread_count) = rayon_threads {
            if thread_count == 0 {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    "rayon_threads must be >= 1 when provided",
                ));
            }
        }

        let batch_mode = BatchOutputMode::parse(output_mode)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e))?;
        let jobs: Vec<(i64, i64)> = game_ids.into_iter().zip(seeds).collect();
        let batch_runs = run_games_batch_with_optional_pool(
            self.engine.combat_data.clone(),
            self.config.clone(),
            self.augment_pools.clone(),
            &jobs,
            agent_mix.as_ref(),
            include_training_rows,
            rayon_threads,
        )
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?;

        let result_list = PyList::empty(py);
        for run in batch_runs {
            let dict = PyDict::new(py);
            dict.set_item("game_id", run.game_id)?;
            dict.set_item("seed", run.seed)?;
            dict.set_item("elapsed", (run.elapsed * 1000.0).round() / 1000.0)?;

            match run.output {
                Ok(result) => {
                    dict.set_item("status", "ok")?;
                    dict.set_item("rounds", result.rounds)?;
                    dict.set_item(
                        "placements",
                        json_to_py(py, &Value::Array(result.placements))?,
                    )?;
                    dict.set_item("analytics", json_to_py(py, &result.analytics)?)?;

                    match batch_mode {
                        BatchOutputMode::Rows => {
                            let training_rows_value = Value::Array(
                                result
                                    .training_rows
                                    .iter()
                                    .map(training_row_to_value)
                                    .collect(),
                            );
                            dict.set_item("training_rows", json_to_py(py, &training_rows_value)?)?;
                        }
                        BatchOutputMode::Jsonl => {
                            let training_rows_jsonl = training_rows_to_jsonl(&result.training_rows)
                                .map_err(|e| {
                                    PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e)
                                })?;
                            dict.set_item("training_rows_jsonl", training_rows_jsonl)?;
                            dict.set_item("training_row_count", result.training_rows.len())?;
                        }
                        BatchOutputMode::Parquet => {
                            let training_rows_parquet =
                                rows_to_parquet_bytes(&result.training_rows).map_err(|e| {
                                    PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e)
                                })?;
                            dict.set_item(
                                "training_rows_parquet",
                                PyBytes::new(py, &training_rows_parquet),
                            )?;
                            dict.set_item("training_row_count", result.training_rows.len())?;
                        }
                    }
                }
                Err(error) => {
                    dict.set_item("status", "error")?;
                    dict.set_item("error", error)?;
                }
            }

            result_list.append(dict)?;
        }

        Ok(result_list)
    }

    #[pyo3(signature = (game_ids, seeds, agent_mix=None, include_training_rows=true, rayon_threads=None))]
    fn run_games_batch_parquet<'py>(
        &self,
        py: Python<'py>,
        game_ids: Vec<i64>,
        seeds: Vec<i64>,
        agent_mix: Option<HashMap<String, i32>>,
        include_training_rows: bool,
        rayon_threads: Option<usize>,
    ) -> PyResult<Bound<'py, PyDict>> {
        if game_ids.len() != seeds.len() {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "game_ids and seeds must have the same length",
            ));
        }
        if let Some(thread_count) = rayon_threads {
            if thread_count == 0 {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    "rayon_threads must be >= 1 when provided",
                ));
            }
        }

        let jobs: Vec<(i64, i64)> = game_ids.into_iter().zip(seeds).collect();
        let batch_runs = run_games_batch_with_optional_pool(
            self.engine.combat_data.clone(),
            self.config.clone(),
            self.augment_pools.clone(),
            &jobs,
            agent_mix.as_ref(),
            include_training_rows,
            rayon_threads,
        )
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?;

        let result_list = PyList::empty(py);
        let mut merged_training_rows: Vec<TrainingRow> = Vec::new();
        let mut total_training_row_count: usize = 0;

        for run in batch_runs {
            let dict = PyDict::new(py);
            dict.set_item("game_id", run.game_id)?;
            dict.set_item("seed", run.seed)?;
            dict.set_item("elapsed", (run.elapsed * 1000.0).round() / 1000.0)?;

            match run.output {
                Ok(result) => {
                    dict.set_item("status", "ok")?;
                    dict.set_item("rounds", result.rounds)?;
                    dict.set_item(
                        "placements",
                        json_to_py(py, &Value::Array(result.placements))?,
                    )?;
                    dict.set_item("analytics", json_to_py(py, &result.analytics)?)?;

                    let row_count = result.training_rows.len();
                    dict.set_item("training_row_count", row_count)?;

                    if include_training_rows && row_count > 0 {
                        total_training_row_count += row_count;
                        merged_training_rows.extend(result.training_rows);
                    }
                }
                Err(error) => {
                    dict.set_item("status", "error")?;
                    dict.set_item("error", error)?;
                }
            }

            result_list.append(dict)?;
        }

        let training_rows_parquet = if include_training_rows && total_training_row_count > 0 {
            rows_to_parquet_bytes(&merged_training_rows)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?
        } else {
            Vec::new()
        };

        let payload = PyDict::new(py);
        payload.set_item("results", result_list)?;
        payload.set_item("training_row_count", total_training_row_count)?;
        payload.set_item(
            "training_rows_parquet",
            PyBytes::new(py, &training_rows_parquet),
        )?;
        Ok(payload)
    }

    #[pyo3(signature = (game_ids, seeds, output_path, agent_mix=None, include_training_rows=true, rayon_threads=None))]
    fn run_games_batch_parquet_to_file<'py>(
        &self,
        py: Python<'py>,
        game_ids: Vec<i64>,
        seeds: Vec<i64>,
        output_path: &str,
        agent_mix: Option<HashMap<String, i32>>,
        include_training_rows: bool,
        rayon_threads: Option<usize>,
    ) -> PyResult<Bound<'py, PyDict>> {
        if game_ids.len() != seeds.len() {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "game_ids and seeds must have the same length",
            ));
        }
        if let Some(thread_count) = rayon_threads {
            if thread_count == 0 {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    "rayon_threads must be >= 1 when provided",
                ));
            }
        }

        let jobs: Vec<(i64, i64)> = game_ids.into_iter().zip(seeds).collect();
        let batch_runs = run_games_batch_with_optional_pool(
            self.engine.combat_data.clone(),
            self.config.clone(),
            self.augment_pools.clone(),
            &jobs,
            agent_mix.as_ref(),
            include_training_rows,
            rayon_threads,
        )
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?;

        let result_list = PyList::empty(py);
        let mut merged_training_rows: Vec<TrainingRow> = Vec::new();
        let mut total_training_row_count: usize = 0;

        for run in batch_runs {
            let dict = PyDict::new(py);
            dict.set_item("game_id", run.game_id)?;
            dict.set_item("seed", run.seed)?;
            dict.set_item("elapsed", (run.elapsed * 1000.0).round() / 1000.0)?;

            match run.output {
                Ok(result) => {
                    dict.set_item("status", "ok")?;
                    dict.set_item("rounds", result.rounds)?;
                    dict.set_item(
                        "placements",
                        json_to_py(py, &Value::Array(result.placements))?,
                    )?;
                    dict.set_item("analytics", json_to_py(py, &result.analytics)?)?;

                    let row_count = result.training_rows.len();
                    dict.set_item("training_row_count", row_count)?;

                    if include_training_rows && row_count > 0 {
                        total_training_row_count += row_count;
                        merged_training_rows.extend(result.training_rows);
                    }
                }
                Err(error) => {
                    dict.set_item("status", "error")?;
                    dict.set_item("error", error)?;
                }
            }

            result_list.append(dict)?;
        }

        let mut wrote_parquet = false;
        if include_training_rows && total_training_row_count > 0 {
            let output_path_ref = Path::new(output_path);
            if let Some(parent) = output_path_ref.parent() {
                if !parent.as_os_str().is_empty() {
                    fs::create_dir_all(parent).map_err(|e| {
                        PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string())
                    })?;
                }
            }
            let training_rows_parquet = rows_to_parquet_bytes(&merged_training_rows)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?;
            fs::write(output_path_ref, training_rows_parquet)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
            wrote_parquet = true;
        }

        let payload = PyDict::new(py);
        payload.set_item("results", result_list)?;
        payload.set_item("training_row_count", total_training_row_count)?;
        payload.set_item("wrote_parquet", wrote_parquet)?;
        Ok(payload)
    }

    fn num_champions(&self) -> usize {
        self.engine.combat_data.champions.len()
    }
}

/// Parse a Python list of unit spec dicts into Rust UnitSpec structs.
fn parse_unit_specs(specs: &Bound<'_, PyList>) -> PyResult<Vec<UnitSpec>> {
    let mut result = Vec::with_capacity(specs.len());

    for item in specs.iter() {
        let dict = item.downcast::<PyDict>()?;

        let api_name: String = dict
            .get_item("api_name")?
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("api_name"))?
            .extract()?;

        let star_level: i32 = dict
            .get_item("star_level")?
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("star_level"))?
            .extract()?;

        let position: Vec<i32> = dict
            .get_item("position")?
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("position"))?
            .extract()?;
        if position.len() != 2 {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "position must be a 2-element [row, col] list",
            ));
        }

        let team: i32 = dict
            .get_item("team")?
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("team"))?
            .extract()?;

        let items: Vec<String> = dict
            .get_item("items")?
            .map(|v| v.extract().unwrap_or_default())
            .unwrap_or_default();

        let traits: Vec<String> = dict
            .get_item("traits")?
            .map(|v| v.extract().unwrap_or_default())
            .unwrap_or_default();

        result.push(UnitSpec {
            api_name,
            star_level,
            position,
            team,
            items,
            traits,
        });
    }

    Ok(result)
}

/// Convert a CombatResult to a Python dict.
fn result_to_dict<'py>(py: Python<'py>, result: &CombatResult) -> PyResult<Bound<'py, PyDict>> {
    let dict = PyDict::new(py);
    dict.set_item("winner", result.winner)?;
    dict.set_item("combat_time", result.combat_time)?;
    dict.set_item("team0_survivors", result.team0_survivors)?;
    dict.set_item("team1_survivors", result.team1_survivors)?;
    dict.set_item("team0_total_damage", result.team0_total_damage)?;
    dict.set_item("team1_total_damage", result.team1_total_damage)?;
    dict.set_item("team0_abilities_cast", result.team0_abilities_cast)?;
    dict.set_item("team1_abilities_cast", result.team1_abilities_cast)?;
    dict.set_item(
        "team0_bilgewater_serpents",
        result.team0_bilgewater_serpents,
    )?;
    dict.set_item(
        "team1_bilgewater_serpents",
        result.team1_bilgewater_serpents,
    )?;
    dict.set_item(
        "team0_shadow_isles_souls",
        result.team0_shadow_isles_souls,
    )?;
    dict.set_item(
        "team1_shadow_isles_souls",
        result.team1_shadow_isles_souls,
    )?;
    let debug_takedowns = PyList::empty(py);
    for takedown in &result.debug_takedowns {
        let entry = PyDict::new(py);
        entry.set_item("killer_team", takedown.killer_team)?;
        entry.set_item("killer_api_name", &takedown.killer_api_name)?;
        entry.set_item("victim_team", takedown.victim_team)?;
        entry.set_item("victim_api_name", &takedown.victim_api_name)?;
        debug_takedowns.append(entry)?;
    }
    dict.set_item("debug_takedowns", debug_takedowns)?;

    // Also add nested total_damage_dealt for compatibility
    let damage_dict = PyDict::new(py);
    damage_dict.set_item("team0", result.team0_total_damage)?;
    damage_dict.set_item("team1", result.team1_total_damage)?;
    dict.set_item("total_damage_dealt", damage_dict)?;

    Ok(dict)
}

fn get_or_create_rayon_pool(thread_count: usize) -> Result<Arc<ThreadPool>, String> {
    let cache = RAYON_POOL_CACHE.get_or_init(|| Mutex::new(HashMap::new()));

    {
        let guard = cache
            .lock()
            .map_err(|_| "Failed to lock Rayon pool cache".to_string())?;
        if let Some(pool) = guard.get(&thread_count) {
            return Ok(Arc::clone(pool));
        }
    }

    let pool = Arc::new(
        ThreadPoolBuilder::new()
            .num_threads(thread_count)
            .build()
            .map_err(|e| e.to_string())?,
    );

    let mut guard = cache
        .lock()
        .map_err(|_| "Failed to lock Rayon pool cache".to_string())?;
    let entry = guard
        .entry(thread_count)
        .or_insert_with(|| Arc::clone(&pool));
    Ok(Arc::clone(entry))
}

fn run_games_batch_with_optional_pool(
    combat_data: CombatData,
    config: GameConfig,
    augment_pools: AugmentPools,
    jobs: &[(i64, i64)],
    agent_mix: Option<&HashMap<String, i32>>,
    include_training_rows: bool,
    rayon_threads: Option<usize>,
) -> Result<Vec<BatchGameRun>, String> {
    if let Some(thread_count) = rayon_threads {
        let pool = get_or_create_rayon_pool(thread_count)?;
        Ok(pool.install(|| {
            run_games_batch_internal(
                combat_data,
                config,
                augment_pools,
                jobs,
                agent_mix,
                include_training_rows,
            )
        }))
    } else {
        Ok(run_games_batch_internal(
            combat_data,
            config,
            augment_pools,
            jobs,
            agent_mix,
            include_training_rows,
        ))
    }
}

fn run_games_batch_internal(
    combat_data: CombatData,
    config: GameConfig,
    augment_pools: AugmentPools,
    jobs: &[(i64, i64)],
    agent_mix: Option<&HashMap<String, i32>>,
    include_training_rows: bool,
) -> Vec<BatchGameRun> {
    jobs.par_iter()
        .map_init(
            || CombatEngine::new(combat_data.clone()),
            |engine, (game_id, seed)| {
                let started = Instant::now();
                let output = game_loop::run_game(
                    engine,
                    &config,
                    &augment_pools,
                    *game_id,
                    *seed as u64,
                    agent_mix,
                    include_training_rows,
                );
                BatchGameRun {
                    game_id: *game_id,
                    seed: *seed,
                    elapsed: started.elapsed().as_secs_f64(),
                    output,
                }
            },
        )
        .collect()
}

fn training_rows_to_jsonl(rows: &[TrainingRow]) -> Result<String, String> {
    let mut payload = String::new();
    for row in rows {
        let row_json = serde_json::to_string(row).map_err(|e| e.to_string())?;
        payload.push_str(&row_json);
        payload.push('\n');
    }
    Ok(payload)
}

fn default_augment_path(combat_data_path: &Path) -> PathBuf {
    combat_data_path
        .parent()
        .and_then(|p| p.parent())
        .and_then(|p| p.parent())
        .map(|root| {
            root.join("data")
                .join("api")
                .join("processed")
                .join("augments_set16.json")
        })
        .unwrap_or_else(|| {
            PathBuf::from("data")
                .join("api")
                .join("processed")
                .join("augments_set16.json")
        })
}

fn training_row_to_value(row: &TrainingRow) -> Value {
    serde_json::to_value(row).unwrap_or(Value::Null)
}

fn combat_debug_to_value(row: &CombatDebugRound) -> Value {
    serde_json::to_value(row).unwrap_or(Value::Null)
}

fn to_json_text<T: serde::Serialize>(value: &T, default: &str) -> String {
    serde_json::to_string(value).unwrap_or_else(|_| default.to_string())
}

fn rows_to_parquet_bytes(rows: &[TrainingRow]) -> Result<Vec<u8>, String> {
    let mut row_schema_version_builder = Int64Builder::with_capacity(rows.len());
    let mut game_id_builder = Int64Builder::with_capacity(rows.len());
    let mut round_builder = Int64Builder::with_capacity(rows.len());
    let mut player_id_builder = Int64Builder::with_capacity(rows.len());
    let mut placement_builder = Int64Builder::with_capacity(rows.len());
    let mut hp_builder = Int64Builder::with_capacity(rows.len());
    let mut gold_builder = Int64Builder::with_capacity(rows.len());
    let mut level_builder = Int64Builder::with_capacity(rows.len());
    let mut streak_builder = Int64Builder::with_capacity(rows.len());
    let mut board_count_builder = Int64Builder::with_capacity(rows.len());
    let mut win_streak_builder = Int64Builder::with_capacity(rows.len());
    let mut loss_streak_builder = Int64Builder::with_capacity(rows.len());
    let mut num_augments_builder = Int64Builder::with_capacity(rows.len());
    let mut num_traits_builder = Int64Builder::with_capacity(rows.len());
    let mut alive_count_builder = Int64Builder::with_capacity(rows.len());
    let mut opponent_hp_builder = Int64Builder::with_capacity(rows.len());
    let mut opponent_gold_builder = Int64Builder::with_capacity(rows.len());
    let mut opponent_level_builder = Int64Builder::with_capacity(rows.len());
    let mut opponent_streak_builder = Int64Builder::with_capacity(rows.len());
    let mut opponent_board_count_builder = Int64Builder::with_capacity(rows.len());
    let mut opponent_win_streak_builder = Int64Builder::with_capacity(rows.len());
    let mut opponent_loss_streak_builder = Int64Builder::with_capacity(rows.len());
    let mut opponent_num_augments_builder = Int64Builder::with_capacity(rows.len());
    let mut opponent_num_traits_builder = Int64Builder::with_capacity(rows.len());
    let mut is_ghost_builder = BooleanBuilder::with_capacity(rows.len());
    let mut combat_result_builder = Int64Builder::with_capacity(rows.len());
    let mut damage_dealt_builder = Float64Builder::with_capacity(rows.len());
    let mut damage_taken_builder = Float64Builder::with_capacity(rows.len());
    let mut combat_time_builder = Float64Builder::with_capacity(rows.len());
    let mut survivors_builder = Int64Builder::with_capacity(rows.len());

    let mut board_names_builder = StringBuilder::with_capacity(rows.len(), 0);
    let mut board_stars_builder = StringBuilder::with_capacity(rows.len(), 0);
    let mut trait_names_builder = StringBuilder::with_capacity(rows.len(), 0);
    let mut trait_counts_builder = StringBuilder::with_capacity(rows.len(), 0);
    let mut augments_builder = StringBuilder::with_capacity(rows.len(), 0);
    let mut opponent_augments_builder = StringBuilder::with_capacity(rows.len(), 0);
    let mut units_builder = StringBuilder::with_capacity(rows.len(), 0);
    let mut traits_builder = StringBuilder::with_capacity(rows.len(), 0);
    let mut opponent_units_builder = StringBuilder::with_capacity(rows.len(), 0);
    let mut opponent_traits_builder = StringBuilder::with_capacity(rows.len(), 0);

    for row in rows {
        row_schema_version_builder.append_value(row.row_schema_version as i64);
        game_id_builder.append_value(row.game_id);
        round_builder.append_value(row.round as i64);
        player_id_builder.append_value(row.player_id as i64);
        placement_builder.append_value(row.placement as i64);
        hp_builder.append_value(row.hp as i64);
        gold_builder.append_value(row.gold as i64);
        level_builder.append_value(row.level as i64);
        streak_builder.append_value(row.streak as i64);
        board_count_builder.append_value(row.board_count as i64);
        win_streak_builder.append_value(row.win_streak as i64);
        loss_streak_builder.append_value(row.loss_streak as i64);
        num_augments_builder.append_value(row.num_augments as i64);
        num_traits_builder.append_value(row.num_traits as i64);
        alive_count_builder.append_value(row.alive_count as i64);
        opponent_hp_builder.append_value(row.opponent_hp as i64);
        opponent_gold_builder.append_value(row.opponent_gold as i64);
        opponent_level_builder.append_value(row.opponent_level as i64);
        opponent_streak_builder.append_value(row.opponent_streak as i64);
        opponent_board_count_builder.append_value(row.opponent_board_count as i64);
        opponent_win_streak_builder.append_value(row.opponent_win_streak as i64);
        opponent_loss_streak_builder.append_value(row.opponent_loss_streak as i64);
        opponent_num_augments_builder.append_value(row.opponent_num_augments as i64);
        opponent_num_traits_builder.append_value(row.opponent_num_traits as i64);
        is_ghost_builder.append_value(row.is_ghost);

        match row.combat_result {
            Some(value) => combat_result_builder.append_value(value as i64),
            None => combat_result_builder.append_null(),
        }

        damage_dealt_builder.append_value(row.damage_dealt);
        damage_taken_builder.append_value(row.damage_taken);
        combat_time_builder.append_value(row.combat_time);
        survivors_builder.append_value(row.survivors as i64);

        board_names_builder.append_value(to_json_text(&row.board_names, "[]"));
        board_stars_builder.append_value(to_json_text(&row.board_stars, "[]"));
        trait_names_builder.append_value(to_json_text(&row.trait_names, "[]"));
        trait_counts_builder.append_value(to_json_text(&row.trait_counts, "[]"));
        augments_builder.append_value(to_json_text(&row.augments, "[]"));
        opponent_augments_builder.append_value(to_json_text(&row.opponent_augments, "[]"));
        units_builder.append_value(to_json_text(&row.units, "[]"));
        traits_builder.append_value(to_json_text(&row.traits, "{}"));
        opponent_units_builder.append_value(to_json_text(&row.opponent_units, "[]"));
        opponent_traits_builder.append_value(to_json_text(&row.opponent_traits, "{}"));
    }

    let schema = Schema::new(vec![
        Field::new("row_schema_version", DataType::Int64, false),
        Field::new("game_id", DataType::Int64, false),
        Field::new("round", DataType::Int64, false),
        Field::new("player_id", DataType::Int64, false),
        Field::new("placement", DataType::Int64, false),
        Field::new("hp", DataType::Int64, false),
        Field::new("gold", DataType::Int64, false),
        Field::new("level", DataType::Int64, false),
        Field::new("streak", DataType::Int64, false),
        Field::new("board_count", DataType::Int64, false),
        Field::new("win_streak", DataType::Int64, false),
        Field::new("loss_streak", DataType::Int64, false),
        Field::new("num_augments", DataType::Int64, false),
        Field::new("num_traits", DataType::Int64, false),
        Field::new("alive_count", DataType::Int64, false),
        Field::new("units", DataType::Utf8, false),
        Field::new("traits", DataType::Utf8, false),
        Field::new("augments", DataType::Utf8, false),
        Field::new("opponent_units", DataType::Utf8, false),
        Field::new("opponent_traits", DataType::Utf8, false),
        Field::new("opponent_hp", DataType::Int64, false),
        Field::new("opponent_gold", DataType::Int64, false),
        Field::new("opponent_level", DataType::Int64, false),
        Field::new("opponent_streak", DataType::Int64, false),
        Field::new("opponent_board_count", DataType::Int64, false),
        Field::new("opponent_win_streak", DataType::Int64, false),
        Field::new("opponent_loss_streak", DataType::Int64, false),
        Field::new("opponent_num_augments", DataType::Int64, false),
        Field::new("opponent_num_traits", DataType::Int64, false),
        Field::new("opponent_augments", DataType::Utf8, false),
        Field::new("is_ghost", DataType::Boolean, false),
        Field::new("combat_result", DataType::Int64, true),
        Field::new("damage_dealt", DataType::Float64, false),
        Field::new("damage_taken", DataType::Float64, false),
        Field::new("combat_time", DataType::Float64, false),
        Field::new("survivors", DataType::Int64, false),
        Field::new("board_names", DataType::Utf8, false),
        Field::new("board_stars", DataType::Utf8, false),
        Field::new("trait_names", DataType::Utf8, false),
        Field::new("trait_counts", DataType::Utf8, false),
    ]);

    let arrays: Vec<ArrayRef> = vec![
        Arc::new(row_schema_version_builder.finish()),
        Arc::new(game_id_builder.finish()),
        Arc::new(round_builder.finish()),
        Arc::new(player_id_builder.finish()),
        Arc::new(placement_builder.finish()),
        Arc::new(hp_builder.finish()),
        Arc::new(gold_builder.finish()),
        Arc::new(level_builder.finish()),
        Arc::new(streak_builder.finish()),
        Arc::new(board_count_builder.finish()),
        Arc::new(win_streak_builder.finish()),
        Arc::new(loss_streak_builder.finish()),
        Arc::new(num_augments_builder.finish()),
        Arc::new(num_traits_builder.finish()),
        Arc::new(alive_count_builder.finish()),
        Arc::new(units_builder.finish()),
        Arc::new(traits_builder.finish()),
        Arc::new(augments_builder.finish()),
        Arc::new(opponent_units_builder.finish()),
        Arc::new(opponent_traits_builder.finish()),
        Arc::new(opponent_hp_builder.finish()),
        Arc::new(opponent_gold_builder.finish()),
        Arc::new(opponent_level_builder.finish()),
        Arc::new(opponent_streak_builder.finish()),
        Arc::new(opponent_board_count_builder.finish()),
        Arc::new(opponent_win_streak_builder.finish()),
        Arc::new(opponent_loss_streak_builder.finish()),
        Arc::new(opponent_num_augments_builder.finish()),
        Arc::new(opponent_num_traits_builder.finish()),
        Arc::new(opponent_augments_builder.finish()),
        Arc::new(is_ghost_builder.finish()),
        Arc::new(combat_result_builder.finish()),
        Arc::new(damage_dealt_builder.finish()),
        Arc::new(damage_taken_builder.finish()),
        Arc::new(combat_time_builder.finish()),
        Arc::new(survivors_builder.finish()),
        Arc::new(board_names_builder.finish()),
        Arc::new(board_stars_builder.finish()),
        Arc::new(trait_names_builder.finish()),
        Arc::new(trait_counts_builder.finish()),
    ];

    let row_count = rows.len().max(1);
    let batch =
        RecordBatch::try_new(Arc::new(schema.clone()), arrays).map_err(|e| e.to_string())?;
    let writer_props = WriterProperties::builder()
        .set_compression(Compression::UNCOMPRESSED)
        .set_dictionary_enabled(false)
        .set_statistics_enabled(EnabledStatistics::None)
        .set_max_row_group_size(row_count)
        .set_write_batch_size(row_count)
        .build();
    let mut buffer: Vec<u8> = Vec::new();
    {
        let mut writer = ArrowWriter::try_new(&mut buffer, Arc::new(schema), Some(writer_props))
            .map_err(|e| e.to_string())?;
        writer.write(&batch).map_err(|e| e.to_string())?;
        writer.close().map_err(|e| e.to_string())?;
    }

    Ok(buffer)
}

fn json_to_py(py: Python<'_>, value: &Value) -> PyResult<PyObject> {
    match value {
        Value::Null => Ok(py.None()),
        Value::Bool(v) => Ok(v.into_py(py)),
        Value::Number(v) => {
            if let Some(i) = v.as_i64() {
                Ok(i.into_py(py))
            } else if let Some(u) = v.as_u64() {
                Ok(u.into_py(py))
            } else if let Some(f) = v.as_f64() {
                Ok(f.into_py(py))
            } else {
                Ok(py.None())
            }
        }
        Value::String(v) => Ok(v.into_py(py)),
        Value::Array(values) => {
            let py_list = PyList::empty(py);
            for item in values {
                py_list.append(json_to_py(py, item)?)?;
            }
            Ok(py_list.into_py(py))
        }
        Value::Object(values) => {
            let py_dict = PyDict::new(py);
            for (key, item) in values {
                py_dict.set_item(key, json_to_py(py, item)?)?;
            }
            Ok(py_dict.into_py(py))
        }
    }
}

/// Python module definition.
#[pymodule]
fn tft_combat_engine(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<RustCombatEngine>()?;
    m.add_class::<RustGameSimulator>()?;
    Ok(())
}
