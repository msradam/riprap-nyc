#!/usr/bin/env sh
# Start Ollama daemon in the background, wait for it to be ready,
# then launch uvicorn on the HF Spaces default port.
#
# HF Spaces locks down /tmp for unprivileged users — write logs to
# $HOME (which we own) instead.
set -e

# --- Earth-observation toolchain (Phase 1 + Phase 4) -------------------
# Build-time install was blocked by HF's build-disk threshold (5
# attempts; all failed at the same point). Runtime install in the
# running container works around the build-sandbox limit — the
# running container has more disk.
#
# Use `--target=$EO_DIR` instead of `--user`: explicit path that we
# can prepend to PYTHONPATH ourselves, so the install location is
# guaranteed visible regardless of HF Spaces' Python site-config.
# The `--user` approach was failing silently because HF's Python
# environment apparently bypasses the user-site discovery path.
EO_DIR="$HOME/.eo-pkgs"
EO_MARKER="$EO_DIR/.installed"
if [ ! -f "$EO_MARKER" ]; then
    echo "[entrypoint] EO toolchain not yet installed; running pip install (~2 min)..."
    mkdir -p "$EO_DIR"
    # Bisect: previous build (1cf59ee) added torchvision + 7 more deps
    # at once and the whole install failed (eo_dir empty, no marker).
    # Pip's resolver is all-or-nothing per RUN — one bad package fails
    # everything. Revert to the known-good 4 + just torchvision (the
    # one terratorch actually needs to import). Once this proves out,
    # add Prithvi-live deps in a second RUN.
    if pip install --no-cache-dir --no-deps --target="$EO_DIR" \
            terratorch==1.1rc6 \
            einops \
            diffusers \
            timm \
            torchvision; then
        echo "[entrypoint] pip install OK; verifying import..."
        if PYTHONPATH="$EO_DIR:$PYTHONPATH" python -c "
import terratorch
from terratorch.registry import FULL_MODEL_REGISTRY
import terratorch.models.backbones.terramind.model.terramind_register
n = len([k for k in FULL_MODEL_REGISTRY if 'terramind' in k.lower()])
assert n > 0, 'no terramind register entries'
print(f'[entrypoint] terratorch ok, terramind register: {n} entries')
"; then
            touch "$EO_MARKER"
            echo "[entrypoint] EO toolchain READY at $EO_DIR"
        else
            echo "[entrypoint] EO verify FAILED — TerraMind/Prithvi-live will skip"
        fi
    else
        echo "[entrypoint] pip install FAILED — TerraMind/Prithvi-live will skip"
    fi
else
    echo "[entrypoint] EO toolchain already installed at $EO_DIR (cached)"
fi
# Always export PYTHONPATH so uvicorn can find the install (no-op if
# the install failed and the dir is empty — the lazy-import in the
# specialists handles that case cleanly).
export PYTHONPATH="$EO_DIR:$PYTHONPATH"

# Stream Ollama's stdout+stderr to BOTH stdout (so it shows up in HF
# Spaces runtime logs — needed to see GPU discovery output from
# OLLAMA_DEBUG=1) AND a file (for the readiness fail-fast tail below).
LOG_FILE="$HOME/ollama.log"
ollama serve 2>&1 | tee "$LOG_FILE" &
OLLAMA_PID=$!

# Wait for Ollama to be reachable (up to 60 s — first start can be slow
# on a cold container with persistent storage being mounted)
for i in $(seq 1 60); do
  if curl -sf http://127.0.0.1:11434/ > /dev/null 2>&1; then
    echo "[entrypoint] ollama up (pid $OLLAMA_PID) after ${i}s"
    break
  fi
  if ! kill -0 "$OLLAMA_PID" 2>/dev/null; then
    echo "[entrypoint] FATAL: ollama serve died. Last 40 lines of $LOG_FILE:"
    tail -40 "$LOG_FILE" || true
    exit 1
  fi
  sleep 1
done

if ! curl -sf http://127.0.0.1:11434/ > /dev/null 2>&1; then
  echo "[entrypoint] FATAL: ollama did not become ready within 60s"
  tail -40 "$LOG_FILE" || true
  exit 1
fi

# Granite 4.1:8b is pulled at runtime instead of baked into the image
# — the EO toolchain (Phase 1 Prithvi + Phase 4 TerraMind) doesn't
# fit alongside Granite weights in HF's build sandbox. First container
# start does the pull (~2 min over the wire). Subsequent runtime
# restarts within the same image lifetime reuse Ollama's cache so
# this is a one-time per-image cost.
#
# 3b is also handled if present, but with RIPRAP_OLLAMA_3B_TAG=
# granite4.1:8b set, the planner alias resolves to 8b too — so 8b
# alone covers planner + reconciler.
for model in "granite4.1:8b" "granite4.1:3b"; do
  if ! ollama list | grep -q "$model"; then
    if [ "$model" = "granite4.1:8b" ]; then
      echo "[entrypoint] $model not found; pulling now (~5GB, ~2 min over the wire)..."
      ollama pull "$model" || {
        echo "[entrypoint] FATAL: pull failed for $model — reconciler will not work"
        exit 1
      }
    else
      # 3B is optional; if it's not there and the env override is set,
      # the router will route the planner alias to 8B.
      echo "[entrypoint] $model not found (optional — planner alias remapped to 8b via RIPRAP_OLLAMA_3B_TAG)"
    fi
  fi
done

ollama list

# Pre-warm Granite 4.1:8b into VRAM so the first reconcile doesn't pay
# the ~30s model-load tax. The empty prompt keeps it tiny; OLLAMA_KEEP_ALIVE
# (24h) holds the weights resident through the demo.
echo "[entrypoint] pre-warming granite4.1:8b into VRAM (one-shot)..."
curl -s -X POST http://127.0.0.1:11434/api/generate \
     -d '{"model":"granite4.1:8b","prompt":"hi","stream":false,"keep_alive":"24h","options":{"num_predict":1}}' \
     -o /dev/null --max-time 120 \
     && echo "[entrypoint] granite4.1:8b warm" \
     || echo "[entrypoint] WARNING: 8b warmup failed (will load lazily)"

# Log GPU visibility + Ollama lib layout so we can confirm CUDA dispatch
# from the runtime logs (paired with OLLAMA_DEBUG=1 in the daemon).
if command -v nvidia-smi > /dev/null 2>&1; then
  echo "[entrypoint] nvidia-smi present:"
  nvidia-smi -L || true
else
  echo "[entrypoint] nvidia-smi NOT present — Ollama will run on CPU"
fi
echo "[entrypoint] ollama lib dirs:"
ls -d /usr/lib/ollama 2>/dev/null && ls /usr/lib/ollama 2>/dev/null | head -20 || echo "  /usr/lib/ollama missing"
ls -d /usr/local/lib/ollama 2>/dev/null && ls /usr/local/lib/ollama 2>/dev/null | head -20 || echo "  /usr/local/lib/ollama missing"

exec uvicorn web.main:app --host 0.0.0.0 --port 7860 --log-level info
