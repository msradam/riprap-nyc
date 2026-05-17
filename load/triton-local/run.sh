#!/usr/bin/env bash
# Run Triton 25.05-py3 locally on M3 Mac (Docker + colima, no GPU) with
# granite_embed, gliner, ttm_forecast loaded.
#
# Uses the baked image `riprap-triton-baked:m3` once it exists (deps
# pre-installed → ~10 s startup), falling back to the base Triton image
# (full pip install → ~2 min startup).
#
# Ports: 8000 HTTP, 8001 gRPC, 8002 metrics. Stop with:
#     docker stop riprap-triton-local
set -euo pipefail

cd "$(dirname "$0")"
ROOT="$(pwd)"

IMAGE="nvcr.io/nvidia/tritonserver:25.05-py3"
if docker image inspect riprap-triton-baked:m3 > /dev/null 2>&1; then
    IMAGE="riprap-triton-baked:m3"
    echo "[run] using baked image: $IMAGE"
else
    echo "[run] using base image: $IMAGE (first boot, will install deps)"
fi

if docker ps -a --format '{{.Names}}' | grep -q '^riprap-triton-local$'; then
    docker rm -f riprap-triton-local 2>/dev/null || true
fi

docker run -d --name riprap-triton-local \
    --platform=linux/arm64 \
    -p 8000:8000 -p 8001:8001 -p 8002:8002 \
    -v "$ROOT/model_repository:/models:ro" \
    -v "$ROOT/hf_cache:/hf_cache" \
    -v "$ROOT/entrypoint.sh:/entrypoint.sh:ro" \
    --shm-size=2g \
    --memory=11g \
    --entrypoint=/entrypoint.sh \
    "$IMAGE"

echo "started riprap-triton-local; tail logs with:"
echo "    docker logs -f riprap-triton-local"
echo
echo "smoke test once 'Started HTTPService' appears:"
echo "    .venv/bin/python load/triton-local/test_granite_embed.py"
