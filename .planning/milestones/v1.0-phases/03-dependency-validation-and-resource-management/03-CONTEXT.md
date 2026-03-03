# Phase 3: Dependency Validation and Resource Management - Context

**Gathered:** 2026-02-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Catch missing runtime dependencies (pyarrow, combat_data.json, Rust extension) at startup with actionable error messages instead of at use-time as silent empty results. Make DataLoader a context manager that cleans up worker pools automatically. No new features — only making existing failure paths explicit and resources properly managed.

</domain>

<decisions>
## Implementation Decisions

### Failure timing
- All three dependency checks happen at **import-time** (module load), not at first use
- pyarrow missing = **hard crash** (ImportError). No degraded mode — there is no meaningful DataLoader without pyarrow
- combat_data.json missing = **hard crash** at module import of simulator.core. Fail before any game logic runs
- Rust extension missing = **import-time with fallback**. Log WARNING and fall back to Python engine (consistent with Phase 2 fallback logging pattern)

### Error messaging
- All error messages include **actionable fix instructions**, not just the problem description
- pyarrow: include `pip install` command AND minimum version constraint from project requirements
  - Example: "pyarrow is required for DataLoader. Install: pip install pyarrow>=14.0. Without it, the data pipeline silently returns empty iterators."
- combat_data.json: include the **expected file path** AND the **regeneration command**
  - Example: "combat_data.json not found at {path}. Regenerate with: python -m simulator.generate_combat_data"
- Rust extension: include the **specific error**, **performance penalty**, AND **rebuild command**
  - Example: "Rust extension failed to load ({error}). Falling back to Python engine (~Nx slower). Rebuild: maturin develop --release"

### DataLoader cleanup
- Context manager (`with DataLoader(...) as dl:`) is the preferred usage pattern
- **Backward compatible**: standalone `DataLoader()` still works with explicit `.close()`. Existing code does not break
- On exception in `with` block: **always re-raise** the original exception after cleanup. Never suppress errors
- If worker pool shutdown itself fails during `__exit__`: **log WARNING and continue**. The original error is more important than a cleanup failure
- If DataLoader is garbage-collected without being closed: emit **ResourceWarning** (like Python's unclosed file warning). Helps catch leaked worker pools

### Rust pre-flight scope
- Pre-flight verifies **import + architecture match** (catches stale cross-compiled binaries), not just bare importability
- Rust extension module exposes a **`__version__` attribute** for programmatic version comparison
- Version mismatch (old extension vs expected) = **WARNING**, not error. Old extension still works, just may be slower or missing optimizations. Don't block execution

### Claude's Discretion
- Exact wording of error messages beyond the patterns above
- How architecture match detection works internally (platform module, struct size check, etc.)
- ResourceWarning implementation details in DataLoader.__del__
- Whether combat_data.json check uses a sentinel import or a file existence check

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. The key principle is: every silent failure path identified in the audit must become an explicit, actionable error or logged warning.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-dependency-validation-and-resource-management*
*Context gathered: 2026-02-27*
