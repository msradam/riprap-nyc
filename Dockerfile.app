# Riprap — lightweight self-host image (FastAPI + SvelteKit).
#
# This is the "I want to run Riprap on my own machine, pointed at the
# live or my own MI300X" image. It does NOT ship Ollama, CUDA, or
# Granite weights — LLM inference is dispatched over HTTP via
# RIPRAP_LLM_BASE_URL (vLLM / OpenAI-compatible) and RIPRAP_ML_BASE_URL
# (the riprap-models GPU specialist service). See .env.example.
#
# For the heavy HF Space deployment (CUDA + bundled Ollama + Granite
# weights baked in), use the root-level Dockerfile instead.
#
# Build:    docker build -t msradam/riprap-nyc:v0.5.0 -f Dockerfile.app .
# Run:      docker run --rm -p 7860:7860 --env-file .env msradam/riprap-nyc:v0.5.0

# -----------------------------------------------------------------------
# Stage 1 — build the SvelteKit static bundle
# -----------------------------------------------------------------------
FROM node:20-slim AS frontend-build

WORKDIR /build
COPY web/sveltekit/package.json web/sveltekit/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY web/sveltekit/ ./
RUN npm run build

# -----------------------------------------------------------------------
# Stage 2 — Python runtime
# -----------------------------------------------------------------------
FROM python:3.10-slim AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Geo libs: geopandas / rasterio / fiona / pyproj need GDAL + GEOS +
# PROJ at runtime. curl for healthchecks.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates \
        gdal-bin libgdal-dev libgeos-dev libproj-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps first so a code-only edit doesn't bust the wheel cache.
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# App code + fixtures + corpus.
COPY app/ ./app/
COPY web/main.py ./web/main.py
COPY web/static/ ./web/static/
COPY scripts/ ./scripts/
COPY data/ ./data/
COPY corpus/ ./corpus/

# Pre-built SvelteKit bundle from stage 1.
COPY --from=frontend-build /build/build ./web/sveltekit/build

EXPOSE 7860

# Default talks to remote LLM + ML backends via the env vars in
# .env.example. RIPRAP_LLM_PRIMARY=vllm makes the LiteLLM Router
# expect an OpenAI-compatible endpoint at RIPRAP_LLM_BASE_URL.
ENV RIPRAP_LLM_PRIMARY=vllm \
    PYTHONPATH=/app

CMD ["uvicorn", "web.main:app", "--host", "0.0.0.0", "--port", "7860", \
     "--log-level", "info", "--proxy-headers"]
