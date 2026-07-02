# Phase 1: Models Exception Hardening - Context

**Gathered:** 2026-02-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Narrow all broad and bare exception handlers in the ML models layer to specific exception types, making training failures visible instead of silently swallowed. This covers all Python files under `models/` including subdirectories. No new features, no new dependencies — only exception handler changes and a new exceptions module.

</domain>

<decisions>
## Implementation Decisions

### Exception naming strategy
- Create a custom exception hierarchy in `models/exceptions.py`
- Two levels: `ModelsPipelineError` base class with subclasses `DataLoadError`, `FeatureEngineeringError`, `TrainingError`
- Callers can catch at any granularity (base class or specific subclass)

### File scope boundary
- Sweep ALL `models/**/*.py` files, not just the 3 named in success criteria
- Explicitly includes: `feature_engineering.py`, `data_loader.py`, `train_xgboost.py`, `dataset.py`, `train_transformer.py`, `evaluate.py`, `transformer.py`, `fe_fast/__init__.py`
- Any file under `models/` with a broad except gets hardened in this phase
- `fe_fast/` Cython extension import fallback is in scope (narrow to `ImportError`/`OSError`)

### Crash vs fallback policy
- **General policy: lean toward fail loud.** Default to crashing with a clear error. Only keep fallbacks when there's a genuine degraded-but-useful mode.
- **torch/CUDA detection** (`train_xgboost.py`): Narrow to `ImportError`, log that torch wasn't found and falling back to CPU
- **torch.compile** (`train_transformer.py`): Already logs a warning — narrow the exception type from `Exception` to the specific torch error types
- **pyarrow import** (`data_loader.py`, `dataset.py`): Claude's discretion on crash vs fallback (Phase 3 adds startup validation anyway, so narrowing the except type may be sufficient here)
- **Simulator item data** (`feature_engineering.py:505`): Claude's discretion on crash vs fallback based on how critical the data is to feature quality

### Claude's Discretion
- Whether custom exceptions carry structured context fields (e.g., `file_path`, `batch_index`) or just descriptive string messages — decide based on what the error paths actually need
- Pyarrow import: crash at import vs narrow-and-fallback (Phase 3 adds the explicit startup check regardless)
- Simulator item data loading: crash vs logged degraded mode based on feature quality impact
- Exact exception type narrowing for each handler (which specific builtins to catch)

</decisions>

<specifics>
## Specific Ideas

- The hierarchy should be shallow and practical — `ModelsPipelineError > DataLoadError/FeatureEngineeringError/TrainingError` — no deeper nesting
- When in doubt on a specific handler, fail loud. The user prefers visible failures over silent degradation.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-models-exception-hardening*
*Context gathered: 2026-02-27*
