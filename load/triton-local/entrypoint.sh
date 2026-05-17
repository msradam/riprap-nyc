#!/usr/bin/env bash
# Local Triton bring-up for M3 Mac (Docker + colima, no GPU).
#
# Triton 25.05-py3 arm64 ships WITHOUT the model-side deps. Install them
# before launching tritonserver so each model's Python backend can import
# what it needs at model-load time.
#
# Models loaded:
#   - granite_embed  (sentence-transformers + transformers)
#   - gliner         (gliner library, torch, transformers)
#   - ttm_forecast   (tsfm_public, torch, huggingface_hub)
#
# Punted (need terratorch — 5-10 min install on ARM + ~3 GB EO weights):
#   - prithvi_pluvial
#   - terramind
# Riprap-app's offline-skip path handles their absence cleanly.
set -euo pipefail

echo "[entrypoint] python: $(python3 --version)"

# Pin numpy<2 before pulling sentence-transformers (which transitively
# wants >=2) — tritonserver + cupy need <2.
if ! python3 -c "import numpy; assert numpy.__version__.startswith('1.')" 2>/dev/null; then
    echo "[entrypoint] installing numpy<2"
    pip install --quiet "numpy<2"
fi

if ! python3 -c "import torch" 2>/dev/null; then
    echo "[entrypoint] installing torch 2.5.1 (CPU-only arm64 wheel)"
    pip install --quiet "torch==2.5.1" --index-url https://download.pytorch.org/whl/cpu
fi

if ! python3 -c "import transformers" 2>/dev/null; then
    echo "[entrypoint] installing transformers + sentence-transformers"
    pip install --quiet "transformers>=4.45" "sentence-transformers>=5.0" \
        "huggingface_hub>=0.34" "safetensors>=0.4"
fi

if ! python3 -c "import gliner" 2>/dev/null; then
    echo "[entrypoint] installing gliner"
    pip install --quiet "gliner>=0.2.6"
fi

if ! python3 -c "import tsfm_public" 2>/dev/null; then
    echo "[entrypoint] installing granite-tsfm (tsfm_public)"
    pip install --quiet "granite-tsfm==0.3.3"
fi

echo "[entrypoint] versions:"
python3 -c "import torch, transformers, gliner, tsfm_public, numpy
print(f'  torch:         {torch.__version__}  cuda={torch.cuda.is_available()}')
print(f'  transformers:  {transformers.__version__}')
print(f'  gliner:        {gliner.__version__}')
print(f'  tsfm_public:   {tsfm_public.__version__}')
print(f'  numpy:         {numpy.__version__}')"

mkdir -p /hf_cache
export HF_HOME=/hf_cache
export TRANSFORMERS_CACHE=/hf_cache
export PYTHONDONTWRITEBYTECODE=1

echo "[entrypoint] starting tritonserver — first load downloads weights from HF"
exec tritonserver \
    --model-repository=/models \
    --model-control-mode=explicit \
    --load-model=granite_embed \
    --load-model=gliner \
    --load-model=ttm_forecast \
    --strict-model-config=false \
    --log-verbose=1
