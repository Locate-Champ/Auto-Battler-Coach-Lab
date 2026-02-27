---
phase: 03-dependency-validation-and-resource-management
plan: 02
subsystem: simulator
tags: [rust, pyo3, logging, error-handling, diagnostics]

# Dependency graph
requires:
  - phase: 02-observable-fallbacks
    provides: Logging patterns (_log convention) established in Phase 2
provides:
  - Actionable FileNotFoundError for missing combat_data.json with git restore command
  - Rust extension pre-flight check separating ImportError from OSError with rebuild hints
  - engine_version() pyfunction in Rust module returning CARGO_PKG_VERSION
  - Backend selection logging at INFO level
affects: [simulator-core, cloud-runner, rust-engine]

# Tech tracking
tech-stack:
  added: []
  patterns: [separated-exception-handling, actionable-error-messages, version-reporting]

key-files:
  created: []
  modified:
    - simulator/core/combat_engine.py
    - simulator/core/engine_wrapper.py
    - simulator/core/rust_engine/src/lib.rs

key-decisions:
  - "File existence check placed inside _load_combat_data() not at module level -- avoids breaking test imports while still failing before game logic"
  - "ImportError and OSError caught separately with distinct diagnostic messages per user decision"
  - "engine_version() lookup wrapped in try/except so pre-flight works even without Rust rebuild"

patterns-established:
  - "Actionable error messages: include file path, cause, and exact fix command (git checkout, maturin develop)"
  - "Separated exception handling: ImportError (not installed) vs OSError (arch mismatch) with platform details"

requirements-completed: [DEPV-02, DEPV-03]

# Metrics
duration: 2min
completed: 2026-02-27
---

# Phase 03 Plan 02: Dependency Validation Summary

**Actionable FileNotFoundError for combat_data.json and Rust extension pre-flight check with architecture validation, version reporting, and rebuild instructions**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-27T15:16:43Z
- **Completed:** 2026-02-27T15:18:48Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- combat_data.json missing now raises FileNotFoundError with exact path and `git checkout` restore command
- Rust engine import separates ImportError (not installed) from OSError (architecture mismatch) with actionable rebuild hints
- Rust module exposes engine_version() returning Cargo.toml version string
- Backend selection logged at INFO level, Rust version logged at DEBUG level

## Task Commits

Each task was committed atomically:

1. **Task 1: Actionable FileNotFoundError for combat_data.json** - `eb2e70e` (feat)
2. **Task 2: Rust extension pre-flight check with version and logging** - `089fa97` (feat)

## Files Created/Modified
- `simulator/core/combat_engine.py` - Added file existence check with actionable error in _load_combat_data()
- `simulator/core/engine_wrapper.py` - Rewrote _try_rust_engine() with separated exception handling, version logging, and backend reporting
- `simulator/core/rust_engine/src/lib.rs` - Added engine_version() pyfunction returning CARGO_PKG_VERSION

## Decisions Made
- File existence check placed inside `_load_combat_data()` (not module-level) to avoid breaking test imports while still failing before game logic runs
- ImportError and OSError caught separately with distinct diagnostic messages and platform details
- engine_version() lookup wrapped in try/except so pre-flight works even without Rust rebuild
- Bare `except Exception` kept only for RustCombatEngine() construction (intentional -- Rust side could raise any PyErr)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Dependency validation diagnostics complete for combat_data.json and Rust extension
- All 119 tests pass with no regressions
- Ready for next plan in phase 03

## Self-Check: PASSED

All files verified present, all commits verified in git log.

---
*Phase: 03-dependency-validation-and-resource-management*
*Completed: 2026-02-27*
