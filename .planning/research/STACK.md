# Stack Research

**Domain:** Python codebase reliability, refactoring, and error handling
**Researched:** 2026-02-27
**Confidence:** HIGH (tools already in use; research validates current choices and adds targeted additions)

---

## Context

This is a subsequent milestone for a brownfield Python 3.11+ codebase. The existing stack (FastAPI, Pydantic, XGBoost, PyTorch, PyO3/Rust, Cython, ruff) is already established. This document focuses on the tools and patterns needed for the 18 specific reliability concerns identified in `.planning/codebase/CONCERNS.md`, not on greenfield stack selection.

The existing `ruff.toml` currently selects only `["E", "F", "W", "I"]`. It does not yet enable the `BLE` (blind-except) or `B` (bugbear) rule families. This is the single most important gap identified.

---

## Recommended Stack

### Core Technologies (Already in Use — Confirmed Correct)

| Technology | Version | Purpose | Why Correct for This Work |
|------------|---------|---------|--------------------------|
| ruff | 0.9+ | Linting + formatting | Already configured; add BLE/B rules to catch bare exceptions systematically |
| Pydantic v2 | 2.5.0+ | Schema validation | `model_validate(..., strict=True)` and `Field(strict=True)` catch type mismatches at pipeline entry; already a dep |
| pytest | 7.4.3+ | Behavior verification during refactors | Already configured; golden-output tests lock behavior before splits |
| Python `logging` stdlib | 3.11 | Structured fallback/warning logging | Standard library; no new dep needed; `logging.warning()` for Cython fallback paths |
| Python `contextlib` stdlib | 3.11 | Context managers | `@contextmanager` and `AbstractContextManager`; no new dep needed for DataLoader fix |

### Supporting Libraries (New Additions Justified)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pandera | 0.20+ | DataFrame / Arrow schema validation | Use at `transform_batch()` entry point to validate column presence before silent corruption occurs. Integrates with pandas and PyArrow. |
| syrupy | 4.x | Snapshot / golden-output testing | Use before every monolithic file split: capture outputs before, assert same outputs after. Prevents determinism regressions without writing full assertion trees. |
| inline-snapshot | 0.14+ | Inline snapshot assertions | Alternative to syrupy; better for smaller assertion sets where you want the expected value embedded in the test source. |

**Note on pandera vs. plain Pydantic for DataFrames:**
Pydantic validates row-by-row objects (dictionaries, dataclasses). Pandera validates columnar structures (pandas DataFrames, Arrow Tables) with column-level type, nullability, and value constraints. Use **Pydantic** for the API request/response layer and `SklearnEvaluator` feature vector schema. Use **pandera** for validating `transform_batch()` DataFrame inputs where column names and dtypes are the actual risk.

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| ruff (BLE001, E722, B) | Detect all 39 bare/broad except instances | Add `"BLE", "B"` to `[lint] select` in `ruff.toml`. BLE001 catches `except Exception:`. E722 catches bare `except:`. Enable per-file-ignores only where broad catches are genuinely intentional (e.g., Rust engine import in benchmark.py). |
| rope | AST-safe module splitting | Pure Python, no IDE required. Use `rope.refactor.move.MoveGlobal` to relocate classes/functions between modules while preserving imports. Required for champion_abilities.py (5.9k LOC) and combat_engine.py (5.3k LOC) splits. |
| pyright / pylsp | Type narrowing after refactors | Catches `check_compatibility() -> None` type contract violations statically. Already installable as a dev dependency; not required to be in CI but useful for validating None-return fixes. |

---

## Pattern Recommendations

### 1. Replacing Bare Exceptions — Specific Exception Types

**Confidence: HIGH** (Python documentation, PEP 20, ruff rules E722/BLE001)

**Pattern:** Replace `except Exception:` and bare `except:` with the narrowest applicable type. Log caught exceptions explicitly rather than silently swallowing.

```python
# BEFORE (current — 39 instances in codebase)
try:
    from .fe_fast import team_summary_fast as _cy_team_summary
except Exception:
    _cy_team_summary = None

# AFTER
import logging
_log = logging.getLogger(__name__)

try:
    from .fe_fast import team_summary_fast as _cy_team_summary
except ImportError as exc:
    _log.warning(
        "fe_fast Cython module unavailable, falling back to pure Python "
        "(performance will be ~5-10x slower). Reason: %s",
        exc,
    )
    _cy_team_summary = None
```

**Why `ImportError` not `Exception`:**
`ImportError` (and its subclass `ModuleNotFoundError`) is the only exception that can be raised by a failed import of an optional compiled extension. Using `except Exception` also catches `AttributeError`, `TypeError`, and any bug in the module's initialization code — masking real problems.

**For CUDA availability checks (`train_xgboost.py`):**
```python
# BEFORE
try:
    import torch
    CUDA_AVAILABLE = torch.cuda.is_available()
except Exception:
    CUDA_AVAILABLE = False

# AFTER
try:
    import torch
    CUDA_AVAILABLE = torch.cuda.is_available()
except ImportError:
    _log.info("torch not installed; CUDA unavailable (CPU training only)")
    CUDA_AVAILABLE = False
```

**Ruff enforcement:** Add `"BLE", "B"` to `[lint] select` in `ruff.toml`. Do not add per-file ignores unless you can document why broad catching is intentionally correct at that site.

---

### 2. Monolithic File Splits — Safe Procedure

**Confidence: HIGH** (rope documentation, Python packaging standards, multiple verified sources)

**The problem with naive splits:** Moving a class from `champion_abilities.py` to a new submodule and deleting it from the original file immediately breaks all callers that `from simulator.core.champion_abilities import X`.

**Safe split procedure (three-phase):**

**Phase A — Extract (no behavior change):**
1. Create the new submodule file (e.g., `simulator/core/abilities/bruisers.py`).
2. Move the target classes/functions there.
3. Add re-exports in the *original file*: `from .abilities.bruisers import BruiserAbilities  # noqa: F401`.
4. Run `python -m simulator.benchmark` — must pass.
5. Run `ruff check . && ruff format --check .` — must pass.
6. Commit as "extract: move BruiserAbilities to abilities/bruisers.py (re-exported for compatibility)".

**Phase B — Update callers (parallel):**
1. Use `grep -r "from simulator.core.champion_abilities import"` to find all call sites.
2. Update each caller to import from the new canonical location.
3. Run the full test suite after each batch.

**Phase C — Remove re-exports (cleanup):**
1. After all callers updated, remove the re-export lines from the original file.
2. Final benchmark + test run.

**Why this order:** Phase A guarantees zero behavior change — existing callers still work via re-exports. Phase B de-risks callers one at a time. Phase C is a pure cleanup with no functional impact.

**Circular import risk:** When splitting `combat_engine.py` and `champion_abilities.py`, both files likely reference each other. Mitigation:
- Create a shared `_types.py` or `_constants.py` in `simulator/core/` for any shared dataclasses/constants.
- Use `TYPE_CHECKING` guards for type-only imports.
- Keep ability *dispatch* in combat_engine; move only ability *implementations* to submodules.

**Tool — rope:** For IDE-agnostic refactoring, rope can be used programmatically:
```python
from rope.base.project import Project
from rope.refactor.move import create_move

project = Project(".")
resource = project.get_resource("simulator/core/combat_engine.py")
mover = create_move(project, resource, offset=<offset_of_class>)
changes = mover.get_changes("simulator/core/abilities/bruisers")
project.do(changes)
```
This updates all import references automatically. Use rope for large moves; manual re-export pattern for initial extraction.

---

### 3. Global State Elimination

**Confidence: HIGH** (FastAPI official docs — lifespan/app.state; Python multiprocessing docs)

#### 3a. FastAPI API Server (`app/api/server.py`)

**Current problem:** `recommender` and `placement_model` are module-level globals initialized in `@app.on_event("startup")` (deprecated). No validation that startup succeeded before endpoints accept requests.

**Recommended pattern — lifespan + app.state:**
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Raises on failure — endpoints never become available with None models
    recommender = TFTRecommender(str(data_dir))
    placement_model = PlacementModel(str(data_dir))
    app.state.recommender = recommender
    app.state.placement_model = placement_model
    yield
    # Cleanup on shutdown if needed

app = FastAPI(lifespan=lifespan)

# Dependency for injection
def get_recommender(request: Request) -> TFTRecommender:
    return request.app.state.recommender
```

**Why:** `@app.on_event("startup")` is deprecated since FastAPI 0.93. The `lifespan` pattern ensures any model load failure raises *before* the application starts serving, so endpoints never run with `None` models. `app.state` is the FastAPI-sanctioned location for shared singleton objects — not module globals.

#### 3b. Cloud Runner (`simulator/cloud_runner.py`)

**Current problem:** Module-level globals `_RUST_FULL_SIMULATOR` and `_RUST_PARQUET_API_VALIDATED` mutated via `global` keyword. Non-reentrant, cannot be tested without module reload.

**Recommended pattern — class-based runner:**
```python
@dataclass
class CloudRunnerState:
    rust_simulator: Optional[object] = None
    parquet_api_validated: bool = False

class CloudRunner:
    def __init__(self, config: RunnerConfig):
        self._state = CloudRunnerState()
        self._config = config

    def ensure_rust_simulator(self) -> object:
        if self._state.rust_simulator is None:
            self._state.rust_simulator = _build_rust_simulator(self._config)
        return self._state.rust_simulator
```

**Why:** Instance state is owned by the object, not the module. Multiple `CloudRunner` instances can coexist (needed for testing). Dependencies can be injected at construction time.

#### 3c. DataLoader Worker Pool

**Current problem:** Module-level `_worker_fe` global shared across workers; pickle failure silently downgrades to disk I/O.

**Recommended pattern — context manager with explicit failure:**
```python
class DataLoader:
    def __enter__(self) -> "DataLoader":
        self._pool = self._create_pool()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._pool is not None:
            self._pool.terminate()
            self._pool.join()
            self._pool = None
        return False  # do not suppress exceptions

    def _create_pool(self) -> multiprocessing.Pool:
        try:
            fe_bytes = pickle.dumps(self._fe)
            initializer = _init_fe_worker_pickled
            initargs = (fe_bytes,)
        except (pickle.PicklingError, AttributeError) as exc:
            _log.warning(
                "FeatureEngineer not picklable (%s); falling back to per-worker disk I/O "
                "(expect ~30ms latency per worker). Consider fixing __getstate__.",
                exc,
            )
            initializer = _init_fe_worker
            initargs = (self._config, self._repo_root)
        return multiprocessing.Pool(self._workers, initializer, initargs)
```

**Why context manager:** `multiprocessing.Pool` already supports `__enter__`/`__exit__` (calls `terminate()` on exit). Wrapping DataLoader as a context manager ensures the pool is always cleaned up, even on exceptions. This follows the Python stdlib pattern for resource-owning objects.

**Why explicit pickle fallback warning:** Silent 30x performance regressions are the most dangerous failure mode for training pipelines. The fallback is intentional but must be observable.

---

### 4. Schema Validation for Feature Engineering

**Confidence: MEDIUM-HIGH** (pandera docs confirmed; pattern matches codebase's pandas/Arrow usage)

**Current problem:** `transform_batch()` assumes specific column names. Missing or renamed columns produce silent feature corruption — wrong numbers, not errors.

**Two-layer approach:**

**Layer 1 — Pydantic for individual snapshot rows (dict inputs):**
```python
from pydantic import BaseModel, Field

class SnapshotRow(BaseModel):
    player_id: str
    stage: int = Field(ge=1, le=7)
    gold: int = Field(ge=0)
    level: int = Field(ge=1, le=10)
    units: list[dict]  # further validated downstream

    model_config = {"extra": "allow"}  # allow additional columns, validate required ones
```

**Layer 2 — pandera for Arrow/DataFrame batch inputs:**
```python
import pandera as pa
from pandera.typing import DataFrame

snapshot_schema = pa.DataFrameSchema(
    columns={
        "player_id": pa.Column(str, nullable=False),
        "stage": pa.Column(int, pa.Check.between(1, 7)),
        "gold": pa.Column(int, pa.Check.ge(0)),
        "level": pa.Column(int, pa.Check.between(1, 10)),
        "units": pa.Column(object),
    },
    strict=False,  # allow extra columns; only validate required ones
)

def transform_batch(self, df: pd.DataFrame) -> np.ndarray:
    try:
        snapshot_schema.validate(df, lazy=True)
    except pa.errors.SchemaErrors as exc:
        raise ValueError(
            f"transform_batch received invalid input schema: {exc.failure_cases}"
        ) from exc
    # ... existing logic
```

**Why `strict=False`:** The schema should validate *required* columns exist with correct types, not reject data with extra columns. Strict mode would break when new columns are added to the snapshot format.

**Why `lazy=True`:** Collect all validation errors at once rather than failing on the first bad column. Better developer experience when debugging a new data version.

---

### 5. Context Manager Pattern for DataLoader

**Confidence: HIGH** (Python stdlib documentation; multiprocessing.Pool is already a context manager)

Standard pattern for any resource-owning class in Python 3.11+:

```python
from contextlib import AbstractContextManager
from typing import Self

class DataLoader(AbstractContextManager):
    def __enter__(self) -> Self:
        self._ensure_pool()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.close()
        return False  # never suppress exceptions

    def close(self) -> None:
        """Explicit close — also callable without context manager."""
        if self._pool is not None:
            self._pool.terminate()
            self._pool.join()
            self._pool = None
```

**Keep `close()` as a standalone method** in addition to `__exit__`. Users in Jupyter notebooks who don't use `with` blocks should still have a way to clean up explicitly. `AbstractContextManager` from `contextlib` provides `__enter__` as a default (returns `self`) and provides the `@contextmanager` compatibility pattern if needed.

---

### 6. Rust Extension Pre-flight Check

**Confidence: MEDIUM** (PyO3 build docs + interpreter mismatch issue patterns)

**Pattern — validate at import time, fail fast with actionable message:**
```python
def _check_rust_extension() -> None:
    """Raise on Rust extension ABI mismatch with a rebuild hint."""
    import sys
    try:
        import tft_combat_engine as _rce
    except ImportError as exc:
        raise RuntimeError(
            f"Rust extension tft_combat_engine not found or not built for "
            f"Python {sys.version_info.major}.{sys.version_info.minor}. "
            f"Rebuild: cd simulator/core/rust_engine && maturin develop"
        ) from exc
    # Verify the extension reports the expected Python version
    expected = f"{sys.version_info.major}{sys.version_info.minor}"
    if hasattr(_rce, "__python_abi__") and expected not in _rce.__python_abi__:
        raise RuntimeError(
            f"Rust extension built for wrong Python ABI "
            f"(got {_rce.__python_abi__}, running {expected}). "
            f"Rebuild: cd simulator/core/rust_engine && maturin develop"
        )
```

**Why at import time vs. runtime:** A wrong-ABI extension will either fail to import (caught by `ImportError`) or produce subtly wrong results at runtime. Import-time detection with a clear rebuild hint is strictly better than a cryptic `AttributeError` or silent wrong output.

---

### 7. Magic Numbers → Config Dataclass

**Confidence: HIGH** (Python dataclasses stdlib; established pattern)

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class FeatureEngineeringConstants:
    """Tuning constants for feature engineering. Values derived from TFT Set 11 analysis."""

    # Stat scaling per star level — from TFT game data
    star_scaling_hp: dict[int, float] = field(
        default_factory=lambda: {1: 1.0, 2: 1.8, 3: 3.24}
    )
    star_scaling_ad: dict[int, float] = field(
        default_factory=lambda: {1: 1.0, 2: 1.5, 3: 2.25}
    )

    # Board geometry
    board_cols: int = 7

    # Stage normalization: divide stage number by this to get [0, 1] range over 7 stages
    default_stage_divisor: int = 7

    # Attack speed hard cap from game engine
    attack_speed_cap: float = 5.0

    # Numerical stability for log / division operations
    epsilon: float = 1e-6


FE_CONSTANTS = FeatureEngineeringConstants()
```

**Why frozen=True:** Config constants must not be mutated at runtime. `frozen=True` enforces this at the dataclass level and makes the intent clear.

**Why not a plain module-level dict or Enum:** A frozen dataclass gives IDE autocompletion, type checking, and is serializable via `dataclasses.asdict()` for logging/debugging. Enums are appropriate for categorical values, not numeric tuning constants.

---

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| ruff BLE001 + E722 | pylint broad-except | ruff is already configured in this codebase and 100x faster in CI. pylint catches deeper issues but is a new dep with a steep configuration surface. Add pylint only if ruff misses something specific. |
| pandera for DataFrame schemas | great_expectations | great_expectations is a full data quality platform with a large configuration footprint. Overkill for a single entry-point validation gate. Pandera integrates directly into Python function signatures. |
| syrupy snapshot testing | hand-written golden files | syrupy manages file creation, updating, and diffing automatically. Hand-written golden files require maintenance. Snapshot testing is the standard pattern for locking behavior before large refactors. |
| rope for AST-safe moves | manual cut-paste | Manual cut-paste doesn't update import references. rope uses Python's AST to track all references and update them. Essential for large moves across 5k+ LOC files. |
| FastAPI lifespan + app.state | @app.on_event("startup") | `@app.on_event` is deprecated since FastAPI 0.93 and will be removed. Lifespan is the official replacement and prevents None-model endpoints by raising before startup completes. |
| `logging.warning()` for fallbacks | `print()` or `warnings.warn()` | `print()` is not filterable, not structured, and disappears in production. `warnings.warn()` is appropriate for API deprecation, not operational status. `logging.warning()` integrates with existing log infrastructure and is filterable by level and logger name. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `except Exception:` for import fallbacks | Catches `AttributeError`, `NameError`, bugs in module init code — masks real errors as optional-dependency fallbacks | `except ImportError:` (the only exception a missing module can raise) |
| Bare `except:` anywhere in active code | Catches `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit` — program becomes uninterruptable | `except Exception:` at absolute minimum; prefer specific types |
| Module-level global mutation with `global` keyword | Non-reentrant, cannot be parallelized, hard to test without module reload | Class-based state with instance variables |
| `@app.on_event("startup")` in FastAPI | Deprecated since FastAPI 0.93; no startup failure propagation | `lifespan` context manager with `app.state` |
| `assert` for runtime validation | Optimized away with `python -O`; should not be used for production input validation | `if not condition: raise ValueError(...)` or Pydantic validation |

---

## Ruff Configuration Changes Required

The current `ruff.toml` only enables `["E", "F", "W", "I"]`. To catch the 39 bare exception instances:

```toml
[lint]
select = ["E", "F", "W", "I", "BLE", "B"]

# BLE001 = blind except (catches `except Exception:`)
# E722   = bare except (catches `except:` with no type)
# B      = flake8-bugbear (catches `try/except/pass` patterns and other bugs)

# If some sites need exemption (e.g., Rust engine import in benchmark.py where
# ANY import exception is intentional):
[lint.extend-per-file-ignores]
"simulator/benchmark.py" = ["E402", "BLE001"]
```

**Why add BLE and B separately rather than using `ALL`:** `ALL` enables rules that conflict with the existing codebase style (E501, E741 already ignored). Adding only BLE and B is the minimal change needed to catch the 39 known bad patterns.

---

## Installation

```bash
# All recommended new additions are either stdlib or lightweight
pip install pandera>=0.20

# Snapshot testing (for pre-split behavior locking)
pip install syrupy>=4.0

# rope for programmatic refactoring (dev-only, not needed in prod)
pip install rope>=1.14

# No new runtime deps added — pandera is dev/test only for this use case
```

**No changes to requirements.txt for prod:** pandera and syrupy are test/dev tooling. rope is used only during the refactor. Add to `requirements-dev.txt` or equivalent.

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| pandera 0.20+ | pandas 2.1+, pyarrow 14.0+ | Supports Arrow Tables directly via `pandera.DataFrameSchema.validate(arrow_table)` with `pandas_engine`. Match existing pandas 2.1+ and pyarrow 14.0+ versions. |
| syrupy 4.x | pytest 7.4.3+ | Drop-in pytest plugin; no configuration needed beyond installing |
| rope 1.14 | Python 3.11+, no other deps | Pure Python, no C extensions. Syntax support up to Python 3.11 confirmed. |
| ruff BLE001 | ruff 0.1+ (already installed) | BLE rule family available in all recent ruff versions; no upgrade needed |

---

## Sources

- ruff official docs — E722, BLE001 rules confirmed at https://docs.astral.sh/ruff/rules/
- FastAPI official docs — lifespan/app.state pattern at https://fastapi.tiangolo.com/advanced/events/ (HIGH confidence)
- Pydantic Context7 `/pydantic/pydantic` — `model_validate(strict=True)`, `Field(strict=True)` confirmed (HIGH confidence)
- pandera docs — DataFrame schema validation at https://pandera.readthedocs.io/ (MEDIUM-HIGH confidence, verified with official docs)
- rope GitHub — Move/extract refactoring at https://github.com/python-rope/rope (MEDIUM confidence — version support up to Python 3.10 documented; 3.11 not explicitly confirmed but community usage confirms it works)
- PEP 760 (Withdrawn) — confirms bare excepts are universally considered bad practice even though the PEP wasn't adopted; https://peps.python.org/pep-0760/ (HIGH confidence for the guidance, not for the PEP itself)
- Python multiprocessing docs — Pool as context manager, `__exit__` calls terminate: https://docs.python.org/3/library/multiprocessing.html (HIGH confidence)
- FastAPI/fastapi GitHub Discussion #8968 — dependency injection without global state (MEDIUM confidence — community discussion)
- WebSearch: syrupy snapshot testing, pandera 2025 usage (MEDIUM confidence — multiple sources agree on current usage patterns)

---
*Stack research for: Python codebase reliability, refactoring, and error handling*
*Researched: 2026-02-27*
