# AGENTS.md — Auto-Battler Coach Lab (canonical)

Default behavior: smallest scoped change, deterministic simulator, no surprises.

## 1) Track map (non-negotiable)
- Active simulator truth: `simulator/core/**` and `simulator/game/**`
- ML training + eval: `models/**`
- Runtime recommender API: `app/api/server.py` uses `src/models/**`
- Legacy/quarantined: `simulator/Simulator/**`, `simulator/Concurrency/**`, `simulator/Evaluator/**` (do not work here)

## 2) Hard rules (non-negotiable)

- Do not touch legacy simulator paths.
- Do not commit unless explicitly requested.
- Never paste secrets/tokens. If a token was leaked, recommend rotation immediately.
- For AWS work: read the repo’s AWS gate/runbook doc first and follow it exactly.
  - Simulation is CPU-bound.
  - Training is GPU-bound.
  If a request conflicts with that, raise the conflict before doing anything.

## 3) Parquet / Arrow rule (performance + consistency)
- Parquet is the default artifact format.
- Validate `pyarrow` in the SAME Python environment running the command:
  - `python -c "import pyarrow; print(pyarrow.__version__)"`
- If pyarrow is missing, install it in that environment before running large jobs.

## 4) Verification rules (run only what applies)
- Combat engine behavior changed:
  - `python -m simulator.benchmark` (determinism must pass)
- Output schema/format changed:
  - `python -m simulator.validate_output <dir>` (19/19 checks pass)
- Coach/runtime scoring changed:
  - run the focused pytest targets for coach planner/scoring
- General:
  - `python -m pytest`
- Frontend changed:
  - `cd app/frontend && npm run build`

## 5) Definition of done
Done means:
- Requested change implemented
- Required verification run and results reported
- What changed + why explained
- Follow-ups listed (suggestions only, do not implement unless asked)

## 6) ## Improvements (anti-bloat rule)

- Do NOT propose improvements by default.
- Only include an "Improvements" section if you found something that:
  (a) prevents a real bug, (b) reduces complexity, or (c) reduces runtime/cost.
- Cap: max 2 bullets.
- Each bullet must include: Benefit (1 sentence) + Effort (S/M/L) + Risk (Low/Med/High).
- Never suggest “nice to have” refactors, new abstractions, new features, or new dependencies unless the user explicitly asked for them.
- Never implement an improvement unless the user explicitly approves it.