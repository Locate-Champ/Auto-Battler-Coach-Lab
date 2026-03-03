# Phase 8: Global State Elimination - Research

**Researched:** 2026-02-27
**Domain:** Python multiprocessing, module-level global elimination, class-based refactoring
**Confidence:** HIGH

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions

**BatchRunner API surface:**
- Single `run()` entry point -- construct with config, call `run(games)`, get results
- Configuration via a frozen `BatchRunnerConfig` dataclass (num_workers, engine, batch_size, rayon settings, etc.)
- Single-use: construct per batch, run once, discard. No pool reuse across calls
- Returns raw results -- caller handles Parquet writing (keeps BatchRunner focused on orchestration)
- `--engine rust_full` auto-profile settings (rayon_batch_size, native_parquet_direct, rayon_threads) become fields on BatchRunnerConfig, applied internally based on engine type

**Worker state passing:**
- Pool initializer + initargs pattern: `Pool(initializer=init_worker, initargs=(sim,))`
- Worker-local global for storing simulator in worker process (`_worker_sim` module-level in worker process, set by initializer)
- Same initargs pattern applied to DataLoader workers -- one consistent pattern across the codebase
- Explicit `mp.get_context('spawn')` to create Pool -- documents intent, doesn't affect global state, correct on all platforms

**Migration & backward compatibility:**
- Update all callers in-place: gate scripts, CLI entry points, cloud_runner CLI. No deprecated shims or thin wrappers
- BatchRunner stays in `cloud_runner.py` -- same file, same import paths. Phase 10 handles the file split later
- `__main__` block rewritten this phase: construct BatchRunnerConfig from argparse, call `BatchRunner(config).run()`
- No backward compatibility layer -- clean break from module globals

**Multiprocessing test scope:**
- Real `multiprocessing.Pool` with 2-4 workers (not mocked)
- Workers run 1-2 actual tiny simulation games via initargs-passed simulator -- proves full spawn + serialize + run path
- Explicit isolation test: two BatchRunner instances with different configs, assert results are independent (no shared state)
- Dedicated DataLoader integration test: create DataLoader with workers, load a batch, verify results through initargs-passed resources

### Claude's Discretion
- Exact BatchRunnerConfig field names and defaults
- Worker function signature details
- argparse-to-config mapping implementation
- Test fixture design for tiny simulations

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| GLBL-01 | cloud_runner.py module-level globals refactored to class-based BatchRunner with instance state | Architecture Pattern 1 (BatchRunner class), Pattern 2 (Worker Init), Code Examples for all three execution paths |
| GLBL-02 | DataLoader worker state uses pool context manager with explicit initargs (not module-level global mutation) | Architecture Pattern 3 (DataLoader spawn context), Code Example for mp.get_context('spawn').Pool |

</phase_requirements>

## Summary

This phase eliminates two module-level mutable globals (`_RUST_FULL_SIMULATOR` and `_RUST_PARQUET_API_VALIDATED`) from `cloud_runner.py` by refactoring the 500-line `run_batch()` function into a `BatchRunner` class with a `BatchRunnerConfig` frozen dataclass. The DataLoader in `models/data_loader.py` already uses the correct `initializer`/`initargs` pattern but needs `mp.get_context('spawn').Pool(...)` for cross-platform consistency.

The primary complexity lies in three distinct execution paths inside `run_batch()`: (1) Rust rayon batch mode (in-process, no Pool, uses `_RUST_FULL_SIMULATOR` directly), (2) sequential mode (no Pool, calls `run_game()` directly after `_worker_init()`), and (3) parallel mode (`multiprocessing.Pool` with `_worker_init` initializer). Each path handles the simulator global differently. The BatchRunner class must encapsulate all three paths while keeping the worker-side global pattern (worker processes set a module-level `_worker_sim` via initializer) -- this is the standard Python multiprocessing pattern and is correct.

The critical finding is that `RustGameSimulator` (PyO3 extension) is almost certainly NOT picklable by default. PyO3 objects require explicit `__getstate__`/`__setstate__` implementation to support pickle. The existing code already handles this correctly: `_worker_init("rust_full")` constructs the simulator from `combat_data_path` in the worker process rather than trying to pickle and send it. The BatchRunner must continue this pattern -- pass construction args (combat_data_path string) via initargs, not the simulator object itself.

**Primary recommendation:** Create `BatchRunnerConfig` as a frozen dataclass capturing all 30+ `run_batch()` parameters, then `BatchRunner.__init__(config)` stores it. The `run()` method replaces `run_batch()` body. Worker-side globals (`_worker_sim`) remain module-level in worker processes (set by initializer) -- this is correct and standard. Main-process globals (`_RUST_FULL_SIMULATOR`, `_RUST_PARQUET_API_VALIDATED`) become instance attributes on `BatchRunner`.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `multiprocessing` (stdlib) | Python 3.10+ | Process pools with spawn semantics | Standard library, no external deps needed |
| `dataclasses` (stdlib) | Python 3.10+ | Frozen config dataclass | Project convention (see coach/weights.py, models/feature_config.py) |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pickle` (stdlib) | Python 3.10+ | Serialization for initargs | Required by spawn-mode Pool for function args |
| `typing` (stdlib) | Python 3.10+ | Type hints for BatchRunnerConfig | Project convention for all dataclasses |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `multiprocessing.Pool` | `concurrent.futures.ProcessPoolExecutor` | ProcessPoolExecutor lacks `imap_unordered` which is used for streaming results; Pool is already in use and proven |
| Frozen `@dataclass` | `NamedTuple` | dataclass is project convention, supports `dataclasses.replace()` for test overrides |

**Installation:**
No new dependencies. Everything is stdlib.

## Architecture Patterns

### Recommended Refactoring Structure
```
simulator/
  cloud_runner.py
    BatchRunnerConfig       # NEW: frozen dataclass, replaces 30+ run_batch params
    BatchRunner             # NEW: class, replaces run_batch() + main-process globals
    StreamingWriter         # UNCHANGED: stays in cloud_runner.py
    run_game()              # MODIFIED: uses _worker_sim instead of _RUST_FULL_SIMULATOR
    _worker_init()          # MODIFIED: sets _worker_sim (renamed from _RUST_FULL_SIMULATOR)
    _worker_sim             # RENAMED: from _RUST_FULL_SIMULATOR, only set in workers
    _worker_parquet_validated  # RENAMED: from _RUST_PARQUET_API_VALIDATED, only in workers
    main()                  # REWRITTEN: argparse -> BatchRunnerConfig -> BatchRunner
models/
  data_loader.py
    DataLoader._ensure_pool()  # MODIFIED: mp.get_context('spawn').Pool(...)
```

### Pattern 1: BatchRunner Class with Config Dataclass
**What:** Replace module-level `run_batch()` function + globals with a class that holds all state as instance attributes.
**When to use:** When a function has 30+ parameters and relies on module-level mutable globals.

```python
# Source: project convention (coach/weights.py, models/feature_config.py)
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

@dataclass(frozen=True)
class BatchRunnerConfig:
    """Immutable configuration for a batch simulation run."""
    num_games: int
    num_workers: int
    output_dir: str
    seed_start: int = 0
    agent_mix: Optional[Dict[str, int]] = None
    chunk_size: int = 100
    engine: str = "python"
    # ... all other run_batch params become fields ...
    # Rust-specific fields:
    rust_full_rayon_batch_size: Optional[int] = None
    rust_full_rayon_threads: Optional[int] = None
    rust_full_native_parquet: bool = False
    rust_full_native_parquet_direct: bool = False
    # ... etc

class BatchRunner:
    """Runs batch simulations with instance-scoped state."""

    def __init__(self, config: BatchRunnerConfig) -> None:
        self._config = config
        # Main-process instance state (replaces module globals):
        self._rust_simulator: Any = None
        self._parquet_api_validated: set[str] = set()

    def run(self) -> Dict[str, Any]:
        """Execute the batch. Returns summary dict."""
        cfg = self._config
        # Three paths: rayon batch, sequential, parallel
        if self._use_rayon_batches:
            return self._run_rayon_batch()
        elif cfg.num_workers <= 1:
            return self._run_sequential()
        else:
            return self._run_parallel()
```

### Pattern 2: Worker Initializer with initargs (NOT Pickling the Simulator)
**What:** Pass construction arguments to worker processes via Pool initializer. Workers construct the simulator locally. The worker-local global is set once per worker process.
**When to use:** When the object to share is not picklable (PyO3/Rust extensions) or is expensive to pickle.

```python
# Source: Python docs - multiprocessing Pool initializer pattern
# This is the CORRECT pattern. The simulator is built IN the worker,
# not pickled and sent from the parent.

# Module-level worker state (only set in worker processes by initializer)
_worker_sim: Any = None
_worker_parquet_validated: set[str] = set()

def _worker_init(engine: str, combat_data_path: str) -> None:
    """Worker process initializer - constructs simulator from args."""
    global _worker_sim, _worker_parquet_validated
    _worker_parquet_validated = set()
    if engine == "rust_full":
        from tft_combat_engine import RustGameSimulator
        _worker_sim = RustGameSimulator(combat_data_path)
    elif engine == "rust":
        from tft_combat_engine import RustCombatEngine
        _worker_sim = RustCombatEngine(combat_data_path)
    else:
        from simulator.core.combat_engine import CombatEngine
        _worker_sim = CombatEngine()

# In BatchRunner._run_parallel():
def _run_parallel(self) -> Dict:
    cfg = self._config
    combat_data_path = str(Path(__file__).parent / "data" / "combat_data.json")
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(
        cfg.num_workers,
        initializer=_worker_init,
        initargs=(cfg.engine, combat_data_path),
    ) as pool:
        for result in pool.imap_unordered(run_game, tasks, chunksize=chunksize):
            self._process_result(result)
```

### Pattern 3: DataLoader spawn Context
**What:** Replace bare `multiprocessing.Pool(...)` with `multiprocessing.get_context('spawn').Pool(...)`.
**When to use:** For cross-platform consistency. Documents intent even on Windows where spawn is default.

```python
# In DataLoader._ensure_pool():
def _ensure_pool(self) -> multiprocessing.pool.Pool:
    if self._pool is None:
        workers = self._effective_workers()
        ctx = multiprocessing.get_context("spawn")
        try:
            fe_state = pickle.dumps(self.feature_engineer)
            self._pool = ctx.Pool(
                processes=workers,
                initializer=_init_fe_worker_pickled,
                initargs=(fe_state,),
            )
        except (pickle.PicklingError, TypeError) as exc:
            _log.warning("FeatureEngineer pickle failed (%s); falling back...", exc)
            self._pool = ctx.Pool(
                processes=workers,
                initializer=_init_fe_worker,
                initargs=(self.feature_engineer.config, self.feature_engineer.repo_root),
            )
    return self._pool
```

### Pattern 4: Rayon Batch Path (In-Process, No Pool)
**What:** The Rust rayon batch path runs in the main process using Rust-internal threading. No `multiprocessing.Pool`. The simulator must be stored as a BatchRunner instance attribute instead of a module global.
**When to use:** When `rust_full_rayon_batch_size` is set.

```python
# In BatchRunner._run_rayon_batch():
def _run_rayon_batch(self) -> Dict:
    # Construct simulator on THIS instance (not a module global)
    self._ensure_rust_simulator()
    sim = self._rust_simulator
    # Use sim directly -- no Pool, no pickling needed
    batch_results = sim.run_games_batch(
        batch_game_ids, batch_seeds, agent_mix,
        include_training_rows, batch_output_mode, rayon_threads,
    )

def _ensure_rust_simulator(self) -> None:
    if self._rust_simulator is None:
        from tft_combat_engine import RustGameSimulator
        combat_data_path = str(Path(__file__).parent / "data" / "combat_data.json")
        self._rust_simulator = RustGameSimulator(combat_data_path)
        self._parquet_api_validated.clear()
```

### Anti-Patterns to Avoid
- **Passing RustGameSimulator via initargs:** The Rust extension object is NOT picklable. Pass the `combat_data_path` string and construct in the worker. This is already the existing pattern.
- **Using `multiprocessing.set_start_method('spawn')` globally:** This is a process-wide setting and can only be called once. Use `mp.get_context('spawn')` instead -- it is local, composable, and does not affect other code.
- **Sharing _worker_sim between main process and workers:** The main process's `_worker_sim` is separate from worker copies. Each worker gets its own copy via the initializer. The rayon path uses `self._rust_simulator` (instance attribute), not `_worker_sim`.
- **Trying to pickle the Pool or BatchRunner:** BatchRunner is main-process only. Never pass it to workers. Workers receive only picklable task tuples.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Pool context management | Custom pool lifecycle | `with ctx.Pool(...) as pool:` | Already used in parallel path (line 1448); handles cleanup on exceptions |
| Spawn-safe pickling | Custom serialization for stdlib types | `pickle` + standard initargs | Python's pickle handles all stdlib types; only Rust extensions need special handling |
| Cross-platform spawn | Platform detection logic | `mp.get_context('spawn')` | Documents intent, works identically on all platforms, no branching needed |
| Config validation | Manual param checking in BatchRunner | `__post_init__` on frozen dataclass | Validation runs once at construction; frozen prevents mutation after |
| Worker-local state | Thread-local storage or custom IPC | Module-level global + Pool initializer | This IS the standard Python multiprocessing pattern per official docs |

**Key insight:** The "eliminate globals" goal means eliminating MAIN-PROCESS mutable module globals. Worker-process globals set via Pool initializer are the standard, correct pattern -- they are not shared state, they are process-local state initialized once per worker.

## Common Pitfalls

### Pitfall 1: Confusing Main-Process Globals with Worker-Process Globals
**What goes wrong:** Removing ALL module-level globals, including the worker-side `_worker_sim`, breaking the Pool initializer pattern.
**Why it happens:** "Eliminate globals" sounds absolute, but worker-process globals set by initializer are process-local, not shared mutable state.
**How to avoid:** Only eliminate globals that are mutated in the main process (`_RUST_FULL_SIMULATOR`, `_RUST_PARQUET_API_VALIDATED`). Worker-side globals (`_worker_sim`) set by initializer are correct.
**Warning signs:** `run_game()` function can't access its simulator reference after refactoring.

### Pitfall 2: Trying to Pickle RustGameSimulator
**What goes wrong:** Passing the RustGameSimulator object as an initarg or in the task tuple causes `pickle.PicklingError` at runtime.
**Why it happens:** PyO3 extension objects don't implement `__reduce__`/`__getstate__` by default. The existing code correctly constructs the simulator inside `_worker_init()` from a path string.
**How to avoid:** Always pass the `combat_data_path` string (picklable) and construct the simulator in the worker. For rayon batch path (no Pool), use `self._rust_simulator` instance attribute.
**Warning signs:** Tests that skip the Rust engine would miss this. Must test with actual spawn Pool.

### Pitfall 3: BatchRunner Returns Raw Results vs. Rayon Direct-to-Disk
**What goes wrong:** The rayon `run_games_batch_parquet_to_file` path writes Parquet chunks directly to disk -- it doesn't "return raw results" in the traditional sense.
**Why it happens:** The user decision says "Returns raw results -- caller handles Parquet writing" but the direct-to-disk path has Rust writing files.
**How to avoid:** BatchRunner must still orchestrate the StreamingWriter internally for the rayon direct-to-disk path, calling `writer.record_external_parquet_chunk()`. The "returns raw results" applies to the non-rayon paths. The caller receives a summary dict.
**Warning signs:** Missing chunk files when using rayon batch mode with native_parquet_direct.

### Pitfall 4: run_game() Task Tuple Fragility
**What goes wrong:** The `run_game()` function unpacks a 12-element tuple positionally. Adding or reordering fields breaks silently.
**Why it happens:** The task tuple is built in `run_batch()` and unpacked in `run_game()` with no named structure.
**How to avoid:** Keep the tuple structure stable in this phase. Phase 10 (file split) can migrate to a named tuple or dataclass. Verify the unpack matches the pack for all 12 fields.
**Warning signs:** Wrong values for engine or parquet flags in worker processes.

### Pitfall 5: Forgetting to Handle StreamingWriter in BatchRunner
**What goes wrong:** The user decision says "Returns raw results -- caller handles Parquet writing" but StreamingWriter is deeply integrated with the batch loop (checkpointing, S3 upload, progress tracking).
**Why it happens:** StreamingWriter is not just a "write Parquet" class -- it handles analytics accumulation, error tracking, checkpoints, and S3 streaming.
**How to avoid:** BatchRunner must create and manage the StreamingWriter internally. The "returns raw results" design means the summary dict is the output -- the writer is an internal implementation detail of run(). The caller doesn't need to touch StreamingWriter.
**Warning signs:** Lost checkpointing, missing S3 uploads, no error tracking.

### Pitfall 6: Windows __main__ Guard Already Present
**What goes wrong:** Forgetting the `if __name__ == "__main__":` guard when rewriting main().
**Why it happens:** Spawn start method reimports the module in child processes. Without the guard, child processes would re-execute main().
**How to avoid:** The existing guard at line 2047 must be preserved. This is already correct in the codebase.
**Warning signs:** Recursive process spawning on Windows, "RuntimeError: An attempt has been made to start a new process before the current process has finished its bootstrapping phase."

## Code Examples

### BatchRunnerConfig Frozen Dataclass
```python
# Pattern matches project convention: coach/weights.py, models/feature_config.py
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass(frozen=True)
class BatchRunnerConfig:
    """Immutable configuration for a batch simulation run.

    Use dataclasses.replace() for test overrides.
    """
    num_games: int
    num_workers: int
    output_dir: str
    seed_start: int = 0
    agent_mix: Optional[Dict[str, int]] = None
    chunk_size: int = 100
    resume: bool = False
    agent_profile: str = "random"
    checkpoint_every: Optional[int] = None
    progress_every: Optional[int] = 500
    max_errors: Optional[int] = None
    require_parquet: bool = False
    pool_chunksize: Optional[int] = None
    pool_chunksize_max: Optional[int] = None
    shard_index: Optional[int] = None
    num_shards: Optional[int] = None
    engine: str = "python"
    rust_full_include_training_rows: bool = True
    rust_full_native_jsonl: bool = False
    rust_full_native_parquet: bool = False
    rust_full_native_parquet_direct: bool = False
    rust_full_rayon_batch_size: Optional[int] = None
    rust_full_rayon_threads: Optional[int] = None
    parquet_compression: str = "uncompressed"
    parquet_use_dictionary: bool = False
    parquet_write_statistics: bool = False
    parquet_row_group_size: Optional[int] = None
    parquet_write_batch_size: Optional[int] = None
    s3_uri: Optional[str] = None
    instance_hourly_usd: float = 0.0
    instance_type: Optional[str] = None
```

### Main Process Rewrite (argparse -> BatchRunnerConfig -> BatchRunner)
```python
def main():
    parser = argparse.ArgumentParser(...)
    # ... all existing argparse definitions ...
    args = parser.parse_args()

    # ... existing validation and auto-profile logic ...

    config = BatchRunnerConfig(
        num_games=args.games,
        num_workers=num_workers,
        output_dir=output_dir,
        seed_start=args.seed_start,
        agent_mix=agent_mix,
        chunk_size=effective_chunk_size,
        # ... map all args to config fields ...
    )
    runner = BatchRunner(config)
    summary = runner.run()

    # ... existing summary printing ...
```

### Explicit Spawn Context Pool Creation
```python
# Source: https://docs.python.org/3/library/multiprocessing.html#contexts-and-start-methods
import multiprocessing as mp

ctx = mp.get_context("spawn")
with ctx.Pool(
    num_workers,
    initializer=_worker_init,
    initargs=(engine, combat_data_path),
) as pool:
    for result in pool.imap_unordered(run_game, tasks, chunksize=chunksize):
        process_result(result)
```

### Isolation Test Pattern
```python
def test_two_batch_runners_independent(tmp_path):
    """Two BatchRunner instances with different configs produce independent results."""
    config_a = BatchRunnerConfig(
        num_games=2, num_workers=1, output_dir=str(tmp_path / "a"),
        seed_start=0, engine="python",
    )
    config_b = BatchRunnerConfig(
        num_games=2, num_workers=1, output_dir=str(tmp_path / "b"),
        seed_start=100, engine="python",
    )
    summary_a = BatchRunner(config_a).run()
    summary_b = BatchRunner(config_b).run()
    # Different seeds -> different results
    assert summary_a["num_games"] == 2
    assert summary_b["num_games"] == 2
    # No shared state contamination
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `multiprocessing.set_start_method()` | `mp.get_context('spawn')` | Python 3.4+ | Context is local, composable, no global side effects |
| Fork as default on Linux | Forkserver as default (Python 3.14+) | Python 3.14 | Spawn/forkserver are now preferred everywhere; fork has known deadlock risks with threaded libraries |
| Global mutable state + functions | Frozen config + class instances | Standard pattern | Testable, composable, no import-time side effects |

**Deprecated/outdated:**
- `multiprocessing.set_start_method('spawn')`: Still works but is global/once-only. Use `get_context()` instead.
- `fork` start method on Linux: Changed from default in Python 3.14 to `forkserver`. This codebase's move to explicit `spawn` context is forward-compatible.

## Callers Audit

### run_batch() Callers (MUST be updated)
| Caller | Location | Call Type |
|--------|----------|-----------|
| `main()` resume path | cloud_runner.py:1930 | Direct call with all params |
| `main()` normal path | cloud_runner.py:1969 | Direct call with all params |

### run_batch() Non-Callers (reference only, no update needed)
| File | Usage |
|------|-------|
| `tests/test_cloud_runner_cost_telemetry.py` | Tests `_build_cost_telemetry()` and `StreamingWriter._compute_summary()` -- does NOT call `run_batch()` |
| `tests/test_benchmark_parity_helpers.py` | References `run_game` indirectly -- verify after refactoring |
| `scripts/verify.ps1` | Invokes `python -m simulator.cloud_runner` CLI -- no code change needed, just verify CLI still works |

### Module-Level Import Consumers
| File | Import |
|------|--------|
| `tests/test_cloud_runner_cost_telemetry.py` | `from simulator import cloud_runner` -- accesses `cloud_runner._build_cost_telemetry`, `cloud_runner.StreamingWriter` |

**Key finding:** `run_batch()` is only called from `main()` in two places (resume and normal path). No external scripts call `run_batch()` directly as a Python API. The gate scripts invoke `python -m simulator.cloud_runner` via CLI.

## Open Questions

1. **RustGameSimulator picklability -- confirmed or assumed?**
   - What we know: PyO3 objects are NOT picklable by default (confirmed by Rust forum, PyO3 docs). The existing code never pickles RustGameSimulator -- it always constructs in-worker via `_worker_init()`.
   - What's unclear: Whether the project's Rust extension has implemented `__getstate__`/`__setstate__`. Based on grep results, it has NOT (no such methods found in Python-side code).
   - Recommendation: HIGH confidence it is NOT picklable. Continue the existing pattern: pass `combat_data_path` string, construct in worker. No investigation needed -- the pattern is already correct.

2. **run_game() task tuple stability during refactoring**
   - What we know: The 12-element positional tuple is fragile but works. Changing it risks silent bugs.
   - What's unclear: Whether this phase should migrate to a named structure.
   - Recommendation: Keep the tuple stable in this phase. Phase 10 can migrate to NamedTuple during the file split. The risk of changing both the class structure AND the task format simultaneously is unnecessary.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (via pytest.ini) |
| Config file | `pytest.ini` (testpaths: tests, simulator) |
| Quick run command | `python -m pytest tests/test_cloud_runner_cost_telemetry.py tests/test_data_loader.py -x` |
| Full suite command | `python -m pytest` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GLBL-01a | BatchRunnerConfig frozen dataclass construction | unit | `pytest tests/test_batch_runner.py::test_config_frozen -x` | No -- Wave 0 |
| GLBL-01b | BatchRunner sequential mode (1 worker, python engine) | integration | `pytest tests/test_batch_runner.py::test_sequential_run -x` | No -- Wave 0 |
| GLBL-01c | BatchRunner parallel mode (2+ workers, spawn Pool) | integration | `pytest tests/test_batch_runner.py::test_parallel_spawn_pool -x` | No -- Wave 0 |
| GLBL-01d | Two BatchRunner instances produce independent results | integration | `pytest tests/test_batch_runner.py::test_two_runners_independent -x` | No -- Wave 0 |
| GLBL-01e | No module-level mutable globals remain in main process | unit | `pytest tests/test_batch_runner.py::test_no_main_process_globals -x` | No -- Wave 0 |
| GLBL-01f | CLI main() uses BatchRunner (not run_batch) | smoke | `pytest tests/test_batch_runner.py::test_cli_uses_batch_runner -x` | No -- Wave 0 |
| GLBL-02a | DataLoader uses mp.get_context('spawn') | unit | `pytest tests/test_data_loader.py::test_spawn_context_pool -x` | No -- Wave 0 |
| GLBL-02b | DataLoader worker init via initargs | integration | `pytest tests/test_data_loader.py::test_worker_init_via_initargs -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_batch_runner.py tests/test_data_loader.py tests/test_cloud_runner_cost_telemetry.py -x`
- **Per wave merge:** `python -m pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_batch_runner.py` -- covers GLBL-01a through GLBL-01f (new file)
- [ ] New tests in `tests/test_data_loader.py` -- covers GLBL-02a, GLBL-02b (append to existing file)

## Sources

### Primary (HIGH confidence)
- [Python multiprocessing docs](https://docs.python.org/3/library/multiprocessing.html) -- get_context, Pool initializer/initargs, spawn behavior on Windows, picklability requirements
- Source code analysis of `simulator/cloud_runner.py` (2048 lines) -- all three execution paths, module globals, callers audit
- Source code analysis of `models/data_loader.py` (1036 lines) -- existing initargs pattern, `_worker_fe` global, `_ensure_pool()`

### Secondary (MEDIUM confidence)
- [Rust forum: PyO3 pickle support](https://users.rust-lang.org/t/rust-extension-module-breaks-multiprocessing-no-pickle-support/112402) -- confirmed PyO3 objects need explicit pickle support, verified against codebase (no __getstate__/__setstate__ found on Rust types)
- [Python multiprocessing fork vs spawn](https://britishgeologicalsurvey.github.io/science/python-forking-vs-spawn/) -- spawn is required on Windows, recommended everywhere
- [Python multiprocessing Pool initializer patterns](https://superfastpython.com/multiprocessing-pool-initializer/) -- standard initializer + initargs pattern documentation

### Tertiary (LOW confidence)
- None -- all findings verified against primary sources or codebase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- stdlib only, no new dependencies, verified against Python docs
- Architecture: HIGH -- patterns directly observed in existing codebase + Python docs
- Pitfalls: HIGH -- all pitfalls derived from direct code analysis and verified PyO3 behavior
- Callers audit: HIGH -- comprehensive grep of all `run_batch`, `cloud_runner` imports across codebase

**Research date:** 2026-02-27
**Valid until:** 2026-03-27 (stable stdlib patterns, no fast-moving dependencies)
