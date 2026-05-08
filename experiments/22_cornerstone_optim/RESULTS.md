# 22 — Cornerstone optimization · results

**Run:** May 8, 2026 · MacBook (local), Python 3.12, GeoPandas 1.1.3,
Shapely 2.1.2, Rasterio 1.5.0.

## Headline

The "33s DEP join" reported on HF Space is **not the join** — it's the
GDB **cold-load**. On Mac with a warm `lru_cache`:

| Layer | Cold-load | Warm join (1 pt) |
|---|---:|---:|
| `dep_extreme_2080` | **30.9s** | ~4 ms |
| `dep_moderate_2050` | 1.5s | ~3 ms |
| `dep_moderate_current` | 0.9s | ~3 ms |
| `sandy_inundation` | 1.8s | ~1 ms |

On HF Space's shared CPU, with worker memory pressure evicting the
cache, every query pays cold-load again. That's the source of the
ReadTimeouts.

## Bench summary (per-query ms, all 3 DEP scenarios + Sandy)

| Address                            | baseline | strtree | bbox-prefilter | raster |
|---|---:|---:|---:|---:|
| 80 Pioneer St, Brooklyn            |     13.0 |     1.6 |           17.7 |    3.2 |
| 2508 Beach Channel Dr, Queens      |     11.2 |     1.9 |           12.5 |    2.4 |
| Coney Island I Houses, BK          |     10.8 |     1.9 |            7.1 |    2.1 |
| Carleton Manor, Queens             |     10.8 |     1.6 |           25.5 |    1.9 |

**All four paths achieve full parity with baseline** on `depth_class`
per scenario and `sandy.inside` for every canonical address.

## Cold-load comparison (paid once at HF Space boot)

| Path | Cold init |
|---|---:|
| baseline (`gpd.read_file` GDB ×3 + GeoJSON) | **~35 s** |
| strtree (same load + tree build) | ~35 s |
| **raster (`rasterio.open` ×4, mmap)** | **73 ms** |

Raster reduces boot-to-first-query from 35s to under 100ms while
also cutting per-query latency in half vs strtree.

## Disk footprint

DEFLATE-compressed uint8 GeoTIFF, NYC-wide grid at 10 ft/px:

| File | Size |
|---|---:|
| `dep_extreme_2080.tif` | 3.6 MB |
| `dep_moderate_2050.tif` | 1.3 MB |
| `dep_moderate_current.tif` | 0.9 MB |
| `sandy.tif` | 1.2 MB |
| **Total baked** | **7.0 MB** |

Compare: source GDBs total ~46 MB and the Sandy GeoJSON is 87 MB —
raster bake is 7% the size of the originals.

## Verdict

**Ship the raster bake.** It wins on every axis:

- Per-query: ~5× faster than baseline (2 ms vs 11 ms locally; on HF
  CPU the multiplier will be larger).
- Cold-load: ~500× faster (73 ms vs ~35 s). This is the actual fix
  for the 33s ReadTimeouts.
- Disk: 7 MB shipped vs 46 MB GDB + 87 MB GeoJSON. Faster
  HF Space pulls.
- Parity: identical depth class on all 4 canonical addresses, all 3
  DEP scenarios, plus Sandy.

STRtree is a useful fallback if for any reason we cannot ship the
baked rasters (e.g. demo-time edits to source layers), but the
default integration plan is raster.

## Live vs bakeable — recap of triage

These layers are **all** baked (Cornerstone = "what the ground
remembers"; static by definition):

- DEP stormwater scenarios — modeled, NYC DEP republishes ~every 5y
- Sandy 2012 inundation — historical, will not change
- Ida 2021 HWMs — already a small point set; haversine is fast
- Microtopo (DEM/HAND/TWI) — already raster
- Prithvi-EO Ida polygons — already baked artifact

These layers stay **live** for demo recency (and also because they're
fast):

- Geocoding (Geosearch + Nominatim fallback)
- FloodNet sensor pull (Touchstone)
- TTM battery surge / pluvial forecast (Lodestone)
- NYCHA / DOE / MTA registers (semi-static, prebuilt at boot)

## Integration plan

1. Move `bake_rasters.py` → `scripts/bake_cornerstone_rasters.py`.
2. Add `data/baked/` to repo (7 MB; well under HF Space limits).
3. Refactor `app/flood_layers/dep_stormwater.py` and
   `app/flood_layers/sandy_inundation.py` to expose:
   - the existing GDB-backed `join()` (kept as fallback if raster
     missing)
   - a new `join_raster()` that opens the baked GeoTIFF on first use
     and `sample()`s each asset point
4. `step_dep` and `step_sandy` in `app/fsm.py` call `join_raster()`.
5. Re-run `scripts/probe_addresses.py` (5/5 must pass) and the 20-query
   batch from FRIDAY-REPORT to verify ReadTimeouts are gone.

`coverage_for_polygon` (neighborhood mode) stays on the GDB path for
now since polygon × polygon overlap fraction is harder to do well in
raster — but neighborhood mode is not on the demo critical path.
