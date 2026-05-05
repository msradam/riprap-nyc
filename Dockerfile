# Riprap — Hugging Face Spaces deployment (Docker SDK, GPU).
#
# Base: NVIDIA CUDA 12.4 runtime + cuDNN on Ubuntu 22.04. Ollama's
# installer detects the GPU and pulls the CUDA-aware build automatically;
# Granite 4.1:3b inference drops from ~60-180s on CPU Basic to ~2-4s on
# nvidia-t4-small.
#
# Bakes:
#   - Python 3.10 (default on 22.04) + pip deps (~2.5 GB once torch is in)
#   - Ollama + granite4.1:3b model (~2 GB)
#   - All pre-computed fixtures in data/ + corpus/
#
# Runtime:
#   - Ollama daemon serves Granite 4.1 via CUDA
#   - Granite Embedding 278M auto-downloads via sentence-transformers
#     on first FastAPI startup (~280 MB)
#   - uvicorn FastAPI on port 7860 (HF Spaces default)

FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04 AS base

# OS deps: Python 3.10 + geo libs + Ollama install dependencies.
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv python-is-python3 \
        curl ca-certificates zstd procps \
        gdal-bin libgdal-dev libgeos-dev libproj-dev \
    && rm -rf /var/lib/apt/lists/*

# HF Spaces convention: run as a non-root "user" account at /home/user/app.
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:/usr/local/bin:/usr/bin:/bin \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/user/.cache/huggingface \
    OLLAMA_HOST=127.0.0.1:11434 \
    OLLAMA_NUM_PARALLEL=1 \
    OLLAMA_KEEP_ALIVE=24h \
    OLLAMA_MAX_LOADED_MODELS=2 \
    OLLAMA_FLASH_ATTENTION=1 \
    OLLAMA_KV_CACHE_TYPE=q8_0 \
    OLLAMA_DEBUG=1

# Install Ollama. install.sh ships the cuda_v12 dispatcher libs
# unconditionally; the GPU detection at the tail of the script only gates
# host-driver install (a no-op inside a container). So this works fine
# on a CPU builder for a GPU-attached runtime.
RUN curl -fsSL https://ollama.com/install.sh | sh

WORKDIR /home/user/app

# Python deps. CUDA 12.x in base image lets pip pull cu124 torch wheels
# automatically when sentence-transformers asks for torch.
COPY --chown=user:user requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# --- Earth-observation toolchain (Phase 1 Prithvi live + Phase 4
# TerraMind synthesis) ---------------------------------------------------
#
# Tried four times to land terratorch on HF's Py3.10 image alongside
# our pinned stack (transformers<5, hf_hub<1, granite-tsfm<0.3.4,
# mellea<0.4). Each attempt failed at the same point — a `mkdir`
# immediately after the --no-deps install — with no actionable error
# in HF's build log. The failure pattern is consistent with build-
# sandbox disk exhaustion; even a 4-package narrow install
# (terratorch + einops + diffusers + timm with --no-deps) hits it.
#
# Accepting this: TerraMind synthesis + Prithvi-live remain
# local-/AMD-only on this deployment. The lazy-import pattern in
# app/context/terramind_synthesis.py + app/flood_layers/prithvi_live.py
# returns clean `skipped: deps unavailable on this deployment` on HF;
# the trace card and the map legend make that visible. The other 14
# specialists run normally.
#
# Re-enable on a deployment with more build disk (Docker SDK on a
# self-hosted machine, AMD droplet, etc.) by adding the EO --no-deps
# install back here.

# Pull both Granite 4.1 variants into the image:
#   :3b — fast routing (planner) + live_now reconciler (short outputs)
#   :8b — synthesis reconciler for single_address / neighborhood / dev_check
# Both fit warm on the T4 with OLLAMA_MAX_LOADED_MODELS=2 (~10 GB total
# VRAM out of 16). We start ollama in the background, poll its HTTP
# endpoint, pull, and let the layer exit (Docker reaps the daemon —
# don't pkill, it'll match this RUN's own cmdline and exit 143).
ENV OLLAMA_MODELS=/home/user/.ollama/models \
    RIPRAP_OLLAMA_3B_TAG=granite4.1:8b
# Granite weights are pulled at *container start* (see entrypoint.sh)
# instead of at build time. HF's build sandbox can't fit the EO
# toolchain + Granite 8B (5GB) simultaneously, but the runtime
# rootfs is larger and persists between container starts within an
# image lifetime. Cold-start on first launch ~2 min for the 8B pull;
# subsequent restarts are fast since Ollama's cache survives.
RUN mkdir -p $OLLAMA_MODELS

# App code + fixtures
COPY --chown=user:user app/ ./app/
COPY --chown=user:user web/ ./web/
COPY --chown=user:user scripts/ ./scripts/
COPY --chown=user:user data/ ./data/
COPY --chown=user:user corpus/ ./corpus/
COPY --chown=user:user agent.py riprap.py ./
COPY --chown=user:user entrypoint.sh ./
RUN chmod +x ./entrypoint.sh

# Hand off to a non-root user the way HF Spaces expects
RUN chown -R user:user /home/user
USER user

EXPOSE 7860
CMD ["./entrypoint.sh"]
