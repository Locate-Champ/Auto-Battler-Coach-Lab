---
phase: 12-champion-abilities-split
plan: "01"
subsystem: simulator
tags: [mixin, composition, MRO, champion-abilities, refactor, deferred-import-replacement]

# Dependency graph
requires:
  - phase: 11-combat-engine-split/11-02
    provides: Mixin composition pattern (MRO-based), _combat_types.py exports, _hex_grid.py exports
provides:
  - _AbilitiesBaseMixin sub-module (_abilities_base.py, 174 LOC) with cast dispatch, 8 helpers, damage, stun, immortal resurrection
  - _AbilitiesSystemsMixin sub-module (_abilities_systems.py, 1,967 LOC) with 10 named systems + 8 named passives
  - Intermediate facade ChampionAbilities inheriting (_AbilitiesSystemsMixin, _AbilitiesBaseMixin)
  - 5 dead duplicate method definitions removed
  - 26 deferred imports replaced with module-level imports in systems mixin
affects: [12-champion-abilities-split/12-02]

# Tech tracking
tech-stack:
  added: []
  patterns: [mixin-composition-for-champion-abilities, deferred-import-elimination]

key-files:
  created:
    - simulator/core/_abilities_base.py
    - simulator/core/_abilities_systems.py
  modified:
    - simulator/core/champion_abilities.py

key-decisions:
  - "_AbilitiesBaseMixin is rightmost in MRO -- provides __init__, helpers, dispatch for all other mixins"
  - "_AbilitiesSystemsMixin is left of base in MRO -- its _cast_leona/_cast_skarner/_cast_xerath/_cast_zilean override dead alphabetical copies"
  - "Deferred from .item_effects import kept in _apply_stun (cross-module circular risk) -- all other deferred imports replaced with module-level"
  - "Dead duplicate definitions removed during base extraction rather than during systems extraction (simplifies subsequent extractions)"
  - "Removed unused random import from _abilities_base.py and unused Optional/Tuple/CombatEngine imports from facade"

patterns-established:
  - "Champion abilities mixin composition: base rightmost, systems left of base, remaining mixins to be added left of systems"
  - "Deferred import replacement: from .combat_engine import X -> from ._combat_types import X at module level"

requirements-completed: [SPLT-04, SPLT-05, SPLT-06]

# Metrics
duration: 9min
completed: 2026-03-02
---

# Phase 12 Plan 01: AbilitiesBase + Systems Extraction Summary

**Extracted _AbilitiesBaseMixin (cast dispatch + 12 helpers) and _AbilitiesSystemsMixin (10 named systems + 8 passives) from champion_abilities.py, reducing facade from 5,911 to 3,472 LOC with benchmark-gated determinism after each step**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-02T21:54:16Z
- **Completed:** 2026-03-02T22:03:19Z
- **Tasks:** 2
- **Files modified:** 3 (2 created, 1 modified)

## Accomplishments
- Extracted _AbilitiesBaseMixin with __init__, cast(), 8 helpers, _hex_distance, _deal_damage, _apply_stun, check_immortal_resurrection (174 LOC)
- Extracted _AbilitiesSystemsMixin with all 10 named systems + 8 named passives (1,967 LOC)
- Removed 5 dead duplicate method definitions (_cast_diana, _cast_leona x2, _cast_skarner, _cast_xerath, _cast_zilean)
- Replaced 26 deferred imports in systems mixin with module-level imports from _combat_types and _hex_grid
- champion_abilities.py reduced from 5,911 to 3,472 LOC (41% reduction)
- All 6 determinism benchmark runs pass (3 after base extraction, 3 after systems extraction)
- Full ruff lint clean across all 3 files

## LOC Report

| File | LOC | Role |
|------|-----|------|
| simulator/core/_abilities_base.py | 174 | Cast dispatch, 8 helpers, _deal_damage, _apply_stun, check_immortal_resurrection |
| simulator/core/_abilities_systems.py | 1,967 | 10 named systems + 8 named passives |
| simulator/core/champion_abilities.py | 3,472 | Intermediate facade + remaining alphabetical, hero augments, cost tiers |

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract _AbilitiesBaseMixin into _abilities_base.py** - `5cf524f` (refactor)
2. **Task 2: Extract _AbilitiesSystemsMixin into _abilities_systems.py** - `f28e0c5` (refactor)

## Files Created/Modified
- `simulator/core/_abilities_base.py` - _AbilitiesBaseMixin: __init__, cast(), _get_var, _find_farthest_enemy, _find_nearest_enemy, _find_lowest_hp_enemy, _get_enemies_in_radius, _dash_to_position, _hex_distance, _deal_damage, _apply_stun, check_immortal_resurrection
- `simulator/core/_abilities_systems.py` - _AbilitiesSystemsMixin: Lucian/Senna soulbound, Ryze trait-dependent, Sylas trifold, Shadow Isles (Gwen/Kalista/Viego/Yorick/Ziggs), Tahm Kench glutton, Galio bench mechanic, T-HEX pilot, Baron Nashor, Rift Herald, Leona flat DR, Taric passive MR, Skarner armor aura, Xerath ascendant, Zilean time bomb, Mel mana drain, Sett show stopper, Brock seismic
- `simulator/core/champion_abilities.py` - Intermediate facade: ChampionAbilities(_AbilitiesSystemsMixin, _AbilitiesBaseMixin), plus remaining methods not yet extracted (alphabetical, hero augments, cost tiers)

## Decisions Made
- _AbilitiesBaseMixin is rightmost in MRO -- provides __init__ and all helpers that other mixins call through self.*
- _AbilitiesSystemsMixin is left of base in MRO -- ensures active _cast_leona/_cast_skarner/_cast_xerath/_cast_zilean take precedence over any remnants
- Dead duplicate definitions removed during Task 1 (base extraction) rather than waiting -- simplifies subsequent extraction steps
- Kept deferred `from .item_effects import get_item_data` in _apply_stun (cross-module circular import risk per RESEARCH.md)
- Removed unused `random` import from _abilities_base.py and unused `Optional`/`Tuple`/`CombatEngine` from facade

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused imports flagged by ruff**
- **Found during:** Task 1 (after base extraction)
- **Issue:** `random` and `DamageType` were unused in _abilities_base.py after construction; `Optional`, `Tuple`, `CombatEngine` were unused in champion_abilities.py after removing base methods
- **Fix:** Removed unused imports from both files
- **Files modified:** simulator/core/_abilities_base.py, simulator/core/champion_abilities.py
- **Verification:** `ruff check` passes clean
- **Committed in:** 5cf524f (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 lint fix)
**Impact on plan:** Auto-fix necessary to pass ruff. No scope creep.

## Issues Encountered
None -- both extractions were clean mechanical moves. Benchmark determinism confirmed identical after each step.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 01 (base + systems) complete -- the two highest-risk extractions are done
- Remaining for Plan 02: hero augments (~385 LOC), alphabetical (~2,095 LOC), cost tiers (~1,270 LOC) -- all mechanical extractions
- champion_abilities.py at 3,472 LOC, to be reduced to ~50 LOC facade in Plan 02
- MRO pattern established: CostTiers, Alphabetical, HeroAugments, Systems, Base (leftmost to rightmost)

---
*Phase: 12-champion-abilities-split*
*Completed: 2026-03-02*
