# Riprap vLLM Space — primary inference backend (msradam/riprap-vllm).
#
# Same shape as the Ollama riprap-inference Space, but with vLLM
# serving Granite 4.1 8B FP8 natively on the L4. FP8 is hardware-
# supported on Ada Lovelace (L4 = sm_89), so no Marlin/AWQ kernels
# needed.
#
# Two backends:
#   - vLLM on :8000 — granite-4.1-8b-fp8, OpenAI-compatible
#   - riprap-models on :7861 — Prithvi/TerraMind/TTM/GLiNER/Embedding
# A FastAPI bearer-auth proxy on :7860 routes /v1/* to whichever
# backend serves it.
#
# VRAM budget on a 24 GB L4:
#   Granite 4.1 8B FP8        ~8 GB
#   vLLM KV cache (gpu_util)  ~3 GB
#   EO model stack            ~10 GB (Prithvi + TerraMind + TTM)
#   Headroom                  ~3 GB
# We cap vLLM at gpu_memory_utilization=0.55 so it doesn't grab the
# whole device.

# Ubuntu 24.04 ships Python 3.12; needed because terratorch 1.1rc6 pulls
# torchgeo>=0.7.0 which itself requires Python 3.11+. NVIDIA's earliest
# CUDA + ubuntu24.04 + cudnn tag is 12.6.0; CUDA 12.6 is forward-compat
# with the cu124 PyTorch wheels we install below.
FROM nvidia/cuda:12.6.3-cudnn-runtime-ubuntu24.04 AS base

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_BREAK_SYSTEM_PACKAGES=1
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv python-is-python3 \
        curl ca-certificates git zstd procps \
        gdal-bin libgdal-dev libgeos-dev libproj-dev \
        libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:/usr/local/bin:/usr/bin:/bin \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/user/.cache/huggingface \
    TRANSFORMERS_CACHE=/home/user/.cache/huggingface

WORKDIR /home/user/app

# vLLM brings its own torch / cu124. Pin a known-working version.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        vllm==0.7.3 \
        fastapi>=0.115 \
        uvicorn[standard]>=0.32 \
        httpx>=0.27 \
        pydantic>=2.9

# riprap-models specialist deps. Layered after vLLM so its torch wins.
COPY services/riprap-models/requirements.txt /tmp/req-models.txt
RUN pip install --no-cache-dir -r /tmp/req-models.txt

RUN pip install --no-cache-dir \
        peft==0.18.1 \
        granite-tsfm==0.3.3 \
        "sentence-transformers>=3.3,<4" \
        "gliner>=0.2.6" \
        torchvision

# Bake terratorch with its transitive deps at build time (vs the canonical
# entrypoint which runtime-installs with --no-deps to dodge the CPU Space's
# tight build sandbox). On L4 we have build room; full install lets all
# the EO probes work without dep-chase whack-a-mole.
RUN pip install --no-cache-dir \
        terratorch==1.1rc6 \
        einops diffusers timm \
        albumentations \
        segmentation-models-pytorch \
        kornia \
        tifffile

# Bake Granite 4.1 8B FP8 weights into the image (~8 GB). vLLM auto-
# detects the FP8 config in the model's config.json.
ENV VLLM_MODEL=ibm-granite/granite-4.1-8b-fp8
RUN python -c "from huggingface_hub import snapshot_download; \
    snapshot_download(repo_id='$VLLM_MODEL', cache_dir='/home/user/.cache/huggingface')"

# Service code. The deploy script moves these to the repo root.
COPY services/riprap-models/main.py  ./riprap_models.py
COPY proxy.py                        ./proxy.py
COPY entrypoint.sh                   ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

RUN chown -R user:user /home/user
USER user

EXPOSE 7860
CMD ["./entrypoint.sh"]
