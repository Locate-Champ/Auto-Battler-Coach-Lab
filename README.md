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

## Cloud script configuration
- `scripts/launch-graviton.sh` requires `DEPLOY_KEY_B64` to be set in your shell for non-dry-run launches.
- Cloud scripts use placeholder defaults for environment-specific values (`<YOUR_BUCKET>`, `<INSTANCE_ROLE_NAME>`, `<YOUR_ORG>/<YOUR_REPO>`); replace them locally before execution.
- Recommended local env vars for cloud runs:
  - `DEPLOY_KEY_B64` (base64-encoded deploy key)
  - `AWS_REGION` (for example `us-east-1`)
  - `S3_BUCKET`
  - `S3_PREFIX` (for example `results/gates`)

## Verification
```bash
python -m pytest
```
