# Phase 8: Global State Elimination - Context

**Gathered:** 2026-02-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Refactor `cloud_runner.py` module-level globals into a class-based `BatchRunner` with instance-scoped state. Fix DataLoader worker pool to use explicit `initargs`. Verify Windows `spawn` multiprocessing semantics with real integration tests. File splitting is out of scope (Phase 10).

</domain>

<decisions>
## Implementation Decisions

### BatchRunner API surface
- Single `run()` entry point — construct with config, call `run(games)`, get results
- Configuration via a frozen `BatchRunnerConfig` dataclass (num_workers, engine, batch_size, rayon settings, etc.)
- Single-use: construct per batch, run once, discard. No pool reuse across calls
- Returns raw results — caller handles Parquet writing (keeps BatchRunner focused on orchestration)
- `--engine rust_full` auto-profile settings (rayon_batch_size, native_parquet_direct, rayon_threads) become fields on BatchRunnerConfig, applied internally based on engine type

### Worker state passing
- Pool initializer + initargs pattern: `Pool(initializer=init_worker, initargs=(sim,))`
- Worker-local global for storing simulator in worker process (`_worker_sim` module-level in worker process, set by initializer)
- Same initargs pattern applied to DataLoader workers — one consistent pattern across the codebase
- Explicit `mp.get_context('spawn')` to create Pool — documents intent, doesn't affect global state, correct on all platforms

### Migration & backward compatibility
- Update all callers in-place: gate scripts, CLI entry points, cloud_runner CLI. No deprecated shims or thin wrappers
- BatchRunner stays in `cloud_runner.py` — same file, same import paths. Phase 10 handles the file split later
- `__main__` block rewritten this phase: construct BatchRunnerConfig from argparse, call `BatchRunner(config).run()`
- No backward compatibility layer — clean break from module globals

### Multiprocessing test scope
- Real `multiprocessing.Pool` with 2-4 workers (not mocked)
- Workers run 1-2 actual tiny simulation games via initargs-passed simulator — proves full spawn + serialize + run path
- Explicit isolation test: two BatchRunner instances with different configs, assert results are independent (no shared state)
- Dedicated DataLoader integration test: create DataLoader with workers, load a batch, verify results through initargs-passed resources

### Claude's Discretion
- Exact BatchRunnerConfig field names and defaults
- Worker function signature details
- argparse-to-config mapping implementation
- Test fixture design for tiny simulations

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 08-global-state-elimination*
*Context gathered: 2026-02-27*
