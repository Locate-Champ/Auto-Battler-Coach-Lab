# Roadmap: Codebase Reliability & Cleanup

## Overview

This milestone systematically eliminates the 18 reliability concerns identified in the codebase audit. The work is ordered by risk: silent training failures (models layer) must be fixed first because they produce wrong models invisibly. Observability and dependency validation follow. Type contracts, schema validation, and API hardening come next. Only after the foundation is clean do the high-complexity structural changes (global state elimination, monolithic file splits) execute — because those changes must not embed the bare-except patterns they would otherwise inherit. Every phase that touches simulator-core code gates on a passing determinism benchmark.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Models Exception Hardening** - Narrow all broad/bare exception handlers in the ML models layer (feature_engineering, data_loader, train_xgboost) (completed 2026-02-27)
- [ ] **Phase 2: Observable Fallbacks** - Wire logging.WARNING for all silent degradation paths (Cython, pickle, module loggers)
- [ ] **Phase 3: Dependency Validation and Resource Management** - Add explicit startup errors for missing pyarrow and combat_data.json; DataLoader context manager; Rust pre-flight check
- [ ] **Phase 4: Type Contracts and Schema Validation** - Fix check_compatibility() return type; document BoardEvaluator contract; add transform_batch() schema validation for both dict and Arrow paths
- [ ] **Phase 5: API Server Hardening** - Migrate FastAPI to lifespan context manager; enforce startup failure gate; replace module globals with app.state
- [ ] **Phase 6: Configuration Extraction and Ruff Gates** - Extract magic numbers to FeatureConfig dataclass; enable ruff BLE/B rules to statically enforce exception hygiene
- [ ] **Phase 7: SklearnEvaluator Wiring** - Implement feature extraction matching training schema; integration test with mock sklearn model
- [ ] **Phase 8: Global State Elimination** - Refactor cloud_runner module globals to class-based BatchRunner; fix DataLoader worker initargs; multiprocessing integration test
- [ ] **Phase 9: Simulator and Coach Exception Hardening** - Second-pass exception narrowing for simulator and coach layers; convert intentional fallbacks to logged specific exceptions
- [ ] **Phase 10: Infrastructure File Splits** - Split cloud_runner.py and feature_engineering.py into focused sub-modules (no determinism dependency)
- [ ] **Phase 11: Combat Engine Split** - Split combat_engine.py (5.3k LOC) into facade + types, hex grid, trait manager, augment manager, item database; benchmark after each step
- [ ] **Phase 12: Champion Abilities Split** - Split champion_abilities.py (5.9k LOC): AbilitiesBase first, then systems, then cost-tier mixins; benchmark after each step

## Phase Details

### Phase 1: Models Exception Hardening
**Goal**: All broad and bare exception handlers in the ML models layer are narrowed to specific exception types, making training failures visible instead of silently swallowed
**Depends on**: Nothing (first phase)
**Requirements**: EXCP-01, EXCP-02
**Success Criteria** (what must be TRUE):
  1. Running `ruff check models/` with BLE001 enabled reports zero violations in feature_engineering.py, data_loader.py, and train_xgboost.py
  2. A deliberately bad input to the models pipeline raises a specific, named exception (not Exception or bare except) that surfaces in the caller's stack trace
  3. Cython and Rust extension imports in models use `except (ImportError, OSError)` so architecture-mismatched extensions fall back rather than crash
  4. No silent pass or broad except in the models layer absorbs an error without re-raising or logging
**Plans:** 1/1 plans complete
Plans:
- [ ] 01-01-PLAN.md — Create exceptions module, narrow all BLE001 violations, widen extension import handlers

### Phase 2: Observable Fallbacks
**Goal**: Every silent performance-degradation path in the codebase emits a logging.WARNING so developers can see when the system is running on a slower fallback
**Depends on**: Phase 1
**Requirements**: OBSV-01, OBSV-02, OBSV-03
**Success Criteria** (what must be TRUE):
  1. When the Cython fe_fast extension is unavailable, a WARNING-level log entry is emitted that names the fallback and the expected performance penalty
  2. When DataLoader activates the pickle fallback disk-I/O path, a WARNING-level log entry is emitted identifying the ~30x slowdown
  3. Every module that previously used print() or silent pass now has a `logging.getLogger(__name__)` logger and routes all diagnostic output through it
  4. The Python log output during a Gate A smoke test contains no unlogged fallback activations
**Plans:** 2 plans
Plans:
- [ ] 02-01-PLAN.md — Wire fallback WARNING logging for Cython/pickle/GPU paths + convert print() in data_loader and train_xgboost
- [ ] 02-02-PLAN.md — Complete logging standardization: rename logger->_log, add loggers to 7 modules, convert remaining print()

### Phase 3: Dependency Validation and Resource Management
**Goal**: Missing runtime dependencies (pyarrow, combat_data.json, Rust extension) are caught at startup with actionable error messages, not at use-time as silent empty results; DataLoader cleans up worker pools automatically
**Depends on**: Phase 2
**Requirements**: DEPV-01, DEPV-02, DEPV-03, RSMG-01, RSMG-02
**Success Criteria** (what must be TRUE):
  1. Importing DataLoader without pyarrow installed raises an explicit ImportError with a message naming pyarrow and explaining the consequence (silent empty iterator)
  2. Starting the simulator with a missing combat_data.json raises an actionable error at import time that includes the expected file path and the command to regenerate it
  3. Importing the Rust extension on a mismatched architecture raises a pre-flight error with a rebuild hint, not a cryptic OSError at first use
  4. DataLoader used as a context manager (`with DataLoader(...) as dl:`) cleans up all worker processes on both normal exit and exception exit without masking the original exception
**Plans:** 2 plans
Plans:
- [ ] 03-01-PLAN.md — Hard pyarrow ImportError + DataLoader context manager with safe cleanup
- [ ] 03-02-PLAN.md — Actionable combat_data.json error + Rust extension pre-flight with version and logging

### Phase 4: Type Contracts and Schema Validation
**Goal**: API contracts at module boundaries are honest — check_compatibility() returns a real bool, BoardEvaluator documents what implementers must provide, and transform_batch() validates its inputs before processing
**Depends on**: Phase 3
**Requirements**: TYPE-01, TYPE-02, SCHM-01, SCHM-02
**Success Criteria** (what must be TRUE):
  1. `RuntimeEvaluator.check_compatibility()` returns True or False in all code paths; callers that branch on its return value produce correct behavior
  2. `BoardEvaluator` base class has a documented abstract contract (either ABC abstractmethod or explicit docstring contract) so implementers know what to override
  3. `FeatureEngineer.transform_batch()` raises a descriptive ValueError listing missing column names when required columns are absent, before any computation runs
  4. Schema validation passes for both the JSONL/dict input path and the Rust Parquet Arrow path — validation runs after normalization, not before, so valid Rust-generated data is not rejected
**Plans:** 2 plans
Plans:
- [ ] 04-01-PLAN.md — Fix evaluator type contracts: BoardEvaluator ABC + check_compatibility() -> bool
- [ ] 04-02-PLAN.md — Add schema validation to transform_batch() and transform_arrow_batch()

### Phase 5: API Server Hardening
**Goal**: The FastAPI server uses the official lifespan pattern, fails loudly if models do not load at startup, and stores all shared state in app.state rather than module-level globals
**Depends on**: Phase 4
**Requirements**: GLBL-03, GLBL-04
**Success Criteria** (what must be TRUE):
  1. The FastAPI server uses `@asynccontextmanager` lifespan and no `@app.on_event("startup")` decorator exists in the codebase
  2. If model loading fails during startup, the server process exits with a non-zero code before any endpoint becomes reachable — no endpoint ever serves a None model
  3. All module-level globals in app/api/server.py are replaced by `app.state` attributes populated inside the lifespan function
  4. `uvicorn --reload` restarts cleanly without carrying stale module-level state across reloads
**Plans**: 1 plan
Plans:
- [ ] 05-01-PLAN.md — Lifespan migration, app.state + Depends() injection, startup failure gate, global exception handler, test suite

### Phase 6: Configuration Extraction and Ruff Gates
**Goal**: Magic numbers in feature_engineering.py are documented and importable via a typed dataclass; ruff BLE/B rules are enforced so future broad exception handlers are caught statically at CI time
**Depends on**: Phase 5
**Requirements**: CONF-01, CONF-02, EXCP-05
**Success Criteria** (what must be TRUE):
  1. All magic numeric constants in feature_engineering.py are replaced by named fields on a frozen `FeatureConfig` dataclass with a docstring explaining the rationale for each value
  2. FeatureConfig can be imported and instantiated in a test with overridden values, verifying constants are not hardcoded at use sites
  3. ruff.toml includes `"BLE", "B"` in the select list and `ruff check .` passes with zero violations across the entire codebase
  4. A deliberately introduced `except Exception:` in any Python file causes `ruff check .` to fail with a BLE001 error
**Plans**: 2 plans
Plans:
- [ ] 06-01-PLAN.md — Extract magic numbers to frozen NumericFeatureConfig dataclass with tests
- [ ] 06-02-PLAN.md — Fix all 82 BLE+B violations and enable ruff BLE+B rule enforcement

### Phase 7: SklearnEvaluator Wiring
**Goal**: SklearnEvaluator extracts features from GameState using the same schema as the XGBoost training pipeline, and the wiring is verified with an integration test
**Depends on**: Phase 6
**Requirements**: SKLR-01, SKLR-02
**Success Criteria** (what must be TRUE):
  1. Calling `SklearnEvaluator.evaluate(game_state)` on a well-formed GameState returns a numeric score without raising NotImplementedError
  2. The feature vector produced by SklearnEvaluator matches the column order and normalization expected by the XGBoost model trained in train_xgboost.py (verified by comparing column names in a test)
  3. An integration test using a mock sklearn model passes in CI, confirming the full evaluate() call path without requiring a real trained model artifact
**Plans**: TBD

### Phase 8: Global State Elimination
**Goal**: cloud_runner.py module-level globals are replaced by a class-based BatchRunner with instance-scoped state; DataLoader worker pool uses explicit initargs; multiprocessing integration confirms Windows spawn semantics work correctly
**Depends on**: Phase 7
**Requirements**: GLBL-01, GLBL-02
**Success Criteria** (what must be TRUE):
  1. `BatchRunner` can be instantiated twice in the same process with different configurations without the instances sharing state
  2. Worker processes spawned by BatchRunner receive the simulator by value through initargs, not by inheriting module-level globals — verified on Windows where spawn is the default start method
  3. DataLoader worker pool initialization uses explicit initargs to pass shared resources, with no module-level global mutation after pool creation
  4. An integration test runs a real `multiprocessing.Pool` with the new BatchRunner and confirms workers produce correct results without a stale-global failure
**Plans**: TBD

### Phase 9: Simulator and Coach Exception Hardening
**Goal**: All broad and bare exception handlers in the simulator and coach layers are narrowed to specific types; intentional fallbacks are converted to logged specific-exception handlers
**Depends on**: Phase 8
**Requirements**: EXCP-03, EXCP-04
**Success Criteria** (what must be TRUE):
  1. Running `ruff check simulator/ coach/` with BLE001 enabled reports zero violations
  2. Every intentional fallback in simulator and coach layers uses `except SpecificErrorType` followed by a `log.warning()` call that names the fallback and the reason
  3. The simulator determinism benchmark passes after all exception handler changes — `python -m simulator.benchmark` exits zero with the same output as before
  4. No simulator fallback path silently degrades behavior without a logged warning visible in coach output
**Plans**: TBD

### Phase 10: Infrastructure File Splits
**Goal**: cloud_runner.py and feature_engineering.py are split into focused sub-modules under 1k LOC each, with all external import paths preserved via facade re-exports; no determinism risk because neither file is simulator-core
**Depends on**: Phase 9
**Requirements**: SPLT-01, SPLT-02, SPLT-05
**Success Criteria** (what must be TRUE):
  1. `from simulator.cloud_runner import CloudRunner` and all existing import paths resolve correctly after the split — no callers require changes
  2. `from models.feature_engineering import FeatureEngineer` and all existing import paths resolve correctly after the split
  3. cloud_runner.py and feature_engineering.py each contain fewer than 1000 LOC after the split (the remainder lives in underscore-prefixed sub-modules)
  4. The full test suite passes without modification after both splits — `python -m pytest` exits zero
**Plans**: TBD

### Phase 11: Combat Engine Split
**Goal**: combat_engine.py (5.3k LOC) is split into a CombatEngine facade plus private sub-modules for types, hex grid, trait manager, augment manager, and item database; determinism is verified by benchmark after every individual structural change
**Depends on**: Phase 10
**Requirements**: SPLT-03, SPLT-06
**Success Criteria** (what must be TRUE):
  1. `from simulator.core.combat_engine import CombatEngine` resolves correctly and all existing callers work without changes
  2. combat_engine.py is reduced to a CombatEngine class facade under 800 LOC with all types and managers in private underscore-prefixed sub-modules
  3. `python -m simulator.benchmark` passes with identical output (fixed seed) after every individual sub-module extraction step — each step is gated on a passing benchmark before the next begins
  4. The five target sub-modules exist and are independently importable: `_combat_types.py`, `_hex_grid.py`, `_trait_manager.py`, `_augment_manager.py`, `_item_database.py`
**Plans**: TBD

### Phase 12: Champion Abilities Split
**Goal**: champion_abilities.py (5.9k LOC) is split into AbilitiesBase plus systems and cost-tier mixins using the mixin composition pattern; AbilitiesBase is extracted first as a hard prerequisite; determinism is verified after every step
**Depends on**: Phase 11
**Requirements**: SPLT-04, SPLT-05, SPLT-06, BNCH-01
**Success Criteria** (what must be TRUE):
  1. `from simulator.core.champion_abilities import ChampionAbilities` resolves correctly after every split step — `python -c "from simulator.core.champion_abilities import ChampionAbilities"` exits zero at each intermediate state
  2. AbilitiesBase is extracted into `_abilities_base.py` before any cost-tier mixin file is created — the base extraction is a standalone commit that passes benchmark before cost-tier work begins
  3. `python -m simulator.benchmark` passes with identical output (fixed seed) after every individual split step including AbilitiesBase, each systems file, and each cost-tier mixin file
  4. Cross-engine parity tests in the benchmark suite are batched to reduce CI overhead per BNCH-01, and the batched suite passes with the same result set as the unbatched baseline
  5. champion_abilities.py is reduced to a thin facade under 250 LOC with all ability implementation in underscore-prefixed mixin sub-modules
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Models Exception Hardening | 0/1 | Complete    | 2026-02-27 |
| 2. Observable Fallbacks | 0/2 | Not started | - |
| 3. Dependency Validation and Resource Management | 0/2 | Not started | - |
| 4. Type Contracts and Schema Validation | 0/2 | Not started | - |
| 5. API Server Hardening | 0/1 | Not started | - |
| 6. Configuration Extraction and Ruff Gates | 0/2 | Not started | - |
| 7. SklearnEvaluator Wiring | 0/TBD | Not started | - |
| 8. Global State Elimination | 0/TBD | Not started | - |
| 9. Simulator and Coach Exception Hardening | 0/TBD | Not started | - |
| 10. Infrastructure File Splits | 0/TBD | Not started | - |
| 11. Combat Engine Split | 0/TBD | Not started | - |
| 12. Champion Abilities Split | 0/TBD | Not started | - |
