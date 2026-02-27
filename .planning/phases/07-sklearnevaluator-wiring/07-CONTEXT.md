# Phase 7: SklearnEvaluator Wiring - Context

**Gathered:** 2026-02-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire `SklearnEvaluator.score()` to extract features from `GameState` matching the XGBoost training schema, replace the current `NotImplementedError`, and verify the full call path with an integration test using a mock sklearn model. No new evaluator types, no training pipeline changes, no new model formats.

</domain>

<decisions>
## Implementation Decisions

### Evaluator selection chain
- SklearnEvaluator becomes **highest priority** in `default_evaluator()` fallback chain: Sklearn → Linear → Heuristic
- Model artifact discovered via **convention path** in the runtime outputs directory (same pattern as `evaluator_linear.json`)
- When both sklearn and linear artifacts exist, **sklearn wins**
- `default_evaluator()` **always logs at INFO** which evaluator was selected and why (aligns with Phase 2 observable-fallbacks work)

### Score interpretation
- The XGBoost model predicts **placement (1st-8th)** — this is the training target
- Claude determines the mapping from placement prediction to the 0-1 `BoardEvaluator.score()` return value
- Claude determines whether calibration against HeuristicEvaluator's range is needed

### Failure behavior
- **Model load failure** (missing file, corrupt artifact): **raise RuntimeError immediately** — caller (`default_evaluator`) catches and falls to next evaluator in chain
- **Feature extraction failure** (model expects features SklearnEvaluator can't compute from GameState): **raise ValueError with details** listing which features are missing — forces fix before deployment
- **predict_proba() runtime error**: Claude's discretion on whether to propagate or handle

### Claude's Discretion
- Feature schema source: where SklearnEvaluator gets the column list (import from models/, read from model metadata, or own mapping)
- Whether to reuse `coach/scoring/features.py` helpers (board_power, derive_traits, etc.) vs standalone extraction
- Schema match strictness (exact column-name match vs positional)
- Feature drift handling (fail loudly vs zero-fill for unknown columns)
- Score mapping implementation (predict_proba interpretation, normalization)
- Score calibration approach
- predict_proba error handling strategy

</decisions>

<specifics>
## Specific Ideas

- The current `SklearnEvaluator` already has joblib-based model loading in `_load()` — build on that, don't rewrite
- `LinearEvaluator._features()` at `evaluator.py:103-114` shows the existing pattern for GameState → feature dict extraction — a useful reference
- Training target is placement (1st-8th), not binary win/loss — score mapping must account for this
- The reliability milestone philosophy applies: errors should be visible, not swallowed

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 07-sklearnevaluator-wiring*
*Context gathered: 2026-02-27*
