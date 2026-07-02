---
phase: 04-type-contracts-and-schema-validation
plan: 02
subsystem: models
tags: [feature-engineering, schema-validation, arrow, parquet]

# Dependency graph
requires:
  - phase: 01-models-exception-hardening
    provides: exception hierarchy and error message patterns
  - phase: 03-dependency-validation-and-resource-management
    provides: pyarrow hard dependency, DataLoader context manager
provides:
  - REQUIRED_COLUMNS frozenset and _REQUIRED_COLUMN_GROUPS for schema validation
  - _validate_columns() method on TFTFeatureEngineer
  - Schema validation at entry to transform_batch() and transform_arrow_batch()
affects: [models, data-loader, training-pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns: [column-group-validation, dual-format-support]

key-files:
  created: []
  modified:
    - models/feature_engineering.py
    - tests/test_feature_engineering.py

key-decisions:
  - "REQUIRED_COLUMNS split into strict (5 columns) + _REQUIRED_COLUMN_GROUPS (3 groups with alternatives) to support both normalized and raw simulation data formats"
  - "Column groups use any-of semantics: streak OR win_streak, units OR board OR board_names, traits OR trait_names"

patterns-established:
  - "Column-group validation: strict required columns checked via set difference, alternative-name groups checked via any-of membership"

requirements-completed: [SCHM-01, SCHM-02]

# Metrics
duration: 3min
completed: 2026-02-27
---

# Phase 4 Plan 2: Schema Validation Summary

**Schema validation on transform_batch() and transform_arrow_batch() with dual-format support for normalized and raw simulation column names**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-27T16:26:41Z
- **Completed:** 2026-02-27T16:29:51Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Both transform_batch() and transform_arrow_batch() now raise descriptive ValueError before any computation when required columns are missing
- Validation supports both normalized format (units/traits/streak) and raw simulation format (board_names/trait_names/win_streak)
- 10 schema validation tests covering dict path, Arrow path, empty batches, error messages, raw format, and constant verification
- Full test suite passes (135 tests, 0 failures)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add required-columns constant and validation to both transform methods** - `297a213` (feat)
2. **Task 1 fix: Support alternative column names in schema validation** - `fd19c9b` (fix)
3. **Task 2: Add schema validation tests for both dict and Arrow paths** - `f4b4e4a` (test)

## Files Created/Modified
- `models/feature_engineering.py` - Added REQUIRED_COLUMNS frozenset (5 strict columns), _REQUIRED_COLUMN_GROUPS tuple (3 groups with alternative names), _validate_columns() method, validation calls in transform_batch() and transform_arrow_batch()
- `tests/test_feature_engineering.py` - Added 8 new tests covering both dict and Arrow validation paths, raw format acceptance, empty batch handling, and constant verification

## Decisions Made
- REQUIRED_COLUMNS contains only the 5 columns with no alternatives (level, hp, gold, round, augments). Columns with alternative names (streak/win_streak, units/board/board_names, traits/trait_names) are validated via _REQUIRED_COLUMN_GROUPS with any-of semantics.
- Column-group validation uses tuple-of-tuples for the group definitions, with `any(name in present for name in group)` check per group.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Strict REQUIRED_COLUMNS rejected legitimate raw simulation data**
- **Found during:** Task 2 (test verification)
- **Issue:** Original REQUIRED_COLUMNS included `streak`, `units`, and `traits` as required, but transform_batch() also supports alternative column names from raw simulation output (`win_streak`/`loss_streak`, `board_names`/`board_stars`, `trait_names`/`trait_counts`). The test_data_loader.py fixture uses these alternative names, causing ValueError.
- **Fix:** Split validation into strict REQUIRED_COLUMNS (5 columns with no alternatives) and _REQUIRED_COLUMN_GROUPS (3 groups where at least one alternative must be present). Updated _validate_columns() to check both.
- **Files modified:** models/feature_engineering.py
- **Verification:** Full test suite passes (135 tests), including test_data_loader.py which uses raw format
- **Committed in:** fd19c9b

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential correctness fix. The plan specified 8 strict required columns but the codebase legitimately supports alternative column names. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviation above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 4 (Type Contracts and Schema Validation) is now complete
- Both plans delivered: 04-01 (evaluator type contracts) and 04-02 (schema validation)
- Ready for Phase 5

## Self-Check: PASSED

- All files verified present: models/feature_engineering.py, tests/test_feature_engineering.py
- All commits verified: 297a213, fd19c9b, f4b4e4a
- SUMMARY.md verified present

---
*Phase: 04-type-contracts-and-schema-validation*
*Completed: 2026-02-27*
