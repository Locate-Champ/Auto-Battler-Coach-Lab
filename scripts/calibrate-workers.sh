#!/usr/bin/env bash
# calibrate-workers.sh
#
# Runs a worker-count sweep on the remote EC2 instance to find optimal
# throughput. Tests a small batch (500 games) at each worker count and
# reports games/sec for each.
#
# Usage:
#   bash scripts/calibrate-workers.sh --instance-id i-xxx
#   bash scripts/calibrate-workers.sh --instance-id i-xxx --games 1000
#   bash scripts/calibrate-workers.sh --instance-id i-xxx --dry-run

set -euo pipefail

REGION="us-east-1"
INSTANCE_ID=""
GAMES_PER_TEST=500
DRY_RUN=false
TIMEOUT=3600  # 1 hour for the full sweep

while [[ $# -gt 0 ]]; do
  case "$1" in
    --instance-id)   INSTANCE_ID="$2"; shift 2 ;;
    --instance-id=*) INSTANCE_ID="${1#*=}"; shift ;;
    --games)         GAMES_PER_TEST="$2"; shift 2 ;;
    --games=*)       GAMES_PER_TEST="${1#*=}"; shift ;;
    --dry-run)       DRY_RUN=true; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

[ -z "$INSTANCE_ID" ] && { echo "ERROR: --instance-id required" >&2; exit 1; }

log() { echo "[$(date +%H:%M:%S)] $*"; }

log "Running worker calibration on ${INSTANCE_ID} (${GAMES_PER_TEST} games per test)..."

SCRIPT=$(cat <<REMOTESCRIPT
#!/bin/bash
set -euo pipefail
cd /home/ubuntu/auto-battler-coach-lab
source .venv/bin/activate

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

NCPU=\$(nproc)
GAMES=${GAMES_PER_TEST}
OUTBASE="/tmp/coach_calibrate"
rm -rf "\$OUTBASE"

echo "=============================================="
echo "  Simulator Worker Calibration"
echo "  Instance: \$(curl -s http://169.254.169.254/latest/meta-data/instance-type 2>/dev/null || echo 'unknown')"
echo "  CPUs: \$NCPU"
echo "  RAM: \$(free -h | awk '/^Mem:/{print \$2}')"
echo "  Games per test: \$GAMES"
echo "  Engine: rust_full"
echo "=============================================="
echo ""

# Worker counts to test: powers of 2 up to nproc, plus nproc itself
# and some intermediate values around the expected sweet spot
WORKER_COUNTS="1 4 16 32 64 96 128 160 192"

# Filter out counts > nproc
FILTERED=""
for W in \$WORKER_COUNTS; do
  if [ "\$W" -le "\$NCPU" ]; then
    FILTERED="\$FILTERED \$W"
  fi
done
# Always include nproc if not already there
if ! echo "\$FILTERED" | grep -qw "\$NCPU"; then
  FILTERED="\$FILTERED \$NCPU"
fi

echo "Testing worker counts:\$FILTERED"
echo ""

# Results table header
printf "%-10s %-12s %-12s %-15s %-10s\n" "Workers" "Games/sec" "Sec/game" "Total time(s)" "Errors"
printf "%-10s %-12s %-12s %-15s %-10s\n" "-------" "---------" "--------" "-------------" "------"

BEST_RATE=0
BEST_WORKERS=1

for W in \$FILTERED; do
  OUTDIR="\${OUTBASE}/w\${W}"
  mkdir -p "\$OUTDIR"

  START_TIME=\$(date +%s%N)

  python -m simulator.cloud_runner \
    --engine rust_full \
    --games "\$GAMES" \
    --workers "\$W" \
    --output "\$OUTDIR" \
    --agent-profile mixed \
    --require-parquet \
    --progress-every 99999 \
    2>/dev/null

  END_TIME=\$(date +%s%N)
  ELAPSED_NS=\$(( END_TIME - START_TIME ))
  ELAPSED_S=\$(echo "scale=2; \$ELAPSED_NS / 1000000000" | bc)

  # Parse summary for error count
  ERRORS=0
  if [ -f "\$OUTDIR/summary.json" ]; then
    ERRORS=\$(python3 -c "import json; d=json.load(open('\$OUTDIR/summary.json')); print(d.get('errors',0))" 2>/dev/null || echo "?")
  fi

  RATE=\$(echo "scale=2; \$GAMES / \$ELAPSED_S" | bc)
  PER_GAME=\$(echo "scale=4; \$ELAPSED_S / \$GAMES" | bc)

  printf "%-10s %-12s %-12s %-15s %-10s\n" "\$W" "\$RATE" "\$PER_GAME" "\$ELAPSED_S" "\$ERRORS"

  # Track best
  IS_BETTER=\$(echo "\$RATE > \$BEST_RATE" | bc)
  if [ "\$IS_BETTER" -eq 1 ]; then
    BEST_RATE="\$RATE"
    BEST_WORKERS="\$W"
  fi

  # Clean up to save disk
  rm -rf "\$OUTDIR"
done

echo ""
echo "=============================================="
echo "  BEST: \$BEST_WORKERS workers @ \$BEST_RATE games/sec"
echo "=============================================="
echo ""

# Projected times at best rate
echo "Projected run times at \$BEST_RATE games/sec:"
for LABEL_GAMES in "Gate_A:1000" "Gate_B:50000" "Gate_C:250000" "Gate_D:1000000"; do
  LABEL=\$(echo "\$LABEL_GAMES" | cut -d: -f1)
  G=\$(echo "\$LABEL_GAMES" | cut -d: -f2)
  SECS=\$(echo "scale=0; \$G / \$BEST_RATE" | bc)
  MINS=\$(echo "scale=1; \$SECS / 60" | bc)
  printf "  %-10s %8s games -> %6s sec (%s min)\n" "\$LABEL" "\$G" "\$SECS" "\$MINS"
done

echo ""
echo "Recommended --workers flag: \$BEST_WORKERS"
echo ""

# Memory snapshot at peak
echo "Current memory usage:"
free -h
REMOTESCRIPT
)

if [ "$DRY_RUN" = true ]; then
  log "(dry-run) Would run calibration sweep on ${INSTANCE_ID}"
  echo "$SCRIPT" | head -20
  echo "  ..."
  exit 0
fi

# Check SSM is online
SSM_STATUS=$(aws ssm describe-instance-information --region "$REGION" \
  --filters "Key=InstanceIds,Values=${INSTANCE_ID}" \
  --query 'InstanceInformationList[0].PingStatus' --output text 2>/dev/null || echo "None")
if [ "$SSM_STATUS" != "Online" ]; then
  echo "ERROR: Instance ${INSTANCE_ID} SSM is '${SSM_STATUS}'. Is it running?" >&2
  exit 1
fi

log "Sending calibration to instance..."
COMMAND_ID=$(aws ssm send-command \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION" \
  --document-name "AWS-RunShellScript" \
  --parameters "{\"commands\":[$(echo "$SCRIPT" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")],\"executionTimeout\":[\"${TIMEOUT}\"],\"workingDirectory\":[\"/home/ubuntu\"]}" \
  --timeout-seconds 600 \
  --query 'Command.CommandId' --output text)

log "Command: ${COMMAND_ID}"
log "This will take 10-20 minutes. Polling..."

while true; do
  STATUS=$(aws ssm get-command-invocation \
    --command-id "$COMMAND_ID" \
    --instance-id "$INSTANCE_ID" \
    --region "$REGION" \
    --query 'Status' --output text 2>/dev/null || echo "Pending")

  case "$STATUS" in
    Success)
      log "Calibration complete!"
      echo ""
      aws ssm get-command-invocation \
        --command-id "$COMMAND_ID" \
        --instance-id "$INSTANCE_ID" \
        --region "$REGION" \
        --query 'StandardOutputContent' --output text 2>/dev/null
      exit 0
      ;;
    Failed|TimedOut|Cancelled)
      log "Calibration ${STATUS}!"
      aws ssm get-command-invocation \
        --command-id "$COMMAND_ID" \
        --instance-id "$INSTANCE_ID" \
        --region "$REGION" \
        --query 'StandardErrorContent' --output text 2>/dev/null | tail -20
      exit 1
      ;;
    *)
      sleep 15
      ;;
  esac
done

