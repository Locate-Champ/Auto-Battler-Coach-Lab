# Coach Explanation Payload Schema

Last updated: 2026-02-13

This document defines the schema the coach emits to the live WebSocket payload for UI rendering.

Source:
- `app/server/websocket.py` (adds `payload["coach"] = ...`)
- `coach/` (candidate -> execute -> score -> explain)

## Top-Level Payload

The live WS payload includes a top-level `coach` object:

```json
{
  "coach": {
    "coach_payload_version": 1,
    "generated_at": "2026-02-13T21:00:00Z",
    "coach_state_schema_version": 1,
    "coach_state_validation_errors": null,
    "config": {
      "sim_budget_pass1": 32,
      "sim_budget_pass2": 0,
      "sim_budget_pass3": 0,
      "max_candidates_items": 60,
      "max_candidates_position": 60,
      "max_candidates_econ": 40,
      "max_candidates_shop": 40,
      "top_k": 3
    },
    "recommendations": { "items": [], "position": [], "econ": [], "shop": [] },
    "errors": { "items": "optional error string" }
  }
}
```

## Recommendation Schema

Each decision type returns a list of `Recommendation` objects.

```json
{
  "action": { "...": "ActionPlan" },
  "score": { "...": "ScoreBreakdown" },
  "explanation": { "...": "Explanation" }
}
```

### ActionPlan

```json
{
  "decision_type": "items|position|econ|shop",
  "action_id": "stable-string-id",
  "title": "short UI label",
  "details": { "module_specific": "payload" },
  "constraints": ["requires_shop_visible"],
  "tags": ["tempo", "greed", "stabilize"]
}
```

### ScoreBreakdown

Required:
- `total_score`: `float`
- `tempo`: object
- `evaluator`: object
- `econ`: object
- `archetype`: object
- `penalties`: list

#### tempo

Required numeric fields:
- `win_prob`: `float` in `[0,1]` (computed "in sims" when opponent is known)
- `win_prob_delta`: `float` (relative to baseline/no-op)
- `expected_hp_delta`: `float` (expected HP change next fight; negative means expected damage)
- `n_sims`: `int`

Optional:
- `ci95`: `[low, high]` win-prob CI (or null)
- `opponent_policy`: `"next_opponent"|"scouted_set"|"proxy_only"`

#### evaluator

Required:
- `board_score`: `float` in `[0,1]`

Optional:
- `matchup_score`: `float|null`
- `uncertainty`: `float|null`

#### econ

Required numeric fields:
- `gold_delta`: `int`
- `interest_delta`: `int`
- `level_delta`: `int`
- `roll_delta`: `int`
- `hp_risk`: `float` in `[0,1]` (heuristic risk proxy; higher = riskier)

Optional:
- `upgrade_hit_prob`: `float|null` (econ roll lookahead)
- `upgrade_top_targets`: `list[[champion_id, prob]]` (top-N immediate upgrade hits)

#### archetype

Required:
- `top_archetypes`: list of `{ "name": str, "similarity": float }` (top-N nearest)
- `alignment_delta`: `float` (relative to baseline/no-op)

#### penalties

Each penalty:
```json
{ "reason": "string", "amount": 0.25 }
```

### Explanation

```json
{
  "confidence": "high|medium|coin_flip|low",
  "lines": ["UI-ready text lines..."],
  "numbers": {
    "win_prob_delta": 0.07,
    "expected_hp_delta": -3.6,
    "gold_delta": -4
  }
}
```

Phrasing rules:
- If values are sim-derived, label lines with `"in sims"` and avoid absolute wording for `coin_flip|low`.
- If opponent board is unknown and tempo uses a proxy evaluator, the explanation must say so.
