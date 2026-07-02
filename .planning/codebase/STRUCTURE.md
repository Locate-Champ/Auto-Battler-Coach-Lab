# Codebase Structure

**Analysis Date:** 2026-02-27

## Directory Layout

```
auto-battler-coach-lab/
├── app/                     # Runtime coaching: watchers, state, API, frontend
│   ├── api/                 # FastAPI REST endpoints (stats, recommendations)
│   ├── frontend/            # React TypeScript UI (overlay, coaching panel)
│   ├── server/              # WebSocket server for real-time state broadcast
│   ├── state/               # Game state tracking & event processing
│   ├── services/            # Helper services (pool tracker)
│   ├── watcher/             # Log parsing & game event extraction
│   ├── redux_bridge/        # Frontend-backend state synchronization
│   ├── config.py            # Runtime configuration (paths, ports)
│   └── main.py              # Entry point: watcher + state + server orchestration
├── coach/                   # Decision-making & recommendation engine
│   ├── modules/             # Pluggable decision modules
│   │   ├── shop/            # Shop action candidates & execution
│   │   ├── position/        # Board positioning optimization
│   │   ├── items/           # Item crafting recommendations
│   │   └── econ/            # Economy/leveling decisions
│   ├── scoring/             # Combat & board evaluation
│   │   ├── combat.py        # Damage/win-rate estimation
│   │   ├── evaluator.py     # Board strength scoring
│   │   └── archetypes.py    # Trait composition library
│   ├── offline/             # Decision tracing & analysis
│   ├── coach.py             # Main orchestrator: candidate generation → scoring → recommendation
│   ├── encoding.py          # Convert GameState → model-ready vectors
│   ├── explain.py           # Generate human-readable explanations
│   ├── actions.py           # ActionPlan dataclass & decision types
│   ├── state.py             # Coach-specific state representations (UnitState, GameState)
│   ├── weights.py           # Scoring configuration per game stage
│   └── odds.py              # Probabilistic calculations (shop hit rates, etc.)
├── simulator/               # Deterministic game & combat simulation
│   ├── core/                # Low-level engines
│   │   ├── combat_engine.py # Python tick-by-tick combat resolver
│   │   ├── engine_wrapper.py # Rust/Python engine dispatcher (HybridCombatEngine)
│   │   ├── batch_simulator.py # Multiprocessing worker for parallel sims
│   │   ├── combat_fast/     # Cython-compiled combat optimization
│   │   ├── item_optimizer.py # Item placement search
│   │   ├── positioning_optimizer.py # Unit position search
│   │   └── utils.py         # Shared utilities (RNG, unit creation)
│   ├── game/                # Full game loop & mechanics
│   │   ├── game.py          # 8-player TFT match orchestrator (rounds, economy, elimination)
│   │   ├── player.py        # Individual player state machine
│   │   ├── actions.py       # Agent behavior (shop, position, economy)
│   │   ├── collector.py     # Snapshot generation at decision points
│   │   ├── shop.py          # Shop generation & unit pool management
│   │   ├── champion_pool.py # Shared champion availability tracking
│   │   ├── unlocks.py       # Unit unlock logic (Hex/Stellacorn, Ixtal, etc.)
│   │   ├── constants.py     # Game constants (board size, costs, damages)
│   │   └── stats/           # Computed champion stats per set
│   ├── data/                # Static game data
│   │   └── combat_data.json # Combat mechanics definitions
│   ├── cloud_runner.py      # AWS SSM orchestrator for batch simulation
│   ├── batch_runner.py      # Local batch runner (fallback to cloud_runner)
│   ├── config.py            # Simulator-specific config (paths, RNG seed)
│   └── benchmark.py         # Determinism verification
├── models/                  # ML training track
│   ├── train_xgboost.py     # XGBoost training (placement, econ decisions)
│   ├── train_transformer.py # Transformer model training (trajectory prediction)
│   ├── feature_engineering.py # Feature extraction & vectorization
│   ├── fe_fast/__init__.py  # Cython-compiled fast feature extraction
│   ├── data_loader.py       # Parquet I/O, train/test splitting, multiprocessing
│   ├── dataset.py           # Dataset class for model training
│   ├── evaluate.py          # Model evaluation metrics
│   ├── embeddings.py        # Champion/item embedding utilities
│   ├── transformer.py       # Transformer architecture definition
│   ├── counterfactual.py    # Causal analysis of model predictions
│   ├── trajectory.py        # Trajectory data preparation
│   ├── information_theory.py # Mutual information, entropy metrics
│   ├── uncertainty.py       # Uncertainty quantification for predictions
│   ├── checkpoints/         # Model checkpoint directory (git-ignored)
│   └── preprocess_tensors.py # Preprocessing utility for tensor datasets
├── src/                     # Runtime inference models
│   ├── models/              # Loaded models for inference
│   │   ├── recommender.py   # TFTRecommender facade (load & run models)
│   │   ├── placement_model.py # Placement model inference wrapper
│   │   ├── feature_engineering.py # Runtime feature extraction (identical to models/)
│   │   ├── role_rules.py    # Hard-coded unit role assignments
│   │   └── positioning_rules.py # Heuristic positioning rules
│   ├── combat_engine/       # Runtime combat (used by recommender)
│   │   ├── combat_loop.py   # Combat tick resolution
│   │   └── game_data_loader.py # Load game mechanics
│   └── metatft_parser.py    # MetaTFT log format parser
├── tests/                   # Pytest test suite
│   ├── conftest.py          # Pytest fixtures (RNG seed, game state)
│   └── test_*.py            # Test modules (simulation, coach, models)
├── scripts/                 # Automation scripts
│   ├── ci/                  # CI/CD helpers
│   │   └── check_public_surface_allowlist.py # Guard on new root-level files
│   ├── tools/               # Utility scripts
│   ├── kb/                  # Knowledge-base update scripts
│   ├── run-gates.sh         # Gate pipeline orchestrator (sim → validate → train → upload)
│   ├── launch-graviton.sh   # Launch CPU simulation instance on AWS
│   ├── launch-gpu.sh        # Launch GPU training instance on AWS
│   ├── bootstrap-cpu.sh     # Bootstrap existing CPU instance
│   ├── bootstrap-gpu.sh     # Bootstrap existing GPU instance
│   ├── create-runtime-bundle.sh # Package repo subset for cloud deployment
│   ├── _gate_*.sh           # Individual gate scripts (a, b, c, d)
│   └── sync_all_data.py     # Sync knowledge-base & metadata
├── outputs/                 # Tracked runtime artifacts (gitignored except AGENTS.md)
│   ├── coach/               # Coaching decision traces & explanations
│   └── kb/                  # Knowledge-base exports
├── results/                 # Simulation output directories (gitignored)
│   └── {run_id}/            # Per-run output (snapshots, artifacts)
├── data/                    # Local data (gitignored)
│   └── local/               # Runtime data for API (models, configs)
├── knowledge-base/          # Game mechanics reference
│   ├── manifests/           # Parsed metadata (champions, items, traits)
│   └── sources/             # Markdown docs (game rules, strategies)
├── .planning/               # GSD planning documents (generated)
│   └── codebase/            # ARCHITECTURE.md, STRUCTURE.md, etc.
├── .github/workflows/       # CI/CD pipelines
│   ├── test-coverage.yml    # Run pytest on PR
│   └── (other automation)
├── .vscode/                 # IDE settings (formatters, debugger)
├── snapshot_schema.py       # JSON schema validation for game snapshots
├── sitecustomize.py         # Python environment customization (ruff import)
├── pytest.ini               # Pytest configuration
├── ruff.toml                # Ruff linter/formatter config
├── package.json             # npm scripts (start, build, sync)
├── requirements.txt         # Python core dependencies
├── requirements-ml.txt      # ML-specific dependencies (torch, xgboost)
├── requirements-simulator.txt # Simulator-only dependencies
├── requirements.lock        # Pinned versions (generated by pip-compile)
├── requirements-ml.lock     # Pinned ML versions
├── requirements-simulator.lock # Pinned simulator versions
├── .env.example             # Template for local env vars
├── .pre-commit-config.yaml  # Pre-commit hook definitions (ruff, detect-secrets)
├── CLAUDE.md                # Claude-specific codebase instructions
├── AGENTS.md                # GSD agent directives (synced from CLAUDE.md)
├── HANDOFF.md               # Engineering handoff notes
├── MEMORY.md                # Long-term decision memory
└── README.md                # Project overview & runbooks
```

## Directory Purposes

**app/:**
- **Purpose:** Live coaching runtime (watchers, state sync, WebSocket server, API)
- **Contains:** Python watcher/parser, state manager, FastAPI server, React frontend
- **Key files:** `main.py` (entry point), `config.py` (local settings), `api/server.py` (FastAPI)

**coach/:**
- **Purpose:** Decision-making & coaching logic (modular, extensible)
- **Contains:** Orchestrator, 4 decision modules (shop/position/items/econ), scoring, explanation
- **Key files:** `coach.py` (main loop), `modules/*/candidates.py` (option generation), `scoring/*.py` (evaluation)

**simulator/core/:**
- **Purpose:** Low-level simulation engines & optimization
- **Contains:** Combat (Python + Rust dispatch), batch worker, item/position optimizers
- **Key files:** `combat_engine.py` (Python), `engine_wrapper.py` (Rust dispatch), `batch_simulator.py` (workers)

**simulator/game/:**
- **Purpose:** Full game mechanics & state machines
- **Contains:** Game loop, player state, shop, unlocks, collector (snapshot generation)
- **Key files:** `game.py` (orchestrator), `player.py` (state machine), `collector.py` (data collection)

**models/:**
- **Purpose:** ML training pipeline (XGBoost, Transformer, feature engineering)
- **Contains:** Data loading, feature extraction, model training, evaluation
- **Key files:** `train_xgboost.py`, `train_transformer.py`, `feature_engineering.py`, `data_loader.py`

**src/models/:**
- **Purpose:** Runtime model inference (loaded from checkpoints)
- **Contains:** Model wrappers, feature extraction for inference, heuristic rules
- **Key files:** `recommender.py` (main facade), `placement_model.py`, `feature_engineering.py`

**tests/:**
- **Purpose:** Pytest test suite (unit, integration, determinism checks)
- **Contains:** Test fixtures, test modules for all components
- **Key files:** `conftest.py` (fixtures), individual `test_*.py` files

**scripts/:**
- **Purpose:** Automation & deployment tooling
- **Contains:** Gate orchestration, AWS launch/bootstrap, data sync, CI helpers
- **Key files:** `run-gates.sh` (main pipeline), `launch-*.sh` (AWS), `create-runtime-bundle.sh` (packaging)

## Key File Locations

**Entry Points:**
- `app/main.py` - Live coaching (watcher + state + server)
- `app/api/server.py` - Standalone API server (FastAPI)
- `simulator/cloud_runner.py` - Batch simulation orchestrator
- `models/train_xgboost.py` - Model training (CLI entry)
- `app/frontend/` - React app root (npm start)

**Configuration:**
- `app/config.py` - App runtime config (paths, ports, MetaTFT dir)
- `simulator/config.py` - Simulator config (AWS, RNG, S3)
- `ruff.toml` - Linting & formatting
- `.env.example` - Template for cloud scripts
- `package.json` - npm scripts

**Core Logic:**
- `coach/coach.py` - Decision orchestrator
- `simulator/game/game.py` - Game loop
- `simulator/core/combat_engine.py` - Combat resolution
- `models/feature_engineering.py` - Feature vectorization
- `app/state/state_manager.py` - Event-driven state updates

**Testing:**
- `simulator/benchmark.py` - Determinism checks
- `simulator/validate_output.py` - Output schema validation
- `tests/conftest.py` - Pytest configuration & fixtures

## Naming Conventions

**Files:**
- `*.py` - Python source files
- `*.tsx` / `*.ts` - React TypeScript components/utilities
- `*.json` - Configuration or game data (combat_data.json, augments.json)
- `test_*.py` - Pytest test modules
- `*_test.py` - Alternative pytest pattern (less common here)
- `conftest.py` - Pytest fixture file
- `*.sh` - Bash scripts (cloud automation)

**Directories:**
- `{component}/__init__.py` - Makes directory a Python package
- `{component}/{module}.py` - Feature module (e.g., `combat_engine.py`)
- `{component}/tests/` or `tests/test_{component}.py` - Tests for component
- `{component}/**/__pycache__/` - Compiled bytecode (gitignored)

**Classes & Functions:**
- `ClassName` - PascalCase for classes (e.g., `GameState`, `CombatEngine`, `StateManager`)
- `function_name()` - snake_case for functions (e.g., `batch_simulate_1v1()`, `process_event()`)
- `CONSTANT_NAME` - UPPER_CASE for module-level constants (e.g., `BOARD_ROWS`, `MAX_ITEMS`)
- `_private_function()` - Leading underscore for internal functions
- `@property` - Used for computed attributes (e.g., `PlayerState.interest`, `PlayerState.streak`)

**Variables:**
- `local_var` - snake_case for local variables
- `self.state` - snake_case for instance attributes
- `GameState` - PascalCase for type hints

## Where to Add New Code

**New Feature (e.g., augment recommendation):**
- **Primary code:** `coach/modules/{new_module}/candidates.py` (option generation), `coach/modules/{new_module}/execute.py` (simulation)
- **Scoring:** `coach/scoring/{new_module}.py` (if new scoring domain)
- **Tests:** `tests/test_coach_modules_{new_module}.py`
- **Integration:** Add to `coach/coach.py` main orchestrator as new `generate_candidates()` call

**New Component/Module (e.g., trajectory predictor):**
- **Implementation:** `src/models/trajectory_predictor.py` (runtime) or `models/trajectory_model.py` (training)
- **Feature engineering:** Add to `models/feature_engineering.py` if new features needed
- **Tests:** `tests/test_models_trajectory.py`
- **Integration:** Expose via `src/models/__init__.py`

**Utilities:**
- **Shared helpers:** `simulator/core/utils.py` (sim), `coach/utils.py` (coach)
- **Game constants:** `simulator/game/constants.py`
- **Coach weights/config:** `coach/weights.py`
- **Tests:** `tests/test_utils_*.py`

**New Simulation Feature (e.g., new mechanic):**
- **Implementation:** `simulator/game/{mechanic}.py` or extend `simulator/game/game.py`
- **Combat logic:** `simulator/core/combat_engine.py`
- **Constants:** Update `simulator/game/constants.py`
- **Tests:** `tests/test_simulator_{mechanic}.py`
- **Validation:** Add check to `simulator/validate_output.py`

## Special Directories

**results/:**
- Purpose: Local simulation output (per-run snapshots, artifacts)
- Generated: Yes (by `simulator/cloud_runner.py`)
- Committed: No (gitignored)
- Lifecycle: Each `run_id` is a subdirectory containing Parquet chunks + metadata

**checkpoints/:**
- Purpose: Model checkpoint storage (XGBoost .model, Transformer .pt files)
- Location: `models/checkpoints/`
- Generated: Yes (by training scripts)
- Committed: No (gitignored)
- Lifecycle: Named by timestamp or gate ID (e.g., `models/checkpoints/xgb_gate_b_20260227.model`)

**outputs/coach/:**
- Purpose: Tracked coaching decision traces (for analysis, learning)
- Location: `outputs/coach/`
- Generated: Yes (by `coach.py` if tracing enabled)
- Committed: Partial (AGENTS.md tracked, traces gitignored by default)
- Lifecycle: Traces are JSONL format, one decision per line

**data/local/:**
- Purpose: Runtime data (API models, game data, configs)
- Location: `data/local/`
- Generated: No (manually populated or via `npm run sync`)
- Committed: No (gitignored)
- Lifecycle: Required by API startup; populated by knowledge-base scripts

**knowledge-base/:**
- Purpose: Game mechanics reference (champions, items, traits, rules)
- Location: `knowledge-base/{manifests,sources}/`
- Generated: Yes (by scraper + sync scripts)
- Committed: Yes (markdown docs)
- Lifecycle: Updated via `npm run sync:game` or `npm run sync:meta`

**outputs/kb/:**
- Purpose: Exported knowledge-base artifacts
- Location: `outputs/kb/`
- Generated: Yes (by sync scripts)
- Committed: No (gitignored)
- Lifecycle: Overwritten each sync run

---

*Structure analysis: 2026-02-27*
