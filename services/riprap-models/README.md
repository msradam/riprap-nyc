# Riprap Models: droplet inference service

GPU inference microservice that runs alongside vLLM on the AMD MI300X
droplet. Exposes one HTTP endpoint per model class consumed by the
Riprap FastAPI app's probes, so all GPU-accelerable forward passes
(Prithvi-NYC-Pluvial, TerraMind LULC + Buildings, Granite TTM r2,
Granite Embedding 278M, GLiNER) run on the MI300X regardless of
which surface (laptop or HF Space) hosts the FastAPI process.

## Service contract

| Method | Path | Purpose |
|---|---|---|
| GET   | `/healthz`            | reachability probe + which models are warm |
| POST  | `/v1/prithvi-pluvial` | Prithvi-NYC-Pluvial v2 segmentation |
| POST  | `/v1/terramind`       | TerraMind LULC / Buildings / Synthesis (adapter-dispatched) |
| POST  | `/v1/ttm-forecast`    | Granite TTM r2 (zero-shot Battery, fine-tune Battery, weekly 311, FloodNet recurrence) |
| POST  | `/v1/granite-embed`   | Granite Embedding 278M batch encode |
| POST  | `/v1/gliner-extract`  | GLiNER typed-entity extraction |

Auth: bearer token on every `/v1/*` route via `RIPRAP_MODELS_API_KEY`.
Same shape as vLLM. `/healthz` is open so liveness probes don't need
auth.

## Deploy: fresh droplet (recommended)

Use the one-shot bring-up script. Works on any AMD ROCm GPU droplet
with Docker + GPU device files (`/dev/kfd`, `/dev/dri`) and SSH root
access. No prior container state required.

```bash
scripts/deploy_droplet.sh <droplet-ip> <bearer-token>
```

What it does, in order:

1. Verifies SSH + AMD GPU device files on the droplet
2. Pulls `vllm/vllm-openai-rocm:v0.17.1`
3. Tar-streams `services/riprap-models/` to `/workspace/riprap-build`
4. Builds `riprap-models:latest` from `services/riprap-models/Dockerfile`
   (base: `rocm/pytorch:rocm7.2.3_ubuntu24.04_py3.12_pytorch_release_2.9.1`,
   ~10–20 min on first build, < 1 min on rebuild)
5. Starts both containers (`vllm` on host port 8001, `riprap-models`
   on host port 7860) with `--restart unless-stopped` so they survive
   reboots
6. Waits up to 90 s for vLLM `/v1/models` and 60 s for
   riprap-models `/healthz`, exits non-zero if either misses

Re-running on the same droplet is idempotent. Existing containers
get `docker rm -f`'d and recreated.

Env knobs:

| Var | Default | Purpose |
|---|---|---|
| `SSH_USER` | `root` | SSH login |
| `SSH_KEY` | (ssh-agent) | path to private key |
| `VLLM_PORT` | `8001` | host port mapping for vLLM |
| `MODELS_PORT` | `7860` | host port mapping for riprap-models |
| `MODEL_REPO` | `ibm-granite/granite-4.1-8b` | LLM repo |
| `HF_CACHE_HOST` | `/root/hf-cache` | HF cache mount on droplet |
| `SKIP_BUILD` | `0` | set `1` to skip Dockerfile build |

After it returns, set the printed env vars in your local shell or HF
Space variables, run `scripts/probe_addresses.py` to verify, and
you're live.

## Deploy: extend an existing container (legacy)

If you already have a `terramind` container with the heavy ML deps
baked in (the bootstrap-droplet path), you can skip the Dockerfile
build and install the runtime deltas only:

```bash
ssh root@<ip> 'mkdir -p /workspace/riprap-models'
rsync -av --delete services/riprap-models/ root@<ip>:/workspace/riprap-models/
ssh root@<ip> bash <<'REMOTE'
docker cp /workspace/riprap-models terramind:/workspace/
docker exec -d -e RIPRAP_MODELS_API_KEY="$TOKEN" terramind \
  bash -c "cd /workspace/riprap-models && \
           pip install --no-cache-dir -r requirements.txt && \
           uvicorn main:app --host 0.0.0.0 --port 7860"
REMOTE
```

This path uses `requirements.txt` (deltas only); the Dockerfile path
above uses `requirements-full.txt` (everything). Service is
externally reachable at `http://<droplet-ip>:7860` once the host port
mapping was set when the container was created.

## Destroy + redeploy runbook

What survives a droplet destruction:

- `services/riprap-models/Dockerfile` plus `requirements-full.txt`.
  Every pinned dep, captured from the bootstrap droplet on
  2026-05-05.
- `scripts/deploy_droplet.sh`. The bring-up script.
- HF Hub model artefacts. Every fine-tune lives at
  `msradam/Prithvi-EO-2.0-NYC-Pluvial`,
  `msradam/TerraMind-NYC-Adapters`,
  `msradam/Granite-TTM-r2-Battery-Surge`. The Dockerfile pulls them
  fresh on first request

What does NOT survive:

- The HF cache at `${HF_CACHE_HOST}` (default `/root/hf-cache`) on
  the droplet. Every redeploy re-downloads around 12 GB of weights
  (Granite 4.1 8b for vLLM around 16 GB, Prithvi v2 around 1.3 GB,
  TerraMind adapters around 600 MB, Granite Embedding around 600 MB,
  GLiNER around 400 MB, Granite TTM r2 around 6 MB). First query
  after redeploy takes around 30 s longer than steady-state because
  of the lazy model load.
- The bearer token. Generate a fresh one when re-deploying.

To redeploy:

```bash
# 1. Spin up a new GPU droplet (DigitalOcean / AMD Developer Cloud)
# 2. Copy your SSH key to it (DO usually does this for you)
# 3. Run:
TOKEN=$(openssl rand -base64 24)
scripts/deploy_droplet.sh <new-ip> "$TOKEN"

# 4. Update HF Space env vars to point at the new IP
huggingface-cli space variables \
  lablab-ai-amd-developer-hackathon/riprap-nyc \
  RIPRAP_LLM_BASE_URL=http://<new-ip>:8001/v1 \
  RIPRAP_LLM_API_KEY=$TOKEN \
  RIPRAP_ML_BASE_URL=http://<new-ip>:7860 \
  RIPRAP_ML_API_KEY=$TOKEN

# 5. Restart the HF Space so it picks up the new env vars
huggingface-cli space restart lablab-ai-amd-developer-hackathon/riprap-nyc

# 6. Verify end-to-end against the redeployed stack
.venv/bin/python scripts/probe_addresses.py \
  --base https://lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space
```

## Local app config

Set in either env or HF Space variables:

```
RIPRAP_ML_BACKEND   = remote
RIPRAP_ML_BASE_URL  = http://129.212.181.238:7860
RIPRAP_ML_API_KEY   = <bearer>
```

`app/inference.py` posts to those endpoints; specialists fall back
to local in-process model loads when the service is unreachable.
