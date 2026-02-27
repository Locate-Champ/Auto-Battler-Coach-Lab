# External Integrations

**Analysis Date:** 2026-02-27

## APIs & External Services

**Meta & Game Data:**
- MetaTFT API (`api-hc.metatft.com`, `data.metatft.com`)
  - What it's used for: Unit stats, item stats, traits, augments, tier lists, win rates, pick rates
  - Endpoints: `/tft-stat-api/units`, `/tft-stat-api/items`, `/tft-stat-api/traits`, `/tft-stat-api/augments_tiers`, `/tft-early-comps/comps_overview`
  - SDK/Client: `requests` (HTTP)
  - Scripts: `scripts/fetch_game_data.py`, `scripts/extract_metatft_augments.py`, `scripts/fetch_early_comps.py`, `simulator/fetch_metatft_items.py`, `simulator/fetch_metatft_positions.py`

**Web Scraping:**
- tactics.tools
  - What it's used for: Meta composition data extraction
  - SDK/Client: `node-fetch` (JavaScript scraper in `scraper/`)
  - Script: `scraper/index.js` (leaderboard, matches, details endpoints)

**Game Log Aggregation:**
- DigitalOcean Spaces (TFT Matches CDN)
  - What it's used for: Hosted match replay data
  - URL: `https://metatft-matches-2.ams3.digitaloceanspaces.com/{uuid}.json`
  - Usage: Referenced in `scripts/watch_logs.py`

**Champion/Unit Data:**
- Riot Games wikis and external sources
  - What it's used for: Champions, synergies, abilities (historical reference)
  - Scripts: `scripts/fetch_champion_stats.py`, `scripts/fetch_wiki_champions.py`
  - SDK/Client: `urllib.request` (standard library HTTP)

## Data Storage

**Local Storage:**
- **Parquet files** (primary)
  - Location: `outputs/coach/`, `outputs/simulator/` directories
  - Client: `pyarrow.parquet`
  - Format: Arrow columnar for ML training data, game logs, feature matrices
  - Usage: Default output from `simulator.cloud_runner`, `models.data_loader`

- **SQLite (local, reserved)**
  - Location: `data/history.db` (configured but not actively used)
  - Client: `aiosqlite` (import available, not used in current code)
  - Purpose: Future game history tracking

- **JSON/JSONL (fallback)**
  - Location: `data/local/`, `outputs/coach/traces/`, `outputs/coach/eval_reports/`
  - Usage: Game snapshots, network traces, coach evaluation reports
  - Fallback when PyArrow unavailable

- **YAML (config)**
  - Location: `data/personal_notes.yaml`, `data/rules.yaml`
  - Client: `pyyaml`
  - Purpose: Personal coaching notes, game rules config

**File Storage:**
- Local filesystem only (no cloud file storage service)
- Artifact outputs: `data/local/`, `outputs/`, `data/coach/`
- Image assets: `app/frontend/src/assets/` (trait icons, trait palettes)

**S3 Integration (Cloud Upload):**
- AWS S3
  - Connection env vars: `AWS_REGION`, `S3_BUCKET`, `S3_PREFIX`
  - Usage: Upload simulation results from CPU instances, training checkpoints from GPU
  - Client: AWS CLI (`aws s3 cp`, `aws s3 sync`)
  - Scripts: `simulator/cloud_runner.py` (_s3_upload method), manual sync in gate runbooks
  - Example S3 paths: `s3://{bucket}/results/gates/gate_b/{run_id}/`, `s3://{bucket}/runtime-bundles/`
  - Note: No boto3 SDK directly used; AWS CLI subprocess calls

**Caching:**
- None configured
- XGBoost uses external memory mode (`--external-memory`) for large datasets instead

## Authentication & Identity

**Auth Provider:**
- Custom/Local authentication only
- No OAuth2, OIDC, or third-party identity providers
- MetaTFT log watching: Local file system (Overwolf log directory)
- AWS access: IAM role (on EC2 instances) or credentials from environment
- No user authentication system (single-player coaching app)

## Monitoring & Observability

**Error Tracking:**
- None (Sentry, Rollbar not integrated)
- Error handling: Try/except with stderr logging

**Logs:**
- **Console logging:** Python `logging` module with print statements
- **File-based logs:** MetaTFT game logs in Overwolf directory (`%LOCALAPPDATA%\Overwolf\Log\Apps\MetaTFT\`)
- **TensorBoard:** Training metrics via `tensorboard` for model checkpoint visualization
- **CloudWatch:** Not integrated (AWS EC2 logs written to `/tmp/`, then uploaded to S3)

**Traces & Debugging:**
- Game traces: JSONL files in `outputs/coach/traces/` (network snapshots)
- Coach evaluation reports: JSON in `outputs/coach/eval_reports/`
- Execution traces: Printed to stdout during `simulator.cloud_runner`, `coach.offline.eval_coach`

## CI/CD & Deployment

**Hosting:**
- AWS EC2
  - CPU simulation: `c8g.48xlarge` (ARM64 Graviton, 192 vCPUs, Ubuntu 22.04 arm64)
  - GPU training: `g5.2xlarge` or `g6.2xlarge` (x86_64, 1 GPU, Deep Learning OSS Nvidia Driver AMI)

**CI Pipeline:**
- GitHub Actions (`.github/workflows/`)
  - `test-coverage.yml` - Full test suite (Python, frontend build, Rust parity, coach eval)
  - `lint.yml` - Code quality (ruff lint/format)
  - `secret-scan.yml` - Secret detection (detect-secrets)
  - `deploy.yml` - Deployment automation
  - Triggers: Push to main, pull requests

**Deployment Scripts:**
- `scripts/launch-graviton.sh` - Launch CPU simulation EC2 instance
- `scripts/launch-gpu.sh` - Launch GPU training EC2 instance (on-demand → spot fallback)
- `scripts/bootstrap-cpu.sh` - Bootstrap CPU instance with code and runtime bundle
- `scripts/bootstrap-gpu.sh` - Bootstrap GPU instance with code and runtime bundle
- `scripts/create-runtime-bundle.sh` - Build deployment bundle (tar.gz with code, deps)
- `scripts/run-gates.sh` - Orchestrate full gate pipeline via AWS SSM
- AWS Systems Manager (SSM) - Remote command execution on instances (no SSH key needed)

## Environment Configuration

**Required env vars:**
- `AWS_REGION` - AWS region for EC2, S3 (default: us-east-1)
- `S3_BUCKET` - S3 bucket for result uploads (required for cloud runs)
- `S3_PREFIX` - S3 path prefix (default: results/gates)
- `COACH_OUTPUTS_DIR` - Local coach outputs directory (optional override)
- `COACH_CHECKPOINT_DIR` - Local checkpoint directory (optional override)
- `COACH_ARTIFACT_ROOT` - Local artifact root (optional override)
- `REPO_URL` - Git repo URL for cloud bootstrap (required for cloud)
- `REPO_REF` - Git branch/tag to check out (default: main)
- `REPO_DIR` - Working directory on instance
- `WORKDIR` - Data directory on instance (default: /data/sim)
- `INSTANCE_OWNER_TAG` - EC2 tag for owner tracking (optional)
- `INSTANCE_ENV_TAG` - EC2 tag for environment (default: dev)
- `DATA_VERSION_TAG` - Version tag for data (optional)
- `RUNTIME_BUNDLE_S3_URI` - Pre-built bundle S3 URI (optional, for fast bootstrap)

**Secrets location:**
- `.env` file (not committed, uses `.env.example` template)
- `.env.local` (machine-specific, not committed)
- AWS IAM roles (no credentials needed on EC2 with proper instance profile)
- GitHub Secrets (for CI/CD workflows, if needed)

**Build config files:**
- `ruff.toml` - Linting and formatting
- `pytest.ini` - Test discovery and exclusions
- `.pre-commit-config.yaml` - Git hooks
- `.github/workflows/*.yml` - CI pipeline definitions

## Webhooks & Callbacks

**Incoming Webhooks:**
- None configured
- MetaTFT log watching via file system polling (Watchdog library)
- No HTTP webhook endpoints for external triggers

**Outgoing Webhooks:**
- None configured
- S3 uploads are one-way data transfer, not triggered by external webhooks
- Coach evaluation results written to local JSONL files

## Data Flow Summary

**Simulation → Training:**
```
MetaTFT Game Events
  → LogWatcher (file polling)
  → GameCollector (aggregates game snapshots)
  → Parquet chunks (local `outputs/`)
  → S3 upload (if cloud_runner configured)
  → DataLoader (reads chunks)
  → TFTFeatureEngineer.vectorize()
  → train/test split by game_id
  → XGBoost training
  → Checkpoint artifacts → S3 upload
```

**Coach Runtime:**
```
MetaTFT Logs (local)
  → LogWatcher + Parser (game state extraction)
  → StateManager (game state machine)
  → Coach planner (budget allocation)
  → Simulator (multi-seed rollout)
  → TFTRecommender + PlacementModel (inference)
  → WebSocket server
  → React frontend (browser overlay)
```

**API Server:**
```
React frontend
  → FastAPI endpoints (`app/api/server.py`)
  → TFTRecommender (loaded at startup)
  → PlacementModel (trained on startup)
  → Response (Pydantic models)
```

---

*Integration audit: 2026-02-27*
