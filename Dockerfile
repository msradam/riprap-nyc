# Riprap — Hugging Face Spaces (Docker SDK) deployment.
#
# Bakes:
#   - Python 3.12 + pip deps (~2.5 GB once torch is in)
#   - Ollama + granite4.1:3b model (~2 GB)
#   - All pre-computed fixtures in data/ + corpus/
#
# Runtime:
#   - Ollama daemon serves Granite 4.1
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
    OLLAMA_NUM_PARALLEL=2 \
    OLLAMA_KEEP_ALIVE=24h

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
ENV OLLAMA_MODELS=/home/user/.ollama/models
RUN mkdir -p $OLLAMA_MODELS && \
    (ollama serve &) && \
    sleep 3 && \
    ollama pull granite4.1:3b && \
    sleep 1 && \
    pkill -f "ollama serve" || true

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
