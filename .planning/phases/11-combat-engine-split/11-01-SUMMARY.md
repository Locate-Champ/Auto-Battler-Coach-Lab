---
phase: 11-combat-engine-split
plan: 01
subsystem: simulator
tags: [python-modules, facade-pattern, file-split, combat-engine]

# Dependency graph
requires:
  - phase: 10-infrastructure-file-splits
    provides: facade re-export pattern with noqa F401, mixin composition pattern
provides:
  - Five standalone sub-modules extracted from combat_engine.py
  - Facade re-exports preserving all import paths
  - combat_engine.py reduced to CombatEngine class + main() (~2,652 LOC)
affects: [11-02-combat-engine-split, 12-champion-abilities-split]

# Tech tracking
tech-stack:
  added: []
  patterns: [TYPE_CHECKING imports for cross-module type hints, module-level side effects travel with host class]

key-files:
  created:
    - simulator/core/_combat_types.py
    - simulator/core/_hex_grid.py
    - simulator/core/_item_database.py
    - simulator/core/_augment_manager.py
    - simulator/core/_trait_manager.py
  modified:
    - simulator/core/combat_engine.py

key-decisions:
  - "Item effects import block moved to _item_database.py (primary consumer) rather than staying in facade"
  - "TYPE_CHECKING pattern used for Unit type hints in _augment_manager.py and _trait_manager.py to avoid circular imports"
  - "AugmentManager augment loading try/except block travels with AugmentManager class to _augment_manager.py"

patterns-established:
  - "TYPE_CHECKING for forward references: sub-modules use from __future__ import annotations + TYPE_CHECKING for cross-module type hints"
  - "Module-level side effects travel with host: HexGrid._build_luts() at module level in _hex_grid.py, not deferred"

requirements-completed: [SPLT-03, SPLT-06]

# Metrics
duration: 14min
completed: 2026-03-02
---

# Phase 11 Plan 01: Sub-Module Extraction Summary

**Five sub-modules extracted from combat_engine.py (types, hex grid, item database, augment manager, trait manager) with facade re-exports preserving all import paths and benchmark determinism**

## Performance

- **Duration:** 14 min
- **Started:** 2026-03-02T05:52:43Z
- **Completed:** 2026-03-02T06:06:57Z
- **Tasks:** 2
- **Files modified:** 6 (1 modified, 5 created)

## Accomplishments
- Extracted ~2,660 LOC from combat_engine.py into 5 private sub-modules
- All existing import paths preserved through facade re-exports with noqa: F401
- Benchmark determinism verified after each of the 5 extraction steps
- All combat regression tests pass unchanged

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract _combat_types.py, _hex_grid.py, and _item_database.py** - `267a0a7` (feat)
2. **Task 2: Extract _augment_manager.py and _trait_manager.py** - `67d7b33` (feat)

## Files Created/Modified
- `simulator/core/_combat_types.py` - All enums (DamageType, TargetingType, AbilityType, UnitState), all dataclasses (CombatStats, Ability, Item, Buff, DotEffect, Unit), helpers (_star_val, _load_combat_data, _COMBAT_DATA_CACHE)
- `simulator/core/_hex_grid.py` - HexGrid class with _build_luts() called at module level
- `simulator/core/_item_database.py` - ItemDatabase, AbilityDatabase, item effects import block, set16_items import block
- `simulator/core/_augment_manager.py` - AugmentManager class, augment data loading block
- `simulator/core/_trait_manager.py` - TeamTraitState, TraitManager (~1,390 LOC with all _apply_* methods)
- `simulator/core/combat_engine.py` - Facade with CombatEngine class, main(), and re-exports of all extracted names

## Decisions Made
- Moved item effects import block (get_item_on_hit, etc.) to _item_database.py since ItemDatabase.create_item() is the primary consumer
- Used TYPE_CHECKING pattern with `from __future__ import annotations` in _augment_manager.py and _trait_manager.py for Unit type hints, avoiding any circular import risk
- Removed unused imports from combat_engine.py after each extraction (heapq, json, dataclass, field, Enum, Callable) to keep the facade clean
- AugmentManager augment loading try/except block moved to _augment_manager.py alongside the class that consumes it

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- combat_engine.py is now 2,652 LOC (reduced from 5,312), containing only CombatEngine class + main()
- Ready for Plan 02 (CombatEngine mixin split into _combat_actions.py, _combat_processing.py, _combat_runners.py)
- All 5 sub-modules independently importable and tested

## Self-Check: PASSED

- All 5 created files exist on disk
- Both task commits (267a0a7, 67d7b33) found in git log
- Benchmark determinism verified: all 3 test suites pass
- Full ruff lint and format check passes
- All facade and sub-module imports verified

---
*Phase: 11-combat-engine-split*
*Completed: 2026-03-02*
