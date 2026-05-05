# Riprap — Hugging Face Spaces (Docker SDK) deployment.
#
# CPU-tuned variant for HF Spaces cpu-basic (free tier). The
# nvidia-t4-small / MI300X variants live alongside as build args
# to switch when the Space is upgraded.
#
# Bakes:
#   - Python 3.12 + pip deps (~2.5 GB once torch is in)
#   - Ollama + granite4.1:3b model (~2 GB) — 3b only on cpu-basic.
#     RIPRAP_OLLAMA_8B_TAG=granite4.1:3b aliases the 8b reconciler
#     calls to 3b so the polished UI runs end-to-end without 8b's
#     ~5 GB image cost. Quality drops vs 8b; speed lever is the
#     vLLM-on-AMD-MI300X demo path (RIPRAP_LLM_PRIMARY=vllm).
#   - All pre-computed fixtures in data/ + corpus/
#
# Runtime:
#   - Ollama daemon serves Granite 4.1:3b
#   - Granite Embedding 278M auto-downloads via sentence-transformers
#     on first FastAPI startup (~280 MB) — cached to /home/user/.cache
#   - uvicorn FastAPI on port 7860 (HF default)

FROM python:3.12-slim AS base

# OS deps for geo libs + curl/zstd for Ollama installer (which now ships
# its tarball compressed with zstd and refuses to install if it's missing).
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates zstd procps \
        gdal-bin libgdal-dev libgeos-dev libproj-dev \
    && rm -rf /var/lib/apt/lists/*

# HF Spaces convention: run as a non-root "user" account at /home/user/app.
# Granite Embedding cache lives in /home/user/.cache/huggingface — it
# survives container restarts when persistent storage is mounted there.
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:/usr/local/bin:/usr/bin:/bin \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/user/.cache/huggingface \
    OLLAMA_HOST=127.0.0.1:11434 \
    OLLAMA_NUM_PARALLEL=1 \
    OLLAMA_KEEP_ALIVE=24h \
    RIPRAP_LLM_PRIMARY=ollama \
    RIPRAP_OLLAMA_8B_TAG=granite4.1:3b \
    RIPRAP_MELLEA_MAX_ATTEMPTS=2

# Install Ollama (single-binary install)
RUN curl -fsSL https://ollama.com/install.sh | sh

WORKDIR /home/user/app

# Python deps (cache the layer)
COPY --chown=user:user requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Pull Granite 4.1:3b into the image. The official Ollama installer
# stores models under /usr/share/ollama/.ollama by default; we point at a
# user-writable location so the runtime container can also serve.
#
# Pattern: start ollama serve in the background, poll its HTTP endpoint
# until it answers, then pull the model. We do NOT kill the daemon at the
# end — the RUN shell's exit reaps it automatically, and `pkill -f` would
# match this RUN command line itself (SIGTERM propagates up, build exits 143).
ENV OLLAMA_MODELS=/home/user/.ollama/models
RUN mkdir -p $OLLAMA_MODELS && \
    ollama serve > /tmp/ollama.log 2>&1 & \
    for i in $(seq 1 60); do \
        curl -sf http://127.0.0.1:11434/ > /dev/null 2>&1 && break; \
        sleep 1; \
    done && \
    ollama list && \
    ollama pull granite4.1:3b && \
    ollama list

# App code + fixtures
COPY --chown=user:user app/ ./app/
COPY --chown=user:user web/ ./web/
COPY --chown=user:user scripts/ ./scripts/
COPY --chown=user:user data/ ./data/
COPY --chown=user:user corpus/ ./corpus/
COPY --chown=user:user agent.py helios_nyc.py ./
COPY --chown=user:user entrypoint.sh ./
RUN chmod +x ./entrypoint.sh

# Hand off to a non-root user the way HF Spaces expects
RUN chown -R user:user /home/user
USER user

EXPOSE 7860
CMD ["./entrypoint.sh"]
