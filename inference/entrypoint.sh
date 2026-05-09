#!/usr/bin/env sh
# Inference Space entrypoint: Ollama + riprap-models + FastAPI proxy.

set -e

# --- 0. EO toolchain (terratorch + Sentinel-2 chain). Runtime-installed
#        because the build sandbox is too tight to fit it next to
#        Granite weights. ---------------------------------------------
EO_DIR="$HOME/.eo-pkgs"
EO_MARKER="$EO_DIR/.installed"
if [ ! -f "$EO_MARKER" ]; then
    echo "[entrypoint.inf] installing EO toolchain into $EO_DIR ..."
    mkdir -p "$EO_DIR"
    if pip install --no-cache-dir --no-deps --target="$EO_DIR" \
            terratorch==1.1rc6 einops diffusers timm; then
        if PYTHONPATH="$EO_DIR:$PYTHONPATH" python -c "
import terratorch
import terratorch.models.backbones.terramind.model.terramind_register
from terratorch.registry import FULL_MODEL_REGISTRY
n = len([k for k in FULL_MODEL_REGISTRY if 'terramind' in k.lower()])
assert n > 0
print(f'[entrypoint.inf] terratorch ok ({n} terramind entries)')
"; then
            touch "$EO_MARKER"
            echo "[entrypoint.inf] EO toolchain READY"
        else
            echo "[entrypoint.inf] EO verify FAILED — TerraMind probes will skip"
        fi
    else
        echo "[entrypoint.inf] pip install FAILED — TerraMind probes will skip"
    fi
else
    echo "[entrypoint.inf] EO toolchain cached"
fi
export PYTHONPATH="$EO_DIR:$PYTHONPATH"

# --- 1. Ollama (Granite 4.1 baked into the image, just serve them) ---
LOG_OLLAMA="$HOME/ollama.log"
ollama serve 2>&1 | tee "$LOG_OLLAMA" &
OLLAMA_PID=$!

for i in $(seq 1 60); do
    if curl -sf http://127.0.0.1:11434/ > /dev/null 2>&1; then
        echo "[entrypoint.inf] ollama up after ${i}s"
        break
    fi
    if ! kill -0 "$OLLAMA_PID" 2>/dev/null; then
        echo "[entrypoint.inf] FATAL: ollama died"
        tail -40 "$LOG_OLLAMA" || true
        exit 1
    fi
    sleep 1
done

# Pre-warm 8B into VRAM (24h keep-alive). 3B will lazy-load on first
# planner call.
echo "[entrypoint.inf] pre-warming granite4.1:8b ..."
curl -s -X POST http://127.0.0.1:11434/api/generate \
     -d '{"model":"granite4.1:8b","prompt":"hi","stream":false,"keep_alive":"24h","options":{"num_predict":1}}' \
     -o /dev/null --max-time 120 \
     && echo "[entrypoint.inf] 8b warm" \
     || echo "[entrypoint.inf] WARN: 8b warmup failed (will load lazily)"

# --- 2. riprap-models on :7861 ---------------------------------------
LOG_MODELS="$HOME/riprap-models.log"
uvicorn riprap_models:app --host 127.0.0.1 --port 7861 --log-level info \
    > "$LOG_MODELS" 2>&1 &
MODELS_PID=$!

for i in $(seq 1 60); do
    if curl -sf http://127.0.0.1:7861/healthz > /dev/null 2>&1; then
        echo "[entrypoint.inf] riprap-models up after ${i}s"
        break
    fi
    if ! kill -0 "$MODELS_PID" 2>/dev/null; then
        echo "[entrypoint.inf] FATAL: riprap-models died"
        tail -40 "$LOG_MODELS" || true
        exit 1
    fi
    sleep 1
done

# --- 3. GPU sanity ---------------------------------------------------
if command -v nvidia-smi > /dev/null 2>&1; then
    nvidia-smi -L || true
fi

# --- 4. FastAPI bearer-auth proxy on :7860 (foreground) -------------
exec uvicorn proxy:app --host 0.0.0.0 --port 7860 --log-level info
