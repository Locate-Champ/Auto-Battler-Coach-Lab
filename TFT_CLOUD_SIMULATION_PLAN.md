# TFT Cloud Simulation Plan v2 - Throughput-Calibrated, Gate-Based

> Date: 2026-02-08
> Purpose: Execution playbook for 50k -> 250k -> 1M simulation scale-up with explicit quality and feasibility gates.

---

## What Changed from v1

1. Throughput planning now uses end-to-end `simulator.cloud_runner` measurements (collector + serialization), not only microbenchmark loops.
2. Scale-up is now a hard gate sequence: `Gate A (1k) -> Gate B (50k) -> Gate C (250k) -> Gate D (1M)`.
3. A formal training-pipeline feasibility gate is added, and implementation now exists for streaming transformer training plus external-memory XGBoost.

---

## 0. Source-of-Truth Inputs (Repo Evidence)

This plan is grounded in the following files:

1. `simulator/benchmark.py` and `Current Simulation Setup.txt`
2. `results/run_1000_verify_ladder_v3_leaksafe/summary.json`
3. `results/run_1000_verify_ladder_v2/summary.json`
4. `results/run_1000_verify_ladder/summary.json`
5. `models/checkpoints/baseline_run1000_v3_leaksafe/fight_training_report.json`
6. `models/data_loader.py`
7. `models/dataset.py`
8. `models/train_transformer.py`
9. `simulator/cloud_runner.py`
10. `simulator/validate_output.py`

---

## 1. Throughput Reality and Planning Formulas

### 1.1 Microbenchmark vs End-to-End Throughput

| Basis | What It Measures | Observed Result | Use Case |
|-------|-------------------|-----------------|----------|
| Microbenchmark (`simulator/benchmark.py`) | Core full-game loop speed | `1.325 sec/game`, `2,717 games/hour/core` | Engine regression tracking |
| End-to-end `cloud_runner` | Real run with collector + chunk writes + process overhead | `4.13 games/sec` on `11 workers` (`14,868/hour`), and `2.61-2.74 games/sec` on `8 workers` (`9,396-9,864/hour`) | Runtime and cost planning |

Use end-to-end numbers for scheduling and spend decisions.

### 1.2 Runtime Formulas

```text
hours = games / games_per_hour
games_per_hour = games_per_sec * 3600
```

### 1.3 Local 1M Estimate (From Observed Summaries)

- Fast observed local profile: `1,000,000 / 14,868 = 67.3 hours`
- Slow observed local profile: `1,000,000 / 9,396 = 106.4 hours`

**Planning band for local 1M:** `67-106 hours` (profile + serialization mode dependent).

---

## 2. Rows and Storage Conversion (Format-Aware)

### 2.1 Rows per Game

Observed rows/game from existing summaries:

- `131.66` (`run_1000_verify_ladder_v3_leaksafe`)
- `133.10` (`run_1000_verify_ladder_v2`)
- `133.09` (`run_1000_verify_ladder`)

Use `~132 rows/game` for planning.

### 2.2 Storage by Output Format

Observed storage per 1,000 games:

- Parquet run: `~12.14 MB` (`chunk_*.parquet`)
- JSONL runs: `~73.3-73.5 MB` (`chunk_*.jsonl`)

| Games | Est. Rows | Parquet (compressed, observed extrapolation) | JSONL fallback (observed extrapolation) |
|-------|-----------|-----------------------------------------------|------------------------------------------|
| 1,000 | ~132k | ~12-15 MB | ~73-75 MB |
| 10,000 | ~1.32M | ~120-150 MB | ~0.73-0.75 GB |
| 50,000 | ~6.6M | ~0.6-0.8 GB | ~3.7 GB |
| 250,000 | ~33M | ~3-4 GB | ~18-19 GB |
| 1,000,000 | ~132M | ~12-20 GB (low tens of GB) | ~73-80 GB |
| 5,000,000 | ~660M | ~60-100 GB | ~365-400 GB |

### 2.3 Hard Requirement

Install `pyarrow` before large runs so `cloud_runner` writes parquet instead of JSONL fallback.

```bash
pip install pyarrow
```

---

## 3. Gate-Based Scale Path (Hard Stop/Go)

Progression is mandatory:

`Gate A (1k smoke) -> Gate B (50k baseline) -> Gate C (250k pre-prod) -> Gate D (1M prod)`

### 3.1 Gate Definitions

| Gate | Simulation Target | Required Checks (All Must Pass) | If Any Check Fails |
|------|-------------------|----------------------------------|--------------------|
| A | 1,000 games | Error rate `<1%`; rows/game `100-180`; `python -m simulator.validate_output` passes; output has chunk files + `summary.json` + `checkpoint.json` | Stop. Fix runtime/data issues first. Re-run Gate A. |
| B | 50,000 games | Gate A checks + leak-safe XGBoost fight baseline in band (`accuracy >= 0.68` and `AUC >= 0.76`, or within `-0.03` / `-0.02` of `0.7036` / `0.7793`) | Stop. Fix feature engineering, leakage, or simulator/data quality. |
| C | 250,000 games | Gate B checks + chosen agent-mix run health; storage/transfer plan written; runtime projection variance within `+-20%` after calibration | Stop. Adjust chunk size/profile mix/infrastructure and re-run C. |
| D | 1,000,000 games | Gate C pass + feasibility blockers acknowledged and dependency gate status recorded (Section 4) | Stop. Do not spend on full 1M run until unblocked. |

### 3.2 Canonical Commands Per Gate

#### Gate A (1k smoke)

```bash
python -m simulator.cloud_runner --games 1000 --workers 11 \
  --output training_data/gate_a_1k --agent-profile mixed --chunk-size 100 \
  --require-parquet --checkpoint-every 100 --progress-every 100 --max-errors 10

python -m simulator.validate_output training_data/gate_a_1k

python -m models.train_xgboost --data training_data/gate_a_1k \
  --task fight --output models/checkpoints/gate_a_1k
```

#### Gate B (50k baseline)

```bash
python -m simulator.cloud_runner --games 50000 --workers 11 \
  --output training_data/gate_b_50k --agent-profile mixed --chunk-size 500 \
  --require-parquet --checkpoint-every 1000 --progress-every 1000 --max-errors 100

python -m simulator.validate_output training_data/gate_b_50k

python -m models.train_xgboost --data training_data/gate_b_50k \
  --task fight --output models/checkpoints/gate_b_50k \
  --external-memory --external-batch-size 8192
```

#### Gate C (250k pre-prod, mixed profile blend)

```bash
# 60% mixed
python -m simulator.cloud_runner --games 150000 --seed-start 0 --workers 11 \
  --output training_data/gate_c_250k/mixed_150k --agent-profile mixed --chunk-size 500 \
  --require-parquet --checkpoint-every 2000 --progress-every 2000 --max-errors 200

# 30% ladder
python -m simulator.cloud_runner --games 75000 --seed-start 150000 --workers 11 \
  --output training_data/gate_c_250k/ladder_75k --agent-profile ladder --chunk-size 500 \
  --require-parquet --checkpoint-every 2000 --progress-every 2000 --max-errors 200

# 10% random
python -m simulator.cloud_runner --games 25000 --seed-start 225000 --workers 11 \
  --output training_data/gate_c_250k/random_25k --agent-profile random --chunk-size 500 \
  --require-parquet --checkpoint-every 2000 --progress-every 2000 --max-errors 200

python -m simulator.validate_output training_data/gate_c_250k
```

#### Gate D (1M production)

```bash
# 60% mixed
python -m simulator.cloud_runner --games 600000 --seed-start 0 --workers <N> \
  --output training_data/gate_d_1m/mixed_600k --agent-profile mixed --chunk-size 500 \
  --require-parquet --checkpoint-every 5000 --progress-every 5000 --max-errors 500

# 30% ladder
python -m simulator.cloud_runner --games 300000 --seed-start 600000 --workers <N> \
  --output training_data/gate_d_1m/ladder_300k --agent-profile ladder --chunk-size 500 \
  --require-parquet --checkpoint-every 5000 --progress-every 5000 --max-errors 500

# 10% random
python -m simulator.cloud_runner --games 100000 --seed-start 900000 --workers <N> \
  --output training_data/gate_d_1m/random_100k --agent-profile random --chunk-size 500 \
  --require-parquet --checkpoint-every 5000 --progress-every 5000 --max-errors 500

python -m simulator.validate_output training_data/gate_d_1m
```

---

## 4. Preconditions Before 1M Generation and Training

### 4.1 Current Status After Loader Upgrades

Implemented now:

- `models/train_transformer.py` defaults to streaming mode.
- `models/dataset.py` provides `TFTStreamingDataset` and split-count estimation without full materialization.
- `models/data_loader.py` provides `iter_raw()`, `count_rows()`, and bounded loading (`max_rows`, optional reservoir sampling).
- `models/train_xgboost.py` provides `--external-memory` using `ExtMemQuantileDMatrix` with disk-backed cache pages.

Remaining limitation:

- External-memory XGBoost uses deterministic game-hash train/test splitting (not stratified `train_test_split`), so tiny datasets may need larger sample size for stable class balance.

### 4.2 Formal Dependency Gates

#### Dependency Gate S (1M simulation storage/IO readiness)

1. Confirm enough disk for chosen format + temporary files.
2. Confirm transfer path and expected upload/download time.
3. Confirm parquet output (`pyarrow` installed).

**1M generation is allowed only if S passes.**

#### Dependency Gate T (1M training readiness)

1. Transformer streaming path is used (`models.train_transformer` default mode, or explicitly not `--in-memory`).
2. Split logic preserves game-level anti-leakage (`label_mode=next_round` + game-hash split).
3. Dry-run training on Gate C-scale directory with bounded steps completes without OOM.
4. XGBoost Gate B+ runs use `--external-memory` (bounded `--max-rows` only for smoke/calibration runs).

**1M model training is blocked until T passes.**

---

## 5. Cloud Strategy Update (Calibrate Then Extrapolate)

### 5.1 Principle

- Simulation workload: CPU-bound
- Training workload: GPU-bound

Do not use GPU instances for data generation.

### 5.2 Calibration Workflow (Required on Target Instance)

Before any large cloud run, execute a 10k calibration job on the exact target machine type:

```bash
python -m simulator.cloud_runner --games 10000 --workers <N> \
  --output /data/calibration_10k --agent-profile mixed --chunk-size 500 \
  --require-parquet --checkpoint-every 500 --progress-every 500 --max-errors 100

python -m simulator.validate_output /data/calibration_10k
```

Use `summary.json` from that run:

```text
games_per_hour_measured = games_per_sec * 3600
projected_runtime_hours = target_games / games_per_hour_measured
compute_cost = hourly_rate * projected_runtime_hours
buffered_compute_cost = compute_cost * 1.25
```

### 5.3 Provider Options (Verify Pricing at Execution Time)

| Option | Strength | Must Verify Right Before Run |
|--------|----------|------------------------------|
| Hetzner CPU instance classes | Usually strong price/perf for pure CPU simulation | Current hourly rate, included storage, egress policy |
| AWS EC2 Spot CPU instances | Regional flexibility and high core options | Live spot rate, interruption behavior, EBS + egress costs |
| Local workstation | No cloud bill | Long wall-clock time and machine availability |

All provider pricing in this plan is variable. Verify at execution time.

---

## 6. Training Expectations and Corrected Math

### 6.1 XGBoost Is Mandatory Pre-Transformer Health Gate

Do not start transformer scaling until Gate B XGBoost leak-safe baseline is healthy.

Known reference from repo (`baseline_run1000_v3_leaksafe`):

- Fight accuracy: `0.7036`
- Fight AUC: `0.7793`

For larger corpora, use `--external-memory` by default. Use bounded rows (`--max-rows`) only for smoke/calibration runs.

### 6.2 Correct Transformer Step-Time Math

```text
steps_per_epoch = ceil(num_rows / batch_size)
epoch_seconds = steps_per_epoch / observed_steps_per_second
```

Example for `132M` rows and batch `2048`:

- `steps_per_epoch = 64,454`
- If `1000 steps/sec` -> `64.5 sec/epoch` (~1.1 min)
- If `100 steps/sec` -> `644.5 sec/epoch` (~10.7 min)
- If `20 steps/sec` -> `3,222.7 sec/epoch` (~53.7 min)

Use measured `steps/sec` from your own first epoch on target hardware.

### 6.3 Accuracy Policy

Do not hardcode fixed expected transformer accuracy percentages before first real run.

Use gated deltas instead:

1. Establish first transformer baseline on Gate C data.
2. Scale data only if validation metrics keep improving materially.
3. If metric gain is `<0.005` across a 4x data increase, prioritize simulator fidelity fixes over more volume.

### 6.4 Transformer Training Command (Streaming First)

```bash
python -m models.train_transformer \
  --data training_data/gate_c_250k \
  --output models/checkpoints/transformer_gate_c \
  --label-mode next_round \
  --steps-per-epoch 2000 \
  --val-steps 200 \
  --test-steps 200
```

Use `--in-memory` only for small local subsets.

---

## 7. Data Validation Protocol (Row-Snapshot Compatible)

### 7.1 Canonical Validator

Always run:

```bash
python -m simulator.validate_output <output_dir>
```

This is the primary gate for placement integrity, round sanity, and schema-level issues.

### 7.2 Required Checks (All Measurable from Artifacts)

1. Error rate `<1%` from `summary.json` (`num_errors / (num_games + num_errors)`).
2. Rows/game in expected band (`100-180`) from `summary.json`.
3. Placement values in valid range (`1-8`) and per-game integrity (validator pass).
4. Round sanity (no outlier game lengths, validator pass).
5. Null/schema sanity on chunk files for required columns.
6. Manual sample inspection of random rows.

### 7.3 Explicitly Avoid These Invalid Assumptions

1. Do not expect uniform placement distribution at row level.
2. Do not require a fixed draw-rate percentage.
3. Do not assume row-level class balance stays constant across profile mixes.

---

## 8. Agent Profile Strategy (Gate-Driven Allocation)

### 8.1 Default 1M Target Mix

- Mixed: `60%` (`600k`)
- Ladder: `30%` (`300k`)
- Random: `10%` (`100k`)

### 8.2 Adaptive Rules from Gate C Measurements

1. If ladder throughput is `<80%` of mixed throughput, reduce ladder share by `10-15` points and move that share to mixed.
2. If any profile error rate is `>=1%`, pause and debug that profile before full allocation.
3. Keep random floor at `>=10%` to preserve edge-case coverage.

### 8.3 Fallback Production Mixes

- Moderate fallback: `70/20/10` (mixed/ladder/random)
- Conservative fallback: `75/15/10`

---

## 9. Timeline and Budget (Formula-First)

### 9.1 Timeline with Gate Checkpoints

#### Expected Path (Cloud-Calibrated)

1. Day 1: Gate A + Gate B locally; verify leak-safe XGBoost health.
2. Day 2: 10k calibration on target cloud CPU instance; finalize projection.
3. Day 2-3: Gate C (250k) and validation.
4. Day 3-4: Gate D (1M) start and monitor.
5. Day 4+: Post-run validation and training kickoff only if dependency gates are satisfied.

#### Local-Only Reference (Observed Range)

- 50k: ~`3.4-5.3 hours`
- 250k: ~`16.8-26.6 hours`
- 1M: ~`67-106 hours`

### 9.2 Budget Formulas

```text
simulation_compute_cost = cpu_hourly_rate * measured_simulation_hours
training_compute_cost = gpu_hourly_rate * measured_training_hours
subtotal = simulation_compute_cost + training_compute_cost + storage_transfer_cost
buffered_total = subtotal * 1.25
```

Use `1.25x` rerun buffer minimum.

### 9.3 Example Cost Scenarios (Illustrative, Not Fixed)

1. If 1M takes 10 hours at $0.50/hour: compute = `$5.00`, buffered = `$6.25`.
2. If 1M takes 18 hours at $1.10/hour: compute = `$19.80`, buffered = `$24.75`.

These are examples only. Recompute using your calibration run.

---

## 10. Decision Flowchart (Enforced Gates + Dependencies)

```text
START
  |
  v
Gate A (1k smoke) passed?
  |
  +-- NO -> Fix runtime/data issues, rerun Gate A.
  |
  +-- YES
         |
         v
Gate B (50k + leak-safe XGBoost health) passed?
  |
  +-- NO -> Fix feature engineering/leakage/simulator quality, rerun Gate B.
  |
  +-- YES
         |
         v
Gate C (250k pre-prod + storage/IO readiness) passed?
  |
  +-- NO -> Fix profile mix/chunking/infra, rerun Gate C.
  |
  +-- YES
         |
         v
Dependency Gate S (1M storage/IO ready) passed?
  |
  +-- NO -> Do not run 1M. Fix storage/transfer plan.
  |
  +-- YES
         |
         v
Run Gate D (1M production simulation)
         |
         v
Dependency Gate T (streaming/sharded training path ready) passed?
  |
  +-- NO -> Archive data only; block full 1M training until pipeline is fixed.
  |
  +-- YES
         |
         v
Run transformer baseline, then scale only if validation gains continue.
```

---

## 11. Public APIs / Interfaces / Types

1. `simulator.cloud_runner` now includes:
   - `--checkpoint-every`
   - `--progress-every`
   - `--max-errors`
   - `--require-parquet`
2. `models.train_transformer` now includes:
   - streaming default (legacy mode via `--in-memory`)
   - `--label-mode`
   - `--steps-per-epoch`, `--val-steps`, `--test-steps`
   - `--scan-max-rows`, `--max-examples-per-split`, `--no-shuffle-files`
3. `models.train_xgboost` now includes:
   - `--external-memory`
   - `--external-batch-size`, `--external-cache-dir`, `--keep-external-cache`
   - `--row-batch-size`, `--max-rows`, `--early-stopping-rounds`
4. `models.dataset` now includes `TFTStreamingDataset` and `estimate_streaming_split_counts`.
5. `models.data_loader` now includes streaming iteration and bounded-row loading options.

---

## 12. Validation Test Cases for This Plan

1. Verify command validity:
   - `python -m simulator.cloud_runner --help`
   - `python -m models.train_xgboost --help`
   - `python -m models.train_transformer --help`
   - `python -m simulator.validate_output --help`
2. Run transformer streaming smoke test:
   - `python -m models.train_transformer --data <dir> --epochs 1 --steps-per-epoch 2 --val-steps 1 --test-steps 1 --max-examples-per-split 256`
3. Run external-memory XGBoost smoke test:
   - `python -m models.train_xgboost --data <dir> --task fight --n-estimators 20 --external-memory --external-batch-size 2048 --max-rows 200000`
4. Recompute runtime projections from at least one real `summary.json` and confirm formula consistency.
5. Confirm storage table includes parquet and JSONL implications.
6. Confirm every gate criterion is measurable via `summary.json`, `errors.json`, chunk files, and training reports.
7. Confirm no fixed cloud-price claims are presented as guaranteed truth.

---

## 13. Acceptance Criteria

1. No arithmetic contradictions.
2. Every numeric claim is repo-evidenced or explicitly variable with calibration instructions.
3. Scale path is deterministic and gate-driven.
4. Another engineer can execute without policy decisions.
5. The plan preserves original intent while reducing wasted spend risk.

---

## 14. Assumptions and Defaults

1. Full rewrite (not incremental patch).
2. Default scaling path is `50k -> 250k -> 1M`.
3. End-to-end `cloud_runner` throughput is the runtime/cost baseline.
4. Parquet (`pyarrow`) is the expected production output format.
5. Transformer training should use streaming mode by default.
