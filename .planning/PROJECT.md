# Auto-Battler Coach Lab

## What This Is

A TFT (Teamfight Tactics) auto-battler coaching system with deterministic combat simulation (Python + Rust engines), ML-based placement prediction (XGBoost), real-time coaching via WebSocket, and a React frontend. The v1.0 reliability milestone eliminated all 18 concerns from the original codebase audit — the codebase now has explicit error paths, observable fallbacks, validated dependencies, and modular file structure.

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
- ✓ All 39 bare/broad exception handlers narrowed to specific types — v1.0
- ✓ Observable fallback logging for Cython, pickle, DataLoader paths — v1.0
- ✓ Explicit startup errors for missing pyarrow, combat_data.json, Rust extension — v1.0
- ✓ DataLoader context manager with automatic pool cleanup — v1.0
- ✓ Type contracts: check_compatibility() returns bool, BoardEvaluator ABC — v1.0
- ✓ Schema validation for transform_batch() (dict + Arrow paths) — v1.0
- ✓ FastAPI lifespan pattern with startup failure gate and app.state DI — v1.0
- ✓ NumericFeatureConfig frozen dataclass replacing magic numbers — v1.0
- ✓ Ruff BLE+B rules enforced statically across entire codebase — v1.0
- ✓ SklearnEvaluator wired with TFTFeatureEngineer integration — v1.0
- ✓ BatchRunner class replacing cloud_runner module globals — v1.0
- ✓ DataLoader spawn context for cross-platform multiprocessing — v1.0
- ✓ combat_engine.py split into facade + 8 sub-modules (<550 LOC facade) — v1.0
- ✓ champion_abilities.py split into facade + 5 mixin sub-modules (31 LOC facade) — v1.0
- ✓ cloud_runner.py split into facade + 3 sub-modules — v1.0
- ✓ feature_engineering.py split into facade + 4 mixin sub-modules — v1.0
- ✓ Cross-engine parity tests batched for CI performance — v1.0

### Active

(No active requirements — next milestone not yet planned)

### Out of Scope

- Champion ability registry/plugin system — noted but deferred beyond structural split
- Mobile or alternative frontends — not relevant to current focus
- Model architecture changes — only fixing plumbing around models
- Third-party logging library (structlog/loguru) — stdlib logging sufficient
- Formal DI framework — manual constructor injection solves the problem

## Context

Shipped v1.0 with 66,107 LOC Python across simulation, ML training, coaching, and web frontend layers. Tech stack: Python 3.14, Rust (PyO3), XGBoost, FastAPI, React/Vite/Tailwind. The v1.0 milestone resolved all 18 codebase audit concerns in 14 phases over 5 days, touching 175 files (+34.7k/-15.1k lines).

Key architectural patterns established:
- Mixin composition for monolithic file splits (facade + underscore-prefixed sub-modules)
- Spawn-safe multiprocessing with explicit initargs (BatchRunner, DataLoader)
- Observable fallbacks via `_log = logging.getLogger(__name__)` in every module

Known issues:
- 2 pre-existing test failures on Python 3.14 (concurrent.futures + SystemExit in mocked context)
- Deferred EXTD-01: Champion ability handler registry for plugin-style dispatch

## Constraints

- **Determinism**: Combat engine must pass benchmark after any change — `python -m simulator.benchmark`
- **No legacy paths**: Do not touch `simulator/Simulator/**`, `simulator/Concurrency/**`, `simulator/Evaluator/**`
- **Verification**: All Python changes must pass `ruff check .` and `ruff format --check .`
- **Parquet rule**: PyArrow must be validated in the same environment running the command

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Include monolithic file splits | User wants full cleanup, accepts higher risk | ✓ Good — all 4 splits completed with determinism preserved |
| Reliability as top priority | Silent failures are the most dangerous class of bugs | ✓ Good — risk-ordered execution caught issues early |
| All 18 concerns in scope | Comprehensive cleanup pass rather than incremental | ✓ Good — 32/32 requirements satisfied in 5 days |
| Mixin composition for splits | Preserves backward-compatible imports via facade re-exports | ✓ Good — zero callers required changes |
| spawn context for multiprocessing | Windows requires spawn, Linux 3.14 changes default | ✓ Good — cross-platform consistency |
| Delete models/exceptions.py | Zero production imports, stdlib exceptions sufficient | ✓ Good — removed 26 LOC dead code |

---
*Last updated: 2026-03-03 after v1.0 milestone*
