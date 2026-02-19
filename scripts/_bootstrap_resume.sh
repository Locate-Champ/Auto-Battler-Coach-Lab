#!/bin/bash
set -euo pipefail

# SSM runs as root; run all setup as ubuntu
su - ubuntu << 'ASUBUNTU'
set -euo pipefail
cd /home/ubuntu

echo "--- Clone ---"
if [ ! -d "auto-battler-coach-lab" ]; then
  GIT_SSH_COMMAND="ssh -i /home/ubuntu/.ssh/id_ed25519 -o StrictHostKeyChecking=yes" \
    git clone --filter=blob:none git@github.com:<YOUR_ORG>/<YOUR_REPO>.git
fi
cd auto-battler-coach-lab
git checkout main
echo "Repo: OK ($(git rev-parse --short HEAD))"

echo "--- Python venv ---"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -U pip -q
pip install -r requirements-simulator.txt maturin awscli -q
pip install -r requirements-ml.txt -q 2>&1 || echo "WARN: ML deps skipped"
echo "Python deps: OK"

echo "--- Rust engine ---"
source /home/ubuntu/.cargo/env
cd simulator/core/rust_engine
maturin develop --release
cd /home/ubuntu/auto-battler-coach-lab
echo "Rust engine: BUILT"

echo "--- Sanity ---"
python -m simulator.cloud_runner --help > /dev/null && echo "cloud_runner: OK"
echo "nproc: $(nproc)"
echo "Disk: $(df -h /data | tail -1 | awk '{print $4}') free"
echo "=== Bootstrap complete ==="
ASUBUNTU

