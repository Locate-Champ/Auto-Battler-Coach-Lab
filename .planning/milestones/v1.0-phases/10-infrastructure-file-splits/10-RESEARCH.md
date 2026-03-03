# Phase 10: Infrastructure File Splits - Research

**Researched:** 2026-02-28
**Domain:** Python module decomposition / facade pattern for monolithic files
**Confidence:** HIGH

## Summary

Phase 10 splits two infrastructure files -- `simulator/cloud_runner.py` (2,070 LOC) and `models/feature_engineering.py` (2,213 LOC) -- into focused sub-modules under 1,000 LOC each. Neither file is simulator-core (combat engine), so there is zero determinism risk. The primary challenge is preserving every existing import path exactly, including private symbols accessed by tests and the `inspect` module object that tests monkeypatch.

The codebase already completed the prerequisite Phase 8 (global state elimination), which refactored cloud_runner's module-level globals into the `BatchRunner` class. The `models/feature_config.py` already exists from Phase 6, containing `NumericFeatureConfig` and `DEFAULT_CONFIG` -- the new split must avoid duplicating this.

The recommended approach uses underscore-prefixed sub-modules (`_cloud_runner_utils.py`, `_cloud_runner_writer.py`, etc.) with the original files becoming thin facades that re-export all public symbols. This is standard Python practice for splitting without breaking consumers. For `feature_engineering.py`, the mixin class pattern is required because all methods access `self.*` instance attributes.

**Primary recommendation:** Split cloud_runner first (cleaner boundaries, standalone functions/classes), verify tests pass, then split feature_engineering (tighter coupling via self.* access requiring mixin pattern). Add `CloudRunner = BatchRunner` and `FeatureEngineer = TFTFeatureEngineer` aliases in the facades to satisfy the roadmap success criteria literally.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SPLT-01 | `feature_engineering.py` (2.1k LOC) split into config, loaders, and transform sub-modules | Architecture Patterns section details 4 sub-modules with mixin class pattern; Code Examples show mixin wiring |
| SPLT-02 | `cloud_runner.py` (2k LOC) split into runner core, utilities, and writer sub-modules | Architecture Patterns section details 3 sub-modules with facade re-exports; Code Examples show facade pattern |
| SPLT-05 | All splits maintain backward-compatible imports via facade re-exports | Facade Re-Export pattern documented with exact symbols to re-export; Common Pitfalls covers private symbol and monkeypatch compatibility |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib | 3.11+ | Module system, `__init__.py` facades | Native language feature, no deps needed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| ruff | (project-configured) | Lint + format verification after split | Required by CLAUDE.md verification rules |
| pytest | (project-configured) | Verify no test breakage | Required by success criteria |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Underscore-prefixed sub-modules | Sub-package with `__init__.py` | Sub-package adds a directory level; underscore convention is lighter and signals "internal" without restructuring imports |
| Mixin classes (feature_engineering) | Standalone functions with explicit `self` arg | Mixin avoids invasive changes to method signatures; standalone functions require passing 10+ attributes explicitly |

**Installation:** No new dependencies required.

## Architecture Patterns

### Recommended Structure: cloud_runner Split

```
simulator/
├── cloud_runner.py                  # Facade (~150 LOC): re-exports + CLI (main, _parse_agent_mix, _cli_flag_present)
├── _cloud_runner_utils.py           # Utilities (~300 LOC): constants, standalone helper functions
├── _cloud_runner_writer.py          # Writer (~500 LOC): StreamingWriter class
└── _cloud_runner_core.py            # Core (~650 LOC): BatchRunnerConfig, BatchAbort, run_game, _worker_init, BatchRunner
```

### Recommended Structure: feature_engineering Split

```
models/
├── feature_engineering.py           # Facade (~200 LOC): TFTFeatureEngineer class definition + __init__ + pickle + re-exports
├── feature_config.py                # ALREADY EXISTS (Phase 6): NumericFeatureConfig, DEFAULT_CONFIG
├── _feature_engineering_config.py   # Constants (~200 LOC): EPSILON, STAR_SCALING_*, BOARD_COLS, REQUIRED_COLUMNS, FeatureConfig, TraitMetadata, helper functions
├── _feature_engineering_loaders.py  # Loader mixin (~400 LOC): _LoaderMixin with all _load_* methods
├── _feature_engineering_transform.py # Single-row mixin (~700 LOC): _TransformMixin with _extract_*, _team_summary, _*_features, transform, _build_feature_names
└── _feature_engineering_batch.py    # Batch mixin (~500 LOC): _BatchTransformMixin with transform_batch, transform_arrow_batch, all _*_batch methods
```

### Pattern 1: Facade Re-Export

**What:** The original module file becomes a thin facade that imports from sub-modules and re-exports every symbol that was previously importable.
**When to use:** Any time a module is split but callers must not change their import paths.
**Example:**

```python
# simulator/cloud_runner.py (facade)
"""Batch runner for mass TFT game simulations. [original docstring preserved]"""
from __future__ import annotations

import inspect  # kept at facade level: tests monkeypatch cloud_runner.inspect.signature

from simulator._cloud_runner_utils import (
    AGENT_PROFILES,
    WILSON_Z_95,
    _build_cost_telemetry,
    _compute_seed_end,
    _ensure_rust_parquet_method_support,
    _estimate_worker_cpu_share_pct,
    _extract_signature_parameter_names,
    _iter_task_batches,
    _normalize_parquet_compression,
    _pyarrow_available,
    _resolve_shard_range,
    _round_or_none,
    _rust_extension_rebuild_hint,
    _sample_cpu_utilization_pct,
    _validate_reference_data_preflight,
    _wilson_interval,
)
from simulator._cloud_runner_writer import StreamingWriter
from simulator._cloud_runner_core import (
    BatchAbort,
    BatchRunner,
    BatchRunnerConfig,
    _worker_init,
    _worker_parquet_validated,
    _worker_sim,
    run_game,
)

# Alias to satisfy roadmap SC1 ("from simulator.cloud_runner import CloudRunner")
CloudRunner = BatchRunner

# CLI functions stay in facade (they are the entry point)
# _parse_agent_mix, _cli_flag_present, main, if __name__ == "__main__"
```

### Pattern 2: Mixin Class Composition

**What:** Methods that access `self.*` attributes are grouped into mixin classes in sub-modules. The main class inherits from all mixins.
**When to use:** When splitting a class whose methods all share instance state.
**Example:**

```python
# models/_feature_engineering_loaders.py
class _LoaderMixin:
    """Mixin providing reference data loading methods for TFTFeatureEngineer."""

    def _load_reference_data(self) -> None:
        self._load_champions()
        self._load_traits()
        self._load_items()
        self._load_augments()
        self._load_personal_reference()

    def _load_champions(self) -> None:
        # ... uses self.repo_root, self.champion_costs, etc.
        ...

# models/feature_engineering.py (facade)
from models._feature_engineering_loaders import _LoaderMixin
from models._feature_engineering_transform import _TransformMixin
from models._feature_engineering_batch import _BatchTransformMixin

class TFTFeatureEngineer(_LoaderMixin, _TransformMixin, _BatchTransformMixin):
    """Transforms raw board state into engineered feature vectors."""
    def __init__(self, ...):
        # ... all __init__ logic stays here
        ...

# Alias for roadmap SC2
FeatureEngineer = TFTFeatureEngineer
```

### Pattern 3: Worker Function Placement (Multiprocessing Pickle Safety)

**What:** `run_game` and `_worker_init` must be top-level functions in a real module file (not closures, not dynamically composed), because `multiprocessing.Pool` pickles function references by `module.function_name`.
**When to use:** Always, for any function passed to Pool.
**Example:**

```python
# simulator/_cloud_runner_core.py
# These MUST be module-level functions, not methods or closures
def run_game(args: Tuple) -> Dict:
    ...

def _worker_init(engine: str = "python"):
    ...
```

### Anti-Patterns to Avoid
- **Moving run_game/\_worker_init into a class or closure:** Multiprocessing pickle requires top-level function references. Wrapping them breaks parallel execution.
- **Duplicating constants between feature_config.py and \_feature_engineering_config.py:** `NumericFeatureConfig` and `DEFAULT_CONFIG` already live in `models/feature_config.py` from Phase 6. The new config sub-module holds only the constants NOT already extracted (EPSILON, STAR_SCALING_*, etc.).
- **Forgetting to re-export private symbols used by tests:** Tests directly access `cloud_runner._build_cost_telemetry`, `cloud_runner._ensure_rust_parquet_method_support`, `cloud_runner._extract_signature_parameter_names`, and `cloud_runner.inspect`. All must be available on the facade module.
- **Changing TFTFeatureEngineer's module path for pickle:** `__getstate__`/`__setstate__` are defined on the class. If the class is defined in a sub-module and only imported into the facade, pickle will reference the sub-module path. Keep the class definition (or at minimum the `class` statement) in the facade file to preserve pickle compatibility, or use `__module__` override.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Import path compatibility | Custom import hooks or sys.modules manipulation | Simple `from X import Y` re-exports in facade | Python's import system handles re-exports natively; sys.modules hacks are fragile |
| Pickle module path preservation | Manual `__module__` overrides on every class | Define class in facade, inherit from mixins | Simpler, standard Python pattern |

**Key insight:** This phase is pure mechanical restructuring. The Python import system already provides everything needed -- no libraries, no frameworks, just careful file organization and re-exports.

## Common Pitfalls

### Pitfall 1: Missing Private Symbol Re-exports
**What goes wrong:** Tests import `cloud_runner._build_cost_telemetry` or `cloud_runner._extract_signature_parameter_names` and get `AttributeError` after the split.
**Why it happens:** Private symbols are moved to sub-modules but not re-exported from the facade.
**How to avoid:** Audit all test files that import from `simulator.cloud_runner` or `simulator import cloud_runner`. Re-export every symbol they access.
**Warning signs:** `AttributeError` in test_benchmark_parity_helpers.py or test_cloud_runner_cost_telemetry.py.

**Known test-touched private symbols on `cloud_runner`:**
- `cloud_runner._build_cost_telemetry` (test_cloud_runner_cost_telemetry.py)
- `cloud_runner._ensure_rust_parquet_method_support` (test_benchmark_parity_helpers.py)
- `cloud_runner._extract_signature_parameter_names` (test_benchmark_parity_helpers.py)
- `cloud_runner.inspect` (test_benchmark_parity_helpers.py monkeypatches `cloud_runner.inspect.signature`)
- `cloud_runner.StreamingWriter` (test_cloud_runner_cost_telemetry.py)
- `cloud_runner.BatchRunner` (test_batch_runner.py)
- `cloud_runner.BatchRunnerConfig` (test_batch_runner.py)

### Pitfall 2: inspect Module Monkeypatch Breakage
**What goes wrong:** `test_benchmark_parity_helpers.py` monkeypatches `cloud_runner.inspect.signature`. If `inspect` is only imported in a sub-module, the monkeypatch targets the wrong module object.
**Why it happens:** The test does `monkeypatch.setattr(cloud_runner.inspect, "signature", ...)`. This requires `inspect` to be an attribute of the `cloud_runner` facade module.
**How to avoid:** Keep `import inspect` in the facade file. The sub-module `_cloud_runner_utils.py` (which uses `inspect.signature`) must import from the same `inspect` module, but the monkeypatch only works if the facade-level `inspect` is the same object. The sub-module should `import inspect` independently -- BUT the test monkeypatches `cloud_runner.inspect`, and the sub-module uses its own local `inspect`. So the functions in the sub-module that use `inspect.signature` need to be called through the facade's reference, OR the sub-module must import `inspect` from the facade. **Resolution:** Keep `_extract_signature_parameter_names` referencing `inspect` directly in the utils module, AND re-export it plus the `inspect` module on the facade. The test monkeypatches `cloud_runner.inspect.signature` which patches the global `inspect` module object (since Python modules are singletons). This means the monkeypatch DOES affect the sub-module's `inspect` reference too, as long as both `import inspect` -- they get the same module object.
**Warning signs:** test_benchmark_parity_helpers.py tests for `_extract_signature_parameter_names` fail with unexpected behavior.

### Pitfall 3: TFTFeatureEngineer Pickle Module Path
**What goes wrong:** Pickled `TFTFeatureEngineer` instances unpickle with wrong module path if the class is defined in a sub-module.
**Why it happens:** Python's pickle stores `class.__module__` and `class.__qualname__`. If the class is defined in `_feature_engineering_loaders.py`, pickle tries to load from there.
**How to avoid:** Define the `class TFTFeatureEngineer(...)` statement in `models/feature_engineering.py` (the facade), inheriting from the mixin classes. This keeps `__module__` as `models.feature_engineering`.
**Warning signs:** `ModuleNotFoundError` or `AttributeError` when unpickling a `TFTFeatureEngineer`.

### Pitfall 4: Circular Import Between Sub-modules
**What goes wrong:** Sub-modules import from each other in a cycle, causing `ImportError`.
**Why it happens:** If `_cloud_runner_core.py` imports from `_cloud_runner_writer.py` and vice versa.
**How to avoid:** Enforce one-way dependency graph:
- cloud_runner: `core -> {utils, writer}`, `writer -> utils`, `facade -> {core, utils, writer}`
- feature_engineering: `batch -> transform -> loaders -> config`, `facade -> {config, loaders, transform, batch}`
**Warning signs:** `ImportError: cannot import name 'X' from partially initialized module`.

### Pitfall 5: SIMULATOR_ALLOWED_FILES Allowlist
**What goes wrong:** CI check `check_public_surface_allowlist.py` rejects new `simulator/_cloud_runner_*.py` files as untracked.
**Why it happens:** New files under `simulator/` that are NOT under `simulator/core/` or `simulator/game/` must be individually listed in `SIMULATOR_ALLOWED_FILES`.
**How to avoid:** Add all three new files to `SIMULATOR_ALLOWED_FILES` in `scripts/ci/check_public_surface_allowlist.py`.
**Warning signs:** CI failure on `check_public_surface_allowlist` check.

### Pitfall 6: Feature Order Regression
**What goes wrong:** Feature vector ordering changes after split, silently corrupting model predictions.
**Why it happens:** `_build_feature_names`, `transform`, `transform_batch`, and `transform_arrow_batch` must produce identical output order. If mixin method resolution order (MRO) changes which method gets called, output may differ.
**How to avoid:** Each mixin provides distinct methods (no name collisions). The facade class calls them in the exact same order as the original monolith. Run `test_feature_engineering.py` which validates feature names and values.
**Warning signs:** test_feature_engineering.py assertion failures on feature count or values.

### Pitfall 7: test_track_boundaries.py Path Reference
**What goes wrong:** `test_track_boundaries.py` explicitly lists `"simulator/cloud_runner.py"` as an active file path. After the split, the file still exists (as facade), so this should not break -- but if the file were removed or renamed, it would.
**How to avoid:** Keep `simulator/cloud_runner.py` as the facade file (do not delete it). The test checks that the file exists and iterates its Python content.
**Warning signs:** test_track_boundaries.py fails with file-not-found.

## Code Examples

### cloud_runner Facade (verified pattern from codebase analysis)

```python
# simulator/cloud_runner.py (after split)
"""Batch runner for mass TFT game simulations.
[... keep original docstring ...]
"""
from __future__ import annotations

import argparse
import inspect  # Must stay here: tests monkeypatch cloud_runner.inspect.signature
import multiprocessing
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from simulator._cloud_runner_utils import (
    AGENT_PROFILES,
    WILSON_Z_95,
    _build_cost_telemetry,
    _compute_seed_end,
    _ensure_rust_parquet_method_support,
    _estimate_worker_cpu_share_pct,
    _extract_signature_parameter_names,
    _iter_task_batches,
    _normalize_parquet_compression,
    _pyarrow_available,
    _resolve_shard_range,
    _round_or_none,
    _rust_extension_rebuild_hint,
    _sample_cpu_utilization_pct,
    _validate_reference_data_preflight,
    _wilson_interval,
)
from simulator._cloud_runner_core import (
    BatchAbort,
    BatchRunner,
    BatchRunnerConfig,
    _worker_init,
    _worker_parquet_validated,
    _worker_sim,
    run_game,
)
from simulator._cloud_runner_writer import StreamingWriter

# Alias for roadmap success criteria SC1
CloudRunner = BatchRunner


def _parse_agent_mix(s: str) -> Dict[str, int]:
    # ... stays in facade (CLI code)


def _cli_flag_present(argv: List[str], flag: str) -> bool:
    # ... stays in facade (CLI code)


def main():
    # ... stays in facade (CLI entry point)


if __name__ == "__main__":
    main()
```

### feature_engineering Mixin Pattern (verified from codebase analysis)

```python
# models/_feature_engineering_loaders.py
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from models._feature_engineering_config import (
    _normalize_token,
    _safe_float,
    _safe_int,
    TraitMetadata,
)

_log = logging.getLogger(__name__)


class _LoaderMixin:
    """Mixin: reference data loading for TFTFeatureEngineer."""

    def _load_reference_data(self) -> None:
        self._load_champions()
        self._load_traits()
        self._load_items()
        self._load_augments()
        self._load_personal_reference()

    # ... all _load_* methods moved here verbatim
```

```python
# models/feature_engineering.py (facade, after split)
"""Feature engineering for TFT board states."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
from pathlib import Path

from .feature_config import DEFAULT_CONFIG, NumericFeatureConfig

# Re-export public symbols from sub-modules
from ._feature_engineering_config import (
    EPSILON,
    STAR_SCALING_HP,
    STAR_SCALING_AD,
    ATTACK_SPEED_CAP,
    BOARD_COLS,
    DEFAULT_STAGE_DIVISOR,
    REQUIRED_COLUMNS,
    _REQUIRED_COLUMN_GROUPS,
    FeatureConfig,
    TraitMetadata,
    _normalize_token,
    _safe_float,
    _safe_int,
    _decode_maybe_json,
)
from ._feature_engineering_loaders import _LoaderMixin
from ._feature_engineering_transform import _TransformMixin
from ._feature_engineering_batch import _BatchTransformMixin


class TFTFeatureEngineer(_LoaderMixin, _TransformMixin, _BatchTransformMixin):
    """Transforms raw board state into engineered feature vectors."""

    def __init__(self, config=None, repo_root=None, numeric_config=None):
        # ... __init__ stays here (keeps __module__ correct for pickle)
        ...

    _DERIVED_ATTRS = (...)  # stays here

    def __getstate__(self):  # stays here for pickle
        ...

    def __setstate__(self, state):  # stays here for pickle
        ...


# Alias for roadmap success criteria SC2
FeatureEngineer = TFTFeatureEngineer
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Monolithic 2k+ LOC files | Facade + underscore-prefixed sub-modules | Standard Python practice | Better navigability, IDE support, git blame granularity |
| Module-level globals in cloud_runner | Class-based BatchRunner (Phase 8) | Phase 8, 2026-02-28 | Prerequisite completed; split is now safe |
| Magic numbers in feature_engineering | NumericFeatureConfig dataclass (Phase 6) | Phase 6, 2026-02-27 | `models/feature_config.py` already exists; do NOT duplicate |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | `pytest.ini` |
| Quick run command | `python -m pytest tests/test_batch_runner.py tests/test_cloud_runner_cost_telemetry.py tests/test_benchmark_parity_helpers.py tests/test_feature_engineering.py tests/test_feature_config.py -x -q` |
| Full suite command | `python -m pytest` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SPLT-01 | feature_engineering.py split with working imports | integration | `python -m pytest tests/test_feature_engineering.py tests/test_feature_config.py -x -q` | Yes |
| SPLT-02 | cloud_runner.py split with working imports | integration | `python -m pytest tests/test_batch_runner.py tests/test_cloud_runner_cost_telemetry.py tests/test_benchmark_parity_helpers.py -x -q` | Yes |
| SPLT-05 | All imports resolve after split | smoke | `python -c "from simulator.cloud_runner import CloudRunner, BatchRunner, BatchRunnerConfig, StreamingWriter, BatchAbort; print('OK')" && python -c "from models.feature_engineering import TFTFeatureEngineer, FeatureEngineer, REQUIRED_COLUMNS, FeatureConfig, TraitMetadata; print('OK')"` | N/A (inline) |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_batch_runner.py tests/test_cloud_runner_cost_telemetry.py tests/test_benchmark_parity_helpers.py tests/test_feature_engineering.py tests/test_feature_config.py -x -q`
- **Per wave merge:** `python -m pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
None -- existing test infrastructure covers all phase requirements. The existing tests for cloud_runner and feature_engineering will serve as regression tests for the split.

## Open Questions

1. **Mixin MRO edge cases with Cython fe_fast**
   - What we know: `_CYTHON_FE` flag and Cython fast-path functions (`_cy_team_summary`, `_cy_parse_units_column`) are imported at module level in feature_engineering.py. After the split, they need to be imported in whichever sub-module uses them.
   - What's unclear: Whether the Cython import try/except block should live in the config sub-module or in the transform sub-module that calls the functions.
   - Recommendation: Place the Cython try/except import in `_feature_engineering_transform.py` (the module that calls those functions). The `_CYTHON_FE` flag and function references are only used in `_team_summary` and `_parse_units_column`, both in the transform layer.

2. **LOC budget for facade files**
   - What we know: Success criteria require each file under 1,000 LOC. The `main()` function in cloud_runner is ~500 LOC of CLI argument parsing.
   - What's unclear: Whether the facade (re-exports + main + parse_agent_mix + _cli_flag_present) will exceed 1,000 LOC.
   - Recommendation: If `main()` alone pushes the facade over 1,000 LOC, move the CLI argument setup into a `_cloud_runner_cli.py` sub-module and keep only the `main()` entry point and `if __name__ == "__main__"` block in the facade. Based on line count analysis: re-exports (~50 LOC) + `_parse_agent_mix` (~15 LOC) + `_cli_flag_present` (~2 LOC) + `main()` (~500 LOC) + `if __name__` (~2 LOC) + imports/aliases (~20 LOC) = ~590 LOC. This is well under 1,000 LOC, so no further splitting needed.

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis of `simulator/cloud_runner.py` (2,070 LOC) -- full file read
- Direct codebase analysis of `models/feature_engineering.py` (2,213 LOC) -- full file read
- Direct codebase analysis of all test files that import from these modules
- `scripts/ci/check_public_surface_allowlist.py` -- verified allowlist requirements
- `.planning/phases/10-infrastructure-file-splits/ccg-plan-input.md` -- CCG pre-analysis with Codex findings

### Secondary (MEDIUM confidence)
- Python module system behavior for re-exports and pickle `__module__` -- well-established Python semantics
- Multiprocessing pickle requirements for top-level functions -- standard Python documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no external dependencies needed, pure Python module restructuring
- Architecture: HIGH - both files fully analyzed, all import paths traced, all test dependencies mapped
- Pitfalls: HIGH - every pitfall identified from actual codebase analysis (test monkeypatches, pickle paths, allowlist, etc.)

**Research date:** 2026-02-28
**Valid until:** 2026-03-28 (stable -- no external dependency changes expected)
