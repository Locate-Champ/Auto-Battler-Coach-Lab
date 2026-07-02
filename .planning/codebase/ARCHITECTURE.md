# Architecture

**Analysis Date:** 2026-02-27

## Pattern Overview

**Overall:** Multi-track architecture with clear separation between simulation, model training, and runtime coaching.

**Key Characteristics:**
- Dual-track design: simulation engine (deterministic) and ML models (probabilistic) operate independently
- Pluggable combat engine with Rust/Python auto-detection for performance
- Modular coaching system with decision-tree-like module hierarchy (shop, position, items, econ)
- WebSocket-driven real-time state synchronization between game watcher, coach, and frontend
- Layered data flow: raw logs → parsed events → game state → recommendations

## Layers

**Simulation Layer:**
- Purpose: Deterministic game simulation for evaluation, training data generation, and combat resolution
- Location: `simulator/core/**`, `simulator/game/**`
- Contains: Combat engine (Python + Rust), batch simulator, game loop, champion pool, player logic
- Depends on: Game data (constants, combats data JSON), augment definitions
- Used by: Training pipeline (models), cloud runner for gate-based data generation

**Game Logic Layer:**
- Purpose: Full TFT game mechanics: rounds, economy, shop, augments, player elimination
- Location: `simulator/game/**`
- Contains: `game.py` (main loop), `player.py` (individual player state), `actions.py` (agent behavior), `collector.py` (snapshot generation)
- Depends on: `simulator/core/combat_engine.py`, champion pool, constants
- Used by: `simulator/cloud_runner.py` for batch game execution

**Combat Engine Layer:**
- Purpose: Resolve 1v1 or team battles with deterministic tick-based mechanics
- Location: `simulator/core/combat_engine.py` (Python), `simulator/core/engine_wrapper.py` (dispatch)
- Contains: Unit positioning, ability resolution, damage calculation, status effects
- Depends on: Combat data JSON (`simulator/data/combat_data.json`), item/ability effects
- Used by: Game loop, batch simulator, optimization modules (positioning, items)

**Feature Engineering Layer:**
- Purpose: Convert raw game snapshots into ML-ready feature vectors
- Location: `models/feature_engineering.py`, `models/fe_fast/__init__.py` (Cython-optimized)
- Contains: Vectorization of board state, pool state, gold economy, item slots
- Depends on: Snapshot schema from `snapshot_schema.py`, game constants
- Used by: Training pipeline, DataLoader for XGBoost/Transformer training

**Model Training Layer:**
- Purpose: Train XGBoost (placement, econ decisions) and Transformer models (trajectory)
- Location: `models/train_xgboost.py`, `models/train_transformer.py`, `models/dataset.py`
- Contains: Feature pipeline, train/test split, model fitting, hyperparameter grids
- Depends on: DataLoader (Parquet I/O), feature engineer, simulator output snapshots
- Used by: Training scripts, cloud training instances (GPU)

**Runtime Model Layer:**
- Purpose: Load pre-trained models for inference on live game state
- Location: `src/models/**`
- Contains: `recommender.py` (recommendations), `placement_model.py` (positioning), `feature_engineering.py` (runtime vectorization)
- Depends on: Checkpoint files (XGBoost .model, Transformer .pt), game constants
- Used by: API server, coaching module

**Coaching Layer:**
- Purpose: Decision-making and action planning for real-time coaching
- Location: `coach/**`
- Contains: Module orchestrator, decision tree (shop, position, items, econ), scoring/evaluation, explanation generation
- Depends on: Simulator for evaluations, runtime models for predictions, state encoder
- Used by: App main loop, WebSocket handler for client updates

**State Management Layer:**
- Purpose: Real-time game state tracking from log watchers
- Location: `app/state/**`
- Contains: `state_manager.py` (event processor), `game_state.py` (data classes)
- Depends on: Log watcher events, parser output
- Used by: Main app, WebSocket server, state change callbacks

**Watcher/Parser Layer:**
- Purpose: Parse game logs in real-time and emit structured events
- Location: `app/watcher/**`
- Contains: `log_watcher.py` (file I/O with debouncing), `parser.py` (log line parsing)
- Depends on: MetaTFT log directory structure
- Used by: Main app initialization and event loop

**API/Server Layer:**
- Purpose: Serve models and state to frontend clients
- Location: `app/api/server.py` (FastAPI endpoints), `app/server/websocket.py` (WebSocket handler)
- Contains: REST endpoints for stats/recommendations, WebSocket broadcast mechanism
- Depends on: Runtime models, state manager
- Used by: Frontend client

**Frontend Layer:**
- Purpose: Visual coaching overlay during live gameplay
- Location: `app/frontend/**`
- Contains: React components (board visualization, coaching panel), hooks for API calls
- Depends on: API server, WebSocket connection
- Used by: End-user during TFT matches

## Data Flow

**Training Data Pipeline:**

1. **Simulation** → `simulator/game/collector.py` captures board snapshots at decision points
2. **Snapshot JSON** → `snapshot_schema.py` normalizes fields
3. **Feature Engineering** → `models/feature_engineering.py` vectorizes snapshots to N-dimensional arrays
4. **Parquet Storage** → `models/data_loader.py` batches features + labels into Parquet chunks (parallel workers)
5. **Train/Test Split** → sklearn `train_test_split` by game_id for trajectory consistency
6. **Model Training** → `models/train_xgboost.py` uses external memory mode for large datasets

**Runtime Coaching Pipeline:**

1. **Game Log** → `app/watcher/log_watcher.py` detects new lines in MetaTFT log files
2. **Parse Event** → `app/watcher/parser.py` regex-extracts stage, gold, units, items → `GameEvent`
3. **Update State** → `app/state/state_manager.py` dispatches to handler (e.g. `_handle_stage_change`)
4. **Encode Board** → `coach/encoding.py` converts `GameState` to model-ready tensor
5. **Generate Candidates** → `coach/modules/{shop,position,items,econ}/candidates.py` enumerate decision options
6. **Score Options** → `coach/scoring/combat.py`, `coach/scoring/evaluator.py` simulate + grade each
7. **Explain Choice** → `coach/explain.py` generates `Explanation` object with breakdowns
8. **Broadcast** → `app/server/websocket.py` sends `Recommendation` to connected clients

**State Management State Machine:**

```
GameEvent (from log parser)
  ↓
StateManager.process_event()
  ↓
Handler dispatches event type → _handle_stage_change, _handle_combat_start, etc.
  ↓
State mutates (e.g., GameState.stage, GameState.board)
  ↓
_notify_state_change() → callbacks fire (e.g., server.on_state_change)
  ↓
WebSocket broadcast to all connected clients
```

**State Management:**
- `GameState` (immutable dataclass) holds current board, gold, stage, units, opponents
- State updates are atomic within StateManager lock
- Callbacks enable decoupling: watcher → state_manager → (coach module + websocket server)
- Event-driven model: no polling, changes propagate via callbacks

## Key Abstractions

**GameState:**
- Purpose: Immutable snapshot of current game state at any moment
- Examples: `app/state/game_state.py`, `coach/state.py` (coach-specific version)
- Pattern: Frozen dataclasses with derived properties (e.g., `PlayerState.interest` computes from gold)

**UnitState:**
- Purpose: Represents a single champion on board or bench
- Examples: `app/state/game_state.py:Unit`, `coach/state.py:UnitState`
- Pattern: Immutable with factory methods (e.g., `with_items()`, `with_position()`)

**ActionPlan:**
- Purpose: Encodes a single decision: shop action, position change, item craft, or econ hold
- Location: `coach/actions.py`
- Pattern: Tagged union (discriminated by `decision_type`)

**CombatEngine:**
- Purpose: Unified interface to Rust or Python combat simulation
- Location: `simulator/core/engine_wrapper.py:HybridCombatEngine`, `simulator/core/combat_engine.py`
- Pattern: Strategy pattern with fallback (prefer Rust for performance, fall back to Python)

**TFTRecommender:**
- Purpose: Load and run inference with pre-trained placement + econ models
- Location: `src/models/recommender.py`
- Pattern: Facade over model loading, feature extraction, and prediction

**CoachConfig:**
- Purpose: Scoring weights and decision thresholds for coaching module
- Location: `coach/weights.py`
- Pattern: Configuration object with stage-aware defaults (e.g., `default_config_for_stage()`)

## Entry Points

**CLI - Full Coach (WebSocket + API):**
- Location: `app/main.py:AutoBattlerCoach.run()`
- Triggers: `python -m app.main` or `npm start` (via `app/run_app.py`)
- Responsibilities: Spin up log watcher → state manager → WebSocket server, handle signals, broadcast updates

**API Server Only:**
- Location: `app/api/server.py`
- Triggers: `uvicorn app.api.server:app --host 0.0.0.0 --port 8000`
- Responsibilities: Serve model inference endpoints (stats, recommendations, augment fit)

**Simulation & Data Generation:**
- Location: `simulator/cloud_runner.py` (orchestrator), `simulator/core/batch_simulator.py` (worker)
- Triggers: `bash scripts/run-gates.sh` or direct `python simulator/cloud_runner.py --games 50000`
- Responsibilities: Run deterministic TFT games, collect snapshots, validate output, upload to S3

**Model Training:**
- Location: `models/train_xgboost.py` (placement/econ), `models/train_transformer.py` (trajectory)
- Triggers: `python -m models.train_xgboost --data-dir <gate_output>`, `python -m models.train_transformer`
- Responsibilities: Load Parquet data, feature engineer, split, train on GPU (or CPU), checkpoint models

**Benchmark/Validation:**
- Location: `simulator/benchmark.py` (determinism), `simulator/validate_output.py` (schema)
- Triggers: `python -m simulator.benchmark`, `python -m simulator.validate_output <outdir>`
- Responsibilities: Verify simulation determinism, validate snapshot schema compliance

## Error Handling

**Strategy:** Explicit exception types, context managers for resource cleanup, graceful fallback.

**Patterns:**
- **Simulation errors:** Determinism failures → pytest snapshot comparison. Combat errors → logged, game marked invalid.
- **Model loading:** FileNotFoundError → wrapped with helpful hint on data location. PyArrow missing → install before gate.
- **WebSocket:** Client disconnect → remove from broadcast list. Invalid JSON → log and skip frame.
- **State updates:** Race conditions → StateManager lock prevents concurrent event processing.

## Cross-Cutting Concerns

**Logging:**
- Python: stdlib `logging` module. Simulators use `print()` for speed. Cloud SSM checks logs for failures.
- Frontend: Browser console + Redux time-travel debugging.

**Validation:**
- Snapshots: `snapshot_schema.py` normalizes/validates JSON schema.
- Models: `sklearn.model_selection` for train/test splits by game_id (ensures trajectory consistency).
- Output: `simulator/validate_output.py` runs 19 checks: schema, dtypes, unique games, etc.

**Authentication:**
- Runtime (live coaching): None (local WebSocket, no auth).
- API: None (local dev server, no auth).
- Cloud: AWS IAM roles on EC2 instances, S3 signed URLs for bundle uploads.

---

*Architecture analysis: 2026-02-27*
