# Phase 14: Integration Polish & Documentation Sync - Context

**Gathered:** 2026-03-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Close remaining integration gaps from the v1.0 milestone: wire DataLoader context manager into production training code, resolve the dead models/exceptions.py hierarchy, and fix stale documentation (REQUIREMENTS.md counts, ROADMAP.md checkboxes).

</domain>

<decisions>
## Implementation Decisions

### exceptions.py resolution
- No production code imports or raises any class from models/exceptions.py
- The codebase is internal-only — no external callers need a custom exception hierarchy
- No concrete future use case for these custom exceptions
- Phase 1 already narrowed all broad exceptions to stdlib types (ImportError, OSError, ValueError, etc.) and those are working fine

### Claude's Discretion
- **exceptions.py fate**: Claude evaluates whether the hierarchy adds value given no imports, no external callers, and stdlib exceptions already working. Most likely outcome: remove as dead code.
- **Decision tracing**: Claude decides whether removing exceptions.py warrants a PROJECT.md key decision entry or a clean deletion
- **DataLoader context manager scope**: train_xgboost.py constructs DataLoader in 2 places (main entrypoint line ~757, feature ablation loop line ~590). Claude decides whether to wire both with `with` or just the main path.
- **Documentation sync depth**: REQUIREMENTS.md shows stale "Pending: 3 (OBSV)" and ROADMAP plan checkboxes are unchecked for completed phases. Claude decides the scope of documentation reconciliation.

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. User wants a clean wrap-up of the v1.0 milestone.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `DataLoader.__enter__`/`__exit__`: Context manager protocol already implemented in Phase 3 — just needs callers to use `with` syntax
- `models/exceptions.py`: 4-class hierarchy (ModelsPipelineError > DataLoadError, FeatureEngineeringError, TrainingError) — currently dead code

### Established Patterns
- Phase 1 used stdlib exceptions (ImportError, OSError, ValueError) at all narrowed sites — no custom exceptions wired
- `_log = logging.getLogger(__name__)` is the standard logger pattern across all modules (Phase 2/13)

### Integration Points
- `train_xgboost.py` main() (~line 757): `loader = DataLoader(args.data, n_workers=args.feature_workers)` — primary wiring target
- `train_xgboost.py` ablation loop (~line 590): `loader = DataLoader(args.data, feature_engineer=...)` — secondary wiring target
- `REQUIREMENTS.md` coverage section: "Complete: 29, Pending: 3" — needs update to reflect Phase 13 completion
- `ROADMAP.md` plan checkboxes: `[ ]` markers on completed phase plans — need `[x]`

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 14-integration-polish-and-doc-sync*
*Context gathered: 2026-03-02*
