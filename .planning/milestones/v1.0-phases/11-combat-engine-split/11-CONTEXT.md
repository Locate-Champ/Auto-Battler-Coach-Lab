# Phase 11: Combat Engine Split - Context

**Gathered:** 2026-03-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Split combat_engine.py (5,312 LOC) into a CombatEngine facade plus private sub-modules for types, hex grid, trait manager, augment manager, item database, and CombatEngine method mixins. Determinism is verified by benchmark after every individual structural change. All existing import paths must resolve correctly after the split.

</domain>

<decisions>
## Implementation Decisions

### Module grouping
- `_combat_types.py`: All enums (DamageType, TargetingType, AbilityType, UnitState) + all dataclasses (CombatStats, Ability, Item, Buff, DotEffect, Unit) + helper functions (_star_val, _load_combat_data, _COMBAT_DATA_CACHE)
- `_hex_grid.py`: HexGrid class (standalone, no cross-dependencies)
- `_trait_manager.py`: TeamTraitState + TraitManager (~1,350 LOC kept as single file — 30+ _apply_* methods are repetitive but cohesive)
- `_augment_manager.py`: AugmentManager class
- `_item_database.py`: ItemDatabase + AbilityDatabase (both are lookup factory classes)

### CombatEngine mixin split
CombatEngine (~2,300 LOC) is too large to keep whole in the facade (800 LOC target). Split into 3 mixins:
- `_combat_actions.py`: damage/heal/shield/CC/debuff methods (~12 methods: calculate_damage, apply_damage, heal_unit, apply_shield, apply_burn, apply_cc, apply_wound, apply_sunder, apply_shred, gain_mana, check_hp_threshold_effects)
- `_combat_processing.py`: attack/ability/movement/tick (~8 methods: process_attack, cast_ability, _post_ability_cast, move_unit_towards, process_unit_tick, tick)
- `_combat_runners.py`: combat runners + round management + trait combat helpers (~12 methods: run_combat, run_combat_adaptive_tick, _next_event_dt, simulate_1v1, process_round_start, _apply_combat_start_items, _fire_piltover_module, _check_noxus_atakhan_summon, _summon_atakhan, _find_atakhan_spawn, _check_atakhan_ruin, _count_traits)
- Facade keeps: __init__, create_unit, set_round_persistent_players, apply_item, _spawn_azir_soldiers, get_occupied_hexes, _invalidate_occupied_cache, set_unit_position, log_event, main(), and all re-exports

### TraitManager size
Keep TraitManager as one `_trait_manager.py` file (~1,350 LOC). The _apply_* methods are repetitive pattern-followers (each applies a specific trait). Sub-splitting by region vs class vs pair would scatter related logic and add import complexity for marginal benefit.

### Extraction ordering
One sub-module per benchmark-gated commit, ordered by risk (lowest first):
1. `_combat_types.py` — zero behavior risk, purely structural
2. `_hex_grid.py` — standalone class, no cross-dependencies
3. `_item_database.py` — lookup factories, minimal coupling
4. `_augment_manager.py` — self-contained manager
5. `_trait_manager.py` — largest extraction, most cross-references
6. `_combat_actions.py` — first CombatEngine mixin
7. `_combat_processing.py` — second mixin (depends on actions)
8. `_combat_runners.py` — final mixin (depends on processing + actions)

### Benchmark gating
Every extraction step is a standalone commit. `python -m simulator.benchmark` must pass with identical output (fixed seed) before the next extraction begins. If benchmark fails, revert and investigate before proceeding.

### Import path preservation
- Facade re-exports all public names so `from simulator.core.combat_engine import X` continues to work
- champion_abilities.py and item_effects.py use many deferred local imports (`from .combat_engine import DamageType, HexGrid, Unit`) — these must resolve through facade re-exports
- Follow the established pattern from Phase 10: underscore-prefixed sub-modules with noqa: F401 facade re-exports

### Claude's Discretion
- Exact method assignment to mixins (may shift 1-2 methods between groups based on call-graph analysis)
- MRO ordering of mixin classes
- Whether main() stays in facade or moves to a separate entry point
- Internal import structure between sub-modules (who imports from whom)

</decisions>

<specifics>
## Specific Ideas

No specific requirements beyond the ROADMAP success criteria. Follow the Phase 10 facade pattern established for cloud_runner.py and feature_engineering.py splits.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 10 established the facade re-export pattern: underscore-prefixed sub-modules with original file as thin facade
- noqa: F401 for intentional re-exports (established in 10-01)
- .gitignore whitelist entries needed for new simulator files (simulator/** ignore-all pattern)

### Established Patterns
- Mixin composition pattern established in Phase 10 (10-02): TFTFeatureEngineer uses _LoaderMixin, _TransformMixin, _BatchTransformMixin
- Facade class defined in facade file (not sub-module) to preserve pickle __module__ path
- MRO order matters — see 10-02 decision on loader-first ordering

### Integration Points
- champion_abilities.py: ~30 deferred imports from combat_engine (DamageType, HexGrid, Unit, UnitState, CombatEngine)
- item_effects.py: ~20 deferred imports from combat_engine (DamageType, HexGrid, Unit, CombatEngine)
- coach/scoring/combat.py: imports CombatEngine
- simulator/benchmark.py: imports CombatEngine
- simulator/core/batch_simulator.py: imports CombatEngine
- simulator/core/engine_wrapper.py: imports CombatEngine (fallback from Rust)

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 11-combat-engine-split*
*Context gathered: 2026-03-01*
