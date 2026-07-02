---
phase: 09-simulator-and-coach-exception-hardening
plan: 01
subsystem: exception-handling
tags: [ruff, BLE001, exception-narrowing, simulator, coach, evaluator, pickle]

# Dependency graph
requires:
  - phase: 01-models-exception-hardening
    provides: "(ImportError, OSError) pattern for extension imports"
  - phase: 06-configuration-extraction-and-ruff-gates
    provides: "BLE001 ruff rule enforcement"
  - phase: 07-sklearnevaluator-wiring
    provides: "SklearnEvaluator with joblib.load and fe.transform sites"
provides:
  - "Zero BLE001 violations in simulator/ and coach/ directories"
  - "Narrowed exception tuples for all 5 broad except-Exception sites"
  - "CCG-validated widened tuples for joblib.load and fe.transform failure modes"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "(ImportError, OSError) for C extension import failures"
    - "Widened pickle/joblib tuple: (OSError, EOFError, ValueError, KeyError, AttributeError, ImportError, pickle.UnpicklingError)"
    - "(TypeError, ValueError, KeyError, AttributeError) for feature transform failures"

key-files:
  created: []
  modified:
    - simulator/benchmark.py
    - simulator/game/game.py
    - coach/scoring/evaluator.py

key-decisions:
  - "Applied CCG-widened exception tuples for joblib.load (7 types) and fe.transform (4 types) based on empirical Codex testing"
  - "Used (ImportError, OSError) for all 3 simulator C extension import sites -- same pattern as Phase 1"
  - "Added import pickle to evaluator.py for pickle.UnpicklingError reference"

patterns-established:
  - "(ImportError, OSError) is the standard tuple for C extension dynamic import try/except"
  - "joblib.load failure modes are wider than typical pickle -- include EOFError, KeyError, AttributeError, ImportError"

requirements-completed: [EXCP-03, EXCP-04]

# Metrics
duration: 3min
completed: 2026-02-28
---

# Phase 9 Plan 1: Simulator and Coach Exception Hardening Summary

**Narrowed 5 broad except-Exception handlers to specific types across simulator/benchmark.py, simulator/game/game.py, and coach/scoring/evaluator.py -- zero BLE001 violations remain**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-28T07:41:13Z
- **Completed:** 2026-02-28T07:43:44Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Eliminated all 5 `except Exception` handlers in simulator/ and coach/ directories
- Applied CCG critique widened tuples for evaluator.py based on empirical failure mode testing
- Maintained deterministic benchmark output after game.py change (hard gate per CLAUDE.md)
- All 19 coach evaluator tests pass with narrowed exception types

## Task Commits

Each task was committed atomically:

1. **Task 1: Narrow simulator exception sites (benchmark.py + game.py)** - `c7ff50f` (fix)
2. **Task 2: Narrow coach evaluator exception sites (evaluator.py)** - `7d9dedf` (fix)

**Deviation fix:** `adcd130` - fix missed benchmark.py site at 4-space indent

## Files Created/Modified
- `simulator/benchmark.py` - Narrowed 2 `except Exception` to `except (ImportError, OSError)` in _create_engine and _create_rust_game_simulator
- `simulator/game/game.py` - Narrowed 1 `except Exception` to `except (ImportError, OSError)` in _create_combat_engine
- `coach/scoring/evaluator.py` - Added `import pickle`, narrowed joblib.load handler to 7 specific types, narrowed fe.transform handler to 4 specific types

## Decisions Made
- Applied CCG-widened exception tuples instead of the narrower plan-specified tuples. The CCG post-plan critique (ccg-plan-review.md) recommended wider tuples based on Codex empirical testing of joblib.load() and fe.transform() failure modes.
- Used (ImportError, OSError) for all simulator sites -- same pattern established in Phase 1 for extension imports.
- Added `import pickle` as stdlib import for `pickle.UnpicklingError` reference.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Missed benchmark.py exception site due to indentation mismatch**
- **Found during:** Task 1 verification (grep guard)
- **Issue:** `replace_all` matched `        except Exception as exc:` (8-space indent) but `_create_rust_game_simulator()` uses 4-space indent, so it was missed
- **Fix:** Manually narrowed the 4-space indented site to `except (ImportError, OSError) as exc:`
- **Files modified:** simulator/benchmark.py
- **Verification:** grep guard returns zero lines, ruff BLE001 passes
- **Committed in:** adcd130

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Auto-fix necessary for correctness. No scope creep.

## Issues Encountered
- ruff-format pre-commit hook reformatted the long joblib.load exception tuple to multi-line format. Re-staged and committed cleanly on second attempt.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All BLE001 violations in simulator/ and coach/ are now resolved
- validate_reference_data.py noqa suppression remains intact and intentional
- Ready for Phase 10+ monolithic splits with all exception handling correct

---
*Phase: 09-simulator-and-coach-exception-hardening*
*Completed: 2026-02-28*
