# Coach Upgrade Index (Planner + Critic)

Last updated: 2026-02-14

This is the entry-point for the coach upgrade plan described in `TFT_COACH_TIMELINE_AND_TODO.md`.

## Truth Table (What Runs Where)

| Path | What it serves | Status |
|------|----------------|--------|
| Live WebSocket coach | `app/server/websocket.py` -> `coach/` | Active. Computes recommendations and broadcasts them under the `coach` field in the live WS payload. |
| Coach combat scoring | `coach/scoring/combat.py` -> `simulator/core/combat_engine.py` | Active. Uses the Python combat engine for relative ranking (seeded sims). |
| REST API server | `app/api/server.py` -> `src/models/` | Legacy. Kept for older endpoints until explicitly migrated. |

## Known Fidelity Gaps -> Coach Behavior

- Prefer **ranking options** (A > B) over quoting absolute winrates.
- When surfacing sim-derived numbers in UI, label them as **"in sims"** (or **"in our engine"**) and avoid absolute claims when confidence is low.
- If opponent board is unknown, the coach must explicitly say it scored against a generic/fallback opponent set (or used a proxy evaluator instead of sims).

## Specs (Contracts)

- Live -> Coach state conversion: `docs/specs/LIVE_TO_COACH_STATE_CONTRACT.md`
- Simulator training row schema: `docs/specs/SNAPSHOT_ROW_SCHEMA.md`
- Coach explanation payload: `docs/specs/COACH_EXPLANATION_SCHEMA.md`
- Model/runtime artifact loading: `docs/specs/MODEL_ARTIFACT_SCHEMA.md`

## Baseline Health Checks

Run these from repo root:

```powershell
python -m simulator.benchmark
python -m simulator.validate_output <some_results_dir>
pytest
```

## Offline Regression Gate (Coach Eval)

The fixed eval-set + baseline report artifacts are checked into the repo under `outputs/coach/` (along with `archetypes.json` and `evaluator_linear.json`) so the eval gate is portable across machines/CI:

```powershell
python -m coach.offline.eval_coach `
  --eval-set outputs/coach/eval_sets/fixed_eval_set_opt_phase1_25.jsonl `
  --limit 25 `
  --output outputs/coach/eval_reports/fixed_current_opt_phase1_25.json `
  --baseline-report outputs/coach/eval_reports/fixed_baseline_opt_phase1_25.json
```

`scripts/verify.ps1 -Mode changed` will run this gate automatically when coach-related code changes (or force it with `-CoachEvalGate`).
`fixed_current_opt_phase1_25.json` is a generated output (not a baseline input).

## Trace Viewer

When live WS traces exist under `outputs/coach/traces/`, you can inspect them with:

```powershell
python -m coach.offline.view_traces --input outputs/coach/traces/coach_traces_YYYYMMDD.jsonl --limit 5 --top 5
```

New traces include a small `state_summary` (stage/level/gold + unit-id map) so the viewer can print champion names for item targets.
