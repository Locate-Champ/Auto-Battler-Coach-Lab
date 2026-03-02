# Phase 14: Integration Polish & Documentation Sync - Research

**Researched:** 2026-03-02
**Domain:** Python resource management patterns, dead code removal, documentation reconciliation
**Confidence:** HIGH

## Summary

Phase 14 is a mechanical cleanup phase that closes three integration gaps identified in the v1.0 milestone audit. The work involves (1) wrapping existing DataLoader usage in `train_xgboost.py` with the context manager protocol already implemented in Phase 3, (2) removing the dead `models/exceptions.py` module that was never imported by any production code, and (3) fixing stale documentation in REQUIREMENTS.md and ROADMAP.md where checkbox states and coverage counts do not match actual completion status.

All three tasks are low-risk, well-understood modifications with no new dependencies or architectural decisions. The DataLoader context manager protocol is already implemented and tested (Phase 3 + tests in `test_data_loader.py`). The exceptions.py removal is a clean deletion of an unused file. The documentation fixes are checkbox-state and counter updates.

**Primary recommendation:** Wire `with DataLoader(...) as loader:` at both call sites in train_xgboost.py (main entrypoint line ~757 and ablation loop line ~590), delete models/exceptions.py as dead code, and update REQUIREMENTS.md coverage counts + ROADMAP.md checkboxes to reflect actual completion state.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- No production code imports or raises any class from models/exceptions.py
- The codebase is internal-only -- no external callers need a custom exception hierarchy
- No concrete future use case for these custom exceptions
- Phase 1 already narrowed all broad exceptions to stdlib types (ImportError, OSError, ValueError, etc.) and those are working fine

### Claude's Discretion
- **exceptions.py fate**: Claude evaluates whether the hierarchy adds value given no imports, no external callers, and stdlib exceptions already working. Most likely outcome: remove as dead code.
- **Decision tracing**: Claude decides whether removing exceptions.py warrants a PROJECT.md key decision entry or a clean deletion
- **DataLoader context manager scope**: train_xgboost.py constructs DataLoader in 2 places (main entrypoint line ~757, feature ablation loop line ~590). Claude decides whether to wire both with `with` or just the main path.
- **Documentation sync depth**: REQUIREMENTS.md shows stale "Pending: 3 (OBSV)" and ROADMAP plan checkboxes are unchecked for completed phases. Claude decides the scope of documentation reconciliation.

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| RSMG-01 | DataLoader implements `__enter__`/`__exit__` context manager for automatic pool cleanup | Already implemented (Phase 3). Research confirms `__enter__`/`__exit__` exist in data_loader.py lines 129-141. Phase 14 wires production callers to use `with` syntax. |
| RSMG-02 | DataLoader `__exit__` handles cleanup exceptions without masking the original exception | Already implemented (Phase 3). `__exit__` catches (OSError, RuntimeError), logs warning, returns False (never suppresses). Phase 14 exercises this via `with` usage. |
| EXCP-02 | Models layer exceptions use specific types | Already satisfied by stdlib exceptions (Phase 1). Phase 14 resolves the dead exceptions.py module that was created for this requirement but never wired. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib | 3.10+ | Context manager protocol (`__enter__`/`__exit__`), `os`, `pathlib` | Built-in language feature, no dependencies |
| ruff | (project version) | Lint verification after changes | Already configured in project ruff.toml |
| pytest | (project version) | Test execution | Already configured in pytest.ini |

### Supporting
No new libraries needed. This phase modifies existing code and documentation only.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `with` statement | `try/finally` with explicit `close()` | `with` is cleaner, already implemented in DataLoader, and is the Python idiom for resource management. The existing `loader.close()` at line 970 would be replaced by automatic cleanup. |
| Delete exceptions.py | Wire exceptions into production code | No concrete use case exists (CONTEXT.md decision). Stdlib exceptions work fine. Wiring would add complexity for zero benefit. |

## Architecture Patterns

### Recommended Project Structure
No structural changes. Files affected:
```
models/
  train_xgboost.py        # Wire `with DataLoader(...)` at 2 sites
  exceptions.py            # DELETE (dead code)
.planning/
  REQUIREMENTS.md          # Fix coverage counts
  ROADMAP.md               # Fix phase/plan checkboxes
```

### Pattern 1: Context Manager Wrapping for DataLoader
**What:** Replace bare `loader = DataLoader(...)` followed by eventual `loader.close()` with `with DataLoader(...) as loader:` block
**When to use:** Every place in production code that constructs a DataLoader
**Example:**
```python
# BEFORE (current main() at line ~757):
loader = DataLoader(args.data, n_workers=args.feature_workers)
# ... ~200 lines of usage ...
loader.close()

# AFTER:
with DataLoader(args.data, n_workers=args.feature_workers) as loader:
    # ... same ~200 lines of usage, indented ...
    # close() called automatically on both normal exit and exceptions
```

### Pattern 2: Ablation Loop Context Manager
**What:** Each iteration of the ablation loop creates a separate DataLoader with a custom FeatureConfig. Each should use `with` for automatic cleanup.
**When to use:** `_run_ablation()` function where DataLoader is created per toggle iteration
**Example:**
```python
# BEFORE (_run_ablation at line ~590):
loader = DataLoader(args.data, feature_engineer=TFTFeatureEngineer(config=config))
# ... uses loader for data loading only (no parallel workers) ...
# no close() call at end

# AFTER:
with DataLoader(args.data, feature_engineer=TFTFeatureEngineer(config=config)) as loader:
    # ... same usage, indented ...
```

### Pattern 3: Dead Code Removal
**What:** Delete `models/exceptions.py` entirely. No import sites exist; no production code references it.
**When to use:** When an entire module is confirmed dead code by grep + audit
**Verification before deletion:**
```bash
# Confirm zero imports (should return empty):
grep -r "from models.exceptions import\|from \.exceptions import" --include="*.py" models/ app/ coach/ simulator/ src/ tests/
```

### Anti-Patterns to Avoid
- **Partial `with` wiring:** Do not wire only main() and skip ablation. Both sites create pools that need cleanup. The ablation loaders are short-lived but still create worker pools if the data is large enough.
- **Keeping dead code "for future use":** CONTEXT.md explicitly establishes there is no concrete future use case. Keeping unused code increases maintenance burden and confuses new contributors.
- **Indentation-only changes mixed with logic changes:** When wrapping main() body in `with`, the change is purely indentation + the `with` line itself. Do NOT change any logic inside the block.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Resource cleanup | Custom try/finally blocks | `with` statement (context manager) | DataLoader already implements `__enter__`/`__exit__`; `with` is the standard Python idiom |
| Dead code detection | Manual import tracing | `grep -r` + audit report | v1.0 audit already confirmed zero imports of exceptions.py |
| Documentation sync | Manual counting | Systematic grep for checkbox states | Counting by hand is error-prone; grep `\[ \]` and `\[x\]` for accuracy |

**Key insight:** Every component needed for this phase already exists. The DataLoader context manager was built in Phase 3 with tests. This phase is pure wiring and cleanup.

## Common Pitfalls

### Pitfall 1: Indentation Drift in main() Wrapping
**What goes wrong:** Wrapping the ~230-line main() body in a `with` block requires re-indenting the entire body. A misplaced line or lost indentation breaks the control flow.
**Why it happens:** Large indentation changes are error-prone in manual editing.
**How to avoid:** The `with` block should start right after validation checks (lines 742-745) and encompass everything from loader creation through `loader.close()` (which gets removed). Verify with `ruff check models/train_xgboost.py` and `python -m pytest tests/test_train_xgboost_external_memory.py` after.
**Warning signs:** IndentationError, unexpected else/elif, ruff E1 errors.

### Pitfall 2: Ablation DataLoader Not Pooling But Still Needing Cleanup
**What goes wrong:** The ablation DataLoaders use `n_workers=0` (default) which means they auto-detect worker count. On machines with many cores, they create actual pools.
**Why it happens:** `DataLoader.__init__` defaults to `n_workers=0` which resolves to `min(cpu_count, 64)` workers in `_effective_workers()`. Pool creation is lazy (only on first vectorization call), but ablation calls `load_fight_prediction_data()` which calls `_vectorize_rows()` which calls `_ensure_pool()` for datasets >= 500 rows.
**How to avoid:** Wire `with` for ablation loaders even though they appear short-lived. This ensures pool cleanup even if an exception occurs mid-ablation.
**Warning signs:** ResourceWarning about garbage-collected DataLoader during ablation.

### Pitfall 3: Forgetting to Remove the Explicit close() Call
**What goes wrong:** After wrapping main() body in `with DataLoader(...) as loader:`, the explicit `loader.close()` at line 970 is now redundant. If left in, it calls close() twice (once explicitly, once via `__exit__`).
**Why it happens:** The `with` statement automatically calls `__exit__` which calls `close()`. A second `close()` would try to close an already-None pool.
**How to avoid:** Remove the `loader.close()` call at line 970 when adding the `with` wrapper. Double-close is harmless (close() checks `self._pool is not None` before acting) but is confusing dead code.
**Warning signs:** close() called on already-closed DataLoader (no error, but unnecessary).

### Pitfall 4: ROADMAP Checkbox Pattern Mismatch
**What goes wrong:** Plan checkboxes use `- [ ]` and `- [x]` inside Phase Details sections. Phase summary checkboxes use the same pattern at the top. Inconsistent patterns cause grep-based verification to miss items.
**Why it happens:** Two different checkbox levels (phase-level and plan-level) use the same markdown syntax in different locations.
**How to avoid:** Update both levels systematically. Phase summary list (lines 15-28) and per-phase plan lists (scattered throughout Phase Details). Use exact string replacement.
**Warning signs:** Audit still shows stale checkboxes after fix.

### Pitfall 5: Stale Coverage Section in REQUIREMENTS.md
**What goes wrong:** The coverage summary at the bottom of REQUIREMENTS.md says "Complete: 29, Pending: 3 (OBSV-01, OBSV-02, OBSV-03 -- Phase 13)" but all 32 are actually complete. The traceability table above it correctly shows all as "Complete".
**Why it happens:** The traceability table was updated when Phase 13 was added, but the coverage summary was not updated after Phase 13 completed.
**How to avoid:** Update the coverage section to read "Complete: 32, Pending: 0" and remove the OBSV pending note.

## Code Examples

Verified patterns from the existing codebase:

### DataLoader Context Manager (already implemented, Phase 3)
```python
# Source: models/data_loader.py lines 129-141
def __enter__(self) -> "DataLoader":
    return self

def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
    try:
        self.close()
    except (OSError, RuntimeError) as cleanup_err:
        _log.warning(
            "DataLoader worker pool cleanup failed during __exit__: %s. "
            "Original exception (if any) takes priority.",
            cleanup_err,
        )
    return False  # Never suppress the original exception
```

### Context Manager Usage in Tests (verified working)
```python
# Source: tests/test_data_loader.py lines 229-234
def test_context_manager_normal_exit(tmp_path: Path) -> None:
    dl = DataLoader(data_dir=tmp_path)
    with dl as loader:
        assert loader is dl
    assert dl._pool is None
```

### main() Wrapping Target (before -> after)
```python
# BEFORE: models/train_xgboost.py lines 757-970
def main() -> None:
    args = parse_args()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not 0.0 < args.test_size < 1.0:
        raise ValueError("--test-size must be in (0, 1)")
    if args.external_memory and args.ablation:
        raise ValueError("--ablation is not supported with --external-memory")

    es_rounds = args.early_stopping_rounds if args.early_stopping_rounds else None
    # ... tree param overrides ...

    loader = DataLoader(args.data, n_workers=args.feature_workers)
    # ... ~200 lines of training logic ...
    loader.close()

# AFTER:
def main() -> None:
    args = parse_args()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not 0.0 < args.test_size < 1.0:
        raise ValueError("--test-size must be in (0, 1)")
    if args.external_memory and args.ablation:
        raise ValueError("--ablation is not supported with --external-memory")

    es_rounds = args.early_stopping_rounds if args.early_stopping_rounds else None
    # ... tree param overrides ...

    with DataLoader(args.data, n_workers=args.feature_workers) as loader:
        # ... same ~200 lines of training logic, indented 4 spaces ...
        # loader.close() REMOVED (handled by __exit__)
```

### Ablation Loop Wrapping Target
```python
# BEFORE: models/train_xgboost.py _run_ablation() line ~590
for toggle in toggles:
    config = FeatureConfig()
    setattr(config, toggle, False)
    loader = DataLoader(args.data, feature_engineer=TFTFeatureEngineer(config=config))
    # ... training and metric collection ...

# AFTER:
for toggle in toggles:
    config = FeatureConfig()
    setattr(config, toggle, False)
    with DataLoader(args.data, feature_engineer=TFTFeatureEngineer(config=config)) as loader:
        # ... same training and metric collection, indented ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Bare resource construction + manual close() | Context manager `with` statement | Python 2.5+ (PEP 343) | Guaranteed cleanup on exceptions; standard Python idiom |
| Custom exception hierarchy for all layers | Stdlib exceptions with narrow handlers | Phase 1 (this project) | Simpler, stdlib types work for internal codebase |

**Deprecated/outdated:**
- `models/exceptions.py`: Created Phase 1 "for downstream phases to import" but no downstream phase ever used it. All 32 requirements satisfied with stdlib exceptions. Remove.

## Discretion Recommendations

Based on CONTEXT.md discretion areas:

### exceptions.py Fate
**Recommendation: DELETE as dead code.**
- Zero production imports confirmed by grep and audit
- Codebase is internal-only (no external callers)
- All 32 requirements satisfied with stdlib exceptions
- No concrete future use case identified
- Phase 1 VERIFICATION explicitly noted it was unused
- Keeping dead code increases maintenance burden

### Decision Tracing
**Recommendation: Add a brief note to the Phase 14 SUMMARY (not PROJECT.md).**
- The deletion is small (26 LOC) and inconsequential to architecture
- PROJECT.md key decisions are for choices that constrain future phases
- There are no future phases in this milestone
- The audit trail (Phase 1 VERIFICATION noting it unused + Phase 14 SUMMARY noting removal) is sufficient

### DataLoader Context Manager Scope
**Recommendation: Wire BOTH sites.**
- main() at line ~757: Primary entrypoint, creates pool for parallel vectorization. Currently has `loader.close()` at end but no protection against exception-path leaks.
- _run_ablation() at line ~590: Creates DataLoader per ablation toggle iteration. No close() call at all. Each creates a potentially live pool via `_effective_workers()` -> `_ensure_pool()`.
- Wiring both is 5 minutes of work and eliminates all resource leak paths.

### Documentation Sync Depth
**Recommendation: Fix all identified stale items systematically.**

Items to fix in REQUIREMENTS.md:
1. Coverage section: Change "Complete: 29, Pending: 3" to "Complete: 32, Pending: 0"
2. Remove the "(OBSV-01, OBSV-02, OBSV-03 -- Phase 13)" note

Items to fix in ROADMAP.md:
1. Phase summary checkboxes: Check phases 2, 3, 4, 5, 6, 8, 9 (add `[x]` and completion dates)
2. Plan checkboxes: Check all completed plans (01-01, 02-01, 02-02, 03-01, 03-02, 04-01, 04-02, 05-01, 06-02, 08-01, 08-02, 09-01, 10-01, 10-02, 11-01, 11-02, 12-01, 12-02, 13-01)
3. Phase 14 status: Update from "0/TBD" after planning

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | pytest.ini |
| Quick run command | `python -m pytest tests/test_data_loader.py -x` |
| Full suite command | `python -m pytest` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RSMG-01 | DataLoader context manager cleans up pool | unit | `python -m pytest tests/test_data_loader.py::test_context_manager_normal_exit tests/test_data_loader.py::test_context_manager_exception_exit -x` | Yes |
| RSMG-02 | __exit__ does not mask original exception | unit | `python -m pytest tests/test_data_loader.py::test_context_manager_exception_exit -x` | Yes |
| EXCP-02 | exceptions.py removed (dead code) | smoke | `python -c "import models.exceptions" 2>&1 \| grep -q "ModuleNotFoundError"` or absence check | No (verify by file absence) |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_data_loader.py -x && ruff check models/train_xgboost.py && ruff format --check models/train_xgboost.py`
- **Per wave merge:** `python -m pytest && ruff check . && ruff format --check .`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
None -- existing test infrastructure covers all phase requirements. The DataLoader context manager tests already exist from Phase 3. No new test files needed. The exceptions.py removal is verified by file absence + import failure.

## Open Questions

1. **Does the ablation DataLoader actually create a pool?**
   - What we know: `_run_ablation` uses default `n_workers=0`, which resolves to `min(cpu_count, 64)` workers. Pool creation is lazy (only in `_ensure_pool`). The `load_fight_prediction_data()` call path goes through `_vectorize_rows()` which calls `_ensure_pool()` if `len(rows) >= 500` and `workers > 1`.
   - What's unclear: Whether typical ablation datasets exceed 500 rows. On production gate B data (50k+ games), they certainly do.
   - Recommendation: Wire `with` regardless. It costs nothing and prevents leaks on any dataset size.

## Sources

### Primary (HIGH confidence)
- `models/data_loader.py` lines 69-157 -- DataLoader class with context manager implementation
- `models/train_xgboost.py` lines 572-659, 737-978 -- Production usage sites
- `models/exceptions.py` -- Full 26-line dead code module
- `tests/test_data_loader.py` lines 229-260 -- Existing context manager + resource warning tests
- `.planning/v1.0-MILESTONE-AUDIT.md` -- Audit confirming all 3 gaps

### Secondary (MEDIUM confidence)
- `.planning/ROADMAP.md` -- Current stale checkbox state (verified by line-by-line reading)
- `.planning/REQUIREMENTS.md` lines 132-137 -- Stale coverage section (verified by reading)

### Tertiary (LOW confidence)
- None. All findings verified from primary sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- No new libraries; pure Python context manager pattern
- Architecture: HIGH -- DataLoader context manager already implemented and tested
- Pitfalls: HIGH -- All pitfalls verified from reading actual source code
- Documentation fixes: HIGH -- Exact stale items enumerated from reading ROADMAP.md and REQUIREMENTS.md

**Research date:** 2026-03-02
**Valid until:** 2026-04-02 (30 days -- stable internal codebase, no external dependency changes)
