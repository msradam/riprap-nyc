# Riprap Inference Space — headless GPU API for both UI Spaces.
#
# Runs three things in one L4 container:
#   1. Ollama serving Granite 4.1 H-Small (Q4_K_M, ~5 GB) on :11434
#      with OpenAI-compat /v1 surface so vLLM-flavored clients work
#   2. riprap-models (Prithvi + TerraMind + TTM + GLiNER + Embedding) on :7861
#   3. FastAPI bearer-auth proxy on :7860 (HF Spaces public port) that
#      forwards /v1/chat/completions, /v1/embeddings → Ollama
#      and /v1/{prithvi,terramind,ttm,gliner,embed}      → riprap-models
#
# Both UI Spaces (lablab-ai-amd-developer-hackathon/riprap-nyc and
# msradam/riprap) point their RIPRAP_LLM_BASE_URL + RIPRAP_ML_BASE_URL
# at this Space's public URL with a shared bearer token.
#
# Why Ollama Q4 instead of vLLM BF16: an L4 has 24 GB VRAM. BF16
# Granite 4.1 8B (~16 GB) plus the EO model stack (~10 GB) plus vLLM
# KV cache exceeds that. Q4 quantized Granite (~5 GB) fits with the
# whole EO chain co-resident. The OpenAI /v1 surface means clients
# can't tell.

FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04 AS base

ENV DEBIAN_FRONTEND=noninteractive
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
    TRANSFORMERS_CACHE=/home/user/.cache/huggingface \
    OLLAMA_HOST=127.0.0.1:11434 \
    OLLAMA_NUM_PARALLEL=1 \
    OLLAMA_KEEP_ALIVE=24h \
    OLLAMA_MAX_LOADED_MODELS=2 \
    OLLAMA_FLASH_ATTENTION=1 \
    OLLAMA_KV_CACHE_TYPE=q8_0 \
    OLLAMA_MODELS=/home/user/.ollama/models

RUN curl -fsSL https://ollama.com/install.sh | sh

WORKDIR /home/user/app

# Proxy app deps (FastAPI + httpx) and riprap-models specialist deps.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        fastapi>=0.115 uvicorn[standard]>=0.32 httpx>=0.27 pydantic>=2.9

COPY services/riprap-models/requirements.txt /tmp/req-models.txt
RUN pip install --no-cache-dir -r /tmp/req-models.txt

# Heavier ML stack the riprap-models service needs at runtime. peft
# baked at build time (see Dockerfile.l4 for backstory). torchvision
# from the cu124 wheel index so it matches the base image's CUDA.
RUN pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cu124 \
        torchvision \
    && pip install --no-cache-dir \
        peft==0.18.1 \
        granite-tsfm==0.3.3 \
        "sentence-transformers>=3.3,<4" \
        "gliner>=0.2.6" \
        --index-url https://pypi.org/simple

# Bake Granite 4.1 weights at build. We pull two tags:
#   :3b — fast routing / planner
#   :8b — Capstone synthesis with Mellea rejection sampling
RUN mkdir -p $OLLAMA_MODELS && \
    ollama serve & \
    OPID=$! && \
    for i in $(seq 1 30); do curl -sf http://127.0.0.1:11434/ > /dev/null && break; sleep 1; done && \
    ollama pull granite4.1:8b && \
    ollama pull granite4.1:3b && \
    kill $OPID 2>/dev/null || true && \
    sleep 2

# Service code. The deploy script (scripts/deploy_inference_space.sh)
# moves inference/{proxy.py,entrypoint.sh,Dockerfile} to the repo root
# before pushing, so the COPY paths below are root-relative.
COPY services/riprap-models/main.py  ./riprap_models.py
COPY proxy.py                        ./proxy.py
COPY entrypoint.sh                   ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

RUN chown -R user:user /home/user
USER user

EXPOSE 7860
CMD ["./entrypoint.sh"]
