# Phase 9: Simulator and Coach Exception Hardening - Context

**Gathered:** 2026-02-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Narrow all broad and bare exception handlers in `simulator/` and `coach/` to specific exception types. Convert intentional fallbacks to logged specific-exception handlers. Verify determinism after all combat-engine changes via benchmark. Does NOT add new features, split files, or change behavior — only makes existing error handling explicit and visible.

</domain>

<decisions>
## Implementation Decisions

### Fallback policy
- Case-by-case: simulator/coach paths that are intentional degradation (e.g., ability edge cases) log and continue; data/training-adjacent paths crash on unexpected errors
- Intentional fallbacks: keep and log — narrow the except clause, add `_log.warning()`, preserve the fallback behavior. Fallbacks exist for a reason
- Follow Phase 1 conventions where they fit (same `(ImportError, OSError)` for extensions, `_log.warning` for fallbacks), adapt where combat-engine determinism demands it
- Trivial root-cause fixes allowed: if the fix is obvious and small (e.g., missing key check), fix it inline. Complex fixes get narrowed handler + follow-up note

### Exception granularity
- Stdlib exceptions only — no custom exception hierarchy. Use `ValueError`, `TypeError`, `RuntimeError`, `KeyError` etc. with descriptive messages. Consistent with Phase 1 approach
- Tuple catch style for related exceptions: `except (ValueError, KeyError) as e:` — matches Phase 1 pattern
- Most specific possible per site: Claude reads the code, determines what exceptions are actually possible, catches exactly those
- Exception chaining: `raise X from e` when wrapping in a different type, plain `raise` when the original is already descriptive

### Combat hot-path safety
- Mid-combat exception = crash that game, log the error, continue with next game in batch. One bad game must not silently poison results
- Extra caution for `combat_engine.py` and `champion_abilities.py`: every change to these files individually benchmarked. Other simulator files follow standard rules
- Champion ability bare excepts: Claude reads each ability's code, determines what can actually fail, narrows accordingly. Some abilities may warrant broader catches than others
- Determinism benchmark runs after each combat-related file change per CLAUDE.md rule: "benchmark is a hard gate after every simulator-core change"

### Logging standards
- Fallback log level: Claude uses WARNING for unexpected fallbacks, INFO for expected/known-limitation fallbacks — consistent with Phase 2 decisions where applicable
- Log message context: enough to diagnose without a debugger, consistent with Phase 1-2 patterns. Don't dump full state
- Add `_log = logging.getLogger(__name__)` to any module getting exception work if missing — consistent with Phase 2 convention (`_log` not `logger`)
- exc_info: use `exc_info=True` at debug level (available when needed), clean descriptive messages at warning level

### Claude's Discretion
- Exact exception type selection per handler site
- Whether a specific bare except is "intentional fallback" or "bug masking" — Claude evaluates based on surrounding code
- Log message wording and context detail level
- Whether a root-cause fix is "trivial enough" to include vs defer

</decisions>

<specifics>
## Specific Ideas

- Phase 1 established the patterns: `(ImportError, OSError)` for extension imports, `_log` naming, descriptive messages. Phase 9 extends these same patterns to simulator and coach layers
- The `ruff check simulator/ coach/` with BLE001 must report zero violations when done — this is the success gate from ROADMAP.md
- Benchmark must pass with identical output (fixed seed) after every combat-engine file change — no exceptions to this rule

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 09-simulator-and-coach-exception-hardening*
*Context gathered: 2026-02-28*
