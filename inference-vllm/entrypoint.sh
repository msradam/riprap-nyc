#!/usr/bin/env sh
# vLLM Space entrypoint: vLLM + riprap-models + FastAPI bearer-auth proxy.

set -e

# --- 0. EO toolchain (terratorch + Sentinel-2 chain) -----------------
EO_DIR="$HOME/.eo-pkgs"
EO_MARKER="$EO_DIR/.installed"
if [ ! -f "$EO_MARKER" ]; then
    echo "[entrypoint.vllm] installing EO toolchain into $EO_DIR ..."
    mkdir -p "$EO_DIR"
    if pip install --no-cache-dir --no-deps --target="$EO_DIR" \
            terratorch==1.1rc6 einops diffusers timm; then
        if PYTHONPATH="$EO_DIR:$PYTHONPATH" python -c "
import terratorch
import terratorch.models.backbones.terramind.model.terramind_register
from terratorch.registry import FULL_MODEL_REGISTRY
n = len([k for k in FULL_MODEL_REGISTRY if 'terramind' in k.lower()])
assert n > 0
print(f'[entrypoint.vllm] terratorch ok ({n} terramind entries)')
"; then
            touch "$EO_MARKER"
            echo "[entrypoint.vllm] EO toolchain READY"
        else
            echo "[entrypoint.vllm] EO verify FAILED — TerraMind probes will skip"
        fi
    else
        echo "[entrypoint.vllm] pip install FAILED — TerraMind probes will skip"
    fi
else
    echo "[entrypoint.vllm] EO toolchain cached"
fi
export PYTHONPATH="$EO_DIR:$PYTHONPATH"

# --- 1. vLLM (Granite 4.1 8B FP8) on :8000 --------------------------
LOG_VLLM="$HOME/vllm.log"
# --gpu-memory-utilization 0.55 caps vLLM at ~13 GB on a 24 GB L4,
# leaving room for the riprap-models EO stack to load alongside.
# --served-model-name aliases the long HF id to the short tags the
# canonical FSM uses (granite4.1:8b → routes through here).
python -m vllm.entrypoints.openai.api_server \
    --model ibm-granite/granite-4.1-8b-fp8 \
    --served-model-name granite4.1:8b granite-4.1-8b ibm-granite/granite-4.1-8b-fp8 \
    --host 127.0.0.1 \
    --port 8000 \
    --gpu-memory-utilization 0.55 \
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
