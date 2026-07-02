# Phase 1: Models Exception Hardening - Research

**Researched:** 2026-02-27
**Domain:** Python exception handling, Ruff BLE001 linting, ML pipeline error patterns
**Confidence:** HIGH

## Summary

This phase requires narrowing 5 broad `except Exception:` handlers across 4 files in `models/` to specific exception types, plus widening 2 Cython/extension import handlers from `except ImportError:` to `except (ImportError, OSError):`. A new `models/exceptions.py` module introduces a shallow custom hierarchy (`ModelsPipelineError > DataLoadError / FeatureEngineeringError / TrainingError`). The scope is surgical: change exception types, add a small module, verify with `ruff check models/ --select BLE001` showing zero violations.

The ruff BLE001 rule flags `except Exception:` and `except BaseException:` but exempts handlers that re-raise or log with `exc_info=True`. Current ruff config (`ruff.toml`) selects `["E", "F", "W", "I"]` and does NOT include `BLE`. Phase 6 (EXCP-05) will permanently enable BLE in `ruff.toml`; this phase only needs to ensure zero violations when BLE001 is run ad-hoc against `models/`.

The 5 BLE001 violations are well-localized and each has a clear narrowing path. No new dependencies are needed. The main judgment calls are (a) whether the `feature_engineering.py:505` simulator-data import should crash or degrade, and (b) what specific exception types `torch.compile` raises on failure.

**Primary recommendation:** Fix all 5 BLE001 violations with specific exception types, widen 2 Cython import handlers to `(ImportError, OSError)`, create `models/exceptions.py` with the agreed hierarchy, and verify with `ruff check models/ --select BLE001`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Create a custom exception hierarchy in `models/exceptions.py`
- Two levels: `ModelsPipelineError` base class with subclasses `DataLoadError`, `FeatureEngineeringError`, `TrainingError`
- Callers can catch at any granularity (base class or specific subclass)
- Sweep ALL `models/**/*.py` files, not just the 3 named in success criteria
- Explicitly includes: `feature_engineering.py`, `data_loader.py`, `train_xgboost.py`, `dataset.py`, `train_transformer.py`, `evaluate.py`, `transformer.py`, `fe_fast/__init__.py`
- Any file under `models/` with a broad except gets hardened in this phase
- `fe_fast/` Cython extension import fallback is in scope (narrow to `ImportError`/`OSError`)
- **General policy: lean toward fail loud.** Default to crashing with a clear error. Only keep fallbacks when there's a genuine degraded-but-useful mode.
- **torch/CUDA detection** (`train_xgboost.py`): Narrow to `ImportError`, log that torch wasn't found and falling back to CPU
- **torch.compile** (`train_transformer.py`): Already logs a warning -- narrow the exception type from `Exception` to the specific torch error types
- **pyarrow import** (`data_loader.py`, `dataset.py`): Claude's discretion on crash vs fallback (Phase 3 adds startup validation anyway, so narrowing the except type may be sufficient here)
- **Simulator item data** (`feature_engineering.py:505`): Claude's discretion on crash vs fallback based on how critical the data is to feature quality

### Claude's Discretion
- Whether custom exceptions carry structured context fields (e.g., `file_path`, `batch_index`) or just descriptive string messages -- decide based on what the error paths actually need
- Pyarrow import: crash at import vs narrow-and-fallback (Phase 3 adds the explicit startup check regardless)
- Simulator item data loading: crash vs logged degraded mode based on feature quality impact
- Exact exception type narrowing for each handler (which specific builtins to catch)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| EXCP-01 | All 39 bare/broad exception handlers narrowed to specific exception types (per-site audit, not mass replacement) | Audit of `models/` found exactly 5 BLE001 violations across 4 files; each has a documented narrowing path in the Code Examples section. This phase addresses the models-layer subset of the 39 total. |
| EXCP-02 | Models layer exceptions (feature_engineering.py, data_loader.py, train_xgboost.py) use `except ImportError`, `except (ImportError, OSError)` for extensions, or other specific types | 5 broad handlers identified with specific replacement types; 2 Cython import sites need widening to `(ImportError, OSError)`. See Exception Handler Inventory below. |
</phase_requirements>

## Standard Stack

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| Ruff | 0.15.2 | Linting for BLE001 violations | Already in project, per CLAUDE.md verification rules |
| Python builtins | 3.11+ | `ImportError`, `OSError`, `RuntimeError`, `ValueError` etc. | Standard library exception types -- no deps needed |

### Supporting
| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| `logging` (stdlib) | 3.11+ | `logging.getLogger(__name__)` for fallback warnings | Already used in `data_loader.py` and `train_transformer.py` |
| `warnings` (stdlib) | 3.11+ | `warnings.warn()` for import-time fallbacks | Already used in `fe_fast/__init__.py` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom `models/exceptions.py` | Stdlib exceptions only | User locked the custom hierarchy decision; stdlib-only wouldn't support catching at `ModelsPipelineError` granularity |

**Installation:** No new packages required.

## Architecture Patterns

### Recommended Module Structure
```
models/
  exceptions.py          # NEW: ModelsPipelineError hierarchy
  feature_engineering.py  # Narrow except Exception at line 505
  data_loader.py          # Narrow except Exception at line 24
  dataset.py              # Narrow except Exception at line 20
  train_xgboost.py        # Narrow except Exception at line 48
  train_transformer.py    # Narrow except Exception at line 392
  fe_fast/__init__.py     # Widen ImportError to (ImportError, OSError)
```

### Pattern 1: Shallow Custom Exception Hierarchy
**What:** A base exception for the models pipeline with domain-specific subclasses.
**When to use:** When callers need to catch "any models error" or a specific sub-domain error.
**Example:**
```python
# models/exceptions.py
class ModelsPipelineError(Exception):
    """Base exception for all models-layer errors."""

class DataLoadError(ModelsPipelineError):
    """Error during data loading (Parquet, JSONL, splits)."""

class FeatureEngineeringError(ModelsPipelineError):
    """Error during feature extraction or transformation."""

class TrainingError(ModelsPipelineError):
    """Error during model training (XGBoost, Transformer)."""
```

**Discretion recommendation:** Use plain string messages, not structured context fields. The 5 error sites are import-time guards and simple fallbacks -- they don't carry batch indices or file paths that callers would programmatically inspect. Keep it simple.

### Pattern 2: Import-Time Fallback with Narrow Catch
**What:** Catching specific import/load errors when optional dependencies may be absent, with a logged fallback.
**When to use:** Optional dependency imports (pyarrow, torch, Cython extensions).
**Example:**
```python
import logging
_log = logging.getLogger(__name__)

try:
    import pyarrow.parquet as pq
except (ImportError, OSError):
    pq = None
    _log.info("pyarrow not available; Parquet loading disabled")
```

### Pattern 3: Extension Import with Architecture Safety
**What:** Catching both `ImportError` and `OSError` when importing compiled extensions.
**When to use:** Cython `.pyd`/`.so` imports where architecture mismatch can raise `OSError` (wrong ELF class, wrong DLL architecture).
**Example:**
```python
try:
    from .fe_fast import team_summary_fast, parse_units_column_fast
    CYTHON_AVAILABLE = True
except (ImportError, OSError):
    team_summary_fast = None
    parse_units_column_fast = None
    CYTHON_AVAILABLE = False
    warnings.warn("Cython fe_fast not available...", RuntimeWarning, stacklevel=2)
```

### Anti-Patterns to Avoid
- **`except Exception: pass`** -- swallows all errors including logic bugs. Always narrow the type and either log or re-raise.
- **Catching `Exception` when only `ImportError` is expected** -- silently hides `AttributeError`, `TypeError`, and other real bugs in the try block.
- **Adding `except (ImportError, OSError, RuntimeError, ValueError, AttributeError, ...):`** -- over-broad tuple catches are just `except Exception` with extra steps. Only catch types that the specific try block can actually raise.

## Exception Handler Inventory

Complete audit of all exception handlers in `models/`:

### BLE001 Violations (5 sites -- MUST FIX)

| # | File | Line | Current | Recommended Replacement | Rationale |
|---|------|------|---------|-------------------------|-----------|
| 1 | `data_loader.py` | 24 | `except Exception:` | `except (ImportError, OSError):` | Only `import pyarrow.parquet` can fail here; `ImportError` if missing, `OSError` if binary mismatch. Keep fallback (pq = None) since Phase 3 adds startup validation. |
| 2 | `dataset.py` | 20 | `except Exception:` | `except (ImportError, OSError):` | Identical pattern to data_loader.py. |
| 3 | `feature_engineering.py` | 505 | `except Exception: pass` | `except (ImportError, ModuleNotFoundError) as exc:` + `_log.debug(...)` | Try block imports `simulator.data.set16_items` and iterates its dicts. Import failure = `ImportError`/`ModuleNotFoundError`. If the import succeeds but data is malformed, that's a real bug that should crash. **Recommendation: narrow to import errors only, add debug log, let data bugs crash.** |
| 4 | `train_transformer.py` | 392 | `except Exception as e:` | `except RuntimeError as e:` | `torch.compile()` raises `RuntimeError` on failure (backend compilation errors, Triton unavailability, unsupported ops). The `torch._dynamo.exc` exception types are all subclasses of `RuntimeError`. Keeping the warning log is correct. |
| 5 | `train_xgboost.py` | 48 | `except Exception: pass` | `except ImportError:` + `_log.info("torch not available, defaulting to CPU")` | Only `import torch` can raise here; if torch imports but `cuda.is_available()` fails, that's a real bug. User locked: narrow to `ImportError`, add log. |

### Already-Narrow Handlers (no changes needed for BLE001)

| File | Line | Current | Status |
|------|------|---------|--------|
| `feature_engineering.py` | 26 | `except ImportError:` | OK but should widen to `(ImportError, OSError)` per success criteria #3 |
| `feature_engineering.py` | 112 | `except (TypeError, ValueError):` | Already specific |
| `feature_engineering.py` | 125 | `except (TypeError, ValueError):` | Already specific |
| `feature_engineering.py` | 140 | `except json.JSONDecodeError:` | Already specific |
| `data_loader.py` | 101 | `except (pickle.PicklingError, TypeError) as exc:` | Already specific |
| `data_loader.py` | 275 | `except ValueError:` | Already specific |
| `data_loader.py` | 307 | `except ValueError:` | Already specific |
| `data_loader.py` | 482 | `except ValueError:` | Already specific |
| `data_loader.py` | 505 | `except ValueError:` | Already specific |
| `data_loader.py` | 618 | `except ValueError:` | Already specific |
| `data_loader.py` | 639 | `except ValueError:` | Already specific |
| `data_loader.py` | 742 | `except ValueError:` | Already specific |
| `data_loader.py` | 757 | `except ValueError:` | Already specific |
| `train_xgboost.py` | 76 | `except xgb.core.XGBoostError:` | Already specific |
| `train_xgboost.py` | 106 | `except xgb.core.XGBoostError:` | Already specific |
| `train_xgboost.py` | 158 | `except ValueError:` | Already specific |
| `train_xgboost.py` | 439 | `except StopIteration:` | Already specific |
| `train_xgboost.py` | 456 | `except OSError as exc:` | Already specific |
| `train_transformer.py` | 32 | `except ImportError:` | Already specific |
| `fe_fast/__init__.py` | 16 | `except ImportError:` | OK but should widen to `(ImportError, OSError)` per success criteria #3 |

### Cython/Extension Import Widening (2 sites -- per success criteria #3)

| File | Line | Current | Recommended |
|------|------|---------|-------------|
| `fe_fast/__init__.py` | 16 | `except ImportError:` | `except (ImportError, OSError):` |
| `feature_engineering.py` | 26 | `except ImportError:` | `except (ImportError, OSError):` |

These are not BLE001 violations (they already catch specific types), but success criteria #3 explicitly requires `(ImportError, OSError)` for Cython/Rust extension imports to handle architecture-mismatch scenarios where a compiled `.so`/`.pyd` exists but has wrong ELF class or wrong DLL machine type.

### Files with Zero Exception Handlers (no work needed)

`evaluate.py`, `transformer.py`, `preprocess_tensors.py`, `counterfactual.py`, `embeddings.py`, `information_theory.py`, `trajectory.py`, `uncertainty.py`, `fe_fast/setup.py`

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Exception hierarchy | Multi-level deep hierarchy with error codes | Shallow 2-level hierarchy (base + 3 subclasses) | User locked this design. Deep hierarchies are over-engineering for 5 error sites. |
| BLE001 detection | Manual grep for `except Exception` | `ruff check models/ --select BLE001` | Ruff catches edge cases (re-raise exemptions, logging exemptions) that grep misses |
| Logging setup | Custom logging framework | `logging.getLogger(__name__)` | stdlib is explicitly in-scope per REQUIREMENTS.md; no third-party loggers (Out of Scope) |

**Key insight:** This phase is mechanical refactoring, not design work. Each of the 5 broad handlers has one correct narrowing based on what the try block actually does. The only creative work is the small `exceptions.py` module, which the user already designed.

## Common Pitfalls

### Pitfall 1: Over-Narrowing torch.compile Exceptions
**What goes wrong:** Catching only `RuntimeError` when `torch.compile` could raise other types (e.g., `TypeError` from invalid arguments, `AttributeError` from version mismatches).
**Why it happens:** `torch.compile` failure modes span TorchDynamo frontend, Inductor backend, and Triton compilation. Exception types vary by failure stage.
**How to avoid:** `RuntimeError` covers the vast majority of `torch.compile` failures since `torch._dynamo.exc` types inherit from `RuntimeError`. If edge cases emerge, they'll surface as visible crashes (which is the desired fail-loud behavior).
**Warning signs:** torch.compile crashing the training run instead of falling back to eager mode on a platform that previously worked.

### Pitfall 2: Breaking the pyarrow Optional Pattern
**What goes wrong:** Changing `pq = None` fallback to a crash, then breaking every code path that checks `if pq is not None:`.
**Why it happens:** Eager "fail loud" applied where graceful degradation is the correct pattern.
**How to avoid:** For pyarrow, keep `pq = None` fallback -- Phase 3 (DEPV-01) adds the explicit startup crash. This phase only narrows the exception TYPE, not the fallback BEHAVIOR.
**Warning signs:** `ModuleNotFoundError: pyarrow` in environments where pyarrow is intentionally optional.

### Pitfall 3: Silent pass After Narrowing
**What goes wrong:** Changing `except Exception: pass` to `except ImportError: pass` -- the handler is narrower but still silent. Success criteria #4 says "No silent pass or broad except in the models layer absorbs an error without re-raising or logging."
**Why it happens:** Focusing only on the exception TYPE and forgetting about the HANDLING.
**How to avoid:** Every narrowed handler must either (a) re-raise, (b) log at WARNING/INFO/DEBUG level, or (c) have a documented reason why silence is acceptable (none in this codebase).
**Warning signs:** `pass` on a line by itself after an except clause with no preceding log statement.

### Pitfall 4: Forgetting to Add models/exceptions.py to Imports
**What goes wrong:** Creating `models/exceptions.py` but not importing from it anywhere, making it dead code.
**Why it happens:** The 5 BLE001 fixes mostly use stdlib exception types. The custom hierarchy is for callers to catch models-layer errors, but there may be no raise sites yet in this phase.
**How to avoid:** Even if no code raises `DataLoadError` yet in Phase 1, the module must exist and be importable. Phase 2+ will add raise sites. Consider adding at least one raise site in this phase to validate the pattern end-to-end.
**Warning signs:** `models/exceptions.py` exists but nothing imports it.

### Pitfall 5: BLE001 Exemptions Masking Real Issues
**What goes wrong:** Assuming `logger.warning("...", e)` is equivalent to `logger.warning("...", exc_info=True)` for BLE001 exemption.
**Why it happens:** BLE001 specifically exempts logging calls with `exc_info=True` parameter, not just any logging call that mentions the exception variable.
**How to avoid:** The `train_transformer.py:392` handler uses `logger.warning("...: %s", e)` which does NOT qualify for the BLE001 exemption. It must be narrowed to a specific type regardless of the logging call.
**Warning signs:** BLE001 still fires after adding logging.

## Code Examples

### Creating models/exceptions.py
```python
# models/exceptions.py
"""Custom exceptions for the models pipeline.

Hierarchy:
    ModelsPipelineError
    +-- DataLoadError
    +-- FeatureEngineeringError
    +-- TrainingError
"""


class ModelsPipelineError(Exception):
    """Base exception for all errors in the models layer."""


class DataLoadError(ModelsPipelineError):
    """Raised when data loading fails (Parquet read, JSONL parse, splits)."""


class FeatureEngineeringError(ModelsPipelineError):
    """Raised when feature extraction or transformation fails."""


class TrainingError(ModelsPipelineError):
    """Raised when model training fails (XGBoost, Transformer)."""
```

### Fix 1: data_loader.py line 24 -- pyarrow import
```python
# BEFORE:
try:  # pragma: no cover - optional dependency
    import pyarrow.parquet as pq
except Exception:  # pragma: no cover - optional dependency
    pq = None

# AFTER:
try:  # pragma: no cover - optional dependency
    import pyarrow.parquet as pq
except (ImportError, OSError):  # pragma: no cover - optional dependency
    pq = None
```

### Fix 2: dataset.py line 20 -- pyarrow import (identical pattern)
```python
# BEFORE:
try:  # pragma: no cover - optional dependency
    import pyarrow.parquet as pq
except Exception:  # pragma: no cover - optional dependency
    pq = None

# AFTER:
try:  # pragma: no cover - optional dependency
    import pyarrow.parquet as pq
except (ImportError, OSError):  # pragma: no cover - optional dependency
    pq = None
```

### Fix 3: feature_engineering.py line 505 -- simulator item data
```python
# BEFORE:
        try:
            from simulator.data import set16_items  # type: ignore

            for internal_name, stats in set16_items.ALL_ITEMS.items():
                # ... iteration code ...
        except Exception:
            # Keep running even when simulator package import fails.
            pass

# AFTER:
        try:
            from simulator.data import set16_items  # type: ignore

            for internal_name, stats in set16_items.ALL_ITEMS.items():
                # ... iteration code ...
        except (ImportError, ModuleNotFoundError):
            # Simulator package not installed -- item alias enrichment skipped.
            # Features degrade slightly (fewer item name normalizations) but
            # the core pipeline remains functional.
            _log.debug("simulator.data.set16_items not available; skipping item alias enrichment")
```
**Note:** `feature_engineering.py` needs `import logging` and `_log = logging.getLogger(__name__)` added at module level (it currently has no logger).

### Fix 4: train_transformer.py line 392 -- torch.compile
```python
# BEFORE:
        try:
            model = torch.compile(model, mode="reduce-overhead")
            logger.info("Model compiled with torch.compile (reduce-overhead)")
        except Exception as e:
            logger.warning("torch.compile failed, using eager mode: %s", e)

# AFTER:
        try:
            model = torch.compile(model, mode="reduce-overhead")
            logger.info("Model compiled with torch.compile (reduce-overhead)")
        except RuntimeError as e:
            logger.warning("torch.compile failed, using eager mode: %s", e)
```

### Fix 5: train_xgboost.py line 48 -- torch/CUDA detection
```python
# BEFORE:
def _best_xgb_device() -> str:
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"

# AFTER:
import logging
_log = logging.getLogger(__name__)

def _best_xgb_device() -> str:
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        _log.info("torch not available; XGBoost will use CPU device")
    return "cpu"
```
**Note:** `train_xgboost.py` currently uses `print()` in a few places but has no logger. This fix adds one. Phase 2 (OBSV-03) will sweep all `print()` to `logging`.

### Widen 1: fe_fast/__init__.py line 16
```python
# BEFORE:
except ImportError:

# AFTER:
except (ImportError, OSError):
```

### Widen 2: feature_engineering.py line 26
```python
# BEFORE:
except ImportError:

# AFTER:
except (ImportError, OSError):
```

## Ruff BLE001 Rule Details

| Property | Value |
|----------|-------|
| Rule ID | BLE001 |
| Category | flake8-blind-except |
| Triggers on | `except Exception:`, `except BaseException:` |
| Does NOT trigger on | Handlers that re-raise, handlers with `logging.*(exc_info=True)` |
| Current ruff.toml select | `["E", "F", "W", "I"]` -- BLE not included |
| Phase 1 verification | `ruff check models/ --select BLE001` (ad-hoc) |
| Phase 6 permanent | Add `"BLE"` to ruff.toml select (EXCP-05) |

**Important:** BLE001 exempts handlers that re-raise or log with `exc_info=True`. Simple `logger.warning("...", e)` does NOT qualify for exemption. All 5 violations must be fixed by narrowing the exception type, not by adding `exc_info=True`.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `except Exception: pass` | Narrow catch + log/re-raise | Python community best practice since PEP 8 | Prevents swallowing `KeyboardInterrupt`, `SystemExit`, logic bugs |
| `except ImportError:` for extensions | `except (ImportError, OSError):` | Became common practice with cross-platform compiled extensions | Handles wrong-architecture `.so`/`.pyd` files that raise `OSError` instead of `ImportError` |
| Custom exception per error site | Shallow domain hierarchy | Modern Python convention | Callers catch at desired granularity without knowing implementation details |

## Discretion Recommendations

### Pyarrow import (data_loader.py:24, dataset.py:20)
**Recommendation: Narrow to `(ImportError, OSError)`, keep `pq = None` fallback.**
Rationale: Phase 3 (DEPV-01) adds the explicit startup crash. Changing the fallback behavior here creates unnecessary risk of breaking existing workflows where pyarrow is intentionally absent. Narrowing the exception type is sufficient for EXCP-02.

### Simulator item data (feature_engineering.py:505)
**Recommendation: Narrow to `(ImportError, ModuleNotFoundError)`, add debug log, let data-structure bugs crash.**
Rationale: The try block does two things: (1) import `simulator.data.set16_items`, (2) iterate its dictionaries. Import failure is expected (training can run without the simulator package). But if the import succeeds and the data structures are malformed (`AttributeError`, `KeyError`, `TypeError`), that's a real bug that should surface. The enrichment adds supplementary item aliases -- useful but not critical for core features. Debug-level logging is appropriate since this fires every time `TFTFeatureEngineer.__init__` runs.

### Custom exception context fields
**Recommendation: Plain string messages only, no structured fields.**
Rationale: The 5 error sites in this phase are import guards and fallback handlers. None of them construct error objects with batch indices or file paths. The custom hierarchy exists for catch granularity, not for carrying structured error context. If future phases need structured context (e.g., `DataLoadError(file_path=..., batch_index=...)`), it can be added then without breaking the existing interface.

## Open Questions

1. **Does `torch.compile` ever raise non-RuntimeError exceptions?**
   - What we know: `torch._dynamo.exc` exception types (`BackendCompilerFailed`, `InternalTorchDynamoError`, `TorchRuntimeError`, `Unsupported`) all appear to be RuntimeError subclasses based on community reports and GitHub issues.
   - What's unclear: Whether edge cases (e.g., missing Triton on Windows, CUDA version mismatch) raise a different exception type.
   - Recommendation: Use `except RuntimeError` -- this is the fail-loud philosophy. If a non-RuntimeError occurs, it should crash visibly rather than silently fall back to eager mode. If a real edge case surfaces in production, widen then.

2. **Should `models/exceptions.py` have any raise sites in this phase?**
   - What we know: The 5 BLE001 fixes use stdlib exceptions (`ImportError`, `RuntimeError`, etc.), not custom exceptions. The custom hierarchy is designed for callers.
   - What's unclear: Whether having a module with no raise sites in Phase 1 feels incomplete.
   - Recommendation: Create the module and make it importable. Phase 2 (OBSV-01 through OBSV-03) and Phase 3 (DEPV-01 through DEPV-03) will add raise sites. Having the hierarchy defined first is correct sequencing.

## Sources

### Primary (HIGH confidence)
- [Ruff BLE001 official docs](https://docs.astral.sh/ruff/rules/blind-except/) -- rule behavior, exemptions for re-raise and exc_info
- `ruff check models/ --select BLE001` run on codebase -- 5 violations confirmed
- Direct source code audit of all `models/**/*.py` files -- complete exception handler inventory

### Secondary (MEDIUM confidence)
- [PyTorch torch.compile troubleshooting](https://docs.pytorch.org/docs/stable/user_guide/torch_compiler/torch.compiler_troubleshooting.html) -- torch.compile failure modes
- [Cython troubleshooting](https://cython.readthedocs.io/en/latest/src/userguide/troubleshooting.html) -- extension import error types
- [Ruff GitHub issue #6421](https://github.com/astral-sh/ruff/issues/6421) -- BLE001 exemption behavior for logging

### Tertiary (LOW confidence)
- `torch._dynamo.exc` exception hierarchy inheriting from `RuntimeError` -- inferred from multiple GitHub issues, not confirmed in official docs. Treated as HIGH-confidence recommendation because fail-loud philosophy means we WANT non-RuntimeError exceptions to crash.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, ruff version verified, all exception types are stdlib
- Architecture: HIGH -- user locked the hierarchy design, patterns are mechanical refactoring
- Pitfalls: HIGH -- based on direct codebase audit, all sites enumerated with line numbers
- Discretion recommendations: MEDIUM -- pyarrow and simulator-data recommendations based on codebase reading and project context, not production telemetry

**Research date:** 2026-02-27
**Valid until:** 2026-03-27 (stable domain -- Python exception handling doesn't change often)
