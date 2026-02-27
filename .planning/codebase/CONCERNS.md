# Codebase Concerns

**Analysis Date:** 2026-02-27

## Incomplete Implementations

**SklearnEvaluator Feature Extraction Not Wired:**
- Issue: `SklearnEvaluator.score()` raises `NotImplementedError` with message "SklearnEvaluator feature extraction is not wired yet"
- Files: `coach/scoring/evaluator.py:62-67`
- Impact: ML-backed board evaluation is non-functional; only HeuristicEvaluator and LinearEvaluator work
- Fix approach: Implement feature extraction pipeline to match training schema, integrate with sklearn model.predict_proba()

**Base BoardEvaluator Abstract:**
- Issue: Base `BoardEvaluator.score()` raises NotImplementedError with no message
- Files: `coach/scoring/evaluator.py:13-15`
- Impact: Cannot instantiate base class directly; relies on inheritance to actual implementations
- Fix approach: This is correct OOP pattern; no change needed unless allowing base class instantiation

## Tech Debt & Architecture Issues

**Global State Management in Cloud Runner:**
- Issue: `cloud_runner.py` uses module-level globals `_RUST_FULL_SIMULATOR` and `_RUST_PARQUET_API_VALIDATED` with global keyword mutations
- Files: `simulator/cloud_runner.py:55-56, 137-159, 270-300`
- Impact:
  - Non-reentrant; breaks if called from multiple threads
  - State persists across multiple invocations unexpectedly
  - Difficult to test without module reloads
  - Implicit dependency on initialization order
- Fix approach: Refactor to class-based runner with instance state; pass Rust simulator as dependency injection parameter

**Overly Broad Exception Handlers:**
- Issue: 39 instances of `except Exception:` or bare `except:` without specific exception type
- Files: Scattered across `simulator/`, `models/`, `coach/`
- Examples:
  - `simulator/benchmark.py:38-44` catches all exceptions from Rust engine import
  - `models/feature_engineering.py:16-29` catches all ImportError variants silently
  - `models/train_xgboost.py:43-49` catches all exceptions checking CUDA availability
- Impact: Silently swallows errors that should fail fast; makes debugging harder
- Fix approach: Specify exception types (e.g., `except ImportError`, `except XGBoostError`); log warnings for fallback paths

**Global Worker State in DataLoader:**
- Issue: `DataLoader` uses module-level global `_worker_fe` shared across multiprocessing workers
- Files: `models/data_loader.py:28, 33-40`
- Impact:
  - Process pool initialization depends on global mutation
  - Pickle fallback hides failures: if FeatureEngineer fails to pickle, silently switches to disk I/O (~30ms per worker slowdown)
  - Comments flag this as performance risk but no metrics tracked
- Fix approach: Move worker state into pool context manager; make pickle requirement explicit or use dill/cloudpickle

**Feature Engineering Cython Dependency Without Fallback Hooks:**
- Issue: Optional Cython acceleration (`fe_fast`) loaded in try/except but silent failures
- Files: `models/feature_engineering.py:16-29`
- Impact:
  - Performance degrades silently if Cython module missing
  - No log warnings to alert users
  - Performance regression not caught in testing
- Fix approach: Log at INFO level when Cython falls back to pure Python; add CI check for Cython build

**Large Monolithic Files Without Clear Responsibility Boundaries:**
- Issue: Several files >2000 lines with mixed concerns
  - `simulator/core/champion_abilities.py` (5911 lines): Champion-specific ability handlers + damage calculations
  - `simulator/core/combat_engine.py` (5306 lines): Core combat loop + state management + ability dispatch
  - `models/feature_engineering.py` (2100 lines): Feature transforms + composition analysis + economy metrics
  - `simulator/cloud_runner.py` (2048 lines): Batch orchestration + error handling + Rust integration + data collection
- Impact:
  - Difficult to navigate and understand; high cognitive load
  - Testing individual concerns requires full module setup
  - Changes to one concern risk breaking another
  - Code duplication and inconsistent patterns
- Fix approach:
  - Split `champion_abilities.py`: separate ability dispatch (200 LOC) from per-champion handlers (group into traits/roles)
  - Split `combat_engine.py`: core loop (800 LOC), unit management (400 LOC), ability execution (400 LOC)
  - Split `cloud_runner.py`: runner state (600 LOC), Rust integration (400 LOC), data collection (500 LOC)
  - Split `feature_engineering.py`: composition features (400 LOC), economy features (300 LOC), trait derivation (200 LOC)

## Data & Serialization Risks

**Pickle-Based Worker Initialization with Silent Fallback:**
- Issue: `DataLoader._ensure_pool()` pickles FeatureEngineer for workers but silently falls back to disk I/O on failure
- Files: `models/data_loader.py:86-112`
- Impact:
  - Pickle failure silently downgrades performance 30x (~1ms vs ~30ms per worker)
  - Suggests FeatureEngineer has mutable/unpickleable state that may be lost
  - No alarm when this occurs in production data runs
- Fix approach:
  - Document what prevents pickling in FeatureEngineer.__getstate__
  - Add explicit `force_pickle=False` flag with warning if used
  - Track pickle success/failure metrics in logs

**Parquet/Arrow Optional Without Clear Validation Path:**
- Issue: PyArrow is optional in data loading; missing pyarrow silently returns empty iterator
- Files: `models/data_loader.py:121-143`
- Impact:
  - No data loaded if pyarrow missing, no error raised
  - Model training silently trains on empty dataset
  - Per CLAUDE.md rule 3, pyarrow must be validated but code does not enforce this
- Fix approach:
  - Raise explicit error if pyarrow needed but missing, per CLAUDE.md rule
  - Add `validate_pyarrow()` call at module load time in training scripts

## Performance Bottlenecks

**Cross-Engine Benchmark/Validation Overhead:**
- Issue: `benchmark.py` manually switches between Python and Rust engines for parity testing
- Files: `simulator/benchmark.py:36-56`
- Impact:
  - Slow cross-engine validation adds latency to CI
  - Requires Rust engine rebuilt + installed for each test
  - No batching of parity tests
- Fix approach:
  - Batch all parity tests in single cross-engine run
  - Cache Rust engine build artifact in CI
  - Add optional `--skip-cross-engine` flag for development

**DataLoader Worker Pool Not Closed Automatically:**
- Issue: `DataLoader._pool` must be manually closed; no context manager
- Files: `models/data_loader.py:66-119`
- Impact:
  - Leaked worker processes if `close()` not called
  - Easy to forget in notebooks/interactive usage
  - Resource cleanup not guaranteed
- Fix approach: Implement `__enter__/__exit__` to make DataLoader a context manager

## Testing & Observability Gaps

**SklearnEvaluator Feature Extraction Untested:**
- Issue: NotImplementedError means code path never exercises actual sklearn integration
- Files: `coach/scoring/evaluator.py:45-67`
- Impact: Regression not caught if sklearn import breaks
- Priority: High (blocks ML-backed evaluation path)
- Fix approach: Implement feature extraction + add unit tests with mock sklearn model

**Rust Extension Rebuild Requirement Not Documented at Runtime:**
- Issue: If Rust extension missing/wrong arch, error message points to manual rebuild but CI doesn't pre-build
- Files: `simulator/cloud_runner.py:89-103, 144-157`
- Impact:
  - Users see cryptic rebuild hints
  - No automatic detection of wrong Python version used
- Fix approach: Add pre-flight check that verifies Rust extension matches running Python interpreter

**Coach Evaluator Compatibility Check Returns None:**
- Issue: `RuntimeEvaluator.check_compatibility()` returns explicit `None` (should return bool or raise)
- Files: `coach/scoring/evaluator.py:135-137`
- Impact: Type contract unclear; cannot tell if check passed/failed
- Fix approach: Remove function or return True; make check raise on incompatibility

## Known Behavioral Risks

**Bare Exception Catch in Feature Engineering Initialization:**
- Issue: `try/except Exception` in feature engineering imports (39 instances total across codebase)
- Files: Various
- Example: `models/feature_engineering.py:26` catches all exceptions from Cython import
- Impact: Hides import errors (version mismatch, missing dependency, typo in module name)
- Fix approach: Log specific exception type + message; make silent fallback explicit in docstring

**API Server Global Model State:**
- Issue: `app/api/server.py` uses module globals `recommender` and `placement_model` initialized in `@app.on_event("startup")`
- Files: `app/api/server.py:32, 36-54`
- Impact:
  - Models not reloaded on request
  - Thread-safety unclear (multiple workers may mutate state)
  - No error if startup fails; endpoints still accessible with None models
- Fix approach:
  - Use dependency injection (FastAPI Depends) for model lifecycle
  - Add startup validation that raises if models cannot load

## Missing Context & Edge Cases

**No Documented Fallback for Missing Combat Data:**
- Issue: `_load_combat_data()` caches JSON at module level; no handling if file missing
- Files: `simulator/core/combat_engine.py:67-73`
- Impact: Entire simulator fails with unclear error if combat_data.json missing
- Fix approach: Add explicit check + helpful error message at import time

**FeatureEngineer.transform_batch() Requires Specific Column Names:**
- Issue: Feature extraction assumes exact column names from snapshot schema; no validation
- Files: `models/feature_engineering.py:144+`
- Impact: Silent feature corruption if input columns renamed or missing
- Fix approach: Add schema validation at entry point; raise with clear error if columns missing

## Scaling & Maintenance Concerns

**Champion Ability Handlers Not Extensible:**
- Issue: New champion abilities require editing `champion_abilities.py` directly; runtime dispatch by `api_name.lower()`
- Files: `simulator/core/champion_abilities.py:24-35`
- Impact: Central bottleneck for new set releases; no plugin system
- Fix approach: Consider registry-based dispatch (register handlers dynamically) for future sets

**Hard-Coded Magic Numbers in Feature Engineering:**
- Issue: Many constants without justification (e.g., `DEFAULT_STAGE_DIVISOR=7`, trait breakpoints, scaling factors)
- Files: `models/feature_engineering.py:31-70`
- Impact: Difficult to tune or understand why these values chosen; scattered across file
- Fix approach: Move to config dataclass with comments on source/rationale

---

*Concerns audit: 2026-02-27*
