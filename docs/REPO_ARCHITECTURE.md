# Repo Architecture + Folder Guide (TFT Coach)

Last updated: 2026-02-13

This repo contains multiple "tracks" of work (runtime coach app, deterministic simulator + data generation, and ML training). This document explains how the pieces fit together and what each top-level folder is for.

## 1) System Architecture (How The Repo Fits Together)

There are two major workflows:

1. **Runtime coaching** (live game -> recommendations -> UI)
2. **Offline simulation + training** (batch sim -> datasets -> models -> artifacts)

### 1.1 Runtime Coaching (Live)

Data sources:

- MetaTFT / Overwolf logs on disk (Windows)
- Optional Redux bridge messages (injected into Overwolf) for richer live state

Core runtime flow:

```text
MetaTFT logs / Redux -> app/watcher + app/redux_bridge
                      -> app/state (StateManager, GameState)
                      -> app/server/websocket.py (FastAPI + WebSocket on :8765)
                      -> app/frontend (React UI via Vite on :5173, proxies /ws and /api)

                                        |
                                        v
                                   coach/ (planner)
                                   - candidate actions
                                   - deterministic executors
                                   - scoring (combat sim + evaluator + archetype prior + econ)
                                   - explanations
```

Important entry points:

- WebSocket + state broadcasting: `app/server/websocket.py`
- App "main" that runs the watcher + WS server: `app/main.py`
- Frontend dev server + proxy: `app/frontend/vite.config.ts`

Ports in dev (as wired today):

- UI (Vite): `http://127.0.0.1:5173`
- WebSocket server: `ws://127.0.0.1:8765/ws` (and proxied as `/ws` from Vite)
- REST API server: `http://127.0.0.1:8000` (proxied as `/api` from Vite)

How "recommendations" currently happen in the live WS server:

- `app/server/websocket.py` converts the live `app.state.GameState` into a `coach.state.GameState`
- It calls `coach.coach.Coach.recommend(...)` for `items`, `position`, `econ`, and `shop`
- The coach scores candidates with:
  - `coach/scoring/combat.py` (uses `simulator.core.combat_engine.CombatEngine`)
  - `coach/scoring/evaluator.py` (lightweight evaluator)
  - `coach/scoring/archetypes.py` (archetype alignment)
  - `coach/scoring/features.py` (econ/plan value and derived traits)

### 1.2 Offline Simulation + Training (Batch)

Core offline flow:

```text
scripts/ sync + data curation
  -> data/api/processed (augments/items/traits/units snapshots)
  -> simulator/cloud_runner.py (8-player full-game batch sim)
  -> results/ (parquet/jsonl chunks + summary/checkpoint)
  -> models/ (XGBoost + Transformer training, streaming for big datasets)
  -> models/checkpoints + outputs/ (trained models + artifacts)
```

Important entry points:

- Batch simulation: `python -m simulator.cloud_runner`
- Output validation (19 checks): `python -m simulator.validate_output <dir>`
- Determinism + throughput benchmark: `python -m simulator.benchmark`
- XGBoost baseline training: `python -m models.train_xgboost --data <dir> --task fight|top4|placement`
- Transformer training (streaming default): `python -m models.train_transformer --data <dir> ...`

The simulator produces **decision-time snapshots** via `simulator/game/collector.py` (one row per alive player per PvP round, including opponent snapshot + round combat metadata + final placement label). That snapshot format is what makes supervised learning practical in this repo.

### 1.3 Two ML "Tracks" Exist (Know Which One You're Touching)

There are two separate ML/recommendation implementations in the repo right now:

1. **New simulator-trained ML pipeline:** `models/`
   - XGBoost baselines, streaming transformer, uncertainty, counterfactual scaffolding
   - Trains on `simulator/cloud_runner` outputs

2. **Legacy/parallel recommender used by the API server:** `src/models/`
   - Used by `app/api/server.py`
   - Uses `data/game_data/*.jsonl` and heuristic/meta CSVs
   - Includes a minimal combat scaffold in `src/combat_engine/` (separate from the real simulator)

When documenting or changing "the model," be explicit about whether it's the `models/` stack or the `src/models/` stack.

## 2) Top-Level Folder Guide

This is a "what lives where" guide for the repo root.

### 2.1 Primary Code Folders

- `app/`
  - Runtime coaching application (watch logs, manage live state, serve WebSockets, host API server, run the UI).
  - Key paths:
    - `app/main.py`: runs the log watcher + WS server
    - `app/server/websocket.py`: FastAPI + WebSocket broadcast server and coach integration
    - `app/api/server.py`: FastAPI REST API (currently uses `src/models/`)
    - `app/frontend/`: React+TypeScript UI (Vite, Tailwind)
    - `app/state/`: canonical live `GameState` + state manager
    - `app/watcher/`: filesystem log watcher + parser
    - `app/redux_bridge/`: Overwolf injection + Redux state bridge

- `coach/`
  - The "planner with a critic" coaching layer (candidate actions + executors + scoring + explanations).
  - Key paths:
    - `coach/coach.py`: orchestrates candidates -> execute -> score -> explain
    - `coach/state.py`: coaching GameState / UnitState / PlayerState
    - `coach/modules/`: per-decision modules (`econ/`, `items/`, `position/`, `shop/`)
    - `coach/scoring/`: combat scoring bridge, evaluator, archetype alignment, feature glue
    - `coach/offline/`: scripts to build archetypes / evaluator artifacts

- `simulator/`
  - The active Set 16 deterministic simulator (8-player game loop + tick-based combat engine).
  - Key paths:
    - `simulator/cloud_runner.py`: batch generator (chunks + checkpoint/resume)
    - `simulator/game/`: economy/shop/augments/matchmaking + `collector.py` snapshot rows
    - `simulator/core/`: combat engine, champion abilities, item effects, timing
    - `simulator/data/`: combat stats, trait defs, timing constants, reference validation
    - Legacy RL stack also exists (e.g. `simulator/Simulator/`, `simulator/main.py`) but is not the production batch path.

- `models/`
  - Simulator-trained ML pipeline and training scripts.
  - Key paths:
    - `models/feature_engineering.py`, `models/data_loader.py`
    - `models/train_xgboost.py`, `models/evaluate.py`
    - `models/embeddings.py`, `models/transformer.py`, `models/dataset.py`, `models/train_transformer.py`
    - `models/checkpoints/`: trained model artifacts + reports
    - `models/analysis/`: MI reports, evaluation outputs, etc

- `src/`
  - Legacy/parallel implementation used by `app/api/server.py`.
  - Contains `src/models/` (FeatureEngineer, PlacementModel, TFTRecommender), `src/metatft_parser.py`, and `src/combat_engine/` (minimal combat scaffold).

- `tests/`
  - Pytest suite covering simulator validators and the `models/` + `coach/` components (streaming dataset, embeddings, uncertainty, counterfactual, etc).

### 2.2 Data + Outputs

- `data/`
  - Primary data store for the project (API snapshots, personal stats, meta comp data, raw local dumps).
  - Key subfolders:
    - `data/api/processed/`: normalized set data (units/traits/items/augments, etc)
    - `data/personal/`: match history + personal performance CSVs
    - `data/meta/`: meta comps and tier lists (used by recommenders)
    - `data/game_data/`: jsonl sources used by `src/models/`

- `results/`
  - Simulator outputs and calibration runs (chunked parquet/jsonl + summaries/checkpoints).
  - This is the main "training data" root for `models/` training.

- `outputs/`
  - Derived artifacts produced by offline scripts and analysis.
  - Examples:
    - `outputs/coach/`: archetype/evaluator artifacts for the coach layer
    - `outputs/kb/`: knowledge-base manifests/summaries

- `knowledge-base/`
  - Curated project knowledge and long-lived artifacts (includes `performance_reference.json`).

- `live-logs/`
  - Captured log files from the live integration runs (useful for debugging parsers/state).

### 2.3 Tooling + Documentation

- `docs/`
  - Documentation hub. Start at `docs/INDEX.md`.
  - This includes simulator docs, architecture docs, integration docs, research notes, and design specs.

- `scripts/`
  - Utility scripts:
    - sync + scraping helpers (`sync_all_data.py`, `fetch_meta_data.py`, etc)
    - verification harness (`verify.ps1`)
    - ntfy notifier (`notify-ntfy.ps1`)

- `scraper/`
  - Node-based scraper utilities (separate from the Python simulator and coach runtime).

### 2.4 Frontend/Overlay Misc

- `app/frontend/`
  - The main UI (React/Vite). `npm start` ultimately runs `app/frontend` scripts.

- `overlay/`
  - Overlay assets directory used by the WS server route `GET /overlay` in `app/server/websocket.py`.
  - Note: as of this snapshot, `overlay/index.html` is not present (the server returns "Overlay not found").

- `trait_icons_set16/`
  - Static trait icon assets.

### 2.5 Repo Meta / Environment Folders

- `.agent/`
  - Continuity state for autonomous agent sessions (`.agent/CONTINUITY.md`).

- `.claude/`
  - Claude/Codex tooling metadata (project memory, settings, etc).

- `.github/`
  - GitHub Actions / repo automation config.

- `.vscode/`
  - VS Code workspace settings.

- `.venv/`
  - Local Python environment (developer machine specific).

- `.pytest_cache/`, `__pycache__/`
  - Local caches (safe to ignore; not part of product logic).

### 2.6 Legacy/Empty/Placeholder Folders

- `archive/`
  - Archived experiments/older code and artifacts that are not part of the active runtime path.

- `Concurrency/`, `Evaluator/`
  - Present at repo root; currently appear to be placeholders/unused in the main paths.

## 3) "Where Do I Change X?" Cheatsheet

- Live state parsing / mapping: `e:\VS Code\tft-coach-234\app\watcher\parser.py`, `e:\VS Code\tft-coach-234\app\state\state_manager.py`
- Live UI: `e:\VS Code\tft-coach-234\app\frontend\src\App.tsx`
- WebSocket payload shape + coach integration: `e:\VS Code\tft-coach-234\app\server\websocket.py`
- Coaching logic (candidates/executors/scoring/explanations): `e:\VS Code\tft-coach-234\coach\`
- Combat simulation fidelity / performance: `e:\VS Code\tft-coach-234\simulator\core\combat_engine.py`, `e:\VS Code\tft-coach-234\simulator\core\champion_abilities.py`, `e:\VS Code\tft-coach-234\simulator\core\item_effects.py`
- Batch data generation + schema: `e:\VS Code\tft-coach-234\simulator\cloud_runner.py`, `e:\VS Code\tft-coach-234\simulator\game\collector.py`
- ML training (simulator-trained): `e:\VS Code\tft-coach-234\models\`
- API server (legacy recommender): `e:\VS Code\tft-coach-234\app\api\server.py`, `e:\VS Code\tft-coach-234\src\models\`

