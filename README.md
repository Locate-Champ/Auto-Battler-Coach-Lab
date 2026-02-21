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
- `.env.example` is a template; keep real machine values in `.env.local`.
- `simulator/config.py` reads `simulator/.env` for simulator-only env vars.
- `scripts/launch-graviton.sh` requires `DEPLOY_KEY_B64` to be set in your shell for non-dry-run launches.
- Launch/instance policy is enforced in scripts:
  - Security group must include `tft-sim-sg`
  - Key pair must be `tft-sim-key`
  - CPU launches must use `c8g.48xlarge`
  - CPU Name tags are auto-versioned as `sim-cpu-v<number>`
  - GPU launches/bootstraps require exactly 8 GPUs and auto-versioned Name tags `train-gpu-v<number>`
- Cloud scripts use placeholder defaults for environment-specific values (`<YOUR_BUCKET>`, `<INSTANCE_ROLE_NAME>`, `<YOUR_ORG>/<YOUR_REPO>`); replace them locally before execution.
- Recommended local env vars for cloud runs:
  - `DEPLOY_KEY_B64` (base64-encoded deploy key)
  - `AWS_REGION` (for example `us-east-1`)
  - `S3_BUCKET`
  - `S3_PREFIX` (for example `results/gates`)

## Runtime bundle workflow (barebones GitHub setup)
- Build a minimal CPU simulation bundle (only required sim/runtime files):
```bash
bash scripts/create-runtime-bundle.sh --profile cpu-sim --from-env-local --s3-uri s3://<YOUR_BUCKET>/runtime-bundles/
```
- Build a minimal GPU training bundle (only required training/runtime files):
```bash
bash scripts/create-runtime-bundle.sh --profile gpu-train --from-env-local --s3-uri s3://<YOUR_BUCKET>/runtime-bundles/
```
- Build a generic overlay bundle from local/private files:
```bash
bash scripts/create-runtime-bundle.sh --mode overlay --from-env-local --s3-uri s3://<YOUR_BUCKET>/runtime-bundles/
```
- Build a full repo snapshot bundle (excluding caches/build artifacts):
```bash
bash scripts/create-runtime-bundle.sh --mode full --from-env-local --s3-uri s3://<YOUR_BUCKET>/runtime-bundles/
```
- Apply a bundle on an instance:
```bash
bash scripts/apply-runtime-bundle.sh --s3-uri s3://<YOUR_BUCKET>/runtime-bundles/<bundle>.tar.gz --target-dir /home/ubuntu/auto-battler-coach-lab
```
- Prune an existing instance repo to bundle contents while preserving `.venv`:
```bash
bash scripts/apply-runtime-bundle.sh --s3-uri s3://<YOUR_BUCKET>/runtime-bundles/<bundle>.tar.gz --target-dir /home/ubuntu/auto-battler-coach-lab --clean-target --preserve-venv --preserve .git
```
- Bootstrap existing instances with repo + deps + optional bundle:
```bash
bash scripts/bootstrap-cpu.sh --instance-id <cpu-instance-id> --from-env-local --bundle-s3-uri s3://<YOUR_BUCKET>/runtime-bundles/<bundle>.tar.gz --clean-repo-before-bundle
bash scripts/bootstrap-gpu.sh --instance-id <gpu-instance-id> --from-env-local --bundle-s3-uri s3://<YOUR_BUCKET>/runtime-bundles/<bundle>.tar.gz --clean-repo-before-bundle
```
- Launch a fresh CPU sim instance and apply the bundle during cloud-init:
```bash
bash scripts/launch-graviton.sh --from-env-local --bundle-s3-uri s3://<YOUR_BUCKET>/runtime-bundles/<bundle>.tar.gz --role-tag cpu-sim
```
- Launch a fresh GPU training instance with on-demand -> spot fallback across 8-GPU candidates:
```bash
bash scripts/launch-gpu.sh --from-env-local --bundle-s3-uri s3://<YOUR_BUCKET>/runtime-bundles/latest-gpu-train.tar.gz
```

Bootstrap scripts enforce `RepoRef` tag checks by default. Tag new instances with `RepoRef=<git ref>` (or pass `--skip-tag-check` to bypass intentionally).
`create-runtime-bundle.sh --profile cpu-sim --print-files` and `--profile gpu-train --print-files` show exact included paths.

## Verification
```bash
python -m pytest
```
