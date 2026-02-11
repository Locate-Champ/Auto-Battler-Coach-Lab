mod abilities;
mod damage;
mod data;
mod engine;
mod game_loop;
mod hex_grid;
mod items;
mod targeting;
/// TFT Combat Engine - Rust implementation with PyO3 bindings.
///
/// This module provides a high-performance combat simulator for Teamfight Tactics,
/// callable from Python via PyO3/maturin.
mod types;
mod unit;

use arrow_array::builder::{Float64Builder, Int64Builder, StringBuilder};
use arrow_array::{ArrayRef, RecordBatch};
use arrow_schema::{DataType, Field, Schema};
use parquet::arrow::ArrowWriter;
use parquet::basic::Compression;
use parquet::file::properties::{EnabledStatistics, WriterProperties};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyList};
use serde_json::Value;
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::Arc;

use data::CombatData;
use engine::{CombatEngine, CombatResult, UnitSpec};
use game_loop::{AugmentPools, GameConfig};

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
            agent_mix,
            include_training_rows,
        )
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?;

        let placements_value = Value::Array(result.placements);
        let training_rows_value = Value::Array(result.training_rows);

        let dict = PyDict::new(py);
        dict.set_item("rounds", result.rounds)?;
        dict.set_item("placements", json_to_py(py, &placements_value)?)?;
        dict.set_item("training_rows", json_to_py(py, &training_rows_value)?)?;
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
            agent_mix,
            true,
        )
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?;

        let placements_value = Value::Array(result.placements);
        let mut training_rows_jsonl = String::new();
        for row in &result.training_rows {
            let row_json = serde_json::to_string(row)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
            training_rows_jsonl.push_str(&row_json);
            training_rows_jsonl.push('\n');
        }

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
            agent_mix,
            true,
        )
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?;

        let placements_value = Value::Array(result.placements);
        let training_rows_parquet = rows_to_parquet_bytes(&result.training_rows)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?;

        let dict = PyDict::new(py);
        dict.set_item("rounds", result.rounds)?;
        dict.set_item("placements", json_to_py(py, &placements_value)?)?;
        dict.set_item("training_rows_parquet", PyBytes::new(py, &training_rows_parquet))?;
        dict.set_item("training_row_count", result.training_rows.len())?;
        dict.set_item("analytics", json_to_py(py, &result.analytics)?)?;
        Ok(dict)
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

    // Also add nested total_damage_dealt for compatibility
    let damage_dict = PyDict::new(py);
    damage_dict.set_item("team0", result.team0_total_damage)?;
    damage_dict.set_item("team1", result.team1_total_damage)?;
    dict.set_item("total_damage_dealt", damage_dict)?;

    Ok(dict)
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

fn value_to_i64(value: Option<&Value>, default: i64) -> i64 {
    match value {
        Some(Value::Number(v)) => v
            .as_i64()
            .or_else(|| v.as_u64().map(|u| u as i64))
            .unwrap_or(default),
        Some(Value::String(v)) => v.parse::<i64>().unwrap_or(default),
        Some(Value::Bool(v)) => {
            if *v {
                1
            } else {
                0
            }
        }
        _ => default,
    }
}

fn value_to_f64(value: Option<&Value>, default: f64) -> f64 {
    match value {
        Some(Value::Number(v)) => v.as_f64().unwrap_or(default),
        Some(Value::String(v)) => v.parse::<f64>().unwrap_or(default),
        Some(Value::Bool(v)) => {
            if *v {
                1.0
            } else {
                0.0
            }
        }
        _ => default,
    }
}

fn value_to_json_text(value: Option<&Value>, default: &str) -> String {
    match value {
        Some(Value::Null) | None => default.to_string(),
        Some(Value::String(v)) => v.clone(),
        Some(v) => serde_json::to_string(v).unwrap_or_else(|_| default.to_string()),
    }
}

fn rows_to_parquet_bytes(rows: &[Value]) -> Result<Vec<u8>, String> {
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
    let mut combat_result_builder = Int64Builder::with_capacity(rows.len());
    let mut damage_dealt_builder = Float64Builder::with_capacity(rows.len());
    let mut damage_taken_builder = Float64Builder::with_capacity(rows.len());

    let mut board_names_builder = StringBuilder::with_capacity(rows.len(), 0);
    let mut board_stars_builder = StringBuilder::with_capacity(rows.len(), 0);
    let mut trait_names_builder = StringBuilder::with_capacity(rows.len(), 0);
    let mut trait_counts_builder = StringBuilder::with_capacity(rows.len(), 0);
    let mut augments_builder = StringBuilder::with_capacity(rows.len(), 0);
    let mut units_builder = StringBuilder::with_capacity(rows.len(), 0);
    let mut traits_builder = StringBuilder::with_capacity(rows.len(), 0);
    let mut opponent_units_builder = StringBuilder::with_capacity(rows.len(), 0);
    let mut opponent_traits_builder = StringBuilder::with_capacity(rows.len(), 0);

    for row in rows {
        let obj = row
            .as_object()
            .ok_or_else(|| "training row is not a JSON object".to_string())?;

        game_id_builder.append_value(value_to_i64(obj.get("game_id"), 0));
        round_builder.append_value(value_to_i64(obj.get("round"), 0));
        player_id_builder.append_value(value_to_i64(obj.get("player_id"), 0));
        placement_builder.append_value(value_to_i64(obj.get("placement"), 0));
        hp_builder.append_value(value_to_i64(obj.get("hp"), 0));
        gold_builder.append_value(value_to_i64(obj.get("gold"), 0));
        level_builder.append_value(value_to_i64(obj.get("level"), 0));
        streak_builder.append_value(value_to_i64(obj.get("streak"), 0));
        board_count_builder.append_value(value_to_i64(obj.get("board_count"), 0));
        win_streak_builder.append_value(value_to_i64(obj.get("win_streak"), 0));
        loss_streak_builder.append_value(value_to_i64(obj.get("loss_streak"), 0));
        num_augments_builder.append_value(value_to_i64(obj.get("num_augments"), 0));
        num_traits_builder.append_value(value_to_i64(obj.get("num_traits"), 0));
        alive_count_builder.append_value(value_to_i64(obj.get("alive_count"), 0));
        opponent_hp_builder.append_value(value_to_i64(obj.get("opponent_hp"), 0));

        match obj.get("combat_result") {
            Some(Value::Null) | None => combat_result_builder.append_null(),
            Some(value) => combat_result_builder.append_value(value_to_i64(Some(value), 0)),
        }

        damage_dealt_builder.append_value(value_to_f64(obj.get("damage_dealt"), 0.0));
        damage_taken_builder.append_value(value_to_f64(obj.get("damage_taken"), 0.0));

        board_names_builder.append_value(value_to_json_text(obj.get("board_names"), "[]"));
        board_stars_builder.append_value(value_to_json_text(obj.get("board_stars"), "[]"));
        trait_names_builder.append_value(value_to_json_text(obj.get("trait_names"), "[]"));
        trait_counts_builder.append_value(value_to_json_text(obj.get("trait_counts"), "[]"));
        augments_builder.append_value(value_to_json_text(obj.get("augments"), "[]"));
        units_builder.append_value(value_to_json_text(obj.get("units"), "[]"));
        traits_builder.append_value(value_to_json_text(obj.get("traits"), "{}"));
        opponent_units_builder.append_value(value_to_json_text(obj.get("opponent_units"), "[]"));
        opponent_traits_builder.append_value(value_to_json_text(obj.get("opponent_traits"), "{}"));
    }

    let schema = Schema::new(vec![
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
        Field::new("combat_result", DataType::Int64, true),
        Field::new("damage_dealt", DataType::Float64, false),
        Field::new("damage_taken", DataType::Float64, false),
        Field::new("board_names", DataType::Utf8, false),
        Field::new("board_stars", DataType::Utf8, false),
        Field::new("trait_names", DataType::Utf8, false),
        Field::new("trait_counts", DataType::Utf8, false),
    ]);

    let arrays: Vec<ArrayRef> = vec![
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
        Arc::new(combat_result_builder.finish()),
        Arc::new(damage_dealt_builder.finish()),
        Arc::new(damage_taken_builder.finish()),
        Arc::new(board_names_builder.finish()),
        Arc::new(board_stars_builder.finish()),
        Arc::new(trait_names_builder.finish()),
        Arc::new(trait_counts_builder.finish()),
    ];

    let row_count = rows.len().max(1);
    let batch = RecordBatch::try_new(Arc::new(schema.clone()), arrays).map_err(|e| e.to_string())?;
    let writer_props = WriterProperties::builder()
        .set_compression(Compression::UNCOMPRESSED)
        .set_dictionary_enabled(false)
        .set_statistics_enabled(EnabledStatistics::None)
        .set_max_row_group_size(row_count)
        .set_write_batch_size(row_count)
        .build();
    let mut buffer: Vec<u8> = Vec::new();
    {
        let mut writer = ArrowWriter::try_new(
            &mut buffer,
            Arc::new(schema),
            Some(writer_props),
        )
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
