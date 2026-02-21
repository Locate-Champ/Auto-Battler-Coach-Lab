"""Build SSM command JSON for XGBoost training - nohup detached version.

The previous attempt timed out because SSM has a 3600s limit and feature
vectorization alone took ~56 minutes. This version writes a self-contained
training script to the instance and runs it via nohup so it survives any
SSM timeout.
"""
import json
import pathlib

RUN_ID = "run50k-20260220-064051"
S3_MODELS = f"s3://tft-sim-results-forrest/tft-results/models/{RUN_ID}"

# The repo is already cloned, bundle applied, pip deps installed, sim data
# downloaded from the previous (timed-out) run. We just need to re-run the
# XGBoost training.

# Build SSM commands that write a wrapper script and nohup it
commands = [
    "#!/bin/bash",
    "set -euo pipefail",
    "",
    "# Write training wrapper script to disk",
    "cat > /tmp/run-xgb-training.sh << 'WRAPPER_EOF'",
    "#!/bin/bash",
    "set -euo pipefail",
    "exec > /tmp/xgb-training-v2.log 2>&1",
    'echo "=== XGBoost training started at $(date -u) ==="',
    "",
    "# Activate DLAMI PyTorch env",
    'export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"',
    "source /opt/pytorch/bin/activate",
    'echo "Python: $(python3 --version)"',
    "",
    "cd /home/ubuntu/Auto-Battler-Coach-Lab",
    "",
    'echo "=== Starting XGBoost fight training ==="',
    'echo "Start time: $(date -u)"',
    f'OUTPUT_DIR="models/checkpoints/{RUN_ID}/xgb_fight"',
    'rm -rf "${OUTPUT_DIR}/.xgb_cache_fight" 2>/dev/null || true',
    'mkdir -p "${OUTPUT_DIR}"',
    "python3 -m models.train_xgboost \\",
    f"  --data results/{RUN_ID} \\",
    "  --task fight \\",
    '  --output "${OUTPUT_DIR}" \\',
    "  --external-memory \\",
    "  --n-estimators 300 \\",
    "  --early-stopping-rounds 50",
    'echo "=== XGBoost fight training complete ==="',
    'echo "End time: $(date -u)"',
    "",
    'echo "Uploading model artifacts to S3..."',
    f'aws s3 sync "${{OUTPUT_DIR}}" {S3_MODELS}/xgb_fight/ --exclude ".xgb_cache_*" --only-show-errors',
    'echo "Upload complete."',
    'echo "=== All done at $(date -u) ==="',
    "",
    "# Signal completion",
    "touch /tmp/xgb-training-DONE",
    "WRAPPER_EOF",
    "chmod +x /tmp/run-xgb-training.sh",
    "",
    "# Remove old completion signal",
    "rm -f /tmp/xgb-training-DONE",
    "",
    "# Launch detached (survives SSM timeout)",
    "nohup /tmp/run-xgb-training.sh &",
    "BGPID=$!",
    'echo "Training launched as PID ${BGPID}"',
    'echo "Monitor: tail -f /tmp/xgb-training-v2.log"',
    'echo "Check completion: test -f /tmp/xgb-training-DONE && echo DONE || echo RUNNING"',
]

params = {"commands": commands}
out_path = str(pathlib.Path(__file__).parent / "ssm-xgb-params.json")
with open(out_path, "w") as f:
    json.dump(params, f)

print(f"Wrote {len(commands)} commands to {out_path}")
for c in commands:
    short = c[:90]
    print(f"  {short}")
