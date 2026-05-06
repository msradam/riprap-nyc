# Code Morning Brief — 2026-05-06

Engineering pass: bug fixes + AMD GPU deploy. All fixes committed to `main`.

---

## Final state — end of day 2026-05-06

**5/5 address probe PASS on AMD MI300X vLLM path.**

```
[1/5] '442 East Houston Street, Manhattan'   PASS   9.8s  mellea=4/4 rerolls=1
[2/5] '80 Pioneer Street, Brooklyn'          PASS   7.0s  mellea=4/4 rerolls=0
[3/5] '100 Gold Street, Manhattan'           PASS  10.2s  mellea=4/4 rerolls=1
[4/5] 'Hollis, Queens'                       PASS   4.9s  mellea=4/4 rerolls=0
[5/5] 'Coney Island, Brooklyn'               PASS   4.3s  mellea=4/4 rerolls=0
```

Demo queries captured at `/tmp/gpu-demo-q01.json`, `/tmp/gpu-demo-q02.json`,
`/tmp/gpu-demo-q13.json` (q13 captured in earlier session).

---

## Bugs resolved

### 1. Graceful not_implemented for retrospective + ranking queries

**Files:** `app/planner.py`  — commit `d3fa102`

Pre-flight regex intercept before the LLM call short-circuits two
categories of queries that Riprap doesn't support and previously
silently misrouted:

- **Retrospective (q14/q18):** "What would Riprap have said on
  Hurricane Ida?", "What was the flood status as of August 2021?" →
  Returns `Plan(intent="not_implemented")` with a user-facing message.
- **Ranking (q15):** "Rank top 5 NYCHA buildings by flood exposure" →
  Same treatment.

`web/main.py` handles `not_implemented` in both the streaming
(`/api/agent/stream`) and non-streaming (`/api/agent`) paths — emits
the message as a `final` event with `status: "not_implemented"` and
zeroed Mellea fields. No LLM call is made.

### 2. [doc_id] placeholder leaking from reconcile prompt

**Files:** `app/mellea_validator.py`, `app/reconcile.py`  — commit `f68243b`

Root cause: `EXTRA_SYSTEM_PROMPT` used `[doc_id]` as an example
placeholder in the section skeleton. Granite echoed it literally.
Mellea's `citations_resolve` check then failed.

Two-part fix:
1. `mellea_validator.py` — added `[doc_id]` to `_check_no_placeholder_tokens`.
2. `reconcile.py` — rewrote `EXTRA_SYSTEM_PROMPT` to use real doc_id
   examples (`[sandy]`, `[nyc311]`, `[microtopo]`, etc.) instead of
   `[doc_id]` placeholders.

### 3. Geocoder fallback when Planning Labs API is down

**File:** `app/geocode.py`  — commit `70892d1`

NYC Planning Labs Geosearch (`geosearch.planninglabs.nyc`) returned
503 during the session. All single_address queries failed "no coords".

Fix: Added `try/except` around `geocode(text, limit=8)` in
`geocode_one()`. Any exception (503, connection error, timeout) now
falls back to Nominatim, matching the existing upstate-hint path.

### 4. STAC searches hang indefinitely without HTTP timeout

**Files:** `app/context/eo_chip_cache.py`, `app/flood_layers/prithvi_live.py`  — commit `70892d1`

`pystac_client` STAC searches and `rioxarray` COG downloads have no
per-request HTTP timeout; they hung indefinitely when Planetary Computer
was slow or unreachable.

Fix: Wrapped both `fetch()` functions in a
`concurrent.futures.ThreadPoolExecutor` with a hard wall-clock cap
(`timeout_s + 15 s`). The FSM step now always returns within budget
with `{"ok": False, "skipped": "timed out"}` on STAC hangs.

Controlled by existing `RIPRAP_EO_CHIP_ENABLE` / `RIPRAP_PRITHVI_LIVE_ENABLE`
env flags (default `1`). Set to `0` to skip STAC lookups entirely.

### 5. NYCHA/DOE/DOH registers hang on first query (91 MB polygon load)

**Files:** `app/fsm.py`, `web/main.py`  — commit `70892d1`

`app/registers/nycha.py:_load_sandy_2263()` loads the full 91 MB
`data/sandy_inundation.geojson` via geopandas on first call. GDAL's
polygon-organisation pass on that file triggers a "processing may be
really slow" path — 3–5 min on M3 local dev, making the first
single_address query appear hung.

Fix: Split nycha / doe_schools / doh_hospitals behind a new
`RIPRAP_NYCHA_REGISTERS` env flag (default `0`, independent of the
GPU-heavy `RIPRAP_HEAVY_SPECIALISTS` flag). When set to `1`,
`web/main.py` pre-warms the lru_caches at startup.

For the demo: nycha/doe/doh data is absent from the briefing (Pioneer
Street and Gold Street have no NYCHA developments in the 2000 m radius
anyway). Re-enable post-demo when the server has a 3-min startup budget.

### 6. riprap-models Dockerfile: ROCm torch replaced by CUDA torch

**File:** `services/riprap-models/Dockerfile`  — commits `488d524`, `8899d4a`

pip's resolver replaced the AMD ROCm `torch 2.9.1+git8907517` with CUDA
`torch 2.10.0` from PyPI. Fix: multi-stage build; Stage 1 captures clean
ROCm site-packages, Stage 2 installs deps, then COPY restores ROCm torch.
vLLM ENTRYPOINT conflict (`vllm: error: unrecognized arguments`) fixed by
`ENTRYPOINT []` in the Dockerfile.

---

## GPU deploy status

**Droplet:** `134.199.193.99` (AMD MI300X, DigitalOcean GPU)

| Container       | Image                             | Port | Status  |
|-----------------|-----------------------------------|------|---------|
| `vllm`          | `vllm/vllm-openai-rocm:v0.17.1`  | 8001 | Running |
| `riprap-models` | `riprap-models:latest`            | 7860 | Running |

vLLM serves `granite-4.1-8b` at `http://134.199.193.99:8001/v1`.
riprap-models correct embedding route: `/v1/granite-embed` (smoke test
script still lists `/v1/embedding` — fix documented in `OPEN-ISSUES.md`).

**Bearer token:** stored in `AMD_TOKEN` at repo root (gitignored).

---

## Environment variables

```bash
# Local dev → AMD GPU
export RIPRAP_LLM_PRIMARY=vllm
export RIPRAP_LLM_BASE_URL=http://134.199.193.99:8001/v1
export RIPRAP_LLM_API_KEY=$(cat AMD_TOKEN)
export RIPRAP_ML_BASE_URL=http://134.199.193.99:7860
export RIPRAP_ML_API_KEY=$(cat AMD_TOKEN)
export RIPRAP_EO_CHIP_ENABLE=0       # skip STAC lookups (Planetary Computer slow)
export RIPRAP_PRITHVI_LIVE_ENABLE=0  # skip STAC lookups
export RIPRAP_TERRAMIND_ENABLE=0     # skip DEM diffusion (slow on CPU)
# RIPRAP_NYCHA_REGISTERS defaults to 0 — don't set unless startup warmup is acceptable

.venv/bin/uvicorn web.main:app --host 127.0.0.1 --port 7861 --log-level info
```

HF Space env (huggingface-cli space variables):
```
RIPRAP_LLM_BASE_URL=http://134.199.193.99:8001/v1
RIPRAP_LLM_API_KEY=<token>
RIPRAP_ML_BASE_URL=http://134.199.193.99:7860
RIPRAP_ML_API_KEY=<token>
```

---

## How to verify

```bash
# 1. Smoke test
TOKEN=$(cat AMD_TOKEN)
scripts/smoke_test_gpu.sh 134.199.193.99 "$TOKEN"
# Expect: vllm_models PASS, vllm_chat_post PASS, models_health PASS,
#         models_granite_embed_post PASS (correct route: /v1/granite-embed)
#         vllm_chat GET FAIL (expected — GET is not a chat endpoint)

# 2. Full 5-address end-to-end probe via local server → AMD
RIPRAP_LLM_PRIMARY=vllm \
RIPRAP_LLM_BASE_URL=http://134.199.193.99:8001/v1 \
RIPRAP_LLM_API_KEY=$(cat AMD_TOKEN) \
RIPRAP_ML_BASE_URL=http://134.199.193.99:7860 \
RIPRAP_ML_API_KEY=$(cat AMD_TOKEN) \
RIPRAP_EO_CHIP_ENABLE=0 \
RIPRAP_PRITHVI_LIVE_ENABLE=0 \
RIPRAP_TERRAMIND_ENABLE=0 \
.venv/bin/python scripts/probe_addresses.py
# Want: 5/5 PASS

# 3. Manual vLLM smoke
curl -s -X POST http://134.199.193.99:8001/v1/chat/completions \
  -H "Authorization: Bearer $(cat AMD_TOKEN)" \
  -H "Content-Type: application/json" \
  -d '{"model":"granite-4.1-8b","messages":[{"role":"user","content":"Reply OK"}],"max_tokens":4}' \
  | python3 -m json.tool
```

---

## Droplet redeploy (if destroyed)

```bash
TOKEN=$(openssl rand -base64 24)
scripts/deploy_droplet.sh <new-ip> "$TOKEN"
# ~10-20 min on a fresh droplet
```

See `CLAUDE.md` → "Droplet redeploy" for full details.

---

## Open issues

See `OPEN-ISSUES.md`:
1. `experiments/` bugs (numpy annotation, f-string Py 3.12, closure loop, dead api)
2. `scripts/smoke_test_gpu.sh` tests `/v1/embedding` — correct route is `/v1/granite-embed`
3. NYCHA/DOE/DOH registers disabled by default — enable post-demo with `RIPRAP_NYCHA_REGISTERS=1` + startup warmup
