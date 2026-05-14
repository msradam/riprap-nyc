#!/usr/bin/env bash
# RunPod setup: install vLLM + riprap-models + proxy, start all three services.
# Run once after SSH-ing into a fresh runpod/pytorch pod on L4.
# All services write logs to /workspace/logs/.

set -euo pipefail

REPO_URL="https://github.com/msradam/riprap-nyc.git"
REPO_DIR="/workspace/riprap-nyc"
LOG_DIR="/workspace/logs"
HF_CACHE="/workspace/hf_cache"
PROXY_TOKEN="${RIPRAP_PROXY_TOKEN:-pm7AmssTxoi0OSvXZH6ciMDwOATzlwXjPHBUKJ-cjQk}"

mkdir -p "$LOG_DIR" "$HF_CACHE"
export HF_HOME="$HF_CACHE"
export TRANSFORMERS_CACHE="$HF_CACHE"

echo "==> [1/6] Clone riprap repo"
if [ -d "$REPO_DIR/.git" ]; then
    echo "    already cloned — pulling latest"
    git -C "$REPO_DIR" pull --ff-only
else
    git clone --depth 1 "$REPO_URL" "$REPO_DIR"
fi

echo "==> [2/6] Install vLLM"
pip install --quiet vllm==0.7.3 nvidia-ml-py>=12.560

echo "==> [3/6] Install riprap-models + proxy deps"
pip install --quiet \
    fastapi>=0.115 \
    uvicorn[standard]>=0.32 \
    httpx>=0.27 \
    pydantic>=2.9 \
    gliner>=0.2.6 \
    "sentence-transformers>=5.0.0" \
    huggingface_hub>=0.34 \
    peft==0.18.1 \
    granite-tsfm==0.3.3 \
    torchvision \
    einops \
    tifffile

echo "==> [4/6] Install terratorch (EO stack, slow)"
pip install --quiet \
    terratorch==1.1rc6 \
    diffusers timm albumentations \
    segmentation-models-pytorch kornia || \
    echo "    WARN: terratorch install failed — TerraMind probes will skip"

echo "==> [5/6] Start vLLM on :8000"
pkill -f "vllm.entrypoints.openai" 2>/dev/null || true
nohup python -m vllm.entrypoints.openai.api_server \
    --model ibm-granite/granite-4.1-8b-fp8 \
    --served-model-name granite4.1:8b granite4.1:3b \
    --host 0.0.0.0 \
    --port 8000 \
    --api-key "$PROXY_TOKEN" \
    --gpu-memory-utilization 0.55 \
    --max-model-len 4096 \
    --enforce-eager \
    --disable-log-requests \
    > "$LOG_DIR/vllm.log" 2>&1 &
VLLM_PID=$!
echo "    vLLM pid $VLLM_PID — waiting for health..."
for i in $(seq 1 240); do
    curl -sf http://127.0.0.1:8000/health > /dev/null 2>&1 && echo "    vLLM ready after ${i}s" && break
    sleep 1
done

echo "==> [6a/6] Start riprap-models on :7861"
pkill -f "riprap_models" 2>/dev/null || true
cp "$REPO_DIR/services/riprap-models/main.py" /workspace/riprap_models.py
nohup uvicorn riprap_models:app --host 0.0.0.0 --port 7861 --log-level info \
    > "$LOG_DIR/riprap-models.log" 2>&1 &
echo "    riprap-models pid $!"

echo "==> [6b/6] Start bearer-auth proxy on :7860 (foreground — keeps container alive)"
pkill -f "proxy:app" 2>/dev/null || true
cp "$REPO_DIR/inference-vllm/proxy.py" /workspace/proxy.py

export RIPRAP_PROXY_TOKEN="$PROXY_TOKEN"

echo
echo "All services started. Logs in $LOG_DIR/"
echo "  LLM+proxy : http://0.0.0.0:7860/v1"
echo "  vLLM raw  : http://0.0.0.0:8000/v1"
echo "  models    : http://0.0.0.0:7861"
echo

# Run proxy in foreground — this keeps the container alive.
exec uvicorn proxy:app --host 0.0.0.0 --port 7860 --log-level info
