# Droplet Runbook

_Last verified: 2026-05-09 (terramind synthesis + LoRA adapters confirmed firing live)_

> **Quick redeploy:** `HF_TOKEN=<write-token> scripts/redeploy.sh <new-droplet-ip>`
> generates a fresh bearer token, builds + brings up vLLM + riprap-models, updates
> the HF Space env vars, restarts the Space, and runs the end-to-end probe.
> Source-committed fixes (e.g. the May 9 terramind chip-tensor + synthesis
> patches) are inherited automatically because `deploy_droplet.sh` tars
> `services/riprap-models/` from this repo at run time.

## Spec

| Field | Value |
|-------|-------|
| Provider | DigitalOcean GPU Droplet (AMD Developer Cloud) |
| Droplet ID | 569363721 |
| Size slug | `gpu-mi300x1-192gb` (from hostname `0.17.1-gpu-mi300x1-192gb-devcloud-atl1`) |
| Region | `atl1` (Atlanta) |
| OS | Ubuntu 24.04.4 LTS |
| Kernel | 6.8.0-106-generic |
| Disk | 697 GiB root, 112 GiB used at inspection |
| RAM | 235 GiB |
| Swap | None |
| GPU | AMD Instinct MI300X VF (gfx942, model 0x74b5) |
| VRAM | 192 GiB (205,822,885,888 bytes) |
| ROCm SMI | 4.0.0+fc0010cf6a |
| ROCm lib | 7.8.0 (installed via `repo.radeon.com/rocm/apt/7.2`) |
| Docker | CE 29.4.2 (from official `download.docker.com/linux/ubuntu`) |

## Services

| Container | Image | Host Port | Container Port | Purpose |
|-----------|-------|-----------|----------------|---------|
| `vllm` | `vllm/vllm-openai-rocm:v0.17.1` | 8001 | 8000 | OpenAI-compatible LLM API (Granite 4.1 8B) |
| `riprap-models` | `riprap-models:latest` (local build) | 7860 | 7860 | GPU-specialist FastAPI service (Prithvi, TerraMind, GLiNER, Granite Embed, TTM) |

Both have `--restart unless-stopped`. Docker is systemd-enabled, so the full stack
auto-starts on reboot with no manual intervention.

A **Caddy** process runs natively (port 80, systemd service) configured to reverse-proxy
to `localhost:8888`. Nothing was listening on 8888 at inspection time — this appears to
be a leftover placeholder, not load-bearing for Riprap.

## Existing provisioning scripts

| Script | What it does | Status |
|--------|--------------|--------|
| `scripts/deploy_droplet.sh` | Full bring-up: SSH verify, pull vLLM image, tar-stream + build riprap-models, start both containers, healthcheck. Idempotent — removes and recreates containers on re-run. | **Complete.** The canonical bring-up script. |
| `scripts/smoke_test_gpu.sh` | 4-check smoke: vLLM /v1/models, vLLM /v1/chat/completions, riprap-models /healthz, riprap-models /v1/granite-embed, /v1/gliner-extract. | **Complete.** Run after deploy to confirm the stack is live. |
| `scripts/save_droplet_image.sh` | Commits the running container, saves + compresses to a local tarball via scp. Useful as a fallback if the public-base Dockerfile rebuild fails. | Complete but **moot** once the bootstrap droplet is destroyed — requires a live droplet to extract from. |
| `scripts/probe_addresses.py` | End-to-end test against `/api/agent/stream` on the HF Space. 5/5 must pass before merging. | Not a droplet-setup script; it tests the full system end-to-end. |

_Previously a gap; now landed:_ `scripts/update_hf_env.sh` automates updating HF
Space variables (`RIPRAP_LLM_BASE_URL`, `RIPRAP_ML_BASE_URL`, `RIPRAP_NYCHA_REGISTERS`,
etc.) and restarting the Space. `scripts/redeploy.sh` orchestrates the three-step
sequence (deploy droplet → update HF Space env → run end-to-end probe) into one
command.

**Gap:** No `redeploy.sh` wrapper exists. `deploy_droplet.sh` handles bring-up on a fresh
droplet but does not handle the HF Space variable update or the post-deploy probe run.
A `redeploy.sh` that chains `deploy_droplet.sh → huggingface-cli variables update →
probe_addresses.py` would complete the loop.

## Recreation steps

### 1. Provision the droplet

Use the DigitalOcean console or `doctl`. The exact size slug used was
`gpu-mi300x1-192gb`; pick `atl1` for the AMD Developer Cloud node type.

```bash
doctl compute droplet create riprap-gpu \
  --size gpu-mi300x1-192gb \
  --region atl1 \
  --image ubuntu-24-04-x64 \
  --ssh-keys <your-key-id>
```

Confirm `/dev/kfd` and `/dev/dri` are present before continuing:

```bash
ssh root@<new-ip> "ls /dev/kfd /dev/dri"
```

> **Note:** The AMD Developer Cloud GPU droplet image pre-installs ROCm and Docker.
> Steps 2–3 below document what was observed on the live system. On a fresh image from
> DigitalOcean's AMD GPU catalog they may already be satisfied — verify before running.

### 2. ROCm install

ROCm 7.2 was installed via the AMD repo. The following sources were present in
`/etc/apt/sources.list.d/`:

```
# /etc/apt/sources.list.d/rocm.list
deb [arch=amd64 signed-by=/etc/apt/keyrings/rocm.gpg] https://repo.radeon.com/rocm/apt/7.2 noble main

# /etc/apt/sources.list.d/amdgpu.list
deb [arch=amd64,i386 signed-by=/etc/apt/keyrings/rocm.gpg] https://repo.radeon.com/amdgpu/30.30/ubuntu noble main

# /etc/apt/sources.list.d/device-metrics-exporter.list
deb [arch=amd64 signed-by=/etc/apt/keyrings/rocm.gpg] https://repo.radeon.com/device-metrics-exporter/apt/1.4.0 noble main
```

Key packages confirmed installed (versions at inspection):

```
amdgpu-dkms          1:6.16.13.30300000-2278356.24.04
amdgpu-core          1:7.2.70200-2278374.24.04
hip-runtime-amd      7.2.26015.70200-43~24.04
hipblas              3.2.0.70200-43~24.04
hipblaslt            1.2.1.70200-43~24.04
hipcc                1.1.1.70200-43~24.04
hipfft               1.0.22.70200-43~24.04
hiprand              3.1.0.70200-43~24.04
hipsolver            3.2.0.70200-43~24.04
hipsparse            4.2.0.70200-43~24.04
```

**Gap:** The exact `amdgpu-install` invocation used to bootstrap the host ROCm install
was not captured (the AMD GPU droplet image likely pre-installs it via cloud-init).
If building on a bare Ubuntu 24.04 node, follow the [official ROCm 7.2 install guide](https://rocm.docs.amd.com/en/docs-7.2.0/deploy/linux/quick_start.html).

### 3. Docker install

Docker CE was installed from the official Docker apt repo:

```
# /etc/apt/sources.list.d/docker.list
deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu noble stable
```

Packages installed:

```
docker-ce              5:29.4.2-2~ubuntu.24.04~noble
docker-ce-cli          5:29.4.2-2~ubuntu.24.04~noble
docker-buildx-plugin   0.33.0-1~ubuntu.24.04~noble
docker-compose-plugin  5.1.3-1~ubuntu.24.04~noble
```

Docker is **systemd-enabled** — starts automatically on reboot.

Standard install steps if needed:

```bash
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | gpg --dearmor -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu noble stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli docker-compose-plugin
systemctl enable --now docker
```

### 4. Pull and launch vLLM

The full `docker run` reconstructed from live `docker inspect`:

```bash
TOKEN=<your-bearer-token>
HF_CACHE=/root/hf-cache

mkdir -p "$HF_CACHE"

docker run -d --name vllm \
  --device=/dev/kfd \
  --device=/dev/dri \
  --group-add video \
  --ipc=host \
  --shm-size=16g \
  -p 8001:8000 \
  -v "${HF_CACHE}:/root/.cache/huggingface" \
  -e GLOO_SOCKET_IFNAME=eth0 \
  -e VLLM_HOST_IP=127.0.0.1 \
  --restart unless-stopped \
  vllm/vllm-openai-rocm:v0.17.1 \
  --model ibm-granite/granite-4.1-8b \
  --host 0.0.0.0 \
  --port 8000 \
  --api-key "$TOKEN" \
  --max-model-len 8192 \
  --served-model-name granite-4.1-8b
```

**Observed startup behavior (from logs):**
- Architecture resolved as `GraniteForCausalLM` (vanilla decoder, no hybrid Mamba)
- dtype: `torch.bfloat16`
- tensor_parallel_size: 1, pipeline_parallel_size: 1, data_parallel_size: 1
- prefix caching: enabled, chunked prefill: enabled
- Model load: ~24 s, 16.46 GiB memory
- Graph capture: ~8 s, 0.45 GiB additional
- Total cold init: ~35 s from container start to API ready
- CUDA graph sizes: 51 sizes up to 512 tokens
- First-request ROCm kernel JIT can add 30–50 s; subsequent requests are 30–50× faster

**`GLOO_SOCKET_IFNAME=eth0` is required.** Without it gloo fails to bind and the engine
core never initialises. Do not remove this env var.

### 5. Build and launch riprap-models

Build the image from the repo source (do this from your local machine; `deploy_droplet.sh`
handles the tar-stream automatically):

```bash
# On the droplet after source is synced to /workspace/riprap-build:
cd /workspace/riprap-build && \
  docker build \
    -t riprap-models:latest \
    -f services/riprap-models/Dockerfile \
    .
```

Full `docker run` reconstructed from live `docker inspect`:

```bash
TOKEN=<your-bearer-token>   # same token as vLLM
HF_CACHE=/root/hf-cache

docker run -d --name riprap-models \
  --device=/dev/kfd \
  --device=/dev/dri \
  --group-add video \
  --ipc=host \
  --shm-size=8g \
  -p 7860:7860 \
  -v "${HF_CACHE}:/root/.cache/huggingface" \
  -e RIPRAP_MODELS_API_KEY="$TOKEN" \
  --restart unless-stopped \
  riprap-models:latest
```

Entrypoint: `uvicorn main:app --host 0.0.0.0 --port 7860 --log-level info --proxy-headers`

**Key environment variables baked into the image** (not injected at runtime, no override needed):

```
ROCM_PATH=/opt/rocm
LD_LIBRARY_PATH=/opt/rocm/lib:/usr/local/lib:
PYTORCH_ROCM_ARCH=gfx942
AITER_ROCM_ARCH=gfx942;gfx950
MORI_GPU_ARCHS=gfx942;gfx950
HSA_NO_SCRATCH_RECLAIM=1
TOKENIZERS_PARALLELISM=false
SAFETENSORS_FAST_GPU=1
HIP_FORCE_DEV_KERNARG=1
HF_HOME=/root/.cache/huggingface
TRANSFORMERS_CACHE=/root/.cache/huggingface
```

**Python packages confirmed on running container** (at inspection):

| Package | Version |
|---------|---------|
| torch | 2.10.0 (ROCm build) |
| transformers | 4.57.6 |
| terratorch | 1.2.7 |
| torchgeo | 0.9.0 |
| torchvision | 0.24.1+d801a34 |
| torchaudio | 2.9.0+eaa9e4e |
| granite-tsfm | 0.3.6 |
| gliner | 0.2.26 |
| sentence-transformers | 5.4.1 |
| timm | 1.0.25 |
| safetensors | 0.8.0rc0 |
| segmentation_models_pytorch | 0.5.0 |
| pytorch-lightning | 2.6.1 |
| huggingface_hub | 0.36.2 |

> **`safetensors==0.8.0rc0` is a release candidate.** If the Dockerfile build fails on
> a fresh droplet with a pip resolution error on this package, bump it to the nearest
> stable release in `services/riprap-models/requirements-full.txt`.

**test_transform patch:** The v2 datamodule `test_transform` patch was confirmed present
in the running container at `/app/vllm/examples/pooling/plugin/prithvi_geospatial_mae_offline.py`.

**First-request model download:** The HF cache at `/root/hf-cache` is a bind mount that
survives container recreation. On a fresh droplet with an empty cache, the first request
to each specialist triggers a ~12 GB model download. Steady-state requests reuse the
cached weights.

### 6. Firewall

UFW was active at inspection. The relevant rules:

```bash
ufw limit 22/tcp      # SSH: rate-limited
ufw allow 80/tcp      # Caddy (reverse proxy placeholder)
ufw allow 443         # HTTPS (currently unused)
ufw deny 6601         # Explicit block
ufw deny 50061        # Explicit block
```

UFW **default is allow incoming**, so ports 8001 (vLLM) and 7860 (riprap-models) are
reachable from the public internet without an explicit allow rule. If you want to
restrict access to the HF Space only, add:

```bash
# Allow only HF Space egress IPs (check current HF IP ranges first)
ufw default deny incoming
ufw allow from <hf-space-ip-range> to any port 8001
ufw allow from <hf-space-ip-range> to any port 7860
ufw allow 22/tcp
```

### 7. Startup behavior

**The stack auto-starts on reboot with no manual intervention:**

- `dockerd` is managed by systemd (`systemctl is-enabled docker → enabled`)
- Both `vllm` and `riprap-models` containers have `RestartPolicy: unless-stopped`
- On reboot: systemd starts Docker → Docker restarts both containers automatically

**After a manual `docker stop` (e.g., for maintenance):** The containers will NOT
auto-start because `unless-stopped` respects explicit stops. Restart manually:

```bash
docker start vllm riprap-models
```

**After a full reboot or Docker daemon restart:** Auto-start kicks in — no action needed.

**vLLM cold-start warning:** After any restart, vLLM takes ~35 s to become ready
(`/v1/models` returns 200). ROCm kernel compilation adds another 30–50 s of latency on
the very first inference request. The HF Space will see timeouts during this window.
The `deploy_droplet.sh` healthcheck loop waits up to 90 s for vLLM to become ready.

## Required secrets

The stack uses a single shared bearer token for both services:

| Env var / flag | Container | Set where |
|----------------|-----------|-----------|
| `--api-key <TOKEN>` | `vllm` | Passed in `docker run` command (visible in `docker inspect`) |
| `RIPRAP_MODELS_API_KEY=<TOKEN>` | `riprap-models` | Passed in `docker run -e` flag (visible in `docker inspect`) |

**No `.env` file exists at `/root/.env` or `/etc/riprap*`.** The token is stored only
in the running container configuration. To see the live token without SSHing:

```bash
ssh root@<droplet-ip> "docker inspect riprap-models | python3 -c \
  \"import sys,json; c=json.load(sys.stdin)[0]; \
  [print(e) for e in c['Config']['Env'] if 'API_KEY' in e]\""
```

**The HF Space must also know the token and the droplet's IP.** Set these Space
variables after every redeploy (new droplet = new IP and new token):

```bash
VLLM_PORT=8001
MODELS_PORT=7860
NEW_IP=<new-droplet-ip>
TOKEN=<new-bearer-token>

huggingface-cli space variables \
  lablab-ai-amd-developer-hackathon/riprap-nyc \
  RIPRAP_LLM_PRIMARY=vllm \
  RIPRAP_LLM_BASE_URL="http://${NEW_IP}:${VLLM_PORT}/v1" \
  RIPRAP_LLM_API_KEY="$TOKEN" \
  RIPRAP_ML_BACKEND=remote \
  RIPRAP_ML_BASE_URL="http://${NEW_IP}:${MODELS_PORT}" \
  RIPRAP_ML_API_KEY="$TOKEN" \
  RIPRAP_NYCHA_REGISTERS=1

huggingface-cli space restart lablab-ai-amd-developer-hackathon/riprap-nyc
```

`RIPRAP_NYCHA_REGISTERS=1` is required for the FSM to attach `step_nycha`,
`step_doe_schools`, `step_doh_hospitals` — without it, the Keystone Stone is
missing those three specialists in the per-query trace. (`scripts/update_hf_env.sh`
sets this automatically.)

## Health check

Two curl commands that confirm both services are live:

```bash
TOKEN=<your-bearer-token>
IP=134.199.193.99   # replace with new IP after redeploy

# vLLM — should return JSON with granite-4.1-8b in the model list
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://${IP}:8001/v1/models" | python3 -m json.tool

# riprap-models — should return {"ok": true, ...}
curl -s "http://${IP}:7860/healthz"
```

For a deeper check run the smoke-test script:

```bash
bash scripts/smoke_test_gpu.sh "$IP" "$TOKEN"
# Want: 4 PASS, 0 FAIL
```

For a full end-to-end check via the HF Space:

```bash
.venv/bin/python scripts/probe_addresses.py \
  --base https://lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space
# Want: 5/5 PASS
```

## Source-committed droplet fixes (May 9 2026)

Two patches landed in `services/riprap-models/main.py` after a live debugging
session against a running droplet. They are committed to source, so the next
`scripts/deploy_droplet.sh` (or `scripts/redeploy.sh`) bring-up will inherit
them automatically — the build context is tarred from this repo at run time.

| Patch | Problem | Fix |
|-------|---------|-----|
| `_build_chip_tensor` shape handling | The HF Space's `eo_chip_cache` ships chips at `(B, C, T, H, W)` 5-D; the droplet assumed `(C, H, W)` 3-D and called `.unsqueeze(1).repeat(1, 4, 1, 1)`, raising `RuntimeError: Number of dimensions of repeat dims can not be smaller than number of dimensions of tensor`. Every TerraMind LoRA request silently failed. | `_build_chip_tensor` now branches on `ndim`: 5-D passes through, 4-D adds batch, 3-D expands to T=4 and adds batch. |
| TerraMind synthesis remote dispatch | `_terramind_inference` only knew `lulc` / `buildings` adapters. `synthesis` (the IBM/NASA v1 base DEM→LULC generative path) had no remote handler, so the HF specialist always fell through to its local terratorch path and crashed on `torchvision::nms` (HF's CPU torch can't load torchvision's C extension). | `_TERRAMIND_SPECS["synthesis"]` + `_load_terramind_synthesis` (FULL_MODEL_REGISTRY build of `terratorch_terramind_v1_base_generate`) + `_terramind_synthesis_inference` (DEM-only 4-D input, 10-class ESRI LULC output). `TerramindIn` schema relaxed so `s2` is optional. |

After a destroy + redeploy you can verify both with:

```bash
# Beach Channel single-address — single_address full activation
.venv/bin/python scripts/probe_addresses.py \
  --base https://lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space \
  --addresses "2508 Beach Channel Drive, Queens" \
  --timeout 240
```

Want all three TerraMind paths firing in the trace (`terramind_lulc`,
`terramind_buildings`, `terramind_synthesis`) along with `prithvi_eo_live`
and `eo_chip_fetch`. All four EO specialists lazy-load on first request,
so the first probe pays cold-load (~30-90 s); subsequent probes are warm.

`save_droplet_image.sh` is complete but only useful while a working droplet is alive.
The bootstrap droplet was destroyed 2026-05-06; this script cannot recover from that.

## Destroy checklist

- [ ] Note the current `RIPRAP_MODELS_API_KEY` / vLLM `--api-key` value (or accept that
      you'll generate a fresh one on the next bring-up and update HF Space variables)
- [ ] Confirm the three NYC fine-tune artefacts exist on HF Hub (they do):
      `msradam/TerraMind-NYC-Adapters`, `msradam/Prithvi-EO-2.0-NYC-Pluvial`,
      `msradam/Granite-TTM-r2-Battery-Surge`
- [ ] Confirm no model weights exist only on the droplet — all are fetched from HF Hub
      on first request; the `/root/hf-cache` bind mount does NOT survive droplet deletion
- [ ] Run `bash scripts/smoke_test_gpu.sh <ip> <token>` one final time; record result
- [ ] Run `python scripts/probe_addresses.py` one final time; record result
- [ ] Update HF Space env vars to point at a new droplet OR confirm the Space gracefully
      falls back to Ollama (pill will turn amber)
- [ ] `doctl compute droplet delete 569363721` or destroy via DO console
- [ ] Verify HF Space is still serving after destroy:
      `curl -sf https://lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space/api/backend`
