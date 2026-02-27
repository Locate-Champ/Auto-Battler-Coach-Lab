---
phase: 06-configuration-extraction-and-ruff-gates
plan: 02
subsystem: infra
tags: [ruff, linting, exception-handling, blind-except, code-quality]

requires:
  - phase: 05-api-server-hardening
    provides: "Stable API server with test suite"
provides:
  - "BLE and B ruff rule enforcement across entire codebase"
  - "50 blind except handlers narrowed to specific exception types"
  - "32 B-rule violations fixed (B007, B009, B905)"
  - "Static lint gate preventing future broad exception handlers"
affects: [all-python-modules]

tech-stack:
  added: []
  patterns: ["specific exception types in all handlers", "underscore-prefixed unused loop vars", "explicit strict= on zip()"]

key-files:
  created: []
  modified:
    - ruff.toml
    - app/api/server.py
    - app/server/websocket.py
    - app/state/state_manager.py
    - app/run_app.py
    - app/watcher/log_watcher.py
    - app/frontend/images/set16_trait_palette.py
    - coach/coach.py
    - coach/offline/build_archetypes.py
    - coach/offline/eval_coach.py
    - coach/offline/view_traces.py
    - coach/scoring/archetypes.py
    - coach/scoring/evaluator.py
    - coach/scoring/features.py
    - models/data_loader.py
    - simulator/cloud_runner.py
    - simulator/core/combat_engine.py
    - simulator/core/engine_wrapper.py
    - simulator/game/game.py
    - simulator/game/unlocks.py
    - src/models/feature_engineering.py
    - tests/test_api_server.py
    - app/services/pool_tracker.py
    - coach/offline/train_evaluator.py
    - models/evaluate.py
    - models/information_theory.py
    - models/uncertainty.py
    - simulator/benchmark.py
    - simulator/core/champion_abilities.py
    - simulator/core/item_optimizer.py
    - simulator/core/positioning_optimizer.py
    - simulator/core/timing_utils.py
    - simulator/game/champion_pool.py
    - simulator/game/collector.py
    - simulator/game/player.py
    - src/models/placement_model.py

key-decisions:
  - "Narrowed exception types based on try-block operations rather than using noqa suppressions"
  - "Used strict=True for zip() where iterables are guaranteed same-length, strict=False where truncation is intentional"
  - "Legacy/quarantined dirs excluded from BLE+B to avoid touching dead code"

patterns-established:
  - "All new except handlers must use specific exception types (enforced by ruff BLE001)"
  - "Unused loop variables prefixed with underscore (enforced by ruff B007)"
  - "All zip() calls must specify explicit strict= parameter (enforced by ruff B905)"

requirements-completed: [EXCP-05]

duration: 12min
completed: 2026-02-27
---

# Plan 06-02: Ruff BLE+B Gate Enforcement Summary

**Fixed 82 BLE+B violations (50 blind excepts, 15 unused loop vars, 10 zip-without-strict, 7 getattr-with-constant) and enabled static lint enforcement in ruff.toml**

## Performance

- **Duration:** 12 min
- **Tasks:** 2
- **Files modified:** 36

## Accomplishments
- All 50 BLE001 blind except handlers narrowed to specific exception types across 21 files
- All 32 B-rule violations fixed: 15 B007 (unused loop vars), 7 B009 (getattr with constant), 10 B905 (zip without strict)
- ruff.toml updated with BLE+B in lint select; legacy dirs excluded
- `ruff check .` passes with zero violations across entire codebase

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix all B-rule violations (B007, B009, B905)** - `116974f` (fix)
2. **Task 2: Fix all BLE001 violations and enable BLE+B in ruff.toml** - `f7f3a8d` (fix)

## Files Created/Modified
- `ruff.toml` - Added BLE+B to lint select and legacy per-file-ignores
- `app/api/server.py` - Narrowed startup model loading excepts to (OSError, ImportError, RuntimeError)
- `app/server/websocket.py` - Narrowed WebSocket broadcast/parsing excepts to specific types
- `app/state/state_manager.py` - Narrowed state parsing excepts to (ValueError, KeyError, TypeError)
- `coach/scoring/*.py` - Narrowed scoring/feature excepts to (ValueError, KeyError, TypeError)
- `simulator/cloud_runner.py` - Narrowed cloud operation excepts to (OSError, ValueError, RuntimeError)
- `simulator/core/combat_engine.py` - Narrowed combat fallback excepts (no behavioral change)
- 29 additional files with B007/B009/B905 fixes

## Decisions Made
- Narrowed exception types by analyzing try-block operations rather than using noqa suppressions per plan guidance
- No error-handling behavior changed — only exception types in except clauses were narrowed

## Deviations from Plan
None - plan executed as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All ruff rules (E, F, W, I, BLE, B) now enforced across non-legacy codebase
- Any future `except Exception:` will be caught at lint time

---
*Phase: 06-configuration-extraction-and-ruff-gates*
*Completed: 2026-02-27*
