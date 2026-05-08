---
title: Riprap Nyc
emoji: 😻
colorFrom: red
colorTo: yellow
sdk: docker
pinned: false
---

<p align="left">
  <img src="assets/logo@2x.png" width="72" height="72" alt="Riprap dam mark" />
</p>

# Riprap

## Flood risk analysis for any NYC address.

Powered by a multi-agent AI system that reads satellites, watches
sensors, forecasts surges, and refuses to stay silent.

![Riprap flood-exposure briefing for 80 Pioneer Street, Brooklyn](assets/screenshots/hero.png)

Live demo: <https://lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space>

---

## Quickstart

Three ways to use Riprap, in increasing order of self-host:

### 1. Try the live demo

The hosted Space runs the full pipeline against a live AMD MI300X
inference backend. Type any NYC address.

<https://lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space>

### 2. Run locally with Docker

```bash
git clone https://github.com/msradam/riprap-nyc
cd riprap-nyc
cp .env.example .env
# edit .env to point RIPRAP_LLM_BASE_URL / RIPRAP_ML_BASE_URL at
# either the live demo's backends or your own self-hosted instance
docker compose up
```

Visit `http://localhost:7860`.

To self-host the GPU inference half (vLLM + the ML specialist
service) on an AMD ROCm or NVIDIA CUDA box, run:

```bash
docker compose --profile with-models up
```

Full single-command MI300X bring-up via DigitalOcean: see
[`docs/DROPLET-RUNBOOK.md`](docs/DROPLET-RUNBOOK.md).

### 3. Develop

```bash
# Python 3.12 venv via uv
uv venv && uv pip install -r requirements.txt

# SvelteKit frontend (committed pre-built; only rebuild if sources change)
cd web/sveltekit && npm ci && npm run build && cd ../..

# Local server (Ollama primary)
.venv/bin/uvicorn web.main:app --host 127.0.0.1 --port 7860

# Local server pointed at AMD MI300X (vLLM primary, Ollama fallback)
RIPRAP_LLM_PRIMARY=vllm \
RIPRAP_LLM_BASE_URL=http://<droplet-ip>:8000/v1 \
RIPRAP_LLM_API_KEY=<token> \
.venv/bin/uvicorn web.main:app --host 127.0.0.1 --port 7860

# End-to-end address suite (5 NYC addresses, intent-aware checks)
.venv/bin/python scripts/probe_addresses.py
```

---

## How Riprap works: the Five Stones

Behind every briefing, around 25 atomic data probes fan out across NYC
datasets, satellite imagery, sensors, and forecasts. The **Five Stones**
group those probes into five legible roles:

> **Cornerstone** remembers. **Keystone** tallies. **Touchstone**
> watches. **Lodestone** projects. **Capstone** writes it all down with
> citations.

| Stone | Role | What fires |
|---|---|---|
| **Cornerstone** | The Hazard Reader. What NYC's ground remembers. | Sandy 2012 inundation extent, NYC DEP stormwater scenarios, 2021 Ida USGS high-water marks, baked Prithvi-EO Ida-attributable polygons, USGS 3DEP DEM + HAND/TWI |
| **Keystone** | The Asset Register. What's exposed. | MTA subway entrances, NYCHA developments, NYC DOE schools, NYS DOH hospitals, **TerraMind-NYC Buildings LoRA** |
| **Touchstone** | The Live Observer. Current state of the city. | FloodNet ultrasonic depth sensors, NYC 311 flood complaints, NWS hourly METAR, NOAA tide-gauge water levels, **Prithvi-EO 2.0 NYC-Pluvial v2**, **TerraMind-NYC LULC LoRA** |
| **Lodestone** | The Projector. What's coming. | NWS public flood alerts, Granite TTM r2 surge nowcast (zero-shot, 6-min cadence, 9.6 h horizon), per-address 311 weekly forecast, FloodNet sensor recurrence forecast, **Granite-TTM-r2-Battery-Surge fine-tune** (96 h hourly horizon) |
| **Capstone** | The Synthesiser. Citation-grounded briefing. | Granite 4.1 + Mellea rejection sampling |

The four data-Stones run sequentially per query; the Capstone
reconciles their documents into one cited paragraph.

---

## NYC-specialised foundation models (Apache 2.0)

Three NYC-specific fine-tunes built on AMD Instinct MI300X via AMD
Developer Cloud, published under permissive licence.

**[`msradam/TerraMind-NYC-Adapters`](https://huggingface.co/msradam/TerraMind-NYC-Adapters).**
LoRA family on TerraMind 1.0 base. LULC mIoU 0.5866 (+6.13 pp over
full-FT baseline), TiM 0.6023, Buildings 0.5511. Trained in around 18
minutes on a single MI300X.

**[`msradam/Prithvi-EO-2.0-NYC-Pluvial`](https://huggingface.co/msradam/Prithvi-EO-2.0-NYC-Pluvial).**
NYC pluvial-flood fine-tune of Prithvi-EO 2.0. Test flood IoU 0.5979
vs 0.10 on the Sen1Floods11 base, a 6× lift. Lovász-Softmax loss with
copy-paste augmentation.

**[`msradam/Granite-TTM-r2-Battery-Surge`](https://huggingface.co/msradam/Granite-TTM-r2-Battery-Surge).**
NYC Battery storm-surge nowcast fine-tune of Granite TimeSeries TTM
r2. Test MAE 0.1091 m, −41% vs persistence and −25% vs zero-shot.

All three are loaded at runtime by their respective FSM probes in
`app/context/` and `app/live/`. Reproduction recipes live under
`experiments/18..21/`.

---

## Architecture

```
NYC address ──► Granite 4.1 3B planner ──► Plan{intent, targets, specialists}
                                                  │
                                                  ▼
                            Five-Stone Burr FSM (one @action per probe)
                            ┌───────────┬───────────┬───────────┬──────────┐
                            ▼           ▼           ▼           ▼          ▼
                       Cornerstone  Keystone   Touchstone   Lodestone  (cont.)
                       (hazard)    (assets)    (live)       (forecast)
                            │           │           │           │
                            └───────────┴─────┬─────┴───────────┘
                                              ▼
                         build_documents() — Granite-native
                         role="document <doc_id>" messages
                                              ▼
                  Capstone: Granite 4.1 8B + Mellea rejection sampling
                  ──► 4-check grounding loop, surgical feedback rerolls
                                              ▼
                       Four-section briefing with [doc_id] citations
                                              ▼
                       SSE stream → SvelteKit UI (briefing, trace, map)
```

LLM inference is dispatched through `app/llm.py`, a LiteLLM Router
shim with two backends: **Ollama** (T4 / local) and **vLLM** (AMD
MI300X). Same `chat()` signature in both directions; vLLM is primary
for the demo, Ollama is the auto-failover.

Source-of-truth pointers:

- `app/stones/`: the Stones taxonomy (NAME / TAGLINE / SOURCES /
  collect()) over the FSM probes.
- `app/fsm.py`: Burr FSM with one probe per `@action`.
- `app/reconcile.py`: `build_documents()` emits Granite-native
  document-role messages in canonical Stone order.
- `app/mellea_validator.py`: strict reconcile path (4-check rejection
  sampling).
- `app/llm.py`: LiteLLM Router shim. Routes to Ollama or vLLM without
  changing caller code.
- `web/main.py`: FastAPI + SSE. The stream emits
  `plan / step / token / mellea_attempt / final` events plus the
  `stone_start / stone_done` envelope around each Stone group.
- `web/sveltekit/`: primary UI (SvelteKit + adapter-static).

For the long-form architecture document, see [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## Data sources

Riprap contacts only public-record federal, state, and city sources at
runtime. No commercial APIs, no proprietary scores, no opaque
aggregators.

| Source | Hosting agency | Used for |
|---|---|---|
| Hurricane Sandy 2012 inundation zone | NYC OTI / NOAA Office for Coastal Management | Cornerstone hazard memory |
| NYC DEP Stormwater Flood Maps | NYC Department of Environmental Protection | DEP modeled-scenario layers |
| Hurricane Ida 2021 USGS high-water marks | USGS Short-Term Network | Empirical validation points |
| FloodNet ultrasonic sensor network | NYU CUSP / FloodNet | Live water-depth observations |
| NYC 311 flood complaints | NYC Open Data | Empirical complaint history |
| NOAA tide gauge — The Battery | NOAA CO-OPS | Live tide and surge level |
| NWS METAR | National Weather Service | Hourly precipitation |
| NWS public flood alerts | National Weather Service | Active warnings and watches |
| MTA subway entrances | MTA / NYC Open Data | Transit asset register |
| NYCHA developments | NYC Housing Authority | Public-housing exposure |
| NYC DOE schools | NYC Department of Education | Education-asset exposure |
| NYS DOH hospitals | New York State Department of Health | Critical-facility exposure |
| USGS 3DEP 1 m DEM | USGS National Map | HAND / TWI microtopography |
| NYC DOB filings | NYC Department of Buildings | Development-check intent |
| NPCC4 SLR projections | NYC Mayor's Office of Climate & Environmental Justice | Policy-context corpus (RAG) |
| Sentinel-2 MSI imagery | ESA / Copernicus | Prithvi + TerraMind inputs |

The full data licence map and vintage table is enumerated in
[`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## What Riprap is not

The civil engineer carries the stamp. Riprap surfaces the evidence the
engineer judges.

- **Not a hydraulic model.** Riprap does not replace HEC-RAS, SWMM, or
  ICM. It synthesises evidence from completed modelling work; it does
  not produce new flow or stage estimates.
- **Not a stamped deliverable.** The briefing is a starting point for
  a memo, not the memo itself. Professional judgment, field
  reconnaissance, and the engineer's stamp are required for any
  actionable output.
- **Not a substitute for site investigation.** Microtopography is from
  1 m USGS 3DEP LiDAR, appropriate for screening, not for design.
- **Not a risk score.** Riprap does not output a 1–10 or 1–100 number.
  Score-based tools (First Street, ClimateCheck, Jupiter) are
  different products for different audiences. Riprap is the evidence
  audit trail behind any such judgment.

---

## Citation

If you reference Riprap in academic or professional work:

```bibtex
@software{riprap_nyc_2026,
  author       = {Rahman, Adam Munawar},
  title        = {Riprap: Citation-Grounded NYC Flood-Exposure Briefings},
  year         = {2026},
  url          = {https://github.com/msradam/riprap-nyc},
  version      = {v0.5.0},
  note         = {Built for the AMD x lablab.ai Developer Hackathon}
}
```

---

## License

Apache 2.0 (this repository). The three NYC-specialised fine-tunes
above are also Apache 2.0; underlying upstream models retain their
own permissive licences (see each `MODEL_CARD.md`).

HF Space configuration reference:
<https://huggingface.co/docs/hub/spaces-config-reference>.

---

## Acknowledgments

- **AMD Developer Cloud** — MI300X compute that made the three
  Apache-2.0 NYC fine-tunes feasible.
- **AMD x lablab.ai Developer Hackathon** — the venue.
- **IBM Research** — Granite 4.1, Granite Embedding 278M, Granite TTM
  r2, Mellea, and the rest of the open-source Granite ecosystem.
- **NASA / IBM Prithvi-EO 2.0** and **IBM / ESA TerraMind 1.0** — the
  geospatial foundation models behind the NYC fine-tunes.
- **NYU CUSP / FloodNet** — the public sensor network whose data
  Riprap reads live.
- **Andrew Hicks** — civil-engineering review of the methodology, and
  framing for what Riprap is not.
- **The Riprap dam mark** — ["Dam" by Chintuza](https://thenounproject.com/icon/dam-4516918/)
  via the Noun Project, licensed CC-BY 3.0. The original SVG embedded
  the attribution as on-canvas text; Riprap's `assets/logo*.svg`
  strips the embedded text and carries the credit here in body copy
  instead, per the Creative Commons attribution requirement.
