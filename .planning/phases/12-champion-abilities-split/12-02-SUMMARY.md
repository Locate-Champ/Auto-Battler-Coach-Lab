---
phase: 12-champion-abilities-split
plan: "02"
subsystem: simulator
tags: [mixin, composition, MRO, champion-abilities, refactor, deferred-import-replacement, ci-consolidation]

# Dependency graph
requires:
  - phase: 12-champion-abilities-split/12-01
    provides: _AbilitiesBaseMixin, _AbilitiesSystemsMixin, intermediate facade, dead duplicate removal
provides:
  - _AbilitiesHeroAugmentsMixin sub-module (_abilities_hero_augments.py, 423 LOC) with hero augment handlers + tick dispatcher
  - _AbilitiesAlphabeticalMixin sub-module (_abilities_alphabetical.py, 1,773 LOC) with 43 champion handlers
  - _AbilitiesCostTiersMixin sub-module (_abilities_cost_tiers.py, 1,217 LOC) with Cost 1-5 champion abilities
  - Final 5-mixin facade (champion_abilities.py, 31 LOC)
  - Consolidated CI parity gate (removed redundant pytest invocation)
  - 80 total deferred imports replaced with module-level (78 in new sub-modules + 2 missed in systems)
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns: [five-mixin-facade-composition, deferred-import-elimination-complete]

key-files:
  created:
    - simulator/core/_abilities_hero_augments.py
    - simulator/core/_abilities_alphabetical.py
    - simulator/core/_abilities_cost_tiers.py
  modified:
    - simulator/core/champion_abilities.py
    - simulator/core/_abilities_systems.py
    - .github/workflows/test-coverage.yml

key-decisions:
  - "MRO order finalized: CostTiers, Alphabetical, HeroAugments, Systems, Base (base rightmost)"
  - "Removed 2 missed deferred imports in _abilities_systems.py (galio bench DamageType/UnitState, skarner impale HexGrid)"
  - "CI parity gate consolidated by removing redundant single-test pytest invocation"

patterns-established:
  - "Champion abilities 5-mixin facade: CostTiers > Alphabetical > HeroAugments > Systems > Base in MRO"
  - "All deferred from .combat_engine imports eliminated across all _abilities_*.py sub-modules"

requirements-completed: [SPLT-04, SPLT-05, SPLT-06, BNCH-01]

# Metrics
duration: 7min
completed: 2026-03-02
---

# Phase 12 Plan 02: Final 3-Mixin Extraction + CI Consolidation Summary

**Extracted hero augments, alphabetical, and cost tier mixins from champion_abilities.py, completing the 5-mixin facade at 31 LOC (down from 5,911), with CI parity gate consolidation**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-02T22:06:29Z
- **Completed:** 2026-03-02T22:13:09Z
- **Tasks:** 2
- **Files modified:** 6 (3 created, 3 modified)

## Accomplishments
- Extracted _AbilitiesHeroAugmentsMixin with hero augment handlers for Xin Zhao, Rumble, Illaoi, Jhin, Viego + tick dispatcher (423 LOC)
- Extracted _AbilitiesAlphabeticalMixin with 43 champion handlers aatrox through shyvana (1,773 LOC)
- Extracted _AbilitiesCostTiersMixin with Cost 1-5 champion abilities (1,217 LOC)
- Finalized champion_abilities.py as thin 5-mixin facade (31 LOC, down from 5,911 original / 3,472 after Plan 01)
- Replaced 78 deferred imports in 3 new sub-modules with module-level imports from _combat_types/_hex_grid
- Cleaned 2 missed deferred imports in _abilities_systems.py from Plan 01
- Consolidated CI parity gate steps (removed redundant single-test pytest invocation) per BNCH-01
- All 6 determinism benchmark runs pass
- Full ruff lint clean across entire codebase

## LOC Report

| File | LOC | Role |
|------|-----|------|
| simulator/core/champion_abilities.py | 31 | Final 5-mixin facade |
| simulator/core/_abilities_base.py | 174 | Cast dispatch, helpers, _deal_damage, _apply_stun |
| simulator/core/_abilities_systems.py | 1,965 | 10 named systems + 8 named passives |
| simulator/core/_abilities_hero_augments.py | 423 | Hero augment handlers + tick dispatcher |
| simulator/core/_abilities_alphabetical.py | 1,773 | 43 alphabetical champion handlers |
| simulator/core/_abilities_cost_tiers.py | 1,217 | Cost 1-5 champion abilities |
| **Total** | **5,583** | **vs 5,911 original (328 LOC reduction from dead code + import cleanup)** |

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract 3 remaining sub-modules and finalize facade** - `1061d8e` (refactor)
2. **Task 2: Consolidate CI parity gate and run full test suite** - `c8178a2` (chore)

## Files Created/Modified
- `simulator/core/_abilities_hero_augments.py` - _AbilitiesHeroAugmentsMixin: process_hero_augment_ticks, xinzhao_hero_tick, rumble_hero_tick, _cast_xinzhao/_cast_rumble/_cast_illaoi/_cast_jhin hero augment variants, check_illaoi_recast, viego_hero_augment_check
- `simulator/core/_abilities_alphabetical.py` - _AbilitiesAlphabeticalMixin: 43 _cast_X methods (aatrox, atakhan, ambessa, aphelios, aurelionsol, caitlyn, darius, draven, lissandra, lux, malzahar, renekton, seraphine, swain, vayne, veigar, wukong, yasuo, yone, yunara, zaahen, annie, annietibbers, bard, diana, fiddlesticks, gangplank, kindred, leblanc, milio, missfortune, nidalee, singed, thresh, warwick, loris, shyvana)
- `simulator/core/_abilities_cost_tiers.py` - _AbilitiesCostTiersMixin: Cost 1 (anivia, blitzcrank, briar, jarvaniv, kogmaw, lulu, qiyana, shen, sona), Cost 2 (ashe, chogath, ekko, graves, neeko, orianna, poppy, reksai, sion, teemo, tristana, tryndamere, twistedfate, vi), Cost 3 (ahri, drmundo, jinx, kennen, kobuko, nautilus, sejuani, zoe), Cost 4 (belveth, braum, fizz, garen, kaisa, nasus), Cost 5 (azir, ornn, volibear)
- `simulator/core/champion_abilities.py` - Final facade: ChampionAbilities composing 5 mixins via MRO
- `simulator/core/_abilities_systems.py` - Removed 2 remaining deferred imports (galio bench + skarner impale)
- `.github/workflows/test-coverage.yml` - Consolidated parity helper test steps (2 -> 1)

## Decisions Made
- MRO order finalized: CostTiers (leftmost), Alphabetical, HeroAugments, Systems, Base (rightmost) -- matches pattern from Plan 01
- Removed 2 missed deferred imports in _abilities_systems.py that were overlooked in Plan 01 (galio DamageType/UnitState, skarner HexGrid) -- all already had module-level equivalents
- CI parity gate consolidated by removing redundant single-test pytest invocation (test_cli_parity_dump_signatures_only_artifact_is_smaller is already run by the full test file invocation)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed 2 missed deferred imports in _abilities_systems.py**
- **Found during:** Task 2 (verification step: grep for deferred imports)
- **Issue:** 2 deferred `from .combat_engine import` statements remained in _abilities_systems.py from Plan 01 (lines 1150 and 1668), despite module-level imports already being present
- **Fix:** Removed both redundant deferred imports (DamageType/UnitState in galio bench handler, HexGrid in skarner impale handler)
- **Files modified:** simulator/core/_abilities_systems.py
- **Verification:** `grep -rn "from .combat_engine import" simulator/core/_abilities_*.py` returns no results
- **Committed in:** c8178a2 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 redundant import cleanup)
**Impact on plan:** Necessary for complete deferred import elimination. No scope creep.

## Issues Encountered
None -- all 3 extractions were clean mechanical moves. Benchmark determinism confirmed identical after extraction.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 12 (final phase) is COMPLETE
- All 12 phases of the v1.0 milestone are done
- champion_abilities.py reduced from 5,911 LOC monolith to 31 LOC facade with 5 clean sub-modules
- Full 5-mixin MRO composition: CostTiers > Alphabetical > HeroAugments > Systems > Base
- All 80 deferred imports replaced with module-level imports (78 in Plan 02 + 2 missed from Plan 01)
- All existing import paths preserved (from simulator.core.champion_abilities import ChampionAbilities)
- CI parity gate consolidated per BNCH-01

---
*Phase: 12-champion-abilities-split*
*Completed: 2026-03-02*
