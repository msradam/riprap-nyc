# Deploying Riprap on a Raspberry Pi

Three shapes, in increasing operational complexity. Pick by what the
deployment needs to do — the architecture supports all three from the
same code.

## Shape A — no-LLM mode (Pi Zero 2 W and up)

The smallest LLM-free deployment. **Disables both Granite calls** — the
planner (replaced with a regex heuristic) and the reconciler (replaced
with deterministic prose synthesized from manifest narration templates).
**Specialist ML still runs** — Prithvi-EO satellite segmentation,
TerraMind LULC / buildings, TTM time-series forecasts, GLiNER entity
extraction, RAG sentence-transformer embeddings — those are data
producers, not the prose layer, so they populate state and the
dashboards regardless of LLM mode.

Every claim is citation-grounded by construction. All 13 compliance
predicates pass.

```bash
git clone https://github.com/msradam/riprap-nyc.git
cd riprap-nyc
RIPRAP_RECONCILER_TIER=no_llm \
docker compose up -d
```

Open `http://<pi-ip>:7860/`. Use this shape for:

- Civic-tech audit / reproducibility demos
- Field deployments without connectivity for inference
- NGO co-locations with no GPU budget
- Cold-start defaults before any model is configured

Briefing wall-time: ~30–60 s, dominated by live HTTP probes (NOAA
tides, NWS, FloodNet) and specialist-ML pebbles. No Granite tokens
generated, ever.

The briefing gives the **standard info for that address** — sandy zone
status, DEP modeled flooding, Ida high-water marks, current tide,
NWS observations, NPCC4 sea-level rise projections, NYC 311 complaint
counts, FloodNet sensor readings. It does **not** answer
query-specific questions ("write me a screening", "compare these two
sites") — those need the LLM tier.

## Shape B — Granite 3B reconciler via Ollama (Pi 5 8 GB recommended)

Adds the LLM tier with Granite 4.1:3b for query-specific prose.
Ollama supports ARM64 natively; no Triton needed; the simplest LLM
deployment for the Pi class.

```bash
docker compose --profile local-llm up -d
docker compose exec ollama ollama pull granite4.1:3b
```

Set in `.env`:

```bash
RIPRAP_RECONCILER_TIER=llm
RIPRAP_RECONCILER_MODEL=granite4.1:3b
RIPRAP_LLM_PRIMARY=ollama
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_NUM_PARALLEL=2          # Pi has finite RAM; 2 slots is comfortable
```

**Memory budget** (Pi 5 8 GB):

| Component | RAM |
|---|---|
| OS + Riprap app + SvelteKit assets | ~1.5 GB |
| Ollama + Granite 4.1:3b loaded | ~3 GB |
| KV cache (2 parallel slots × 4K ctx) | ~1 GB |
| Pebble data (geojson + small rasters in lru_cache) | ~1 GB |
| Headroom | ~1.5 GB |

Briefing wall-time on Pi 5: **~60–90 s** (Granite 3B reconcile is the
ceiling). The pebble fan-out itself runs in 5–10 s.

## Shape C — Triton Inference Server on Pi (multi-model unification)

For deployments that already standardize on Triton's API across hosts
(MI300X production, L4 dev, Pi field), this serves the LLM via the
same gRPC/HTTP interface as the larger boxes.

### Why Triton on a Pi at all

Not because Triton is faster — it isn't, on a CPU. The argument is
**operational uniformity**: identical model_repository layout +
identical client code from Pi → laptop → MI300X. When a probe needs
a specialist model (Prithvi-Lite, GLiNER-tiny), it goes through the
same Triton API regardless of host.

### Stack

- Triton Inference Server (ARM64 build, `nvcr.io/nvidia/tritonserver:24.10-py3` or newer with ARM support)
- Python backend wrapping `llama-cpp-python` for Granite 3B GGUF
- Optionally, ONNX runtime backends for any pebble-side ML the
  deployment ships (most NYC pebbles are pure-geospatial and don't need this)

The Triton model_repository for the Granite reconciler lives in the
companion repo (separate because it's deployment-scoped, not part of
Riprap core): [msradam/riprap-triton](https://github.com/msradam/riprap-triton).

### Reference layout

```
riprap-triton-pi/
  Dockerfile.pi
  model_repository/
    granite_reconciler/
      config.pbtxt           # backend: python, max_batch_size: 1
      1/
        model.py             # wraps llama-cpp-python.Llama
        granite4.1-3b.gguf   # Q4_K_M quant, ~2 GB
    granite_planner/
      config.pbtxt           # same backend, smaller ctx
      1/
        model.py
```

### Wiring to Riprap

Triton's HTTP server exposes an OpenAI-compatible endpoint via the
`openai` backend wrapper. Point Riprap's LiteLLM router at it:

```bash
RIPRAP_LLM_PRIMARY=vllm                    # use the "OpenAI-compatible" path
RIPRAP_LLM_BASE_URL=http://triton:8000/v1  # Triton's HTTP server
RIPRAP_RECONCILER_MODEL=granite4.1:3b
```

### Reality check

Triton on a Pi adds operational overhead (a second container, the
Triton runtime, the Python backend's Python-process-per-instance
cost) for marginal benefit over running Ollama directly. **Shape B is
the right default; Shape C is for the operator who already runs
Triton elsewhere and wants one model-serving API across the fleet.**

## Picking a shape

| Constraint | Shape |
|---|---|
| No GPU, no LLM, sub-second briefings, audit-grade trust | A (templated) |
| Pi 5, query-specific prose, single user / low concurrency | B (Ollama + Granite 3B) |
| Already running Triton in production, want one API | C (Triton + Granite 3B) |
| Cluster of Pis sharing one LLM | B/C with one host running Ollama or Triton |

## Per-shape compliance scores

All three shapes ship with the briefing-standards predicates wired in
(see `docs/briefing-standards.md`). Measurements from a single run on
`189 Atlantic Ave, Brooklyn` (laptop, M3 Pro, Ollama):

| Shape | Compliance | Briefing wall-time | Prose quality |
|---|---|---|---|
| A — no-LLM mode                | **13 / 13** | ~60 s | Standard address info, slot-filled, every claim cited |
| B — Granite 8B-q3 / Ollama     | 12 / 13      | ~80 s | Analytic; misses one citation density check |
| B — Granite 3B / Ollama        | 7 / 13       | ~160 s (cold) / ~80 s (warm) | Analytic but skips the boilerplate-disclaimer prompt instructions |
| C — Granite 3B / Triton on Pi  | 7 / 13 *(estimated, same model)* | ~120 s + Triton overhead | Same content as Shape B 3B |

**The 3B-LLM-tier deserves a real caveat.** It produces analytic content
(matched 8B's depth on the parts it covered) but consistently failed
the scope-declaration, automation-disclosure, and informational-
disclaimer predicates that the 8B model and the templated tier both
pass. Smaller models follow long multi-part prompt instructions less
reliably.

**Pi recommendation:** start with **Shape A (templated)** — it's the
only configuration that guarantees the compliance bar on a Pi today.
Move to Shape B only when prompt-tuning + the Mellea-compliance
integration (see TODO in `riprap/core/compliance/__init__.py`) closes
the 3B → 13/13 gap reliably.

## Open hardware testing

The Pi numbers above are **untested on hardware**. Before claiming
these in the README, run:

```bash
# On the Pi
docker compose --profile local-llm up -d
docker compose exec ollama ollama pull granite4.1:3b
.venv/bin/python scripts/probe_addresses.py --base http://localhost:7860
```

and capture the wall-times + compliance scores into `docs/deployment-pi-results.md`.
