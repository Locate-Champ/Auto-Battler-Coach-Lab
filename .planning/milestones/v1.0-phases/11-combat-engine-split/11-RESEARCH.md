# Phase 11: Combat Engine Split - Research

**Researched:** 2026-03-02
**Domain:** Python module decomposition / large file split with determinism preservation
**Confidence:** HIGH

## Summary

Phase 11 splits `simulator/core/combat_engine.py` (5,312 LOC) into a CombatEngine facade plus 8 private sub-modules: `_combat_types.py`, `_hex_grid.py`, `_item_database.py`, `_augment_manager.py`, `_trait_manager.py`, `_combat_actions.py`, `_combat_processing.py`, and `_combat_runners.py`. The file's structure is well-segmented by comment banners and class boundaries, making mechanical extraction low-risk. The primary technical challenge is the CombatEngine mixin split (3 mixins from a 2,397 LOC class) where methods have dense cross-references to `self.*` attributes and other `self.*` methods.

Phase 10 established the exact pattern: underscore-prefixed sub-modules, facade re-exports with `# noqa: F401`, mixin composition for class method splitting, and class definition in the facade file (not sub-module) to preserve pickle/module identity. The .gitignore already whitelists `simulator/core/**`, and the CI allowlist uses prefix matching on `simulator/core/`, so no allowlist updates are needed.

**Primary recommendation:** Execute the 8-step extraction sequence exactly as specified in CONTEXT.md, with `python -m simulator.benchmark` as the hard gate after each commit. Start with zero-risk structural extractions (types, hex grid) and end with the CombatEngine mixin splits that carry the highest cross-reference complexity.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- `_combat_types.py`: All enums (DamageType, TargetingType, AbilityType, UnitState) + all dataclasses (CombatStats, Ability, Item, Buff, DotEffect, Unit) + helper functions (_star_val, _load_combat_data, _COMBAT_DATA_CACHE)
- `_hex_grid.py`: HexGrid class (standalone, no cross-dependencies)
- `_trait_manager.py`: TeamTraitState + TraitManager (~1,350 LOC kept as single file -- 30+ _apply_* methods are repetitive but cohesive)
- `_augment_manager.py`: AugmentManager class
- `_item_database.py`: ItemDatabase + AbilityDatabase (both are lookup factory classes)
- CombatEngine mixin split into 3 mixins:
  - `_combat_actions.py`: damage/heal/shield/CC/debuff methods (~12 methods)
  - `_combat_processing.py`: attack/ability/movement/tick (~8 methods)
  - `_combat_runners.py`: combat runners + round management + trait combat helpers (~12 methods)
- Facade keeps: __init__, create_unit, set_round_persistent_players, apply_item, _spawn_azir_soldiers, get_occupied_hexes, _invalidate_occupied_cache, set_unit_position, log_event, main(), and all re-exports
- TraitManager kept as one file (~1,350 LOC) -- no sub-splitting
- Extraction ordering: one sub-module per benchmark-gated commit, ordered by risk (lowest first): types -> hex_grid -> item_database -> augment_manager -> trait_manager -> combat_actions -> combat_processing -> combat_runners
- Benchmark gating: every extraction step is a standalone commit; `python -m simulator.benchmark` must pass with identical output before next extraction begins
- Import path preservation: facade re-exports all public names so `from simulator.core.combat_engine import X` continues to work
- Follow Phase 10 pattern: underscore-prefixed sub-modules with noqa: F401 facade re-exports

### Claude's Discretion
- Exact method assignment to mixins (may shift 1-2 methods between groups based on call-graph analysis)
- MRO ordering of mixin classes
- Whether main() stays in facade or moves to a separate entry point
- Internal import structure between sub-modules (who imports from whom)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SPLT-03 | `combat_engine.py` (5.3k LOC) split into facade + types, hex grid, trait manager, augment manager, item database sub-modules | Full file structure analysis confirms clean section boundaries at lines 105 (types), 335 (hex grid), 504 (trait manager), 1881 (augment manager), 2484 (item/ability database), 2735 (CombatEngine class). Module-level imports/caches need to move with their consumers. |
| SPLT-06 | Determinism benchmark passes after each individual combat_engine/champion_abilities split step | `python -m simulator.benchmark` is the determinism gate. It imports `CombatEngine` from `simulator.core.combat_engine` and runs fixed-seed combats verifying identical output. Each extraction step must preserve: (a) all public names on the facade, (b) module-level side effects like `HexGrid._build_luts()`, (c) RNG call ordering in combat methods. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib | 3.10+ | Module system, dataclasses, enum, typing | All types and patterns used in combat_engine.py are stdlib |
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
  combat_engine.py          # Facade: CombatEngine class (inherits 3 mixins), re-exports, ~700-800 LOC
  _combat_types.py          # Enums, dataclasses, helpers: ~330 LOC
  _hex_grid.py              # HexGrid class: ~165 LOC
  _trait_manager.py         # TeamTraitState + TraitManager: ~1,380 LOC
  _augment_manager.py       # AugmentManager + module-level augment loading: ~605 LOC
  _item_database.py         # ItemDatabase + AbilityDatabase + module-level item loading: ~250 LOC
  _combat_actions.py        # _CombatActionsMixin: damage/heal/shield/CC methods: ~520 LOC
  _combat_processing.py     # _CombatProcessingMixin: attack/ability/movement/tick: ~520 LOC
  _combat_runners.py        # _CombatRunnersMixin: run_combat, simulate_1v1, round mgmt: ~600 LOC
  champion_abilities.py     # Unchanged (Phase 12)
  item_effects.py           # Unchanged
```

### Pattern 1: Facade Re-export (established Phase 10)
**What:** Original file becomes a thin facade that imports from sub-modules and re-exports all public names.
**When to use:** Every extraction step.
**Example:**
```python
# combat_engine.py (facade)
from ._combat_types import (  # noqa: F401
    AbilityType,
    CombatStats,
    DamageType,
    DotEffect,
    HexGrid,  # NOTE: HexGrid re-exported even though in _hex_grid.py
    Item,
    TargetingType,
    Unit,
    UnitState,
    _COMBAT_DATA_CACHE,
    _load_combat_data,
    _star_val,
)
from ._hex_grid import HexGrid  # noqa: F401
# ... etc
```

### Pattern 2: Mixin Composition (established Phase 10-02)
**What:** CombatEngine class methods split into mixin classes. The actual CombatEngine class is defined in the facade file inheriting all mixins.
**When to use:** Steps 6-8 (CombatEngine method extraction).
**Example:**
```python
# combat_engine.py (facade)
from ._combat_actions import _CombatActionsMixin
from ._combat_processing import _CombatProcessingMixin
from ._combat_runners import _CombatRunnersMixin

class CombatEngine(_CombatActionsMixin, _CombatProcessingMixin, _CombatRunnersMixin):
    """TFT Combat Simulation Engine v2."""
    # __init__, create_unit, apply_item, etc. stay here
    ...
```

### Pattern 3: Module-level Side Effects Must Travel with Host
**What:** Module-level code like `HexGrid._build_luts()` and the augment/item data loading blocks must move to the same sub-module as their class. The facade imports trigger the sub-module, which runs the side effects.
**When to use:** Steps 2 (_hex_grid.py), 3 (_item_database.py), 4 (_augment_manager.py).
**Example:** `HexGrid._build_luts()` at line 495 must move to `_hex_grid.py` after the HexGrid class definition.

### Anti-Patterns to Avoid
- **Changing import paths in callers:** All 100+ deferred `from .combat_engine import X` statements in champion_abilities.py and item_effects.py MUST continue to resolve through the facade. Never update caller imports.
- **Splitting TraitManager:** The 30+ `_apply_*` methods are repetitive followers of the same pattern. Sub-splitting by region/class/pair would scatter related logic for marginal benefit.
- **Moving CombatEngine class to a sub-module:** The class definition must stay in `combat_engine.py` to preserve `__module__` identity for any serialization/introspection code.
- **Importing between mixins:** Each mixin should only reference `self.*` and type imports. Do NOT import one mixin from another -- method resolution happens through the composed class.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Re-export management | Manual __all__ lists | `# noqa: F401` on re-export imports | Matches Phase 10 pattern, ruff respects it |
| Module-level cache sharing | Passing caches between modules | Import the sub-module's cache variable | `_COMBAT_DATA_CACHE` dict is mutable; importing it shares the reference |
| Mixin method dispatch | Complex delegation/proxy pattern | Python MRO with simple inheritance | Established in Phase 10-02; Python handles method lookup automatically |

**Key insight:** This is purely structural -- no behavioral changes. The Python import system and MRO handle all the complexity. The only real work is cutting code along clean boundaries and verifying determinism.

## Common Pitfalls

### Pitfall 1: Module-level code ordering
**What goes wrong:** Moving `_COMBAT_DATA_CACHE` to `_combat_types.py` but leaving `_load_combat_data` in the facade creates an import-time error because `_load_combat_data` references `_COMBAT_DATA_CACHE`.
**Why it happens:** Module-level globals and functions that reference each other must move together.
**How to avoid:** Move `_COMBAT_DATA_CACHE`, `_load_combat_data`, and `_star_val` together to `_combat_types.py` as a unit. They share no dependencies outside stdlib.
**Warning signs:** `NameError` at import time.

### Pitfall 2: HexGrid._build_luts() call timing
**What goes wrong:** If `HexGrid._build_luts()` is not called at import time of the sub-module, distance lookups will fail with KeyError during combat.
**Why it happens:** The call at line 495 (`HexGrid._build_luts()`) is at module scope -- it runs when `combat_engine.py` is first imported. After moving HexGrid to `_hex_grid.py`, this call must be at the module level of `_hex_grid.py`.
**How to avoid:** Place `HexGrid._build_luts()` immediately after the class definition in `_hex_grid.py`.
**Warning signs:** Benchmark fails with `KeyError` in `HexGrid._DISTANCE_LUT`.

### Pitfall 3: Augment/item module-level try/except blocks
**What goes wrong:** The augment data loading block (lines 1886-1898) and item import block (lines 2489-2515) use module-level try/except to set `_AUGMENTS_LOADED` and `_ITEMS_LOADED` flags. If these move to sub-modules but the flags are referenced elsewhere in the facade, you get `NameError`.
**Why it happens:** Module-level flags are consumed by the class methods in the same file. When the class stays in the facade but the flags move to a sub-module, the facade must re-import them.
**How to avoid:** Move the entire try/except block plus the flag variables to the sub-module. In the facade, import the flags if needed, or better yet, let the sub-module's class reference its own module-level flags.
**Warning signs:** `NameError: _AUGMENTS_LOADED is not defined` at runtime.

### Pitfall 4: Mixin self-reference to methods in other mixins
**What goes wrong:** `_CombatProcessingMixin.process_attack()` calls `self.calculate_damage()`, `self.apply_damage()`, `self.heal_unit()`, and `self.gain_mana()` -- all of which are in `_CombatActionsMixin`. If the mixin is tested in isolation, these calls fail.
**Why it happens:** Mixins are designed to be composed, not standalone. Methods freely call other methods via `self`.
**How to avoid:** Do NOT try to make mixins independently testable. Test only through the composed `CombatEngine` class. Ensure MRO order puts actions before processing before runners.
**Warning signs:** `AttributeError: _CombatProcessingMixin object has no attribute 'calculate_damage'`.

### Pitfall 5: RNG call ordering drift
**What goes wrong:** The benchmark checks deterministic output using fixed seeds. If the extraction accidentally reorders method definitions or changes import-time side effects that consume RNG, output changes.
**Why it happens:** Moving code between files can subtly change execution order if module-level code consumes RNG (it doesn't here, but moving `random.choice` calls in `process_round_start` to a different module could theoretically affect import order).
**How to avoid:** Never change method bodies during extraction. Copy-paste exactly. Run benchmark after EVERY step.
**Warning signs:** Benchmark outputs differ despite no logical change.

### Pitfall 6: Circular imports between sub-modules
**What goes wrong:** `_combat_types.py` defines `Unit`, `_hex_grid.py` uses `Unit` in type hints, and `_combat_types.py` imports `HexGrid` for type hints. This creates a circular import.
**Why it happens:** The original file has everything in one namespace. Splitting introduces import edges.
**How to avoid:** Use `TYPE_CHECKING` imports for type hints. In `_hex_grid.py`, use `from __future__ import annotations` and `if TYPE_CHECKING: from ._combat_types import Unit`. In practice, HexGrid has NO runtime dependency on Unit or other types -- its methods use only tuples and ints. The `_combat_types.py` module references `DamageType` in `DotEffect` but `DamageType` is defined in the same file, so no issue.
**Warning signs:** `ImportError: cannot import name 'X' from partially initialized module`.

## Code Examples

### Example 1: _combat_types.py structure
```python
# simulator/core/_combat_types.py
"""Combat type definitions: enums, dataclasses, and helper functions."""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# Module-level cache for combat data
_COMBAT_DATA_CACHE: Dict[str, Any] = {}


def _load_combat_data(path: Path) -> dict:
    """Load combat data from JSON, using module-level cache."""
    key = str(path)
    if key not in _COMBAT_DATA_CACHE:
        if not path.is_file():
            raise FileNotFoundError(...)
        with open(path, "r", encoding="utf-8") as f:
            _COMBAT_DATA_CACHE[key] = json.load(f)
    return _COMBAT_DATA_CACHE[key]


def _star_val(var_data, star_level: int, default=0):
    ...


class DamageType(Enum):
    ...

# ... all enums and dataclasses ...

class Unit:
    ...
```

### Example 2: Facade re-export pattern with mixins
```python
# simulator/core/combat_engine.py (facade, after all 8 steps)
"""TFT Combat Simulator Engine v2 - Facade."""

from ._combat_types import (  # noqa: F401
    Ability,
    AbilityType,
    Buff,
    CombatStats,
    DamageType,
    DotEffect,
    Item,
    TargetingType,
    Unit,
    UnitState,
    _COMBAT_DATA_CACHE,
    _load_combat_data,
    _star_val,
)
from ._hex_grid import HexGrid  # noqa: F401
from ._trait_manager import TeamTraitState, TraitManager  # noqa: F401
from ._augment_manager import AugmentManager  # noqa: F401
from ._item_database import AbilityDatabase, ItemDatabase  # noqa: F401
from ._combat_actions import _CombatActionsMixin
from ._combat_processing import _CombatProcessingMixin
from ._combat_runners import _CombatRunnersMixin

# ... module-level imports for ChampionAbilities, combat_fast, item_effects ...


class CombatEngine(_CombatRunnersMixin, _CombatProcessingMixin, _CombatActionsMixin):
    """TFT Combat Simulation Engine v2."""

    # Game constants
    HEX_SIZE = 180
    MANA_PER_ATTACK_BY_ROLE = { ... }
    # ... other class constants ...

    def __init__(self, combat_data_path=None, logging_enabled=True):
        ...

    def create_unit(self, api_name, star_level, position, team, items=None, instance_id=""):
        ...

    def set_round_persistent_players(self, team0_player=None, team1_player=None):
        ...

    def apply_item(self, unit, item):
        ...

    def _spawn_azir_soldiers(self, team, team_id, positions=None):
        ...

    def get_occupied_hexes(self):
        ...

    def _invalidate_occupied_cache(self):
        ...

    def set_unit_position(self, unit, new_pos):
        ...

    def log_event(self, event_type, **kwargs):
        ...


def main():
    ...

if __name__ == "__main__":
    main()
```

### Example 3: Mixin sub-module structure
```python
# simulator/core/_combat_actions.py
"""Combat action methods: damage, heal, shield, CC, debuffs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from ._combat_types import DamageType, DotEffect, Unit

from ._combat_types import DamageType, DotEffect, UnitState
from ._hex_grid import HexGrid


class _CombatActionsMixin:
    """Mixin providing damage/heal/shield/CC methods for CombatEngine."""

    def calculate_damage(self, attacker, defender, base_damage, damage_type, can_crit=True, is_ability=False):
        ...

    def apply_damage(self, attacker, defender, damage, damage_type, source="attack"):
        ...

    def heal_unit(self, unit, amount, source="heal"):
        ...

    # ... remaining action methods ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single monolithic file with all types + classes + engine | Facade + private sub-modules with mixin composition | Phase 10 (2026-02-28) established pattern | Code navigability, IDE support, git blame granularity |

## Detailed File Structure Analysis

### Current combat_engine.py section boundaries (verified)
| Section | Lines | LOC | Target Sub-module |
|---------|-------|-----|-------------------|
| Module imports + _COMBAT_DATA_CACHE + _load_combat_data + _star_val | 1-98 | ~98 | `_combat_types.py` (helpers) |
| Enums: DamageType, TargetingType, AbilityType, UnitState | 100-144 | ~45 | `_combat_types.py` |
| Dataclasses: CombatStats, Ability, Item, Buff, DotEffect, Unit | 146-329 | ~184 | `_combat_types.py` |
| HexGrid class + _build_luts() call | 330-496 | ~167 | `_hex_grid.py` |
| TeamTraitState + TraitManager | 498-1879 | ~1,382 | `_trait_manager.py` |
| Augment loading block + AugmentManager | 1881-2482 | ~602 | `_augment_manager.py` |
| Item loading block + ItemDatabase + AbilityDatabase | 2484-2728 | ~245 | `_item_database.py` |
| CombatEngine class | 2730-5131 | ~2,402 | Facade + 3 mixins |
| main() | 5133-5312 | ~180 | Facade (stays) |

### CombatEngine method assignment to mixins (verified via call-graph)
| Method | Line | Mixin | Cross-calls to |
|--------|------|-------|----------------|
| calculate_damage | 3029 | _combat_actions | HexGrid (static) |
| check_hp_threshold_effects | 3116 | _combat_actions | self.heal_unit, self.log_event |
| gain_mana | 3187 | _combat_actions | (none) |
| apply_damage | 3203 | _combat_actions | self.heal_unit, self.gain_mana, self.log_event, self.check_hp_threshold_effects, self.trait_manager |
| heal_unit | 3369 | _combat_actions | self.log_event |
| apply_shield | 3392 | _combat_actions | self.log_event |
| apply_burn | 3406 | _combat_actions | self.log_event |
| apply_cc | 3434 | _combat_actions | self.log_event |
| apply_wound | 3485 | _combat_actions | self.log_event |
| apply_sunder | 3495 | _combat_actions | self.log_event |
| apply_shred | 3519 | _combat_actions | self.log_event |
| find_target | 3548 | _combat_processing | HexGrid (static) |
| get_enemies_in_range | 3616 | _combat_processing | HexGrid (static) |
| can_attack | 3631 | _combat_processing | HexGrid (static) |
| process_attack | 3635 | _combat_processing | self.calculate_damage, self.apply_damage, self.gain_mana, self.log_event |
| _post_ability_cast | 3736 | _combat_processing | self.calculate_damage, self.apply_damage |
| cast_ability | 3758 | _combat_processing | self.find_target, self.calculate_damage, self.apply_damage, self.heal_unit, self.apply_shield, self._post_ability_cast, self.log_event, self.get_enemies_in_range, self.set_unit_position, self.get_occupied_hexes |
| move_unit_towards | 4011 | _combat_processing | self.set_unit_position, self.get_occupied_hexes, self.log_event |
| process_unit_tick | 4027 | _combat_processing | self.find_target, self.can_attack, self.process_attack, self.cast_ability, self.move_unit_towards, self.heal_unit, self.log_event, self.get_occupied_hexes, self.set_unit_position |
| tick | 4271 | _combat_runners | self.apply_damage, self.log_event, self._fire_piltover_module, self._check_noxus_atakhan_summon, self._check_atakhan_ruin, self.process_unit_tick |
| _fire_piltover_module | 4370 | _combat_runners | self.apply_shield, self.apply_damage, self.log_event |
| _check_noxus_atakhan_summon | 4449 | _combat_runners | self._summon_atakhan |
| _summon_atakhan | 4489 | _combat_runners | self._find_atakhan_spawn, self._invalidate_occupied_cache, self.log_event |
| _find_atakhan_spawn | 4586 | _combat_runners | (none) |
| _check_atakhan_ruin | 4609 | _combat_runners | self.log_event |
| _count_traits | 4640 | _combat_runners | (none) |
| process_round_start | 4655 | _combat_runners | self.log_event, self.trait_manager |
| _apply_combat_start_items | 4709 | _combat_runners | (none, delegates to item_effects) |
| run_combat | 4725 | _combat_runners | self.process_round_start, self._count_traits, self.trait_manager, self.augment_manager, self._apply_combat_start_items, self.tick |
| _next_event_dt | 4867 | _combat_runners | (reads self._piltover_data) |
| run_combat_adaptive_tick | 4920 | _combat_runners | same as run_combat + self._next_event_dt, self.tick |
| simulate_1v1 | 5058 | _combat_runners | self.create_unit, self.run_combat |

### Complete list of names requiring facade re-export
External callers import these names from `simulator.core.combat_engine`:

| Name | Used by | Source sub-module |
|------|---------|-------------------|
| CombatEngine | benchmark.py, batch_simulator.py, engine_wrapper.py, game.py, coach/scoring/combat.py, tests | facade (class defined here) |
| DamageType | champion_abilities.py (~100 sites), item_effects.py (~30 sites), test_combat_regressions.py | _combat_types.py |
| HexGrid | champion_abilities.py (~15 sites), item_effects.py (~12 sites) | _hex_grid.py |
| Unit | champion_abilities.py, item_effects.py | _combat_types.py |
| UnitState | champion_abilities.py, item_effects.py | _combat_types.py |
| DotEffect | item_effects.py (2 sites) | _combat_types.py |
| Item | test_combat_regressions.py | _combat_types.py |
| CombatStats | (internal use, safe to re-export) | _combat_types.py |
| Ability | (internal use) | _combat_types.py |
| AbilityType | (internal use) | _combat_types.py |
| TargetingType | (internal use) | _combat_types.py |
| Buff | (internal use) | _combat_types.py |
| _star_val | (internal use) | _combat_types.py |
| _load_combat_data | (internal use) | _combat_types.py |
| _COMBAT_DATA_CACHE | (internal use) | _combat_types.py |
| TeamTraitState | (internal use) | _trait_manager.py |
| TraitManager | (internal use) | _trait_manager.py |
| AugmentManager | (internal use) | _augment_manager.py |
| ItemDatabase | (internal use, also used in main()) | _item_database.py |
| AbilityDatabase | (internal use) | _item_database.py |

### Module-level side effects that must migrate with their classes
1. `HexGrid._build_luts()` (line 495) -> must be at module level in `_hex_grid.py`
2. Augment data loading try/except block (lines 1886-1898, sets `_AUGMENTS_DATA`, `_AUGMENTS_LOADED`, `_RAW_AUGMENTS`) -> must move to `_augment_manager.py`
3. Item import try/except block (lines 2489-2515, sets `_ITEMS_LOADED`, `ALL_ITEMS`, etc.) -> must move to `_item_database.py`
4. `_COMBAT_DATA_CACHE` dict (line 64) -> must move to `_combat_types.py` with `_load_combat_data`
5. ChampionAbilities import (lines 26-31) -> stays in facade (used only by CombatEngine.__init__)
6. Cython combat_fast import (lines 35-43) -> stays in facade or moves to `_combat_actions.py` (used only by calculate_damage)
7. Item effects import (lines 47-61) -> stays in facade (used only by CombatEngine apply_item and process_attack)

### Import dependency graph between sub-modules
```
_combat_types.py  <- standalone (only stdlib)
_hex_grid.py      <- standalone (only stdlib + heapq)
_trait_manager.py <- imports _combat_types (UnitState, for check_freljord_on_death)
_augment_manager.py <- imports _combat_types (for type hints), _hex_grid (HexGrid.hex_distance in apply_hex_effects)
_item_database.py <- imports _combat_types (Item, Ability, DamageType, etc.)
_combat_actions.py <- imports _combat_types (DamageType, DotEffect, UnitState, Unit), _hex_grid (HexGrid)
_combat_processing.py <- imports _combat_types (DamageType, UnitState, Unit, _star_val), _hex_grid (HexGrid)
_combat_runners.py <- imports _combat_types (CombatStats, Ability, Unit, UnitState, DamageType, _star_val, _load_combat_data), _hex_grid (HexGrid)
combat_engine.py (facade) <- imports all sub-modules
```
No circular dependencies in this graph.

### MRO Recommendation
```python
class CombatEngine(_CombatRunnersMixin, _CombatProcessingMixin, _CombatActionsMixin):
```
Rationale: Actions are the lowest-level primitives (damage, heal). Processing calls actions. Runners call processing. MRO resolves right-to-left in Python, so actions should be rightmost (resolved first for shared method names, though none overlap).

### Cython import placement
`_cy_calculate_damage` and `_CYTHON_OK` are used ONLY in `calculate_damage()` (line 3029). Two options:
1. Move to `_combat_actions.py` (where calculate_damage lives) -- cleaner locality
2. Keep in facade and pass through -- more import complexity

**Recommendation:** Move the Cython import try/except to `_combat_actions.py` since it is the sole consumer. This avoids the facade needing to import and pass the Cython function.

### Item effects import placement
`_get_item_on_hit`, `_get_item_on_damage_dealt`, etc. are used in:
- `ItemDatabase.create_item()` (in `_item_database.py`)
- `CombatEngine.process_attack()` (in `_combat_processing.py`, but via `item.on_hit` callback -- the function refs are already stored on Item objects)

The module-level import (lines 47-61) can move to `_item_database.py` since that's where `ItemDatabase.create_item()` uses them. The CombatEngine methods only call `item.on_hit(self, ...)` which is already bound to the Item instance.

**However:** `_ITEM_EFFECTS_LOADED` flag is also referenced by `TraitManager.assign_piltover_modules()` at line 562. This means:
- Either `_item_database.py` exports `_ITEM_EFFECTS_LOADED` and `_trait_manager.py` imports it
- Or the flag stays as a module-level sentinel in `_item_database.py` and TraitManager checks it

**Recommendation:** Move the item_effects import block to `_item_database.py` and export `_ITEM_EFFECTS_LOADED`. TraitManager imports it from `_item_database.py`. Alternatively, TraitManager can check `_ITEMS_LOADED` instead (which is about set16_items, not item_effects) -- need to verify the actual check. Looking at line 562: `if not _ITEMS_LOADED:` -- this checks the set16_items import, not item_effects. So the `_ITEMS_LOADED` flag (from the set16_items import block) must be accessible to TraitManager. Since both are in the `_item_database.py` module, TraitManager would import it from there.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (already configured) |
| Config file | pyproject.toml |
| Quick run command | `python -m pytest tests/test_combat_regressions.py tests/test_occupied_hex_cache.py -x` |
| Full suite command | `python -m pytest` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SPLT-03 | All public names importable from facade | smoke | `python -c "from simulator.core.combat_engine import CombatEngine, DamageType, HexGrid, Unit, UnitState, DotEffect, Item"` | N/A (inline) |
| SPLT-03 | Sub-modules independently importable | smoke | `python -c "from simulator.core._combat_types import DamageType; from simulator.core._hex_grid import HexGrid"` | N/A (inline) |
| SPLT-03 | Existing tests pass unchanged | unit | `python -m pytest tests/test_combat_regressions.py tests/test_occupied_hex_cache.py tests/test_unlock_game_integration.py -x` | Yes |
| SPLT-06 | Determinism benchmark passes after each step | integration | `python -m simulator.benchmark` | Yes (simulator/benchmark.py) |
| SPLT-06 | Ruff clean after each step | lint | `ruff check . && ruff format --check .` | N/A (tool) |

### Sampling Rate
- **Per extraction commit:** `python -m simulator.benchmark` (hard gate) + `ruff check . && ruff format --check .` + `python -m pytest tests/test_combat_regressions.py tests/test_occupied_hex_cache.py -x`
- **After all 8 steps:** `python -m pytest` (full suite)
- **Phase gate:** Full suite green + benchmark passes

### Wave 0 Gaps
None -- existing test infrastructure covers all phase requirements. The benchmark is the primary determinism gate, and existing unit tests cover import paths and combat correctness.

## Open Questions

1. **main() placement**
   - What we know: main() is a demo function at the bottom of combat_engine.py (180 LOC). It references CombatEngine, ItemDatabase, and print statements.
   - What's unclear: Whether it should stay in the facade or move elsewhere.
   - Recommendation: Keep main() in the facade. It is the `__main__` entry point for `python -m simulator.core.combat_engine` and references CombatEngine which is defined in the facade. Moving it would add complexity for no benefit.

2. **Exact boundary for find_target / get_enemies_in_range / can_attack**
   - What we know: These are used by process_attack and cast_ability (both in _combat_processing). They are also conceptually "targeting" utilities.
   - What's unclear: CONTEXT.md lists them as "processing" methods. They could also be in "actions" since they are utility methods.
   - Recommendation: Keep in _combat_processing per CONTEXT.md. They are called from process_attack/cast_ability/process_unit_tick, all of which are in processing.

## Sources

### Primary (HIGH confidence)
- Direct analysis of `simulator/core/combat_engine.py` (5,312 LOC, read in full)
- Direct analysis of Phase 10 plans and patterns (`10-01-PLAN.md`, `10-02-PLAN.md`)
- Direct analysis of `models/feature_engineering.py` facade pattern
- Grep of all import sites across the codebase (100+ `from .combat_engine import` in champion_abilities.py and item_effects.py)
- `.gitignore` whitelist analysis confirming `simulator/core/**` is tracked

### Secondary (MEDIUM confidence)
- Phase 10 STATE.md decisions on MRO ordering and pickle __module__ preservation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new libraries, pure Python module mechanics
- Architecture: HIGH - established Phase 10 pattern, verified against actual file structure
- Pitfalls: HIGH - all pitfalls identified from direct code analysis and Phase 10 experience

**Research date:** 2026-03-02
**Valid until:** 2026-04-01 (stable -- no external dependencies to become stale)
