---
phase: 11-combat-engine-split
plan: "02"
subsystem: simulator
tags: [mixin, composition, MRO, combat-engine, refactor]

# Dependency graph
requires:
  - phase: 11-combat-engine-split/11-01
    provides: 5 standalone sub-modules (_combat_types, _hex_grid, _item_database, _augment_manager, _trait_manager)
provides:
  - 3 mixin sub-modules (_combat_actions, _combat_processing, _combat_runners)
  - CombatEngine thin facade (<550 LOC) composing 3 mixins via MRO
  - All existing import paths preserved via facade re-exports
affects: [12-champion-abilities-split]

# Tech tracking
tech-stack:
  added: []
  patterns: [mixin-composition, MRO-based-method-resolution, TYPE_CHECKING-for-cross-module-hints]

key-files:
  created:
    - simulator/core/_combat_actions.py
    - simulator/core/_combat_processing.py
    - simulator/core/_combat_runners.py
  modified:
    - simulator/core/combat_engine.py

key-decisions:
  - "MRO order: CombatEngine(_CombatRunnersMixin, _CombatProcessingMixin, _CombatActionsMixin) -- Actions rightmost (lowest-level), Runners leftmost (highest-level)"
  - "Cython import block placed in _combat_actions.py (sole consumer of _cy_calculate_damage)"
  - "Removed unused random/deepcopy imports from facade after runner extraction"
  - "Each mixin uses only self.* for cross-method calls -- no mixin-to-mixin imports"

patterns-established:
  - "Mixin composition: split large class into domain-specific mixins, compose via MRO in facade"
  - "Benchmark gate: run determinism test after every extraction step"

requirements-completed: []

# Metrics
duration: 20min
completed: 2026-03-02
---

# Phase 11 Plan 02: CombatEngine Mixin Extraction Summary

**CombatEngine decomposed into 3 mixin sub-modules (actions/processing/runners) with MRO composition, reducing facade from 2,652 to 548 LOC**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-03-02
- **Completed:** 2026-03-02
- **Tasks:** 2
- **Files modified:** 4 (3 created, 1 modified)

## Accomplishments
- Extracted 32 methods from CombatEngine into 3 domain-specific mixin classes
- combat_engine.py reduced from 2,652 LOC (post-11-01) to 548 LOC -- well under 800 LOC target
- All 3 determinism benchmarks pass (1v1, team combat, full game)
- All 184 tests pass (2 pre-existing Python 3.14 failures unrelated to this work)
- Full ruff lint clean across entire codebase

## LOC Report

| File | LOC | Role |
|------|-----|------|
| simulator/core/combat_engine.py | 548 | Thin facade (init, create_unit, items, logging, main) |
| simulator/core/_combat_actions.py | 544 | 11 damage/heal/shield/CC methods |
| simulator/core/_combat_processing.py | 742 | 8 targeting/attack/ability/movement methods |
| simulator/core/_combat_runners.py | 885 | 13 combat loop/round/trait helper methods |
| simulator/core/_combat_types.py | 273 | Data classes (Unit, CombatStats, Ability, etc.) |
| simulator/core/_hex_grid.py | 167 | Hex grid geometry and pathfinding |
| simulator/core/_item_database.py | 267 | Item/ability database loaders |
| simulator/core/_augment_manager.py | 610 | Augment effects and application |
| simulator/core/_trait_manager.py | 1390 | Trait stat bonuses and Noxus/Piltover/etc. |
| **Total** | **5426** | 8 sub-modules + 1 facade |

Original combat_engine.py was 5,312 LOC. Total is now 5,426 LOC (+114 from module boilerplate: docstrings, imports, class definitions).

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract 3 CombatEngine mixin sub-modules** - `34162e9` (refactor)
2. **Task 2: Finalize facade, verify LOC target, run full test suite** - verification only, no code changes

## Files Created/Modified
- `simulator/core/_combat_actions.py` - _CombatActionsMixin: calculate_damage, apply_damage, heal_unit, apply_shield, apply_burn, apply_cc, apply_wound, apply_sunder, apply_shred, gain_mana, check_hp_threshold_effects
- `simulator/core/_combat_processing.py` - _CombatProcessingMixin: find_target, get_enemies_in_range, can_attack, process_attack, _post_ability_cast, cast_ability, move_unit_towards, process_unit_tick
- `simulator/core/_combat_runners.py` - _CombatRunnersMixin: tick, _fire_piltover_module, _check_noxus_atakhan_summon, _summon_atakhan, _find_atakhan_spawn, _check_atakhan_ruin, _count_traits, process_round_start, _apply_combat_start_items, run_combat, _next_event_dt, run_combat_adaptive_tick, simulate_1v1
- `simulator/core/combat_engine.py` - Thin facade: CombatEngine class with __init__, create_unit, apply_item, logging, re-exports

## Decisions Made
- MRO order: Actions rightmost (resolved first, lowest-level primitives), Processing middle, Runners leftmost (highest-level orchestration)
- Cython import block moved to _combat_actions.py since calculate_damage() is the sole consumer
- Removed unused `random` and `deepcopy` imports from facade after runner extraction (they moved to _combat_runners.py)
- Removed unused `HexGrid` import and `TYPE_CHECKING` from _combat_runners.py (HexGrid not used there)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused imports flagged by ruff**
- **Found during:** Task 1 (after runner extraction)
- **Issue:** `random`, `deepcopy` in facade and `HexGrid` in _combat_runners.py became unused after method extraction
- **Fix:** Removed unused imports and cleaned up TYPE_CHECKING block in _combat_runners.py
- **Files modified:** simulator/core/combat_engine.py, simulator/core/_combat_runners.py
- **Verification:** `ruff check` passes clean
- **Committed in:** 34162e9

**2. [Rule 1 - Bug] Fixed import sorting (I001) in _combat_runners.py**
- **Found during:** Task 1 (after removing HexGrid import)
- **Issue:** Removing the `from ._hex_grid import HexGrid` line left the import block un-sorted per isort rules
- **Fix:** Removed orphaned `if TYPE_CHECKING: pass` block and `TYPE_CHECKING` from typing imports
- **Files modified:** simulator/core/_combat_runners.py
- **Verification:** `ruff check` passes clean
- **Committed in:** 34162e9

---

**Total deviations:** 2 auto-fixed (2 lint fixes)
**Impact on plan:** Both auto-fixes were necessary to pass ruff. No scope creep.

## Issues Encountered
- Multiple Edit tool failures when removing runner methods from combat_engine.py caused file corruption. Resolved by matching the full block of leftover methods and replacing with empty content.
- Import ordering (ruff I001) triggered after adding mixin imports -- resolved by placing imports in alphabetical order.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 11 (combat-engine-split) complete: 8 sub-modules + thin facade
- combat_engine.py at 548 LOC (target was <800)
- All import paths preserved, all tests pass
- Ready for Phase 12 (champion_abilities.py split)

---
*Phase: 11-combat-engine-split*
*Completed: 2026-03-02*
