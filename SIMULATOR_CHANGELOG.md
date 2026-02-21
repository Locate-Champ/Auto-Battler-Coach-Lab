# Simulator Changelog (Extracted from AI Session Logs)

> Auto-generated from Codex and Claude Code conversation logs. One day per section, most recent first.

---

## February 20, 2026

**Sources:** 3 Claude Code sessions, 3 Codex sessions (Codex sessions were tennis-market-analysis -- no simulator content)

### What Was Done

#### 50k Sim Run -- Completed Successfully
- **Instance:** c8g.48xlarge (192 vCPUs, Graviton), tagged `sim-cpu-v2`
- **Command used:**
  ```bash
  python -m simulator.cloud_runner --games 50000 --workers 96 --engine rust_full \
    --output results/run50k-20260220-064051 \
    --s3-uri s3://tft-sim-results-forrest/tft-results/gates/run50k-20260220-064051 \
    --parquet-compression snappy --parquet-use-dictionary --parquet-write-statistics
  ```
- **Auto-applied Rust speed profile:** `chunk_size=1000`, `native_parquet=True`, `native_parquet_direct=True`, `rayon_batch_size=64`, `rayon_threads=96`
- **Results:** 50,000 games, 0 errors, 19/19 validation checks passed
- **Run time:** ~8 minutes on c8g.48xlarge
- **Output:** 52 objects, ~1.1 GB on S3
- **Top 5 champs (avg placement):** Brock (1.0), Volibear (1.17), Sylas (1.23), Baron Nashor (1.24), Thresh (1.27)
- **Bottom 5 champs (avg placement):** Aphelios (5.3), Sona (5.16), Caitlyn (5.04), Kog'Maw (5.02), Lulu (5.01)

#### XGBoost Training -- Did NOT Complete
- 5 failed/incomplete attempts on g5.2xlarge GPU instance
- **Root cause:** XGBoost external memory mode re-reads all data pages from disk every boosting round. Feature engineering alone takes ~56 min. With 300 estimators + `lossguide` + `max_leaves=256`, each tree is expensive.
- SSM 60-minute timeout killed attempt 4. Attempt 5 ran 3.5+ hours on CPU-only before instance was stopped.
- **No model artifacts produced.**

#### Bugs Found and Fixed
1. **`load_from_env_file` exit code bug** -- last `[[ ]] && assignment` returns exit 1 under `set -e`. Fixed with `|| true`.
2. **Unescaped heredoc variables** -- `BUNDLE_TMP` and `$(date +%s)` expanded locally instead of on remote. Fixed with proper escaping.
3. **MSYS/Git Bash path conversion** -- unquoted `${LAUNCH_ARGS[@]}` caused `/home/ubuntu` to convert to `C:/Program Files/Git/...`. Fixed by quoting.
4. **SSM RunShellScript defaults to `/bin/sh`** -- `set -o pipefail` fails under dash. Fixed by adding `#!/bin/bash` as first command.
5. **Missing `helper_units.json` entries** -- local changes not committed to git; EC2 cloned `main` which had old version. Fixed via S3 code bundle upload.
6. **GPU DLAMI requirement** -- launch script used vanilla Ubuntu AMI with no NVIDIA drivers. Fixed by switching to Deep Learning AMI (`ami-0ad2671533287584d`).
7. **GPU policy scripts** -- relaxed required GPU count from 8 to 1, changed default instance types to g5.2xlarge/g6.2xlarge.
8. **IAM role placeholder** -- scripts had `<INSTANCE_ROLE_NAME>`. Fixed by reading from `.env.local`.
9. **Python detection** -- `python3` on Windows Git Bash resolves to Windows Store stub. Fixed in both bootstrap scripts.
10. **DLAMI venv issues** -- PyTorch lives at `/opt/pytorch/bin/python3` (3.12.10), not system `python3` (3.10). `LD_LIBRARY_PATH` unbound under `set -u`. `nvidia-smi | head -3` caused SIGPIPE (exit 141) under `set -eo pipefail`.

#### Research Session: Optimal Worker Mix for Rust Engine
- **Answer (from commit `ab75fa6`, Feb 16):** Use `--workers 1` + `--rust-full-rayon-threads <PHYSICAL_CORES>`
- **Rationale:** Rayon manages its own thread pool. Multiple Python workers + Rayon = oversubscription (both fight for same cores).
- Rayon confirmed in `Cargo.toml` (`rayon = "1.10"`) and `src/lib.rs` (`rayon::prelude::*`, `ThreadPoolBuilder`)

### Performance Metrics

| Run | Engine | Workers | Rayon Threads | Batch | Games | Time | Games/sec |
|-----|--------|---------|---------------|-------|-------|------|-----------|
| Local smoke (rust_full) | rust_full | 1 | 8 | 64 | 200 | 12.9s | **15.54** |
| Local streaming smoke | rust_full | 1 | N/A | N/A | 120 | 8.7s | **13.85** |
| AWS c8g.48xlarge 50k | rust_full | 96 | 96 | 64 | 50,000 | ~8min | **~104** |
| Historical: Python 11w | python | 11 | N/A | N/A | -- | -- | **4.13** |
| Historical: Python 8w | python | 8 | N/A | N/A | -- | -- | **2.61-2.74** |
| Projected: Rust 192 rayon (c8g.48xl) | rust_full | 1 | 192 | -- | -- | -- | **~130/sec** |

### Key Commits Referenced
- `284eef5` perf(simulator): Cython accel, adaptive tick, multiprocessing, Rust LUT
- `7a21e8d` perf(simulator): optimize combat engine hot paths (~2-3x throughput)
- `5dd5bf4` feat(simulator): harden rust determinism and native parquet writing
- `7075d67` feat(simulator): add parquet sizing CLI and rust api guards
- `0f3f95d` feat(simulator): fix pool caching bug in benchmark + S3 streaming uploads
- `5dcb414` fix(simulator): restore Python/Rust parity for CI gate
- `ab75fa6` docs: document optimal worker/rayon thread configuration

### How to Run

#### Local Quick Run
```bash
python -m simulator.cloud_runner --games 1000 --workers 11 --output results/batch
python -m simulator.validate_output results/batch
```

#### Rust Engine (Recommended for Production)
```bash
export OMP_NUM_THREADS=1; export OPENBLAS_NUM_THREADS=1; export MKL_NUM_THREADS=1; export NUMEXPR_NUM_THREADS=1

python -m simulator.cloud_runner --engine rust_full --games 10000 --workers 1 \
  --output /data/rust_full_10k --agent-profile mixed --require-parquet \
  --rust-full-native-parquet --rust-full-native-parquet-direct \
  --rust-full-rayon-batch-size 64 --rust-full-rayon-threads <PHYSICAL_CORES> \
  --parquet-compression snappy --parquet-use-dictionary --parquet-write-statistics \
  --checkpoint-every 500 --progress-every 500 --max-errors 100
```

#### AWS Cloud (c8g.48xlarge)
```bash
python -m simulator.cloud_runner --games 50000 --workers 96 --engine rust_full \
  --output results/<RUN_ID> \
  --s3-uri s3://tft-sim-results-forrest/tft-results/gates/<RUN_ID> \
  --parquet-compression snappy --parquet-use-dictionary --parquet-write-statistics
```

#### Automated Pipeline (PowerShell)
```powershell
powershell -ExecutionPolicy Bypass -File .\.agent\runbooks\run-50k-sim-plus-modeling.ps1 -StopOnComplete
```

#### Rayon Thread Sweep (Find Optimal Config)
```bash
export OMP_NUM_THREADS=1; export OPENBLAS_NUM_THREADS=1; export MKL_NUM_THREADS=1; export NUMEXPR_NUM_THREADS=1

for threads in <CORES-8> <CORES-4> <CORES>; do
  for batch in 32 64 128; do
    python -m simulator.cloud_runner --engine rust_full --games 10000 --workers 1 \
      --rust-full-rayon-batch-size ${batch} --rust-full-rayon-threads ${threads} \
      --rust-full-native-parquet --rust-full-native-parquet-direct \
      --parquet-compression snappy --parquet-use-dictionary --parquet-write-statistics \
      --output /data/rust_sweep_t${threads}_b${batch} --agent-profile mixed \
      --require-parquet --checkpoint-every 500 --progress-every 500 --max-errors 100
  done
done
```

#### Benchmark / Determinism
```bash
python -m simulator.benchmark
```

#### Validation (19 checks)
```bash
python -m simulator.validate_output <output_dir>
```

### Recommended Next Steps (as of this date)
- Run thread/batch sweep on c8g.48xlarge to find optimal `rayon_threads`/`rayon_batch_size`
- Use `--arrow` flag + in-memory mode for XGBoost training (cuts 56-min feature engineering to minutes)
- Commit local data file changes (helper_units.json, combat_data.json) so cloud runs don't need code bundle workaround
- 50k sim data on S3 is ready for training -- no model produced yet

### AWS Cost Notes
- GPU instance (g5.2xlarge, $1.006/hr) ran ~4 hours = ~$4 (no model produced)
- CPU instance (c8g.48xlarge) ran for sim + idle time
- All instances terminated at end of session

---

## February 19, 2026

**Sources:** 12 Codex sessions (5 were Auto-Battler, 7 were tennis-market-analysis or aborted), 0 Claude Code sessions

### What Was Done

#### Public Surface Reduction -- Major Repo Pruning
- Ran `git rm --cached -r simulator` to untrack everything, then selectively re-added only the "active engine surface"
- **Result:** 148 files changed, 13,217 insertions(+), 72,154 deletions(-) -- down from 200+ to **78 tracked simulator files**
- Deleted from tracking: legacy `simulator/Simulator/`, `simulator/Concurrency/`, `simulator/Evaluator/`, `simulator/Models/`, plus PDFs
- Kept: `simulator/core/`, `simulator/game/`, `simulator/data/` (selected files), `benchmark.py`, `cloud_runner.py`, `config.py`, `validate_output.py`
- **Commit:** `e5d7cba` -- "chore(simulator): keep active engine surface and simulator-owned augment baseline"
- Related commits: `4175891` (knowledge-base pruning), `d47e4dd` (scripts pruning), `349a73d` (runtime decoupling), `5a079a8` (CI allowlist enforcement)

#### Augment Path Resolution (New Feature)
- Created `simulator/core/augment_paths.py` -- shared resolver with env var override (`SIMULATOR_AUGMENTS_PATH`)
- Resolution order: (1) env override, (2) `simulator/data/augments_set16.json` (new tracked baseline), (3) `data/api/processed/augments_set16.json` (legacy fallback)
- Wired into `simulator/core/combat_engine.py` (line 1779) and `simulator/game/game.py` (line 38)
- Also updated `models/feature_engineering.py` to use same resolution chain

#### Champion Unlock System (New Feature)
- Created `simulator/game/unlocks.py` -- full unlock requirements manager
- **41 unlockable champions** with CSV-based requirements from `data/unlock requirements.csv`
- Evaluates unlock conditions **only after combat** (PvP and PvE) with guaranteed next-shop injection
- Supports **immediate (non-combat) unlocks** for Bard, Sylas, Tahm Kench
- Implements **Shurima progressive thresholds** (first, second, third per Shuriman unlock)
- Multi-unlock in single combat: all injected into next shop
- Guarantee queue deduplication (new unlocks append, don't overwrite pending)
- Unlock condition types: level requirements, trait counts, star level thresholds, reroll counts, sell counts, HP loss, front-row positioning (Sett), serpent spending (Tahm), sunshard gains (Brock)
- **Sett bug found and fixed:** Was using back rows instead of front rows (`row < 2`)
- Wired into `simulator/game/player.py`, `simulator/game/game.py`, `simulator/game/shop.py`, `simulator/game/champion_pool.py`

#### Ixtal Quest System
- Created `simulator/game/sync_ixtal_quest_rewards.py` -- sync CLI for quest data
- Generated `simulator/game/ixtal_quest_rewards.json` -- **39 Ixtal quest reward ladders**
- Loaded from LittleBuddyBot structured HTML content

#### Bilgewater Shop System
- Added `auto_purchase_bilgewater_shop` to `simulator/game/player.py` (line 236)
- Bilgewater shop contents defined in `simulator/data/set16_items.py` (stat buffs, items, unit buys, lesser dupe, reroll)
- Wired into PvE and PvP round flow in `simulator/game/game.py` (lines 321, 373)
- Tahm unlock changed to require **serpents spent** (not gained)

#### Cloud Runner Cost Telemetry (New Feature)
- Added `_build_cost_telemetry()` to `simulator/cloud_runner.py` (line 232)
- Computes: `games_per_sec`, `rounds_per_sec`, `sec_per_game`, `sec_per_round`, CPU utilization, USD estimates
- New `cost_telemetry` block in `summary.json`
- New CLI flags: `--instance-hourly-usd`, `--instance-type`
- Auto-capping workers to 8 when CPU-derived default exceeds 8

#### TFT Patch 16.4/16.5 Data Sync
- Ran `python scripts/sync_all_data.py` (~100 seconds full sync)
- Fixed non-ASCII output in sync summary (Windows cp1252 issue)
- Fixed helper classification so `TFT16_AnnieTibbers` stays in simulator helper data
- MetaTFT API returns `selected_patch=16.4`, `external_patch=16.5`
- Verified: 183 trait mappings, 100 champions, 283 augments loaded
- Patched `fetch_game_data.py` to prefer `external_patch` when available
- Updated stale `recommender` reference from `metatft_augment_tierlist_16_3.csv`

#### Full AWS Pipeline Designed and Implemented
- **CPU sim then GPU training** with S3 handoff between instances
- Scripts created/updated:
  - `scripts/bootstrap-gpu.sh` -- remote GPU instance setup via SSM
  - `scripts/bootstrap-cpu.sh` -- symmetric CPU bootstrap
  - `scripts/create-runtime-bundle.sh` -- package repo for S3 deployment (`--profile cpu-sim|gpu-train`)
  - `scripts/apply-runtime-bundle.sh` -- apply bundle with `--clean-target --preserve-venv`
  - `scripts/launch-gpu.sh` -- GPU launcher with on-demand/spot fallback, GPU enforcement
  - `scripts/launch-graviton.sh` -- standardized tags, metadata, bundle support
- PowerShell runbooks created under `.agent/runbooks/` (git-ignored):
  - `run-50k-sim-plus-modeling.ps1`, `run-250k-transformer-sim-modeling.ps1`, `run-1m-*`, `run-5m-*`
- S3 runtime bundles uploaded to `s3://tft-sim-results-forrest/runtime-bundles/`
- Launch policy: CPU=`sim-cpu-vN` on `c8g.48xlarge`, GPU=`train-gpu-vN` on `g5.2xlarge`

#### 50k Sim Run -- First Attempt (Late Night)
- **Instance:** c8g.48xlarge, instance ID `i-0be5628f806d5597a`, named `sim-cpu-v1`
- **Run ID:** `run50k-20260220-002415`
- **Validation: PASSED (19/19 checks)**
- Bootstrap failed twice before succeeding on v3 (shell compat + `HOME` unset in SSM)
- XGBoost training attempted but not completed (SSM issues, quota limits, direction changes)

### Performance Metrics

| Metric | Value |
|--------|-------|
| Python 1v1 (1000 sims) | 247-259 sims/sec |
| Python 4v4 (100 sims) | 75-77 sims/sec |
| Python Full Game (5 games, 8 players) | 0.79-0.83 sec/game, **4,329-4,586 games/hour** |
| Full Game avg rounds | 28.2-28.4 |
| Benchmark wall time | 13.6-14.3s |
| Champions loaded | 106 |
| Augments loaded | 283 |

#### Cost Telemetry Test Results

| Run | Games | Time | Rate | Rounds | CPU Est | Cost Est |
|-----|-------|------|------|--------|---------|----------|
| 1 | 2 | 1.9s | 1.08 g/s | 56 | 8.33% (sampled 28.95%) | $0.139/1k games |
| 2 | 1 | 1.0s | 0.99 g/s | 27 | 8.33% (sampled 26.7%) | $0.152/1k games |

Both used `--instance-hourly-usd 0.54` (c7i.2xlarge pricing).

### Tests Created/Passed
- `tests/test_unlock_requirements.py` -- 23+ tests (multi-unlock, Sett front-row, Shurima thresholds, CSV parsing, guarantee timing, Tahm spent-serpent, Brock quest)
- `tests/test_unlock_game_integration.py` -- integration tests for PvE/PvP guarantee behavior
- `tests/test_cloud_runner_cost_telemetry.py` -- 3 tests (telemetry metrics, completed runs, empty runs)
- `tests/test_simulator_augment_paths.py` -- augment path resolution
- `tests/test_public_surface_allowlist.py` -- CI allowlist enforcement
- All existing tests continued passing: 54+ tests across multiple suites
- Benchmark determinism: **passed**

### Simulator Data Inventory (post-pruning)

| File | Size |
|------|------|
| `combat_data.json` | 278 KB |
| `timing_constants.json` | 233 KB |
| `augments_set16.json` | 344 KB |
| `traits.json` | 42 KB |
| `set16_items.py` | 29 KB |
| `helper_units.json` | 3 KB |

### AWS Configuration Established

| Resource | Value |
|----------|-------|
| CPU Instance | c8g.48xlarge (192 vCPUs, Graviton) |
| GPU Instance | g5.2xlarge (8 vCPUs, 1 GPU) |
| Region | us-east-1 |
| S3 Bucket | tft-sim-results-forrest |
| Security Group | tft-sim-sg |
| Key Pair | tft-sim-key |
| Runtime Bundles | `s3://tft-sim-results-forrest/runtime-bundles/latest-cpu-sim.tar.gz` |

### Bugs Found
1. **Sett unlock** -- was checking back rows instead of front rows
2. **`set -o pipefail` under `/bin/sh`** -- SSM defaults to dash, not bash
3. **`HOME` unset in SSM** -- breaks Rust env sourcing (`source $HOME/.cargo/env`)
4. **Non-ASCII sync summary output** -- broke on Windows cp1252
5. **`TFT16_AnnieTibbers` dropped** from helper_units.json after data refresh
6. **AWS vCPU quotas** -- G/VT spot quota of 8 blocks g5.48xlarge; Standard spot quota of 32 blocks c8g.48xlarge spot
7. **SSM command channel** can go unhealthy on GPU instances (requires reboot)

### How to Run (New Commands from This Day)

```bash
# Cost telemetry run
python -m simulator.cloud_runner --games 1000 --workers 11 --output results/batch \
  --instance-hourly-usd 0.54 --instance-type c7i.2xlarge --progress-every 100

# XGBoost training
python -m models.train_xgboost --data results/<RUN_ID> --task fight \
  --output models_checkpoints/xgb --external-memory --external-batch-size 8192

# Transformer training
python -m models.train_transformer --data results/<RUN_ID> \
  --output models_checkpoints/transformer

# Full data sync
python scripts/sync_all_data.py
```

---

## February 18, 2026

**Sources:** 6 Codex sessions (3 were Auto-Battler/tft-coach-234, 3 were scraping/tennis), 0 Claude Code sessions

### What Was Done

#### Major Repo Restructuring (7+ Phase Cleanup)
- Multi-phase pruning of the repo from `tft-coach-234` toward a clean public surface
- Two-pass untracking of generated artifacts (`results/`, `live-logs/`, `tmp/`, `models/checkpoints/`)
- Added `outputs/coach/` as sole tracked runtime artifact path with `outputs/coach/README.md` contract
- Denied noisy/legacy trees from agent visibility in `.claude/settings.json`

#### Simulator Stats Migration
- **Problem:** `test_track_boundaries.py` caught active simulator code importing from quarantined legacy `simulator/Simulator/` package
- **Fix:** Extracted stats tables into active tree:
  - Created `simulator/game/stats/__init__.py`
  - Created `simulator/game/stats/pool_stats.py`
  - Created `simulator/game/stats/origin_class_stats.py`
  - Updated imports in `simulator/game/constants.py` and `simulator/game/ryze_emblem_optimizer.py`
- **Commit:** `1780efc` -- "refactor(simulator): move stats tables out of legacy Simulator package"

#### Artifact Path Resolver Created
- Created `coach/artifacts.py` -- runtime artifact path resolver with env var precedence
- Initial: `TFT_OUTPUTS_DIR` > `TFT_ARTIFACT_ROOT/outputs/coach` > `<repo>/outputs/coach`
- Later migrated to: `COACH_OUTPUTS_DIR` > `COACH_ARTIFACT_ROOT/outputs/coach` (with `TFT_*` fallback)
- Same pattern for checkpoints: `COACH_CHECKPOINT_DIR` > `COACH_ARTIFACT_ROOT/checkpoints`
- Added `tests/test_no_hardcoded_artifact_paths.py` guard test

#### Track Boundary Enforcement
- Created `tests/test_track_boundaries.py` -- prevents active simulator code from importing quarantined legacy packages
- Added to CI pipeline in `.github/workflows/test-coverage.yml`
- **Dual-Track Override Policy:** PRs touching both `src/models/**` and `models/**` need label `allow-dual-track` + `Dual-Track Reason:` + `Exit Plan:`
- **Commit:** `b38e268` -- "test: enforce track boundaries and add quarantine signposts"

#### Repo Rename: `tft-coach-234` -> `Auto-Battler-Coach-Lab`
- GitHub rename completed, remote URL updated
- Full repo copy from `E:\VS Code\tft-coach-234` to `E:\VS Code\Auto-Battler-Coach-Lab` via robocopy
- Git integrity verified in new location

#### Debranding and Data Sanitization
- Purged 11 tracked personal/raw data files from `data/personal/` and `data/api/raw/`
- Ran `git filter-repo` to remove sensitive paths from all git history
- Force-pushed rewritten `main` (backup branch `backup/pre-filter-2026-02-19` preserved)
- Renamed repo-facing "tft" labels in docs/scripts/bat/UI
- **Kept internal simulator module names intact** -- only repo-facing names debranded
- "tft" allowlist: `TFT16_*` protocol IDs, `MetaTFT` vendor names, `TFT_*` fallback env vars

### Performance Baseline (Documented, measured 2026-02-07)

| Metric | Value |
|--------|-------|
| Engine load time | 0.008s |
| 1v1 combat | 177.7 sims/sec |
| 4v4 team combat | 63.3 sims/sec |
| Full 8-player game | 1.325 sec/game, **2,717 games/hour/core** |
| End-to-end batch (11 workers) | **4.13 games/sec (14,868 games/hour)** |
| Rows per game | ~132 |
| Storage per 1K games | ~12 MB (Parquet), ~73 MB (JSONL) |

#### Scale-Up Estimates (from AGENTS.md)

| Games | Est. Rows | Parquet Size | Time (11 workers) |
|-------|-----------|-------------|-------------------|
| 1,000 | 132K | ~12 MB | ~4 min |
| 50,000 | 6.6M | ~600 MB | ~3.4 hours |
| 250,000 | 33M | ~3 GB | ~17 hours |
| 1,000,000 | 132M | ~12-20 GB | ~67 hours |

### Simulator Codebase Inventory (documented this day)

| File | Lines | Description |
|------|-------|-------------|
| `simulator/core/combat_engine.py` | 4,690 | Deterministic tick-based combat (30 FPS) |
| `simulator/core/champion_abilities.py` | 5,124 | 99/100 champion handlers |
| `simulator/core/item_effects.py` | 1,245 | Item combat effects |
| `simulator/game/game.py` | 718 | 8-player game orchestrator |
| `simulator/game/player.py` | 644 | Economy/leveling/board |
| `simulator/game/actions.py` | 530 | Agents: random/econ/slam |
| `simulator/game/constants.py` | 271 | Game rules, NAME_TO_API |
| `simulator/game/collector.py` | 162 | ML training data snapshots |
| `simulator/cloud_runner.py` | 693 | Production batch runner |
| Data: 106 champions, 283 augments, 134 items, 53 traits | | |

### Known Bugs/Gaps Documented

| Issue | Status |
|-------|--------|
| Augment combat effects | Largest gap -- 283 augments selected, ~0 have combat effects |
| 36 ranged champions | Missing missile speeds in timing data |
| 42 obfuscated trait vars | Hex hash names in `traits.json` |
| Some artifact items | Stats-only (Fishbones, CappaJuice, EternalPact lack combat effects) |
| Wukong ability handler | `defender=None` possible, pre-existing |

### Key Commits
- `4d6c892` docs: move aws runbook and archive heavy root docs
- `acab55a` docs: slim AGENTS and generate CLAUDE deterministically
- `b38e268` test: enforce track boundaries and add quarantine signposts
- `72b04b1` ci: fail PRs that change both src/models and models without override label
- `1780efc` refactor(simulator): move stats tables out of legacy Simulator package
- `71e61ef` chore(agent): enforce in-repo plans directory
- `2f6bfba` chore: declutter repo root + public-safe README
- `817fcf4` chore(repo): rename tft-scraper to scraper
- `af28f52` chore(repo): sanitize tracked data and debrand repo-facing tft labels

### Tests (20 passed)
- `tests/test_track_boundaries.py` -- quarantine enforcement
- `tests/test_no_hardcoded_artifact_paths.py` -- artifact resolver guard
- `tests/test_simulator_game_stats_imports.py` -- stats import validation
- `tests/test_coach_artifacts.py` -- env var precedence and fallback

---

## February 17, 2026

**Sources:** 1 Codex session (~4.5 hours, 13MB), 0 Claude Code sessions

### What Was Done

#### AWS Gates Runbook Execution -- First Live Cloud Runs
Codex orchestrated the full AWS gates pipeline via SSM on a `c8a.48xlarge` (192 vCPUs) instance. This was the first time the simulator ran at cloud scale with the Rust engine.

**Bootstrap** took 4 attempts to get right:
1. SSM parameter parsing error (semicolons in shell commands)
2. `set -o pipefail` fails under `/bin/sh` (SSM default)
3. `awscli` apt package unavailable on AMI
4. Success -- full setup: system packages, Python venv, Rust toolchain, repo clone, `maturin develop --release`, pip deps

**Environment variables set before runs:**
```bash
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export RAYON_NUM_THREADS=2
```

#### Calibration 10k -- Completed
- **Games:** 10,000 | **Workers:** 180 | **Throughput:** 252.97 games/sec
- **Total rows:** 1,410,767 | **Errors:** 0 | **Validation:** 19/19 PASS
- **S3:** `s3://tft-sim-results-forrest/tft-results/gates/calib/calib_10k_20260217_2052/`

#### Gate A 1k -- Completed
- **Games:** 1,000 | **Workers:** 180 | **Throughput:** 237.95 games/sec
- **Total rows:** 141,204 | **Errors:** 0 | **Validation:** 19/19 PASS
- **S3:** `s3://tft-sim-results-forrest/tft-results/gates/gate_a/gate_a_1k_20260217_2054/`

#### Gate B 50k -- Sim Completed, Training Timed Out
- **Games:** 50,000 | **Workers:** 180 | **Throughput:** 262.11 games/sec
- **Total rows:** 7,051,355 | **Errors:** 0 | **Validation:** 19/19 PASS
- **S3 upload:** NOT completed (session stopped by user)
- **Disk:** `/data/tft/results/gate_b_50k_20260217_2056/` (50 parquet chunks + summary.json)
- **XGBoost training** was combined into same SSM command -- SSM 1-hour timeout killed it (SIGKILL, ResponseCode 137)

#### Gates C (250k) and D (1M) -- Not Attempted

### Performance Metrics

| Run | Games | Workers | Throughput | Rows | Validation |
|-----|-------|---------|-----------|------|------------|
| Calibration 10k | 10,000 | 180 | **252.97 games/sec** (~911k/hr) | 1,410,767 | 19/19 PASS |
| Gate A 1k | 1,000 | 180 | **237.95 games/sec** (~857k/hr) | 141,204 | 19/19 PASS |
| Gate B 50k | 50,000 | 180 | **262.11 games/sec** (~944k/hr) | 7,051,355 | 19/19 PASS |

**vs Local Baseline:** c8a.48xlarge at ~262 games/sec = **~63x faster** than local 11-worker baseline (4.13 games/sec)

### AWS Infrastructure Details

| Resource | Value |
|----------|-------|
| Instance | c8a.48xlarge (192 vCPUs), `i-0851c860800286e7c` |
| Execution | SSM Send-Command (no SSH) |
| S3 Bucket | `tft-sim-results-forrest` |
| S3 Prefix | `tft-results/gates/` |
| VPC Endpoints | 3 created: `ssm`, `ssmmessages`, `ec2messages` (TCP 443) |

### Bugs Found
1. **SSM parameter parsing** -- semicolons conflicted with SSM JSON format
2. **`set -o pipefail` under `/bin/sh`** -- SSM default shell is dash, not bash
3. **`awscli` apt unavailable** -- installed via `pip install awscli` in venv instead
4. **Rust/cargo not on PATH in SSM** -- must explicitly `source $HOME/.cargo/env`
5. **AWS CLI not on PATH for S3 upload** -- venv not activated in upload command
6. **EC2 Describe permissions** -- cannot scope to instance ARN, requires `Resource: "*"`
7. **SSM not reaching instance** -- needed 3 VPC Interface Endpoints
8. **XGBoost training timeout** -- combined sim+train exceeded SSM 1-hour limit (SIGKILL)

### How to Run (Commands from This Day)

```bash
# Rust engine build on EC2 (inside venv)
source /data/tft/venv/bin/activate
cd /data/tft/repo
maturin develop --release

# Cloud sim run (180 workers on c8a.48xlarge)
python -m simulator.cloud_runner --games 50000 --workers 180 --engine rust_full \
  --agent-profile mixed --require-parquet --output /data/tft/results/<run_name>/

# Validation
python -m simulator.validate_output /data/tft/results/<run_name>/

# S3 upload
aws s3 cp /data/tft/results/<run_name>/ s3://tft-sim-results-forrest/tft-results/gates/<run_name>/ --recursive
```

### Recovery Items (as of end of day)
- Gate B 50k data on EC2 disk not uploaded to S3 (instance stopped, not terminated)
- XGBoost training needs separate SSM command with `nohup`/`screen` to avoid timeout
- User requested CPU throttle to ~80% (reduce workers from 180 to ~150)

---

## February 16, 2026

**Sources:** 3 Codex sessions (all tft-coach-234), 0 Claude Code sessions

### What Was Done

#### Rust-First Production Hardening (Major)

**Deterministic seeding fix (correctness bug):**
- `simulator/game/game.py` line 626: `_derive_combat_seed()` was only called for `engine_name == 'python'`. Rust combat in the Python game loop was **non-deterministic**.
- **Fix:** Extended to `engine_name in ('python', 'rust')` so Rust gets the same per-combat seed.

**Native Parquet writer hardened:**
- `simulator/core/rust_engine/src/lib.rs` was hardcoded to UNCOMPRESSED, no dictionary, no stats
- **Fix:** Full compression/dictionary/statistics option parsing through PyO3 boundary
- New CLI flags: `--parquet-compression`, `--parquet-use-dictionary`, `--parquet-write-statistics`, `--parquet-row-group-size`, `--parquet-write-batch-size`

**Arc-backed data sharing (performance):**
- `CombatData.champions` was `HashMap<String, Value>` -- deep cloned per Rayon worker
- **Fix:** Wrapped in `Arc<HashMap<String, Value>>` for cheap reference-count clones

**Streaming Parquet writer:**
- `run_games_batch_parquet_to_file()` was buffering all rows in memory before writing
- **Fix:** Refactored to write directly through one `ArrowWriter` per file (true streaming)

**CPython/venv mismatch guard:**
- `maturin develop --release` installs into venv, but `python` might run global CPython
- **Fix:** Added strict Rust extension API/CPython guard in `cloud_runner.py` that fails fast with rebuild commands

#### Schema Drift Prevention
- Created `snapshot_schema.py` as shared constant module for `JSONISH_COLUMNS` (now includes `opponent_augments`)
- Wired into `models/data_loader.py`, `models/dataset.py`, `simulator/cloud_runner.py`
- Fixed: `opponent_augments` was serialized to JSON strings in parquet but never decoded on read

#### Validator Scalability for 1M+ Outputs
- Refactored `simulator/validate_output.py` to stream rows instead of loading all into memory
- New CLI flags: `--max-rows`, `--sample-games`, `--sample-seed`
- Seedable reservoir sampling for reproducible partial validation
- All 19 checks preserved and passing

#### Reference Data Preflight Expanded
- `simulator/data/validate_reference_data.py` now also validates `items_set16.json` and `augments_set16.json`

#### Transformer Label Mode Fix
- `models/train_transformer.py` default changed from `label_mode="current"` to `label_mode="next_round"` (leak-safe temporal labeling)

### Performance Metrics

| Metric | Python Engine | Rust Engine | Rust Full Engine |
|--------|--------------|-------------|------------------|
| 1v1 throughput | 184-206 sims/sec | 3,980-5,040 sims/sec | 4,071-4,613 sims/sec |
| 4v4 team combat | 59-62 sims/sec | 403-446 sims/sec | 434-488 sims/sec |
| Full game | 0.95-0.99s/game | 0.31-0.34s/game | 0.32-0.37s/game |
| Full game throughput | 3,633-3,776 games/hr | 10,671-11,719 games/hr | 9,715-11,186 games/hr |

**Key: Rust is ~24x faster for 1v1, ~7x for 4v4, ~3x for full games vs Python.**

Determinism tests all passed across all 3 engines (1v1: 100 runs, 4v4: 50 runs, full game: 5 runs).

#### Rust Unit Tests: 34 passed
- `data::tests` (3), `damage::tests` (3), `engine::tests` (5), `hex_grid::tests` (11), `items::tests` (2), `python_rng::tests` (6), `targeting::tests` (2), `abilities::tests` (2)

#### Historical Batch Performance (from CONTINUITY)

| Mode | Games/sec | Notes |
|------|-----------|-------|
| Default rows/parquet | 2.96 | 1k games, 15.98 MB |
| Native-jsonl+parquet | 3.15 | 1k games, 6.67 MB |
| Native-parquet pre-tune | 3.04 | 1k games, 68 MB (1000 files) |
| Native-parquet post-tune | 3.11 | 1k games, 193 MB (1000 files) |
| Full-game benchmark | ~11,726 games/hr | 0.307s/game |

### Key Commits
- `f707f53` feat(simulator): harden rust determinism and native parquet writing
- `817f7f5` feat(simulator): add parquet sizing CLI and rust api guards
- `afc3540` docs(simulator): update rust-first parquet tuning guidance
- `4c17ea6` fix(models): unify jsonish schema and decode handling
- `49b4881` feat(simulator): stream output validation with seeded game sampling
- `345c18a` feat(simulator): gate required processed reference datasets
- `5a3ddb4` docs: sync ml pipeline status and validator usage

### Tests: 82-86 passed (full suite)

| Test File | Count |
|-----------|-------|
| `test_benchmark_parity_helpers.py` | 23 |
| `test_combat_regressions.py` | 13 |
| `test_coach_planner.py` | 10 |
| `test_data_loader.py` | 6 |
| `test_coach_archetype_library.py` | 4 |
| `test_validate_output.py` | 3 |
| `test_dataset_streaming.py` | 3 |
| `simulator/test_item_combat.py` | 3 |
| + 17 more across other suites | |

### Bugs Found
1. **Rust combat non-deterministic** -- seed not passed in Python game loop for Rust engine
2. **Parquet writer hardcoded** to UNCOMPRESSED with no dictionary/stats
3. **Deep CombatData clones** in Rayon batch path (performance regression)
4. **CPython/venv mismatch** -- extension installed in venv but global Python used at runtime
5. **Parquet direct-to-file buffered everything** in memory (defeated streaming purpose)
6. **`opponent_augments` not decoded** from JSON strings when reading parquet
7. **Validator OOM risk** on 1M+ game outputs (loaded all rows into memory)

### How to Run (New Commands from This Day)

```bash
# Benchmark all engines
python -m simulator.benchmark --engine python
python -m simulator.benchmark --engine rust
python -m simulator.benchmark --engine rust_full

# Rust engine with full parquet controls
python -m simulator.cloud_runner --engine rust_full --games 200 --workers 1 \
  --output results/my_output \
  --rust-full-native-parquet --rust-full-native-parquet-direct \
  --rust-full-rayon-batch-size 64 --rust-full-rayon-threads 8 \
  --parquet-compression snappy --parquet-use-dictionary --parquet-write-statistics \
  --parquet-row-group-size 64 --parquet-write-batch-size 64

# Sampled validation for large outputs
python -m simulator.validate_output results/big_run --sample-games 10 --max-rows 1280

# Reference data preflight
python -m simulator.data.validate_reference_data

# Build Rust engine
maturin develop --release

# Rust unit tests
cargo test --manifest-path simulator/core/rust_engine/Cargo.toml
```

---

## February 15, 2026

**Sources:** 9 Codex sessions (all tft-coach-234), 0 Claude Code sessions

### What Was Done

#### Combat Engine Correctness Fixes (Major -- from ChatGPT 5.2Pro Code Review)

Five critical bugs identified and fixed:

1. **HP item stats applied wrong** -- `hp` stat key only added to `unit.stats.hp`, not `unit.stats.max_hp`, causing tank items to be undervalued. Rust engine already did this correctly.
2. **Trait state not team-scoped** -- `TraitManager` stored Bilgewater count/serpents and Shadow Isles count/souls in global fields. Team 1's trait application overwrote team 0's state.
   - **Fix:** Added `TeamTraitState` dataclass, Bilgewater + Shadow Isles state now per-team.
3. **Invoker mana regen was a no-op** -- `mana_regen` was set but never read in `process_attack()`. Invoker trait did literally nothing.
   - **Fix:** Created centralized `CombatEngine.gain_mana()` with Invoker multiplier. All mana gains routed through it.
4. **RNG streams not separated** -- Game and combat shared a single `random` stream. Any combat change cascaded into shop/augment RNG, making regression testing fragile.
   - **Fix:** Combat saves/restores random state when `seed` is provided. `TFTGame` passes deterministic per-matchup seeds.
5. **validate_output check count drift** -- Docs said 19 checks, code headings said 16. Fixed to match actual 19.

#### Blacksmith Currency Move to Game Layer
- **Problem:** Blacksmith progression + artifacts keyed by `id(unit)` broke on unit reconstruction between rounds
- **Fix:** Moved to game layer (`simulator/game/player.py`) keyed by stable `ChampionInstance.instance_id`
- Added `instance_id` to `ChampionInstance` in `simulator/game/types.py`
- Bilgewater serpent storage also moved from TraitManager (combat layer) to Player (game layer)

#### Persistent Augment Bonuses Generalized
- Replaced `id(unit)` keying with `ChampionInstance.instance_id` for all persistent augment bonuses
- Created `AugmentManager.PERSISTENT_EFFECT_STAT_MAP` -- table-driven approach for any persistent augment stat
- Promoted `AbilityPower -> ('ability_power', 'ap')` to production mapping
- `Player.build_combat_team()` now replays all mapped bonuses generically

#### Rust Engine: Kill Attribution Debug Hook
- Added `debug_takedowns` struct with kill attribution data (which unit got the takedown)
- Exposed through PyO3 bindings in `simulator/core/rust_engine/src/lib.rs`
- Rust now tracks and returns `team*_bilgewater_serpents` and `team*_shadow_isles_souls`

#### Parity Diagnostics Hardened
- Parity dump now consumes takedown attribution context, labeling `last_hit_attribution_drift` explicitly
- New `--parity-dump-signatures-only` CLI flag for compact artifacts (summarized takedowns, no raw events)
- Guard against false drift labels when combat debug missing on one side or zero-takedown edge case

#### Coach Module Created (New Package)
- Created entire `coach/` package: planner, actions, scoring, explain, encoding, econ/items/position modules
- Wired into live WebSocket streaming in `app/`
- Created `docs/specs/COACH_EXPLANATION_SCHEMA.md`, `docs/specs/LIVE_TO_COACH_STATE_CONTRACT.md`

#### Row Schema Versioning
- Added `row_schema_version=1` to Python collector (`simulator/game/collector.py`) and Rust parquet writer
- Created `docs/specs/SNAPSHOT_ROW_SCHEMA.md`

#### Git History Rewrite
- Purged 88.41 MB `TFTSet16.wad.client` from all git history using `git-filter-repo`
- Added `*.wad.client` to `.gitignore`
- Fresh-cloned and re-synced repo

#### AWS Infrastructure Setup
- Registered AWS API MCP server for Codex: `codex mcp add aws-api --env AWS_REGION=us-east-1`
- Confirmed IAM user `codex-automation` in account `492411260211`
- S3 bucket `tft-coach-sims` ready for simulation output
- Full admin access confirmed (recommended: replace with least-privilege)

#### Cloud Run Command Planning
- Documented gate-based runs: Gate B (50k), Gate C (250k), Gate D (1M), Gate E (5M with 10 shards)
- Agent mix: `random:60,econ:30,slam:10`
- Confirmed `rust_full` best for c8a.48xlarge (Rayon parallelism avoids Python IPC bottleneck)
- Sharding via `--num-shards` / `--shard-index` with disjoint seed ranges

### Performance Metrics

| Metric | Value |
|--------|-------|
| Python 1v1 | 215.4 sims/sec |
| Python 4v4 | 58.4 sims/sec |
| Python Full Game | 0.955s/game (**3,769 games/hr/core**) |
| 30-game batch (1 worker) | 0.84 games/sec, 4,192 rows |
| Benchmark wall time | 196.8s (full verify suite) |
| Determinism | PASS (all 3 levels, all sessions) |
| Validation | 19/19 PASS |
| Prior A/B test (2 workers) | Default 3.69 g/s vs native-jsonl+parquet 3.98 g/s (+7.9%) |

### Key Commits
- `ccf3f015` feat(simulator): add row_schema_version to training rows
- `62ff4b96` feat(coach): add planner, offline eval gate, and artifacts
- `74f36788` feat(app): stream coach recommendations over live websocket
- `e582335e` ci: build frontend and add coach eval gate
- `432965ce` docs: add coach upgrade index and repo architecture
- `aad5c878` chore(data): add tactics.tools match scraper
- `cfb97b6` fix(simulator): tighten parity diagnostics and persistent combat state

### Tests: 57 -> 68 passed (growing through the day)
- `test_combat_regressions.py` (new): HP item max_hp, Bilgewater team-scoped, Shadow Isles team-scoped, Invoker mana multiplier, RNG isolation, augment persistence, upgrade/sell transitions, PERSISTENT_EFFECT_STAT_MAP coverage
- `test_benchmark_parity_helpers.py`: Parity dump shape, signatures-only compact, zero-takedown, CLI artifact size, one-sided debug guard
- Rust `cargo test`: 34 passed
- Full verify.ps1: pytest + benchmark + validate + frontend build

### Bugs Found
1. **HP item applied to hp but not max_hp** (Python only -- Rust was correct)
2. **Trait state global instead of team-scoped** (Bilgewater/Shadow Isles cross-contamination)
3. **Invoker mana regen was a complete no-op**
4. **Game + combat shared RNG stream** (combat changes cascaded into shop/augment RNG)
5. **validate_output check headings miscounted** (16 vs actual 19)
6. **Blacksmith keyed by `id(unit)`** broke on unit reconstruction between rounds
7. **88.41 MB WAD binary** in git history (purged with filter-repo)

### Files Changed (Key)
- `simulator/core/combat_engine.py` -- HP items, TeamTraitState, gain_mana(), RNG isolation, augment persistence, PERSISTENT_EFFECT_STAT_MAP
- `simulator/core/champion_abilities.py` -- Team-scoped reads, Ambessa mana flow
- `simulator/core/item_effects.py` -- Mana gains through gain_mana()
- `simulator/game/game.py` -- Combat seed passing, currency wiring, debug sidecar
- `simulator/game/player.py` -- Blacksmith/Bilgewater storage, instance_id, augment replay
- `simulator/game/types.py` -- ChampionInstance.instance_id
- `simulator/game/collector.py` -- row_schema_version=1
- `simulator/core/rust_engine/src/engine.rs` -- debug_takedowns, trait counters
- `simulator/core/rust_engine/src/lib.rs` -- PyO3 bindings updated
- `simulator/core/rust_engine/src/game_loop.rs` -- debug sidecar plumbing
- `simulator/benchmark.py` -- takedown attribution, signatures-only mode
- `simulator/validate_output.py` -- check numbering fix
- `.github/workflows/test-coverage.yml` -- Rust regression + parity CI steps

---

## February 14, 2026

**Sources:** 2 Codex sessions (both tft-coach-234), 0 Claude Code sessions

### What Was Done

#### Gate A Run (1k games, rust_full engine)
- **Command:** `--engine rust_full --games 1000 --workers 11 --agent-profile mixed --chunk-size 500 --require-parquet`
- **Output:** `results/gates/gate_a_rust_full_mixed_1k_20260214`
- **Rate:** 14.75 games/sec | **Rows:** 141,204 | **Errors:** 0 | **Validation:** 19/19 PASS
- Rust config: rayon_batch_size=64, rayon_threads=11, native_parquet=True, native_parquet_direct=True, snappy

#### Gate B Run (50k games, rust_full engine)
- **Command:** `--engine rust_full --games 50000 --workers 11 --agent-profile mixed --chunk-size 500 --require-parquet`
- **Output:** `results/gates/gate_b_rust_full_mixed_50k_seed0_20260214`
- **Rate:** 11.95 games/sec | **Wall time:** 69.7 minutes | **Rows:** 7,051,355 | **Errors:** 0
- **Validation:** 19/19 PASS (took 341.7s to validate)
- **100 Parquet chunks**, ~10.83 GB on disk
- **Top champs:** Sylas (1.17), Baron Nashor (1.23), Shyvana (1.25), Kindred (1.29)
- **Bottom champs:** Aphelios (5.35), Sona (5.14), Caitlyn (5.05)

#### XGBoost Training Attempted (Gate B data)
- Started with external-memory mode against 7,051,355 rows
- Ran **~1.5 hours** locally before user killed it -- single-core Python feature engineering bottleneck
- No `fight_training_report.json` produced (training hadn't reached XGBoost tree-building phase)
- **Pivoted to AWS plan** -- upload dataset to S3, run on cloud instance

#### Pre-existing XGBoost Baseline (1k games)
- Accuracy: **0.7036**, AUC-ROC: **0.7793**
- Params: max_depth=8, learning_rate=0.05, n_estimators=500, subsample=0.8, tree_method=hist

#### Coach Eval Gate + CI/CD Fixes
- Added `DecisionTrace.state_summary` with `unit_id_to_champion_id` mapping (resolves opaque IDs to champion names)
- Added `coach-eval-gate` CI job running `python -m coach.offline.eval_coach` on Ubuntu
- Fixed CI `continue-on-error: true` on critical steps (made them actual gates)
- Fixed CI `working-directory` from `./app` to `./app/frontend`
- Fixed `verify.ps1` early-exit blocking CI eval gate + added POSIX venv detection
- Fixed mojibake in Figma design docs

### Performance Metrics

| Run | Engine | Games | Workers | Rate | Rows | Time |
|-----|--------|-------|---------|------|------|------|
| Gate A (new) | rust_full | 1,000 | 11 | **14.75 g/s** | 141,204 | 67.8s |
| Gate B (new) | rust_full | 50,000 | 11 | **11.95 g/s** | 7,051,355 | 69.7 min |
| Calibration (prior) | rust_full | 10,000 | 11 | **13.86 g/s** | -- | -- |
| Calibration (prior) | Python mixed | 10,000 | 11 | **4.61 g/s** | 1,324,649 | -- |
| Benchmark (verify) | Python | 5 games | 1 | 0.965s/game | -- | -- |

Python benchmark: 196.5 sims/sec (1v1), 61.3 sims/sec (4v4), **3,732 games/hr** (full game).
All determinism tests PASS. 57 pytest tests passed (73.1s).

### Bugs Found
1. **XGBoost external-memory no progress output** -- training appears hung for hours (only writes output near end)
2. **CI `continue-on-error: true`** on critical steps made frontend build/test a no-op gate
3. **CI working-directory** pointed to `./app` instead of `./app/frontend`
4. **verify.ps1 early-exit** blocked CI from running coach eval gate on clean trees
5. **verify.ps1 POSIX detection** -- only found Windows venv Python
6. **Mojibake** in Figma design docs from encoding corruption

### How to Run (Commands from This Day)

```bash
# Gate A (1k, rust_full)
python -m simulator.cloud_runner --engine rust_full --games 1000 --workers 11 \
  --agent-profile mixed --chunk-size 500 --require-parquet \
  --output results/gates/gate_a_rust_full_mixed_1k

# Gate B (50k, rust_full)
python -m simulator.cloud_runner --engine rust_full --games 50000 --workers 11 \
  --agent-profile mixed --chunk-size 500 --require-parquet \
  --output results/gates/gate_b_rust_full_mixed_50k

# XGBoost training (external memory, large datasets)
python -m models.train_xgboost --data results/gates/gate_b_* --task fight \
  --output models_checkpoints/gate_b_fight \
  --external-memory --external-batch-size 8192 \
  --external-cache-dir /mnt/xgb_cache

# Upload to AWS for cloud training
aws s3 sync results/gates/gate_b_* s3://tft-sim-results-forrest/tft/gate_b_50k/
```

---

## February 13, 2026

**Sessions**: 6 Codex sessions (all tft-coach-234), 0 Claude Code sessions
**Total duration**: ~9+ hours across 6 sessions
**Branch**: `codex/split-commits-20260213` (most work uncommitted)

### What Was Done

**Session 1 (12:11, ~1.5h) — Git Cleanup & Commit Split**
- Diagnosed VS Code "too many active changes" warning — caused by ~30k untracked files in `tft-scraper/data/` and `results/`
- Fixed via `.git/info/exclude` (local-only, not `.gitignore`) — untracked count dropped from ~30k to 13
- Split working tree into 3 commits on new branch `codex/split-commits-20260213`:
  - `404212df` — `perf(simulator): centralize position updates and occupied cache`
  - `0f8b5674` — `feat(ml): improve transformer training pipeline and eval`
  - `09faf9ff` — `ci: add windows cython smoke test and verify helper`
- Created `scripts/verify.ps1` verification script and `tests/test_occupied_hex_cache.py`

**Session 2 (13:33, ~1h) — Coach Layer Creation**
- Created entire `coach/` package (~20 files) implementing planning-with-a-critic coaching layer:
  - Orchestrator: `coach/coach.py`
  - State/actions/rules: `coach/state.py`, `coach/actions.py`, `coach/rules.py`
  - Decision modules: items, positioning, econ, shop (each with candidates + executor)
  - Scorers: `coach/scoring/combat.py` (combat sim tempo), `coach/scoring/evaluator.py`, `coach/scoring/archetypes.py`
  - Offline pipeline: `coach/offline/build_knowledge_base.py`, `coach/offline/train_evaluator.py`
  - Demo runner: `coach/demo.py`
- Coach uses `simulator.core.combat_engine.CombatEngine` directly for tempo scoring
- Fixed SyntaxError in archetypes.py and ValueError in train_evaluator.py (parquet list-type columns)

**Session 3 (14:29, ~3h) — Coach Verification + Live App Wiring**
- Verified coach layer end-to-end: pytest pass, demo success, benchmark determinism PASS
- Wired coach into live app pipeline:
  - `app/server/websocket.py` — new `/redux` WebSocket endpoint
  - `app/redux_bridge/inject.js` — MetaTFT Redux store interception script
  - `app/services/pool_tracker.py` — champion pool tracking (Set 16 pool sizes)
  - Updated frontend: `CoachingPanel.tsx`, `useGameState.ts`
- Implemented pool-aware Monte Carlo lookahead in `coach/odds.py`
- Improved candidate quality: defensive items prefer tanky units, expanded position templates

**Session 4 (16:01, ~38min) — Documentation**
- Created `docs/CURRENT_MODEL_AND_SIMULATOR.md` and `docs/REPO_ARCHITECTURE.md`
- Documented simulator's two flows: runtime live coaching (WebSocket) and offline simulation/training
- Referenced 106 champions, 283 augments, decision-time snapshots as Parquet/JSONL

**Session 5 (18:02, ~2.7h) — Coach Upgrade Timeline (Milestones 0-10)**
- Unified coach data structures: `CoachAction`, `ScoreBreakdown`, `Explanation`, `ActionPlan`
- Combat scoring hardening using simulator's Python combat engine for relative ranking
- WebSocket payload versioning (`coach_payload_version: 1`)
- Explored simulator internals deeply: combat engine `run_combat()`, game loop round progression, round damage arrays, Rust `TrainingRow` struct, Parquet serialization
- Ran cloud runner validation: 30 games, 1 worker, Python engine — **19/19 checks PASS**
- Ran Rust engine cargo tests: **34 passed, 0 failed**

**Session 6 (23:02, ~2.2h) — Coach Milestones 10-12 + Eval Gate**
- Archetype item signatures from meta comp data
- Offline eval harness: `coach/offline/eval_coach.py` with fixed eval sets, `[GATE] PASS/FAIL` exit codes
- Trace viewer: `coach/offline/view_traces.py` for readable decision trace analysis
- `DecisionTrace` dataclass added to `coach/coach.py`, writes to `outputs/coach/traces/`
- Eval gate wired into `scripts/verify.ps1` as new verification step
- Explored combat engine board mirroring, `create_unit()`, `run_combat()` for positioning module

### Performance Metrics

**Python Engine Benchmark (best run — Session 5)**:
| Metric | Value |
|--------|-------|
| 1v1 throughput | 270.5 sims/sec |
| Team combat (4v4) | 77.9 sims/sec |
| Full game | 0.715s/game (5,033 games/hr) |
| Avg rounds/game | 26.4 |

**Python Engine Benchmark (Session 3)**:
| Metric | Value |
|--------|-------|
| 1v1 throughput | 199.8 sims/sec |
| Team combat (4v4) | 56.4 sims/sec |
| Full game | 1.033s/game (3,485 games/hr) |
| Avg rounds/game | 27.1 |

**Cloud Runner (Session 5)**: 1.3 games/sec (30 games, 1 worker, Python engine, local)

### Tests

- Python tests grew from **43 to 57** across the day's sessions
- Rust engine: **34 tests passed** (damage, abilities, hex grid, items, RNG parity, targeting)
- New test files: `test_occupied_hex_cache.py`, `test_coach_planner.py`, `test_coach_archetype_library.py`, `test_coach_combat_scorer.py`, `test_coach_position_module.py`
- Output validation: **19/19 checks PASS**

### Determinism

All determinism tests passed consistently across all benchmark runs:
- 1v1 (100 runs): PASS
- Team combat (50 runs): PASS
- Full game (5 runs): PASS — Placements: `[(7,1),(0,2),(4,3),(5,4),(3,5),(2,6),(6,7),(1,8)]`

### Key Commits

- `915fdff4` — HEAD of main (Merge PR #98: optimize-simulator-performance)
- `404212df` — perf(simulator): centralize position updates and occupied cache
- `0f8b5674` — feat(ml): improve transformer training pipeline and eval
- `09faf9ff` — ci: add windows cython smoke test and verify helper

### Bugs Found & Fixed

1. **VS Code git overload** — 30k untracked files in `tft-scraper/data/` and `results/` — fixed via `.git/info/exclude`
2. **SyntaxError in archetypes.py** — escaped quotes in f-string — fixed by extracting to helper variable
3. **ValueError in train_evaluator.py** — parquet list-type columns not parseable by `int()` — fixed with type detection
4. **PowerShell syntax issues** — bash-style heredocs, `||` operator, `Get-Date -AsUTC` not available — workarounds applied
5. **GitHub 88MB file warning** — large file hitting LFS recommendation threshold

### How to Run

```bash
# Verification script (created this day)
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1 -Mode changed
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1 -Mode all
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1 -Mode changed -CoachEvalGate

# Coach demo
python -m coach.demo

# Coach offline eval
python -m coach.offline.eval_coach --eval-set outputs/coach/eval_sets/fixed_eval_set_opt_phase1_25.jsonl --limit 25 --output outputs/coach/eval_reports/fixed_current.json

# Trace viewer
python -m coach.offline.view_traces --input outputs/coach/traces/coach_traces_YYYYMMDD.jsonl --limit 5 --top 5

# Train evaluator from parquet
python -m coach.offline.train_evaluator --input-dir results/opt_phase1_validate_100 --output outputs/coach/evaluator_linear.json

# Simulator benchmark
python -m simulator.benchmark --engine python --games 20

# Cloud runner (small validation)
python -m simulator.cloud_runner --games 30 --workers 1 --engine python --require-parquet --output results/tmp

# Validate output
python -m simulator.validate_output results/tmp

# Rust engine tests
cd simulator/core/rust_engine && cargo test
```

---

<!-- Next day will be added above this line -->
