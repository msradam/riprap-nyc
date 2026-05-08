# Friday Mission Report: Performance Restoration & Audit
**Date:** Friday, May 8, 2026
**System State:** v0.5.0 (Healthy & Live)
**Target:** [lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space](https://lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space)

## 1. Performance Diagnosis
The "sudden slowness" (180s+ ReadTimeouts) reported during batch testing was isolated to a **Geospatial Processing Bottleneck** on the Hugging Face Space CPU.

*   **Primary Bottleneck:** The **Cornerstone Stone** (Hazard Reader). 
*   **Metric:** A single `dep` (NYC DEP Stormwater) spatial join against high-res GDB layers takes **~33.0s** on the shared HF CPU.
*   **Summation:** Summing across all specialists (Sandy, DEP, Microtopo, Ida HWM), a single query requires ~60-90s of pure spatial computation before the Reconciler begins.
*   **The Trap:** Automated batch tests triggered a queue. Because `OLLAMA_NUM_PARALLEL=1`, subsequent queries timed out waiting for the geospatial processing window of the previous query to clear.
*   **Steady State:** vLLM inference on the MI300X is healthy (**0.08s latency**), confirming the bottleneck is entirely local to the Space's CPU-bound spatial logic.

## 2. Stabilization Completed
- **Register Memory Fix:** Resolved a 503 error on the `mta_entrances` API. All three registers (NYCHA, Schools, MTA) are now pre-built and resident in Space memory.
- **Naming Alignment:** Patched `stoneRegistry.ts` to recognize shortened v0.5.0 step names (e.g., `sandy`, `nycha`). The UI now correctly displays active Stones instead of "outside NYC" ghosts.
- **Geocoding Resilience:** Implemented a robust Nominatim fallback that maps region/county data (e.g., "Kings County") to NYC boroughs ("Brooklyn"), bypassing the current NYC Geosearch outage.

## 3. Top 3 Canonical Demo Locations
Selected via city-wide register scan for maximum "Data Density":

| Rank | Location | High-Signal Assets | Query String |
| :--- | :--- | :--- | :--- |
| **1** | **Beach Channel Dr, Queens** | 8 Subway Entrances, 2 Schools, NYCHA | `2508 Beach Channel Drive, Queens - resilient infrastructure briefing` |
| **2** | **Coney Island Houses, BK** | 5 Schools, 3 Subway Entrances, NYCHA | `Coney Island I Houses, Brooklyn - emergency management briefing` |
| **3** | **Carleton Manor, Queens** | 7 Subway Entrances, 2 Schools | `Carleton Manor Houses, Queens - transit resilience assessment` |

## 4. Immediate Next Step: Optimization
The next logical phase is **Algorithmic Optimization of Cornerstone**.
- **Strategy:** Move from full `geopandas` spatial joins to a pre-indexed or point-in-polygon lookup for the Hazard Reader.
- **Constraint:** Maintain the "Five Stones" integrity while reducing the 33s `dep` join time to <1s.
- **Validation:** Retest the 20-query batch after optimization to confirm the performance gain.

---

## 5. Status as of May 9 — Demo-ready

All work from §4 plus a follow-on EO + frontend pass landed. **3/3 canonical demo queries pass live**; see `DEMO-PLAYBOOK.md` for talking points and the smoke-test invocation. Highlights:

- **Cornerstone** raster bake (`data/baked/*.tif`, 7 MB) — 33 s → <100 ms, full parity (see `experiments/22_cornerstone_optim/RESULTS.md`).
- **Keystone** register specialists (NYCHA / DOE / DOH) read pre-built JSON catalogs — 8+ min hang → <100 ms, no live polygon math.
- **Live EO chain fully wired through to the map**: `prithvi_eo_live`, `terramind_lulc`, `terramind_buildings`, `terramind` (synthesis) — every fine-tune emits `pred_b64` from the droplet, HF polygonises locally, frontend renders four new map layers.
- **UI honesty pass**: misleading "RIPRAP_HEAVY_SPECIALISTS=0" copy gone; skip messages reflect actual cause.
- **Droplet runbook + redeploy script** (`scripts/redeploy.sh <ip>`) inherit every committed source fix on next bring-up — no out-of-band patches required.

Final probe (Pioneer / Beach Channel / Coney Island): 30s / 26s / 10s, Mellea 4/4 on each, rich Stone activation across single_address and neighborhood paths.
