#!/usr/bin/env sh
# Entrypoint for the personal HF Space (msradam/riprap-nyc) on L4.
#
# Boots three things in order:
#   1. Ollama serve  → granite4.1:8b on localhost:11434
#   2. riprap-models → Prithvi/TerraMind/TTM/GLiNER/Embedding on :7861
#   3. web.main      → FastAPI + SSE on :7860 (HF Spaces public port)
#
# The 8B is baked into the image (see Dockerfile.l4); the EO toolchain
# (terratorch + deps) installs at runtime to keep the build sandbox
# under its disk threshold. ~2 minutes on first cold start; cached
# thereafter for the lifetime of the image.

set -e

# --- 1. EO toolchain (runtime-installed; same pattern as the canonical
#        entrypoint.sh) -------------------------------------------------
EO_DIR="$HOME/.eo-pkgs"
EO_MARKER="$EO_DIR/.installed"
if [ ! -f "$EO_MARKER" ]; then
    echo "[entrypoint.l4] installing EO toolchain into $EO_DIR ..."
    mkdir -p "$EO_DIR"
    if pip install --no-cache-dir --no-deps --target="$EO_DIR" \
            terratorch==1.1rc6 einops diffusers timm torchvision; then
        if PYTHONPATH="$EO_DIR:$PYTHONPATH" python -c "
import terratorch
import terratorch.models.backbones.terramind.model.terramind_register
from terratorch.registry import FULL_MODEL_REGISTRY
n = len([k for k in FULL_MODEL_REGISTRY if 'terramind' in k.lower()])
assert n > 0
print(f'[entrypoint.l4] terratorch ok ({n} terramind entries)')
"; then
            touch "$EO_MARKER"
            echo "[entrypoint.l4] EO toolchain READY"
        else
            echo "[entrypoint.l4] EO verify FAILED — Prithvi/TerraMind probes will skip"
        fi
    else
        echo "[entrypoint.l4] pip install FAILED — Prithvi/TerraMind probes will skip"
    fi
else
    echo "[entrypoint.l4] EO toolchain already installed (cached)"
fi
export PYTHONPATH="$EO_DIR:$PYTHONPATH"

# --- 2. Ollama serve --------------------------------------------------
LOG_OLLAMA="$HOME/ollama.log"
ollama serve 2>&1 | tee "$LOG_OLLAMA" &
OLLAMA_PID=$!

for i in $(seq 1 60); do
    if curl -sf http://127.0.0.1:11434/ > /dev/null 2>&1; then
        echo "[entrypoint.l4] ollama up (pid $OLLAMA_PID) after ${i}s"
        break
    fi
    if ! kill -0 "$OLLAMA_PID" 2>/dev/null; then
        echo "[entrypoint.l4] FATAL: ollama serve died"
        tail -40 "$LOG_OLLAMA" || true
        exit 1
    fi
    sleep 1
done

# Granite 4.1:8b is baked. Pre-warm into VRAM so the first reconcile
# doesn't pay the ~30s model-load tax.
echo "[entrypoint.l4] pre-warming granite4.1:8b into VRAM ..."
curl -s -X POST http://127.0.0.1:11434/api/generate \
     -d '{"model":"granite4.1:8b","prompt":"hi","stream":false,"keep_alive":"24h","options":{"num_predict":1}}' \
     -o /dev/null --max-time 120 \
     && echo "[entrypoint.l4] granite warm" \
     || echo "[entrypoint.l4] WARNING: granite warmup failed (will load lazily)"

# --- 3. riprap-models on :7861 ---------------------------------------
# Same FastAPI app the AMD droplet runs, just rehosted in-process here
# so app/inference.py's RIPRAP_ML_BASE_URL points at localhost.
LOG_MODELS="$HOME/riprap-models.log"
uvicorn riprap_models:app --host 127.0.0.1 --port 7861 --log-level info \
    > "$LOG_MODELS" 2>&1 &
MODELS_PID=$!

for i in $(seq 1 60); do
    if curl -sf http://127.0.0.1:7861/healthz > /dev/null 2>&1; then
        echo "[entrypoint.l4] riprap-models up (pid $MODELS_PID) after ${i}s"
        break
    fi
    if ! kill -0 "$MODELS_PID" 2>/dev/null; then
        echo "[entrypoint.l4] FATAL: riprap-models died"
        tail -40 "$LOG_MODELS" || true
        exit 1
    fi
    sleep 1
done

# --- GPU sanity --------------------------------------------------------
if command -v nvidia-smi > /dev/null 2>&1; then
    echo "[entrypoint.l4] nvidia-smi:"
    nvidia-smi -L || true
else
    echo "[entrypoint.l4] WARNING: nvidia-smi missing — running on CPU"
fi

# --- 4. Web app (foreground) -----------------------------------------
exec uvicorn web.main:app --host 0.0.0.0 --port 7860 --log-level info
