# Codebase Reliability & Cleanup

## What This Is

A systematic effort to fix all 18 concerns identified in the codebase audit — silent failures, tech debt, missing error handling, monolithic file splits, and incomplete implementations. The goal is a more reliable, maintainable, and observable codebase across the simulator, models, coach, and API layers.

## Core Value

Stop silent failures. Every error path must be explicit, every fallback must be logged, and no operation should silently degrade without the developer knowing.

## Requirements

### Validated

- ✓ Deterministic combat simulation (Python + Rust engines) — existing
- ✓ Batch game simulation via cloud runner with gate system — existing
- ✓ Feature engineering pipeline (Python + Cython fast path) — existing
- ✓ XGBoost and Transformer model training — existing
- ✓ Parquet-based data pipeline with DataLoader — existing
- ✓ FastAPI runtime recommender API — existing
- ✓ Coach system with heuristic/linear evaluators — existing
- ✓ WebSocket-based real-time game state sync — existing
- ✓ React frontend with Vite/Tailwind — existing

### Active

- [ ] Fix all silent failure paths (bare except, missing pyarrow, pickle fallback)
- [ ] Wire SklearnEvaluator feature extraction
- [ ] Fix type contracts (check_compatibility returns None)
- [ ] Add explicit error messages for missing dependencies (combat_data.json, pyarrow)
- [ ] Refactor global state (cloud_runner, DataLoader, API server)
- [ ] Split monolithic files (champion_abilities, combat_engine, feature_engineering, cloud_runner)
- [ ] Add schema validation for feature engineering inputs
- [ ] Make DataLoader a context manager
- [ ] Add logging for Cython fallback paths
- [ ] Extract magic numbers to config dataclass
- [ ] Add Rust extension pre-flight check
- [ ] Improve benchmark cross-engine validation performance

### Out of Scope

- New features or gameplay mechanics — this is cleanup only
- Champion ability registry/plugin system — noted but deferred beyond split
- Mobile or alternative frontends — not relevant to reliability work
- Model architecture changes — only fixing the plumbing around models

## Context

This is a brownfield project with a mature codebase spanning simulation (Python+Rust), ML training, real-time coaching, and a web frontend. The codebase audit identified 18 concerns across 7 categories. The simulator core (`simulator/core/**`, `simulator/game/**`) is the active truth and must remain deterministic after any changes. Legacy paths (`simulator/Simulator/**`, `simulator/Concurrency/**`, `simulator/Evaluator/**`) are quarantined and must not be touched.

Key risk: the monolithic file splits (champion_abilities at 5.9k LOC, combat_engine at 5.3k LOC) touch the simulator core. These require determinism verification via `python -m simulator.benchmark` after every structural change.

## Constraints

- **Determinism**: Combat engine must pass benchmark after any change — `python -m simulator.benchmark`
- **No legacy paths**: Do not touch `simulator/Simulator/**`, `simulator/Concurrency/**`, `simulator/Evaluator/**`
- **Verification**: All Python changes must pass `ruff check .` and `ruff format --check .`
- **Parquet rule**: PyArrow must be validated in the same environment running the command
- **Priority**: Reliability first — silent failures before refactors before new wiring

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Include monolithic file splits | User wants full cleanup, accepts higher risk | — Pending |
| Reliability as top priority | Silent failures are the most dangerous class of bugs | — Pending |
| All 18 concerns in scope | Comprehensive cleanup pass rather than incremental | — Pending |

---
*Last updated: 2026-02-27 after initialization*
