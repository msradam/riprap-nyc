# Riprap Models — droplet inference service.
#
# Self-contained ROCm + PyTorch image that runs every GPU-accelerable
# specialist Riprap consumes (Prithvi-NYC-Pluvial, TerraMind LULC +
# Buildings, Granite TTM r2, Granite Embedding 278M, GLiNER).
#
# Base: AMD's public ROCm 7.2.3 + Python 3.12 + PyTorch 2.9.1 release
# image. Same minor torch version as the bespoke MI300X image the
# bootstrap droplet was hand-built with (`torch==2.9.1+git8907517`),
# but pulled from a public registry so any fresh droplet can recreate
# the env without internal AMD wheels. The released 2.9.1 has the
# kernels we need — none of riprap-models calls into vLLM-specific
# attention paths, so the dev-build vs release-build delta is
# inconsequential for our forward passes.
#
# Build:    docker build -t riprap-models:latest -f Dockerfile ../..
# Layout:   the build context is the project root so the COPY lines
#           below can reach `services/riprap-models/`.
# Use the vLLM ROCm image as base — it ships torch 2.9.1+git8907517
# (the actual AMD bespoke build) and is already cached on DigitalOcean
# AMD GPU droplets, so no download is needed during bring-up.
# The public rocm/pytorch release image is a fallback if this image is
# not available; see the comment block above for background.
FROM vllm/vllm-openai-rocm:v0.17.1

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/root/.cache/huggingface \
    TRANSFORMERS_CACHE=/root/.cache/huggingface \
    # MI300X tuning the running container uses; baking them in so a
    # bring-up doesn't require remembering the env-set incantation.
    HIP_FORCE_DEV_KERNARG=1 \
    HSA_NO_SCRATCH_RECLAIM=1 \
    PYTORCH_ROCM_ARCH=gfx942

# git is needed by some HF model-card downloads (terratorch yaml repos
# pull via the git protocol). curl for healthcheck. libgl1 for
# rasterio's Pillow path. The base ROCm image is Ubuntu 24.04, and
# already includes most build-time deps we need.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl git libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/riprap-models

# Install deps in two layers so a code-only change doesn't bust the
# heavy ML wheel cache. requirements.txt holds runtime-narrow
# packages that the service imports; requirements-full.txt is the
# super-set the FSM specialists pull in transitively (terratorch's
# kornia / albumentations chain, granite-tsfm's tsfm_public, etc.).
COPY services/riprap-models/requirements-full.txt /tmp/req-full.txt
RUN pip install --upgrade pip && \
    # Freeze the ROCm torch/torchvision/torchaudio at whatever version
    # the vLLM base image ships, so transitive deps (peft, torchgeo, etc.)
    # don't pull a CUDA build from PyPI and replace the ROCm one.
    pip list --format=freeze > /tmp/all-pkgs.txt && \
    grep -E "^(torch|torchvision|torchaudio)==" /tmp/all-pkgs.txt > /tmp/torch-lock.txt && \
    cat /tmp/torch-lock.txt && \
    pip install -r /tmp/req-full.txt --constraint /tmp/torch-lock.txt

# Service code itself. Cheap to invalidate; lands last.
COPY services/riprap-models/main.py /workspace/riprap-models/main.py
COPY services/riprap-models/requirements.txt /workspace/riprap-models/requirements.txt

EXPOSE 7860

# Ensure we don't use the vLLM entrypoint.
ENTRYPOINT []

# `--proxy-headers` so a future LB sees the right client IP. The
# /healthz route is unauthenticated by design (operators want
# readiness probes to work without secrets); /v1/* requires the
# bearer token via RIPRAP_MODELS_API_KEY.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860", \
     "--log-level", "info", "--proxy-headers"]
