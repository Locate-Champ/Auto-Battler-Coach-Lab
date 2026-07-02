---
phase: 07-sklearnevaluator-wiring
plan: 01
subsystem: scoring
tags: [sklearn, xgboost, feature-engineering, evaluator, joblib]

# Dependency graph
requires:
  - phase: 04-type-contracts-and-schema-validation
    provides: BoardEvaluator ABC, SklearnEvaluator stub, REQUIRED_COLUMNS schema
  - phase: 06-configuration-extraction-and-ruff-gates
    provides: NumericFeatureConfig for TFTFeatureEngineer
provides:
  - Working SklearnEvaluator.score() with TFTFeatureEngineer integration
  - _gamestate_to_row() adapter bridging GameState to feature engineer row format
  - _placement_to_score() mapping predicted placement to 0-1 score
  - Updated default_evaluator() priority chain (Sklearn > Linear > Heuristic)
  - Observable evaluator selection with INFO-level logging
affects: [coach-pipeline, model-deployment, runtime-api]

# Tech tracking
tech-stack:
  added: []
  patterns: [gamestate-to-row-adapter, lazy-feature-engineer-init, placement-to-score-mapping, frozen-dataclass-object-setattr]

key-files:
  created: []
  modified:
    - coach/scoring/evaluator.py
    - tests/test_coach_evaluator.py

key-decisions:
  - "Always use model.predict() (not predict_proba) with placement-to-score linear mapping for simplicity and robustness across regressor/classifier model types"
  - "Replicate _round_num_from_stage() inline in evaluator.py to avoid circular import from coach.coach"
  - "Fixed frozen dataclass mutation bug: existing _load() used direct assignment on frozen dataclass; switched to object.__setattr__() pattern"

patterns-established:
  - "GameState-to-row adapter: _gamestate_to_row() converts structured GameState to dict format for TFTFeatureEngineer.transform()"
  - "Lazy feature engineer: TFTFeatureEngineer instantiated on first score() call via object.__setattr__() on frozen dataclass"

requirements-completed: [SKLR-01, SKLR-02]

# Metrics
duration: 4min
completed: 2026-02-27
---

# Phase 7 Plan 01: SklearnEvaluator Wiring Summary

**ML-backed board evaluator wired via TFTFeatureEngineer adapter with placement-to-score mapping, observable evaluator selection chain, and 11 integration tests**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-27T20:17:46Z
- **Completed:** 2026-02-27T20:21:35Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- SklearnEvaluator.score() returns a float in [0, 1] from any GameState without raising NotImplementedError
- Feature vector column order matches TFTFeatureEngineer.feature_names() via the _gamestate_to_row() adapter
- default_evaluator() selects Sklearn > Linear > Heuristic with INFO logging at each selection point
- 11 new tests covering wiring (7) and integration (4), all passing alongside 8 existing tests

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement SklearnEvaluator.score() and update default_evaluator()** - `683d858` (feat)
2. **Task 2: Integration tests for SklearnEvaluator wiring** - `bc2d413` (test)

## Files Created/Modified
- `coach/scoring/evaluator.py` - Added _gamestate_to_row(), _placement_to_score(), _round_num_from_stage(); rewrote SklearnEvaluator.score() with lazy TFTFeatureEngineer init; updated default_evaluator() with Sklearn priority and INFO logging; fixed frozen dataclass mutation in _load()
- `tests/test_coach_evaluator.py` - Added TestSklearnEvaluatorWiring (7 tests) and TestSklearnEvaluatorIntegration (4 tests) covering SKLR-01 and SKLR-02

## Decisions Made
- Used model.predict() exclusively (not predict_proba) with linear placement-to-score mapping `(8 - placement) / 7` -- simpler and works for both XGBRegressor and XGBClassifier
- Replicated _round_num_from_stage() inline to avoid circular import from coach.coach
- Fixed frozen dataclass mutation bug in _load(): existing code used `self._model = ...` which would raise FrozenInstanceError; switched to `object.__setattr__(self, '_model', model)` pattern

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed frozen dataclass mutation in _load()**
- **Found during:** Task 1
- **Issue:** Existing `_load()` used `self._model = joblib.load(...)` which violates frozen=True semantics and would raise FrozenInstanceError
- **Fix:** Changed to `object.__setattr__(self, '_model', model)` pattern
- **Files modified:** coach/scoring/evaluator.py
- **Verification:** Integration test test_mock_model_full_path passes the full load/score path
- **Committed in:** 683d858

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Essential for correctness -- frozen dataclass mutation was broken in existing code. No scope creep.

## Issues Encountered
- 2 pre-existing test failures in tests/test_api_server.py (test_startup_failure_exits, test_startup_failure_placement_model_exits) -- confirmed pre-existing by testing without our changes. Not related to this plan.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- SklearnEvaluator is fully wired and tested; ready for model deployment via `evaluator_sklearn.joblib` artifact
- default_evaluator() chain is complete with observable selection
- No blockers for subsequent phases

---
*Phase: 07-sklearnevaluator-wiring*
*Completed: 2026-02-27*
