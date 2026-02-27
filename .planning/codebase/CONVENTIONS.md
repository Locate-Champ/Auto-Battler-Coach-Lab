# Coding Conventions

**Analysis Date:** 2026-02-27

## Naming Patterns

**Files:**
- Python modules: `snake_case.py` (e.g., `feature_engineering.py`, `combat_scorer.py`)
- TypeScript/React components: `PascalCase.tsx` for components (e.g., `CoachingPanel.tsx`), `camelCase.ts` for utilities (e.g., `useGameState.ts`)
- Test files: `test_<module>.py` prefix (e.g., `test_feature_engineering.py`)

**Functions:**
- Python: `snake_case` (e.g., `_normalize_token()`, `generate_candidates()`)
- Private/internal Python functions: leading underscore (e.g., `_build_team()`, `_assign_positions_deterministically()`)
- TypeScript: `camelCase` for functions and utilities
- React component functions: `PascalCase` with React.FC type annotation (e.g., `const TipCard: React.FC<{ tip: Tip }> = ({ tip }) => ...`)

**Variables:**
- Python: `snake_case` (e.g., `max_candidates_items`, `win_streak`, `loss_streak`)
- TypeScript: `camelCase` (e.g., `gameState`, `tipType`, `stageSections`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `EPSILON`, `STAR_SCALING_HP`, `BOARD_COLS`)
- Module-level lookup tables: `_CONSTANT_NAME` with leading underscore (e.g., `_ECON_AUGMENT_KEYWORDS`, `_CC_HEAVY_NAME_KEYS`)

**Types:**
- Python dataclasses: `PascalCase` (e.g., `FeatureConfig`, `TraitMetadata`, `CombatEstimate`)
- TypeScript interfaces: `PascalCase` (e.g., `Tip`, `GameState`, `AugmentRow`)
- TypeScript type aliases: `PascalCase` (e.g., `TipType`, `AugmentChoiceType`)
- Generic dict keys: `camelCase` (e.g., `win_prob`, `expected_hp_delta`, `n_sims`)

## Code Style

**Formatting:**
- Tool: Ruff (formatting via `ruff format`)
- Line length: 100 characters (configurable in `ruff.toml`)
- Indentation: 4 spaces (Python), 2 spaces (TypeScript/React)
- Quote style: Double quotes (`"`) for strings in formatted code

**Linting:**
- Tool: Ruff (configured in `ruff.toml`)
- Active rulesets: E (pycodestyle errors), F (pyflakes), W (warnings), I (isort)
- Ignored rules:
  - `E501`: Line-too-long (enforced by formatter, not linter)
  - `E741`: Ambiguous variable names (allowed in math-heavy simulator code)
  - `F841`: Unused variable assignments (revisit later)
- Legacy exemptions: `simulator/Simulator/**`, `simulator/Concurrency/**`, `simulator/Evaluator/**` are not linted

**Import Organization:**
- Order: Standard library → Third-party → First-party (isort)
- First-party packages: `simulator`, `coach`, `app`, `models`, `src`
- Use `from __future__ import annotations` at top of all modern Python files for forward-compatible type hints
- Explicit imports preferred over star imports, except in `__init__.py` re-exports (which use `F401` ignore)
- Conditional imports with try/except for optional features:
  ```python
  try:
      from .fe_fast import CYTHON_AVAILABLE as _CYTHON_FE
  except ImportError:
      _CYTHON_FE = False
  ```

**Path Aliases:**
- Python: No path aliases; use relative/absolute imports
- TypeScript: Path aliases via tsconfig (check `app/frontend/tsconfig.json` for specifics)

## Error Handling

**Patterns:**
- Python: Use `try/except` with specific exception types
  ```python
  try:
      stage_num = int(stage.split("-")[0])
  except (ValueError, IndexError):
      return default_value
  ```
- Bare `except Exception:` acceptable only for broad fallback patterns (e.g., `except Exception: return 4`)
- Custom exceptions: Extend `Exception` with docstrings explaining the error context
- Assertions: Used in tests; not for runtime validation in production code
- Early returns: Preferred over deeply nested conditionals

## Logging

**Framework:** `print()` for simple output in CLI tools and demos (e.g., `coach/demo.py`, `coach/offline/` scripts)

**Patterns:**
- Use `print(f"[STATUS] ...")` for status messages
- Use `print(f"[OK] ...")` for success
- Use `print(f"[FAIL] ...")` for failures/errors
- Use `print(f"[GATE] ...")` for test gate status
- No structured logging framework; print-based for operational visibility
- No log levels; output is all operational traces

## Comments

**When to Comment:**
- Comment non-obvious algorithmic choices, especially in performance-critical paths
- Document math-heavy operations with references (e.g., scaling factors, probability calculations)
- Explain bitflag manipulations and compact single-line logic
- Note intentional deviations from clean code (e.g., `# Compact single-line intentional` in `models/feature_engineering.py`)

**Docstrings:**
- Use triple-quoted docstrings for functions and classes
- Function docstrings: Brief description (one line), optional longer explanation
- Format: Google-style or brief one-liners:
  ```python
  def _normalize_token(value: Any) -> str:
      """Normalize free-form names into a stable key."""

  def validate_comp_for_level(engine: CombatEngine, units: list, player_level: int) -> dict:
      """
      Validate if a comp is legal for a given player level.

      Returns:
          dict with 'valid' bool and 'issues' list
      """
  ```
- No JSDoc/TSDoc for React components; type annotations via React.FC and interface definitions suffice

## Function Design

**Size:** Prefer functions under 50 lines; break complex logic into smaller helpers with `_` prefix for internal

**Parameters:**
- Type-hint all parameters (e.g., `state: GameState`, `units: tuple[UnitState, ...]`)
- Dataclasses and frozen dataclasses for structured parameters
- Avoid mutable default arguments (use `None` + check in body)

**Return Values:**
- Explicit return type hints required (e.g., `-> CombatEstimate`, `-> list[str]`)
- Prefer returning immutable types (tuples, frozen dataclasses)
- Return early rather than storing result in temporary variables

## Module Design

**Exports:**
- `__init__.py` files use explicit re-exports to define public API
- Example: `src/models/__init__.py` re-exports key classes with `F401` ignore
- Modules with public APIs include docstring at top explaining purpose

**Barrel Files:**
- Used in `src/models/` and `simulator/core/combat_fast/` to expose public interfaces
- Convention: `from module import Class` followed by `__all__` list or `F401` ignore for re-exports

## Dataclass Conventions

**Python:**
- Use `@dataclass(frozen=True, slots=True)` for immutable state objects (e.g., `CombatEstimate`, `GameState`)
- Use `@dataclass` without freezing for mutable containers (e.g., `FeatureConfig` for optional features)
- Include type hints for all fields
- Optional fields use `Optional[T] = None`
- Implement `__getstate__` and `__setstate__` for pickle support in large objects (e.g., `TFTFeatureEngineer`)

**TypeScript:**
- Use `interface` for object shape definitions (e.g., `interface Tip { type: TipType; ... }`)
- Use `type` for union types and aliases (e.g., `type TipType = 'econ' | 'combat' | ...`)
- Props interfaces: suffix with `Props` (e.g., `CoachingPanelProps`)

## Hot-Path Performance Patterns

**In `models/feature_engineering.py` (compiler rules E701, E702 ignored):**
- Compact single-line operations for bitflag accumulation (e.g., `flags |= 1`)
- Pre-computed lookup tables (e.g., `_CHAMPION_PACKED`, `_ITEM_PACKED`) to avoid repeated conversions
- LRU caching via `@functools.lru_cache` for expensive conversions (e.g., `_normalize_token`)

---

*Convention analysis: 2026-02-27*
