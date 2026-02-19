# Auto-Battler Coach Lab

A research sandbox for deterministic simulation, evaluation, and explainable coaching for a hex-grid auto-battler ruleset.

## Repo policy
- No personal match history or account-linked identifiers in tracked files.
- No proprietary asset packs (icons/art dumps) in tracked files.
- Local runtime and personal data must stay under `data/local/**` (gitignored).

## Structure
- `app/`: runtime API, websocket server, and frontend.
- `coach/`: planner/scoring modules.
- `simulator/`: deterministic game and combat simulation.
- `models/` and `src/`: training track and runtime recommender track.
- `outputs/coach/`: only tracked runtime artifact subset.

## Quick start
```bash
npm start
```

## Verification
```bash
python -m pytest
```
