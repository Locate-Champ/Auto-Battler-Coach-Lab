# Phase 7: SklearnEvaluator Wiring - Research

**Researched:** 2026-02-27
**Domain:** sklearn/XGBoost model integration, feature schema bridging, evaluator pipeline
**Confidence:** HIGH

## Summary

This phase wires `SklearnEvaluator.score()` to extract features from `GameState`, replacing the current `NotImplementedError` stub. The core challenge is bridging two different data formats: the `GameState` dataclass used by the coach evaluator system, and the raw collector row dicts consumed by `TFTFeatureEngineer.transform()`. The training pipeline (`train_xgboost.py`) saves models via `model.save_model()` (XGBoost native JSON), but the existing `SklearnEvaluator._load()` uses `joblib.load()` -- this mismatch must be addressed. The XGBoost model predicts placement (1-8), so score mapping to the 0-1 `BoardEvaluator.score()` return value requires an explicit conversion.

The feature engineering pipeline (`TFTFeatureEngineer`) produces a dense feature vector whose column order is determined by `_build_feature_names()` and depends on loaded reference data (champions, traits, items, augments). The SklearnEvaluator must use the same `TFTFeatureEngineer` instance (or one with the same config and reference data) to produce column-compatible feature vectors. The safest approach is to instantiate `TFTFeatureEngineer` at `SklearnEvaluator` construction time and call `transform()` with a GameState-to-row-dict adapter.

The `default_evaluator()` fallback chain currently tries LinearEvaluator, then falls back to HeuristicEvaluator. Per CONTEXT.md decisions, SklearnEvaluator becomes highest priority: Sklearn -> Linear -> Heuristic, with INFO logging for which evaluator was selected.

**Primary recommendation:** Build a `_gamestate_to_row()` adapter that converts `GameState` into the dict format `TFTFeatureEngineer.transform()` expects, then use the feature engineer to produce the feature vector for model prediction.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Evaluator selection chain
- SklearnEvaluator becomes **highest priority** in `default_evaluator()` fallback chain: Sklearn -> Linear -> Heuristic
- Model artifact discovered via **convention path** in the runtime outputs directory (same pattern as `evaluator_linear.json`)
- When both sklearn and linear artifacts exist, **sklearn wins**
- `default_evaluator()` **always logs at INFO** which evaluator was selected and why (aligns with Phase 2 observable-fallbacks work)

#### Score interpretation
- The XGBoost model predicts **placement (1st-8th)** -- this is the training target
- Claude determines the mapping from placement prediction to the 0-1 `BoardEvaluator.score()` return value
- Claude determines whether calibration against HeuristicEvaluator's range is needed

#### Failure behavior
- **Model load failure** (missing file, corrupt artifact): **raise RuntimeError immediately** -- caller (`default_evaluator`) catches and falls to next evaluator in chain
- **Feature extraction failure** (model expects features SklearnEvaluator can't compute from GameState): **raise ValueError with details** listing which features are missing -- forces fix before deployment
- **predict_proba() runtime error**: Claude's discretion on whether to propagate or handle

### Claude's Discretion
- Feature schema source: where SklearnEvaluator gets the column list (import from models/, read from model metadata, or own mapping)
- Whether to reuse `coach/scoring/features.py` helpers (board_power, derive_traits, etc.) vs standalone extraction
- Schema match strictness (exact column-name match vs positional)
- Feature drift handling (fail loudly vs zero-fill for unknown columns)
- Score mapping implementation (predict_proba interpretation, normalization)
- Score calibration approach
- predict_proba error handling strategy

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SKLR-01 | SklearnEvaluator feature extraction implemented (matches training schema from train_xgboost.py) | GameState-to-row adapter pattern, TFTFeatureEngineer integration, feature_names() column matching, placement-to-score mapping |
| SKLR-02 | SklearnEvaluator integration tested with mock sklearn model | Mock model with predict/predict_proba, synthetic GameState fixture, column-name verification pattern, CI-safe test without real model artifact |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| models.feature_engineering.TFTFeatureEngineer | (project) | Feature vector construction | Already the training pipeline's feature engineer; reusing ensures schema match |
| models.feature_engineering.FeatureConfig | (project) | Feature group toggles | Controls which feature groups are active; must match training config |
| coach.scoring.evaluator.BoardEvaluator | (project) | Abstract evaluator base class | All evaluators implement this ABC |
| coach.state.GameState | (project) | Input state dataclass | The input to score() |
| numpy | >=1.24 | Feature vector array | Already a dependency, used by TFTFeatureEngineer |
| joblib | (existing dep) | Model deserialization | Already used by SklearnEvaluator._load() |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| coach.scoring.features | (project) | derive_traits, board_power helpers | Building the trait dict for the row adapter |
| coach.artifacts | (project) | runtime_outputs_dir() | Convention path discovery |
| logging | stdlib | Observable fallbacks | INFO-level evaluator selection logging |
| unittest.mock | stdlib | Mock sklearn model | Integration test without real artifact |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| TFTFeatureEngineer | Hand-rolled feature extraction | Would drift from training schema; reusing FE is safer |
| joblib | XGBoost native load_model | train_xgboost.py saves as JSON via save_model(); joblib is for sklearn-wrapped models; need to decide which format to support |

**Installation:** No new dependencies required. All libraries already in the project.

## Architecture Patterns

### Recommended Project Structure
```
coach/scoring/
    evaluator.py           # SklearnEvaluator changes (score() implementation)
                           # default_evaluator() changes (priority chain + logging)
tests/
    test_coach_evaluator.py  # Extended with SKLR-01 and SKLR-02 tests
```

### Pattern 1: GameState-to-Row Adapter
**What:** A function that converts a `GameState` into the `Dict[str, Any]` format that `TFTFeatureEngineer.transform()` expects.
**When to use:** Every `SklearnEvaluator.score()` call.
**Why this pattern:** The feature engineer's `transform()` method expects a collector row dict with keys like `level`, `hp`, `gold`, `round`, `streak`, `units`, `traits`, `augments`. GameState has these as structured fields. The adapter bridges the two.
**Example:**
```python
# Source: codebase analysis of feature_engineering.py _economy_features (line 1236)
# and _extract_units (line 776) and _extract_traits (line 750)
def _gamestate_to_row(state: GameState) -> dict[str, Any]:
    """Convert GameState to the dict format TFTFeatureEngineer.transform() expects."""
    # Economy fields (from _economy_features at line 1236)
    row: dict[str, Any] = {
        "level": state.player.level,
        "hp": state.player.hp,
        "gold": state.player.gold,
        "round": state.stage_number * 7 + state.round_number,  # approximate
        "streak": state.player.streak,  # PlayerState.streak property = win - loss
    }
    # Units field (from _extract_units at line 776, tries "units" key first)
    row["units"] = [
        {
            "champion_id": u.champion_id,
            "star_level": u.star_level,
            "items": list(u.items),
            "position": u.position,
        }
        for u in state.board
    ]
    # Traits field (from _extract_traits at line 750, tries "traits" key as dict)
    row["traits"] = dict(state.traits) if state.traits else {}
    # Augments field
    row["augments"] = list(state.augments)
    return row
```

### Pattern 2: Placement-to-Score Mapping
**What:** Convert XGBoost placement prediction (1-8 float) to 0-1 BoardEvaluator score.
**When to use:** After model prediction, before returning from score().
**Why this pattern:** The training target is placement (1=best, 8=worst). Lower placement is better. The score() contract returns higher values for stronger boards.
**Example:**
```python
# Linear inversion: placement 1 -> score 1.0, placement 8 -> score 0.0
# For placement regression models:
def _placement_to_score(placement: float) -> float:
    return max(0.0, min(1.0, (8.0 - placement) / 7.0))

# For classification models (predict_proba for top4/fight):
# predict_proba()[:, 1] already returns probability in [0, 1]
# which can be used directly as the score.
```

### Pattern 3: Model Format Handling
**What:** The training pipeline saves models via `model.save_model(path)` (XGBoost native JSON format), but SklearnEvaluator uses `joblib.load()`. Need to support the right format.
**When to use:** Model loading in SklearnEvaluator._load().
**Analysis:**
- `train_xgboost.py` line 926: `model.save_model(model_path)` saves as `{task}_xgboost.json`
- This saves the XGBoost-native JSON format, not a joblib-serialized sklearn wrapper
- `evaluate.py` lines 219-240: loads via `xgb.XGBClassifier()` + `model.load_model(path)`
- The existing `SklearnEvaluator._load()` uses `joblib.load()` which expects a different format
- **Decision needed:** Either (a) keep joblib and expect users to re-save models via joblib, or (b) support XGBoost native format too
- **Recommendation:** Support the sklearn-compatible model (joblib) as designed -- the convention artifact in `outputs/coach/` can be a joblib-serialized model. The training pipeline's JSON output is for the checkpoints dir; a separate export step saves the runtime artifact via joblib. This aligns with the existing `evaluator_linear.json` pattern where runtime artifacts differ from training artifacts.

### Pattern 4: Observable Evaluator Selection
**What:** `default_evaluator()` logs which evaluator was selected at INFO level.
**When to use:** Every call to `default_evaluator()`.
**Example:**
```python
# Source: CONTEXT.md locked decision
def default_evaluator() -> BoardEvaluator:
    # Try sklearn first (highest priority)
    sklearn_path = runtime_outputs_dir() / "evaluator_sklearn.joblib"
    if sklearn_path.exists():
        try:
            evaluator = SklearnEvaluator(model_path=str(sklearn_path))
            evaluator._load()  # Validate model loads correctly
            _log.info("Evaluator selected: SklearnEvaluator from %s", sklearn_path)
            return evaluator
        except (OSError, ValueError, KeyError, RuntimeError):
            _log.warning("SklearnEvaluator failed to load from %s, trying next", sklearn_path)

    # Try linear evaluator
    linear_path = runtime_outputs_dir() / "evaluator_linear.json"
    if linear_path.exists():
        try:
            evaluator = LinearEvaluator.from_json(linear_path)
            _log.info("Evaluator selected: LinearEvaluator from %s", linear_path)
            return evaluator
        except (OSError, ValueError, KeyError, RuntimeError):
            _log.warning("LinearEvaluator failed to load from %s, trying next", linear_path)

    _log.info("Evaluator selected: HeuristicEvaluator (no trained model found)")
    return HeuristicEvaluator()
```

### Anti-Patterns to Avoid
- **Duplicating feature logic:** Do NOT re-implement feature extraction in evaluator.py. Use TFTFeatureEngineer to guarantee schema match.
- **Hardcoding column names:** Do NOT maintain a separate list of feature names. Get them from `feature_engineer.feature_names()`.
- **Swallowing prediction errors:** Per CONTEXT.md, feature extraction failures must raise ValueError with details. Do not zero-fill or silently degrade.
- **Importing heavy deps at module level:** joblib and TFTFeatureEngineer should be imported lazily (in `_load()` or `score()`) to avoid import-time failures for users who don't use sklearn evaluator.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Feature extraction from game state | Custom feature computation | `TFTFeatureEngineer.transform()` | 100+ features with complex normalization; any drift from training schema produces wrong predictions |
| Feature name ordering | Manual column list | `TFTFeatureEngineer.feature_names()` | Dynamic based on reference data; depends on FeatureConfig toggles |
| Model serialization | Custom pickle/JSON | `joblib.load()` (already in codebase) | Handles numpy arrays, sklearn pipelines, and version compatibility |
| Placement-to-score math | Complex calibration | Linear mapping `(8 - placement) / 7` | Simple, interpretable, monotonic; calibration adds complexity with unclear benefit |

**Key insight:** The feature engineering pipeline is 2100+ lines of carefully tuned logic with reference data dependencies, Cython fast paths, and multiple input format handlers. Reusing it via the adapter pattern is the only safe approach.

## Common Pitfalls

### Pitfall 1: Feature Count Mismatch
**What goes wrong:** SklearnEvaluator produces a feature vector with a different number of columns than the model expects, causing cryptic dimension errors at prediction time.
**Why it happens:** `TFTFeatureEngineer.feature_names()` length depends on loaded reference data (number of traits, champions, items). If the feature engineer at evaluation time loads different reference data than at training time, counts differ.
**How to avoid:** Store the expected feature count in model metadata or validate `len(feature_engineer.feature_names())` against `model.n_features_in_` at load time. Raise ValueError immediately on mismatch.
**Warning signs:** `XGBoostError: feature_names mismatch` or numpy shape errors.

### Pitfall 2: Round Number Encoding
**What goes wrong:** The feature engineer's `_economy_features()` uses `row["round"]` as an integer round number (e.g., 4, 10, 17...). GameState stores stage as "4-2" string.
**Why it happens:** The training pipeline gets `round` from raw simulation data (an absolute round counter). GameState has `stage` (e.g., "4-2") and derived `stage_number`/`round_number` properties.
**How to avoid:** The adapter must compute an approximate absolute round number from `stage_number` and `round_number`. The mapping is: `base = 4 + (stage - 2) * 7 + (round_in_stage - 1)` for stage >= 2 (see `coach.py` line 82-97 `_round_num_from_stage`).
**Warning signs:** Economy features like `round` and `stage` having unexpected values.

### Pitfall 3: Frozen Dataclass Mutation
**What goes wrong:** `SklearnEvaluator` is `@dataclass(frozen=True, slots=True)`, so you cannot assign `self._feature_engineer = ...` after construction.
**Why it happens:** The existing `_load()` method uses `self._model = joblib.load(...)` which violates frozen semantics (but works via `object.__setattr__`).
**How to avoid:** Use `object.__setattr__(self, '_feature_engineer', fe)` pattern (same as existing `_model` caching), or make the feature engineer a constructor parameter with lazy initialization.
**Warning signs:** `FrozenInstanceError` at runtime.

### Pitfall 4: Model Format Confusion
**What goes wrong:** `joblib.load()` is called on an XGBoost native JSON model file, causing deserialization errors.
**Why it happens:** `train_xgboost.py` saves as `{task}_xgboost.json` via `model.save_model()` (XGBoost native format). `SklearnEvaluator._load()` uses `joblib.load()` (expects sklearn-serialized format).
**How to avoid:** The convention artifact in `outputs/coach/` should be explicitly joblib-serialized. The integration test should use a mock model, not a real training artifact.
**Warning signs:** `joblib.load()` raises `ValueError` or `pickle.UnpicklingError`.

### Pitfall 5: Missing Reference Data at Runtime
**What goes wrong:** `TFTFeatureEngineer.__init__()` loads reference data from `simulator/data/combat_data.json`. In a deployment context where this file is absent, feature names will be empty or different.
**Why it happens:** The feature engineer requires `combat_data.json` for champion stats, traits, items. Without it, trait feature names depend on zero loaded traits.
**How to avoid:** The SklearnEvaluator should validate that `len(feature_engineer.feature_names()) > 0` at load time. If reference data is missing, raise RuntimeError immediately rather than producing garbage features.
**Warning signs:** Feature count is 0 or very small (e.g., 8 vs expected 100+).

### Pitfall 6: predict_proba vs predict for Different Tasks
**What goes wrong:** Calling `predict_proba()` on a regression model (placement task) raises AttributeError because regression models don't have `predict_proba`.
**Why it happens:** `train_xgboost.py` trains XGBClassifier for fight/top4 tasks (which have predict_proba) and XGBRegressor for placement task (which only has predict).
**How to avoid:** Check whether the model has `predict_proba` (already done in existing code at line 70-71). For regression models, use `predict()` directly and apply placement-to-score mapping. For classification models, use `predict_proba()[:, 1]` for probability.
**Warning signs:** `AttributeError: 'XGBRegressor' object has no attribute 'predict_proba'`.

## Code Examples

Verified patterns from the existing codebase:

### GameState Fields Available for Adaptation
```python
# Source: coach/state.py
# GameState provides:
state.stage          # "4-2" string
state.stage_number   # 4 (property)
state.round_number   # 2 (property)
state.player.level   # int
state.player.hp      # int
state.player.gold    # int
state.player.streak  # int (property: win_streak - loss_streak)
state.player.interest  # int (property: min(gold // 10, 5))
state.board          # tuple[UnitState, ...] -- each has champion_id, star_level, items, position
state.bench          # tuple[UnitState, ...]
state.augments       # tuple[str, ...]
state.traits         # tuple[tuple[str, int], ...] -- (trait_name, count) pairs
```

### LinearEvaluator._features() Reference Pattern
```python
# Source: coach/scoring/evaluator.py lines 103-114
# This is the existing pattern for GameState -> feature dict in evaluator.py
def _features(self, state: GameState) -> dict[str, float]:
    traits = derive_traits(state.board)
    num_2plus = sum(1 for _, c in traits.items() if c >= 2)
    return {
        "board_power": float(board_power(state.board)),
        "level": float(state.player.level),
        "gold": float(state.player.gold),
        "hp": float(state.player.hp),
        "interest": float(state.player.interest),
        "streak": float(state.player.streak),
        "num_traits_2plus": float(num_2plus),
    }
```

### Feature Engineer Usage (from DataLoader)
```python
# Source: models/data_loader.py line 340-361
# _vectorize_rows calls transform_batch with list of row dicts:
def _vectorize_rows(self, rows):
    n_features = len(self.feature_engineer.feature_names())
    if not rows:
        return np.zeros((0, n_features), dtype=np.float32)
    return self.feature_engineer.transform_batch(list(rows))
```

### What a Row Dict Must Contain
```python
# Source: models/feature_engineering.py lines 47-66
# Required columns after normalization:
REQUIRED_COLUMNS = frozenset({"level", "hp", "gold", "round", "augments"})
# Plus at least one from each group:
# ("streak", "win_streak")
# ("units", "board", "board_names")
# ("traits", "trait_names")
```

### Round Number Computation
```python
# Source: coach/coach.py lines 82-97
def _round_num_from_stage(stage: str) -> int:
    stage_num = int(stage.split("-")[0])
    round_in_stage = int(stage.split("-")[1])
    if stage_num <= 1:
        return max(0, round_in_stage - 1)
    base = 4 + (stage_num - 2) * 7 + (round_in_stage - 1)
    if stage_num >= 3:
        base -= 1
    return max(0, int(base))
```

### Existing SklearnEvaluator._load() Pattern (Frozen Dataclass Workaround)
```python
# Source: coach/scoring/evaluator.py lines 55-65
# Note: uses implicit object.__setattr__ despite frozen=True
def _load(self) -> object:
    if self._model is not None:
        return self._model
    import joblib
    self._model = joblib.load(self.model_path)
    return self._model
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| SklearnEvaluator raises NotImplementedError | Must wire to TFTFeatureEngineer | Phase 7 | Enables ML-backed board evaluation |
| default_evaluator: Linear -> Heuristic | Sklearn -> Linear -> Heuristic | Phase 7 | ML model becomes primary evaluator when available |
| Silent evaluator selection | INFO-level logged selection | Phase 7 (aligns with Phase 2 observable-fallbacks) | Visibility into which evaluator is active |

**Key architectural note:** The `SklearnEvaluator._load()` method already works with frozen dataclass mutation (line 64: `self._model = joblib.load(...)`). This pattern must be extended for the feature engineer instance.

## Open Questions

1. **Artifact naming convention**
   - What we know: LinearEvaluator uses `evaluator_linear.json` in `runtime_outputs_dir()`
   - What's unclear: Exact filename for sklearn artifact. `evaluator_sklearn.joblib` follows the pattern.
   - Recommendation: Use `evaluator_sklearn.joblib` -- matches the `evaluator_linear.json` naming pattern and makes the serialization format explicit in the extension.

2. **Model task type detection**
   - What we know: Training saves different model types (XGBClassifier for fight/top4, XGBRegressor for placement). Each has different prediction methods.
   - What's unclear: Should SklearnEvaluator auto-detect model type, or should the convention path encode the task?
   - Recommendation: Use `hasattr(model, 'predict_proba')` to detect classification vs regression models. This is already in the existing code (line 70-71). For classification, use `predict_proba()[:, 1]` as score directly. For regression (placement), use `(8 - predict()) / 7` mapping.

3. **Feature engineer initialization cost**
   - What we know: `TFTFeatureEngineer.__init__()` loads reference data from disk (`combat_data.json`).
   - What's unclear: Whether this is fast enough for lazy initialization on first `score()` call.
   - Recommendation: Initialize lazily on first `score()` call using the same `object.__setattr__` pattern as `_model`. The reference data loads once and is cached.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (see pytest.ini) |
| Config file | `pytest.ini` |
| Quick run command | `python -m pytest tests/test_coach_evaluator.py -x` |
| Full suite command | `python -m pytest` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SKLR-01 | SklearnEvaluator.score() returns numeric score from GameState | integration | `python -m pytest tests/test_coach_evaluator.py::TestSklearnEvaluatorWiring::test_score_returns_float -x` | No -- Wave 0 |
| SKLR-01 | Feature vector column names match TFTFeatureEngineer.feature_names() | unit | `python -m pytest tests/test_coach_evaluator.py::TestSklearnEvaluatorWiring::test_feature_column_match -x` | No -- Wave 0 |
| SKLR-01 | Placement prediction mapped to 0-1 score range | unit | `python -m pytest tests/test_coach_evaluator.py::TestSklearnEvaluatorWiring::test_placement_to_score_mapping -x` | No -- Wave 0 |
| SKLR-01 | Feature extraction failure raises ValueError with details | unit | `python -m pytest tests/test_coach_evaluator.py::TestSklearnEvaluatorWiring::test_feature_extraction_failure_raises -x` | No -- Wave 0 |
| SKLR-01 | Model load failure raises RuntimeError | unit | `python -m pytest tests/test_coach_evaluator.py::TestSklearnEvaluatorWiring::test_load_failure_raises_runtime_error -x` | No -- Wave 0 |
| SKLR-02 | Integration test with mock sklearn model passes full evaluate() path | integration | `python -m pytest tests/test_coach_evaluator.py::TestSklearnEvaluatorIntegration::test_mock_model_full_path -x` | No -- Wave 0 |
| SKLR-02 | default_evaluator() returns SklearnEvaluator when artifact exists | integration | `python -m pytest tests/test_coach_evaluator.py::TestSklearnEvaluatorIntegration::test_default_evaluator_prefers_sklearn -x` | No -- Wave 0 |
| SKLR-02 | default_evaluator() logs evaluator selection at INFO | unit | `python -m pytest tests/test_coach_evaluator.py::TestSklearnEvaluatorIntegration::test_default_evaluator_logs_selection -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_coach_evaluator.py -x`
- **Per wave merge:** `python -m pytest`
- **Phase gate:** Full suite green + `ruff check .` + `ruff format --check .`

### Wave 0 Gaps
- [ ] `tests/test_coach_evaluator.py` -- extend existing file with TestSklearnEvaluatorWiring and TestSklearnEvaluatorIntegration classes
- [ ] Synthetic GameState fixture for tests (may already exist in conftest or can be built inline)
- [ ] Mock sklearn model fixture (object with predict/predict_proba methods returning numpy arrays)

## Sources

### Primary (HIGH confidence)
- `coach/scoring/evaluator.py` -- Current SklearnEvaluator stub, LinearEvaluator._features() pattern, default_evaluator() chain, BoardEvaluator ABC
- `models/feature_engineering.py` -- TFTFeatureEngineer.transform(), _build_feature_names(), _economy_features(), _extract_units(), _extract_traits(), REQUIRED_COLUMNS
- `models/train_xgboost.py` -- Training pipeline: save_model() format, task types (fight/top4/placement), model classes (XGBClassifier/XGBRegressor)
- `coach/state.py` -- GameState, PlayerState, UnitState dataclass definitions
- `coach/scoring/features.py` -- derive_traits(), board_power(), squash01() helpers
- `coach/artifacts.py` -- runtime_outputs_dir() convention path
- `coach/coach.py` -- _round_num_from_stage() round number computation, Coach.evaluator usage
- `models/data_loader.py` -- _vectorize_rows() showing how feature engineer is called
- `tests/test_coach_evaluator.py` -- Existing evaluator tests (TYPE-01/TYPE-02)
- `models/feature_config.py` -- NumericFeatureConfig frozen dataclass

### Secondary (MEDIUM confidence)
- `outputs/coach/` directory listing -- confirmed `evaluator_linear.json` exists as convention artifact
- `models/evaluate.py` -- XGBoost native model loading pattern via load_model()

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all components are already in the codebase; no new libraries needed
- Architecture: HIGH -- clear adapter pattern with strong evidence from existing LinearEvaluator pattern and feature engineering pipeline
- Pitfalls: HIGH -- identified from direct code analysis of format mismatches, frozen dataclass constraints, and model type differences

**Research date:** 2026-02-27
**Valid until:** 2026-03-27 (stable -- internal codebase, no external API changes expected)
