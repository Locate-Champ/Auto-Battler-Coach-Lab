# Feature Research

**Domain:** Production Python codebase reliability improvements
**Researched:** 2026-02-27
**Confidence:** HIGH (grounded in direct codebase analysis + verified industry patterns)

---

## Feature Landscape

### Table Stakes (Must Have for Production Reliability)

Features that any production Python codebase is expected to have. Missing them means the system silently misbehaves or becomes impossible to debug.

| Feature | Why Expected | Complexity | Concerns Addressed |
|---------|--------------|------------|--------------------|
| Specific exception handling (no bare `except`) | Broad catches hide the actual failure — a `TypeError` is not the same as a `FileNotFoundError`; catching both identically is a bug factory | LOW | CONCERNS #3 (39 broad `except Exception`/bare `except` instances in simulator, models, coach) |
| Observable fallbacks (log before degrading) | Every time the system silently drops to a slower or weaker code path, a developer loses hours debugging phantom performance | LOW | CONCERNS #4 (Cython fallback silent), #6 (pickle fallback ~30ms penalty silent) |
| Explicit dependency validation at startup | Missing `pyarrow` silently returns empty iterators — training on zero rows produces a valid-looking model with garbage weights | LOW | CONCERNS #7 (pyarrow optional, silent empty iterator), #10 (Rust extension missing) |
| Context manager for resource-owning classes | `DataLoader` holds a live multiprocessing pool; if `close()` is never called, worker processes leak — common in notebooks and test runners | LOW | CONCERNS #9 (DataLoader pool not auto-closed) |
| Fail-fast on missing critical data files | `_load_combat_data()` raises a `FileNotFoundError` with no context; users see a traceback into internals rather than a helpful message | LOW | CONCERNS #13 (combat_data.json missing produces unclear error) |
| Type-correct return values on public API contracts | `RuntimeEvaluator.check_compatibility()` returns `None` where the signature implies a boolean pass/fail result — callers cannot act on it | LOW | CONCERNS #11 (check_compatibility returns None) |
| Structured logging with named loggers per module | `print()` calls in startup code (server.py) are invisible to log aggregators; production requires `logging.getLogger(__name__)` | LOW | CONCERNS #12 (API server uses print() for startup), CONCERNS #4 |
| Input schema validation at pipeline entry points | Feature extraction silently corrupts features when input column names are renamed — the model trains on wrong dimensions | MEDIUM | CONCERNS #14 (FeatureEngineer.transform_batch requires exact column names with no validation) |

### Differentiators (Best-in-Class Observability and Maintainability)

Features that raise the codebase above baseline reliability — not assumed, but valuable for a ML + simulation system that runs at scale.

| Feature | Value Proposition | Complexity | Concerns Addressed |
|---------|-------------------|------------|--------------------|
| Class-based runner with instance-scoped state | Module-level globals (`_RUST_FULL_SIMULATOR`, `_RUST_PARQUET_API_VALIDATED`) are non-reentrant and persist across test invocations — a class makes the boundary explicit and testable without module reloads | MEDIUM | CONCERNS #2 (cloud_runner global state), #5 (API server global model state) |
| FastAPI lifespan-scoped model loading with startup failure gate | Using `@app.on_event("startup")` does not prevent endpoints from being reached if startup silently fails; the `lifespan` context manager + startup failure gate ensures no endpoint serves a `None` model | MEDIUM | CONCERNS #12 (API server globals, partial startup does not fail routes) |
| SklearnEvaluator feature extraction wired and tested | The ML-backed board evaluation path is entirely non-functional today; wiring it with unit tests unlocks the full coach evaluation pipeline | HIGH | CONCERNS #1 (SklearnEvaluator NotImplementedError), CONCERNS #8 (untested code path) |
| Rust extension pre-flight check (arch + interpreter match) | Without a pre-flight check, a mismatched Rust build produces a confusing import error rather than a clear rebuild instruction | LOW | CONCERNS #10 (Rust extension missing/wrong arch) |
| Magic numbers extracted to config dataclass | Constants like `DEFAULT_STAGE_DIVISOR=7` and trait breakpoint weights are scattered across feature_engineering.py with no rationale — moving them to a `FeatureConfig` dataclass makes tuning safe and documented | LOW | CONCERNS #15 (hard-coded magic numbers in feature engineering) |
| Monolithic file split with documented module boundaries | 5.9k-LOC `champion_abilities.py` and 5.3k-LOC `combat_engine.py` each bundle multiple concerns — splitting into focused modules (<1k LOC each) reduces cognitive load and test surface | HIGH | CONCERNS #5 (large monolithic files) |

### Anti-Features (Deliberately NOT to Do During Cleanup)

Things that are commonly reached for during cleanup but create more problems than they solve in this context.

| Anti-Feature | Why Requested | Why Problematic | What to Do Instead |
|--------------|---------------|-----------------|---------------------|
| Replace `logging` with a third-party structured logging library (structlog, loguru) | Structlog/loguru give JSON output and context binding out of the box | Adds a new runtime dependency; existing code uses stdlib `logging` throughout; migration is cosmetic, not functional | Use stdlib `logging.getLogger(__name__)` consistently; add `%(module)s` and level to the format string — that is sufficient for this codebase |
| Add a formal dependency injection framework (dependency-injector, lagom) | DI frameworks make wiring explicit and mockable | Heavyweight for the scope of the issue; the real problem is `global` mutation, which is fixed by passing state through constructors | Refactor to class constructors and `FastAPI.state` / `Depends()` — manual DI is correct here |
| Introduce Pydantic models for all internal data structures | Pydantic validates at runtime and gives good error messages | The internal data pipeline uses numpy arrays and dataclasses; retrofitting Pydantic on `transform_batch()` inputs would require pervasive type changes and risks breaking the Cython fast path | Use `pandera` or a lightweight schema check (assert expected columns present) at the one entry point that is actually broken |
| Rewrite SklearnEvaluator as a full ML inference service | The existing placeholder raises NotImplementedError; "properly" fixing it might mean adding a model server | This is cleanup, not new feature work; the fix scope is: extract features from `GameState` using the same schema as training, call `model.predict_proba()`, return a float | Wire the existing pipeline; do not introduce a new model-serving layer |
| Add retry logic to all exception handlers | Retries are intuitive when something fails | Retries on `ImportError` or `FileNotFoundError` are meaningless — these are permanent failures. Retries on transient network errors (cloud_runner S3 uploads) are already handled by boto3 | Fail fast on permanent errors; let transient errors surface or use existing boto3 retry config |
| Wrap all 39 broad `except` blocks in a single pass | Seems efficient — one PR fixes all 39 | Mass exception narrowing without understanding each site risks silently suppressing errors that were being caught for good reasons, or changing silent-pass to log-and-pass without a test to cover the new path | Fix by layer in order of risk: models first (training on bad data), simulator second (determinism risk), coach last (heuristic fallbacks are intentional) |

---

## Feature Dependencies

```
[Explicit dependency validation at startup]
    └──enables──> [Input schema validation at pipeline entry points]
                      └──requires──> [Structured logging with named loggers]

[Specific exception handling]
    └──enables──> [Observable fallbacks (log before degrading)]

[Context manager for DataLoader]
    └──independent of other table stakes items

[Class-based runner with instance-scoped state]
    └──enables──> [FastAPI lifespan-scoped model loading]
    └──requires──> [Specific exception handling] (refactor happens alongside narrowing)

[Monolithic file split]
    └──requires──> [Specific exception handling] (split must not introduce new broad catches)
    └──requires──> determinism verification after every structural change

[SklearnEvaluator feature extraction wired]
    └──requires──> [Input schema validation at pipeline entry points] (must match training schema)
    └──requires──> [Explicit dependency validation at startup] (joblib must be present)
```

### Dependency Notes

- **Explicit dependency validation requires structured logging:** The validation function needs a logger to report which dependency is missing and what action to take. Without named loggers, validation warnings are invisible in production.
- **Monolithic file split requires specific exception handling first:** Splitting `combat_engine.py` while it still has broad `except Exception` blocks embeds the anti-pattern into the new file structure. Fix exception handling in the file before splitting it.
- **SklearnEvaluator wiring requires input schema validation:** The feature extraction pipeline must validate that the `GameState` columns match the training schema before calling `model.predict_proba()`, otherwise the model silently receives wrong-dimension vectors.
- **Class-based runner does not block other work:** The `cloud_runner.py` global state refactor is self-contained. All other table stakes items can proceed in parallel.

---

## MVP Definition

### Launch With (v1 — Table Stakes)

These unblock the most dangerous failure modes first: silent training on empty data, silent performance degradation, and leaked worker processes.

- [ ] Explicit dependency validation for pyarrow (raises on missing, not silent empty iterator) — prevents training on zero rows
- [ ] Specific exception handling in models layer (feature_engineering.py, data_loader.py, train_xgboost.py) — highest risk, affects data quality
- [ ] Observable fallbacks: log at WARNING when Cython falls back to pure Python; log at WARNING when pickle falls back to disk init — makes degraded mode visible
- [ ] Context manager for DataLoader (`__enter__`/`__exit__`) — prevents worker process leaks in notebooks and test runners
- [ ] Fail-fast for missing combat_data.json with an actionable error message — replaces cryptic traceback with a clear instruction
- [ ] Type-correct `check_compatibility()` return value — remove the `return None` anti-pattern

### Add After Validation (v1.x — Differentiators, Lower Risk)

- [ ] Rust extension pre-flight check — improves developer experience on arch/interpreter mismatch
- [ ] Magic numbers extracted to FeatureConfig dataclass — enables safe tuning
- [ ] Specific exception handling in simulator and coach layers — second pass after models layer is clean
- [ ] FastAPI lifespan model loading with startup failure gate — prevents `None` model serving

### Future Consideration (v2+ — High Complexity)

- [ ] Class-based cloud_runner (global state refactor) — medium complexity, touches production batch pipeline; validate table stakes fixes first
- [ ] Monolithic file splits (champion_abilities, combat_engine, feature_engineering, cloud_runner) — highest complexity; each requires determinism verification; defer until all exception handling is correct in the files being split
- [ ] SklearnEvaluator feature extraction wired — highest effort; depends on schema validation being in place and requires test coverage

---

## Feature Prioritization Matrix

| Feature | Reliability Value | Implementation Cost | Priority |
|---------|------------------|---------------------|----------|
| Explicit dependency validation (pyarrow, joblib) | HIGH — silent empty training is a data correctness bug | LOW — 5–10 lines per site | P1 |
| Specific exception handling — models layer | HIGH — overly broad catches hide import errors and version mismatches | LOW — narrow to ImportError/AttributeError at each site | P1 |
| Observable fallbacks (Cython, pickle) | HIGH — performance regressions are invisible without logs | LOW — add `_log.warning(...)` before fallback path | P1 |
| Context manager for DataLoader | HIGH — process leaks in test runners cause flaky CI | LOW — implement `__enter__`/`__exit__` | P1 |
| Fail-fast for missing combat_data.json | MEDIUM — affects simulation startup clarity | LOW — add existence check at `_load_combat_data()` | P1 |
| Type-correct check_compatibility() | LOW — type contract clarity, not a live failure | LOW — remove `return None` or implement bool check | P2 |
| Rust extension pre-flight check | MEDIUM — developer experience on arch mismatch | LOW — check `sys.version_info` + extension metadata | P2 |
| FastAPI lifespan model loading | MEDIUM — prevents `None` model serving under abnormal startup | MEDIUM — refactor to `lifespan` context manager | P2 |
| Magic numbers to FeatureConfig dataclass | LOW — maintainability, not a correctness bug | LOW — mechanical extract | P2 |
| Specific exception handling — simulator/coach | MEDIUM — fallbacks are partially intentional in coach | LOW | P2 |
| Class-based cloud_runner state refactor | MEDIUM — non-reentrant globals are a real issue in batch testing | MEDIUM | P2 |
| Monolithic file splits | MEDIUM — maintainability, determinism risk | HIGH — each split requires benchmark verification | P3 |
| SklearnEvaluator feature extraction wired | HIGH — unlocks ML evaluation path | HIGH — requires schema alignment with training | P3 |

---

## Sources

- Direct codebase analysis: `models/data_loader.py`, `models/feature_engineering.py`, `coach/scoring/evaluator.py`, `app/api/server.py`, `simulator/cloud_runner.py`, `simulator/benchmark.py` (HIGH confidence — primary source)
- `.planning/codebase/CONCERNS.md` — codebase audit with 18 identified concerns (HIGH confidence — authoritative)
- Python logging HOWTO: https://docs.python.org/3/library/logging.html (HIGH confidence — official docs)
- FastAPI dependency injection patterns: https://fastapi.tiangolo.com/tutorial/dependencies/ (HIGH confidence — official docs)
- Python exception handling best practices: https://blog.miguelgrinberg.com/post/the-ultimate-guide-to-error-handling-in-python (MEDIUM confidence — verified with official docs)
- Python context managers: https://realpython.com/python-with-statement/ (MEDIUM confidence — established reference)
- DI refactoring: https://maximilianocontieri.com/refactoring-024-replace-global-variables-with-dependency-injection (MEDIUM confidence — pattern well-established, multiple sources agree)

---
*Feature research for: Production Python codebase reliability improvements*
*Researched: 2026-02-27*
