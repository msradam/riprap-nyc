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
