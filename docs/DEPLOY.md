# Deployment topology

Riprap is composed of two HF Spaces in production. The **UI Space**
is CPU-only and contains the FastAPI + SvelteKit front-end; the
**inference Space** is an L4 GPU and runs vLLM (Granite 4.1 8B FP8)
plus the EO model stack co-resident.

```
                ┌──────────────────────────────────────────────┐
                │   msradam/riprap-vllm  (NVIDIA L4, 24 GB)    │
                │                                              │
                │   :7860  proxy.py    bearer-auth FastAPI     │
                │      ├─ /v1/chat/* /v1/embeddings  → :8000   │
                │      └─ /v1/{prithvi,terramind,...} → :7861  │
                │      └─ /v1/power   NVML readings            │
                │                                              │
                │   :8000  vLLM  Granite 4.1 8B FP8            │
                │   :7861  riprap-models                       │
                │          Prithvi-EO 2.0 NYC-Pluvial          │
                │          TerraMind LULC + Buildings          │
                │          Granite TTM r2                      │
                │          GLiNER + Granite Embedding 278M     │
                └────────────────────▲─────────────────────────┘
                                     │ bearer-auth HTTPS
                                     │
       ┌─────────────────────────────┴──────────────────────────┐
       │  lablab-ai-amd-developer-hackathon/riprap-nyc          │
       │  Hackathon submission UI · cpu-basic                   │
       │                                                        │
       │  FastAPI (web/main.py)  +  SvelteKit static build      │
       │  Burr FSM (app/fsm.py)                                 │
       │                                                        │
       │  RIPRAP_LLM_BASE_URL = …/v1                            │
       │  RIPRAP_ML_BASE_URL  = …                               │
       └────────────────────────────────────────────────────────┘
```

The UI Space holds no GPU weights and contacts no commercial APIs.
Every model call routes through the bearer-authenticated proxy on
the inference Space.

---

## Hugging Face Spaces

### `lablab-ai-amd-developer-hackathon/riprap-nyc` — UI Space

The hackathon submission. CPU-basic tier. Image built from the root
`Dockerfile`. Holds no model weights — every inference call goes
remote via env vars.

**Required Space variables:**

```
RIPRAP_LLM_PRIMARY        = vllm
RIPRAP_LLM_BASE_URL       = https://msradam-riprap-vllm.hf.space/v1
RIPRAP_LLM_VLLM_8B_NAME   = granite4.1:8b
RIPRAP_ML_BACKEND         = remote
RIPRAP_ML_BASE_URL        = https://msradam-riprap-vllm.hf.space
RIPRAP_NYCHA_REGISTERS    = 1
RIPRAP_HEAVY_SPECIALISTS  = 1
RIPRAP_PRITHVI_LIVE_ENABLE= 1
RIPRAP_TERRAMIND_ENABLE   = 1
RIPRAP_EO_CHIP_ENABLE     = 1
```

**Required secrets** (set via Settings → Variables and secrets):

```
RIPRAP_LLM_API_KEY        bearer token shared with the inference Space
RIPRAP_ML_API_KEY         bearer token shared with the inference Space
HF_TOKEN                  for register / catalog downloads
```

### `msradam/riprap-vllm` — Inference Space

L4 (`l4x1`) tier. Image built from `inference-vllm/Dockerfile`.
Bakes Granite 4.1 8B FP8 weights and the EO model dependencies
(terratorch + peft + diffusers + segmentation-models-pytorch +
nvidia-ml-py for NVML power sampling).

**Required secret:**

```
RIPRAP_PROXY_TOKEN        bearer token; must match RIPRAP_LLM_API_KEY /
                          RIPRAP_ML_API_KEY on the UI Spaces
```

**Endpoints:**

| Path | Routes to | Notes |
|---|---|---|
| `POST /v1/chat/completions` | vLLM | Granite 4.1 8B FP8, OpenAI-compat |
| `POST /v1/completions` | vLLM | OpenAI-compat |
| `GET  /v1/models` | vLLM | served-model-name family |
| `POST /v1/embeddings` | riprap-models | Granite Embedding 278M |
| `POST /v1/prithvi-pluvial` | riprap-models | Prithvi-EO 2.0 NYC-Pluvial |
| `POST /v1/terramind` | riprap-models | TerraMind LULC / Buildings / synthesis |
| `POST /v1/ttm-forecast` | riprap-models | Granite TTM r2 + Battery surge |
| `POST /v1/gliner-extract` | riprap-models | GLiNER typed-entity |
| `GET  /v1/power` | proxy | Real NVML power (W) — see `docs/EMISSIONS.md` |
| `GET  /healthz` | proxy + both backends | Aggregates health status |

All `/v1/*` endpoints require `Authorization: Bearer <PROXY_TOKEN>`.
`/v1/power` and the bracket-sampling LLM client path are described
in [`docs/EMISSIONS.md`](EMISSIONS.md).

---

## Personal mirror — `msradam/riprap`

Self-contained L4 mirror that runs the full stack (UI + vLLM + EO
models) in a single container. Used for parallel demos when the
shared inference Space is busy. Built from `Dockerfile.l4`.

```bash
scripts/deploy_personal_space.sh
```

This is paused by default for the hackathon period to keep the L4
budget on the primary inference Space.

---

## Local development

### Pure local (Ollama)

```bash
uv venv && uv pip install -r requirements.txt
cd web/sveltekit && npm ci && npm run build && cd ../..
ollama pull granite4.1:3b
ollama pull granite4.1:8b
.venv/bin/uvicorn web.main:app --host 127.0.0.1 --port 7860
```

Visit `http://127.0.0.1:7860`. Inference runs locally — no GPU
power readings (the chip will display the data-sheet estimate with
a `~` icon).

### Local UI, remote inference

```bash
RIPRAP_LLM_PRIMARY=vllm \
RIPRAP_LLM_BASE_URL=https://msradam-riprap-vllm.hf.space/v1 \
RIPRAP_LLM_API_KEY=<token> \
RIPRAP_ML_BACKEND=remote \
RIPRAP_ML_BASE_URL=https://msradam-riprap-vllm.hf.space \
RIPRAP_ML_API_KEY=<token> \
.venv/bin/uvicorn web.main:app --host 127.0.0.1 --port 7860
```

Same flow as the hosted UI Space, but rendered locally. Real NVML
power readings come back through the proxy headers and bracket
samples just like in production.

---

## Deploy commands

| Target | Script | Notes |
|---|---|---|
| Inference Space (`msradam/riprap-vllm`) | `scripts/deploy_vllm_space.sh` | Orphan-branch push from `inference-vllm/` |
| UI Space (`lablab-ai-amd-developer-hackathon/riprap-nyc`) | cherry-pick onto `huggingface/main` then `git push huggingface` | HF Spaces' xet hook rejects pushes that walk through commits with binaries; cherry-picking from a clean ancestor avoids it |
| Personal mirror (`msradam/riprap`) | `scripts/deploy_personal_space.sh` | Orphan-branch push from `Dockerfile.l4` |
| Inference fallback (`msradam/riprap-inference`) | `scripts/deploy_inference_space.sh` | Ollama-backed mirror; redundant when riprap-vllm is up |

---

## Verifying a deploy

```bash
PYTHONPATH=. uv run python scripts/probe_stones_fire.py --timeout 600
```

Asserts: all five Stones fire, no torchvision/terratorch dep
regression, the `emissions` block reports `nvidia_l4` hardware, and
real NVML measurements come through (`n_measured` ≈ `n_calls`).

The address probe sweeps the full canonical set (5 NYC addresses):

```bash
.venv/bin/python scripts/probe_addresses.py \
    --base https://lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space
```

---

## Historical notes

The hackathon submission was originally built against an AMD MI300X
DigitalOcean droplet (running both vLLM and the EO model service).
The droplet was decommissioned **2026-05-06** and inference moved
to the L4 HF Spaces above. The bring-up runbook for the MI300X
droplet is preserved in [`docs/DROPLET-RUNBOOK.md`](DROPLET-RUNBOOK.md)
for anyone reproducing the original AMD-judging setup; setting
`RIPRAP_HARDWARE_LABEL=AMD MI300X` on a droplet redeploy will swap
the emissions ledger back to the MI300X data-sheet figures.
