#!/bin/bash
set -euo pipefail
cd /home/ubuntu/tft-coach-234
source .venv/bin/activate

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

RUN_ID="gate_a_1k_$(date +%Y%m%d_%H%M%S)"
OUTDIR="/data/tft/results/${RUN_ID}"
mkdir -p "$OUTDIR"

echo "=== Gate A: 1000 games ==="
echo "Start: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Workers: 192, Engine: rust_full"

python -m simulator.cloud_runner \
  --engine rust_full \
  --games 1000 \
  --workers 192 \
  --output "$OUTDIR" \
  --agent-profile mixed \
  --require-parquet \
  --progress-every 100

echo "End: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Output size: $(du -sh "$OUTDIR" | cut -f1)"
echo "$RUN_ID" > /tmp/tft_gate_a_run_id
echo "$OUTDIR" > /tmp/tft_gate_a_outdir
echo "=== Gate A sim done ==="
