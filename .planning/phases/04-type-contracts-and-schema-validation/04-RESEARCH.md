# Phase 4: Type Contracts and Schema Validation - Research

**Researched:** 2026-02-27
**Status:** Complete

## Executive Summary

Phase 4 targets three module boundaries where contracts are dishonest or missing. The changes are isolated, low-risk, and fully testable without simulator runs. All four requirements (TYPE-01, TYPE-02, SCHM-01, SCHM-02) map to specific code locations with clear before/after states.

## Codebase Findings

### 1. RuntimeEvaluator.check_compatibility() (TYPE-01)

**File:** `coach/scoring/evaluator.py` (lines 131-137)

**Current state:**
```python
class RuntimeEvaluator:
    evaluator: BoardEvaluator

    def check_compatibility(self) -> None:
        # LinearEvaluator.from_json already enforces schema_version + feature order.
        return None
```

**Problems:**
- Return type annotation is `-> None` — the method is declared as doing nothing useful
- Body explicitly `return None` — callers get `None` instead of a bool
- No callers exist outside this file (grep confirms), but the API contract is broken for any future consumer

**Required change:**
- Change return type to `-> bool`
- Return `True` when evaluator is compatible, `False` when it's not (e.g., wrong type, None)
- Handle edge cases: `None` evaluator, wrong type → return `False` (per CONTEXT.md decision)
- No exceptions for invalid input — "not compatible" is the honest answer

**Risk:** LOW — no external callers, backward-compatible if callers previously ignored the return value

### 2. BoardEvaluator Abstract Contract (TYPE-02)

**File:** `coach/scoring/evaluator.py` (lines 13-15)

**Current state:**
```python
class BoardEvaluator:
    def score(self, state: GameState) -> float:
        raise NotImplementedError
```

**Subclasses (all in same file):**
- `HeuristicEvaluator(BoardEvaluator)` — implements `score()`
- `SklearnEvaluator(BoardEvaluator)` — implements `score()` (calls `_load()`)
- `LinearEvaluator(BoardEvaluator)` — implements `score()` (calls `_features()`)

**Required change:**
- Convert to `ABC` with `@abstractmethod` on `score()`
- All three subclasses already implement `score()` → no breakage
- `@dataclass(frozen=True, slots=True)` on subclasses is compatible with ABC inheritance

**Compatibility check:**
- `HeuristicEvaluator` — `@dataclass(frozen=True, slots=True)`, implements `score()` ✓
- `SklearnEvaluator` — `@dataclass(frozen=True, slots=True)`, implements `score()` ✓
- `LinearEvaluator` — `@dataclass(frozen=True, slots=True)`, implements `score()` ✓

**Risk:** LOW — `raise NotImplementedError` → `@abstractmethod` is equivalent but catches errors at instantiation instead of call time

### 3. transform_batch() Schema Validation (SCHM-01, SCHM-02)

**File:** `models/feature_engineering.py`

**transform_batch() (line 1473):**
```python
def transform_batch(self, rows: Sequence[Mapping[str, Any]]) -> np.ndarray:
    n = len(rows)
    if n == 0:
        return np.zeros(...)
    # No input validation — dives straight into feature extraction
```

**transform_arrow_batch() (line 1702):**
```python
def transform_arrow_batch(self, batch: Any) -> np.ndarray:
    n = batch.num_rows
    if n == 0:
        return np.zeros(...)
    schema_names = set(batch.schema.names)
    # Uses schema_names but never validates required columns are present
```

**Column access patterns:**
- Dict path: Accesses `row.get("level")`, `row.get("hp")`, `row.get("gold")`, etc. with defaults
- Arrow path: Uses `_col_np()` helper with defaults, `_col_decoded()` helper with None fills
- Both paths silently produce zero-filled features when columns are missing

**Required columns (from both paths):**
- Scalar: `level`, `hp`, `gold`, `round`, `streak`, `opponent_hp`
- JSON/structured: `units`, `traits`, `augments`
- Optional matchup: `opponent_units`, `opponent_traits`

**Validation approach (per CONTEXT.md decisions):**
- Manual column check using set difference — no pandera dependency
- Column presence only — no dtype validation
- Collect ALL missing columns before raising
- ValueError message includes: missing columns, present columns, expected columns, which path
- Validation runs after normalization (critical requirement from roadmap)

**Where to validate:**
- Dict path (`transform_batch`): Check first row's keys against required set
- Arrow path (`transform_arrow_batch`): Check `batch.schema.names` against required set
- Share a single required-columns definition (post-normalization shapes are identical for scalar columns)

**Risk:** LOW — adds a guard at the entry point of existing methods; existing valid data passes through unchanged

### 4. Existing Test Infrastructure

**Relevant test files:**
- `tests/test_feature_engineering.py` — Tests for `TFTFeatureEngineer` with sample rows
- `tests/test_coach_planner.py`, `tests/test_coach_combat_scorer.py` — Coach module tests
- No existing tests for `RuntimeEvaluator` or `BoardEvaluator`

**Test approach:**
- TYPE-01/TYPE-02: New test file `tests/test_coach_evaluator.py` for evaluator contracts
- SCHM-01/SCHM-02: Add tests to `tests/test_feature_engineering.py` for validation behavior

### 5. Existing Error Patterns (from Phases 1-3)

Error message style established in prior phases:
```python
# Phase 1: specific + actionable
raise ImportError(
    "pyarrow is required for DataLoader but could not be imported. "
    "Install: pip install 'pyarrow>=14.0'. "
    "Without pyarrow, the data pipeline silently returns empty iterators."
)

# Phase 3: file path + resolution
raise FileNotFoundError(
    f"combat_data.json not found at '{path}'. "
    "Expected at simulator/game/data/combat_data.json."
)
```

Schema validation errors should follow this pattern:
```python
raise ValueError(
    f"Missing required columns in {path_name} input: {sorted(missing)}. "
    f"Present columns: {sorted(present)}. "
    f"Required columns: {sorted(required)}."
)
```

## Implementation Complexity

| Requirement | Files Modified | Lines Changed (est.) | Risk |
|-------------|---------------|---------------------|------|
| TYPE-01 | 1 (`evaluator.py`) | ~15 | LOW |
| TYPE-02 | 1 (`evaluator.py`) | ~10 | LOW |
| SCHM-01 | 1 (`feature_engineering.py`) | ~30 | LOW |
| SCHM-02 | 1 (`feature_engineering.py`) | ~10 (shared with SCHM-01) | LOW |

**Total:** 2 source files modified, ~65 lines changed, plus ~80 lines of new tests.

## Dependencies

- No new dependencies required (ABC is stdlib, set operations are builtin)
- No pandera (per CONTEXT.md decision)
- Phase 3 must be complete (it is — confirmed in STATE.md)

## RESEARCH COMPLETE
