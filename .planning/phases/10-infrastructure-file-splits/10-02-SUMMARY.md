---
phase: 10-infrastructure-file-splits
plan: 02
subsystem: models
tags: [feature-engineering, mixin-pattern, code-split, facade]

# Dependency graph
requires:
  - phase: 06-configuration-extraction-and-ruff-gates
    provides: "NumericFeatureConfig in models/feature_config.py"
  - phase: 04-type-contracts-and-schema-validation
    provides: "REQUIRED_COLUMNS and _REQUIRED_COLUMN_GROUPS column validation"
provides:
  - "Four underscore-prefixed sub-modules splitting feature_engineering.py into <1000 LOC files"
  - "Mixin class pattern (_LoaderMixin, _TransformMixin, _BatchTransformMixin)"
  - "Facade pattern preserving all existing import paths"
affects: [10-infrastructure-file-splits]

# Tech tracking
tech-stack:
  added: []
  patterns: [mixin-class-inheritance, underscore-prefix-internal-modules, facade-re-export]

key-files:
  created:
    - models/_feature_engineering_config.py
    - models/_feature_engineering_loaders.py
    - models/_feature_engineering_transform.py
    - models/_feature_engineering_batch.py
  modified:
    - models/feature_engineering.py

key-decisions:
  - "MRO order: _LoaderMixin, _TransformMixin, _BatchTransformMixin -- loaders first for __init__ call order"
  - "TFTFeatureEngineer class defined in facade (not sub-module) to preserve pickle __module__ path"
  - "Cython try/except import block placed in both _transform and _batch modules independently"

patterns-established:
  - "Mixin pattern: underscore-prefixed sub-modules with no __init__, methods access self.* via MRO"
  - "Facade pattern: thin file re-exports all public symbols from sub-modules"
  - "One-way dependency graph: all sub-modules depend only on _config, never on each other"

requirements-completed: [SPLT-01, SPLT-05]

# Metrics
duration: 8min
completed: 2026-02-28
---

# Phase 10 Plan 02: Feature Engineering Split Summary

**Split 2,213 LOC feature_engineering.py into 4 mixin sub-modules (config 147, loaders 476, transform 880, batch 717 LOC) plus 125 LOC facade preserving all import paths and pickle compatibility**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-28T16:44:33Z
- **Completed:** 2026-02-28T16:52:21Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Split monolithic 2,213 LOC file into 5 files all under 1,000 LOC
- All 16 existing tests pass without modification
- Pickle `__module__` preserved as `models.feature_engineering` for serialization compatibility
- All public imports (`TFTFeatureEngineer`, `FeatureEngineer`, `REQUIRED_COLUMNS`, `FeatureConfig`, `TraitMetadata`) continue to resolve from original path

## Task Commits

Each task was committed atomically:

1. **Task 1: Create feature_engineering sub-modules** - `b2cd37b` (feat)
2. **Task 2: Convert feature_engineering.py to facade with mixin inheritance** - `8c928b5` (feat)

## Files Created/Modified
- `models/_feature_engineering_config.py` - Constants, FeatureConfig/TraitMetadata dataclasses, helper functions (147 LOC)
- `models/_feature_engineering_loaders.py` - _LoaderMixin: all _load_* and _build_fast_lookup_sets methods (476 LOC)
- `models/_feature_engineering_transform.py` - _TransformMixin: single-row transform, extraction, feature methods (880 LOC)
- `models/_feature_engineering_batch.py` - _BatchTransformMixin: batch/Arrow transform, vectorized feature methods (717 LOC)
- `models/feature_engineering.py` - Facade: TFTFeatureEngineer class with mixin inheritance, re-exports (125 LOC)

## Decisions Made
- MRO order `_LoaderMixin, _TransformMixin, _BatchTransformMixin` because `__init__` calls `_load_reference_data` (loaders) then `_build_feature_names` (transform)
- Kept `TFTFeatureEngineer` class definition in facade file so `__module__` stays `models.feature_engineering` for pickle compatibility
- Cython `try/except` import block duplicated in `_transform` and `_batch` modules since both use Cython fast paths independently
- Used `__all__` in facade to document all re-exported public symbols

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed ruff import sorting and unused import**
- **Found during:** Task 1 (sub-module creation)
- **Issue:** ruff flagged I001 import sorting in _batch and _loaders, and unused `Optional` import in _loaders
- **Fix:** Removed unused `Optional` from _loaders, ran `ruff check --fix` and `ruff format` on all sub-modules
- **Files modified:** models/_feature_engineering_loaders.py, models/_feature_engineering_batch.py
- **Verification:** `ruff check` and `ruff format --check` pass clean
- **Committed in:** b2cd37b (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minor import cleanup required by ruff. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Feature engineering module fully split and tested
- Pattern established for remaining infrastructure splits in Phase 10+
- All callers (tests, coach/scoring/evaluator.py) continue working without changes

---
*Phase: 10-infrastructure-file-splits*
*Completed: 2026-02-28*
