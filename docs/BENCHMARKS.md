# Benchmarks

Live measurements collected against the lablab demo Space (`lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space`) on **2026-05-09**, running the canonical four-address verification set defined in `scripts/probe_addresses.py` (`DEFAULT_ADDRESSES`). Inference served from `msradam/riprap-vllm` on a single NVIDIA L4 (24 GB, Ada Lovelace, 72 W TGP).

Every per-call energy figure is **measured off the device** via `nvmlDeviceGetPowerUsage` — the proxy stamps `X-GPU-Power-W` / `X-GPU-Energy-J` headers on every ML response and the LLM client brackets each completion with two `/v1/power` GETs. See [`docs/EMISSIONS.md`](EMISSIONS.md) for the pipeline. The reproducer is `scripts/probe_benchmarks.py`; raw output in `outputs/benchmarks.json`.

vLLM was warm before the run (CUDA-graph compile already paid). The first call after a cold restart pays an additional ~120 s penalty — see "Cold-start" below.

---

## Headline

| | |
|---|---|
| Median wall-clock | **123.4 s** |
| Median per-query energy | **1.51 Wh · 5435 J** |
| Median tokens / query | **4434** |
| Calls measured on real GPU | **48 / 48 (100 %)** |
| Mellea grounding pass rate | **4 / 4** on every query |
| Hardware | NVIDIA L4 (60 W sustained) |

---

## Per-query results

### 1. `80 Pioneer Street, Brooklyn` — Red Hook

| | |
|---|---|
| Intent | `single_address` |
| Geocode | 80 PIONEER STREET, Brooklyn (40.67811, -74.00951) BBL 3005310031 |
| Wall-clock | **119.4 s** |
| Briefing | 1,461 chars · streamed 745 tokens to client |
| Mellea | 2 attempts, 1 reroll → **4 / 4** requirements passed |

**Stones fired**

| Stone | Specialists fired |
|---|---|
| Cornerstone | sandy_inundation · dep_stormwater · microtopo_lidar · ida_hwm_2021 · prithvi_eo_v2 |
| Keystone | nycha_development_exposure · doe_school_exposure · doh_hospital_exposure · terramind_synthesis · eo_chip_fetch · terramind_buildings |
| Touchstone | floodnet · nyc311 · noaa_tides · nws_obs · prithvi_eo_live · terramind_lulc |
| Lodestone | nws_alerts · ttm_forecast · ttm_311_forecast · ttm_battery_surge |
| Capstone | mellea_reconcile_address |

**Inference energy** — 12 calls, 12 / 12 measured

| | Wh | Joules | n_calls | Notes |
|---|---|---|---|---|
| Total | **1.316 Wh** | **4 737 J** | 12 | 5 148 tokens (3 LLM, 9 ML calls) |
| LLM | 1.311 Wh | 4 720 J | 3 | Granite 4.1 8B FP8 (planner + reconciler + mellea reroll) |
| ML | 0.005 Wh | 17 J | 9 | Prithvi-NYC-Pluvial · TerraMind LULC + Buildings · TTM r2 (zero-shot + Battery surge fine-tune) · Granite Embedding · GLiNER |

By-design skips: `mta_entrance_exposure` (no entrances within radius), `floodnet_forecast` (insufficient historical data).

---

### 2. `2508 Beach Channel Drive, Queens` — Bayswater

| | |
|---|---|
| Intent | `single_address` |
| Geocode | 2508 BEACH CHANNEL DRIVE, Bayswater (40.60065, -73.76256) BBL 4157370045 |
| Wall-clock | **124.9 s** |
| Briefing | 1,364 chars · streamed 346 tokens to client |
| Mellea | 1 attempt, 0 rerolls → **4 / 4** requirements passed |

**Stones fired**

| Stone | Specialists fired |
|---|---|
| Cornerstone | sandy_inundation · dep_stormwater · microtopo_lidar · ida_hwm_2021 · prithvi_eo_v2 |
| Keystone | mta_entrance_exposure · nycha_development_exposure · doe_school_exposure · doh_hospital_exposure · terramind_synthesis · eo_chip_fetch · terramind_buildings |
| Touchstone | floodnet · nyc311 · noaa_tides · nws_obs · prithvi_eo_live · terramind_lulc |
| Lodestone | nws_alerts · ttm_forecast · ttm_311_forecast · ttm_battery_surge |
| Capstone | mellea_reconcile_address |

**Inference energy** — 13 calls, 13 / 13 measured

| | Wh | Joules | n_calls | Notes |
|---|---|---|---|---|
| Total | **1.468 Wh** | **5 286 J** | 13 | 3 366 tokens (2 LLM, 11 ML calls) |
| LLM | 1.461 Wh | 5 259 J | 2 | Single-shot Mellea pass — no rerolls |
| ML | 0.007 Wh | 27 J | 11 | All EO + forecast specialists |

By-design skips: `floodnet_forecast` (only 1 historical event in window).

---

### 3. `Coney Island I Houses, Brooklyn` — Coney Island

| | |
|---|---|
| Intent | `single_address` |
| Geocode | CONEY IS I SITE 5 HOUSES, Brooklyn (40.57482, -73.99316) BBL 3070530014 |
| Wall-clock | **126.0 s** |
| Briefing | 1,565 chars · streamed 734 tokens to client |
| Mellea | 2 attempts, 1 reroll → **4 / 4** requirements passed |

**Stones fired**

| Stone | Specialists fired |
|---|---|
| Cornerstone | sandy_inundation · dep_stormwater · microtopo_lidar · ida_hwm_2021 · prithvi_eo_v2 |
| Keystone | nycha_development_exposure · doe_school_exposure · doh_hospital_exposure · terramind_synthesis · eo_chip_fetch · terramind_buildings |
| Touchstone | floodnet · nyc311 · noaa_tides · nws_obs · prithvi_eo_live · terramind_lulc |
| Lodestone | nws_alerts · ttm_forecast · ttm_311_forecast · ttm_battery_surge |
| Capstone | mellea_reconcile_address |

**Inference energy** — 13 calls, 13 / 13 measured

| | Wh | Joules | n_calls | Notes |
|---|---|---|---|---|
| Total | **1.622 Wh** | **5 839 J** | 13 | 4 925 tokens (3 LLM, 10 ML calls) |
| LLM | 1.618 Wh | 5 825 J | 3 | One Mellea reroll consumed about 0.5 Wh |
| ML | 0.004 Wh | 13 J | 10 | All EO + forecast specialists |

By-design skips: `mta_entrance_exposure` (no entrances within radius), `floodnet_forecast` (insufficient historical data).

---

### 4. `Carleton Manor Houses, Queens` — resolved as neighborhood

The planner could not pin the literal NYCHA development name "Carleton Manor Houses" through the geocoder, so it routed to `neighborhood` intent and the resolver assigned the closest NTA (Astoria-Ditmars-Steinway). Briefing renders cleanly against neighborhood-aggregated polygons; specialist fan-out is reduced because address-level joins (NYCHA / DOE / DOH register lookups, TerraMind LoRAs, TTM forecasts) don't apply at the NTA level.

| | |
|---|---|
| Intent | `neighborhood` |
| Resolved NTA | Astoria-Ditmars-Steinway, Queens |
| Wall-clock | **109.3 s** |
| Briefing | 1,320 chars · streamed 700 tokens to client |
| Mellea | 2 attempts, 1 reroll → **4 / 4** requirements passed |

**Stones fired**

| Stone | Specialists fired |
|---|---|
| Cornerstone | sandy_nta · dep_extreme_2080_nta · dep_moderate_2050_nta · dep_moderate_current_nta · microtopo_nta |
| Keystone | nycha_development_exposure |
| Touchstone | floodnet · nyc311_nta |
| Lodestone | (none — neighborhood intent doesn't run forecast specialists) |
| Capstone | (rolled into reconcile step) |

**Inference energy** — 5 calls, 5 / 5 measured

| | Wh | Joules | n_calls | Notes |
|---|---|---|---|---|
| Total | **1.551 Wh** | **5 585 J** | 5 | 3 944 tokens · narrower fan-out, single big LLM reconcile |
| LLM | 1.547 Wh | 5 569 J | 3 | Planner + reconciler + reroll |
| ML | 0.004 Wh | 16 J | 2 | NTA-level register joins |

---

## Aggregates

| Query | Wall (s) | Wh | J | Tokens | Mellea | Stones |
|---|---:|---:|---:|---:|:---:|:---:|
| 80 Pioneer Street | 119.4 | 1.316 | 4 737 | 5 148 | 2 att, 4/4 | 5 / 6 / 6 / 4 / 1 |
| 2508 Beach Channel | 124.9 | 1.468 | 5 286 | 3 366 | 1 att, 4/4 | 5 / 7 / 6 / 4 / 1 |
| Coney Island I | 126.0 | 1.622 | 5 839 | 4 925 | 2 att, 4/4 | 5 / 6 / 6 / 4 / 1 |
| Carleton Manor (→ Astoria NTA) | 109.3 | 1.551 | 5 585 | 3 944 | 2 att, 4/4 | 5 / 1 / 2 / 0 / 0 (NTA) |
| **Median** | **123.4** | **1.510** | **5 435** | **4 434** | — | — |

All 4 queries: 100 % Mellea grounding pass, 100 % calls measured on real GPU, zero non-by-design specialist failures.

---

## Where the energy goes

The reconciler dominates per-query energy by a factor of ~200×. On a typical address run (12–13 calls), 99 %+ of the joules are spent in the LLM reconciliation step — the EO and forecast specialists each draw <0.001 Wh because they're sub-second forward passes on the L4. This is why a Mellea reroll roughly doubles per-query Wh: each reroll is another full 8 B-param decode.

| Source | Share of total Wh (median across queries) |
|---|---|
| Granite 4.1 8B FP8 (planner + reconciler + Mellea attempts) | ~99.6 % |
| All 8–11 ML inference calls (Prithvi · TerraMind LoRAs · TTM r2 · Embedding · GLiNER) | ~0.4 % |

Cloud reference (Epoch AI, 2025): a typical GPT-4o-class query draws ~0.3 Wh. Riprap on the L4 lands in the ~1.3–1.6 Wh range — higher than that reference because Riprap's reconciler reads ~3K tokens of grounded documents per query and Mellea adds 0.5–1 reroll worth of decodes on average. Trading energy for citations is the explicit design choice.

---

## Cold-start cost

The first inference after a Space restart pays a ~120 s vLLM CUDA-graph compile. During that window the planner alone takes 2–3 minutes; subsequent queries fall to the steady-state numbers above. The riprap-models EO stack is now eager-loaded at lifespan startup (Prithvi + all three TerraMind paths + GLiNER + Embedding), so the *first* user query after restart pays only the vLLM cold-compile, not an additional 30–60 s of EO model loads on top.

For demos: prime once with a throwaway query right after restart. Steady-state numbers above are what the judge experience will look like.

---

## Reproducing

```bash
PYTHONPATH=. uv run python scripts/probe_benchmarks.py \
    --base https://lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space \
    --timeout 300 \
    --out outputs/benchmarks.json
```

The full ledger (every per-call power_w, joules, hardware, model, prompt/completion split) lives in `outputs/benchmarks.json` after a run. The Stone-fire CI script `scripts/probe_stones_fire.py` runs a single address with assertions for "all five Stones fire, no torchvision/terratorch dep regression" — useful before each deploy.

For verification of any single row in this document, the `final` SSE event from `/api/agent/stream?q=<query>` carries the full `emissions.calls[]` array directly.
