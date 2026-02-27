---
phase: 02-observable-fallbacks
plan: 01
subsystem: models
tags: [logging, fallback, cython, xgboost, pickle]

# Dependency graph
requires:
  - phase: 01-models-exception-hardening
    provides: "Exception-safe try/except blocks in fe_fast, data_loader, train_xgboost"
provides:
  - "WARNING-level logging on all silent performance-degradation fallback paths in models/"
  - "All print() calls in data_loader.py and train_xgboost.py converted to _log calls"
affects: [03-models-import-safety, 08-cloud-runner-refactor]

# Tech tracking
tech-stack:
  added: []
  patterns: [logging.getLogger(__name__) per module, lazy %s formatting in log calls]

key-files:
  created: []
  modified:
    - models/fe_fast/__init__.py
    - models/data_loader.py
    - models/train_xgboost.py

key-decisions:
  - "Replace warnings.warn with logging.warning in fe_fast to unify logging mechanism"
  - "No duplicate Cython fallback warning in feature_engineering.py -- fe_fast/__init__.py already covers it"
  - "logging.basicConfig added only to train_xgboost.py __main__ block, not library modules"

patterns-established:
  - "Fallback WARNING pattern: _log.warning with performance estimate and remediation hint"
  - "Print-to-logger conversion: _log.info for informational, _log.warning for disguised warnings"

requirements-completed: [OBSV-01, OBSV-02]

# Metrics
duration: 4min
completed: 2026-02-27
---

# Phase 2 Plan 1: Observable Fallbacks Summary

**WARNING-level logging for Cython/pickle/GPU fallback paths plus 23 print-to-logger conversions across data_loader.py and train_xgboost.py**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-27T13:32:46Z
- **Completed:** 2026-02-27T13:37:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Cython fe_fast fallback emits WARNING with ~2x performance estimate and build instructions (replaces silent warnings.warn)
- DataLoader pickle fallback message now explicitly says "~30x slower" for visibility
- XGBoost GPU->CPU fallback in both _train_with_fallback and _train_booster_with_fallback now warns before falling back
- All 23 print() calls in data_loader.py (8) and train_xgboost.py (15) converted to _log.info/_log.warning with lazy %s formatting
- No duplicate Cython warnings (fe_fast/__init__.py only, feature_engineering.py left silent)

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire fallback WARNING logging for Cython, pickle, and XGBoost GPU paths** - `d42dbdc` (feat)
2. **Task 2: Convert print() to logger calls in data_loader.py and train_xgboost.py** - `b20fa75` (feat)

## Files Created/Modified
- `models/fe_fast/__init__.py` - Replace warnings.warn with _log.warning for Cython fallback (~2x estimate)
- `models/data_loader.py` - Enhanced pickle fallback message with ~30x estimate; 8 print() -> _log.info()
- `models/train_xgboost.py` - GPU fallback _log.warning; 15 print() -> _log.info/_log.warning; basicConfig in __main__

## Decisions Made
- Replaced `warnings.warn` with `logging.warning` in fe_fast to unify under the logging framework -- warnings module is inappropriate for library fallback notifications
- Deliberately left feature_engineering.py except block silent (no warning) to avoid duplicate Cython fallback messages since importing fe_fast triggers its __init__.py warning
- Added `logging.basicConfig()` only in train_xgboost.py's `__main__` guard, never in library modules

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- matplotlib not installed in local environment, so `import models.train_xgboost` fails locally. This is pre-existing and unrelated to the changes. AST parsing confirmed syntax correctness of all modifications.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All fallback paths in models/ now emit WARNING-level log messages with performance estimates
- Ready for 02-02 (if it exists) or Phase 3 models import safety work
- No blockers

---
*Phase: 02-observable-fallbacks*
*Completed: 2026-02-27*
