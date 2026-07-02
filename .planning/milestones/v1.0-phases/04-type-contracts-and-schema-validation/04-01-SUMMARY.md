---
phase: 04-type-contracts-and-schema-validation
plan: 01
subsystem: coach
tags: [abc, abstractmethod, type-contracts, evaluator, bool-return]

# Dependency graph
requires:
  - phase: 03-dependency-validation-and-resource-management
    provides: "Hard pyarrow import, DataLoader context manager, Rust pre-flight check"
provides:
  - "BoardEvaluator ABC with @abstractmethod enforcement on score()"
  - "RuntimeEvaluator.check_compatibility() returning bool (True/False)"
  - "Contract test suite for evaluator module (8 tests)"
affects: [04-02, 07-sklearn-evaluator-wiring]

# Tech tracking
tech-stack:
  added: []
  patterns: [ABC-abstractmethod-for-base-contracts, bool-return-for-compatibility-checks, debug-logging-on-false-compatibility]

key-files:
  created:
    - tests/test_coach_evaluator.py
  modified:
    - coach/scoring/evaluator.py

key-decisions:
  - "check_compatibility() returns False for None/wrong-type instead of raising -- invalid input is 'not compatible', not an exception"
  - "Added _log.debug() when check_compatibility() returns False -- follows logging patterns from Phases 1-3"

patterns-established:
  - "ABC + @abstractmethod for base class contracts: enforces at instantiation time, not call time"
  - "Bool return for compatibility checks: callers branch on True/False, no exception handling needed"

requirements-completed: [TYPE-01, TYPE-02]

# Metrics
duration: 2min
completed: 2026-02-27
---

# Phase 4 Plan 1: Evaluator Type Contracts Summary

**BoardEvaluator converted to ABC with @abstractmethod on score(), check_compatibility() returns real bool with debug logging on False paths**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-27T16:18:56Z
- **Completed:** 2026-02-27T16:21:09Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- BoardEvaluator is now an ABC -- direct instantiation raises TypeError at class creation time, not at score() call time
- check_compatibility() returns True for valid BoardEvaluator instances, False for None or wrong-type, with debug logging on the False path
- 8 contract tests covering ABC enforcement, subclass instantiation, and bool return type verification

## Task Commits

Each task was committed atomically:

1. **Task 1: Convert BoardEvaluator to ABC and fix check_compatibility() return type** - `0adc8dd` (feat)
2. **Task 2: Add contract tests for evaluator module** - `b6b5c2d` (test)

## Files Created/Modified
- `coach/scoring/evaluator.py` - BoardEvaluator ABC conversion, check_compatibility() bool return, logging imports
- `tests/test_coach_evaluator.py` - 8 contract tests for ABC enforcement and check_compatibility() behavior

## Decisions Made
- check_compatibility() returns False for None/wrong-type instead of raising exceptions -- "not compatible" is the honest answer for invalid input, per CONTEXT.md
- Added `_log.debug()` when check_compatibility() returns False, following the logging patterns established in Phases 1-3
- Kept `raise NotImplementedError` body in BoardEvaluator.score() -- standard ABC convention alongside @abstractmethod

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Ruff I001 import sorting violation on test file -- auto-fixed with `ruff check --fix` (blank line between `from __future__` and `import pytest` needed removal)
- Pre-existing test failure in `test_data_loader.py::test_task_loaders_return_feature_matrices` -- caused by `_validate_columns` in feature_engineering.py (SCHM-01/SCHM-02 domain from Plan 04-02), not related to this plan's changes

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Evaluator type contracts are honest and tested, ready for Phase 4 Plan 02 (schema validation in transform_batch)
- Pre-existing test failure in test_data_loader.py needs resolution in Plan 04-02 (schema validation work)

## Self-Check: PASSED

- [x] coach/scoring/evaluator.py exists
- [x] tests/test_coach_evaluator.py exists
- [x] 04-01-SUMMARY.md exists
- [x] Commit 0adc8dd found
- [x] Commit b6b5c2d found

---
*Phase: 04-type-contracts-and-schema-validation*
*Completed: 2026-02-27*
