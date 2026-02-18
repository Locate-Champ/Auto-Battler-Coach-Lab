#!/usr/bin/env bash
# run-gates.sh
#
# Runs TFT simulator gates on a remote EC2 instance via SSM.
# Each phase (sim, validate, train, upload) is a SEPARATE SSM command
# with its own timeout — the key lesson from the Codex timeout failure.
#
# Usage:
#   bash scripts/run-gates.sh --instance-id i-xxx --gates a
#   bash scripts/run-gates.sh --instance-id i-xxx --gates a,b
#   bash scripts/run-gates.sh --instance-id i-xxx --gates b --skip-sim   # train+upload only (recovery)
#   bash scripts/run-gates.sh --instance-id i-xxx --gates b,c --dry-run
#   bash scripts/run-gates.sh --instance-id i-xxx --gates b --workers 128
#
# Gate definitions (measured on c8g.48xlarge @ 192 workers, ~343 games/sec):
#   a = 1,000 games   (smoke test, ~3 sec sim)
#   b = 50,000 games  (baseline + XGBoost, ~3 min sim + training)
#   c = 250,000 games (pre-prod, ~14 min sim + training)
#   d = 1,000,000 games (production, ~56 min sim + training)

set -euo pipefail

# ── CONFIG ──────────────────────────────────────────────────────────────────
REGION="us-east-1"
S3_BUCKET="tft-sim-results-forrest"
S3_PREFIX="tft-results/gates"

# Defaults (can be overridden with flags)
INSTANCE_ID=""
GATES=""
WORKERS=192       # Calibrated optimal for c8g.48xlarge (nproc unreliable in SSM)
DRY_RUN=false
SKIP_SIM=false    # set to skip simulation (recovery: train+upload only)
ENGINE="rust_full"
AGENT_PROFILE="mixed"
SKIP_TRAIN=false  # set to skip XGBoost training
# ────────────────────────────────────────────────────────────────────────────

# Timeouts per phase (seconds)
# These are generous — better to be safe than hit TimedOut again
declare -A SIM_TIMEOUT=( [a]=300 [b]=1800 [c]=7200 [d]=28800 )
declare -A TRAIN_TIMEOUT=( [a]=600 [b]=3600 [c]=10800 [d]=43200 )
VALIDATE_TIMEOUT=300
UPLOAD_TIMEOUT=3600

# Game counts per gate
declare -A GAME_COUNT=( [a]=1000 [b]=50000 [c]=250000 [d]=1000000 )
declare -A PROGRESS_EVERY=( [a]=100 [b]=500 [c]=2000 [d]=5000 )

# ── Parse args ───────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --instance-id)   INSTANCE_ID="$2"; shift 2 ;;
    --instance-id=*) INSTANCE_ID="${1#*=}"; shift ;;
    --gates)         GATES="$2"; shift 2 ;;
    --gates=*)       GATES="${1#*=}"; shift ;;
    --workers)       WORKERS="$2"; shift 2 ;;
    --workers=*)     WORKERS="${1#*=}"; shift ;;
    --dry-run)       DRY_RUN=true; shift ;;
    --skip-sim)      SKIP_SIM=true; shift ;;
    --skip-train)    SKIP_TRAIN=true; shift ;;
    --engine=*)      ENGINE="${1#*=}"; shift ;;
    --agent-profile=*) AGENT_PROFILE="${1#*=}"; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

[ -z "$INSTANCE_ID" ] && { echo "ERROR: --instance-id required" >&2; exit 1; }
[ -z "$GATES" ] && { echo "ERROR: --gates required (e.g. --gates a,b)" >&2; exit 1; }

log() { echo "[$(date +%H:%M:%S)] $*"; }
die() { echo "[ERROR] $*" >&2; exit 1; }

# Windows-compatible python3 resolver
PYTHON3=$(command -v python3 2>/dev/null || command -v py 2>/dev/null || echo "")
[ -z "$PYTHON3" ] && die "python3 (or py) not found on PATH"
# If using 'py' launcher, pass -3 flag
[[ "$PYTHON3" == *"py"* && "$PYTHON3" != *"python"* ]] && PYTHON3="$PYTHON3 -3"

# ── SSM command runner ───────────────────────────────────────────────────────
# Sends a shell script to the instance, waits for completion, prints output.
ssm_run() {
  local LABEL="$1"
  local TIMEOUT="$2"
  local SCRIPT="$3"

  log "── ${LABEL} (timeout: ${TIMEOUT}s) ──"

  if [ "$DRY_RUN" = true ]; then
    log "(dry-run) Would send to ${INSTANCE_ID}:"
    echo "$SCRIPT" | head -30
    [ "$(echo "$SCRIPT" | wc -l)" -gt 30 ] && echo "  ... (truncated)"
    return 0
  fi

  COMMAND_ID=$(aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --region "$REGION" \
    --document-name "AWS-RunShellScript" \
    --parameters "{\"commands\":[$(echo "$SCRIPT" | $PYTHON3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")],\"executionTimeout\":[\"${TIMEOUT}\"],\"workingDirectory\":[\"/home/ubuntu\"]}" \
    --timeout-seconds 600 \
    --query 'Command.CommandId' --output text)

  log "SSM Command: ${COMMAND_ID}"

  local LAST_STATUS=""
  while true; do
    STATUS=$(aws ssm get-command-invocation \
      --command-id "$COMMAND_ID" \
      --instance-id "$INSTANCE_ID" \
      --region "$REGION" \
      --query 'Status' --output text 2>/dev/null || echo "Pending")

    # Only log status changes
    if [ "$STATUS" != "$LAST_STATUS" ]; then
      log "Status: ${STATUS}"
      LAST_STATUS="$STATUS"
    fi

    case "$STATUS" in
      Success)
        aws ssm get-command-invocation \
          --command-id "$COMMAND_ID" \
          --instance-id "$INSTANCE_ID" \
          --region "$REGION" \
          --query 'StandardOutputContent' --output text 2>/dev/null | tail -60
        return 0
        ;;
      Failed|TimedOut|Cancelled)
        log "STDERR:"
        aws ssm get-command-invocation \
          --command-id "$COMMAND_ID" \
          --instance-id "$INSTANCE_ID" \
          --region "$REGION" \
          --query 'StandardErrorContent' --output text 2>/dev/null | tail -30
        die "SSM command '${LABEL}' ended with status: ${STATUS}"
        ;;
      *)
        sleep 15
        ;;
    esac
  done
}

# ── Verify instance is ready ────────────────────────────────────────────────
log "Checking SSM connectivity for ${INSTANCE_ID}..."
if [ "$DRY_RUN" = false ]; then
  SSM_STATUS=$(aws ssm describe-instance-information --region "$REGION" \
    --filters "Key=InstanceIds,Values=${INSTANCE_ID}" \
    --query 'InstanceInformationList[0].PingStatus' --output text 2>/dev/null || echo "None")
  if [ "$SSM_STATUS" != "Online" ]; then
    die "Instance ${INSTANCE_ID} SSM status is '${SSM_STATUS}', not 'Online'. Is it running?"
  fi
  log "SSM: Online"
fi

# ── Verify bootstrap completed ──────────────────────────────────────────────
ssm_run "Check bootstrap" 120 "$(cat <<'SCRIPT'
#!/bin/bash
set -euo pipefail
cd /home/ubuntu/tft-coach-234
source .venv/bin/activate

echo "Python: $(python3 --version)"
echo "Rust: $(rustc --version 2>/dev/null || echo 'not found')"
echo "AWS CLI: $(aws --version 2>/dev/null || echo 'not found')"

python -c "from simulator.core.rust_engine import rust_combat_engine; print('Rust engine: OK')" 2>/dev/null \
  || echo "Rust engine: MISSING (will use Python engine)"

python -m simulator.cloud_runner --help > /dev/null 2>&1 \
  && echo "cloud_runner: OK" \
  || echo "cloud_runner: BROKEN"

echo "Disk free: $(df -h /data | tail -1 | awk '{print $4}')"
echo "CPUs: $(nproc)"
echo "Bootstrap check: PASS"
SCRIPT
)"

# ── Worker count setup ───────────────────────────────────────────────────────
WORKER_ARG="--workers ${WORKERS}"

# ── Run each gate ────────────────────────────────────────────────────────────
IFS=',' read -ra GATE_LIST <<< "$GATES"

for GATE in "${GATE_LIST[@]}"; do
  GATE=$(echo "$GATE" | tr -d ' ')  # trim whitespace

  if [ -z "${GAME_COUNT[$GATE]+x}" ]; then
    die "Unknown gate: '${GATE}'. Valid: a, b, c, d"
  fi

  GAMES="${GAME_COUNT[$GATE]}"
  PROGRESS="${PROGRESS_EVERY[$GATE]}"

  log ""
  log "═══════════════════════════════════════════════════════════"
  log "  GATE ${GATE^^}: ${GAMES} games"
  log "═══════════════════════════════════════════════════════════"

  RUN_ID="gate_${GATE}_${GAMES}_\$(date +%Y%m%d_%H%M%S)"

  # ── Phase 1: Simulate ──────────────────────────────────────────────
  if [ "$SKIP_SIM" = false ]; then
    ssm_run "Gate ${GATE^^} — Simulate ${GAMES} games" "${SIM_TIMEOUT[$GATE]}" "$(cat <<SCRIPT
#!/bin/bash
set -euo pipefail
cd /home/ubuntu/tft-coach-234
source .venv/bin/activate

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

RUN_ID="${RUN_ID}"
OUTDIR="/data/tft/results/\${RUN_ID}"
mkdir -p "\$OUTDIR"

echo "=== Gate ${GATE^^}: Simulating ${GAMES} games ==="
echo "Output: \$OUTDIR"
echo "Workers: ${WORKERS}"
echo "Engine: ${ENGINE}"
echo "Start: \$(date -u +%Y-%m-%dT%H:%M:%SZ)"

python -m simulator.cloud_runner \\
  --engine ${ENGINE} \\
  --games ${GAMES} \\
  ${WORKER_ARG} \\
  --output "\$OUTDIR" \\
  --agent-profile ${AGENT_PROFILE} \\
  --require-parquet \\
  --progress-every ${PROGRESS}

echo ""
echo "End: \$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Output size: \$(du -sh "\$OUTDIR" | cut -f1)"

# Save the RUN_ID for subsequent phases
echo "\$RUN_ID" > /tmp/tft_current_run_id
echo "\$OUTDIR" > /tmp/tft_current_outdir
SCRIPT
)"
  else
    log "Skipping simulation (--skip-sim). Finding existing data..."
    ssm_run "Gate ${GATE^^} — Find existing data" 120 "$(cat <<SCRIPT
#!/bin/bash
set -euo pipefail
# Find the most recent gate_${GATE} directory
LATEST=\$(ls -dt /data/tft/results/gate_${GATE}_* 2>/dev/null | head -1)
if [ -z "\$LATEST" ]; then
  echo "ERROR: No existing gate_${GATE} data found in /data/tft/results/"
  ls /data/tft/results/ 2>/dev/null || echo "(empty)"
  exit 1
fi
echo "Using existing data: \$LATEST"
echo "\$(basename "\$LATEST")" > /tmp/tft_current_run_id
echo "\$LATEST" > /tmp/tft_current_outdir
ls -lh "\$LATEST"/*.parquet 2>/dev/null | wc -l | xargs -I{} echo "Parquet chunks: {}"
SCRIPT
)"
  fi

  # ── Phase 2: Validate ─────────────────────────────────────────────
  ssm_run "Gate ${GATE^^} — Validate output" "$VALIDATE_TIMEOUT" "$(cat <<'SCRIPT'
#!/bin/bash
set -euo pipefail
cd /home/ubuntu/tft-coach-234
source .venv/bin/activate

OUTDIR=$(cat /tmp/tft_current_outdir)
echo "Validating: $OUTDIR"
python -m simulator.validate_output "$OUTDIR"
SCRIPT
)"

  # ── Phase 3: XGBoost training ──────────────────────────────────────
  if [ "$SKIP_TRAIN" = false ]; then
    TRAIN_CMD="python -m models.train_xgboost --data \"\$OUTDIR\" --task fight --output \"\$CKPTDIR\""
    # Use external memory for Gate B and above
    if [ "$GATE" != "a" ]; then
      TRAIN_CMD="${TRAIN_CMD} --external-memory --external-batch-size 8192"
    fi

    ssm_run "Gate ${GATE^^} — XGBoost training (fight)" "${TRAIN_TIMEOUT[$GATE]}" "$(cat <<SCRIPT
#!/bin/bash
set -euo pipefail
cd /home/ubuntu/tft-coach-234
source .venv/bin/activate

OUTDIR=\$(cat /tmp/tft_current_outdir)
RUN_ID=\$(cat /tmp/tft_current_run_id)
CKPTDIR="/data/tft/models_checkpoints/\${RUN_ID}"
mkdir -p "\$CKPTDIR"

echo "=== Gate ${GATE^^}: XGBoost Training ==="
echo "Data: \$OUTDIR"
echo "Checkpoints: \$CKPTDIR"
echo "Start: \$(date -u +%Y-%m-%dT%H:%M:%SZ)"

${TRAIN_CMD}

echo ""
echo "End: \$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Checkpoint contents:"
ls -lh "\$CKPTDIR"/

if [ -f "\$CKPTDIR/fight_training_report.json" ]; then
  echo ""
  echo "=== Training Report ==="
  python3 -m json.tool "\$CKPTDIR/fight_training_report.json" 2>/dev/null \\
    || cat "\$CKPTDIR/fight_training_report.json"
fi

# Save checkpoint dir for upload
echo "\$CKPTDIR" > /tmp/tft_current_ckptdir
SCRIPT
)"
  else
    log "Skipping XGBoost training (--skip-train)."
  fi

  # ── Phase 4: Upload to S3 ─────────────────────────────────────────
  ssm_run "Gate ${GATE^^} — Upload to S3" "$UPLOAD_TIMEOUT" "$(cat <<SCRIPT
#!/bin/bash
set -euo pipefail
cd /home/ubuntu/tft-coach-234
source .venv/bin/activate

OUTDIR=\$(cat /tmp/tft_current_outdir)
RUN_ID=\$(cat /tmp/tft_current_run_id)
S3_DEST="s3://${S3_BUCKET}/${S3_PREFIX}/gate_${GATE}/\${RUN_ID}/"

echo "Uploading simulation data to \${S3_DEST}..."
aws s3 sync "\$OUTDIR" "\${S3_DEST}" \\
  --exclude "*.xgb_cache_*" \\
  --only-show-errors \\
  --region ${REGION}

# Upload XGBoost checkpoints if they exist
if [ -f /tmp/tft_current_ckptdir ]; then
  CKPTDIR=\$(cat /tmp/tft_current_ckptdir)
  if [ -d "\$CKPTDIR" ]; then
    echo "Uploading XGBoost checkpoints..."
    aws s3 sync "\$CKPTDIR" "\${S3_DEST}xgb/" \\
      --only-show-errors \\
      --region ${REGION}
  fi
fi

echo ""
echo "Upload complete. S3 contents:"
aws s3 ls "\${S3_DEST}" --region ${REGION} --summarize 2>/dev/null | tail -5
SCRIPT
)"

  log ""
  log "Gate ${GATE^^} complete."
done

# ── Summary ──────────────────────────────────────────────────────────────────
log ""
log "═══════════════════════════════════════════════════════════"
log "  All gates complete: ${GATES}"
log "  S3: s3://${S3_BUCKET}/${S3_PREFIX}/"
log "═══════════════════════════════════════════════════════════"
log ""
log "Remember to stop the instance when done:"
log "  aws ec2 stop-instances --instance-ids ${INSTANCE_ID} --region ${REGION}"
