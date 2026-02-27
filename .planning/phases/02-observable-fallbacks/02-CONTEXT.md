# Phase 2: Observable Fallbacks - Context

**Gathered:** 2026-02-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire logging.WARNING for all silent performance-degradation paths in the models layer so developers can see when the system runs on slower fallbacks. Replace all print() calls in models/ with proper logging. No new features, no scope beyond `models/**/*.py`.

</domain>

<decisions>
## Implementation Decisions

### Warning message content
- Include estimated performance penalty in fallback warnings (e.g., "~30x slower", "~2x slower")
- Include remediation/fix hints (e.g., "pip install pyarrow", "rebuild Cython with: python setup.py build_ext")
- Emit fallback warnings once at import/initialization time, not on every activation — no log spam during training loops
- Convert `warnings.warn()` in `fe_fast/__init__.py` to `logging.warning()` for consistency — all fallback diagnostics go through the logging module

### print() replacement mapping
- Training metrics output (accuracy, MAE, confusion matrices) → `logger.info()`
- Progress/status prints (labeling mode, epoch/batch progress) → `logger.info()`
- File save confirmations ("Saved model -> path") → `logger.info()`
- Disguised warnings (e.g., "Warning: unable to remove cache dir") → `logger.warning()`

### Log level assignment
- Scope: models layer only (`models/**/*.py`) — simulator/coach print() cleanup deferred to Phase 9
- Per-module loggers: each module uses `_log = logging.getLogger(__name__)`, no root logger configuration in library code
- Entry points (`train_xgboost.py`, `train_transformer.py`) add `logging.basicConfig()` in their `if __name__ == '__main__':` blocks so logger output is visible when run directly
- Library modules (data_loader.py, feature_engineering.py, dataset.py, evaluate.py) do NOT configure basicConfig — formatting is the caller's responsibility

### Claude's Discretion
- Per-fallback log level for non-performance fallbacks (e.g., torch not found on CPU box) — assign WARNING or INFO based on whether the fallback is expected vs unexpected in context
- Exact performance penalty estimates where not documented in code — use reasonable approximations
- Whether any existing print() calls should be logger.debug() instead of info() — use judgment for truly verbose per-batch output

</decisions>

<specifics>
## Specific Ideas

- The Cython fallback warning already exists as `warnings.warn()` with good text — convert to logging.warning() and enhance with performance estimate
- DataLoader pickle fallback already logs via `_log.warning()` (added in Phase 1 exception hardening) — verify it includes the ~30x estimate, add if missing
- train_xgboost.py:460 `print(f"Warning: ...")` is the clearest candidate for logger.warning()

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-observable-fallbacks*
*Context gathered: 2026-02-27*
