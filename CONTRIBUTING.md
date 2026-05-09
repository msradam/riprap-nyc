# Contributing

Riprap is the hackathon submission for the AMD × lablab.ai
Developer Hackathon, but the source ships under Apache 2.0 and is
intended to be reusable as a template for citation-grounded civic
AI in any flood-vulnerable region. Pull requests welcome.

## Quickstart

Python 3.12 + `uv`:

```bash
git clone https://github.com/msradam/riprap-nyc
cd riprap-nyc
uv venv && uv pip install -r requirements.txt
```

SvelteKit (the build is committed; only rebuild when sources
change under `web/sveltekit/src`):

```bash
cd web/sveltekit && npm ci && npm run build && cd ../..
```

Run the dev server locally pointing at the production inference
Space (real Granite + EO models, real NVML energy readings):

```bash
RIPRAP_LLM_PRIMARY=vllm \
RIPRAP_LLM_BASE_URL=https://msradam-riprap-vllm.hf.space/v1 \
RIPRAP_LLM_API_KEY=<token> \
RIPRAP_ML_BACKEND=remote \
RIPRAP_ML_BASE_URL=https://msradam-riprap-vllm.hf.space \
RIPRAP_ML_API_KEY=<token> \
.venv/bin/uvicorn web.main:app --host 127.0.0.1 --port 7860
```

Or run pure-local with Ollama (no GPU readings; data-sheet estimate):

```bash
ollama pull granite4.1:3b granite4.1:8b
.venv/bin/uvicorn web.main:app --host 127.0.0.1 --port 7860
```

## Verifying changes

Two probe scripts exercise the live deployment end-to-end:

```bash
# All five Stones must fire on the canonical address; emissions
# block must carry nvidia_l4 hardware; no torchvision/terratorch
# dep regressions in the trace.
PYTHONPATH=. uv run python scripts/probe_stones_fire.py --timeout 600

# Full canonical suite — five NYC addresses, intent-aware checks,
# Mellea grounding budget, no specialist crashes.
.venv/bin/python scripts/probe_addresses.py \
    --base https://lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space
```

Both default to the lablab UI Space; pass `--base http://127.0.0.1:7860`
to hit a local server.

## Structure

```
app/                       Python package — the FSM and its specialists
├── fsm.py                 Burr FSM, one @action per probe
├── llm.py                 LiteLLM Router shim (Ollama / vLLM)
├── inference.py           HTTP client for the riprap-models service
├── emissions.py           Per-query energy + token tracker
├── stones/                Stone taxonomy (NAME / TAGLINE / collect())
├── flood_layers/          Cornerstone probes (sandy, dep, microtopo, …)
├── context/               Keystone + Touchstone register + EO probes
├── live/                  Lodestone forecast probes
├── intents/               single_address / neighborhood / compare / live_now
├── reconcile.py           Capstone — Granite-native document reconcile
└── mellea_validator.py    Mellea four-check rejection sampling

web/                       FastAPI + SvelteKit
├── main.py                FastAPI app, SSE streaming, layer endpoints
├── sveltekit/             Primary UI (adapter-static; build committed)
└── static/                Legacy custom-element pages (still mounted)

inference-vllm/            Inference Space source (vLLM + EO models + proxy)
├── Dockerfile             L4 image, bakes Granite 4.1 8B FP8 + EO deps
├── entrypoint.sh          Boots vllm, riprap-models, proxy as subprocesses
└── proxy.py               Bearer-auth + NVML power sampler + SSE pass-through

inference/                 Ollama-backed inference Space (fallback variant)
services/riprap-models/    The EO/forecast specialist HTTP service

scripts/
├── probe_stones_fire.py   Programmatic Stone-fire CI
├── probe_addresses.py     Canonical 5-address suite
├── deploy_vllm_space.sh   Deploy the L4 inference Space
├── deploy_personal_space.sh  Deploy the personal L4 mirror
├── deploy_inference_space.sh Deploy the Ollama-backed inference Space
└── …                       Register builders, raster bakers, etc.

experiments/               Reproduction recipes for the three NYC fine-tunes
docs/                      Architecture, methodology, deploy, emissions, runbooks
tests/                     pytest suite (envelope + compare-shape tests)
```

## Style

- Python 3.12; `uv` for package management.
- LLM calls go through `app/llm.py` — never import `litellm` /
  `ollama` directly from a specialist. The `chat()` shim wraps both
  backends and the energy ledger reads off it.
- Remote ML calls go through `app/inference.py::_post`. Specialists
  may try local fallback only when `inference.remote_enabled()` is
  False; once a remote call has been attempted, return a clean
  `{ok: False, skipped: ...}` on failure rather than crashing
  through to local code paths that may not be installed.
- Every specialist emits one trace record per call with `step` /
  `ok` / `elapsed_s` / `result` / `err` so the SSE stream and the
  emissions tracker can reason about it.

## Reporting issues

GitHub issues at <https://github.com/msradam/riprap-nyc/issues>.
For hackathon-period demo issues during May 4–10 2026, the live
deploy at
<https://lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space>
is the source of truth.
