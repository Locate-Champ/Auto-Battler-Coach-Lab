# Auto-Battler Coach Lab Repo Handoff

Last updated: 2026-02-22 (America/New_York)

## Purpose
Use this handoff set to bootstrap a new ChatGPT session with current project truth.

## Read order
1. `AGENTS.md` (canonical rules)
2. `docs/CHATGPT_PROJECT_STATE.md` (current architecture + track map)
3. `docs/CHATGPT_EXECUTION_RULES.md` (execution and verification contract)
4. `README.md` (quick commands + environment context)

## 60-second snapshot
- Project is a TFT coaching lab with two main workflows:
  - Live runtime coaching (`app/**`, `coach/**`, `app/frontend/**`)
  - Offline simulator/training (`simulator/**`, `models/**`)
- Runtime API (`app/api/server.py`) currently loads recommender classes from `src/models/**`.
- Active simulator truth is in `simulator/core/**` and `simulator/game/**`.
- Legacy simulator paths are quarantined:
  - `simulator/Simulator/**`
  - `simulator/Concurrency/**`
  - `simulator/Evaluator/**`

## Fast start commands
```bash
npm start
python -m pytest
python -m simulator.benchmark
```

## Local data policy
- Keep personal/raw runtime data under `data/local/**` only.
- Do not commit asset packs or account-linked data.
- Runtime should fail with actionable errors when required local files are missing.
