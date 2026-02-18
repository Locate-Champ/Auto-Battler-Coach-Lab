#!/bin/bash
set -euo pipefail
cd /home/ubuntu/tft-coach-234
source .venv/bin/activate

OUTDIR=$(cat /tmp/tft_gate_a_outdir)
RUN_ID=$(cat /tmp/tft_gate_a_run_id)

echo "=== Validate Gate A ==="
python -m simulator.validate_output "$OUTDIR"

echo "=== Upload Gate A to S3 ==="
aws s3 sync "$OUTDIR" "s3://tft-sim-results-forrest/tft-results/gates/gate_a/${RUN_ID}/" \
  --only-show-errors --region us-east-1

echo "Upload complete."
aws s3 ls "s3://tft-sim-results-forrest/tft-results/gates/gate_a/${RUN_ID}/" --summarize --region us-east-1 | tail -3
echo "=== Gate A complete ==="
