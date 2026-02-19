# AWS Gate Runbook (tft-coach-234)

This is a copy/paste runbook you can drop into your repo (example path: `docs/AWS_GATES_RUNBOOK.md`).
It's written for running the **simulator gates** on an AWS EC2 instance and syncing outputs to **S3**.

## Instance Guide: Simulation vs. Training

> **Rule**: Simulation = CPU cores. ML Training = GPU. Never use a GPU instance for simulation.

| Phase | Right Instance | Wrong Instance |
|-------|---------------|----------------|
| Gate runs (simulation) | c8g.48xlarge (192 ARM cores) | Any `g*` GPU type |
| XGBoost / Transformer training | g5.2xlarge or g6e.2xlarge | c8g (GPU idle, wasteful) |

---

## GPU Instance: ML Training Only

Use a GPU instance **only** after simulation is complete and you have a Gate B/C/D dataset to train on.

| Instance | GPU | VRAM | Spot ~$/hr | Use for |
|----------|-----|------|-----------|---------|
| `g5.2xlarge` | A10G | 24 GB | ~$0.25 | XGBoost + small transformer |
| `g6e.2xlarge` | L40S | 48 GB | ~$0.40 | Large transformer, full training |

### AMI for GPU instances

Search for: `Deep Learning AMI GPU PyTorch` — filter **x86_64**, **Ubuntu 22.04**, owner: Amazon.
Do **not** use the ARM64 variant — GPU instances (`g*`) are x86_64, not ARM.

### One-time GPU instance setup

```bash
# Clone repo
cd /home/ubuntu
git clone git@github.com:forrestmiller34/tft-coach-234.git
cd tft-coach-234

# Python venv + ML deps
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements-ml.txt
pip install pyarrow

# Verify GPU is visible
python3 -c "import torch; print('CUDA:', torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

### Pull data from S3 and train

```bash
source /home/ubuntu/tft-coach-234/.venv/bin/activate
cd /home/ubuntu/tft-coach-234

# Pull Gate B data from S3
aws s3 sync s3://tft-sim-results-forrest/tft-results/gates/gate_b_50k_<DATE>/ results/gate_b/ \
  --region us-east-1

# XGBoost
python -m models.train_xgboost \
  --data results/gate_b/ \
  --task fight \
  --output models/checkpoints/gate_b_xgb

# Transformer (if GPU confirmed)
python -m models.train_transformer \
  --data results/gate_b/ \
  --output models/checkpoints/gate_b_transformer
```

### Deploy key setup (do once per fresh instance)

The GPU instance needs a GitHub deploy key to clone private repos without a PAT.

Generate a key on the instance and add the public key to GitHub repo deploy keys:

```bash
ssh-keygen -t ed25519 -C "tft-coach-gpu" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub
# Copy the output → GitHub repo → Settings → Deploy keys → Add deploy key (read-only)

# Test
ssh -T git@github.com
```

Then clone with SSH instead of HTTPS:

```bash
git clone git@github.com:forrestmiller34/tft-coach-234.git
```

---

## Recommended Instance: c8g.48xlarge (Graviton4 ARM)

| Instance | CPU | Real Cores | vCPUs | $/hr (On-Demand) | Est. Games/Hr | Cost per 1M Games |
|---|---|---|---|---|---|---|
| **c8g.48xlarge** | Graviton4 (ARM) | 192 | 192 (no SMT) | ~$7.66 | ~470K | ~$16.30 |
| c7a.48xlarge | AMD EPYC 9R14 | 192 | 192 (no SMT) | ~$9.85 | ~520K | ~$18.90 |
| c7i.48xlarge | Intel Xeon 8488C | 96 | 192 (SMT) | ~$8.57 | ~340K | ~$25.20 |

The Rust engine compiles natively on ARM (no x86 intrinsics, no cross-compile needed).
All Python deps (pyarrow, numpy, xgboost) have native ARM wheels.
Use **Spot pricing** for ~60-70% off — the simulator is checkpoint-friendly.

### Quick Launch (from local machine)

```bash
# Launch c8g.48xlarge with auto-bootstrap
bash scripts/launch-graviton.sh

# Launch with spot pricing
bash scripts/launch-graviton.sh --spot

# Dry run (preview only)
bash scripts/launch-graviton.sh --dry-run
```

### Run Gates (via SSM, no SSH needed)

```bash
# Single gate
bash scripts/run-gates.sh --instance-id i-xxx --gates a

# Multiple gates
bash scripts/run-gates.sh --instance-id i-xxx --gates a,b,c

# Recovery: skip sim, just train + upload
bash scripts/run-gates.sh --instance-id i-xxx --gates b --skip-sim
```

### AMI

Use Ubuntu 22.04 LTS **arm64** (the launch script finds this automatically).
The IAM role `tft-sim-role` from the original setup works unchanged.

---

## Manual Setup (alternative to launch script)

---

## What this runbook covers

- One-time EC2 setup (Ubuntu-ish)
- Gate runs:
  - Gate A: 1,000 games (smoke)
  - Gate B: 50,000 games (baseline data + optional XGBoost baseline)
  - Gate C: 250,000 games (pre-prod scale)
  - Gate D: 1,000,000 games (production scale)
- Validate outputs after each run
- Upload outputs to S3
- Resume an interrupted run
- Optional: shard a big run across multiple instances

---

## Assumptions (for manual setup below)

- You're running these commands **on the EC2 instance** (via SSM Session Manager or SSH).
- The instance has an IAM role with:
  - **AmazonSSMManagedInstanceCore** (for Session Manager)
  - **S3 write permissions** to your chosen bucket/prefix
- Your repo is accessible from the instance (public GitHub, or via deploy key/other auth).
- If using Graviton4 (ARM): select the **arm64** Ubuntu AMI (not amd64).

---


## Common SSM gotchas (so you don’t rediscover them every run)

- **SSM defaults to `/bin/sh`**. If your command uses `source` or `set -o pipefail`, wrap it: `bash -lc '<command>'`.
- **SSM often runs as `root`**, but your repo + SSH keys live under `ubuntu`. Prefer: `sudo -u ubuntu -H bash -lc '<command>'`.
- **Git "dubious ownership"** happens when files are owned by root but you run git as ubuntu (or vice versa). Fix once with:
  ```bash
  git config --global --add safe.directory /home/ubuntu/tft-coach-234
  ```
  Better fix: don’t mix ownership in the first place.
- **Don’t assume `python` exists**. Use `python3` unless you’ve activated a venv in bash.
- **No secrets in chat**. Never paste a GitHub PAT into SSM commands. Use deploy keys.

---

## 0) Configure your run variables

Edit these once per machine/session:

```bash
# ===== EDIT THESE =====
export AWS_REGION="us-east-1"
export S3_BUCKET="tft-sim-results-YOURNAME"
export S3_PREFIX="tft-results/gates"
export REPO_URL="https://github.com/forrestmiller34/tft-coach-234.git"
export REPO_REF="main"
# ======================

# Where to put everything locally
export WORKDIR="/data/tft"
export OUT_ROOT="$WORKDIR/results"
export CKPT_ROOT="$WORKDIR/models_checkpoints"

# Worker count for simulator multiprocessing (start conservative, then increase)
# On a c8a.48xlarge, nproc is huge—don’t be afraid to start with 32 or 64 and measure.
export WORKERS="${WORKERS:-64}"
```

If you want the box to decide workers automatically:

```bash
export WORKERS="$(nproc)"
```

(That can be aggressive; if you see thrash / slowdowns, reduce it.)

---

## 1) One-time EC2 setup (Ubuntu 22.04 style)

```bash
set -euo pipefail

# Create workspace
sudo mkdir -p "$WORKDIR" "$OUT_ROOT" "$CKPT_ROOT"
sudo chown -R "$USER":"$USER" "$WORKDIR"

cd "$WORKDIR"

# System deps
sudo apt-get update
sudo apt-get install -y \
  git curl ca-certificates \
  python3 python3-venv python3-pip python3-dev \
  build-essential pkg-config libssl-dev \
  awscli

# Rust toolchain (needed to build the rust engine extension)
curl https://sh.rustup.rs -sSf | sh -s -- -y
source "$HOME/.cargo/env"

# Clone repo (or update it)
if [ ! -d "tft-coach-234" ]; then
  git clone --filter=blob:none "$REPO_URL" tft-coach-234
fi

cd tft-coach-234
git fetch --all --tags
git checkout "$REPO_REF"

# Python venv
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip

# Simulator deps (pyarrow for parquet output)
pip install -r requirements-simulator.txt maturin

# (Optional) ML deps (needed if you run train_xgboost on the instance)
pip install -r requirements-ml.txt

# Build Rust extension into this venv (enables --engine rust_full)
cd simulator/core/rust_engine
maturin develop --release
cd "$WORKDIR/tft-coach-234"
```

Sanity-check entrypoints:

```bash
source "$WORKDIR/tft-coach-234/.venv/bin/activate"
cd "$WORKDIR/tft-coach-234"

python -m simulator.cloud_runner --help | head -n 30
python -m simulator.validate_output --help | head -n 30
python -m models.train_xgboost --help | head -n 30
```

---

## 2) Recommended environment knobs (avoid surprise thread explosions)

These are optional but often help on giant CPU boxes:

```bash
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

# If Rayon is used inside Rust, this env var is the standard knob:
export RAYON_NUM_THREADS="$(nproc)"
```

---

## 3) Optional: quick calibration run (10k)

This is a cheap “does it work + what’s throughput?” run before you spend real money.

```bash
source "$WORKDIR/tft-coach-234/.venv/bin/activate"
cd "$WORKDIR/tft-coach-234"

RUN_ID="calib_10k_$(date +%Y%m%d_%H%M%S)"
OUTDIR="$OUT_ROOT/$RUN_ID"

python -m simulator.cloud_runner \
  --engine rust_full \
  --games 10000 \
  --workers "$WORKERS" \
  --output "$OUTDIR" \
  --agent-profile mixed \
  --require-parquet \
  --progress-every 500

python -m simulator.validate_output "$OUTDIR"

aws s3 sync "$OUTDIR" "s3://$S3_BUCKET/$S3_PREFIX/$RUN_ID/" \
  --only-show-errors \
  --region "$AWS_REGION"
```

---

## Gate A — 1k smoke test

Goal: quick stop/go. Make sure it runs, output validates, and Parquet is produced.

```bash
source "$WORKDIR/tft-coach-234/.venv/bin/activate"
cd "$WORKDIR/tft-coach-234"

RUN_ID="gate_a_1k_$(date +%Y%m%d_%H%M%S)"
OUTDIR="$OUT_ROOT/$RUN_ID"

python -m simulator.cloud_runner \
  --engine rust_full \
  --games 1000 \
  --workers "$WORKERS" \
  --output "$OUTDIR" \
  --agent-profile mixed \
  --require-parquet \
  --progress-every 100

python -m simulator.validate_output "$OUTDIR"

aws s3 sync "$OUTDIR" "s3://$S3_BUCKET/$S3_PREFIX/$RUN_ID/" \
  --only-show-errors \
  --region "$AWS_REGION"
```

Optional: tiny XGBoost smoke (not required for Gate A, but good confidence):

```bash
CKPTDIR="$CKPT_ROOT/$RUN_ID"
python -m models.train_xgboost \
  --data "$OUTDIR" \
  --task fight \
  --output "$CKPTDIR"

aws s3 sync "$CKPTDIR" "s3://$S3_BUCKET/$S3_PREFIX/$RUN_ID/xgb/" \
  --only-show-errors \
  --region "$AWS_REGION"
```

---

## Gate B — 50k baseline

Goal: a real baseline dataset + leak-safe baseline training (optional but recommended).

```bash
source "$WORKDIR/tft-coach-234/.venv/bin/activate"
cd "$WORKDIR/tft-coach-234"

RUN_ID="gate_b_50k_$(date +%Y%m%d_%H%M%S)"
OUTDIR="$OUT_ROOT/$RUN_ID"

python -m simulator.cloud_runner \
  --engine rust_full \
  --games 50000 \
  --workers "$WORKERS" \
  --output "$OUTDIR" \
  --agent-profile mixed \
  --require-parquet \
  --progress-every 500

python -m simulator.validate_output "$OUTDIR"

aws s3 sync "$OUTDIR" "s3://$S3_BUCKET/$S3_PREFIX/$RUN_ID/" \
  --only-show-errors \
  --region "$AWS_REGION"
```

Optional: XGBoost baseline in external-memory mode (good for big-ish corpora):

```bash
CKPTDIR="$CKPT_ROOT/$RUN_ID"
python -m models.train_xgboost \
  --data "$OUTDIR" \
  --task fight \
  --output "$CKPTDIR" \
  --external-memory

aws s3 sync "$CKPTDIR" "s3://$S3_BUCKET/$S3_PREFIX/$RUN_ID/xgb/" \
  --only-show-errors \
  --region "$AWS_REGION"
```

---

## Gate C — 250k pre-prod scale

Simple version (single run, mixed profile):

```bash
source "$WORKDIR/tft-coach-234/.venv/bin/activate"
cd "$WORKDIR/tft-coach-234"

RUN_ID="gate_c_250k_$(date +%Y%m%d_%H%M%S)"
OUTDIR="$OUT_ROOT/$RUN_ID"

python -m simulator.cloud_runner \
  --engine rust_full \
  --games 250000 \
  --workers "$WORKERS" \
  --output "$OUTDIR" \
  --agent-profile mixed \
  --require-parquet \
  --progress-every 2000

python -m simulator.validate_output "$OUTDIR"

aws s3 sync "$OUTDIR" "s3://$S3_BUCKET/$S3_PREFIX/$RUN_ID/" \
  --only-show-errors \
  --region "$AWS_REGION"
```

Optional: diversity run (separate directories, then you can train on the parent folder):

```bash
RUN_ID="gate_c_250k_diverse_$(date +%Y%m%d_%H%M%S)"
ROOT="$OUT_ROOT/$RUN_ID"
mkdir -p "$ROOT"

# 150k mixed
python -m simulator.cloud_runner --engine rust_full --games 150000 --workers "$WORKERS" \
  --output "$ROOT/mixed_150k" --agent-profile mixed --require-parquet --progress-every 2000
python -m simulator.validate_output "$ROOT/mixed_150k"

# 75k ladder-ish profile
python -m simulator.cloud_runner --engine rust_full --games 75000 --workers "$WORKERS" \
  --output "$ROOT/ladder_75k" --agent-profile ladder --require-parquet --progress-every 2000
python -m simulator.validate_output "$ROOT/ladder_75k"

# 25k random
python -m simulator.cloud_runner --engine rust_full --games 25000 --workers "$WORKERS" \
  --output "$ROOT/random_25k" --agent-profile random --require-parquet --progress-every 2000
python -m simulator.validate_output "$ROOT/random_25k"

aws s3 sync "$ROOT" "s3://$S3_BUCKET/$S3_PREFIX/$RUN_ID/" --only-show-errors --region "$AWS_REGION"
```

---

## Gate D — 1M production scale

Single-run version (simplest):

```bash
source "$WORKDIR/tft-coach-234/.venv/bin/activate"
cd "$WORKDIR/tft-coach-234"

RUN_ID="gate_d_1m_$(date +%Y%m%d_%H%M%S)"
OUTDIR="$OUT_ROOT/$RUN_ID"

python -m simulator.cloud_runner \
  --engine rust_full \
  --games 1000000 \
  --workers "$WORKERS" \
  --output "$OUTDIR" \
  --agent-profile mixed \
  --require-parquet \
  --progress-every 5000

python -m simulator.validate_output "$OUTDIR"

aws s3 sync "$OUTDIR" "s3://$S3_BUCKET/$S3_PREFIX/$RUN_ID/" \
  --only-show-errors \
  --region "$AWS_REGION"
```

If you want to run **multiple instances** and merge later, use sharding (supported by the simulator CLI):

```bash
# Example: 10 shards, shard 0 (run one shard per instance)
python -m simulator.cloud_runner \
  --engine rust_full \
  --games 1000000 \
  --num-shards 10 \
  --shard-index 0 \
  --workers "$WORKERS" \
  --output "$OUT_ROOT/gate_d_1m_shard00" \
  --agent-profile mixed \
  --require-parquet \
  --progress-every 5000
```

---

## Resume an interrupted run

If the run gets interrupted (spot interruption, reboot, etc.), resume with the same settings and `--resume`.

Example (resume Gate B):

```bash
source "$WORKDIR/tft-coach-234/.venv/bin/activate"
cd "$WORKDIR/tft-coach-234"

# OUTDIR should be the folder that already contains checkpoint.json
python -m simulator.cloud_runner \
  --engine rust_full \
  --games 50000 \
  --workers "$WORKERS" \
  --resume "$OUTDIR" \
  --agent-profile mixed \
  --require-parquet \
  --progress-every 500
```

---

## “Did it work?” checklist

On the instance:

```bash
ls -lah "$OUTDIR"
cat "$OUTDIR/summary.json" | head
cat "$OUTDIR/checkpoint.json" | head
```

In S3:

```bash
aws s3 ls "s3://$S3_BUCKET/$S3_PREFIX/" --region "$AWS_REGION" | tail
```

---

## SSM Timeout Lessons (from Feb 2026 Gate B failure)

**Problem**: Codex put simulation + XGBoost training in a single SSM command with the default 1-hour timeout. Training exceeded the limit and got killed (ResponseCode=137).

**Fix** (implemented in `scripts/run-gates.sh`):
- **Separate SSM commands** for each phase: simulate, validate, train, upload
- **Explicit `executionTimeout`** on every command (generous — better safe than killed)
- **Install `awscli` via pip** into the venv (the apt `awscli` package was missing on the AMI)
- Use `/bin/bash` (not `/bin/sh`) — `set -o pipefail` requires bash

Timeout budget per gate:

| Gate | Sim | Train | Validate | Upload |
|------|-----|-------|----------|--------|
| A (1k) | 5 min | 10 min | 5 min | 5 min |
| B (50k) | 30 min | 1 hr | 5 min | 1 hr |
| C (250k) | 2 hr | 3 hr | 5 min | 1 hr |
| D (1M) | 8 hr | 12 hr | 5 min | 1 hr |

---

## Next improvements

- Add S3 lifecycle rules by prefix (`calib/` 30d, `gates/` 90-180d, `prod/` 6-12mo) to prevent storage creep.
- If you plan to run 1M often, consider sharding across multiple smaller spot instances for better preemption tolerance.
- Add a post-gate ntfy notification from the instance so you don't have to watch the terminal.
