#!/usr/bin/env bash
# recover-gate-b.sh
#
# Recovery script for Gate B: starts the EC2 instance, runs XGBoost training
# on the existing 50k simulation data, uploads results to S3, then stops
# the instance.
#
# Run from your local machine (requires aws cli configured with us-east-1).
#
# Usage:
#   bash scripts/recover-gate-b.sh              # full run (train + upload + stop)
#   bash scripts/recover-gate-b.sh --dry-run    # print commands without executing
#   bash scripts/recover-gate-b.sh --no-stop    # leave instance running after upload

set -euo pipefail

# â”€â”€ CONFIG â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
INSTANCE_ID="i-0851c860800286e7c"
REGION="us-east-1"
S3_BUCKET="<YOUR_BUCKET>"
S3_PREFIX="results/gates/gate_b"

# Path on the EC2 instance where the 50k sim data lives
REMOTE_DATA_DIR="/data/sim/results/gate_b_50k_20260217_2056"
REMOTE_REPO="/home/ubuntu/auto-battler-coach-lab"
REMOTE_VENV="${REMOTE_REPO}/.venv"

# SSM timeouts (seconds) - generous to avoid the timeout that killed Codex's run
VERIFY_TIMEOUT=120        # 2 min to check data exists
TRAIN_TIMEOUT=10800       # 3 hours for XGBoost training
UPLOAD_TIMEOUT=1800       # 30 min for S3 upload
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

DRY_RUN=false
NO_STOP=false
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --no-stop) NO_STOP=true ;;
  esac
done

log() { echo "[$(date +%H:%M:%S)] $*"; }
die() { echo "[ERROR] $*" >&2; exit 1; }

# â”€â”€ STEP 0: Start the instance and wait for SSM â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
log "Starting instance ${INSTANCE_ID}..."
if [ "$DRY_RUN" = true ]; then
  log "(dry-run) aws ec2 start-instances --instance-ids ${INSTANCE_ID}"
else
  STATE=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --region "$REGION" \
    --query 'Reservations[0].Instances[0].State.Name' --output text)
  if [ "$STATE" = "running" ]; then
    log "Instance already running."
  else
    aws ec2 start-instances --instance-ids "$INSTANCE_ID" --region "$REGION" --output text > /dev/null
    log "Waiting for instance to reach 'running' state..."
    aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --region "$REGION"
  fi

  log "Waiting for SSM agent to come online (up to 3 min)..."
  for i in $(seq 1 18); do
    SSM_STATUS=$(aws ssm describe-instance-information --region "$REGION" \
      --filters "Key=InstanceIds,Values=${INSTANCE_ID}" \
      --query 'InstanceInformationList[0].PingStatus' --output text 2>/dev/null || echo "None")
    if [ "$SSM_STATUS" = "Online" ]; then
      log "SSM agent is online."
      break
    fi
    if [ "$i" -eq 18 ]; then
      die "SSM agent did not come online within 3 minutes."
    fi
    sleep 10
  done
fi

# Helper: send an SSM command, wait for it, print output
ssm_run() {
  local LABEL="$1"
  local TIMEOUT="$2"
  local SCRIPT="$3"

  log "â”€â”€ ${LABEL} (timeout: ${TIMEOUT}s) â”€â”€"

  if [ "$DRY_RUN" = true ]; then
    log "(dry-run) Would execute on instance:"
    echo "$SCRIPT"
    return 0
  fi

  COMMAND_ID=$(aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --region "$REGION" \
    --document-name "AWS-RunShellScript" \
    --parameters "{\"commands\":[$(echo "$SCRIPT" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")],\"executionTimeout\":[\"${TIMEOUT}\"],\"workingDirectory\":[\"/home/ubuntu\"]}" \
    --timeout-seconds 600 \
    --query 'Command.CommandId' --output text)

  log "Command ID: ${COMMAND_ID}"
  log "Waiting for completion..."

  # Poll until done (SSM wait-for doesn't exist, so we poll)
  while true; do
    STATUS=$(aws ssm get-command-invocation \
      --command-id "$COMMAND_ID" \
      --instance-id "$INSTANCE_ID" \
      --region "$REGION" \
      --query 'Status' --output text 2>/dev/null || echo "Pending")

    case "$STATUS" in
      Success)
        log "Command succeeded."
        # Print stdout (truncated)
        aws ssm get-command-invocation \
          --command-id "$COMMAND_ID" \
          --instance-id "$INSTANCE_ID" \
          --region "$REGION" \
          --query 'StandardOutputContent' --output text 2>/dev/null | tail -50
        return 0
        ;;
      Failed|TimedOut|Cancelled)
        log "Command ${STATUS}!"
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

# â”€â”€ STEP 1: Verify Gate B data exists on disk â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
ssm_run "Verify Gate B data" "$VERIFY_TIMEOUT" "$(cat <<'REMOTESCRIPT'
#!/bin/bash
set -euo pipefail

DATA_DIR="/data/sim/results/gate_b_50k_20260217_2056"

if [ ! -d "$DATA_DIR" ]; then
  echo "ERROR: Data directory not found: $DATA_DIR"
  exit 1
fi

CHUNK_COUNT=$(ls "$DATA_DIR"/*.parquet 2>/dev/null | wc -l)
echo "Found ${CHUNK_COUNT} parquet chunks in ${DATA_DIR}"

if [ "$CHUNK_COUNT" -lt 1 ]; then
  echo "ERROR: No parquet files found!"
  exit 1
fi

if [ -f "$DATA_DIR/summary.json" ]; then
  echo "summary.json present:"
  cat "$DATA_DIR/summary.json" | python3 -m json.tool 2>/dev/null || cat "$DATA_DIR/summary.json"
else
  echo "WARNING: No summary.json found (non-fatal)"
fi

du -sh "$DATA_DIR"
echo "Data verification: OK"
REMOTESCRIPT
)"

# â”€â”€ STEP 2: Run XGBoost training (fight task, external memory) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
ssm_run "XGBoost training (fight)" "$TRAIN_TIMEOUT" "$(cat <<'REMOTESCRIPT'
#!/bin/bash
set -euo pipefail

DATA_DIR="/data/sim/results/gate_b_50k_20260217_2056"
REPO="/home/ubuntu/auto-battler-coach-lab"
CKPT_DIR="${DATA_DIR}/xgb_checkpoints"

cd "$REPO"
source .venv/bin/activate

mkdir -p "$CKPT_DIR"

echo "Starting XGBoost training (fight task, external memory)..."
echo "Data: ${DATA_DIR}"
echo "Output: ${CKPT_DIR}"
echo "Time: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

python -m models.train_xgboost \
  --data "$DATA_DIR" \
  --task fight \
  --output "$CKPT_DIR" \
  --external-memory \
  --external-batch-size 8192

echo ""
echo "Training complete at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Checkpoint contents:"
ls -lh "$CKPT_DIR"/

# Print the training report if it was generated
if [ -f "$CKPT_DIR/fight_training_report.json" ]; then
  echo ""
  echo "=== Training Report ==="
  python3 -m json.tool "$CKPT_DIR/fight_training_report.json" 2>/dev/null \
    || cat "$CKPT_DIR/fight_training_report.json"
fi
REMOTESCRIPT
)"

# â”€â”€ STEP 3: Upload everything to S3 â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
RUN_NAME="gate_b_50k_20260217_2056"
S3_DEST="s3://${S3_BUCKET}/${S3_PREFIX}/${RUN_NAME}/"

ssm_run "Upload to S3" "$UPLOAD_TIMEOUT" "$(cat <<REMOTESCRIPT
#!/bin/bash
set -euo pipefail

DATA_DIR="/data/sim/results/gate_b_50k_20260217_2056"
REPO="/home/ubuntu/auto-battler-coach-lab"
S3_DEST="${S3_DEST}"

cd "\$REPO"
source .venv/bin/activate

echo "Uploading to \${S3_DEST}..."

# Upload sim data (parquet chunks + summary)
aws s3 sync "\$DATA_DIR" "\${S3_DEST}" \
  --exclude "*.xgb_cache_*" \
  --only-show-errors

echo "Upload complete."
echo "Verifying S3 contents..."
aws s3 ls "\${S3_DEST}" --summarize | tail -5
REMOTESCRIPT
)"

# â”€â”€ STEP 4: Stop instance (unless --no-stop) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if [ "$NO_STOP" = true ]; then
  log "Skipping instance stop (--no-stop flag set)."
  log "Remember to stop it manually when done!"
else
  log "Stopping instance ${INSTANCE_ID}..."
  if [ "$DRY_RUN" = true ]; then
    log "(dry-run) aws ec2 stop-instances --instance-ids ${INSTANCE_ID}"
  else
    aws ec2 stop-instances --instance-ids "$INSTANCE_ID" --region "$REGION" --output text > /dev/null
    log "Instance stop initiated."
  fi
fi

log ""
log "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"
log "  Gate B Recovery Complete"
log "  S3: ${S3_DEST}"
log "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"

