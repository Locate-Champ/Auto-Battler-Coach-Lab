# Pitfalls Research

**Domain:** Python codebase refactoring — monolithic file splits, error handling hardening, global state elimination, schema validation, Rust/Cython extension boundary changes
**Researched:** 2026-02-27
**Confidence:** HIGH (all pitfalls grounded in actual code patterns found in this repository)

---

## Critical Pitfalls

### Pitfall 1: Breaking the champion_abilities / combat_engine circular-import avoidance pattern

**What goes wrong:**
`champion_abilities.py` uses ~100+ deferred (local) imports inside individual handler methods:
```python
def _cast_ahri(self, unit, enemies, allies, ability_vars):
    from .combat_engine import DamageType, HexGrid  # line-level import
```
This is an intentional design to avoid a circular import: `combat_engine.py` imports `ChampionAbilities`, which would circularly import `combat_engine` if the import were at the module level. When splitting `champion_abilities.py` into per-role sub-files (e.g., `abilities/mage.py`, `abilities/tank.py`), the refactorer typically promotes these deferred imports to module-level in the new sub-files, which resurrects the circular import and causes `ImportError` at startup.

**Why it happens:**
Splitting a monolithic file encourages "cleaning up" the code by removing the local imports pattern, which is considered a code smell. But the pattern here is load-bearing, not aesthetic.

**How to avoid:**
Preserve the deferred `from .combat_engine import ...` pattern exactly as-is in every sub-file. Do not promote these to module-level. Alternatively, extract the needed types (`DamageType`, `HexGrid`, `UnitState`, `DotEffect`) into a separate `combat_types.py` module that neither `combat_engine.py` nor `champion_abilities.py` imports from each other — then both can import types from the shared module at the module level without circularity.

**Warning signs:**
- `ImportError: cannot import name 'CombatEngine' from partially initialized module` at process start
- Any edit that moves a `from .combat_engine import` from inside a method to the top of a new sub-file
- A new file in `simulator/core/abilities/` that has module-level `from ..combat_engine import DamageType`

**Phase to address:**
Monolithic file split phase. Before writing any split, audit all method-local imports in `champion_abilities.py` and document the circular dependency chain explicitly.

---

### Pitfall 2: Simulator benchmark not run after every structural change, masking RNG-path drift

**What goes wrong:**
The determinism contract for `simulator/core/combat_engine.py` depends on the exact call sequence reaching the Python `random` module in the same order. When splitting `combat_engine.py` into submodules (core loop, unit management, ability execution), re-ordering method definitions or inlining helper calls can silently change the RNG call sequence. The benchmark (`python -m simulator.benchmark`) catches this — but only if run after each structural change, not just at the end of the split.

**Why it happens:**
The natural workflow is to do the full split in one pass, then verify. Any single refactor step that reorders how methods call each other (even if behaviorally equivalent under a normal interpreter) can accumulate into a seed-dependent divergence that is hard to bisect later.

**How to avoid:**
Run `python -m simulator.benchmark` after each logically distinct change to `combat_engine.py`, not once at the end of the phase. Treat a failing benchmark the same as a failing test: stop, revert the last step, and proceed more carefully. The benchmark must also cover Rust-vs-Python parity if the `HybridCombatEngine` dispatch path changes.

**Warning signs:**
- Benchmark runs only once at phase completion
- Helper methods extracted from `CombatEngine` are reordered relative to original file
- Any method on `CombatEngine` moves to a different module with a different resolution path
- `_COMBAT_DATA_CACHE` module-level dict moves to a different module (changes the cache key semantics)

**Phase to address:**
Monolithic file split phase — specifically the `combat_engine.py` split task. Set a rule: benchmark after each method extraction, not after the full split.

---

### Pitfall 3: Over-narrowing bare except handlers breaks the Rust extension fallback chain

**What goes wrong:**
`simulator/core/engine_wrapper.py` and `simulator/benchmark.py` use `except Exception` on Rust engine import attempts to gracefully fall back to Python. When "fixing" bare excepts, replacing `except Exception` with `except ImportError` on lines like:
```python
try:
    from tft_combat_engine import RustCombatEngine
    ...
except Exception:
    return None
```
...is correct. But if the Rust `.so`/`.pyd` file exists but was compiled for a different CPython version, the failure is not `ImportError` — it is `SystemError`, `OSError`, or on some platforms a `LoadLibraryError` variant (subclass of `OSError`). Catching only `ImportError` will let these propagate uncaught and crash the process instead of falling back to Python.

**Why it happens:**
`ImportError` is the obvious exception to catch for missing modules. Developers don't intuitively consider that a present-but-incompatible extension raises a different exception class.

**How to avoid:**
For Rust/Cython extension imports that serve as optional accelerators, catch `(ImportError, OSError)` at minimum, or retain `except Exception` with a narrowing note in the comment. For Rust imports where fallback is critical, the pattern should be:
```python
try:
    from tft_combat_engine import RustCombatEngine
except (ImportError, OSError):
    RustCombatEngine = None  # type: ignore[assignment,misc]
```
For imports where failure is fatal (not optional), replace with `except ImportError` and let other exceptions propagate — that is the correct behavior.

**Warning signs:**
- Any `except Exception` on a Rust/Cython import is replaced with `except ImportError` alone
- `_try_rust_engine()` in `engine_wrapper.py` is narrowed to `ImportError` only
- The `except Exception` catch in `benchmark.py:38-44` is changed without confirming which exception types the current Rust wheel raises on arch mismatch

**Phase to address:**
Bare except hardening phase. Audit each site: classify as (a) optional accelerator — use `(ImportError, OSError)`, (b) fatal dependency — use `ImportError` only, (c) logging fallback — use `except Exception` with `_log.warning`.

---

### Pitfall 4: Removing global state from cloud_runner while multiprocessing workers still reference the module-level globals

**What goes wrong:**
`cloud_runner.py` has two module-level globals: `_RUST_FULL_SIMULATOR` and `_RUST_PARQUET_API_VALIDATED`. Worker processes spawned by `multiprocessing.Pool` get a forked copy of the parent's memory on Unix (fork start method), so after a global is set in the parent, new workers inherit it. If the globals are moved to instance state on a `BatchRunner` class but the `multiprocessing` pool initializer still references the old module path (or workers are spawned before the instance is created), workers get `None` where they expect an initialized simulator. On Windows (spawn start method, which is the default here), the module is re-imported from scratch in each worker — so any global set after fork won't be there regardless.

**Why it happens:**
The refactoring creates a `BatchRunner` class with instance state, passes it to pool workers via the `initializer` argument — but the initializer function signature still references the module-level path `simulator.cloud_runner._RUST_FULL_SIMULATOR` by name. The global is gone from the module, the workers import `None`.

**How to avoid:**
Pass the simulator object explicitly through the pool `initargs` tuple when converting to class-based design. Do not rely on module-level globals surviving into worker processes on either fork or spawn. The initializer function should receive the simulator as a parameter and set it in the worker's own module-level variable (which is acceptable as a worker-local state):
```python
_worker_simulator = None

def _init_worker(rust_simulator_bytes):
    global _worker_simulator
    _worker_simulator = pickle.loads(rust_simulator_bytes)
```

**Warning signs:**
- Workers return `AttributeError: module 'simulator.cloud_runner' has no attribute '_RUST_FULL_SIMULATOR'`
- Pool initializer functions that access `cloud_runner._RUST_FULL_SIMULATOR` by dotted path rather than via injected parameter
- Tests that mock the module global pass, but integration tests with actual multiprocessing fail

**Phase to address:**
Global state elimination phase. When refactoring `cloud_runner.py` to class-based design, simultaneously update the pool initializer to use parameter injection.

---

### Pitfall 5: DataLoader context manager __exit__ silently swallowing exceptions because close() ignores pool errors

**What goes wrong:**
When adding `__enter__`/`__exit__` to make `DataLoader` a context manager, the natural implementation is:
```python
def __exit__(self, exc_type, exc_val, exc_tb):
    self.close()
    return False  # don't suppress exceptions
```
The existing `close()` method calls `pool.close()` then `pool.join()`. If a worker raised an exception that was not surfaced to the main process, `pool.join()` may hang or suppress the error. The `__exit__` returning `False` is correct — but if `close()` itself raises (e.g., pool already terminated), the original exception is replaced by the `close()` exception.

**Why it happens:**
Context manager `__exit__` implementations commonly wrap `close()` in a try/except to avoid masking the original exception with cleanup errors. Omitting this means a `MemoryError` in `close()` obscures the actual data loading error.

**How to avoid:**
```python
def __exit__(self, exc_type, exc_val, exc_tb):
    try:
        self.close()
    except Exception as cleanup_err:
        if exc_type is None:
            raise  # no original exception; re-raise cleanup error
        _log.warning("DataLoader.close() error during exception cleanup: %s", cleanup_err)
    return False
```

**Warning signs:**
- `__exit__` that calls `self.close()` without try/except around it
- Tests that only exercise the happy path (no exception during context) passing fine but error-path tests never written
- `pool.terminate()` not called in `close()` when `pool.join()` would block

**Phase to address:**
Context manager addition phase. Write a test that raises inside `with DataLoader(...) as dl:` and verify the original exception propagates cleanly.

---

### Pitfall 6: Schema validation for feature engineering rejects valid rows due to column aliasing in Parquet vs. JSONL paths

**What goes wrong:**
`FeatureEngineer.transform_batch()` (dict path) and `transform_arrow_batch()` (Arrow path) both read the same logical column names, but Parquet files written by the Rust engine may alias some columns differently (e.g., `unit_count` vs. `units_count`, `trait_list` vs `traits`). Adding schema validation at `transform_batch()` entry point that checks for exact column names will reject Rust-generated Parquet batches that have equivalent but differently-named columns, silently returning zero-length arrays or raising on valid data.

**Why it happens:**
The JSONL path goes through `normalize_jsonish_fields()` (from `snapshot_schema.py`) which normalizes aliases. The Arrow path skips normalization to avoid dict conversion overhead. Adding validation that passes on JSONL-normalized dicts but not on raw Arrow batches creates a split-brain validation path.

**How to avoid:**
Apply schema validation after the normalization step (for the dict path) or add a separate Arrow-aware schema check that accounts for known column aliases. Do not validate raw column names against the normalized schema in `transform_arrow_batch()`. The `snapshot_schema.py:JSONISH_COLUMNS` set is the canonical alias mapping — check against it, not against raw names.

**Warning signs:**
- Validation added at the top of `transform_batch()` before `normalize_jsonish_fields()` is called
- `transform_arrow_batch()` has column name validation that doesn't account for the Rust Parquet writer's column naming conventions
- Gate B runs produce 0-row training datasets after adding validation, but JSONL test files pass fine

**Phase to address:**
Schema validation phase. Validate AFTER normalization in the dict path. For Arrow path, add a column presence check against the `JSONISH_COLUMNS` alias map rather than against exact names.

---

### Pitfall 7: Feature engineering split breaks the Cython fast path dispatch via attribute lookup

**What goes wrong:**
The Cython fast path in `models/feature_engineering.py` is loaded at module level:
```python
try:
    from .fe_fast import team_summary_fast as _cy_team_summary
    from .fe_fast import parse_units_column_fast as _cy_parse_units_column
    _CYTHON_FE = True
except ImportError:
    _cy_team_summary = None
    _cy_parse_units_column = None
    _CYTHON_FE = False
```
When splitting `feature_engineering.py` into sub-modules (e.g., `composition_features.py`, `economy_features.py`), each sub-module needs its own conditional import of the Cython symbols it uses. If a sub-module moves a function that uses `_cy_team_summary` but doesn't re-declare the Cython import, it will reference the parent module's `_cy_team_summary` via `from .feature_engineering import _cy_team_summary` — creating a new import dependency on the parent that may introduce circular imports or silently bind to `None` if the parent's try/except hasn't run yet.

**Why it happens:**
The natural refactoring move is to import the shared Cython symbols from wherever they were originally defined. But module-level `None`-initialized variables don't signal their "optional" nature — they look like normal imports.

**How to avoid:**
Each new sub-module that uses Cython-accelerated functions must declare its own conditional import at the top:
```python
try:
    from .fe_fast import team_summary_fast as _cy_team_summary
except ImportError:
    _cy_team_summary = None
```
Do not cross-import `_cy_team_summary` from a sibling module. The `_CYTHON_FE` boolean should remain in a single shared location (e.g., `fe_fast/__init__.py:CYTHON_AVAILABLE`) that all sub-modules can import without risk.

**Warning signs:**
- A new sub-module imports `_cy_team_summary` from `feature_engineering` (the parent) rather than from `fe_fast`
- `CYTHON_AVAILABLE` flag is copy-pasted as a local boolean in multiple sub-modules (they may diverge if one's import fails and another's doesn't)
- Performance benchmark shows pure-Python path even after Cython is confirmed installed

**Phase to address:**
Monolithic file split phase — specifically `feature_engineering.py`. Establish the Cython import pattern for sub-modules before writing any sub-module code.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Keep `except Exception` with a `# noqa` comment on Rust extension imports instead of specifying `(ImportError, OSError)` | Avoids researching exact exception types per platform | Masking real errors becomes permanent technical debt | Never — document the two-exception pattern once and apply consistently |
| Re-export all split symbols from the original module's `__init__.py` via `from .submodule import *` | No downstream import breaks | Star imports hide what is actually public; future linting and type checking becomes harder | Acceptable as a transitional shim for one milestone, remove in the following milestone |
| Skip running `simulator.benchmark` mid-split and batch at the end | Faster iteration | Single bisect point becomes impossible if determinism breaks; hard to find which step caused it | Never for `combat_engine.py` splits |
| Add schema validation as a `logging.warning` rather than raising | No test breakage in the short term | The entire point of the schema validation concern is preventing silent feature corruption | Never — the concern explicitly requires raising with a clear error |
| Use `contextlib.suppress(Exception)` in `default_evaluator()` instead of specific exceptions | Quick silencing | Hides `MemoryError`, `KeyboardInterrupt` — wrong class of exceptions for this scope | Never |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Rust `tft_combat_engine` extension | Catch only `ImportError` when checking for extension presence | Catch `(ImportError, OSError)` — wrong arch `.pyd`/`.so` raises `OSError` not `ImportError` |
| Cython `fe_fast` / `combat_fast` extensions | Assume `_CYTHON_FE = False` means pure Python is slower by a known factor | Log the fallback at `logging.INFO` level so CI can detect performance regression |
| `multiprocessing.Pool` with pickled `FeatureEngineer` | Test pickle success in the main process only | Test that workers actually initialize correctly by running a trivial transform task on pool creation |
| Parquet Arrow path vs. JSONL dict path | Add column validation only to one of the two ingestion paths | Both paths must validate equivalently — normalize first, then validate |
| FastAPI `@app.on_event("startup")` global model state | Convert to `app.state` without changing dependency injection pattern | Use `FastAPI.state` for process-level singletons, use `Depends()` for per-request access |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Over-validating in `transform_arrow_batch()` — checking column names per-batch rather than per-schema | 300K-row Gate B run takes 2x longer with schema checks; profiler shows `set.intersection` in feature hot path | Validate schema once on first batch, cache result; do not re-validate identical schemas per batch | At any dataset size — Arrow batch iteration is already the bottleneck |
| Moving `_COMBAT_DATA_CACHE` dict into a class instance during `combat_engine.py` split | Each `CombatEngine()` instantiation re-parses `combat_data.json`; benchmark shows 8ms vs 0.1ms cold start | Keep the module-level cache; instance state should hold a reference to the shared dict, not own a copy | When benchmark is run on a suite that instantiates many engines |
| Adding `pickle.loads` verification in `DataLoader._ensure_pool()` to prove pickle succeeded | Pool startup takes 30% longer as all workers deserialize a verification payload | Trust the existing `try/except (pickle.PicklingError, TypeError)` pattern; do not add redundant deserialization round-trips | At Gate B scale with 64 workers |

---

## "Looks Done But Isn't" Checklist

- [ ] **Bare except hardening:** Each site must be audited for which exception types the fallback path actually needs — replacing with `ImportError` alone is only correct for pure-Python optional dependencies, not Rust/Cython `.so`/`.pyd` files. Verify by checking if the extension file exists but is arch-mismatched.
- [ ] **Global state elimination in cloud_runner:** After converting to `BatchRunner` class, verify that pool workers receive the simulator via `initargs`, not via module-level lookup. Run a multiprocessing integration test (not just a unit test with the class).
- [ ] **DataLoader context manager:** Verify that an exception raised inside `with DataLoader(...) as dl:` propagates to the caller rather than being replaced by a `close()` error. Write a test with a mock that raises in `_ensure_pool()`.
- [ ] **Schema validation:** Confirm validation runs on Rust-generated Parquet (not just JSONL test fixtures). Gate B dry-run with the validation active is the only reliable check.
- [ ] **combat_engine.py split determinism:** Run `python -m simulator.benchmark` against the same seed before and after each split step, not just at the end. Log the exact seed used so the same seed can be re-run for bisect.
- [ ] **champion_abilities.py split:** Confirm no method-local `from .combat_engine import` was promoted to module-level in any sub-file. Run `python -c "from simulator.core.champion_abilities import ChampionAbilities"` as a smoke test after each file is created.
- [ ] **Feature engineering split Cython dispatch:** After the split, run a benchmark that exercises the Cython path explicitly (not just confirms it doesn't crash). If `_cy_team_summary is None` in any sub-module when Cython is installed, the dispatch silently fell back.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Circular import introduced in combat_engine split | MEDIUM | `git bisect` to find which file creation triggered it; move offending top-level import back inside the method that uses it |
| Benchmark determinism failure after split | HIGH | Revert the most recent structural change; compare call graph with `cProfile` against the pre-split baseline; find first diverging RNG call |
| Workers receive `None` simulator after global state removal | LOW | Add `assert _worker_simulator is not None` at top of worker function; check that `initargs` passes the serialized simulator bytes |
| Schema validation rejects valid Rust Parquet rows | LOW | Check `snapshot_schema.JSONISH_COLUMNS` alias map; confirm validation runs after `normalize_jsonish_fields()`, not before |
| Cython dispatch silently broken after feature_engineering split | LOW | Add `assert _cy_team_summary is not None` guarded by `if _CYTHON_FE` in each sub-module; run a micro-benchmark comparing wall-clock against known baseline |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Circular import from champion_abilities split (Pitfall 1) | Monolithic file split — champion_abilities task | `python -c "from simulator.core.champion_abilities import ChampionAbilities"` must succeed with no `ImportError`; run before moving to next task |
| RNG drift in combat_engine split (Pitfall 2) | Monolithic file split — combat_engine task | `python -m simulator.benchmark` with fixed seed must produce identical output to pre-split baseline |
| Over-narrowing Rust extension except handlers (Pitfall 3) | Bare except hardening phase | On a machine with a mismatched-arch Rust wheel installed, `HybridCombatEngine()` must fall back to Python without crashing |
| Global state / multiprocessing worker init (Pitfall 4) | Global state elimination phase | Integration test that spawns a real `multiprocessing.Pool` with the new `BatchRunner` class; confirm workers process a batch correctly |
| DataLoader context manager cleanup exception masking (Pitfall 5) | Context manager addition phase | Unit test: raise inside `with DataLoader(...):`; confirm original exception propagates, not a `close()` exception |
| Schema validation breaking Arrow path (Pitfall 6) | Schema validation phase | Gate B dry-run (or synthetic Rust Parquet fixture) with validation active; confirm row count matches pre-validation run |
| Cython dispatch broken by feature_engineering split (Pitfall 7) | Monolithic file split — feature_engineering task | Micro-benchmark comparing transform throughput per-row with and without Cython; must match pre-split performance |

---

## Sources

- Direct code inspection: `simulator/core/champion_abilities.py` (100+ method-local `from .combat_engine import` patterns confirming the deferred import design)
- Direct code inspection: `simulator/core/engine_wrapper.py` (`_try_rust_engine` with `except Exception` fallback chain)
- Direct code inspection: `models/data_loader.py` (`_ensure_pool` pickle fallback, `_iter_parquet_rows` silent return on `pq is None`)
- Direct code inspection: `models/feature_engineering.py` (Cython conditional import at module level, `_CYTHON_FE` flag)
- Direct code inspection: `app/api/server.py` (module globals `recommender`, `placement_model` set in `@app.on_event("startup")`)
- Direct code inspection: `.planning/codebase/CONCERNS.md` (18-concern audit with specific file/line references)
- Python multiprocessing documentation (spawn vs fork start method behavior — training data confirmed against Python 3.11+ defaults on Windows using spawn)
- Known Python pattern: `except ImportError` vs `except (ImportError, OSError)` for compiled extensions — confirmed in CPython issue tracker behavior for mismatched `.pyd` files on Windows

---
*Pitfalls research for: Auto-Battler Coach Lab codebase refactoring (18-concern cleanup)*
*Researched: 2026-02-27*
