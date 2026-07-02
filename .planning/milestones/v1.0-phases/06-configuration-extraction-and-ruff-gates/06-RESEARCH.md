# Phase 6: Configuration Extraction and Ruff Gates - Research

**Researched:** 2026-02-27
**Domain:** Python dataclass configuration, ruff linting (BLE/B rules)
**Confidence:** HIGH

## Summary

This phase has two independent workstreams: (1) extracting magic numeric constants from `models/feature_engineering.py` into a frozen dataclass, and (2) enabling ruff BLE and B rule groups across the entire codebase. Both are well-scoped, mechanically verifiable, and carry low risk.

The feature_engineering.py file (2,160 LOC) already has 6 module-level constants (`EPSILON`, `STAR_SCALING_HP`, `STAR_SCALING_AD`, `ATTACK_SPEED_CAP`, `BOARD_COLS`, `DEFAULT_STAGE_DIVISOR`) but contains ~15 additional domain-meaningful magic numbers scattered inline: item classification thresholds, economy constants, personal scoring weights, matchup scaling factors, and composition proxy multipliers. These need extraction to a new frozen dataclass. Note: the file already has a `FeatureConfig` class (line 101) that controls feature group toggles (booleans) -- the new numeric constants dataclass must use a different name to avoid collision.

For ruff gates, enabling BLE and B rules produces 82 violations across ~20 files: 50 BLE001 (broad except), 15 B007 (unused loop variable), 10 B905 (zip without strict), 7 B009 (getattr with constant). Legacy/quarantined directories (`simulator/Simulator/**`, `simulator/Concurrency/**`, `simulator/Evaluator/**`) are already excluded via existing per-file-ignores. All violations must be fixed to achieve `ruff check .` passing with zero violations. The user decision is clear: refactor all broad exception handlers to specific types with no noqa suppressions.

**Primary recommendation:** Create `models/feature_config.py` with a frozen `NumericFeatureConfig` dataclass (name avoids collision with existing `FeatureConfig`), then fix all 82 BLE+B violations file-by-file before adding the rule groups to ruff.toml.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Single flat frozen dataclass (not nested sub-configs)
- Lives in a dedicated config module (e.g., src/models/feature_config.py), not inline in feature_engineering.py
- All fields have default values matching the current magic numbers
- Per-field inline comments explaining the rationale for each default value
- Only feature_engineering.py -- no other files in scope for constant extraction
- Numeric constants only -- no string or list constants
- Domain-meaningful magic numbers only -- skip trivial values like 0, 1, 100 used for basic arithmetic
- Rename to consistent descriptive snake_case field names on the dataclass (may differ from original inline variable names)
- Enable BLE and B rule groups only -- no additional rule groups (UP, SIM, etc.)
- Refactor all existing broad exception handlers to specific exception types -- no noqa suppressions
- Exclude legacy/quarantined paths (simulator/Simulator/**, simulator/Concurrency/**, simulator/Evaluator/**) from ruff enforcement
- Rely on existing pre-commit hooks for enforcement -- no new CI step needed
- Module-level DEFAULT_CONFIG = FeatureConfig() instance for production code to import directly
- Tests use dataclasses.replace(DEFAULT_CONFIG, field=new_value) for overrides
- Purely code-defined -- no environment variable overrides
- Export only FeatureConfig class and DEFAULT_CONFIG -- no re-exported individual constants

### Claude's Discretion
- Exact field names chosen based on what each constant represents in context
- Whether to add type annotations beyond basic int/float (e.g., NewType for domain clarity)
- Organization of ruff.toml changes (extend existing select vs replace)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CONF-01 | Magic numbers in feature_engineering.py extracted to frozen FeatureConfig dataclass with documented rationale | Identified ~15 domain-meaningful magic numbers across item classification, economy, personal scoring, matchup, and composition features; existing `FeatureConfig` class (boolean toggles) requires new class name |
| CONF-02 | Constants are importable and overridable for testing | Use `dataclasses.replace(DEFAULT_CONFIG, field=new_value)` pattern; frozen dataclass ensures immutability while `replace()` creates modified copies |
| EXCP-05 | Ruff rules BLE and B enabled in ruff.toml to statically detect future broad exceptions | 82 current violations (50 BLE001, 15 B007, 10 B905, 7 B009) must be fixed before enabling; legacy dirs already excluded |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python dataclasses | stdlib (3.14) | Frozen dataclass for config | Zero-dependency, built-in, supports `replace()` |
| ruff | 0.15.2 | Linting with BLE+B rules | Already installed and configured in project |
| pytest | 9.0.2 | Testing config overrides and ruff gate | Already the project test runner |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pre-commit | (already configured) | Runs ruff on commit | Existing `.pre-commit-config.yaml` uses `ruff-pre-commit v0.9.7` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| dataclass | pydantic BaseModel | Out of scope per project requirements ("Over-validation; pandera at entry points is sufficient") |
| dataclass | NamedTuple | Less ergonomic for `replace()`, no mutable default factory support |

**Installation:**
No new dependencies needed. Everything is already installed.

## Architecture Patterns

### Recommended Project Structure
```
models/
  feature_config.py       # NEW: frozen dataclass + DEFAULT_CONFIG
  feature_engineering.py   # MODIFIED: imports from feature_config, replaces inline magic numbers
```

### Pattern 1: Frozen Dataclass with Module-Level Default
**What:** A `@dataclass(frozen=True)` class with all numeric constants as typed fields with defaults. A module-level `DEFAULT_CONFIG` instance provides the production values.
**When to use:** When constants need to be documented, importable, and overridable for testing.
**Example:**
```python
# models/feature_config.py
from dataclasses import dataclass

@dataclass(frozen=True)
class NumericFeatureConfig:
    """Numeric constants for TFT feature engineering.

    Each field replaces a magic number in feature_engineering.py.
    Default values match the original inline constants.
    """

    # --- Item classification thresholds ---
    attack_speed_weight: float = 50.0  # Weight for AS in offensive signal calculation
    hp_divisor: float = 100.0  # Divisor to normalize HP to a 0-1 scale
    armor_divisor: float = 20.0  # Divisor to normalize armor contribution
    mr_divisor: float = 20.0  # Divisor to normalize magic resist contribution
    classification_threshold: float = 0.2  # Minimum signal gap to classify offensive vs defensive

    # --- Economy ---
    interest_gold_divisor: float = 10.0  # Gold per interest bracket (TFT rule: 1 gold per 10)
    max_interest: float = 5.0  # Maximum interest gold per round (TFT cap)

    # --- Scoring ---
    default_avg_placement: float = 4.5  # Neutral avg placement (midpoint of 1-8)
    personal_score_placement_divisor: float = 8.0  # Normalizes placement delta to ~0-1 range
    carry_item_score_weight: float = 0.01  # Small bonus for carry item count in personal score

    # --- Composition ---
    trait_ap_proxy_per_trait: float = 5.0  # Estimated AP contribution per active trait
    bis_item_threshold: float = 3.0  # Items needed on carry to count as "best in slot"

    # --- Matchup ---
    stage_hp_pressure_multiplier: float = 10.0  # HP pressure scaling per stage number
    share_to_percent_multiplier: float = 100.0  # Converts 0-1 share to 0-100 for armor/MR comparison

    # --- Team summary ---
    dps_weight_in_physical_proxy: float = 0.01  # Small DPS contribution to physical damage share
    attack_speed_pct_threshold: float = 1.0  # AS values above this are percentage-based (Riot data quirk)

DEFAULT_CONFIG = NumericFeatureConfig()
```

### Pattern 2: Importing and Using the Config
**What:** Feature engineering methods receive or default to the module-level config.
**When to use:** Everywhere a magic number was previously inline.
**Example:**
```python
# models/feature_engineering.py
from .feature_config import DEFAULT_CONFIG, NumericFeatureConfig

# In methods:
offensive_signal = stats["ad"] + stats["ap"] + stats["attack_speed"] * self._numeric_config.attack_speed_weight
```

### Pattern 3: Test Override with dataclasses.replace
**What:** Tests create modified config copies without mutating the default.
**When to use:** Testing that constants are not hardcoded at use sites.
**Example:**
```python
# tests/test_feature_config.py
from dataclasses import replace
from models.feature_config import DEFAULT_CONFIG, NumericFeatureConfig

def test_config_override():
    custom = replace(DEFAULT_CONFIG, max_interest=10.0)
    assert custom.max_interest == 10.0
    assert DEFAULT_CONFIG.max_interest == 5.0  # Original unchanged
```

### Anti-Patterns to Avoid
- **Naming collision with existing FeatureConfig:** The file already has `class FeatureConfig` (boolean feature group toggles at line 101). The new numeric config class MUST have a different name (e.g., `NumericFeatureConfig` or `FeatureConstants`).
- **Extracting trivial arithmetic constants:** Per CONTEXT.md, skip values like 0, 1, 100 used for basic arithmetic (e.g., `max(1, n_units)`, `float(n_units)`, loop counters). Only extract domain-meaningful constants.
- **Making the config mutable:** Must be `frozen=True` to prevent runtime mutation of shared defaults.
- **Passing config via environment variables:** Explicitly out of scope per user decision.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Immutable config | Custom `__setattr__` override | `@dataclass(frozen=True)` | Built-in, handles hash/eq correctly |
| Config override | Manual copy + field assignment | `dataclasses.replace()` | Type-safe, validates field names exist |
| Lint enforcement | Custom CI script for exception detection | `ruff check --select BLE,B` | Maintained by Astral, catches edge cases |

**Key insight:** Python's dataclass module already provides everything needed. No custom infrastructure required.

## Common Pitfalls

### Pitfall 1: FeatureConfig Name Collision
**What goes wrong:** Creating a new `FeatureConfig` class in `feature_config.py` shadows the existing `FeatureConfig` class in `feature_engineering.py` when both are imported.
**Why it happens:** The CONTEXT.md uses the generic name "FeatureConfig" but the file already has a class with that name (for boolean toggles).
**How to avoid:** Use a distinct name like `NumericFeatureConfig` or `FeatureConstants`. The existing `FeatureConfig` (toggles) stays where it is.
**Warning signs:** Import errors, test failures on existing `FeatureConfig` usage.

### Pitfall 2: Forgetting Batch Methods
**What goes wrong:** Magic numbers are replaced in the single-row methods (`_economy_features`, `_matchup_features`, etc.) but not in the corresponding batch methods (`_economy_features_batch`, `_matchup_features_batch`, etc.).
**Why it happens:** The file has BOTH per-row and batch implementations of many features, with duplicated magic numbers.
**How to avoid:** For every magic number replaced, grep for the same literal value and replace ALL occurrences. The file has duplicated constants at approximately: lines 1220+1816+1890 (interest), lines 1224+1819+1891 (HP%), lines 1172+1941 (trait AP proxy), lines 1291+1983 (BIS threshold), lines 1381+2099 (stage pressure), lines 1395-96+2091-92 (share scaling).
**Warning signs:** Running the test suite with overridden config values and seeing some features still use old values.

### Pitfall 3: Breaking Existing FeatureConfig Toggle Tests
**What goes wrong:** Tests that import `from models.feature_engineering import FeatureConfig` break if the namespace changes.
**Why it happens:** Moving or renaming the existing boolean toggle class.
**How to avoid:** Do NOT move the existing `FeatureConfig` class. Only create a NEW class in the new module. Existing imports remain stable.
**Warning signs:** Import errors in existing tests.

### Pitfall 4: BLE001 Fixes Changing Error Behavior
**What goes wrong:** Narrowing `except Exception` to `except SpecificError` causes previously-caught errors to propagate as unhandled.
**Why it happens:** The original broad catch was hiding unexpected error types.
**How to avoid:** For each BLE001 fix, analyze what the try block actually does and what exceptions it can raise. Common patterns: `ValueError`/`TypeError` for parsing, `KeyError` for dict access, `OSError`/`ConnectionError` for I/O, `RuntimeError` for general logic errors.
**Warning signs:** New exceptions appearing in logs after the change.

### Pitfall 5: B905 zip(strict=True) Breaking on Mismatched Lengths
**What goes wrong:** Adding `strict=True` to `zip()` calls where iterables intentionally have different lengths causes `ValueError`.
**Why it happens:** Some `zip()` calls intentionally truncate to the shorter iterable.
**How to avoid:** For each B905 fix, check whether the iterables are guaranteed same-length. If truncation is intentional, use `strict=False` explicitly. If same-length is expected, use `strict=True`.
**Warning signs:** ValueError in zip calls after the change.

### Pitfall 6: Forgetting the src/models/feature_engineering.py BLE001
**What goes wrong:** The `src/models/feature_engineering.py` file (line 246) also has a BLE001 violation that must be fixed for `ruff check .` to pass.
**Why it happens:** There are TWO feature_engineering.py files in different directories.
**How to avoid:** Fix ALL 50 BLE001 violations listed in the ruff output, including `src/models/feature_engineering.py:246`.
**Warning signs:** `ruff check .` still fails after fixing "all" violations.

## Code Examples

### Creating the Frozen Config Dataclass
```python
# Source: Python stdlib dataclasses documentation
from dataclasses import dataclass

@dataclass(frozen=True)
class NumericFeatureConfig:
    """Numeric constants for feature engineering.

    Frozen to prevent runtime mutation of shared defaults.
    Use dataclasses.replace() to create modified copies for testing.
    """
    max_interest: float = 5.0  # Maximum interest gold per round (TFT game rule)
    interest_gold_divisor: float = 10.0  # Gold per interest bracket
    # ... all other fields ...

DEFAULT_CONFIG = NumericFeatureConfig()
```

### Using replace() in Tests
```python
# Source: Python stdlib dataclasses documentation
from dataclasses import replace
from models.feature_config import DEFAULT_CONFIG, NumericFeatureConfig

def test_interest_override():
    """Verify constants are not hardcoded at use sites."""
    custom = replace(DEFAULT_CONFIG, max_interest=10.0)
    fe = TFTFeatureEngineer(numeric_config=custom)
    # ... test that interest cap changes with config ...
```

### Narrowing Broad Exception Handlers (BLE001 Fix Pattern)
```python
# BEFORE (BLE001 violation):
try:
    player_xp = int(str(state.xp).split("/", 1)[0])
except Exception:
    player_xp = None

# AFTER (specific exception):
try:
    player_xp = int(str(state.xp).split("/", 1)[0])
except (ValueError, IndexError, AttributeError):
    player_xp = None
```

### Fixing Unused Loop Variables (B007 Fix Pattern)
```python
# BEFORE (B007 violation):
for board_id, units in opponent_boards.items():
    for unit in units:
        ...

# AFTER (prefix with underscore):
for _board_id, units in opponent_boards.items():
    for unit in units:
        ...
```

### Fixing getattr with Constant (B009 Fix Pattern)
```python
# BEFORE (B009 violation):
gold = int(getattr(row, "gold") or 0)

# AFTER (direct attribute access):
gold = int(row.gold or 0)
```

### Fixing zip without strict (B905 Fix Pattern)
```python
# BEFORE (B905 violation):
for a, b in zip(list_a, list_b):
    ...

# AFTER (explicit strict parameter):
for a, b in zip(list_a, list_b, strict=True):  # or strict=False if truncation intended
    ...
```

### Adding BLE and B to ruff.toml
```toml
# ruff.toml
[lint]
select = ["E", "F", "W", "I", "BLE", "B"]

# Legacy dirs already excluded via per-file-ignores:
[lint.extend-per-file-ignores]
"simulator/Simulator/**" = ["E", "F", "W", "I", "BLE", "B"]
"simulator/Concurrency/**" = ["E", "F", "W", "I", "BLE", "B"]
"simulator/Evaluator/**" = ["E", "F", "W", "I", "BLE", "B"]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Inline magic numbers | Frozen dataclass with defaults | Python 3.7+ (dataclasses) | Documented, importable, testable constants |
| `except Exception:` with no lint | ruff BLE001 rule enforcement | ruff 0.1.0+ | Catches blind exceptions at lint time |
| `zip()` with implicit behavior | `zip(strict=True/False)` | Python 3.10+ (PEP 618) | Explicit length-matching intent |

**Deprecated/outdated:**
- None relevant. `@dataclass(frozen=True)` and ruff BLE/B rules are stable, well-established features.

## Open Questions

1. **Naming the new dataclass**
   - What we know: `FeatureConfig` already exists in `feature_engineering.py` for boolean toggles
   - What's unclear: Whether the user wants us to rename the existing one or name the new one differently
   - Recommendation: Name the new class `NumericFeatureConfig` (or `FeatureConstants`). Per Claude's discretion on naming, choose the clearest option that avoids collision. `NumericFeatureConfig` is recommended because it parallels the existing `FeatureConfig` naming.

2. **Config module location: `models/` vs `src/models/`**
   - What we know: CONTEXT.md says "e.g., src/models/feature_config.py" but the target file is `models/feature_engineering.py` (2.1k LOC), not `src/models/feature_engineering.py` (330 LOC)
   - What's unclear: Whether the config module should live alongside the file it serves
   - Recommendation: Place at `models/feature_config.py` since that's where `models/feature_engineering.py` lives. The `src/models/` path in CONTEXT.md was likely illustrative.

3. **How TFTFeatureEngineer receives the numeric config**
   - What we know: The class already takes `config: Optional[FeatureConfig]` in `__init__` for toggle config
   - What's unclear: Whether to add a second parameter or bundle both configs
   - Recommendation: Add `numeric_config: Optional[NumericFeatureConfig] = None` parameter to `__init__`, defaulting to `DEFAULT_CONFIG`. Keeps the two config types separate (toggles vs numeric constants).

## Violation Inventory (for planning)

### BLE001 Violations by File (50 total)
| File | Count | Notes |
|------|-------|-------|
| `app/server/websocket.py` | 5 | WebSocket broadcast, parsing, coach compute |
| `app/state/state_manager.py` | 6 | State parsing, update handling |
| `app/api/server.py` | 2 | Startup model loading (Phase 5 lifespan) |
| `app/run_app.py` | 1 | Process termination |
| `app/frontend/images/set16_trait_palette.py` | 1 | Breakpoint parsing |
| `app/watcher/log_watcher.py` | 1 | Watcher loop |
| `coach/coach.py` | 1 | Coach main loop |
| `coach/offline/build_archetypes.py` | 1 | Archetype building |
| `coach/offline/eval_coach.py` | 2 | Evaluation loop |
| `coach/offline/view_traces.py` | 2 | Trace viewing |
| `coach/scoring/archetypes.py` | 4 | Archetype scoring |
| `coach/scoring/evaluator.py` | 1 | Scoring evaluation |
| `coach/scoring/features.py` | 3 | Feature computation |
| `models/data_loader.py` | 2 | Data loading |
| `simulator/cloud_runner.py` | 9 | Cloud runner (various) |
| `simulator/core/combat_engine.py` | 1 | Combat engine exception |
| `simulator/core/engine_wrapper.py` | 1 | Engine wrapper |
| `simulator/game/game.py` | 1 | Game loop |
| `simulator/game/unlocks.py` | 3 | Unlock system |
| `src/models/feature_engineering.py` | 1 | Transform loop |
| `tests/test_api_server.py` | 2 | Test assertions |

### B007/B009/B905 Violations by File (32 total)
| File | Rule | Count |
|------|------|-------|
| `app/services/pool_tracker.py` | B007 | 1 |
| `coach/offline/train_evaluator.py` | B009 | 7 |
| `coach/offline/train_evaluator.py` | B007 | 1 |
| `models/data_loader.py` | B905 | 1 |
| `models/evaluate.py` | B905 | 2 |
| `models/information_theory.py` | B905 | 2 |
| `models/uncertainty.py` | B905 | 1 |
| `simulator/benchmark.py` | B905 | 1 |
| `simulator/cloud_runner.py` | B905 | 1 |
| `simulator/core/champion_abilities.py` | B007 | 2 |
| `simulator/core/combat_engine.py` | B007 | 3 |
| `simulator/core/item_optimizer.py` | B007 | 1 |
| `simulator/core/positioning_optimizer.py` | B007 | 1 |
| `simulator/core/timing_utils.py` | B007 | 1 |
| `simulator/game/champion_pool.py` | B007 | 1 |
| `simulator/game/collector.py` | B007 | 2 |
| `simulator/game/player.py` | B007 | 1 |
| `src/models/placement_model.py` | B905 | 2 |

## Magic Numbers Inventory (for planning)

Domain-meaningful numeric constants in `models/feature_engineering.py` to extract:

| Current Value | Usage Location(s) | Proposed Field Name | Rationale |
|---------------|-------------------|--------------------|-----------|
| `50.0` | L456 (item classification) | `attack_speed_weight` | AS weight in offensive signal |
| `100.0` | L458, L1224, L1819, L1891 | `hp_divisor` | Normalizes HP to 0-1 scale |
| `20.0` | L458 (armor) | `armor_divisor` | Normalizes armor contribution |
| `20.0` | L458 (MR) | `mr_divisor` | Normalizes magic resist contribution |
| `0.2` | L463, L466 | `classification_threshold` | Min signal gap for offensive/defensive classification |
| `10.0` | L1220, L1816, L1890 | `interest_gold_divisor` | Gold per interest bracket (TFT rule) |
| `5.0` | L1220, L1816, L1890 | `max_interest` | Maximum interest gold per round (TFT cap) |
| `4.5` | L623, L642, L665, L1422, L1436, L2120, L2140 | `default_avg_placement` | Neutral avg placement (midpoint of 1-8) |
| `8.0` | L644 | `personal_score_placement_divisor` | Normalizes placement delta to ~0-1 |
| `0.01` | L1083, L1449, L2155 | `carry_item_score_weight` | Small bonus for carry item count |
| `5.0` | L1172, L1941 | `trait_ap_proxy_per_trait` | Estimated AP per active trait |
| `3.0` | L1291, L1983 | `bis_item_threshold` | Items on carry for "best in slot" |
| `10.0` | L1381, L2099 | `stage_hp_pressure_multiplier` | HP pressure scaling per stage |
| `100.0` | L1395-96, L2091-92 | `share_to_percent_multiplier` | Converts 0-1 share to 0-100 scale |
| `0.01` | L1083 | `dps_weight_in_physical_proxy` | DPS contribution to physical share |
| `1.0` | L431 | `attack_speed_pct_threshold` | AS > 1.0 means percentage in Riot data |

Note: Some values (like `100.0`) serve different purposes at different sites. The `hp_divisor` and `share_to_percent_multiplier` are conceptually different but numerically identical -- use separate fields for clarity.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | None (uses pytest defaults) |
| Quick run command | `python -m pytest tests/test_feature_engineering.py -x` |
| Full suite command | `python -m pytest` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONF-01 | All magic numbers replaced by frozen dataclass fields | unit | `python -m pytest tests/test_feature_config.py -x` | No -- Wave 0 |
| CONF-02 | Config importable and overridable in tests | unit | `python -m pytest tests/test_feature_config.py::test_config_override -x` | No -- Wave 0 |
| EXCP-05 | ruff BLE+B enabled and passes | smoke | `ruff check . --select BLE,B` | N/A (CLI check) |

### Sampling Rate
- **Per task commit:** `ruff check . && python -m pytest tests/test_feature_engineering.py tests/test_feature_config.py -x`
- **Per wave merge:** `ruff check . && python -m pytest`
- **Phase gate:** Full suite green + `ruff check .` zero violations

### Wave 0 Gaps
- [ ] `tests/test_feature_config.py` -- covers CONF-01, CONF-02 (import, instantiation, override, field count)
- [ ] `models/feature_config.py` -- the frozen dataclass module itself

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: `models/feature_engineering.py` (2,160 LOC), `ruff.toml`, `.pre-commit-config.yaml`
- `ruff check --select BLE,B .` output: 82 violations enumerated (ruff 0.15.2)
- Python stdlib dataclasses documentation: `@dataclass(frozen=True)`, `dataclasses.replace()`

### Secondary (MEDIUM confidence)
- Ruff official docs (https://docs.astral.sh/ruff/rules/) - BLE001, B007, B009, B905 rule definitions verified

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all tools already installed and configured in project
- Architecture: HIGH - stdlib dataclasses, straightforward extraction pattern
- Pitfalls: HIGH - verified by inspecting actual codebase (name collision, batch method duplication, etc.)
- Violation inventory: HIGH - generated by running `ruff check` directly

**Research date:** 2026-02-27
**Valid until:** 2026-03-27 (stable domain -- stdlib dataclasses and ruff rules do not change frequently)
