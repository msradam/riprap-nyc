#!/usr/bin/env bash
# Riprap GPU-droplet bring-up — vLLM + riprap-models, idempotent.
#
# Designed for a fresh AMD MI300X droplet (DigitalOcean GPU droplet,
# AMD Developer Cloud node, etc.) with nothing more than:
#   - Ubuntu 22.04 / 24.04
#   - Docker + AMD ROCm GPU drivers (kfd / dri device files)
#   - SSH root access
#
# The script SSHes to the droplet, ensures the right images are
# pulled, builds the riprap-models container from this repo, starts
# both services, and runs healthchecks. Re-running on the same
# droplet is idempotent: existing containers are removed and
# recreated cleanly.
#
# Usage:
#   scripts/deploy_droplet.sh <droplet-ip> <bearer-token>
#
# Example:
#   scripts/deploy_droplet.sh 129.212.181.238 "$(cat /tmp/riprap/vllm_token.txt)"
#
# Env knobs (optional, all have sensible defaults):
#   SSH_USER             default "root"
#   SSH_KEY              path to ssh key; default uses ssh-agent
#   VLLM_IMAGE           default "vllm/vllm-openai-rocm:v0.17.1"
#   VLLM_PORT            default 8001 (host) → 8000 (container)
#   MODELS_PORT          default 7860 (host) → 7860 (container)
#   MODEL_REPO           default "ibm-granite/granite-4.1-8b"
#   HF_CACHE_HOST        default "/root/hf-cache" on droplet
#   SKIP_BUILD           "1" to skip building riprap-models image
#                        (assume it's already present on droplet)
#
# Exits non-zero on any step that fails — including the final
# healthcheck — so this is safe to wrap in CI.
set -euo pipefail

if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <droplet-ip> <bearer-token>" >&2
    exit 64
fi

DROPLET_IP="$1"
TOKEN="$2"

SSH_USER="${SSH_USER:-root}"
SSH_KEY_FLAG=""
if [ -n "${SSH_KEY:-}" ]; then
    SSH_KEY_FLAG="-i $SSH_KEY"
fi
SSH="ssh $SSH_KEY_FLAG -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 ${SSH_USER}@${DROPLET_IP}"
SCP="scp $SSH_KEY_FLAG -o StrictHostKeyChecking=accept-new"

VLLM_IMAGE="${VLLM_IMAGE:-vllm/vllm-openai-rocm:v0.17.1}"
VLLM_PORT="${VLLM_PORT:-8001}"
MODELS_PORT="${MODELS_PORT:-7860}"
MODEL_REPO="${MODEL_REPO:-ibm-granite/granite-4.1-8b}"
HF_CACHE_HOST="${HF_CACHE_HOST:-/root/hf-cache}"
SKIP_BUILD="${SKIP_BUILD:-0}"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Riprap droplet bring-up"
echo "    droplet ip:   $DROPLET_IP"
echo "    vllm port:    $VLLM_PORT"
echo "    models port:  $MODELS_PORT"
echo "    model repo:   $MODEL_REPO"
echo "    repo root:    $REPO_ROOT"
echo

# ---- 1. Verify SSH + droplet readiness ----------------------------------
echo "==> 1. SSH connectivity + GPU device check"
$SSH bash -s <<'REMOTE'
set -e
if ! command -v docker > /dev/null; then
    echo "[droplet] docker not installed; aborting" >&2
    exit 1
fi
if [ ! -e /dev/kfd ] || [ ! -e /dev/dri ]; then
    echo "[droplet] no AMD GPU device files (/dev/kfd or /dev/dri); aborting" >&2
    exit 1
fi
echo "[droplet] docker + AMD GPU device files present"
docker --version
REMOTE

# ---- 2. Pull vLLM image ---------------------------------------------------
echo
echo "==> 2. Pull vLLM image (if not cached)"
$SSH "docker image inspect $VLLM_IMAGE > /dev/null 2>&1 || docker pull $VLLM_IMAGE"

# ---- 3. Sync riprap-models source to droplet -----------------------------
echo
echo "==> 3. Sync riprap-models source"
$SSH "mkdir -p /workspace/riprap-models /workspace/riprap-build"
# Sync Dockerfile + sources via tar over SSH (rsync may be missing on
# a minimal droplet; tar is part of any Linux base).
tar -C "$REPO_ROOT" -cf - services/riprap-models | \
    $SSH "tar -C /workspace/riprap-build -xf -"

# ---- 4. Build riprap-models image ----------------------------------------
if [ "$SKIP_BUILD" = "1" ]; then
    echo
    echo "==> 4. Skipping image build (SKIP_BUILD=1)"
else
    echo
    echo "==> 4. Build riprap-models image"
    echo "    (this takes ~10-20 min on first build; subsequent builds"
    echo "     reuse layer cache and are < 1 min)"
    $SSH "cd /workspace/riprap-build && \
          docker build \
            -t riprap-models:latest \
            -f services/riprap-models/Dockerfile \
            ."
fi

# ---- 5. Start vLLM container ---------------------------------------------
echo
echo "==> 5. Start vLLM container"
$SSH bash -s <<REMOTE
set -e
docker rm -f vllm > /dev/null 2>&1 || true
mkdir -p ${HF_CACHE_HOST}
docker run -d --name vllm \\
    --device=/dev/kfd --device=/dev/dri --group-add=video \\
    --ipc=host --shm-size=16g \\
    -p ${VLLM_PORT}:8000 \\
    -v ${HF_CACHE_HOST}:/root/.cache/huggingface \\
    -e GLOO_SOCKET_IFNAME=eth0 -e VLLM_HOST_IP=127.0.0.1 \\
    --restart unless-stopped \\
    ${VLLM_IMAGE} \\
    --model ${MODEL_REPO} \\
    --host 0.0.0.0 --port 8000 --api-key "${TOKEN}" \\
    --max-model-len 8192 --served-model-name granite-4.1-8b
echo "[droplet] vllm container started"
REMOTE

# ---- 6. Start riprap-models container ------------------------------------
echo
echo "==> 6. Start riprap-models container"
$SSH bash -s <<REMOTE
set -e
docker rm -f riprap-models > /dev/null 2>&1 || true
docker run -d --name riprap-models \\
    --device=/dev/kfd --device=/dev/dri --group-add=video \\
    --ipc=host --shm-size=8g \\
    -p ${MODELS_PORT}:7860 \\
    -v ${HF_CACHE_HOST}:/root/.cache/huggingface \\
    -e RIPRAP_MODELS_API_KEY="${TOKEN}" \\
    --restart unless-stopped \\
    riprap-models:latest
echo "[droplet] riprap-models container started"
REMOTE

# ---- 7. Healthchecks -----------------------------------------------------
echo
echo "==> 7. Healthchecks"
echo "    waiting up to 90s for vLLM to expose /v1/models..."
DEADLINE=$((SECONDS + 90))
while (( SECONDS < DEADLINE )); do
    if curl -sf --max-time 5 "http://${DROPLET_IP}:${VLLM_PORT}/v1/models" \
            -H "Authorization: Bearer ${TOKEN}" > /tmp/vllm-models.json 2>/dev/null; then
        echo "    vLLM ready: $(head -c 200 /tmp/vllm-models.json)..."
        break
    fi
    sleep 3
done
if (( SECONDS >= DEADLINE )); then
    echo "    vLLM did not become ready in 90s; tailing container logs:" >&2
    $SSH "docker logs --tail 30 vllm" >&2
    exit 1
fi

echo "    waiting up to 60s for riprap-models /healthz..."
DEADLINE=$((SECONDS + 60))
while (( SECONDS < DEADLINE )); do
    if curl -sf --max-time 5 "http://${DROPLET_IP}:${MODELS_PORT}/healthz" \
            > /tmp/models-health.json 2>/dev/null; then
        echo "    riprap-models ready: $(cat /tmp/models-health.json)"
        break
    fi
    sleep 2
done
if (( SECONDS >= DEADLINE )); then
    echo "    riprap-models did not become ready in 60s; tailing container logs:" >&2
    $SSH "docker logs --tail 30 riprap-models" >&2
    exit 1
fi

echo
echo "==> DONE"
echo "    vLLM         http://${DROPLET_IP}:${VLLM_PORT}/v1/models"
echo "    riprap-models http://${DROPLET_IP}:${MODELS_PORT}/healthz"
echo
echo "Set these in your local env or HF Space variables:"
echo "    RIPRAP_LLM_PRIMARY=vllm"
echo "    RIPRAP_LLM_BASE_URL=http://${DROPLET_IP}:${VLLM_PORT}/v1"
echo "    RIPRAP_LLM_API_KEY=${TOKEN}"
echo "    RIPRAP_ML_BACKEND=remote"
echo "    RIPRAP_ML_BASE_URL=http://${DROPLET_IP}:${MODELS_PORT}"
echo "    RIPRAP_ML_API_KEY=${TOKEN}"
