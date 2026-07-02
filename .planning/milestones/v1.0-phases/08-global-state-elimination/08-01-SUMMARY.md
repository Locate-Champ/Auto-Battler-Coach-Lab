---
phase: 08-global-state-elimination
plan: 01
subsystem: simulator
tags: [dataclass, multiprocessing, refactoring, cloud-runner]

# Dependency graph
requires:
  - phase: 06-configuration-extraction-and-ruff-gates
    provides: ruff linting and formatting gates
provides:
  - BatchRunnerConfig frozen dataclass with all 31 run_batch() parameters
  - BatchRunner class with instance-scoped state and three execution paths
  - Worker-local globals renamed (_worker_sim, _worker_parquet_validated)
  - _ensure_rust_parquet_method_support accepts explicit validated_set parameter
affects: [08-02, 10-cloud-runner-split]

# Tech tracking
tech-stack:
  added: []
  patterns: [frozen-dataclass-config, instance-scoped-state, spawn-context-pool]

key-files:
  created: []
  modified:
    - simulator/cloud_runner.py
    - tests/test_benchmark_parity_helpers.py

key-decisions:
  - "Worker-local globals (_worker_sim, _worker_parquet_validated) preserved as process-local state -- standard multiprocessing pattern"
  - "Parallel path uses mp.get_context('spawn').Pool() for Windows compatibility"
  - "Clean break: run_batch() removed entirely, no backward compatibility shim"

patterns-established:
  - "Frozen dataclass config pattern: BatchRunnerConfig with dataclasses.replace() for test overrides"
  - "Instance-scoped state: BatchRunner stores _rust_simulator and _parquet_api_validated as instance attributes"

requirements-completed: [GLBL-01]

# Metrics
duration: 9min
completed: 2026-02-27
---

# Phase 08 Plan 01: Global State Elimination Summary

**BatchRunnerConfig frozen dataclass + BatchRunner class replacing run_batch() and module-level mutable globals**

## Performance

- **Duration:** 9 min
- **Started:** 2026-02-28T03:57:22Z
- **Completed:** 2026-02-28T04:06:17Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Replaced module-level mutable globals (_RUST_FULL_SIMULATOR, _RUST_PARQUET_API_VALIDATED) with instance-scoped state in BatchRunner class
- Created BatchRunnerConfig frozen dataclass with all 31 run_batch() parameters for immutable configuration
- Renamed worker-process globals to _worker_sim and _worker_parquet_validated for clarity
- Updated _ensure_rust_parquet_method_support to accept explicit validated_set parameter instead of mutating module global
- Rewritten main() to construct BatchRunnerConfig and call BatchRunner(config).run()
- Parallel path now uses mp.get_context("spawn").Pool() for cross-platform safety

## Task Commits

Each task was committed atomically:

1. **Task 1: Create BatchRunnerConfig dataclass and refactor _ensure_rust_parquet_method_support** - `d1832e7` (feat)
2. **Task 2: Create BatchRunner class, rename worker globals, rewrite main(), update tests** - `0da8e39` (feat)

## Files Created/Modified
- `simulator/cloud_runner.py` - Added BatchRunnerConfig frozen dataclass, BatchRunner class with run() method, renamed worker globals, removed run_batch(), updated main()
- `tests/test_benchmark_parity_helpers.py` - Updated 3 parquet guard tests to pass local validated_set instead of monkeypatching removed module global

## Decisions Made
- Worker-local globals (_worker_sim, _worker_parquet_validated) preserved as process-local state -- standard multiprocessing pattern, not shared mutable state
- Parallel path uses mp.get_context("spawn").Pool() for Windows compatibility (fork not available on Windows)
- Clean break: run_batch() removed entirely with no backward compatibility shim, per CONTEXT.md guidance

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Pre-existing test failure in tests/test_api_server.py::test_startup_failure_exits (Python 3.14 compatibility issue with concurrent.futures and SystemExit in mocked contexts) -- unrelated to changes, not in scope

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- BatchRunner class ready for Phase 08 Plan 02 (main() decomposition)
- Clean API surface for Phase 10 (cloud_runner split)
- All 166 tests pass (2 skipped for optional deps), excluding pre-existing api_server failure

## Self-Check: PASSED

- FOUND: simulator/cloud_runner.py
- FOUND: tests/test_benchmark_parity_helpers.py
- FOUND: .planning/phases/08-global-state-elimination/08-01-SUMMARY.md
- FOUND: d1832e7 (Task 1 commit)
- FOUND: 0da8e39 (Task 2 commit)

---
*Phase: 08-global-state-elimination*
*Completed: 2026-02-27*
