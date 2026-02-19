#!/bin/bash
set -euo pipefail
cd /home/ubuntu/auto-battler-coach-lab
source .venv/bin/activate

OUTDIR=$(cat /tmp/coach_gate_b_outdir)
RUN_ID=$(cat /tmp/coach_gate_b_run_id)
CKPTDIR="/data/sim/models_checkpoints/${RUN_ID}"
mkdir -p "$CKPTDIR"

echo "=== Gate B: XGBoost Training ==="
echo "Data: $OUTDIR"
echo "Output: $CKPTDIR"
echo "Start: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

python -m models.train_xgboost \
  --data "$OUTDIR" \
  --task fight \
  --output "$CKPTDIR" \
  --external-memory \
  --external-batch-size 8192

echo "End: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Checkpoint contents:"
ls -lh "$CKPTDIR"/

if [ -f "$CKPTDIR/fight_training_report.json" ]; then
  echo "=== Training Report ==="
  python3 -m json.tool "$CKPTDIR/fight_training_report.json" 2>/dev/null || cat "$CKPTDIR/fight_training_report.json"
fi

echo "$CKPTDIR" > /tmp/coach_gate_b_ckptdir
echo "=== XGBoost done ==="


