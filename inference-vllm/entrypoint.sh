#!/usr/bin/env sh
# vLLM Space entrypoint: vLLM + riprap-models + FastAPI bearer-auth proxy.

set -e

# EO toolchain (terratorch + transitive deps) is now baked into the
# image at build time, not runtime-installed. Verify import once at
# startup so the trace makes the failure visible if a wheel goes
# stale.
python -c "
import terratorch
import terratorch.models.backbones.terramind.model.terramind_register
from terratorch.registry import FULL_MODEL_REGISTRY
n = len([k for k in FULL_MODEL_REGISTRY if 'terramind' in k.lower()])
assert n > 0
print(f'[entrypoint.vllm] terratorch ok ({n} terramind entries)')
" || echo "[entrypoint.vllm] WARN: terratorch import failed — TerraMind probes will skip"

# --- 1. vLLM (Granite 4.1 8B FP8) on :8000 --------------------------
LOG_VLLM="$HOME/vllm.log"
# --gpu-memory-utilization 0.45 caps vLLM at ~10 GB on the 22.5 GB L4,
# leaving ~12.5 GB for the riprap-models EO stack (Prithvi, TerraMind
# x3, TTM, GLiNER, Embedding) which peaks at ~10 GB during loading.
# Previous value 0.55 left only ~0.5 GB headroom and caused OOM crashes
# when riprap-models loaded alongside vLLM.
python -m vllm.entrypoints.openai.api_server \
    --model ibm-granite/granite-4.1-8b-fp8 \
    --served-model-name granite4.1:8b granite-4.1-8b ibm-granite/granite-4.1-8b-fp8 \
    --host 127.0.0.1 \
    --port 8000 \
    --gpu-memory-utilization 0.45 \
    --max-model-len 8192 \
    --enforce-eager \
    --disable-log-requests \
    > "$LOG_VLLM" 2>&1 &
VLLM_PID=$!

for i in $(seq 1 240); do
    if curl -sf http://127.0.0.1:8000/health > /dev/null 2>&1; then
        echo "[entrypoint.vllm] vLLM up (pid $VLLM_PID) after ${i}s"
        break
    fi
    if ! kill -0 "$VLLM_PID" 2>/dev/null; then
        echo "[entrypoint.vllm] FATAL: vLLM died"
        tail -60 "$LOG_VLLM" || true
        exit 1
    fi
    sleep 1
done

if ! curl -sf http://127.0.0.1:8000/health > /dev/null 2>&1; then
    echo "[entrypoint.vllm] FATAL: vLLM did not become ready within 240s"
    tail -60 "$LOG_VLLM" || true
    exit 1
fi

# Background watchdog: if vLLM dies after startup, restart it.
_start_vllm() {
    python -m vllm.entrypoints.openai.api_server \
        --model ibm-granite/granite-4.1-8b-fp8 \
        --served-model-name granite4.1:8b granite-4.1-8b ibm-granite/granite-4.1-8b-fp8 \
        --host 127.0.0.1 \
        --port 8000 \
        --gpu-memory-utilization 0.45 \
        --max-model-len 8192 \
        --enforce-eager \
        --disable-log-requests \
        >> "$LOG_VLLM" 2>&1 &
    echo $!
}
_vllm_watchdog() {
    local pid=$1
    while true; do
        sleep 30
        if ! kill -0 "$pid" 2>/dev/null; then
            echo "[watchdog] vLLM died — restarting..." >> "$LOG_VLLM"
            pid=$(_start_vllm)
            echo "[watchdog] vLLM restarted as pid $pid" >> "$LOG_VLLM"
        fi
    done
}
_vllm_watchdog "$VLLM_PID" &

# --- 2. riprap-models on :7861 --------------------------------------
LOG_MODELS="$HOME/riprap-models.log"
uvicorn riprap_models:app --host 127.0.0.1 --port 7861 --log-level info \
    > "$LOG_MODELS" 2>&1 &
MODELS_PID=$!

for i in $(seq 1 60); do
    if curl -sf http://127.0.0.1:7861/healthz > /dev/null 2>&1; then
        echo "[entrypoint.vllm] riprap-models up (pid $MODELS_PID) after ${i}s"
        break
    fi
    if ! kill -0 "$MODELS_PID" 2>/dev/null; then
        echo "[entrypoint.vllm] FATAL: riprap-models died"
        tail -40 "$LOG_MODELS" || true
        exit 1
    fi
    sleep 1
done

# --- 3. GPU sanity --------------------------------------------------
if command -v nvidia-smi > /dev/null 2>&1; then
    nvidia-smi -L || true
fi

# --- 4. FastAPI bearer-auth proxy on :7860 (foreground) -------------
exec uvicorn proxy:app --host 0.0.0.0 --port 7860 --log-level info
