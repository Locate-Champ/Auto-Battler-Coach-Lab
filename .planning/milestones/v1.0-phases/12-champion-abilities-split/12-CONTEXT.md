# Phase 12: Champion Abilities Split - Context

**Gathered:** 2026-03-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Split champion_abilities.py (5,911 LOC) into AbilitiesBase plus sub-module mixins using mixin composition pattern (matching Phase 11). AbilitiesBase extracted first as a hard prerequisite. Determinism verified via benchmark after every extraction step. Facade under 250 LOC.

</domain>

<decisions>
## Implementation Decisions

### Split Grouping Strategy
- Follow the file's existing section headers as the grouping basis
- Target 5-6 sub-module files total (base, systems, hero augments, alphabetical, cost tiers — Claude decides whether alphabetical and cost-tier sections need further splitting based on LOC balance)
- Hero augment handlers get their own file (_abilities_hero_augments.py)

### Special Systems Handling
- All named special systems in one file (_abilities_systems.py): Immortal trait logic, Soulbound (Lucian/Senna), Ryze trait-dependent, Sylas trifold rotation, Shadow Isles soul collection, Tahm Kench glutton, Galio bench mechanic, T-HEX pilot system, Baron Nashor, Rift Herald
- Named passive abilities (Leona, Taric, Skarner, Xerath, Zilean, Mel, Sett, Brock) — Claude decides whether they join systems file or get their own file, based on final LOC balance

### AbilitiesBase Extraction Scope
- AbilitiesBase contains: __init__(self, engine), cast() dispatcher, all 8 helper methods (_get_var, _find_farthest_enemy, _find_nearest_enemy, _find_lowest_hp_enemy, _get_enemies_in_radius, _dash_to_position), _deal_damage, _apply_stun, and check_immortal_resurrection
- check_immortal_resurrection() moves to AbilitiesBase (public API called by combat engine belongs in base)
- Use mixin pattern matching Phase 11: _AbilitiesBaseMixin, other sub-modules as mixins, ChampionAbilities composes via MRO

### Import Strategy
- Switch deferred `from .combat_engine import DamageType/UnitState/etc.` to module-level `from ._combat_types import ...` in sub-modules
- Phase 11 already extracted DamageType, UnitState, Unit, etc. into _combat_types.py — no circular import risk since _combat_types doesn't import champion_abilities
- This replaces 117 deferred import statements with clean module-level imports

### Extraction Order
- AbilitiesBase first (roadmap requirement, standalone commit + benchmark)
- Systems next (highest risk, cross-method audit needed per STATE.md concern)
- Remaining sub-modules after (hero augments, cost tiers, alphabetical)
- Claude decides benchmark gating frequency: strict per-extraction for high-risk, batched for simple extractions

### Target LOC and File Count
- Facade target: under 250 LOC (likely ~50-80 based on Phase 11 pattern)
- No per-sub-module LOC limit — sub-modules can be whatever size they naturally end up
- 5-6 files total is the target range

### Claude's Discretion
- Whether to split the alphabetical section (~2,100 LOC) into two files or keep as one
- Whether cost tiers (Cost 1-5, ~1,270 LOC) should be one file or split
- Where named passives land (systems file vs separate file) — based on LOC balance
- Benchmark gating frequency for simple extractions (per-extraction vs batched)

</decisions>

<specifics>
## Specific Ideas

- Match Phase 11's mixin composition pattern exactly for consistency
- Extraction order: base -> systems (hardest) -> rest (builds confidence)
- The cross-method call audit flagged in STATE.md (self._cast_, self.engine., self._deal_damage() in special systems) must be done before writing _abilities_systems.py

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 11 mixin pattern: _CombatActionsMixin, _CombatProcessingMixin, _CombatRunnersMixin — exact template for this split
- _combat_types.py: Already exports DamageType, UnitState, Unit, CombatStats, Ability, DotEffect — can replace 117 deferred imports
- combat_engine.py facade: Template for the champion_abilities.py facade (MRO composition + re-exports)

### Established Patterns
- Mixin composition via MRO with rightmost = lowest-level
- TYPE_CHECKING for cross-module type hints (used in _augment_manager.py, _trait_manager.py)
- Each mixin uses only self.* for cross-method calls — no mixin-to-mixin imports
- Benchmark gate after every structural change to simulator core

### Integration Points
- combat_engine.py imports ChampionAbilities: `from .champion_abilities import ChampionAbilities` (line 51, deferred under TYPE_CHECKING)
- 238 `self.engine.*` calls from champion_abilities into combat_engine methods
- 1 `from .item_effects import get_item_data` call (in _apply_stun helper)
- Only 1 cross-_cast_ call: _cast_illaoi calls itself recursively (line 4548)

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 12-champion-abilities-split*
*Context gathered: 2026-03-02*
