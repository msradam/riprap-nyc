# 22 — Cornerstone optimization

**Goal:** drop the 33s DEP join and 5–10s Sandy join on the HF Space CPU
to <1s without changing Stone semantics.

## Layer triage: live vs bakeable

The Cornerstone is a **Hazard Reader** — it reads what the ground
*already remembers*. Every Cornerstone source is by definition
historical or modeled, so the per-query cost of recomputing a
spatial join is unwarranted. Live recency belongs to the **Touchstone**
(FloodNet) and **Lodestone** (forecasts), not here.

| Source | Nature | Updates | Verdict |
|---|---|---|---|
| `dep_stormwater` | Modeled scenarios (2050/2080 SLR + design storm) | NYC DEP republishes every few years | **bake** to GeoTIFF |
| `sandy_inundation` | Empirical 2012 extent | Will not change | **bake** to GeoTIFF |
| `ida_hwm` | USGS HWMs (point set, ~few hundred) | Will not change | already O(n) haversine — leave alone |
| `prithvi_water` | Pre-baked Ida polygons | Will not change | already baked |
| `microtopo` (DEM/HAND/TWI) | LiDAR-derived rasters | Re-baked on terrain changes | already raster — already fast |

**Live (kept live for demo recency):**
- Geocoding (Geosearch + Nominatim fallback)
- FloodNet sensor pull (Touchstone)
- TTM battery surge / pluvial forecast (Lodestone)
- NYCHA / DOE / MTA registers (semi-static, prebuilt at boot — already fast)

So this experiment only touches the two slow Cornerstone specialists.

## Approaches benchmarked

1. **baseline** — current `gpd.sjoin` (full layer)
2. **strtree** — pre-warm `gdf.sindex`, query with single-point `intersects`
3. **bbox-prefilter** — clip layer to bbox(point, 100ft) then sjoin
4. **raster** — bake polygons → uint8 GeoTIFF in EPSG:2263; `rasterio.sample()` per point

For DEP, the raster encodes max `Flooding_Category` per pixel
(0=outside, 1/2/3 = depth class). Sandy is a 1-bit raster.

## Files

- `bench.py` — runs all four paths on canonical addresses
- `bake_rasters.py` — one-time bake of DEP + Sandy to GeoTIFF
- `RESULTS.md` — written after `bench.py` completes

## Canonical addresses

Per `scripts/probe_addresses.py` (`DEFAULT_ADDRESSES`):

1. 80 Pioneer Street, Brooklyn — (40.6790, -74.0050)
2. 2508 Beach Channel Drive, Queens — (40.5867, -73.8062)
3. Coney Island I Houses, Brooklyn — (40.5772, -73.9870)
4. Carleton Manor, Queens — (40.6033, -73.7626)
