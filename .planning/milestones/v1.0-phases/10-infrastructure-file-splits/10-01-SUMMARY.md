---
phase: 10-infrastructure-file-splits
plan: 01
subsystem: infra
tags: [python-modules, facade-pattern, file-split, cloud-runner]

# Dependency graph
requires:
  - phase: 08-global-state-elimination
    provides: "BatchRunner class with instance-scoped state (no module globals)"
provides:
  - "_cloud_runner_utils.py with constants and standalone helper functions"
  - "_cloud_runner_writer.py with StreamingWriter class"
  - "_cloud_runner_core.py with BatchRunner, BatchRunnerConfig, run_game, _worker_init"
  - "cloud_runner.py facade with re-exports and CloudRunner alias"
affects: [11-feature-engineering-split, 12-abilities-systems-split]

# Tech tracking
tech-stack:
  added: []
  patterns: ["underscore-prefixed sub-module with facade re-export", "noqa F401 for intentional re-exports"]

key-files:
  created:
    - "simulator/_cloud_runner_utils.py"
    - "simulator/_cloud_runner_writer.py"
    - "simulator/_cloud_runner_core.py"
  modified:
    - "simulator/cloud_runner.py"
    - "scripts/ci/check_public_surface_allowlist.py"
    - ".gitignore"

key-decisions:
  - "Used noqa: F401 for facade re-exports rather than __all__ to keep each re-export explicit and greppable"
  - "Added .gitignore whitelist entries for new simulator files (simulator/** ignore-all pattern requires explicit exceptions)"

patterns-established:
  - "Facade re-export pattern: underscore-prefixed sub-modules with original file as thin facade"
  - "Import inspect at facade level for monkeypatch compatibility in tests"

requirements-completed: [SPLT-02, SPLT-05]

# Metrics
duration: 10min
completed: 2026-02-28
---

# Phase 10 Plan 01: cloud_runner.py Split Summary

**Split 2,070-LOC cloud_runner.py into 3 sub-modules (utils 293, writer 536, core 735 LOC) plus 586-LOC facade with all 35 targeted tests passing unchanged**

## Performance

- **Duration:** 10 min
- **Started:** 2026-02-28T16:44:31Z
- **Completed:** 2026-02-28T16:55:28Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Split monolithic cloud_runner.py (2,070 LOC) into 3 focused sub-modules, all under 1,000 LOC
- All existing import paths preserved via facade re-exports including private symbols used by tests
- CloudRunner = BatchRunner alias added for roadmap success criteria
- CI allowlist and .gitignore updated for 3 new files
- 184 tests pass (2 skipped, 2 deselected pre-existing Python 3.14 failures)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create cloud_runner sub-modules** - `11b9126` (feat)
2. **Task 2: Convert cloud_runner.py to facade and update allowlist** - `e322c72` (feat)

## Files Created/Modified
- `simulator/_cloud_runner_utils.py` - Constants (WILSON_Z_95, AGENT_PROFILES) and standalone helper functions (293 LOC)
- `simulator/_cloud_runner_writer.py` - StreamingWriter class for incremental result output (536 LOC)
- `simulator/_cloud_runner_core.py` - BatchRunnerConfig, BatchAbort, run_game, _worker_init, BatchRunner (735 LOC)
- `simulator/cloud_runner.py` - Thin facade with re-exports, CloudRunner alias, CLI entry point (586 LOC)
- `scripts/ci/check_public_surface_allowlist.py` - Added 3 new simulator file entries
- `.gitignore` - Added whitelist entries for 3 new underscore-prefixed files

## Decisions Made
- Used `noqa: F401` annotations on facade re-exports rather than `__all__` list -- keeps each re-export explicit and greppable while satisfying ruff
- Added .gitignore whitelist entries because `simulator/**` ignore-all pattern requires explicit exceptions for each tracked file
- Removed unused `sys` import from `_cloud_runner_core.py` and unused `_round_or_none` import from `_cloud_runner_writer.py` (not actually used in writer; only used in utils via `_build_cost_telemetry`)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] .gitignore whitelist for new simulator files**
- **Found during:** Task 1 (committing sub-modules)
- **Issue:** `simulator/**` gitignore pattern blocked tracking of new `_cloud_runner_*.py` files
- **Fix:** Added 3 whitelist entries to `.gitignore` in alphabetical order
- **Files modified:** `.gitignore`
- **Verification:** `git add` succeeded after whitelist update
- **Committed in:** `11b9126` (Task 1 commit)

**2. [Rule 1 - Bug] Import sorting and unused imports in sub-modules**
- **Found during:** Task 1 (ruff verification)
- **Issue:** ruff I001 (import sorting) violations in core and writer; unused `sys` import in core; unused `_round_or_none` import in writer
- **Fix:** Reordered imports per ruff isort rules; removed unused imports
- **Files modified:** `simulator/_cloud_runner_core.py`, `simulator/_cloud_runner_writer.py`
- **Verification:** `ruff check` and `ruff format --check` pass on all 3 sub-modules
- **Committed in:** `11b9126` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both auto-fixes necessary for correctness. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- cloud_runner split complete with all backward-compatible imports verified
- Phase 10 Plan 02 (feature_engineering.py split) can proceed independently
- Facade re-export pattern established for reuse in Plan 02

---
*Phase: 10-infrastructure-file-splits*
*Completed: 2026-02-28*
