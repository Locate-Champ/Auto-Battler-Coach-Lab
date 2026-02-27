---
phase: 01-models-exception-hardening
plan: 01
subsystem: models
tags: [exception-handling, ruff, BLE001, logging, pyarrow, cython]

# Dependency graph
requires: []
provides:
  - "Custom exception hierarchy (ModelsPipelineError > DataLoadError / FeatureEngineeringError / TrainingError)"
  - "Zero BLE001 violations in models/"
  - "All extension imports catch (ImportError, OSError)"
  - "Module-level loggers in feature_engineering.py and train_xgboost.py"
affects: [02-models-global-state, 03-startup-validation, 04-schema-validation]

# Tech tracking
tech-stack:
  added: []
  patterns: [narrowed-exception-handlers, extension-import-safety-pattern]

key-files:
  created: [models/exceptions.py]
  modified: [models/data_loader.py, models/dataset.py, models/feature_engineering.py, models/train_xgboost.py, models/train_transformer.py, models/fe_fast/__init__.py]

key-decisions:
  - "Placed _log after all imports to avoid E402 violations"
  - "Used (ImportError, ModuleNotFoundError) for simulator.data import since ModuleNotFoundError is a subclass but makes intent explicit"

patterns-established:
  - "Exception narrowing: every except clause in models/ names the specific types the try block can raise"
  - "Extension import pattern: Cython/Rust extension imports use (ImportError, OSError) to handle architecture mismatches"
  - "No silent pass: every except handler logs, re-raises, or has a functional fallback"

requirements-completed: [EXCP-01, EXCP-02]

# Metrics
duration: 5min
completed: 2026-02-27
---

# Phase 1 Plan 1: Models Exception Hardening Summary

**Narrowed 5 broad exception handlers in models/ to specific types, created ModelsPipelineError hierarchy, and widened 2 extension import handlers to catch OSError**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-27T07:42:49Z
- **Completed:** 2026-02-27T07:48:00Z
- **Tasks:** 2
- **Files modified:** 7 (1 created, 6 modified)

## Accomplishments
- Created models/exceptions.py with 4-class hierarchy: ModelsPipelineError > DataLoadError / FeatureEngineeringError / TrainingError
- Narrowed all 5 BLE001 violations to specific exception types with zero remaining violations
- Widened 2 Cython/Rust extension import handlers from ImportError to (ImportError, OSError) for architecture-mismatch safety
- Added module-level loggers to feature_engineering.py and train_xgboost.py, eliminating all silent pass handlers
- All 119 tests pass with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Create exceptions module and narrow all 5 BLE001 violations** - `c754763` (feat)
2. **Task 2: Widen extension import handlers and run full verification** - `80c082f` (feat)

## Files Created/Modified
- `models/exceptions.py` - Custom exception hierarchy for models pipeline (NEW)
- `models/data_loader.py` - Narrowed pyarrow import to (ImportError, OSError), fixed _log placement
- `models/dataset.py` - Narrowed pyarrow import to (ImportError, OSError)
- `models/feature_engineering.py` - Narrowed simulator data import to (ImportError, ModuleNotFoundError), widened fe_fast import to (ImportError, OSError), added logger
- `models/train_xgboost.py` - Narrowed torch import to ImportError with info log, added logger
- `models/train_transformer.py` - Narrowed torch.compile handler to RuntimeError
- `models/fe_fast/__init__.py` - Widened Cython extension import to (ImportError, OSError)

## Decisions Made
- Placed `_log = logging.getLogger(__name__)` after all module-level imports (not between stdlib and third-party) to avoid E402 import-order violations from ruff
- Used `(ImportError, ModuleNotFoundError)` for `simulator.data.set16_items` import since it is a cross-package import where ModuleNotFoundError makes the intent explicit

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed _log placement to avoid E402 import-order violations**
- **Found during:** Task 1 (commit attempt)
- **Issue:** Plan instructed placing `_log = logging.getLogger(__name__)` between stdlib imports and numpy import, but this triggered ruff E402 (module-level import not at top of file) for all subsequent imports
- **Fix:** Moved `_log` assignment to after all module-level imports in both data_loader.py and feature_engineering.py
- **Files modified:** models/data_loader.py, models/feature_engineering.py
- **Verification:** `ruff check models/` passes with zero errors
- **Committed in:** c754763 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Import placement fix was necessary for ruff compliance. No scope creep.

## Issues Encountered
- Pre-existing ruff error (F401 unused import) in untracked file `models/preprocess_tensors.py` and format issues in `models/evaluate.py` -- both out of scope for this plan as they are not caused by our changes

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Exception hierarchy is importable and ready for downstream phases to use
- All models/ files pass BLE001 checks -- future phases can maintain this standard
- Module loggers established in feature_engineering.py and train_xgboost.py for downstream logging needs

---
*Phase: 01-models-exception-hardening*
*Completed: 2026-02-27*
