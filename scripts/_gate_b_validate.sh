#!/bin/bash
set -euo pipefail
cd /home/ubuntu/tft-coach-234
source .venv/bin/activate

OUTDIR=$(cat /tmp/tft_gate_b_outdir)
echo "=== Validate Gate B ==="
python -m simulator.validate_output "$OUTDIR"
echo "=== Validation done ==="
