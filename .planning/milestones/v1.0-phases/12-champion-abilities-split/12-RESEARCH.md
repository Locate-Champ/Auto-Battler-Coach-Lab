# Phase 12: Champion Abilities Split - Research

**Researched:** 2026-03-02
**Domain:** Python module decomposition / 5.9k LOC monolithic class split with determinism preservation
**Confidence:** HIGH

## Summary

Phase 12 splits `simulator/core/champion_abilities.py` (5,911 LOC) into AbilitiesBase plus sub-module mixins using the mixin composition pattern established in Phase 11. The file is well-segmented by comment banners into 14+ logical sections, making mechanical extraction low-risk. The primary technical challenge is the cross-method call audit for the special systems section, where methods call `self._deal_damage()`, `self._get_var()`, `self._find_nearest_enemy()`, and other helpers that must resolve through MRO from AbilitiesBase.

Phase 11 established the exact mixin composition pattern: underscore-prefixed sub-modules, `self.*` for all cross-mixin calls (no mixin-to-mixin imports), MRO composition in the facade, and `TYPE_CHECKING` for type hints. The `_combat_types.py` module already exports `DamageType`, `UnitState`, `Unit`, and `HexGrid` is in `_hex_grid.py` -- these can replace all 117 deferred `from .combat_engine import ...` statements with clean module-level imports.

**Primary recommendation:** Execute the extraction in the order specified in CONTEXT.md (AbilitiesBase first, then systems, then remaining sub-modules). AbilitiesBase extraction is the hard prerequisite and must be a standalone commit with benchmark gate before any other sub-module is created. The deferred import replacement (117 statements) should happen within each sub-module file as it is created, not as a separate pass.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Follow the file's existing section headers as the grouping basis
- Target 5-6 sub-module files total (base, systems, hero augments, alphabetical, cost tiers -- Claude decides whether alphabetical and cost-tier sections need further splitting based on LOC balance)
- Hero augment handlers get their own file (_abilities_hero_augments.py)
- All named special systems in one file (_abilities_systems.py): Immortal trait logic, Soulbound (Lucian/Senna), Ryze trait-dependent, Sylas trifold rotation, Shadow Isles soul collection, Tahm Kench glutton, Galio bench mechanic, T-HEX pilot system, Baron Nashor, Rift Herald
- Named passive abilities (Leona, Taric, Skarner, Xerath, Zilean, Mel, Sett, Brock) -- Claude decides whether they join systems file or get their own file, based on final LOC balance
- AbilitiesBase contains: __init__(self, engine), cast() dispatcher, all 8 helper methods (_get_var, _find_farthest_enemy, _find_nearest_enemy, _find_lowest_hp_enemy, _get_enemies_in_radius, _dash_to_position), _deal_damage, _apply_stun, and check_immortal_resurrection
- check_immortal_resurrection() moves to AbilitiesBase (public API called by combat engine belongs in base)
- Use mixin pattern matching Phase 11: _AbilitiesBaseMixin, other sub-modules as mixins, ChampionAbilities composes via MRO
- Switch deferred `from .combat_engine import DamageType/UnitState/etc.` to module-level `from ._combat_types import ...` in sub-modules
- Phase 11 already extracted DamageType, UnitState, Unit, etc. into _combat_types.py -- no circular import risk since _combat_types doesn't import champion_abilities
- This replaces 117 deferred import statements with clean module-level imports
- AbilitiesBase first (roadmap requirement, standalone commit + benchmark)
- Systems next (highest risk, cross-method audit needed per STATE.md concern)
- Remaining sub-modules after (hero augments, cost tiers, alphabetical)
- Claude decides benchmark gating frequency: strict per-extraction for high-risk, batched for simple extractions
- Facade target: under 250 LOC (likely ~50-80 based on Phase 11 pattern)
- No per-sub-module LOC limit -- sub-modules can be whatever size they naturally end up
- 5-6 files total is the target range

### Claude's Discretion
- Whether to split the alphabetical section (~2,100 LOC) into two files or keep as one
- Whether cost tiers (Cost 1-5, ~1,270 LOC) should be one file or split
- Where named passives land (systems file vs separate file) -- based on LOC balance
- Benchmark gating frequency for simple extractions (per-extraction vs batched)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SPLT-04 | `champion_abilities.py` (5.9k LOC) split into AbilitiesBase + systems + cost-tier mixin sub-modules | Full file structure analysis confirms clean section boundaries. LOC breakdown by section documented below. 117 deferred imports can be replaced with module-level imports from `_combat_types` and `_hex_grid`. External API surface is minimal (only `cast()` and `check_immortal_resurrection()` called from outside). |
| SPLT-05 | All splits maintain backward-compatible imports via facade re-exports | The facade pattern from Phase 11 applies directly: `from .champion_abilities import ChampionAbilities` must continue to work. combat_engine.py imports `ChampionAbilities` at line 51. No other external imports of sub-names exist. |
| SPLT-06 | Determinism benchmark passes after each individual combat_engine/champion_abilities split step | `python -m simulator.benchmark` is the determinism gate. It imports CombatEngine which instantiates ChampionAbilities. Each extraction step must preserve: (a) MRO method resolution order so `self._cast_X` dispatch works correctly, (b) the last-definition-wins semantics for 5 duplicate method names, (c) 238 `self.engine.*` calls that become `self.*` calls through MRO on base helper methods. |
| BNCH-01 | Cross-engine parity tests batched for reduced CI overhead | The CI workflow in `.github/workflows/test-coverage.yml` runs parity tests as a separate `parity-gate` job with `--parity-layered`, `--parity-focused`, and `--parity-gate` flags. Currently each parity layer runs independently. Batching means combining multiple parity invocations into a single benchmark run to reduce setup/teardown overhead. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib | 3.10+ | Module system, typing, dataclasses | All types and patterns used are stdlib |
| ruff | >=0.4 | Lint + format validation after each step | Project verification rule: `ruff check .` and `ruff format --check .` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | >=7 | Run existing tests to verify no regressions | After each extraction step |

### Alternatives Considered
None -- this is a structural refactor using only stdlib module mechanics. No new libraries needed.

## Architecture Patterns

### Recommended Project Structure (after split)
```
simulator/core/
  champion_abilities.py          # Facade: ChampionAbilities class (inherits N mixins), re-exports, <250 LOC
  _abilities_base.py             # _AbilitiesBaseMixin: __init__, cast(), 8 helpers, _deal_damage, _apply_stun, check_immortal_resurrection: ~190 LOC
  _abilities_systems.py          # _AbilitiesSystemsMixin: Immortal, Soulbound, Ryze, Sylas, Shadow Isles, Tahm Kench, Galio, T-HEX, Baron, Rift Herald + named passives: ~1,770 LOC
  _abilities_hero_augments.py    # _AbilitiesHeroAugmentsMixin: Xin Zhao, Rumble, Illaoi, Jhin, Viego hero augment handlers + tick dispatcher: ~385 LOC
  _abilities_alphabetical.py     # _AbilitiesAlphabeticalMixin: Main alphabetical champion handlers (aatrox through shyvana): ~2,095 LOC
  _abilities_cost_tiers.py       # _AbilitiesCostTiersMixin: Cost 1-5 champion abilities: ~1,270 LOC
```

### Pattern 1: Mixin Composition via MRO (established Phase 11)
**What:** ChampionAbilities class inherits from multiple mixin classes, each providing a subset of methods. Cross-method calls use `self.*` which resolves through Python MRO.
**When to use:** Every mixin file follows this pattern.
**Example:**
```python
# _abilities_base.py
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from ._combat_types import DamageType, UnitState
from ._hex_grid import HexGrid

if TYPE_CHECKING:
    from ._combat_types import Unit


class _AbilitiesBaseMixin:
    """Base mixin providing helpers, damage, stun, and dispatch for ChampionAbilities."""

    def __init__(self, engine: "CombatEngine"):
        self.engine = engine

    def cast(self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict) -> bool:
        handler = getattr(self, f"_cast_{unit.api_name.replace('TFT16_', '').lower()}", None)
        if handler:
            return handler(unit, enemies, allies, ability_vars)
        return False

    # ... helper methods ...
```

```python
# champion_abilities.py (facade)
from ._abilities_base import _AbilitiesBaseMixin
from ._abilities_systems import _AbilitiesSystemsMixin
from ._abilities_hero_augments import _AbilitiesHeroAugmentsMixin
from ._abilities_alphabetical import _AbilitiesAlphabeticalMixin
from ._abilities_cost_tiers import _AbilitiesCostTiersMixin


class ChampionAbilities(
    _AbilitiesCostTiersMixin,
    _AbilitiesAlphabeticalMixin,
    _AbilitiesHeroAugmentsMixin,
    _AbilitiesSystemsMixin,
    _AbilitiesBaseMixin,
):
    """Handler for champion-specific ability mechanics."""
    pass
```

### Pattern 2: Deferred Import Replacement
**What:** Replace 117 deferred `from .combat_engine import DamageType/UnitState/HexGrid` statements inside method bodies with module-level imports from `_combat_types` and `_hex_grid`.
**When to use:** In every sub-module file as it is created.
**Example:**
```python
# BEFORE (in champion_abilities.py):
def _cast_aatrox(self, unit, enemies, allies, ability_vars):
    from .combat_engine import DamageType  # deferred to avoid circular import
    ...

# AFTER (in _abilities_alphabetical.py):
from ._combat_types import DamageType  # module-level, no circular import risk
...
def _cast_aatrox(self, unit, enemies, allies, ability_vars):
    ...  # DamageType available at module level
```

### Pattern 3: Duplicate Method Resolution (CRITICAL)
**What:** champion_abilities.py has 5 methods defined twice (or three times): `_cast_diana` (lines 505, 1481), `_cast_leona` (lines 664, 1702, 3778), `_cast_skarner` (lines 2163, 3926), `_cast_xerath` (lines 2043, 3975), `_cast_zilean` (lines 2083, 4012). In Python, the last definition wins. The split must preserve this semantic.
**When to use:** During extraction of alphabetical and named-passives/systems sections.
**How to handle:**
- The LAST definition of each duplicate must be the one that is active after the split.
- MRO resolution: if `_cast_leona` exists in both `_AbilitiesAlphabeticalMixin` and `_AbilitiesSystemsMixin`, the leftmost class in MRO wins. The MRO order must be arranged so the named-passives/systems version (the later definition in the original file) takes precedence.
- **Simplest approach:** Only include the LAST (active) definition in the sub-modules. The earlier (dead) definitions are dead code and can be dropped during extraction.
- **Risk mitigation:** Verify that the duplicate earlier definitions are truly dead code by confirming they are overridden by the later definition in the same class.

### Anti-Patterns to Avoid
- **Mixin-to-mixin imports:** Do NOT import from one mixin file into another. All cross-method calls go through `self.*` resolved by MRO. This is the Phase 11 established pattern.
- **Forgetting `from __future__ import annotations`:** Each mixin file needs this for forward reference type hints.
- **Changing MRO without verifying duplicate resolution:** The 5 duplicate methods MUST resolve to the same active implementation as the original monolithic file.
- **Moving `self.engine.*` calls without understanding the pattern:** The `self.engine` attribute is set in `_AbilitiesBaseMixin.__init__()`. All 238 `self.engine.*` calls in sub-module methods will work because `self.engine` is an instance attribute set on the object.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Import resolution for `DamageType` etc. | New helper module or registry | Direct `from ._combat_types import DamageType` | _combat_types.py already exports everything needed; no circular import since it doesn't import champion_abilities |
| Cross-mixin method dispatch | Explicit delegation or registry | Python MRO via `self.*` calls | Phase 11 proved this works; Python MRO handles all dispatch automatically |
| Test for duplicate method resolution | Custom test harness | Single import + `getattr` check | `python -c "from simulator.core.champion_abilities import ChampionAbilities; ca = ChampionAbilities.__mro__; print('OK')"` validates MRO |

**Key insight:** The Phase 11 mixin pattern handles all complexity. No new infrastructure is needed.

## Common Pitfalls

### Pitfall 1: Duplicate Method Definitions Break After Split
**What goes wrong:** 5 methods are defined multiple times in the original file (`_cast_diana`, `_cast_leona`, `_cast_skarner`, `_cast_xerath`, `_cast_zilean`). If both definitions end up in different mixins, MRO determines which one is active, and it may differ from the original file's "last definition wins" behavior.
**Why it happens:** In a single class, later definitions shadow earlier ones. In MRO, the leftmost parent class wins.
**How to avoid:** Drop the earlier (dead) definitions during extraction. Only include the LAST definition of each duplicate in the appropriate sub-module. Verify with benchmark after extraction.
**Warning signs:** Benchmark producing different results after an extraction step; champions using wrong ability implementation.

### Pitfall 2: self.engine Not Initialized in Sub-module Methods
**What goes wrong:** Sub-module mixin methods call `self.engine.log_event()` etc., but `self.engine` is only set in `_AbilitiesBaseMixin.__init__()`.
**Why it happens:** If `__init__` is not properly called on the base mixin or MRO skips it.
**How to avoid:** `_AbilitiesBaseMixin` must be the rightmost parent in the MRO chain (same as Phase 11 pattern). Only `_AbilitiesBaseMixin` defines `__init__`; no other mixin should define `__init__`.
**Warning signs:** `AttributeError: 'ChampionAbilities' object has no attribute 'engine'` at runtime.

### Pitfall 3: Named Passives Have External-Facing API Methods
**What goes wrong:** Methods like `apply_leona_flat_dr()`, `apply_glutton_feeding()`, `assign_thex_pilot()`, `trigger_demacia_rally()`, `trigger_thex_death()`, `setup_baron_riftscourge()` etc. appear to be public API methods (no underscore prefix), suggesting they might be called from outside `ChampionAbilities`.
**Why it happens:** These methods were designed as hooks for the combat engine or game layer to call.
**How to avoid:** Verified during research: grep confirms NONE of these methods are called from outside `champion_abilities.py`. They are only called internally via `self.*`. This means they can safely move to any mixin without affecting external callers. The only two externally-called methods are `cast()` and `check_immortal_resurrection()` (called from `_combat_processing.py` line 245 and `_combat_actions.py` line 268 respectively).
**Warning signs:** If any external caller is added in the future, the facade would need to re-export or the calling code would need to go through `self.champion_abilities.*`.

### Pitfall 4: _hex_distance Helper Method Lost
**What goes wrong:** There is a private `_hex_distance()` method at line 1574 that delegates to `HexGrid.hex_distance()`. Some _cast_ methods call `self._hex_distance()` instead of importing HexGrid directly.
**Why it happens:** It was a convenience wrapper added in the alphabetical section.
**How to avoid:** Move `_hex_distance()` to `_AbilitiesBaseMixin` alongside the other helper methods (it's a helper like `_find_nearest_enemy`). All callers will resolve it through `self._hex_distance()` via MRO.
**Warning signs:** `AttributeError: '_AbilitiesAlphabeticalMixin' object has no attribute '_hex_distance'`.

### Pitfall 5: item_effects Import in _apply_stun
**What goes wrong:** `_apply_stun()` (line 126-144) contains a deferred `from .item_effects import get_item_data`. This is NOT a `_combat_types` import -- it's a cross-module import to `item_effects.py`.
**Why it happens:** `_apply_stun` needs item data to check Quicksilver and Titan's Resolve CC immunity.
**How to avoid:** Keep this as a deferred import inside the method body in `_abilities_base.py`. It cannot be module-level because `item_effects.py` may import from `combat_engine.py`, creating a circular import. The deferred import pattern is correct here.
**Warning signs:** `ImportError` or circular import at module load time.

## Code Examples

### Example 1: AbilitiesBase Mixin Structure
```python
# simulator/core/_abilities_base.py
"""Base mixin: dispatch, helpers, damage, stun, immortal resurrection."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from ._combat_types import DamageType, UnitState
from ._hex_grid import HexGrid

if TYPE_CHECKING:
    from ._combat_types import Unit


class _AbilitiesBaseMixin:
    """Base mixin providing cast dispatch, helpers, and common combat actions."""

    def __init__(self, engine):
        self.engine = engine

    def cast(self, unit: "Unit", enemies: List["Unit"], allies: List["Unit"], ability_vars: Dict) -> bool:
        handler = getattr(self, f"_cast_{unit.api_name.replace('TFT16_', '').lower()}", None)
        if handler:
            return handler(unit, enemies, allies, ability_vars)
        return False

    def _get_var(self, ability_vars: Dict, key: str, star_level: int, default: float = 0) -> float:
        # ... existing implementation ...

    def _find_farthest_enemy(self, unit, enemies, max_range=99):
        # Uses HexGrid directly (module-level import)
        ...

    def _find_nearest_enemy(self, unit, enemies):
        # Uses HexGrid directly
        ...

    def _find_lowest_hp_enemy(self, unit, enemies):
        ...

    def _get_enemies_in_radius(self, center, radius, enemies):
        # Uses HexGrid directly
        ...

    def _dash_to_position(self, unit, target_pos):
        # Uses HexGrid directly, calls self.engine.*
        ...

    def _hex_distance(self, pos1, pos2):
        return HexGrid.hex_distance(pos1, pos2)

    def _apply_stun(self, target, duration, source):
        from .item_effects import get_item_data  # KEEP deferred -- cross-module
        ...

    def _deal_damage(self, attacker, target, damage, damage_type, source, can_crit=True):
        ...

    def check_immortal_resurrection(self, unit):
        ...
```

### Example 2: Facade Structure
```python
# simulator/core/champion_abilities.py (facade, <250 LOC target)
"""
TFT Set 16 Champion Ability Implementations

Facade module -- all implementation lives in _abilities_*.py sub-modules.
"""

from ._abilities_base import _AbilitiesBaseMixin  # noqa: F401
from ._abilities_systems import _AbilitiesSystemsMixin  # noqa: F401
from ._abilities_hero_augments import _AbilitiesHeroAugmentsMixin  # noqa: F401
from ._abilities_alphabetical import _AbilitiesAlphabeticalMixin  # noqa: F401
from ._abilities_cost_tiers import _AbilitiesCostTiersMixin  # noqa: F401


class ChampionAbilities(
    _AbilitiesCostTiersMixin,
    _AbilitiesAlphabeticalMixin,
    _AbilitiesHeroAugmentsMixin,
    _AbilitiesSystemsMixin,
    _AbilitiesBaseMixin,
):
    """Handler for champion-specific ability mechanics."""
    pass
```

### Example 3: MRO Order Rationale
```python
# MRO: CostTiers, Alphabetical, HeroAugments, Systems, Base
# Base is RIGHTMOST -- resolved first in MRO for __init__ and helpers
# Systems is LEFT of Base -- its methods (including overriding _cast_leona etc.) take priority
# This matches the original file's "last definition wins" because the named passive sections
# come AFTER the alphabetical section in the original file.
#
# Verification: For _cast_leona, the active definition is at line 3778 (named passives section).
# In MRO, _AbilitiesSystemsMixin._cast_leona will shadow _AbilitiesAlphabeticalMixin._cast_leona.
# This preserves "last definition wins" semantics.
```

## File Structure Analysis

### LOC Breakdown by Section (verified from source)

| Section | Lines | LOC | Target Sub-module |
|---------|-------|-----|-------------------|
| Module header + class def + imports | 1-17 | 17 | Facade |
| `__init__` + `cast()` dispatcher | 18-36 | 19 | _abilities_base.py |
| HELPER METHODS (8 helpers + _deal_damage + _apply_stun) | 37-163 | 127 | _abilities_base.py |
| CHAMPION ABILITY HANDLERS (alphabetical) | 164-2258 | 2,095 | _abilities_alphabetical.py |
| IMMORTAL TRAIT | 2259-2281 | 23 | _abilities_base.py (per CONTEXT.md) |
| LUCIAN & SENNA Soulbound | 2282-2424 | 143 | _abilities_systems.py |
| RYZE Trait-Dependent | 2425-2648 | 224 | _abilities_systems.py |
| SYLAS Trifold | 2649-2793 | 145 | _abilities_systems.py |
| SHADOW ISLES Soul Collection | 2794-3098 | 305 | _abilities_systems.py |
| TAHM KENCH Glutton | 3099-3351 | 253 | _abilities_systems.py |
| GALIO Bench Mechanic | 3352-3449 | 98 | _abilities_systems.py |
| T-HEX Pilot System | 3450-3627 | 178 | _abilities_systems.py |
| BARON NASHOR | 3628-3728 | 101 | _abilities_systems.py |
| RIFT HERALD | 3729-3773 | 45 | _abilities_systems.py |
| LEONA Flat DR Passive | 3774-3822 | 49 | _abilities_systems.py (named passive) |
| TARIC Passive MR | 3823-3921 | 99 | _abilities_systems.py (named passive) |
| SKARNER Armor Aura | 3922-3970 | 49 | _abilities_systems.py (named passive) |
| XERATH Ascendant | 3971-4007 | 37 | _abilities_systems.py (named passive) |
| ZILEAN Time Bomb | 4008-4077 | 70 | _abilities_systems.py (named passive) |
| MEL Mana Drain | 4078-4140 | 63 | _abilities_systems.py (named passive) |
| SETT Show Stopper | 4141-4188 | 48 | _abilities_systems.py (named passive) |
| BROCK Seismic | 4189-4258 | 70 | _abilities_systems.py (named passive) |
| HERO AUGMENT HANDLERS | 4259-4643 | 385 | _abilities_hero_augments.py |
| COST 1 | 4644-4882 | 239 | _abilities_cost_tiers.py |
| COST 2 | 4883-5292 | 410 | _abilities_cost_tiers.py |
| COST 3 | 5293-5545 | 253 | _abilities_cost_tiers.py |
| COST 4 | 5546-5771 | 226 | _abilities_cost_tiers.py |
| COST 5 | 5772-5912 | 141 | _abilities_cost_tiers.py |

### Projected Sub-module Sizes

| File | LOC | Content |
|------|-----|---------|
| _abilities_base.py | ~190 | __init__, cast, 8 helpers, _hex_distance, _deal_damage, _apply_stun, check_immortal_resurrection |
| _abilities_systems.py | ~1,770 | 10 named systems + 8 named passives (Leona, Taric, Skarner, Xerath, Zilean, Mel, Sett, Brock) |
| _abilities_hero_augments.py | ~385 | Xin Zhao, Rumble, Illaoi, Jhin, Viego hero augments + tick dispatcher |
| _abilities_alphabetical.py | ~2,095 | 43 champion handlers (aatrox through shyvana) |
| _abilities_cost_tiers.py | ~1,270 | Cost 1-5 champion abilities |
| champion_abilities.py (facade) | ~30-50 | Imports + class definition |
| **Total** | **~5,740+** | All implementation + facade overhead |

### Discretion Recommendations

**Alphabetical section (~2,095 LOC): Keep as one file.** Splitting into two files adds complexity (deciding which champions go where) without meaningful benefit. 2,095 LOC is large but contains simple, repetitive `_cast_X` methods with no internal cross-references between them.

**Cost tiers (~1,270 LOC): Keep as one file.** Five small cost sections (239 + 410 + 253 + 226 + 141) are cohesive and have no cross-references. One file is cleaner than splitting by cost tier.

**Named passives: Include in _abilities_systems.py.** The 8 named passives total ~485 LOC. Adding them to systems (~1,285 LOC) brings it to ~1,770 LOC -- reasonable and keeps all "special mechanics" champions together. Creating a separate _abilities_passives.py for just 485 LOC adds a file without much value.

**Benchmark gating: Strict for base and systems, batched for the remaining three.** Base extraction is the hard prerequisite and must be individually gated. Systems extraction is highest risk (cross-method audit + duplicate resolution). The remaining three extractions (hero augments, alphabetical, cost tiers) are simple mechanical moves that can be batched with a single benchmark gate at the end.

**Total: 5 sub-modules + facade = 6 files.** This is within the 5-6 target range.

## Cross-Method Call Audit (Systems Section)

This audit addresses the STATE.md blocker: "Phase 12 risk: _abilities_systems.py cross-method call audit required before writing the file."

### self.engine.* calls in systems section (lines 2259-4258)

All 10 named systems + 8 named passives call `self.engine.*` for:
- `self.engine.log_event(...)` -- 53 calls (most frequent)
- `self.engine.apply_shield(...)` -- 8 calls
- `self.engine.heal_unit(...)` -- 7 calls
- `self.engine.apply_damage(...)` -- 6 calls
- `self.engine.trait_manager.*` -- 5 calls (in Ryze trait-dependent)
- `self.engine.units` -- 3 calls
- `self.engine.get_occupied_hexes()` -- 2 calls
- `self.engine.set_unit_position(...)` -- 2 calls
- `self.engine.time` -- 2 calls
- `self.engine.gain_mana(...)` -- 1 call
- `self.engine.champions` -- 1 call
- `self.engine.get_ability_vars(...)` -- 1 call (in process_hero_augment_ticks)

**Conclusion:** All `self.engine.*` calls work because `self.engine` is an instance attribute set in `_AbilitiesBaseMixin.__init__()`. No changes needed -- these calls resolve identically after the split.

### self._method_name() calls in systems section

Systems methods call these base helpers:
- `self._get_var(...)` -- frequent in all systems
- `self._deal_damage(...)` -- frequent in all systems
- `self._apply_stun(...)` -- in Soulbound, Sylas, Tahm Kench, Galio
- `self._find_nearest_enemy(...)` -- in Soulbound, Ryze, Sylas
- `self._find_farthest_enemy(...)` -- in Shadow Isles
- `self._get_enemies_in_radius(...)` -- in Tahm Kench, T-HEX, Baron
- `self._dash_to_position(...)` -- in T-HEX
- `self._hex_distance(...)` -- in Leona passive (named passives section)

**Conclusion:** All `self._method_name()` calls resolve through MRO to `_AbilitiesBaseMixin`. This works because `_AbilitiesBaseMixin` is the rightmost parent in the MRO chain, providing all these helpers.

### self._cast_X() cross-calls

One cross-_cast_ call found: `_cast_illaoi` calls itself recursively at line 4548 (within hero augments section, `check_illaoi_recast`). This is a self-recursive call, not a cross-module call, so it resolves through `self.*` without issue.

The `_soulbound_swap()` method (line 2375) is called by both `_cast_lucian()` and `_cast_senna()`, all within the systems section. No cross-module issue.

**Audit result: CLEAR.** No cross-method calls in the systems section require special handling. All calls resolve through `self.*` via MRO.

## Duplicate Method Disposition

| Method | Definitions (line #) | Active Definition | Where Active Goes | Dead Code Action |
|--------|---------------------|-------------------|-------------------|------------------|
| `_cast_diana` | 505 (alphabetical), 1481 (alphabetical) | 1481 (later in alphabetical) | _abilities_alphabetical.py | Drop line 505 definition |
| `_cast_leona` | 664 (alphabetical), 1702 (alphabetical), 3778 (named passive) | 3778 (named passive) | _abilities_systems.py | Drop lines 664 and 1702 definitions |
| `_cast_skarner` | 2163 (alphabetical), 3926 (named passive) | 3926 (named passive) | _abilities_systems.py | Drop line 2163 definition |
| `_cast_xerath` | 2043 (alphabetical), 3975 (named passive) | 3975 (named passive) | _abilities_systems.py | Drop line 2043 definition |
| `_cast_zilean` | 2083 (alphabetical), 4012 (named passive) | 4012 (named passive) | _abilities_systems.py | Drop line 2083 definition |

**Key insight:** The named passive section's `_cast_` methods are the active implementations for Leona, Skarner, Xerath, and Zilean. The alphabetical section's versions are dead code. During extraction, only include the active (last) definition. If both definitions end up in different mixins, MRO would need to resolve correctly, but dropping dead code is simpler and cleaner.

## External API Surface

Only TWO methods are called from outside `champion_abilities.py`:

| Method | Called From | Line |
|--------|------------|------|
| `cast()` | `_combat_processing.py` | 245 |
| `check_immortal_resurrection()` | `_combat_actions.py` | 268 |

Both are called via `self.champion_abilities.cast(...)` and `self.champion_abilities.check_immortal_resurrection(...)`. Both belong in `_AbilitiesBaseMixin` per CONTEXT.md.

The 13 other public-looking methods (e.g., `apply_leona_flat_dr`, `trigger_demacia_rally`, `assign_thex_pilot` etc.) have ZERO external callers. They are only referenced within `champion_abilities.py` itself.

## Import Replacement Map

### Current deferred imports (117 total)
| Import | Count | Replacement |
|--------|-------|-------------|
| `from .combat_engine import DamageType` | 78 | `from ._combat_types import DamageType` (module-level) |
| `from .combat_engine import DamageType, HexGrid` | 12 | `from ._combat_types import DamageType` + `from ._hex_grid import HexGrid` (module-level) |
| `from .combat_engine import DamageType, UnitState` | 10 | `from ._combat_types import DamageType, UnitState` (module-level) |
| `from .combat_engine import HexGrid` | 8 | `from ._hex_grid import HexGrid` (module-level) |
| `from .combat_engine import UnitState` | 8 | `from ._combat_types import UnitState` (module-level) |
| `from .combat_engine import CombatEngine, Unit` | 1 | `TYPE_CHECKING` block (stays deferred) |

### Exception: item_effects import
| Import | Location | Action |
|--------|----------|--------|
| `from .item_effects import get_item_data` | `_apply_stun()` in base | KEEP deferred (cross-module, potential circular) |

## BNCH-01: Cross-Engine Parity Batching

### Current CI Structure
The `parity-gate` job in `.github/workflows/test-coverage.yml` runs:
1. Parity helper tests (pytest)
2. Parity dump compactness regression (pytest)
3. Rust engine build + install
4. Rust-enabled combat regressions (pytest)
5. Full parity gate benchmark (`--parity-layered --parity-focused --parity-gate`)

### Batching Opportunity
The parity gate already runs as a single `python -m simulator.benchmark` invocation with combined `--parity-layered --parity-focused --parity-gate` flags. The engine is instantiated once and reused across layers. This is already batched at the invocation level.

The BNCH-01 requirement ("Cross-engine parity tests batched for reduced CI overhead") likely refers to ensuring the parity tests don't run redundantly across multiple CI jobs or multiple invocations. Currently the parity gate is a single job -- the implementation may involve:
1. Verifying the current single-invocation pattern is sufficient
2. Adding a `--batch-all` or similar flag if multiple parity invocations exist
3. Documenting the batched pattern for future maintainers

**Confidence: MEDIUM.** The exact intended scope of "batching" is somewhat ambiguous. The current CI already runs parity as a single invocation. Research suggests the implementation may be minimal (verification + documentation) or may involve consolidating test assertions.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=7 |
| Config file | Project root (pyproject.toml or pytest.ini) |
| Quick run command | `python -m pytest tests/test_combat_regressions.py -x -q` |
| Full suite command | `python -m pytest` |
| Benchmark command | `python -m simulator.benchmark` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SPLT-04 | champion_abilities.py split into sub-modules | smoke | `python -c "from simulator.core.champion_abilities import ChampionAbilities"` | N/A (CLI check) |
| SPLT-05 | Backward-compatible imports via facade | smoke | `python -c "from simulator.core.champion_abilities import ChampionAbilities"` | N/A (CLI check) |
| SPLT-06 | Determinism benchmark passes after each split step | integration | `python -m simulator.benchmark` | Yes: simulator/benchmark.py |
| BNCH-01 | Parity tests batched for CI overhead | integration | `python -m pytest tests/test_benchmark_parity_helpers.py -q` | Yes: tests/test_benchmark_parity_helpers.py |

### Sampling Rate
- **Per task commit:** `python -c "from simulator.core.champion_abilities import ChampionAbilities"` (import check) + `ruff check .` + `ruff format --check .`
- **Per wave merge / high-risk extraction:** `python -m simulator.benchmark` (determinism gate)
- **Phase gate:** Full suite green (`python -m pytest` + `python -m simulator.benchmark`)

### Wave 0 Gaps
None -- existing test infrastructure covers all phase requirements. No new test files needed; benchmark.py and existing tests are sufficient.

## Open Questions

1. **BNCH-01 exact scope**
   - What we know: CI already runs parity as a single invocation with combined flags. The requirement says "batched for reduced CI overhead."
   - What's unclear: Whether this means (a) verify current batching is sufficient, (b) add new batching capability to benchmark.py, or (c) consolidate multiple CI steps into fewer steps.
   - Recommendation: Start by verifying the current pattern satisfies the requirement. If additional batching is needed, add a `--batch-parity` convenience flag that combines all parity sub-commands. LOW risk.

2. **Dead code in alphabetical section**
   - What we know: 5 methods have earlier definitions that are overridden. The earlier definitions are dead code.
   - What's unclear: Whether these were intentional (progressive implementation) or accidental (copy-paste).
   - Recommendation: Drop dead code during extraction. Benchmark will confirm correctness.

## Sources

### Primary (HIGH confidence)
- Direct source code analysis of `simulator/core/champion_abilities.py` (5,911 LOC)
- Direct source code analysis of `simulator/core/combat_engine.py` (Phase 11 facade pattern)
- Direct source code analysis of `simulator/core/_combat_actions.py`, `_combat_runners.py`, `_combat_processing.py` (Phase 11 mixin pattern)
- Direct source code analysis of `simulator/core/_combat_types.py` (available exports)
- Direct source code analysis of `.github/workflows/test-coverage.yml` (CI parity gate)
- `grep` analysis of all external callers (238 `self.engine.*` calls, 2 external API calls, 117 deferred imports)

### Secondary (MEDIUM confidence)
- Phase 11 RESEARCH.md and 11-02-PLAN.md (mixin composition pattern documentation)
- CONTEXT.md decisions (user-locked split strategy)

### Tertiary (LOW confidence)
- BNCH-01 interpretation (ambiguous requirement, see Open Questions)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - stdlib only, no external dependencies
- Architecture: HIGH - directly replicates Phase 11 proven pattern, verified against source code
- Pitfalls: HIGH - all identified through direct code analysis (duplicate methods, import patterns, cross-method audit)
- BNCH-01: MEDIUM - requirement scope slightly ambiguous

**Research date:** 2026-03-02
**Valid until:** 2026-04-02 (stable domain, no external dependency drift risk)
