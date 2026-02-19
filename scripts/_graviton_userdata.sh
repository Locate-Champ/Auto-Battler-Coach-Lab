#!/bin/bash
set -euo pipefail
exec > >(tee -a /var/log/coach-bootstrap.log) 2>&1
echo "=== Simulator Bootstrap started at $(date -u) ==="

export DEBIAN_FRONTEND=noninteractive

apt-get update -q
apt-get install -y -q git curl ca-certificates python3 python3-venv python3-pip python3-dev build-essential pkg-config libssl-dev

mkdir -p /data/sim/results /data/sim/models_checkpoints
chown -R ubuntu:ubuntu /data/sim

# Install deploy key for private repo
mkdir -p /home/ubuntu/.ssh
echo "DEPLOY_KEY_PLACEHOLDER" | base64 -d > /home/ubuntu/.ssh/id_ed25519
chmod 600 /home/ubuntu/.ssh/id_ed25519
chown ubuntu:ubuntu /home/ubuntu/.ssh/id_ed25519
ssh-keyscan -t ed25519 github.com >> /home/ubuntu/.ssh/known_hosts 2>/dev/null || true
chown ubuntu:ubuntu /home/ubuntu/.ssh/known_hosts

# Run setup as ubuntu
sudo -u ubuntu -H bash << 'SETUPBLOCK'
set -euo pipefail
source "$HOME/.profile" 2>/dev/null || true

if [ ! -f "$HOME/.cargo/env" ]; then
  curl https://sh.rustup.rs -sSf | sh -s -- -y
fi
source "$HOME/.cargo/env"

cd /home/ubuntu
if [ ! -d "auto-battler-coach-lab" ]; then
  GIT_SSH_COMMAND="ssh -i $HOME/.ssh/id_ed25519 -o StrictHostKeyChecking=yes" \
    git clone --filter=blob:none git@github.com:<YOUR_ORG>/<YOUR_REPO>.git
fi
cd auto-battler-coach-lab
git checkout main

python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements-simulator.txt maturin
pip install awscli
pip install -r requirements-ml.txt 2>&1 || echo "WARNING: ML deps skipped (non-fatal)"

cd simulator/core/rust_engine
maturin develop --release
cd /home/ubuntu/auto-battler-coach-lab

python -c "import tft_combat_engine; print('Rust engine OK')" 2>/dev/null \
  || python -c "from simulator.core import rust_engine; print('Rust engine alt-import OK')" 2>/dev/null \
  || echo "WARNING: Rust engine check failed - will verify at gate runtime"

python -m simulator.cloud_runner --help > /dev/null 2>&1 && echo "cloud_runner: OK" || echo "WARNING: cloud_runner broken"
echo "=== Simulator Bootstrap complete at $(date -u) ==="
SETUPBLOCK


