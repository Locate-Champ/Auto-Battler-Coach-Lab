#!/usr/bin/env bash
# launch-graviton.sh
#
# Launches a c8g.48xlarge (Graviton4 ARM) instance for simulator gates.
# Run from your local machine. Requires: aws cli configured for us-east-1.
#
# Usage:
#   bash scripts/launch-graviton.sh                  # launch and wait for SSM
#   bash scripts/launch-graviton.sh --dry-run        # print what would happen
#   bash scripts/launch-graviton.sh --spot           # use spot pricing (~60-70% cheaper)
#   bash scripts/launch-graviton.sh --instance-type c7g.16xlarge  # override instance type
#
# After launch, run gates with:
#   bash scripts/run-gates.sh --instance-id <id> --gates b,c

set -euo pipefail

# â”€â”€ CONFIG â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
REGION="us-east-1"
INSTANCE_TYPE="c8g.48xlarge"
IAM_ROLE="<INSTANCE_ROLE_NAME>"              # IAM instance profile name (verified 2026-02-18)
KEY_PAIR=""                           # leave empty if using SSM only (no SSH)
SECURITY_GROUP=""                     # leave empty to use default VPC SG
VOLUME_SIZE_GB=100                    # gp3, enough for Gate D output
REPO_SSH="git@github.com:<YOUR_ORG>/<YOUR_REPO>.git"
REPO_REF="main"
REPO_DIR="auto-battler-coach-lab"
# Deploy key private key (base64-encoded). Must be provided via env var.
DEPLOY_KEY_B64="${DEPLOY_KEY_B64:-}"
USE_SPOT=false
DRY_RUN=false
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

for arg in "$@"; do
  case "$arg" in
    --dry-run)    DRY_RUN=true ;;
    --spot)       USE_SPOT=true ;;
    --instance-type=*) INSTANCE_TYPE="${arg#*=}" ;;
  esac
done

log() { echo "[$(date +%H:%M:%S)] $*"; }
die() { echo "[ERROR] $*" >&2; exit 1; }

if [ "$DRY_RUN" = false ] && [ -z "$DEPLOY_KEY_B64" ]; then
  die "DEPLOY_KEY_B64 is empty. Export a base64-encoded deploy key before launching."
fi

# â”€â”€ Find the latest Ubuntu 22.04 ARM64 AMI â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
log "Finding latest Ubuntu 22.04 arm64 AMI in ${REGION}..."
AMI_ID=$(aws ec2 describe-images \
  --region "$REGION" \
  --owners 099720109477 \
  --filters \
    "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-arm64-server-*" \
    "Name=state,Values=available" \
    "Name=architecture,Values=arm64" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text)

if [ -z "$AMI_ID" ] || [ "$AMI_ID" = "None" ]; then
  die "Could not find Ubuntu 22.04 arm64 AMI in ${REGION}"
fi
log "AMI: ${AMI_ID}"

# â”€â”€ Find default VPC security group if not specified â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if [ -z "$SECURITY_GROUP" ]; then
  SECURITY_GROUP=$(aws ec2 describe-security-groups \
    --region "$REGION" \
    --filters "Name=group-name,Values=default" \
    --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || true)
  log "Using default SG: ${SECURITY_GROUP}"
fi

# â”€â”€ User-data (cloud-init) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# This bootstraps the instance so it's ready for gate runs via SSM.
# It does NOT run any gates â€” that's done separately via run-gates.sh.
USER_DATA=$(cat <<USERDATA
#!/bin/bash
set -euo pipefail
exec > >(tee -a /var/log/coach-bootstrap.log) 2>&1
echo "=== Simulator Bootstrap started at \$(date -u) ==="

export DEBIAN_FRONTEND=noninteractive

# System deps
apt-get update -q
apt-get install -y -q \
  git curl ca-certificates \
  python3 python3-venv python3-pip python3-dev \
  build-essential pkg-config libssl-dev

# Create workspace
mkdir -p /data/sim/results /data/sim/models_checkpoints
chown -R ubuntu:ubuntu /data/sim

# Install deploy key for private repo access
mkdir -p /home/ubuntu/.ssh
echo "${DEPLOY_KEY_B64}" | base64 -d > /home/ubuntu/.ssh/id_ed25519
chmod 600 /home/ubuntu/.ssh/id_ed25519
chown ubuntu:ubuntu /home/ubuntu/.ssh/id_ed25519
# Trust github.com host key
ssh-keyscan -t ed25519 github.com >> /home/ubuntu/.ssh/known_hosts 2>/dev/null || true
chown ubuntu:ubuntu /home/ubuntu/.ssh/known_hosts

# Everything below runs as ubuntu
sudo -u ubuntu -H bash -l <<'ASUSER'
set -euo pipefail

# Rust toolchain (native ARM â€” no cross-compile needed)
if [ ! -f "\$HOME/.cargo/env" ]; then
  curl https://sh.rustup.rs -sSf | sh -s -- -y
fi
source "\$HOME/.cargo/env"

# Clone repo via SSH deploy key
cd /home/ubuntu
if [ ! -d "${REPO_DIR}" ]; then
  git clone --filter=blob:none "${REPO_SSH}" "${REPO_DIR}"
fi
cd "${REPO_DIR}"
git fetch --all --tags
git checkout "${REPO_REF}"

# Python venv + deps
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip

pip install -r requirements-simulator.txt maturin
pip install -r requirements-ml.txt || echo "WARNING: ML deps failed (non-fatal for sim-only runs)"

# Install awscli into venv (avoids the apt awscli issue Codex hit)
pip install awscli

# Build Rust engine (native ARM, release mode)
cd simulator/core/rust_engine
maturin develop --release
cd /home/ubuntu/${REPO_DIR}

# Smoke test
python -c "from simulator.core.rust_engine import rust_combat_engine; print('Rust engine OK')" \
  || echo "WARNING: Rust engine import failed"
python -m simulator.cloud_runner --help > /dev/null 2>&1 \
  && echo "cloud_runner OK" \
  || echo "WARNING: cloud_runner --help failed"

echo "=== Simulator Bootstrap complete at $(date -u) ==="
ASUSER
USERDATA
)

# â”€â”€ Build launch command â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
LAUNCH_ARGS=(
  aws ec2 run-instances
  --region "$REGION"
  --image-id "$AMI_ID"
  --instance-type "$INSTANCE_TYPE"
  --iam-instance-profile "Name=${IAM_ROLE}"
  --block-device-mappings "[{\"DeviceName\":\"/dev/sda1\",\"Ebs\":{\"VolumeSize\":${VOLUME_SIZE_GB},\"VolumeType\":\"gp3\",\"Throughput\":250,\"Iops\":3000}}]"
  --user-data "$USER_DATA"
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=sim-graviton4},{Key=Project,Value=auto-battler-coach-lab}]"
  --metadata-options "HttpTokens=required,HttpEndpoint=enabled"
)

if [ -n "$KEY_PAIR" ]; then
  LAUNCH_ARGS+=(--key-name "$KEY_PAIR")
fi

if [ -n "$SECURITY_GROUP" ]; then
  LAUNCH_ARGS+=(--security-group-ids "$SECURITY_GROUP")
fi

if [ "$USE_SPOT" = true ]; then
  LAUNCH_ARGS+=(--instance-market-options '{"MarketType":"spot","SpotOptions":{"SpotInstanceType":"one-time"}}')
  log "Using SPOT pricing."
fi

# â”€â”€ Launch â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if [ "$DRY_RUN" = true ]; then
  log "(dry-run) Would launch with:"
  echo "  AMI: ${AMI_ID}"
  echo "  Type: ${INSTANCE_TYPE}"
  echo "  Role: ${IAM_ROLE}"
  echo "  Volume: ${VOLUME_SIZE_GB} GB gp3"
  echo "  Spot: ${USE_SPOT}"
  log "(dry-run) User-data preview (first 10 lines):"
  echo "$USER_DATA" | head -10
  exit 0
fi

log "Launching ${INSTANCE_TYPE}..."
INSTANCE_ID=$(${LAUNCH_ARGS[@]} \
  --query 'Instances[0].InstanceId' --output text)

if [ -z "$INSTANCE_ID" ]; then
  die "Launch failed â€” no instance ID returned."
fi

log "Instance ID: ${INSTANCE_ID}"
log "Waiting for 'running' state..."
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --region "$REGION"
log "Instance is running."

# â”€â”€ Wait for SSM â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
log "Waiting for SSM agent (up to 5 min)..."
for i in $(seq 1 30); do
  SSM_STATUS=$(aws ssm describe-instance-information --region "$REGION" \
    --filters "Key=InstanceIds,Values=${INSTANCE_ID}" \
    --query 'InstanceInformationList[0].PingStatus' --output text 2>/dev/null || echo "None")
  if [ "$SSM_STATUS" = "Online" ]; then
    log "SSM agent is online."
    break
  fi
  if [ "$i" -eq 30 ]; then
    log "WARNING: SSM not online after 5 min. Bootstrap may still be running."
    log "Check: aws ssm start-session --target ${INSTANCE_ID} --region ${REGION}"
  fi
  sleep 10
done

# â”€â”€ Summary â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
log ""
log "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"
log "  Instance launched successfully"
log "  ID:     ${INSTANCE_ID}"
log "  Type:   ${INSTANCE_TYPE}"
log "  AMI:    ${AMI_ID} (Ubuntu 22.04 arm64)"
log "  Region: ${REGION}"
log "  Spot:   ${USE_SPOT}"
log "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"
log ""
log "Bootstrap is running via cloud-init (5-10 min)."
log "Monitor progress:"
log "  aws ssm start-session --target ${INSTANCE_ID} --region ${REGION}"
log "  Then: sudo tail -f /var/log/coach-bootstrap.log"
log ""
log "Once bootstrap is done, run gates:"
log "  bash scripts/run-gates.sh --instance-id ${INSTANCE_ID} --gates a,b"
log ""
log "To stop the instance later:"
log "  aws ec2 stop-instances --instance-ids ${INSTANCE_ID} --region ${REGION}"


