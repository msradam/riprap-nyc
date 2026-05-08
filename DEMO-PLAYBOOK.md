# Riprap Demo Playbook
**For:** AMD Developer Cloud Hackathon · May 4–10, 2026
**Live URL:** https://lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space

## What was fixed for the demo

1. **Cornerstone (Hazard Reader) latency** — DEP stormwater + Sandy 2012 join went from a 33-second cold-load to <100ms. Both layers are baked to compact GeoTIFFs (`data/baked/`, 7 MB total) sampled with rasterio. The 33s ReadTimeouts in batch testing are gone.

2. **Heavy register specialists no longer hang** — `step_nycha`, `step_doe_schools`, `step_doh_hospitals` previously did 20 polygon×polygon intersections per query (8+ minute hang on HF Space CPU). They now read pre-computed exposure flags from `data/registers/*.json` (sub-millisecond). Hospitals don't have a pre-built register but read the 30 KB GeoJSON directly and sample the new Cornerstone rasters per hit.

3. **Live EO chain enabled** — `eo_chip_fetch` (multi-modal Sentinel-2 + Sentinel-1 from Microsoft Planetary Computer) and `prithvi_eo_live` (NYC-Pluvial flood segmentation on live imagery, remote-inferenced on the AMD MI300X) are now firing on every query. This is the marquee live-data Stone for the demo.

4. **Misleading UI copy fixed** — three Stone specialists (TerraMind Buildings/LULC/Synthesis, Prithvi-NYC-Pluvial) previously claimed `RIPRAP_HEAVY_SPECIALISTS=0` when they silently skipped. Heavy specialists are actually enabled in production — the new copy reflects the actual cause (no recent <30% cloud Sentinel-2 chip / inference unavailable).

## The 3 demo queries

### 1. **2508 Beach Channel Drive, Queens** — full single_address activation
**What it shows:** the deep-data-density address from FRIDAY-REPORT. Single_address intent triggers every specialist:
- **Cornerstone:** Sandy outside, all DEP scenarios outside (this is Bayswater, just inland of the Sandy zone — useful counter-example)
- **Touchstone:** 2 FloodNet sensors (600m radius), 64 NYC 311 flood complaints, NOAA station 8516945 live, NWS hourly METAR
- **Lodestone:** Granite TTM forecasts (peak 0.47 ft surge ~2h ahead), TTM 311-forecast, NWS alerts
- **Keystone:** **7 MTA entrances** (6 in Sandy, 5 in DEP-2080), **2 NYCHA developments**, **5 schools** (4 in Sandy, 3 in DEP-2080), **1 hospital** — all with elevation/HAND from baked rasters
- **Live EO:** **`prithvi_eo_live`** fires with a real Sentinel-2 chip (≤30% cloud, ≤120 days old) — flood segmentation runs on the MI300X; **`eo_chip_fetch`** pulls multi-modal S2L2A + S1RTC chip
- **Capstone:** Granite Embedding RAG (3 hits) + GLiNER typed extraction + Mellea-grounded Granite-4.1 8B reconciliation (4/4 requirements pass)

**Talking points:** "This is what 'resilient infrastructure briefing' produces when every specialist fires. The Touchstone and Cornerstone disagree — Bayswater is just inland of Sandy 2012 but its subway entrances 200m away are deep in the zone. Live data: the Prithvi specialist just pulled a Sentinel-2 image from this month and ran flood segmentation on the MI300X."

### 2. **Coney Island I Houses, Brooklyn** — neighborhood path, narrative briefing
**What it shows:** neighborhood intent routing. Planner reads "Houses" with no street number → resolves to NTA polygon, runs the neighborhood specialist set (sandy_nta, dep_*_nta, nyc311_nta).
- Returns a Markdown briefing structured as Status / Empirical / Modeled / Policy
- Uses NTA-aggregated metrics ("X% of the neighborhood was inundated during Sandy")
- ~7-second total latency

**Talking points:** "Same system, different intent. The planner picks neighborhood for queries that name an area without a house number. The briefing is denser narrative; the underlying data is NTA-aggregated, which is the right unit for emergency-management framing."

### 3. **80 Pioneer Street, Brooklyn (Red Hook)** — single_address, full activation
**What it shows:** Red Hook is canonical Sandy turf. All Stones populated:
- **Cornerstone:** Sandy inside, DEP-2080 outside, microtopo 0.83m elevation (low-lying)
- **NYCHA:** Red Hook Houses (East/West) — both inside Sandy
- **Schools:** PS 27, PS 30 — both inside Sandy
- **Hospitals:** 3 nearby
- **MTA:** entrances inside Sandy
- **Live Sentinel-2 chip + Prithvi flood segmentation** runs

**Talking points:** "Red Hook is the canonical 'this is what we got wrong in 2012' address. The system surfaces a NYCHA development, a school, a hospital, and a subway entrance — all at risk in the same query. That's the demo: one query, four asset classes, every Stone audited, plus a live Sentinel-2 chip."

## Reading the trace

The trace UI groups specialists by Stone. Each row shows status (fired / silent / errored) and a one-line skip reason if silent. Silent isn't broken — it's the engineering-honest contract: when a specialist's preconditions aren't met, it stays silent rather than fabricating.

**Honest skips you'll see in the demo:**
- *"FloodNet sensor recurrence: sensor has < silent-floor historical events; forecast omitted"* — sensor too new to forecast
- *"NPCC4 SLR projection: not yet wired into FSM"* — out of scope, listed for transparency
- *"NWS public alerts: no active flood-relevant alerts at this address"* — true, no active alert today

**Specialists that may show as skipped/errored on the demo:**
- **TerraMind LULC / Buildings / Synthesis** — the droplet's MI300X has Prithvi loaded but not TerraMind weights yet. Specialists return *"remote inference unreachable + local torchvision binary unavailable on this deployment"* — honest. Out of scope to fix from the Space side; needs droplet rebuild with terramind models.
- **floodnet_forecast** — sensors with <5 historical events skip the forecast.

## Caveats to be ready for

- **NYCHA cards are binary, not pct-overlap** — per-query view shows `inside_sandy_2012: bool` and `dep_*_class: int` instead of `pct_inside_sandy_2012` floats. Same source data, less precise representation but fast (~ms instead of 8 min). The `/api/register/nycha` city-wide register is unchanged.
- **Heavy specialists are enabled** but may silently skip if Sentinel-2 chip fetch returns nothing recent for the query address. Prithvi-EO Live looks back 120 days for <30% cloud — most NYC addresses have a recent hit; very edge-of-NYC ones may not.
- **Inference is remote** on AMD MI300X via vLLM at `165.245.141.218:8001`. If the droplet is down, the reconciler will fail and the Capstone Stone won't render a paragraph; specialists will still fire and surface their data.
- **Bake re-runs** — `data/baked/*.tif` (7 MB) was generated once via `scripts/bake_cornerstone_rasters.py`. Re-bake when DEP scenarios get republished by NYC DEP (rare, ~every 5 years).
- **Register rebuilds** — `data/registers/*.json` are regenerated by `scripts/build_*_register.py` when the underlying NYCHA / DOE / NYS DOH datasets refresh.

## End-to-end smoke test

To verify before showtime:

```
.venv/bin/python scripts/probe_addresses.py \
  --base https://lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space \
  --addresses "2508 Beach Channel Drive, Queens|Coney Island I Houses, Brooklyn|80 Pioneer Street, Brooklyn" \
  --timeout 240
```

Expected: 3/3 PASS, each in 6–17 s after warm-up. If 2508 Beach Channel takes >60s, that's the post-restart pre-warm finishing — re-run.

## Final summary of changes shipped this cycle

| Change | Files | Effect |
|---|---|---|
| Cornerstone raster bake | `app/flood_layers/{dep_stormwater,sandy_inundation}.py`, `scripts/bake_cornerstone_rasters.py`, `data/baked/*.tif` | 33s → <100ms cold; <5ms per query |
| Register refactor | `app/registers/{nycha,doe_schools,doh_hospitals}.py`, `app/registers/_loader.py` | 8+ min hang → <100ms total |
| EO deps | `requirements.txt` (planetary-computer/pystac-client/rioxarray/xarray/einops) | Live Sentinel-2 + Prithvi remote inference |
| Deps gate split | `app/flood_layers/prithvi_live.py`, `app/context/terramind_synthesis.py`, `app/context/terramind_nyc.py` | Tier-1 chip-fetch separated from Tier-2 local-inference |
| UI honesty | `web/sveltekit/src/lib/data/stoneRegistry.ts`, `web/sveltekit/src/lib/client/registerAdapter.ts`, `web/sveltekit/src/routes/q/[queryId]/+page.svelte` | "RIPRAP_HEAVY_SPECIALISTS=0" copy gone; new NYCHA schema |
| HF env | `scripts/update_hf_env.sh` (RIPRAP_NYCHA_REGISTERS=1), set on live Space | Heavy register specialists actually attached to FSM |
| FSM consumers | `app/fsm.py`, `app/reconcile.py` | Match new NYCHA schema |
| Warmup hygiene | `web/main.py` | Drop 91 MB Sandy GeoJSON pre-load (no longer needed) |
