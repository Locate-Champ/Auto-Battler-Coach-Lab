# Architecture Research

**Domain:** Safe monolithic Python module splitting — deterministic combat simulator
**Researched:** 2026-02-27
**Confidence:** HIGH (based on direct codebase inspection + verified Python packaging patterns)

---

## Standard Architecture

### System Overview

The four files targeted for splitting fall into two categories with very different risk profiles:

```
SIMULATOR CORE (HIGH RISK — determinism-critical)
┌──────────────────────────────────────────────────────────────┐
│  simulator/core/combat_engine.py  (5306 LOC)                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ Data Models  │  │ Grid/Traits/ │  │  CombatEngine    │   │
│  │ Unit,Stats,  │  │ Augment/Item │  │  run_combat()    │   │
│  │ Buff,Ability │  │ Databases    │  │  tick()          │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
│           ↑ imported by champion_abilities.py                 │
│  simulator/core/champion_abilities.py  (5911 LOC)            │
│  ┌──────────┐  ┌───────────┐  ┌──────────────────────────┐  │
│  │ Helpers  │  │ Handlers  │  │ Special Systems          │  │
│  │ _deal_   │  │ _cast_    │  │ Immortal, Soulbound,     │  │
│  │ _damage  │  │ (by cost) │  │ Ryze, Tahm Kench, T-Hex  │  │
│  └──────────┘  └───────────┘  └──────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘

INFRASTRUCTURE (LOWER RISK — no determinism dependency)
┌──────────────────────────────────────────────────────────────┐
│  simulator/cloud_runner.py  (2048 LOC)                        │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  │
│  │ Utilities &    │  │ StreamingWriter │  │ run_batch()    │  │
│  │ preflight fns  │  │ (output/S3)    │  │ + main() CLI   │  │
│  │ (1-469)        │  │ (470-986)      │  │ (987-2048)     │  │
│  └────────────────┘  └────────────────┘  └────────────────┘  │
│                                                               │
│  models/feature_engineering.py  (2100 LOC)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │ Config &     │  │ Reference    │  │ TFTFeatureEngineer │  │
│  │ constants    │  │ data loaders │  │ (transform/batch)  │  │
│  └──────────────┘  └──────────────┘  └────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### Component Responsibilities (Current vs Post-Split)

| File | Current LOC | Post-Split Target Files | Each LOC |
|------|-------------|-------------------------|----------|
| `combat_engine.py` | 5306 | `_combat_types.py` + `_hex_grid.py` + `_trait_manager.py` + `_augment_manager.py` + `_item_database.py` + `combat_engine.py` | 150–500 each |
| `champion_abilities.py` | 5911 | `_abilities_base.py` + `_abilities_cost1.py` + `_abilities_cost2.py` + `_abilities_cost3.py` + `_abilities_cost4.py` + `_abilities_cost5.py` + `_abilities_systems.py` + `champion_abilities.py` | 200–700 each |
| `cloud_runner.py` | 2048 | `_runner_utils.py` + `_runner_writer.py` + `cloud_runner.py` | 400–700 each |
| `feature_engineering.py` | 2100 | `_fe_config.py` + `_fe_loaders.py` + `_fe_transforms.py` + `feature_engineering.py` | 150–600 each |

---

## Recommended Project Structure (Post-Split)

```
simulator/core/
├── combat_engine.py          # CombatEngine class only (~700 LOC)
├── _combat_types.py          # Enums + dataclasses (DamageType, Unit, Buff, etc.) (~300 LOC)
├── _hex_grid.py              # HexGrid class only (~200 LOC)
├── _trait_manager.py         # TeamTraitState + TraitManager (~700 LOC)
├── _augment_manager.py       # AugmentManager class (~600 LOC)
├── _item_database.py         # ItemDatabase + AbilityDatabase (~250 LOC)
├── champion_abilities.py     # ChampionAbilities (dispatch + helpers only) (~200 LOC)
├── _abilities_base.py        # Shared helper methods for ability handlers (~170 LOC)
├── _abilities_systems.py     # Special systems: Immortal, Soulbound, Ryze, Sylas,
│                             #   Tahm Kench, Galio, T-Hex, Hero Augments (~1800 LOC)
├── _abilities_cost1.py       # Cost 1 handlers: anivia, blitzcrank, briar... (~350 LOC)
├── _abilities_cost2.py       # Cost 2 handlers: ashe, cho'gath, ekko... (~500 LOC)
├── _abilities_cost3.py       # Cost 3 handlers: ahri, drMundo, jinx... (~400 LOC)
├── _abilities_cost4.py       # Cost 4 handlers: belveth, braum, fizz... (~500 LOC)
└── _abilities_cost5.py       # Cost 5 handlers: azir, ornn, volibear (~350 LOC)

simulator/
└── cloud_runner.py           # run_batch() + main() + _worker_init (~700 LOC)
    _runner_utils.py          # Preflight/validation/stats helpers (~470 LOC)
    _runner_writer.py         # StreamingWriter class (~500 LOC)

models/
├── feature_engineering.py    # TFTFeatureEngineer class (transform methods) (~700 LOC)
├── _fe_config.py             # FeatureConfig + constants + keywords (~100 LOC)
├── _fe_loaders.py            # Reference data loaders (_load_champions, _load_traits,
│                             #   _load_items, _load_augments, helpers) (~700 LOC)
└── _fe_transforms.py         # Per-group feature methods (composition, economy,
                              #   trait, item, augment, matchup, personal) (~600 LOC)
```

### Structure Rationale

- **Leading underscore prefix (`_combat_types.py`):** Signals these are internal to the package, not public API. Downstream code continues to import from `combat_engine` via re-exports, not from the underscore modules.
- **`champion_abilities.py` kept as thin facade:** The external import `from .champion_abilities import ChampionAbilities` in `combat_engine.py` must not change. The class stays in the same file but delegates to mixin modules.
- **Cost-based split for abilities:** The existing comment structure (`# COST 1 CHAMPION ABILITIES` through `# COST 5`) creates natural boundaries that are already there in the code, requiring no new judgment about grouping.
- **`_abilities_systems.py` absorbs the special sections:** Immortal, Soulbound, Ryze's trait-dependent ability, Sylas's rotation, Tahm Kench glutton, Galio bench mechanic, T-Hex pilot system, and the hero augment tick dispatcher are all non-standard systems that cross champion boundaries. Grouping them separately from cost-based handlers is cleaner than trying to re-sort them by cost tier.

---

## Architectural Patterns

### Pattern 1: Facade File with Re-exports

**What:** The original monolithic file is kept at its original path but reduced to a thin shell that imports from the sub-modules and re-exports all previously public names.

**When to use:** Any split where external importers exist that you cannot update atomically. This is the correct approach for `combat_engine.py` and `champion_abilities.py` because both have callers outside the package.

**Trade-offs:** The facade file adds one indirection level, but it is invisible to all callers. Zero import breakage across the codebase.

**Example:**
```python
# simulator/core/combat_engine.py (after split)
# Re-export everything that was previously defined here
from ._combat_types import (  # noqa: F401
    DamageType, TargetingType, AbilityType, UnitState,
    CombatStats, Ability, Item, Buff, DotEffect, Unit,
)
from ._hex_grid import HexGrid  # noqa: F401
from ._trait_manager import TeamTraitState, TraitManager  # noqa: F401
from ._augment_manager import AugmentManager  # noqa: F401
from ._item_database import ItemDatabase, AbilityDatabase  # noqa: F401

class CombatEngine:
    # ... only the CombatEngine class body here
```

Existing callers (`from simulator.core.combat_engine import CombatEngine`) continue to work without modification. The `HexGrid`, `DamageType`, and `Unit` imports scattered across `champion_abilities.py` also continue to resolve.

### Pattern 2: Mixin Classes for Large Method Collections

**What:** The `ChampionAbilities` class methods are split across multiple mixin classes. The final `ChampionAbilities` inherits from all mixins, presenting a single unified interface to `CombatEngine`.

**When to use:** When a single class has 100+ methods grouped by concern, and all methods share `self.engine` state — moving them to separate files as stand-alone functions would break internal method calls like `self._deal_damage()` and `self._get_var()`.

**Trade-offs:** Slightly more complex MRO to reason about, but each mixin is independent (no mixin calls methods on another mixin directly). Python's MRO is deterministic so this poses no behavior risk.

**Example:**
```python
# simulator/core/_abilities_base.py
class AbilitiesBase:
    """Helper methods shared by all ability handler mixins."""
    def _deal_damage(self, attacker, target, damage, damage_type, source, can_crit=True):
        ...
    def _get_var(self, ability_vars, key, star_level, default=0):
        ...
    def _find_nearest_enemy(self, unit, enemies):
        ...
    # all other helpers

# simulator/core/_abilities_cost1.py
from ._abilities_base import AbilitiesBase
class AbilitiesCost1(AbilitiesBase):
    def _cast_anivia(self, unit, enemies, allies, ability_vars): ...
    def _cast_blitzcrank(self, unit, enemies, allies, ability_vars): ...
    # etc.

# simulator/core/champion_abilities.py
from ._abilities_cost1 import AbilitiesCost1
from ._abilities_cost2 import AbilitiesCost2
from ._abilities_cost3 import AbilitiesCost3
from ._abilities_cost4 import AbilitiesCost4
from ._abilities_cost5 import AbilitiesCost5
from ._abilities_systems import AbilitiesSystems

class ChampionAbilities(
    AbilitiesCost1, AbilitiesCost2, AbilitiesCost3,
    AbilitiesCost4, AbilitiesCost5, AbilitiesSystems
):
    """Handler for champion-specific ability mechanics."""
    def __init__(self, engine):
        self.engine = engine

    def cast(self, unit, enemies, allies, ability_vars):
        handler = getattr(self, f"_cast_{unit.api_name.replace('TFT16_', '').lower()}", None)
        if handler:
            return handler(unit, enemies, allies, ability_vars)
        return False
```

**Critical note on `AbilitiesBase` inheritance:** The `_deal_damage`, `_get_var`, `_dash_to_position`, `_apply_stun`, `_find_farthest_enemy`, `_find_nearest_enemy`, `_find_lowest_hp_enemy`, `_get_enemies_in_radius` helpers (lines 37–167 of `champion_abilities.py`) must move into `AbilitiesBase` before any cost-tier file is extracted. If these helpers stay in `champion_abilities.py` during a partial split, any intermediate state where a mixin calls `self._deal_damage()` but the method is not yet in the base class will raise `AttributeError` at runtime.

### Pattern 3: Internal Utility Module for Free Functions

**What:** Free functions that do not belong to any class — statistics helpers, preflight validators, CLI argument parsers — are moved to an internal `_runner_utils.py` module. The main file imports them.

**When to use:** `cloud_runner.py` has ~470 lines of module-level functions (lines 59–469) before `StreamingWriter` begins. These functions have no shared state and no circular dependency on the classes in the same file.

**Trade-offs:** Zero behavior change. These functions are not part of the public API (`cloud_runner` has no `__init__.py` re-exports). The move is purely mechanical.

**Example:**
```python
# simulator/_runner_utils.py
def _pyarrow_available() -> bool: ...
def _normalize_parquet_compression(name: str) -> str: ...
def _rust_extension_rebuild_hint() -> str: ...
def _wilson_interval(...) -> Tuple[float, float]: ...
def _validate_reference_data_preflight() -> None: ...
# ... all module-level helper functions

# simulator/cloud_runner.py (after split)
from ._runner_utils import (
    _pyarrow_available, _normalize_parquet_compression,
    _wilson_interval, _validate_reference_data_preflight,
    # ... rest
)
from ._runner_writer import StreamingWriter
```

### Pattern 4: Sub-module Package for Feature Groups

**What:** `feature_engineering.py` is split by grouping the `_*_feature_names()` / `_*_features()` / `_*_features_batch()` method triples into their own module, then imported back as a mixin or as free-standing functions called by `TFTFeatureEngineer`.

**When to use:** `TFTFeatureEngineer` has 7 clearly named feature groups (composition, economy, traits, items, augments, matchup, personal), each with a consistent `_*_feature_names()` / `_*_features()` / `_*_features_batch()` triple. These groups have no cross-dependencies between them — they only depend on the reference-data sets loaded in `_load_*` methods.

**Trade-offs:** The reference-data state (`self._champion_ids`, `self._trait_lookup`, etc.) is on the `TFTFeatureEngineer` instance. Moving the transform methods to a mixin preserves `self` access. Moving them to free functions would require passing the data as arguments, which is messier. Mixin pattern is correct here.

---

## Data Flow

### Cross-File Dependencies (Critical for Split Ordering)

```
combat_engine.py defines:
  DamageType, HexGrid, Unit, CombatEngine, UnitState
        ↓
champion_abilities.py imports all of these (via inline deferred imports)
        ↓
engine_wrapper.py, batch_simulator.py, benchmark.py import CombatEngine
coach/scoring/combat.py imports CombatEngine
```

Consequence: `combat_engine.py` types must be extractable without touching `champion_abilities.py` first — the facade pattern in `combat_engine.py` means `from .combat_engine import DamageType` in `champion_abilities.py` still works even after `DamageType` physically lives in `_combat_types.py`.

```
feature_engineering.py defines:
  FeatureConfig, TFTFeatureEngineer
        ↓
data_loader.py, dataset.py, train_xgboost.py import both
src/models/placement_model.py imports FeatureEngineer (different class, different file)
tests/test_feature_engineering.py imports TFTFeatureEngineer
```

Consequence: `FeatureConfig` and `TFTFeatureEngineer` must remain importable from `models.feature_engineering` after the split. The facade re-export in `feature_engineering.py` covers this.

```
cloud_runner.py defines:
  run_batch, run_game, StreamingWriter, main
  Uses module globals: _RUST_FULL_SIMULATOR, _RUST_PARQUET_API_VALIDATED
        ↓
scripts/run-gates.sh, scripts/_gate_b.sh invoke via CLI
No Python importers outside the module itself
```

Consequence: `cloud_runner.py` has no external Python importers — it is only invoked as a CLI. This makes it the safest split because there are no import compatibility obligations. The globals must stay in the same process scope as `run_game` and `run_batch` since they are mutated inside worker init and batch execution. If `run_game` moves to `_runner_utils.py`, the globals must also move there, or be passed explicitly (the refactor to class-based state handles this correctly).

---

## Scaling Considerations

| Split Complexity | Risk | Notes |
|-----------------|------|-------|
| `cloud_runner.py` (free functions) | Low | No external importers, no determinism dependency, no circular references |
| `feature_engineering.py` (config + loaders) | Low | External importers exist but only use `TFTFeatureEngineer` and `FeatureConfig` — both stay re-exported |
| `combat_engine.py` (type extraction) | Medium | External importers import `CombatEngine`, `HexGrid`, `DamageType`, `Unit`. Facade covers all. Benchmark must pass after each step. |
| `champion_abilities.py` (cost-tier split) | Medium-High | Mixin MRO complexity. Deferred inline imports of `DamageType`, `HexGrid`, `UnitState` inside cast handlers must be validated against the post-split module paths. If `DamageType` is now in `_combat_types.py` but re-exported from `combat_engine.py`, the inline `from .combat_engine import DamageType` inside the mixin methods still works because the facade re-exports it. |
| `champion_abilities.py` (special systems) | High | Immortal, Tahm Kench, T-Hex, Galio systems cross-call other handler methods (e.g., `_cast_galio` calls `self.engine.trait_manager`). These must be extracted together into `_abilities_systems.py`, not distributed into cost tiers. |

---

## Split Order of Operations (Safest First)

### Phase 1: No-risk infrastructure splits (no determinism dependency)

**Step 1.1 — `cloud_runner.py` free-function extraction**

Extract lines 59–469 (all module-level functions before `StreamingWriter`) into `simulator/_runner_utils.py`. Import them back into `cloud_runner.py`. The module globals `_RUST_FULL_SIMULATOR` and `_RUST_PARQUET_API_VALIDATED` stay in `cloud_runner.py` for now (they are mutated by `run_game` which also stays). No behavior change.

Verification: `ruff check .` + `ruff format --check .` only. No benchmark needed.

**Step 1.2 — `cloud_runner.py` StreamingWriter extraction**

Extract `StreamingWriter` class (lines 470–986) into `simulator/_runner_writer.py`. Import it back in `cloud_runner.py`. No external importers of `StreamingWriter` exist outside `cloud_runner.py`.

Verification: `ruff check .` + `ruff format --check .` only.

**Step 1.3 — `feature_engineering.py` config/constants extraction**

Extract `FeatureConfig`, `TraitMetadata`, and the module-level constants (`EPSILON`, `STAR_SCALING_HP`, `ATTACK_SPEED_CAP`, keyword tuples, magic number constants) into `models/_fe_config.py`. Re-export all from `feature_engineering.py`. `data_loader.py` imports `FeatureConfig` from `models.feature_engineering` — this remains valid.

Verification: `ruff check .` + `ruff format --check .` + `python -m pytest tests/test_feature_engineering.py`.

**Step 1.4 — `feature_engineering.py` loader extraction**

Extract `_load_reference_data`, `_build_fast_lookup_sets`, `_load_json`, `_load_champions`, `_load_traits`, `_normalize_item_effects`, `_classify_item_type`, `_load_items`, `_infer_augment_tier`, `_infer_augment_flags`, `_augment_data_candidates`, `_load_augments`, `_load_personal_reference` into `models/_fe_loaders.py` as a mixin class `FeatureLoaderMixin`. `TFTFeatureEngineer` inherits from it.

Verification: `ruff check .` + `ruff format --check .` + `python -m pytest tests/test_feature_engineering.py`.

### Phase 2: Simulator type extraction (benchmark required after each step)

**Step 2.1 — `combat_engine.py` type/enum extraction**

Extract `DamageType`, `TargetingType`, `AbilityType`, `UnitState`, `CombatStats`, `Ability`, `Item`, `Buff`, `DotEffect`, `Unit` (lines 99–323) into `simulator/core/_combat_types.py`. Add re-exports at the top of `combat_engine.py`. This is purely moving definitions; no logic changes.

Verification: `ruff check .` + `python -m simulator.benchmark` (determinism must pass).

**Step 2.2 — `combat_engine.py` HexGrid extraction**

Extract `HexGrid` class (lines 329–490) into `simulator/core/_hex_grid.py`. Re-export from `combat_engine.py`. The deferred `from .combat_engine import HexGrid` inside `champion_abilities.py` continues to work via the re-export.

Verification: `ruff check .` + `python -m simulator.benchmark`.

**Step 2.3 — `combat_engine.py` TraitManager extraction**

Extract `TeamTraitState` and `TraitManager` (lines 498–1874) into `simulator/core/_trait_manager.py`. This is the largest component in `combat_engine.py` (~1376 lines). `CombatEngine` holds a `TraitManager` instance; after extraction `CombatEngine` imports it. Re-export from `combat_engine.py`.

Verification: `ruff check .` + `python -m simulator.benchmark`.

**Step 2.4 — `combat_engine.py` AugmentManager extraction**

Extract `AugmentManager` (lines 1895–2511) into `simulator/core/_augment_manager.py`. Same pattern: re-export from `combat_engine.py`.

Verification: `ruff check .` + `python -m simulator.benchmark`.

**Step 2.5 — `combat_engine.py` database extraction**

Extract `ItemDatabase` and `AbilityDatabase` (lines 2512–2728) into `simulator/core/_item_database.py`. Re-export.

Verification: `ruff check .` + `python -m simulator.benchmark`.

At this point `combat_engine.py` contains only the `CombatEngine` class and module-level setup (data loading, import block) — approximately 700 lines.

### Phase 3: Champion abilities split (highest risk, benchmark after every file)

**Step 3.1 — Extract `AbilitiesBase` helpers**

Move the helper methods block (lines 37–167 of `champion_abilities.py`) into `simulator/core/_abilities_base.py` as class `AbilitiesBase`. `ChampionAbilities` inherits from it. Verify that `cast()`, `_deal_damage()`, `_get_var()`, etc. all resolve correctly.

Verification: `ruff check .` + `python -m simulator.benchmark`.

**Step 3.2 — Extract special systems**

Move all non-cost-tier sections (Immortal, Soulbound/Lucian+Senna, Ryze, Sylas, Shadow Isles, Tahm Kench, Galio, T-Hex, Baron Nashor, Rift Herald, Leona passive, Taric passive, Skarner, Xerath, Zilean, Mel, Sett, Brock, Xin Zhao, Rumble, Illaoi, Jhin, and `process_hero_augment_ticks`) into `simulator/core/_abilities_systems.py` as mixin `AbilitiesSystems(AbilitiesBase)`.

**This step must come before cost-tier splits** because the cost-tier sections (cost 1–5) contain only clean `_cast_*` handlers, while the special systems sections are intercalated between them in the current file. Extracting systems first leaves only cost-tier handlers behind.

Verification: `ruff check .` + `python -m simulator.benchmark`.

**Step 3.3 — Extract cost 1 handlers**

Move `# COST 1 CHAMPION ABILITIES` block (lines 4648–4882) into `simulator/core/_abilities_cost1.py` as mixin `AbilitiesCost1(AbilitiesBase)`.

Verification: `ruff check .` + `python -m simulator.benchmark`.

**Steps 3.4–3.7 — Extract cost 2, 3, 4, 5 handlers**

Same pattern, one cost tier per step. Each step has its own benchmark run.

After step 3.7, `champion_abilities.py` contains only `ChampionAbilities.__init__`, `ChampionAbilities.cast()`, and the inheritance chain declaration.

---

## Testing Checkpoints

| Checkpoint | After Step | Tests to Run |
|------------|-----------|--------------|
| Infra split green | 1.2 | `ruff check .` + `ruff format --check .` |
| FE split green | 1.4 | `ruff check .` + `python -m pytest tests/test_feature_engineering.py` |
| Types extracted | 2.1 | `ruff check .` + `python -m simulator.benchmark` |
| HexGrid extracted | 2.2 | `ruff check .` + `python -m simulator.benchmark` |
| TraitManager extracted | 2.3 | `ruff check .` + `python -m simulator.benchmark` |
| AugmentManager extracted | 2.4 | `ruff check .` + `python -m simulator.benchmark` |
| Databases extracted | 2.5 | `ruff check .` + `python -m simulator.benchmark` |
| AbilitiesBase extracted | 3.1 | `ruff check .` + `python -m simulator.benchmark` |
| Systems extracted | 3.2 | `ruff check .` + `python -m simulator.benchmark` |
| Each cost tier extracted | 3.3–3.7 | `ruff check .` + `python -m simulator.benchmark` |
| All splits complete | end | `python -m pytest` (full suite) + `python -m simulator.benchmark` |

**Benchmark is mandatory after every simulator/core change.** No exceptions. The benchmark verifies that `python` and `rust` engines produce identical output for identical seeds — structural refactors must not accidentally change initialization order, default argument values, or any stateful path.

---

## Anti-Patterns

### Anti-Pattern 1: Big-Bang Split

**What people do:** Move all sub-modules simultaneously in a single commit.
**Why it's wrong:** If the benchmark fails after a big-bang split, the diff is too large to bisect. The failure could be in any of the 7 new files.
**Do this instead:** One sub-module per commit, benchmark after each. The extra commits are cheap; the debugging cost of a failed big-bang split is not.

### Anti-Pattern 2: Removing the Facade

**What people do:** Update all import sites across the codebase to point to the new sub-module path (e.g., change `from simulator.core.combat_engine import DamageType` to `from simulator.core._combat_types import DamageType`).
**Why it's wrong:** This creates a large, noisy diff that touches files outside the split scope. It also breaks the rule that underscore-prefixed modules are internal. External code should never import from `_combat_types` directly.
**Do this instead:** Keep the facade re-exports in `combat_engine.py` permanently. The sub-modules are an implementation detail.

### Anti-Pattern 3: Splitting Before Extracting Helpers

**What people do:** Start extracting cost-tier ability files before moving `AbilitiesBase` helpers.
**Why it's wrong:** Each cost-tier mixin calls `self._deal_damage()`, `self._get_var()`, `self._get_enemies_in_radius()` etc. If those methods are still on `ChampionAbilities` (not on a base class) when the first mixin is extracted, the mixin's `self` lookup will fail because the mixin is not yet composed with `ChampionAbilities`.
**Do this instead:** Always extract `AbilitiesBase` (the helpers) as the first step of the abilities split. Every subsequent mixin inherits from it.

### Anti-Pattern 4: Moving Module-Level Globals Across Files

**What people do:** Move `_RUST_FULL_SIMULATOR` and `_RUST_PARQUET_API_VALIDATED` to `_runner_utils.py` during the cloud_runner split.
**Why it's wrong:** These globals are mutated by `run_game()` (called in worker subprocesses) and by `_worker_init()` and `run_batch()`. Moving them to a different module while some mutators stay in `cloud_runner.py` creates a split-brain: one file's copy of the variable changes but the other's does not, because `global` statements in Python refer to the module they are written in.
**Do this instead:** During the free-function extraction (Step 1.1), do not move `run_game` or the globals. Move only the pure utility functions that have no global state. The globals refactor (into a class-based runner) is a separate concern addressed by the `cloud_runner` global state tech debt item, not by the file split.

---

## Integration Points

### External Boundaries (Must Not Break)

| Boundary | Current Import | Stays Valid After Split |
|----------|---------------|------------------------|
| `simulator/benchmark.py` | `from simulator.core.combat_engine import CombatEngine` | YES — CombatEngine stays in combat_engine.py |
| `coach/scoring/combat.py` | `from simulator.core.combat_engine import CombatEngine` | YES |
| `simulator/core/batch_simulator.py` | `from simulator.core.combat_engine import CombatEngine` | YES |
| `champion_abilities.py` inline | `from .combat_engine import DamageType, HexGrid, UnitState` | YES — all re-exported from combat_engine.py |
| `models/data_loader.py` | `from .feature_engineering import FeatureConfig, TFTFeatureEngineer` | YES — re-exported |
| `models/train_xgboost.py` | `from .feature_engineering import FeatureConfig, TFTFeatureEngineer` | YES |
| `tests/test_feature_engineering.py` | `from models.feature_engineering import TFTFeatureEngineer` | YES |
| CLI invocation | `python simulator/cloud_runner.py` | YES — main() stays in cloud_runner.py |

### Internal Boundaries (New After Split)

| Boundary | Communication | Consideration |
|----------|---------------|---------------|
| `_abilities_cost*.py` → `_abilities_base.py` | Inheritance (`self.*`) | Base class must be listed first in MRO |
| `_abilities_systems.py` → `_abilities_base.py` | Inheritance | Same |
| `champion_abilities.py` → all `_abilities_*.py` | Inheritance composition | `ChampionAbilities` inherits all mixins |
| `combat_engine.py` → `_combat_types.py` | Re-export at module level | Must come before `CombatEngine` class body |
| `cloud_runner.py` → `_runner_utils.py` | Direct import of functions | No circular dependency possible |
| `cloud_runner.py` → `_runner_writer.py` | `from ._runner_writer import StreamingWriter` | StreamingWriter uses no globals from cloud_runner |

---

## Sources

- Direct inspection of `simulator/core/champion_abilities.py` (5911 LOC, 2026-02-27)
- Direct inspection of `simulator/core/combat_engine.py` (5306 LOC, 2026-02-27)
- Direct inspection of `models/feature_engineering.py` (2100 LOC, 2026-02-27)
- Direct inspection of `simulator/cloud_runner.py` (2048 LOC, 2026-02-27)
- `.planning/codebase/CONCERNS.md` — identifies split targets and proposed sub-modules
- `.planning/codebase/ARCHITECTURE.md` — layer dependencies and data flow
- Python packaging documentation: PEP 328 (relative imports), Python module `__init__.py` re-export patterns (HIGH confidence — standard Python behavior)
- Python MRO (C3 linearization) for mixin composition: deterministic and well-specified (HIGH confidence)

---
*Architecture research for: Safe monolithic Python module splitting in deterministic combat simulator*
*Researched: 2026-02-27*
