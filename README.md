---
title: Riprap Nyc
emoji: 😻
colorFrom: red
colorTo: yellow
sdk: docker
pinned: false
---

# Riprap — citation-grounded NYC flood-exposure briefings

Riprap takes any NYC address (or neighborhood, or development-permit query)
and produces a four-section briefing — **Status / Empirical evidence /
Modeled scenarios / Policy context** — where every numeric claim is
anchored to a `[doc_id]` citation pointing back into the source document.

The Capstone reconciler is **Granite 4.1** (8B, served via Ollama on T4
or vLLM on AMD MI300X), wrapped in **Mellea**-validated rejection
sampling. Sentences that fail one of four grounding checks
(`numerics_grounded`, `no_placeholder_tokens`, `citations_dense`,
`citations_resolve`) are rerolled with surgical feedback until the
budget is exhausted.

Live demo: <https://msradam-riprap-nyc.hf.space>

---

## How Riprap works — the Five Stones

Behind every briefing, ~25 atomic specialists fan out across NYC datasets,
satellite imagery, sensors, and forecasts. The **Five Stones** are a
re-grouping of those specialists into five legible roles:

> **Cornerstone** remembers. **Keystone** tallies. **Touchstone**
> watches. **Lodestone** projects. **Capstone** writes it all down with
> citations.

| Stone | Role | What fires |
|---|---|---|
| **Cornerstone** | The Hazard Reader — what NYC's ground remembers | Sandy 2012 inundation extent, NYC DEP stormwater scenarios, 2021 Ida USGS high-water marks, baked Prithvi-EO Ida-attributable polygons, USGS 3DEP DEM + HAND/TWI |
| **Keystone** | The Asset Register — what's exposed | MTA subway entrances, NYCHA developments, NYC DOE schools, NYS DOH hospitals, **TerraMind-NYC Buildings LoRA** |
| **Touchstone** | The Live Observer — current state of the city | FloodNet ultrasonic depth sensors, NYC 311 flood complaints, NWS hourly METAR, NOAA tide-gauge water levels, **Prithvi-EO 2.0 NYC-Pluvial v2**, **TerraMind-NYC LULC LoRA** |
| **Lodestone** | The Projector — what's coming | NWS public flood alerts, Granite TTM r2 surge nowcast (zero-shot, 6-min cadence, 9.6 h horizon), per-address 311 weekly forecast, FloodNet sensor recurrence forecast, **Granite-TTM-r2-Battery-Surge fine-tune** (96 h hourly horizon) |
| **Capstone** | The Synthesiser — citation-grounded briefing | Granite 4.1 + Mellea rejection sampling |

The four data-Stones run sequentially per query; the Capstone reconciles
their documents into one cited paragraph.

---

## NYC-specialised foundation models (Apache 2.0)

Three NYC-specific fine-tunes built on AMD Instinct MI300X via AMD
Developer Cloud, published under permissive licence:

- **[`msradam/TerraMind-NYC-Adapters`](https://huggingface.co/msradam/TerraMind-NYC-Adapters)**
  — LoRA family on TerraMind 1.0 base. LULC mIoU 0.5866 (+6.13 pp over
  full-FT baseline), TiM 0.6023, Buildings 0.5511. Trained in ~18 min on
  a single MI300X.
- **[`msradam/Prithvi-EO-2.0-NYC-Pluvial`](https://huggingface.co/msradam/Prithvi-EO-2.0-NYC-Pluvial)**
  — NYC pluvial-flood fine-tune of Prithvi-EO 2.0. Test flood IoU
  0.5979 vs 0.10 on the Sen1Floods11 base — a 6× lift. Lovász-Softmax
  loss + copy-paste augmentation.
- **[`msradam/Granite-TTM-r2-Battery-Surge`](https://huggingface.co/msradam/Granite-TTM-r2-Battery-Surge)**
  — NYC Battery storm-surge nowcast fine-tune of Granite TimeSeries TTM
  r2. Test MAE 0.1091 m, −41% vs persistence and −25% vs zero-shot.

All three are loaded at runtime by their respective FSM specialists in
`app/context/` and `app/live/`.

---

## Architecture pointers

- `app/stones/` — the Stones taxonomy (NAME / TAGLINE / SOURCES /
  collect()) over the FSM specialists.
- `app/fsm.py` — Burr FSM with one specialist per `@action`.
- `app/reconcile.py` — `build_documents()` emits Granite-native
  document-role messages in canonical Stone order.
- `app/mellea_validator.py` — strict reconcile path (4-check rejection
  sampling).
- `app/llm.py` — LiteLLM Router shim. Routes to Ollama (T4 / local) or
  vLLM (AMD MI300X) without changing caller code.
- `web/main.py` — FastAPI + SSE. The stream emits
  `plan / step / token / mellea_attempt / final` events plus the
  `stone_start / stone_done` envelope around each Stone group.
- `web/sveltekit/` — primary UI (SvelteKit + adapter-static).
- `web/svelte/` + `web/static/` — legacy custom-element bundle, still
  serving `/legacy`, `/single`, `/compare`.
- `experiments/18_terramind_nyc_lora/` /
  `experiments/19_prithvi_nyc_v2/` /
  `experiments/20_ttm_battery_surge/` — full reproduction recipes for
  the three HF artifacts above.

---

## Local development

```bash
# Local server (Ollama primary)
.venv/bin/uvicorn web.main:app --host 127.0.0.1 --port 7860

# Local server pointed at AMD MI300X (vLLM primary, Ollama fallback)
RIPRAP_LLM_PRIMARY=vllm \
RIPRAP_LLM_BASE_URL=http://<droplet-ip>:8000/v1 \
RIPRAP_LLM_API_KEY=<token> \
.venv/bin/uvicorn web.main:app --host 127.0.0.1 --port 7860

# Programmatic Mellea probe (server must be running)
.venv/bin/python scripts/probe_mellea.py --query "Hollis" --runs 5
```

---

## License

Apache 2.0 (this repository). The three NYC-specialised models above
are also Apache 2.0; underlying upstream models retain their own
permissive licences (see each `MODEL_CARD.md`).

Check out the HF Space configuration reference at
<https://huggingface.co/docs/hub/spaces-config-reference>.
