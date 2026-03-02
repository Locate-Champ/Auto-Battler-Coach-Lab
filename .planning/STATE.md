---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: in-progress
last_updated: "2026-03-02T07:30:00Z"
progress:
  total_phases: 12
  completed_phases: 11
  total_plans: 18
  completed_plans: 18
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-27)

**Core value:** Stop silent failures — every error path must be explicit, every fallback must be logged
**Current focus:** Phase 11: Combat Engine Split

## Current Position

Phase: 11 of 12 (Combat Engine Split) -- COMPLETE
Plan: 2 of 2 in current phase (11-02 complete -- phase done)
Status: Phase 11 complete -- combat_engine.py split into 8 sub-modules + thin facade (548 LOC)
Last activity: 2026-03-02 -- Completed 11-02-PLAN.md (mixin extraction)

Progress: [###############] 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 18
- Average duration: 5.4 min
- Total execution time: 1.81 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-models-exception-hardening | 1 | 5 min | 5 min |
| 02-observable-fallbacks | 2 | 7 min | 3.5 min |
| 03-dependency-validation-and-resource-management | 2 | 6 min | 3 min |
| 04-type-contracts-and-schema-validation | 2 | 5 min | 2.5 min |
| 05-api-server-hardening | 1 | 12 min | 12 min |
| 06-configuration-extraction-and-ruff-gates | 2 | 8 min | 4 min |
| 07-sklearnevaluator-wiring | 1 | 4 min | 4 min |
| 08-global-state-elimination | 2 | 14 min | 7 min |
| 09-simulator-and-coach-exception-hardening | 1 | 3 min | 3 min |
| 10-infrastructure-file-splits | 2 | 12 min | 6 min |
| 11-combat-engine-split | 2 | 34 min | 17 min |

**Recent Trend:**
- Last 5 plans: 10-01 (4 min), 10-02 (8 min), 11-01 (14 min), 11-02 (20 min)
- Trend: increasing (larger file splits take more time)

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Init]: Models layer exceptions are highest priority — training on bad data is catastrophically worse than a visible error
- [Init]: Monolithic splits are last (Phases 10-12) — all exception handling must be correct before splits embed it
- [Init]: cloud_runner globals must be class-refactored (Phase 8) before cloud_runner is split (Phase 10)
- [Init]: Schema validation must run after normalization — validate after normalization, not before, to avoid rejecting valid Rust Arrow data
- [Init]: Benchmark is a hard gate after every simulator-core change — failing benchmark = stop and revert
- [01-01]: Place _log assignments after all module-level imports to avoid E402 violations
- [01-01]: Use (ImportError, OSError) for extension imports, (ImportError, ModuleNotFoundError) for cross-package imports
- [02-01]: Replace warnings.warn with logging.warning in fe_fast to unify logging mechanism
- [02-01]: No duplicate Cython fallback warning in feature_engineering.py -- fe_fast/__init__.py already covers it
- [02-01]: logging.basicConfig added only to train_xgboost.py __main__ block, not library modules
- [02-02]: Per-batch logging kept at info level (fires every 100 batches, not every batch)
- [02-02]: evaluate.py has no basicConfig -- library module per user decision in CONTEXT.md
- [03-02]: File existence check in _load_combat_data() not at module level -- avoids breaking test imports while failing before game logic
- [03-02]: ImportError and OSError caught separately with distinct diagnostic messages per user decision
- [03-02]: engine_version() lookup wrapped in try/except so pre-flight works even without Rust rebuild
- [03-01]: pyarrow changed from optional to hard dependency -- silent empty iterators were causing invisible training failures
- [03-01]: __exit__ wraps close() in try/except, logs cleanup failure, never suppresses original exception
- [03-01]: __del__ uses getattr for partially-initialized safety and local warnings import for interpreter shutdown
- [04-01]: check_compatibility() returns False for None/wrong-type instead of raising -- "not compatible" is the honest answer
- [04-01]: Added _log.debug() when check_compatibility() returns False -- follows logging patterns from Phases 1-3
- [04-01]: Kept raise NotImplementedError body in BoardEvaluator.score() -- standard ABC convention alongside @abstractmethod
- [04-02]: REQUIRED_COLUMNS split into strict (5 columns) + _REQUIRED_COLUMN_GROUPS (3 groups with alternatives) to support both normalized and raw simulation data formats
- [04-02]: Column groups use any-of semantics: streak OR win_streak, units OR board OR board_names, traits OR trait_names
- [06-01]: Named class NumericFeatureConfig to avoid collision with existing FeatureConfig (boolean toggles)
- [06-01]: Placed config in models/feature_config.py alongside feature_engineering.py, not src/models/
- [06-01]: Used local nc = self._numeric_config shorthand in methods with multiple config references
- [07-01]: Always use model.predict() (not predict_proba) with placement-to-score linear mapping for simplicity across model types
- [07-01]: Replicate _round_num_from_stage() inline in evaluator.py to avoid circular import from coach.coach
- [07-01]: Fixed frozen dataclass mutation bug in _load() using object.__setattr__() pattern
- [08-01]: Worker-local globals (_worker_sim, _worker_parquet_validated) preserved as process-local state -- standard multiprocessing pattern
- [08-01]: Parallel path uses mp.get_context("spawn").Pool() for Windows compatibility
- [08-01]: Clean break: run_batch() removed entirely, no backward compatibility shim per CONTEXT.md
- [08-02]: DataLoader uses mp.get_context("spawn") for cross-platform consistency -- Windows requires spawn, Linux 3.14 changes default
- [08-02]: BatchRunner parallel test uses real multiprocessing.Pool (not mocked) to prove spawn+serialize+run works on Windows
- [09-01]: Applied CCG-widened exception tuples for joblib.load (7 types) and fe.transform (4 types) based on empirical Codex testing
- [09-01]: Used (ImportError, OSError) for all 3 simulator C extension import sites -- same pattern as Phase 1
- [09-01]: Added import pickle to evaluator.py for pickle.UnpicklingError reference
- [10-02]: MRO order _LoaderMixin, _TransformMixin, _BatchTransformMixin -- loaders first for __init__ call order
- [10-02]: TFTFeatureEngineer class defined in facade (not sub-module) to preserve pickle __module__ path
- [10-02]: Cython try/except import block placed in both _transform and _batch modules independently
- [11-01]: Item effects import block moved to _item_database.py (primary consumer) rather than staying in facade
- [11-01]: TYPE_CHECKING pattern used for Unit type hints in _augment_manager.py and _trait_manager.py to avoid circular imports
- [11-01]: AugmentManager augment loading try/except block travels with AugmentManager class to _augment_manager.py
- [11-02]: MRO order CombatEngine(_CombatRunnersMixin, _CombatProcessingMixin, _CombatActionsMixin) -- Actions rightmost (lowest-level), Runners leftmost (highest-level)
- [11-02]: Cython import block placed in _combat_actions.py (sole consumer of _cy_calculate_damage)
- [11-02]: Each mixin uses only self.* for cross-method calls -- no mixin-to-mixin imports
- [11-02]: Removed unused random/deepcopy from facade after runner extraction (moved to _combat_runners.py)

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 12 risk: _abilities_systems.py cross-method call audit required before writing the file — audit self._cast_, self.engine., and self._deal_damage() calls in the special systems section
- Phase 4 risk: pandera Arrow Table validation path behavior for Arrow Tables with schema metadata may differ from pandas DataFrames — verify with synthetic fixture before production use
- Pre-existing: test_api_server.py::test_startup_failure_exits fails on Python 3.14 (concurrent.futures + SystemExit in mocked context)

## Session Continuity

Last session: 2026-03-02
Stopped at: Completed 11-02-PLAN.md (Phase 11 complete)
Resume file: .planning/phases/11-combat-engine-split/11-02-SUMMARY.md
