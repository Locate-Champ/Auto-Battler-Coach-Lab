#!/bin/bash
set -euo pipefail
cd /home/ubuntu/auto-battler-coach-lab
source .venv/bin/activate

OUTDIR=$(cat /tmp/coach_gate_b_outdir)
echo "=== Validate Gate B ==="
python -m simulator.validate_output "$OUTDIR"
echo "=== Validation done ==="


