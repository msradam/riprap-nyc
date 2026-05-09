# Riprap architecture

> **What it is.** A web tool that takes any NYC address and produces a
> short, citation-grounded **flood-exposure briefing**. A tier (1–4)
> with a paragraph of evidence, where every numeric claim links back to
> the specific dataset, agency report, or model output it came from.
>
> **Who it's for.** Urban planners, journalists on deadline, NYCEM
> grant writers filing FEMA BRIC sub-applications, agency capital
> planners, researchers under FOIL/IRB constraints. Not consumers
> shopping for flood insurance.
>
> **Why local foundation models.** A newsroom with FOIL'd documents
> can't paste them into a vendor LLM. We run Granite 4.1 (3 B-param
> chat model), Granite Embedding 278M (RAG), Prithvi-EO 2.0 (300 M-param
> Earth-observation model, offline pre-compute) and Granite TimeSeries
> TTM r2 (1.5 M-param zero-shot forecaster) inside one container. No
> vendor LLM is contacted at runtime.

---

## 1. A 60-second primer on NYC flooding

Skip if you already know this. Most architecture docs assume you do.
This one doesn't.

### 1.1 Three kinds of flood

NYC gets hit by three flood mechanisms that look completely different
on a map and are caused by different physics:

- **Coastal / surge flooding**. The ocean rises into the city.
  Driven by storm surge (wind pushing water against the coast),
  astronomical high tide, and wave run-up. Affects the **shoreline:**
  Brighton Beach, Coney Island, Red Hook, Lower Manhattan, the
  Rockaways, Staten Island east shore. **Hurricane Sandy 2012** is
  the canonical event. Water came over the seawall and flooded
  subway tunnels, hospitals, and electrical substations. Affects
  buildings that were dry that morning.
- **Pluvial / stormwater flooding**. Rain falls faster than the
  drainage system can carry it away. Affects **inland low points,
  basement apartments, and chronically under-sewered neighborhoods**:
  Hollis (Queens), Carroll Gardens (Brooklyn), Jamaica. **Hurricane
  Ida 2021** is the canonical event for NYC. Most of the deaths
  were in basement apartments far from any coast. Optical satellites
  largely *can't see* this kind of flooding because the water drains
  fast and is often sub-surface.
- **Compound flooding**. Coastal + pluvial happening at the same
  time, with groundwater rising too. Currently the active research
  frontier (NPCC4 Ch. 3 calls it out explicitly). Most agencies model
  these mechanisms separately; reality combines them.

A good civic flood tool has to cover all three and be honest about
what each signal can and cannot see. Riprap surfaces evidence for all
three but **doesn't predict damage**. See scope below.

### 1.2 Empirical vs modeled vs proxy

Each piece of flood evidence falls into one of three classes, and the
distinction matters for how much weight to give it:

- **Empirical**. Something flooded a place and was measured. USGS
  high-water marks (people went out after Hurricane Ida and surveyed
  where water reached on building walls). The 2012 Sandy Inundation
  Zone (mapped by the city after the storm). FloodNet ultrasonic
  sensors that recorded an actual depth. **Highest-confidence**: this
  flood happened here.
- **Modeled scenarios**. Hydraulic models simulate "what if" cases.
  FEMA's regulatory floodplains (1 % and 0.2 % annual chance). NYC
  DEP's Stormwater Maps (modeled water depth under three rainfall
  scenarios with varying sea-level-rise assumptions). **Useful but
  scenario-bounded**: this could happen here under those conditions.
- **Proxy signals**. Indirect indicators of flooding. NYC 311
  complaints ("street flooding", "sewer backup") clustering around an
  address. Topographic indices (HAND, TWI) suggesting water *would*
  pool here based on terrain. **Useful but biased**: 311 reflects
  civic engagement as well as flooding; terrain says nothing about
  drainage capacity.

Riprap surfaces all three classes. The score weights them in that
order (empirical > modeled > proxy), with empirical hits granted a
**floor rule**. See [§5](#5-the-scoring-rubric).

### 1.3 Hydrology indices used in this app

Two terrain-derived numbers come up repeatedly. They're cheap to
compute from a Digital Elevation Model (DEM) and they're the
hydrological literature's canonical exposure proxies:

- **HAND (Height Above Nearest Drainage)**. Vertical distance from
  the address up to the nearest river/drainage channel. **<1 m** = at
  drainage level (water *will* reach here in flood). **>10 m** =
  hillslope (very dry). Nobre et al. 2011.
- **TWI (Topographic Wetness Index)**. `ln(catchment_area / tan
  slope)`. **High TWI** = water tends to accumulate here (large
  contributing area, gentle slope). Beven & Kirkby 1979.

Neither is a flood prediction; both are exposure indicators that say
"water *would* pool here based on terrain alone."

---

## 2. What Riprap actually produces

For a given address (or any of three modes; see [§4](#4-three-user-modes)),
Riprap returns:

1. **A tier 1–4** computed by a deterministic, published rubric
   ([§5](#5-the-scoring-rubric)). Tier 1 = "high exposure"; Tier 4 =
   "limited exposure"; Tier 0 = "no flagged exposure."
2. **A 4-section briefing paragraph** synthesised by Granite 4.1 with
   `[doc_id]` citations after every numeric claim. Sections:
   *Status*, *Empirical evidence*, *Modeled scenarios*, *Policy
   context*. A section is omitted entirely if no specialist fired for
   it (silence-over-confabulation contract).
3. **Evidence cards**. One per fired specialist, with the raw values
   and a link to the source dataset.
4. **Map overlay**. The address pinned, with the empirical and
   modeled flood extents that overlap it.
5. **Live "right now" signals**. Active NWS flood alerts, current
   tide residual at the Battery, recent precipitation at the nearest
   ASOS, and a Granite TTM short-horizon forecast of the surge
   residual. **These do not modify the tier** (per IPCC AR6 WG II's
   distinction between exposure and event occurrence).

The full output is a JSON blob with all specialist outputs preserved,
so a journalist or planner can audit every number that appears in the
prose.

---

## 3. The Burr FSM and how the specialists chain

Riprap is a **state machine**, a Burr FSM (DAGWorks), that walks
through a fixed list of "specialist" functions in order. Each
specialist either produces a structured fact or stays silent. At the
end, the reconciler reads all the produced facts and writes the
paragraph.

The full chain, in execution order:

```
            ┌─────────────────────────────┐
  query ──► │ 1. geocode (DCP Geosearch)  │  address text → lat/lon, BBL, borough
            └────────────┬────────────────┘
                         ▼
         ┌─────────────────────────────────────────────┐
         │     STATIC EMPIRICAL + REGULATORY LAYERS    │
         │ (snapshot of city-published flood layers)   │
         ├─────────────────────────────────────────────┤
         │ 2. sandy           in 2012 Sandy zone? Y/N  │  empirical
         │ 3. dep_stormwater  in 3 modeled scenarios?  │  modeled
         │ 4. floodnet        live sensor history      │  empirical
         │ 5. nyc311          flood complaints in 200m │  proxy
         └────────────┬────────────────────────────────┘
                      ▼
         ┌─────────────────────────────────────────────┐
         │            LIVE "RIGHT NOW" LAYER           │
         │ (out of static score; reported separately)  │
         ├─────────────────────────────────────────────┤
         │ 6. noaa_tides    Battery / Kings Pt level   │  live, 6-min
         │ 7. nws_alerts    active flood-relevant      │  live
         │ 8. nws_obs       nearest ASOS recent precip │  live
         │ 9. ttm_forecast  9.6h surge-residual nowcast│  Granite TTM r2
         └────────────┬────────────────────────────────┘
                      ▼
         ┌─────────────────────────────────────────────┐
         │   TERRAIN + EVENT-LEVEL EMPIRICAL LAYERS    │
         ├─────────────────────────────────────────────┤
         │ 10. microtopo    DEM + TWI + HAND at point  │  proxy
         │ 11. ida_hwm      USGS Ida 2021 HWM proximity│  empirical
         │ 12. prithvi      Prithvi-EO Ida flood polys │  empirical (model-derived)
         └────────────┬────────────────────────────────┘
                      ▼
         ┌─────────────────────────────────────────────┐
         │ 10. microtopo    DEM + TWI + HAND at point  │  proxy
         │ 11. ida_hwm      USGS Ida 2021 HWM proximity│  empirical
         │ 12. mta_entrance MTA subway entrance exposure│  empirical
         │ 13. prithvi_v2   Prithvi Ida flood polys     │  empirical (model-derived)
         │ 14. prithvi_live live Prithvi inference      │  (gpu-only; skipped cpu-basic)
         │ 15. terramind    TerraMind LULC synthesis    │  (gpu-only; skipped cpu-basic)
         └────────────┬────────────────────────────────┘
                      ▼
         ┌─────────────────────────────────────────────┐
         │ 16. rag (Granite Embedding 278M)            │  retrieves policy paragraphs
         │     query corpus of 5 NYC agency PDFs        │  relevant to this address
         │ 17. gliner_extract (GLiNER medium-v2.1)     │  entity extraction over RAG hits
         └────────────┬────────────────────────────────┘
                      ▼
         ┌─────────────────────────────────────────────┐
         │ 18. reconcile (Granite 4.1 :8b)             │  document-grounded synthesis
         │     reads all "documents" produced by 1-17  │  → 4-section cited paragraph
         │     Mellea rejects ungrounded outputs        │  → audit trail
         └────────────┬────────────────────────────────┘
                      ▼
                 cited briefing
                 + tier badge + evidence cards + map
```

The `single_address` path emits **24 step events** (including the live
sub-specialists ttm_311_forecast, ttm_battery_surge, floodnet_forecast,
and the eo_chip_fetch / terramind_lulc / terramind_buildings gates).
`neighborhood` emits 8–10 steps (NTA-level specialists only; per-address
registers don't run).

Each step is implemented as a `@action` in `app/fsm.py`. The Burr
runtime handles state-passing between actions and emits a trace record
per step (timing, ok/err, summary fields) which the front-end shows live.

### 3.1 What every specialist does, plain language

| # | Specialist                | Plain-language description                                                                                                                                                       | Class              |
|---|---------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------|
| 1 | **geocode**               | Resolve the user's text ("116-50 Sutphin Blvd, Queens") to a (lat, lon) and a NYC tax-lot ID (BBL). Uses NYC Planning's free Geosearch API.                                      | n/a                |
| 2 | **sandy**                 | Did the address get flooded by Hurricane Sandy in 2012? Point-in-polygon over the official NYC Sandy Inundation Zone.                                                            | empirical          |
| 3 | **dep_stormwater**        | Three modeled stormwater-flooding scenarios from NYC DEP: Moderate-2050, Extreme-2080, Tidal-2050. Each tells you depth (none / 0.4–0.8 ft / etc.) at this point.                | modeled            |
| 4 | **floodnet**              | NYC's ultrasonic flood-sensor network. How many sensors are within 600 m, and have any of them registered a flood event in the last 3 years?                                     | empirical          |
| 5 | **nyc311**                | The 311 service-request archive. How many flood-related complaints (street flooding, sewer backup, catch-basin clogged) within 200 m of the address over the last 5 years?       | proxy              |
| 6 | **noaa_tides** *(live)*   | Current tide observation at the nearest of three NOAA gauges (Battery / Kings Pt / Sandy Hook). Reports observed water level, predicted astronomical tide, and the **residual** (≈ surge). | live               |
| 7 | **nws_alerts** *(live)*   | Are there active NWS flood-relevant alerts at this point right now? Flash Flood Warnings, Coastal Flood Advisories, etc.                                                         | live               |
| 8 | **nws_obs** *(live)*      | Recent precipitation from the nearest airport ASOS station (KNYC / KLGA / KJFK / KEWR / KFRG).                                                                                   | live               |
| 9 | **ttm_forecast** *(live)* | Granite TTM r2 zero-shot forecast of the surge **residual** at the Battery for the next ~9.6 h. NOAA already publishes the astronomical tide; TTM forecasts the part NOAA doesn't. | live (model-derived) |
| 10 | **microtopo**            | LiDAR-derived terrain features at the point: elevation, HAND, TWI, local relief percentile.                                                                                      | proxy              |
| 11 | **ida_hwm**              | USGS Hurricane Ida 2021 high-water marks. Actual measured water heights surveyed in the days after the storm.                                                                   | empirical          |
| 12 | **mta_entrance_exposure** | MTA subway entrances within radius: how many, how many are inside Sandy 2012 zone, how many are in DEP Extreme-2080. | empirical          |
| 13 | **prithvi_eo_v2**        | Pre-computed point-in-polygon against 166 Prithvi-derived Ida 2021 flood polygons (offline-built; instant at request time).                                                      | empirical (model-derived) |
| 14 | **prithvi_eo_live** / **terramind_synthesis** | Live Prithvi / TerraMind inference over fresh EO chips. GPU-only; silenced (deterministic skip) on cpu-basic HF Space. | empirical (model-derived) |
| 15 | **rag**                  | Granite Embedding 278M retrieves the most-relevant paragraphs from 5 NYC policy PDFs (Comptroller, NPCC4, MTA, NYCHA, ConEd) given the address's borough + which scenarios fired. | policy             |
| 16 | **gliner_extract**       | GLiNER medium-v2.1 runs named-entity extraction over the RAG-retrieved paragraphs: locations, agencies, dates, infrastructure-project names. Results ride into the reconciler as additional grounding context. | ancillary |
| 17 | **reconcile**            | Granite 4.1 :8b reads all documents produced by steps 1–16 and writes the cited briefing paragraph. Mellea rejection-sampling validates 4 grounding requirements; up to 3 attempts. See [§6](#6-document-grounded-reconciliation). | LLM synthesis |

### 3.2 Worked example: 2940 Brighton 3rd St, Brooklyn

To make the chain concrete, here's what fires for a Brighton Beach
address:

| Step | What it returns |
|---|---|
| geocode    | `(40.5780, -73.9617)`, BBL `3-08660-0001`, Brooklyn |
| sandy      | **YES**. Inside the 2012 Sandy Inundation Zone |
| dep_stormwater | `dep_moderate_2050`: depth 0.4-0.8 ft; `dep_extreme_2080`: depth 0.8-2.0 ft |
| floodnet   | 2 sensors within 600 m; 1 trigger event in last 3 yr (peak 14 cm) |
| nyc311     | 11 flood-related complaints in 200 m, 5-yr window |
| noaa_tides | Sandy Hook gauge, +0.49 ft residual *(today's reading)* |
| nws_alerts | 0 active alerts |
| nws_obs    | KJFK ASOS, no recent precipitation |
| ttm_forecast | Forecast peak residual +0.6 ft in 4.2 h *(today's run)* |
| microtopo  | Elevation 2.36 m, HAND 0.7 m, TWI 11.3, percentile 8 (very low) |
| ida_hwm    | 0 USGS HWMs within 800 m (Ida hit Queens hardest, not Brighton) |
| prithvi    | Inside an Ida-attributable polygon? **NO** (Ida was pluvial-inland) |
| rag        | Top hits: NPCC4 Ch.3 (coastal), MTA Resilience (Coney Island D-train), Comptroller |
| reconcile  | (see below) |
| **Tier**   | **1 (High exposure)** with empirical floor applied |

The reconciler then writes:

```
**Status.** This Brighton Beach address sits **inside the 2012 Sandy
Inundation Zone** [sandy], on relatively low ground with HAND of 0.7 m
[microtopo].

**Empirical evidence.** NYC 311 records show **11 flood-related
complaints** within 200 m over the last 5 years [nyc311]; 2 FloodNet
sensors are within 600 m and one logged a 14 cm event in the last 3
years [floodnet].

**Modeled scenarios.** The address sits inside **DEP Moderate-2050**
with depth class 0.4-0.8 ft and **DEP Extreme-2080** with depth class
0.8-2.0 ft [dep_moderate_2050][dep_extreme_2080].

**Policy context.** **NPCC4 Ch. 3** documents accelerating coastal-
flood frequency along this stretch [rag_npcc4].
```

Note what *didn't* fire: no Ida HWM doc (Ida didn't flood here), no
Prithvi doc (no Ida-attributable polygon), no NWS alerts (clear day),
no TTM doc (forecast residual under threshold). The reconciler never
saw those headers and didn't invent them.

---

## 4. Five planner intents

The planner (`app/planner.py`) classifies every free-text query into one of
five intents before the FSM runs. This happens in a single Granite 4.1 call
that streams its JSON output to the client as `plan_token` events.

| Intent                | Triggered by                                  | FSM path                         | Steps |
|-----------------------|-----------------------------------------------|----------------------------------|-------|
| `single_address`      | Fully-qualified street address                | Full linear FSM (geocode → 19 specialists → reconcile) | 24 |
| `neighborhood`        | NTA name, borough name, bare zip              | NTA-level specialists only (no per-address registers)   | 8–10 |
| `compare`             | "A vs B", "compare X to Y"                   | Two sequential single_address runs; merged two-column paragraph | 2 × 24 |
| `development_check`   | "what's being built at X", "is Y risky"       | DOB filings + flood layers                              | 3–5 |
| `live_now`            | "is it flooding now", "current alerts"        | Live-only specialists (tides, alerts, obs) — no Mellea  | 4 |
| `not_implemented`     | Retrospective, ranking, cross-city queries    | Returns rationale immediately                           | 0 |

### Compare intent detail

`_run_compare()` in `web/main.py` executes the full `single_address` FSM
sequentially for each target, then merges the two paragraphs under
`## PLACE A: …` / `## PLACE B: …` headers separated by `---`. The
`CompareBriefing.svelte` component renders this as a two-column layout with
a "Key differences" delta bar above. During streaming the tokens are rendered
in a single column (sequential); the two-column layout appears when the
`final` event lands.

**Registered routes**

| Path                                      | Serves |
|-------------------------------------------|--------|
| `/`                                       | SvelteKit landing + live query UI |
| `/api/agent/stream?q=…`                   | SSE stream — planner + all intent paths |
| `/register/{schools,nycha,mta_entrances}` | Pre-computed bulk register browser |
| `/legacy`, `/single`, `/compare`, `/register/*` | Legacy custom-element bundle (compatibility) |

Registers are pre-computed because running 1,900 reconciler calls at request
time is a non-starter; the register build runs offline
(`scripts/build_*_register.py`) and results are loaded from
`data/registers/*.json` at boot.

---

## 5. The scoring rubric

This is the part of the system that produces the tier 1–4. It is
**deterministic, published, and not done by the language model**.
See `METHODOLOGY.md` for the full citation list; here's the
high-level structure.

### 5.1 Three thematic sub-indices

Following Cutter et al. 2003 (SoVI hazards-of-place) and Tate 2012
(uncertainty analysis), indicators are grouped into thematic sub-
indices, equal-weighted within each group, normalized to [0, 1]:

| Sub-index       | What it captures                                         | Top weights |
|-----------------|----------------------------------------------------------|-------------|
| **Regulatory**  | Inside FEMA / DEP / NPCC4 modeled or regulated zones     | FEMA 1 %; DEP-2050; DEP Tidal |
| **Hydrological**| Terrain-based exposure (HAND, TWI, percentile, relief)   | HAND (Nobre 2011); TWI half-weighted (urban DEM noise) |
| **Empirical**   | Did flooding actually happen here (Sandy, Ida HWMs, 311) | Sandy + HWM<100m → also trigger floor |

The **composite** is the sum of the three sub-indices (range 0–3).
Tier breakpoints: ≥1.5 → Tier 1, ≥1.0 → Tier 2, ≥0.5 → Tier 3, >0 →
Tier 4, 0 → Tier 0.

### 5.2 Max-empirical floor

If **Sandy 2012 inundation** OR **a USGS Ida HWM within 100 m** fired,
the tier is capped at **2 (Elevated)**. It cannot be worse,
regardless of the additive composite.

This recovers the *important* multiplicative behaviour Balica 2012
argues for (empirical observations should not be cancelled by
terrain or modeled scenarios) without giving up additive transparency.
The 100 m radius is chosen because USGS HWM positional uncertainty is
typically 5–30 m. 100 m gives ~3σ headroom for a confident "this
address was inundated" signal.

### 5.3 Live signals stay out

NWS alerts, NOAA tide residual, and NWS hourly precipitation are
**not** in the static tier. Per IPCC AR6 WG II glossary and NPCC4
Ch. 3, exposure is a quasi-stationary property of place; event
occurrence is time-varying. They appear separately as live evidence
cards.

---

## 6. Document-grounded reconciliation

`app/reconcile.py` builds a list of OpenAI-style chat messages where
each specialist's emission is its own message with a stable `doc_id`
ride-along on the role. Granite 4.1's Ollama chat template recognises
any `role: "document <doc_id>"` message and lifts it into a
`<documents>` block, prepending IBM's official grounded-generation
system message ("Write the response by strictly aligning with the
facts in the provided documents").

Example packet for the Brighton Beach address (abbreviated):

```python
[
    {"role": "system", "content": "<citation-discipline + 4-section skeleton>"},
    {"role": "document sandy",            "content": "Address is INSIDE the 2012 Sandy zone. ..."},
    {"role": "document dep_extreme_2080", "content": "Depth class 0.8-2.0 ft. ..."},
    {"role": "document floodnet",         "content": "2 sensors; peak 14 cm. ..."},
    {"role": "document nyc311",           "content": "11 flood complaints in 200 m. ..."},
    {"role": "document microtopo",        "content": "Elev 2.36 m, HAND 0.7 m, TWI 11.3. ..."},
    {"role": "document rag_npcc4",        "content": "<retrieved paragraph>"},
    {"role": "user", "content": "Write the cited briefing now."},
]
```

The four-section structure (`**Status.** / **Empirical evidence.** /
**Modeled scenarios.** / **Policy context.**`) is enforced by the
`EXTRA_SYSTEM_PROMPT`. Sections without supporting documents are
omitted entirely.

### 6.1 Two reconciler models

- **`granite4.1:3b`** runs the planner and `live_now` (short outputs,
  routing decisions). Always streamed.
- **`granite4.1:8b`** runs the synthesis path for `single_address`,
  `neighborhood`, and `development_check` (long outputs, dense
  citations). Pre-warmed into VRAM in `entrypoint.sh` so the first
  query doesn't pay the model-load tax. Both fit warm on the T4 with
  `OLLAMA_MAX_LOADED_MODELS=2` and `OLLAMA_KEEP_ALIVE=24h`.

### 6.2 Mellea-validated rejection sampling

`app/mellea_validator.py` wraps the Granite-via-Ollama call in IBM
Research's [Mellea](https://github.com/generative-computing/mellea)
framework. Instruct, validate, repair. The synthesis intents call
`reconcile_strict_streaming(...)` which:

1. **Streams** each generation attempt's tokens to the user (via the
   FSM threadlocal `set_token_callback` for `single_address` or a
   `progress_q` for the polygon intents).
2. After each attempt, runs **four deterministic checks** on the
   accumulated paragraph:
   - **`numerics_grounded`**. Every non-trivial number in the output
     appears verbatim in a source document.
   - **`no_placeholder_tokens`**. Output contains no leaked
     `[source]` / `<document>` template markup.
   - **`citations_dense`**. Every non-trivial number has a
     `[doc_id]` citation **somewhere in the same sentence** (sentence
     boundaries: `. ` / `.\n` / end-of-text).
   - **`citations_resolve`**. Cited `doc_id`s are a subset of the
     input doc_ids.
3. If any check fails, fires a `mellea_attempt` SSE event with the
   failed-requirement names, then **rerolls** with a feedback prompt
   that names the specific failing sentences (the model usually
   responds well to surgical corrections). Loop budget: 3 attempts.

The frontend renders an inline banner above the briefing. Amber on
reroll (with the failed-req list), green on first-try pass. The final
reconcile step in the trace shows the `passed: N/4 · rerolls: M`
metadata for full audit transparency.

### 6.3 Number recognition is identifier-aware

The numeric guardrail uses `\b-?\d[\d,]*(?:\.\d+)?\b` so that
identifier codes embedded in prose (`QN1206` NTA codes, `BBL
3-00589-0003` parcels, `BIN`, `B12` community boards) are *not*
treated as numeric claims demanding citation. This was the dominant
false-positive in early probing; without it, almost every neighborhood
briefing failed `citations_dense` because the opening sentence
typically reads "*X (NTA QN1206) in Queens…*".

### 6.4 Why no native Granite 4.x inline citations

We investigated using Granite's native `<|start_of_cite|>{document_id:
X}fact<|end_of_cite|>` mode. **It's deprecated in 4.x.** Verified:

- The official Ollama chat template for `granite4.x` has no citation
  branch (the 3.3 / 4.0-preview templates did).
- `granite_common` ships only `granite3/granite32` and
  `granite3/granite33` subdirs. No 4.x equivalent.
- `granite-io` has only `granite_3_2/` and `granite_3_3/` processor
  dirs.

The base 4.1 weights still contain the cite tokens (training residue),
so the model emits them as real tokens when nudged. But only as an
end-of-response list, not inline in prose. IBM's published 4.x
grounding path is a separate **Citation Generation LoRA** (built on
`granite-4.0-micro`, not 4.1) requiring HF transformers + LoRA
loading. Mellea's `OllamaBackend` explicitly raises
`NotImplementedError` for activated LoRAs. So our hand-rolled
`[doc_id]` regex + reroll **is** the right pattern for our setup
(Granite 4.1 via Ollama, inline placement).

---

## 7. The four foundation models

| Model | Params | Runtime | Role |
|-------|--------|---------|------|
| **Granite 4.1 :3b alias**   | 8 B†   | Ollama or vLLM (AMD MI300X)          | Planner (intent + specialist routing) + `live_now` reconciler. †Production alias `RIPRAP_OLLAMA_3B_TAG=granite4.1:8b` — planner runs 8b in production. |
| **Granite 4.1 :8b**         | 8 B    | Ollama or vLLM (AMD MI300X)          | Synthesis reconciler for `single_address`, `neighborhood`, `development_check`, `compare`. Validated by Mellea (4 grounding requirements + reroll). |
| **Granite Embedding 278M**  | 278 M  | sentence-transformers (CPU)          | RAG retrieval over 5 policy PDFs at query time.    |
| **Prithvi-EO 2.0**          | 300 M  | TerraTorch (offline pre-compute)     | NYC-Pluvial fine-tune; segmented Hurricane Ida 2021 pre/post Sentinel-2 polygons baked into `data/`. Fine-tune: `msradam/Prithvi-EO-2.0-NYC-Pluvial`. |
| **Granite TimeSeries TTM r2** | 1.5 M | granite-tsfm (CPU)                  | Zero-shot forecast of the Battery surge residual, ~9.6 h horizon. Fine-tune: `msradam/Granite-TTM-r2-Battery-Surge`. |
| **GLiNER medium-v2.1**      | ~200 M | gliner (CPU)                         | Named-entity extraction over RAG hits (locations, agencies, dates, infrastructure). `urchade/gliner_medium-v2.1`. |

**Granite 4.1 ≠ Granite Time Series.** Granite 4.1 is IBM's chat-LLM
family. Granite TimeSeries TTM is a separate IBM Research product
line (Ekambaram et al. 2024, NeurIPS). Both happen to share the
"Granite" brand but have different architectures, training data, and
authors.

**LiteLLM Router.** All LLM calls go through `app/llm.py`, a ~250-line
shim over a LiteLLM Router. Two backends are wired: `RIPRAP_LLM_PRIMARY=ollama`
(local + HF Space default) and `RIPRAP_LLM_PRIMARY=vllm` (AMD MI300X demo
path, auto-fails over to Ollama). The shim normalizes role names and
citation-token format so the rest of the codebase is backend-agnostic.

### 7.1 Why Prithvi runs offline

Prithvi-EO 2.0 with TerraTorch needs a GPU and minutes per HLS tile.
We segmented Hurricane Ida 2021 once (pre: 2021-08-25, post:
2021-09-02 ~12 h after peak), filtered the output (>30 000 sqft to
drop noise, <1 km² to drop tidal artifacts) into **166 polygons**
baked into `data/prithvi_ida_2021.geojson`. The runtime FSM does a
point-in-polygon test, not fresh inference. This is honest about
where foundation models earn their keep: **once, to produce a
defensible event-level signal. Not per request**.

### 7.2 Why TTM r2 runs live

TTM r2 is **1.5 M params**. Vastly smaller than Prithvi or Granite
4.1. Inference is millisecond-scale even on CPU. It forecasts only
the residual (surge component) at the Battery, which complements the
NOAA snapshot specialist; it does **not** try to forecast the
astronomical tide (NOAA already publishes that exactly).

---

## 8. Live signals separation

Live data (steps 6–9 in the FSM diagram) is fundamentally different
from static layers and is handled separately:

- **Surface**: in evidence cards and a "Right now" section in the UI.
- **Score**: explicitly excluded. Tier is reproducible across queries
  unless source data changed.
- **Cadence**: NOAA tides update every 6 min; NWS alerts on push;
  NWS obs ~hourly; TTM is computed per query (cheap).
- **Failure mode**: graceful. If NOAA times out, no `noaa_tides`
  doc is emitted; the reconciler simply doesn't see it.

This mirrors how First Street separates Flood Factor (static, 30-yr)
from event-day Flood Lab products, and how Fathom separates Global
Flood Map from real-time intelligence.

---

## 9. Repository layout

```
riprap-nyc/
  ARCHITECTURE.md            this file
  METHODOLOGY.md             scoring methodology + full citations
  README.md                  HF Spaces frontmatter + user-facing summary
  Dockerfile                 nvidia/cuda:12.4 base + Ollama + Granite
  entrypoint.sh              Ollama daemon + uvicorn launcher
  requirements.txt           runtime deps (FastAPI, geopandas, sentence-transformers, ollama, burr, granite-tsfm)
  pyproject.toml             ruff + vulture config
  riprap.py                  CLI driver for register builds
  agent.py                   single-address CLI

  app/
    fsm.py                   Burr FSM (14 actions; Mellea hooks via threadlocal)
    planner.py               Granite 4.1:3b intent router (5 intents)
    geocode.py               NYC DCP Geosearch + borough-hint filter
    reconcile.py             Granite 4.1 grounded reconciler + numeric guardrail
    mellea_validator.py      streaming rejection sampler + 4 grounding checks
    rag.py                   Granite Embedding 278M retrieval
    score.py                 deterministic exposure rubric (3 sub-indices, floor)
    spatial.py               geopandas join helpers
    energy.py                per-query inference Wh accounting
    register_builder.py      bulk-mode runner (offline)

    intents/                 per-intent orchestration on top of fsm.py
      live_now.py            shoreline tide + alerts (cheap, non-strict)
      single_address.py      drives the linear FSM with strict reconcile
      neighborhood.py        polygon-aggregated specialists
      development_check.py   DOB permit overlap with flood polygons
    llm.py                   LiteLLM Router shim — all LLM calls go here.
                             Routes to vLLM (AMD) or Ollama; normalizes
                             role names and citation token format.
    areas/
      nta.py                 NYC NTA 2020 polygon resolver

    flood_layers/
      sandy_inundation.py    NYC OD 5xsi-dfpx
      dep_stormwater.py      9i7c-xyvv (3 scenarios)
      ida_hwm.py             USGS STN Event 312
      prithvi_water.py       Ida pre/post diff polygons (offline-built)

    context/
      microtopo.py           DEM + TWI + HAND raster sampling
      nyc311.py              erm2-nwe9 buffer aggregation
      floodnet.py            api.floodnet.nyc Hasura GraphQL
      noaa_tides.py          live water level + residual
      nws_alerts.py          live alerts at point
      nws_obs.py             nearest ASOS hourly METAR

    live/
      ttm_forecast.py        Granite TTM r2 surge-residual nowcast

    assets/
      schools.py             DCP FacDB
      nycha.py               phvi-damg
      mta_entrances.py       i9wp-a4ja

  web/
    main.py                  FastAPI. Primary SSE at /api/agent/stream.
                             _run_compare() handles the compare intent
                             (sequential single_address × 2; no separate
                             intent module). /api/backend returns live
                             backend descriptor for the UI pill.
    static/
      agent.html             legacy primary UI (Svelte custom elements)
      dist/                  Svelte 5 custom-element bundle (committed).
                              Built from web/svelte/ via `npm run build`.

  web/sveltekit/             SvelteKit app (primary UI). Build →
                             web/sveltekit/build/. Served at / by FastAPI.
    src/routes/
      +page.svelte           landing + query form
      q/[queryId]/+page.svelte  live query page (SSE stream consumer)
    src/lib/components/
      briefing/
        Briefing.svelte      4-section cited paragraph renderer
        CompareBriefing.svelte  two-column compare layout + delta bar
      shell/StatusPill.svelte   AMD / Ollama / Local backend indicator

  web/svelte/                Legacy Svelte 5 custom-element source.
                             Builds <r-briefing>, <r-trace>, <r-sources-footer>.
                             Still loaded by agent.html / register/*.html.

  scripts/                   offline pre-compute + diagnostic probes
    run_prithvi_ida.py
    compute_hydrology_indices.py
    fetch_nyc_dem.py
    fetch_ida_hwms.py
    build_schools_register.py
    build_nycha_register.py
    build_mta_entrances_register.py
    probe_mellea.py          drives the SSE stream N times, dumps
                              per-attempt pass/fail to CSV

  corpus/                    5 LFS-tracked NYC policy PDFs
  data/                      LFS-tracked baked fixtures
    sandy_inundation.geojson
    prithvi_ida_2021.geojson 166 Hurricane Ida polygons
    ida_2021_hwms_ny.geojson
    nyc_dem_30m.tif, twi.tif, hand.tif
    schools.geojson, nycha.geojson, mta_entrances.geojson
    dep/                     Esri FileGDBs (DEP scenarios)
    registers/               pre-computed register outputs
```

---

## 10. Honest scope (what Riprap does NOT do)

- **Not a damage probability.** Riprap is exposure triage. We have no
  labeled flood-damage outcomes (claim records, insurance loss data),
  so we cannot calibrate. The tier is a literature-grounded prior,
  not a prediction.
- **Not a flood insurance rating.** For that, see FEMA Risk Rating 2.0
  (claims-driven GLM over decades of labeled outcomes).
- **Not a vulnerability assessment.** Engineering fragility (foundation
  type, electrical hardening, drainage condition), social capacity,
  and financial absorption are out of scope.
- **No sub-surface flooding.** Optical satellites can't see basement
  apartments or subway entrances. The dominant Hurricane Ida damage
  mode in NYC. Prithvi correctly emits no polygons for Hollis or
  Carroll Gardens. That silence is a feature, not a bug.
- **Vintage-bounded.** FEMA NFHL is years stale; DEP Stormwater Maps
  are 2021; corpus PDFs are point-in-time. All vintages are cited in
  the methodology panel.
- **Public infrastructure only.** ConEd substations, water-supply
  components, and other adversarially-sensitive registers are not
  published. NYC OD has the same redaction posture; we follow it.

---

## 11. Why local foundation models

1. **Data governance.** A newsroom with FOIL'd documents, an agency
   capital planner with internal data, or a researcher under IRB
   constraints can't paste organization context into a vendor LLM.
   All four models run inside this container; the org boundary
   holds. Public NYC and USGS services receive resolved address
   coordinates only; no LLM vendor does.
2. **Inference energy.** Granite 4.1 :3b draws roughly **0.03 Wh per
   query** vs an estimated **~0.3 Wh per query** for GPT-4o-class
   frontier models ([Epoch AI, 2025](https://epoch.ai/gradient-updates/how-much-energy-does-chatgpt-use)).
   Order of magnitude lower per-query inference energy. The
   methodology panel reports a per-query Wh estimate so users can
   verify.
3. **Reproducibility.** Apache-2.0 stack end to end; no commercial
   licenses required to reproduce the system.

---

## 12. Deployment

### 12.1 Hugging Face Spaces (production)

**HF Space**: `lablab-ai-amd-developer-hackathon/riprap-nyc` (cpu-basic).
Serves the FastAPI + SvelteKit UI. Hardware: cpu-basic (no GPU).

**AMD MI300X droplet** (separate): vLLM + riprap-models containers
(`services/riprap-models/`). The Space talks to the droplet over HTTP;
env vars `RIPRAP_LLM_BASE_URL` / `RIPRAP_ML_BASE_URL` point at it.
The bootstrap droplet was destroyed 2026-05-06; redeploy via
`scripts/deploy_droplet.sh <ip> <token>`.

LLM routing: `RIPRAP_LLM_PRIMARY=vllm` → AMD MI300X (30–50× faster than
T4 Ollama). Falls over to local Ollama on connection failure. Backend
status visible in the UI pill (top-right corner; backed by `GET /api/backend`).

Verified warm query times on AMD MI300X + vLLM (2026-05-06 probe):
- `single_address`: 5–12 s (4/4 Mellea, 0–2 rerolls)
- `neighborhood`: 3–5 s
- `compare` (two sequential legs): ~15 s

Cold-start after container restart: ~30 s for vLLM kernel JIT compile + prefix cache warmup. Run one warm-up query before a demo.

The SvelteKit build in `web/sveltekit/build/` and the Svelte bundle in
`web/static/dist/` are both committed, so HF Spaces runs no Node build step.

### 12.2 Local development

```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt
ollama pull granite4.1:3b
ollama pull granite4.1:8b
uvicorn web.main:app --reload --port 8000

# Frontend (only when changing components)
cd web/svelte && npm install && npm run build
```

The fixtures in `data/` and the policy PDFs in `corpus/` are LFS-
tracked. Granite Embedding and TTM download on first query.

### 12.3 Diagnostic probes

```bash
# Drive the live stream N times, dump per-attempt Mellea outcomes:
.venv/bin/python scripts/probe_mellea.py --query "Hollis" --runs 5
# Output: outputs/probe_*.csv with per-attempt pass/fail, paragraph,
#         elapsed time, reroll count.
```

---

## 13. License

Apache-2.0. All foundation models (Granite 4.1, Granite Embedding,
Prithvi-EO 2.0, Granite TimeSeries TTM r2) and all input datasets
(NYC OpenData, USGS, NOAA, NWS, FloodNet NYC, NASA/MS Planetary
Computer for HLS Sentinel-2) are public. Visual idiom adapted from
[NYC Planning Labs](https://planninglabs.nyc/).
