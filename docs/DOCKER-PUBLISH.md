# Publishing the Riprap Docker images

The repo ships the build context for two images:

| Image | Dockerfile | Purpose |
|---|---|---|
| `msradam/riprap-nyc` | [`Dockerfile.app`](../Dockerfile.app) | Lightweight FastAPI + SvelteKit app. Talks to remote LLM/ML backends over HTTP. |
| `msradam/riprap-models` | [`services/riprap-models/Dockerfile`](../services/riprap-models/Dockerfile) | ROCm + PyTorch GPU specialist service (Prithvi, TerraMind, GLiNER, Granite Embed, TTM). |

There is also a third Dockerfile at the repo root (`Dockerfile`) — that
is the heavy HF Space image (CUDA + bundled Ollama + Granite weights).
It builds and ships automatically when the `huggingface` git remote is
pushed; **do not** publish it under `msradam/riprap-nyc` on Docker Hub
or GHCR, that name is reserved for the lightweight self-host image.

This document covers what was deferred from the v0.5.0 cleanup pass:
**actually building and pushing** the public Docker Hub / GHCR
artefacts. The compose file and `.env.example` are already in the repo
and reference the eventual `msradam/riprap-nyc:v0.5.0` tag.

---

## 1. Build locally

The build context has to be the repo root for both images, because
`services/riprap-models/Dockerfile` reaches up to grab
`services/riprap-models/main.py` and the requirements files.

```bash
cd $(git rev-parse --show-toplevel)

# Lightweight self-host image (linux/amd64 by default; pass
# --platform linux/arm64,linux/amd64 if you want a multi-arch
# manifest and have buildx + qemu set up).
docker build \
  -f Dockerfile.app \
  -t msradam/riprap-nyc:v0.5.0 \
  -t msradam/riprap-nyc:latest \
  .

# GPU specialist service. Requires a build host with at least
# ~30 GB free disk for the rocm/pytorch base + wheels.
docker build \
  -f services/riprap-models/Dockerfile \
  -t msradam/riprap-models:v0.5.0 \
  -t msradam/riprap-models:latest \
  .
```

Expected sizes:

- `riprap-nyc` ~1.4 GB (python:3.10-slim + GDAL + torch CPU + transformers)
- `riprap-models` ~12-15 GB (ROCm + torch dev build + terratorch chain)

---

## 2. Smoke-test the app image locally

```bash
cp .env.example .env
# fill .env with reachable RIPRAP_LLM_BASE_URL / RIPRAP_ML_BASE_URL.
# Easiest: point at the live HF Space's backends:
#   RIPRAP_LLM_PRIMARY=ollama
#   RIPRAP_LLM_BASE_URL=https://lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space
# (or your own droplet from docs/DROPLET-RUNBOOK.md).

docker compose up -d riprap-app
sleep 10

# Drive the SSE endpoint via curl
curl -sN "http://localhost:7860/api/agent/stream?q=80%20Pioneer%20Street%20Brooklyn" \
  --max-time 120 | head -40

# Or run the canonical 5-address probe against the container
RIPRAP_LLM_BASE_URL=http://localhost:7860 \
  .venv/bin/python scripts/probe_addresses.py --base http://localhost:7860
# Expect: 5/5 PASS.
```

Stop:

```bash
docker compose down
```

---

## 3. Push to Docker Hub

```bash
docker login -u msradam        # then enter the password / access token
docker push msradam/riprap-nyc:v0.5.0
docker push msradam/riprap-nyc:latest
docker push msradam/riprap-models:v0.5.0
docker push msradam/riprap-models:latest
```

If you'd rather use GitHub Container Registry instead:

```bash
echo "$GH_TOKEN" | docker login ghcr.io -u msradam --password-stdin
docker tag msradam/riprap-nyc:v0.5.0 ghcr.io/msradam/riprap-nyc:v0.5.0
docker tag msradam/riprap-nyc:latest ghcr.io/msradam/riprap-nyc:latest
docker push ghcr.io/msradam/riprap-nyc:v0.5.0
docker push ghcr.io/msradam/riprap-nyc:latest
docker tag msradam/riprap-models:v0.5.0 ghcr.io/msradam/riprap-models:v0.5.0
docker tag msradam/riprap-models:latest ghcr.io/msradam/riprap-models:latest
docker push ghcr.io/msradam/riprap-models:v0.5.0
docker push ghcr.io/msradam/riprap-models:latest
```

Required PAT scope for GHCR: `write:packages`.

---

## 4. After pushing — README updates

Once the v0.5.0 tag is live on Docker Hub, the existing
[`README.md`](../README.md) "Run locally" section already points at
the right tag — no further edits needed.

If you publish under a different namespace (a personal Hub account
you don't want to use long-term, etc.), update the `image:` line in
[`docker-compose.yml`](../docker-compose.yml) and the references in
the README.

---

## Status as of v0.5.0 tag (2026-05-07)

- `Dockerfile.app` and `services/riprap-models/Dockerfile` exist and
  the compose file references both with the correct image tags.
- The lightweight image was **not** pre-built or pushed during the
  cleanup pass — the build host (Apple Silicon laptop) had no Docker
  daemon running and a multi-gigabyte Apple-Silicon → linux/amd64
  build under QEMU would not finish inside the polish budget. Adam
  to run section 1 + 3 of this doc on a host with Docker before any
  external pull will succeed.
- `docker compose config` validates against the current compose file
  (verified via podman-compose during the cleanup).
