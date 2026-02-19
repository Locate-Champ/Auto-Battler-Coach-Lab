#!/bin/bash
set -euo pipefail
cd /home/ubuntu/auto-battler-coach-lab
source .venv/bin/activate

OUTDIR=$(cat /tmp/coach_gate_a_outdir)
RUN_ID=$(cat /tmp/coach_gate_a_run_id)

echo "=== Validate Gate A ==="
python -m simulator.validate_output "$OUTDIR"

echo "=== Upload Gate A to S3 ==="
aws s3 sync "$OUTDIR" "s3://<YOUR_BUCKET>/results/gates/gate_a/${RUN_ID}/" \
  --only-show-errors --region us-east-1

echo "Upload complete."
aws s3 ls "s3://<YOUR_BUCKET>/results/gates/gate_a/${RUN_ID}/" --summarize --region us-east-1 | tail -3
echo "=== Gate A complete ==="


