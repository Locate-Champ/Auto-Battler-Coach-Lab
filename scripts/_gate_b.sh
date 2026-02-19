#!/bin/bash
set -euo pipefail
cd /home/ubuntu/auto-battler-coach-lab
source .venv/bin/activate

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

RUN_ID="gate_b_50k_$(date +%Y%m%d_%H%M%S)"
OUTDIR="/data/sim/results/${RUN_ID}"
mkdir -p "$OUTDIR"

echo "=== Gate B: 50000 games ==="
echo "Start: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Workers: 192, Engine: rust_full"

python -m simulator.cloud_runner \
  --engine rust_full \
  --games 50000 \
  --workers 192 \
  --output "$OUTDIR" \
  --agent-profile mixed \
  --require-parquet \
  --progress-every 500

echo "End: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Output size: $(du -sh "$OUTDIR" | cut -f1)"
echo "$RUN_ID" > /tmp/coach_gate_b_run_id
echo "$OUTDIR" > /tmp/coach_gate_b_outdir
echo "=== Gate B sim done ==="


