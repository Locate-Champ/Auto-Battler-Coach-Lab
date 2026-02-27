# Testing Patterns

**Analysis Date:** 2026-02-27

## Test Framework

**Runner:**
- pytest (Python)
- No frontend test runner configured (see `.planning/codebase/CONCERNS.md` for implications)

**Assertion Library:**
- pytest assertions (native `assert` statements)

**Run Commands:**
```bash
pytest                          # Run all tests in tests/ and simulator/
pytest tests/test_coach_planner.py    # Run specific test file
pytest tests/ -v               # Verbose output
pytest tests/ --tb=short       # Short traceback format
pytest -k "combat"             # Run tests matching pattern
```

## Test File Organization

**Location:**
- `tests/` directory for main test suite (30+ test files)
- `simulator/test_*.py` for simulator-specific tests (co-located with source)
- Test files are separate from source, not co-located with code

**Naming:**
- Pattern: `test_<module>.py` (e.g., `test_feature_engineering.py`, `test_coach_planner.py`)
- Test functions: `test_<description>()` (e.g., `test_transform_has_no_nan_values()`)
- Helper functions: `_<description>()` with leading underscore (e.g., `_sample_row()`, `_state_for_items()`)

**Structure:**
```
tests/
├── test_feature_engineering.py         # Model/feature engineering tests
├── test_coach_planner.py              # Coach decision logic tests
├── test_coach_artifacts.py            # Coach artifact/directory tests
├── test_combat_regressions.py         # Combat engine regression tests
├── test_data_loader.py                # Data loading/streaming tests
├── conftest.py (optional)             # Pytest fixtures/config
└── ...
```

## Test Structure

**Test Organization (pytest.ini discovery):**
```ini
[pytest]
testpaths =
    tests
    simulator
norecursedirs =
    UnitTests
    Simulator
    TestInterface
```

**Conftest Setup:**
- `simulator/conftest.py`: Adds simulator root to sys.path so relative imports work
- No global conftest in tests/ root; fixtures defined locally in test files

**Typical Test Suite Pattern:**
```python
from __future__ import annotations

from pathlib import Path
import pytest

from coach.coach import Coach
from coach.state import GameState, PlayerState, UnitState


def _state_for_items() -> GameState:
    """Helper to build deterministic test state."""
    player = PlayerState(level=6, hp=78, gold=22, win_streak=0, loss_streak=2)
    board = (
        UnitState(
            instance_id="u0",
            champion_id="TFT16_Draven",
            star_level=2,
            items=(),
            position=(0, 6),
            location="board",
        ),
    )
    return GameState(stage="3-2", player=player, board=board)


def test_describe_what_is_tested() -> None:
    state = _state_for_items()
    result = some_function(state)
    assert result.field == expected_value
```

## Mocking

**Framework:** pytest's `monkeypatch` fixture (built-in)

**Patterns:**
```python
def test_with_monkeypatch(monkeypatch) -> None:
    monkeypatch.setenv("COACH_OUTPUTS_DIR", str(tmp_path))
    monkeypatch.setattr(module, "_RUST_PARQUET_API_VALIDATED", set())
    monkeypatch.delenv("KEY", raising=False)
```

**Usage:**
- Environment variables: `monkeypatch.setenv()`, `monkeypatch.delenv()`
- Module/class attributes: `monkeypatch.setattr(module, "attr", value)`
- No external mocking library (like unittest.mock); monkeypatch is sufficient

**What to Mock:**
- Environment variables for artifact path resolution tests
- Module-level state flags for testing validation logic
- External file system paths using pytest's `tmp_path` fixture

**What NOT to Mock:**
- Core game logic (CombatEngine, GameState); use real instances with test data
- Feature engineering or ML models; use actual implementations with sample data
- Coach decision-making; test with real state objects
- Dataloader; test with real Parquet/JSON files in temp directories

## Fixtures and Factories

**Test Data Patterns:**
```python
def _sample_row() -> dict:
    """Factory for feature engineering test data."""
    return {
        "game_id": 1,
        "round": 12,
        "player_id": 0,
        "level": 7,
        "hp": 74,
        "gold": 32,
        "units": [
            {
                "champion_id": "TFT16_Fiddlesticks",
                "star_level": 2,
                "items": ["TFT_Item_BlueBuff"],
            },
        ],
        "opponent_units": [...],
        "combat_result": 1,
        "placement": 2,
    }


def _state_for_items() -> GameState:
    """Factory for coach state with specific setup."""
    player = PlayerState(level=6, hp=78, gold=22, win_streak=0, loss_streak=2)
    return GameState(stage="3-2", player=player, board=(...))
```

**Location:**
- Factories defined as `_helper_function()` at module top, before test functions
- No separate fixture files; helpers co-located with tests using them
- pytest `tmp_path` fixture used for file-based tests:
  ```python
  def test_with_temp_directory(tmp_path: Path) -> None:
      output_file = tmp_path / "output.json"
      # Write and test
  ```

## Coverage

**Requirements:** No enforced coverage target; tests are regression + functionality focused

**Run Coverage:**
```bash
pytest --cov=coach --cov=models --cov-report=html
```

Coverage reports in `htmlcov/` (not committed)

## Test Types

**Unit Tests:**
- Scope: Single function or class method
- Approach: Test with minimal dependencies; use factories for test data
- Example: `test_transform_has_same_length_as_feature_names()` tests `TFTFeatureEngineer.transform()`
- Deterministic: All tests with fixed seeds for RNG

**Integration Tests:**
- Scope: Multiple components interacting
- Approach: Combine coach planning, combat scoring, feature engineering
- Example: `test_coach_planner_chooses_item_slam_when_items_available()` runs full coach pipeline
- Use deterministic seeds (`combat_base_seed=123`) for reproducibility

**Regression Tests:**
- Scope: Combat engine correctness, trait scoping, item effects
- Approach: Test specific known issues with explicit assertions
- File: `tests/test_combat_regressions.py`
- Example: `test_hp_item_updates_max_hp_and_starts_full()` verifies HP items work correctly

**Gate Tests (CI):**
- Scope: Public surface allowlist, path validation, contract checks
- Example: `test_public_surface_allowlist.py` ensures new files are declared
- Example: `test_ingest_contract.py` validates data schema consistency
- Run in CI to catch breaking changes early

## Parametrized Tests

**Pattern:**
```python
PERSISTENT_EFFECT_TEST_CASES: list[tuple[str, float]] = [
    ("ManaRegen", 2.0),
    ("AbilityPower", 25.0),
]


@pytest.mark.parametrize(
    ("effect_name", "effect_value"),
    PERSISTENT_EFFECT_TEST_CASES,
    ids=[effect_name for effect_name, _effect_value in PERSISTENT_EFFECT_TEST_CASES],
)
def test_item_conditional_augment_persists_effect(
    effect_name: str,
    effect_value: float,
) -> None:
    engine = CombatEngine(logging_enabled=False)
    # Test using effect_name and effect_value
```

**Usage:**
- Define test case list at module top as tuple of (input, expected)
- Use `ids=` for readable test names (instead of `[0]`, `[1]`, etc.)
- Common for combat mechanics testing with multiple item/trait combinations

## Common Patterns

**Async Testing:**
Not used in codebase (no async/await in Python tests)

**Error Testing:**
```python
def test_validate_coach_state_detects_invalid_stage() -> None:
    state = GameState(stage="", player=PlayerState(...), board=())
    errors = validate_coach_state(state)
    assert "stage: missing/empty" in errors
```

**Determinism Testing:**
```python
def test_combat_scorer_is_deterministic_and_uses_cache() -> None:
    scorer = CombatScorer()
    m1 = scorer.simulate_matchup(..., base_seed=123)
    m2 = scorer.simulate_matchup(..., base_seed=123)
    assert m1 == m2  # Exact equality
```

**State Mutation Testing:**
```python
def test_trait_scoping_bilgewater_serpents() -> None:
    engine = CombatEngine(logging_enabled=False)
    attacker = engine.create_unit(...)
    defender = engine.create_unit(...)

    # Avoid mutating shared combat-data list by copying
    attacker.traits = list(attacker.traits) + ["Bilgewater"]

    engine.units = [attacker, defender]
    engine._alive_team0 = [attacker]
    engine._alive_team1 = [defender]

    # Test effect
```

## Test Exclusions & Markers

**Marks Used:**
- `@pytest.mark.parametrize` for data-driven tests
- No custom marks; tests either run or are skipped via import guards
- Conditional skip: `pytest.importorskip("torch")` for optional dependencies

**Skip Patterns:**
```python
# In test_dataset_streaming.py
pytest.importorskip("torch")

# In CI: ML-only tests skipped if dependencies missing
# See .github/workflows/test-coverage.yml
```

## Test Isolation

**Fixture Cleanup:**
- `tmp_path` automatically cleaned by pytest
- Environment variable changes reverted by `monkeypatch` (fixture scope)
- No explicit teardown; rely on pytest fixture lifecycle

**State Isolation:**
- Each test function is independent
- Avoid module-level state mutations
- Use factories (`_state_for_items()`) to create fresh test data per test

---

*Testing analysis: 2026-02-27*
