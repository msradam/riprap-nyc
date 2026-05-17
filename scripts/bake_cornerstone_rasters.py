"""Bake DEP scenarios + Sandy extent to compact GeoTIFFs in data/baked/.

The Cornerstone is a Hazard Reader — it reads what NYC's ground already
remembers (modeled DEP scenarios, empirical 2012 Sandy extent). All of
those layers are static, so we bake them once into uint8 GeoTIFFs in
EPSG:2263 (NYC State Plane, feet) and look up per-asset depth class
via rasterio.sample() instead of running gpd.sjoin per query.

Per-query latency drops from ~10 ms (warm) / ~33 s (cold-load) on the
HF Space CPU to ~3 ms with a 73 ms one-time cold-load. Baked footprint
is ~7 MB total versus ~46 MB GDBs + 87 MB Sandy GeoJSON.

See experiments/22_cornerstone_optim/RESULTS.md for the bench.

Run:
    uv run python scripts/bake_cornerstone_rasters.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from rasterio import features
from rasterio.transform import from_origin

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from app.flood_layers import dep_stormwater, sandy_inundation  # noqa: E402

NYC_CRS = "EPSG:2263"
RES_FT = 10.0
OUT_DIR = REPO / "data" / "baked"


def nyc_grid(res_ft: float = RES_FT):
    minx, miny = 910_000.0, 110_000.0
    maxx, maxy = 1_080_000.0, 280_000.0
    width = int(np.ceil((maxx - minx) / res_ft))
    height = int(np.ceil((maxy - miny) / res_ft))
    return from_origin(minx, maxy, res_ft, res_ft), width, height


def burn(gdf, value_col_or_const, out_path, transform, width, height):
    if isinstance(value_col_or_const, str):
        shapes = ((geom, int(val)) for geom, val
                  in zip(gdf.geometry, gdf[value_col_or_const], strict=False))
    else:
        v = int(value_col_or_const)
        shapes = ((geom, v) for geom in gdf.geometry)
    arr = features.rasterize(
        shapes=shapes, out_shape=(height, width), transform=transform,
        fill=0, dtype="uint8", merge_alg=rasterio.enums.MergeAlg.replace,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff", "dtype": "uint8", "count": 1,
        "width": width, "height": height, "transform": transform,
        "crs": NYC_CRS, "compress": "deflate", "predictor": 2,
        "tiled": True, "blockxsize": 512, "blockysize": 512, "nodata": 0,
    }
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(arr, 1)
    return arr


def bake_dep(scenario, transform, width, height):
    print(f"  baking {scenario}...", end=" ", flush=True)
    t0 = time.perf_counter()
    g = dep_stormwater.load(scenario).copy()
    g["Flooding_Category"] = g["Flooding_Category"].astype(int)
    # rasterize lowest first so highest category wins at overlaps
    g = g.sort_values("Flooding_Category", ascending=True)
    out = OUT_DIR / f"{scenario}.tif"
    arr = burn(g, "Flooding_Category", out, transform, width, height)
    dt = time.perf_counter() - t0
    print(f"{dt:5.1f}s  {out.stat().st_size/1e6:5.1f} MB  "
          f"nonzero={int((arr>0).sum()):,}")


def bake_sandy(transform, width, height):
    print("  baking sandy...", end=" ", flush=True)
    t0 = time.perf_counter()
    g = sandy_inundation.load().copy()
    out = OUT_DIR / "sandy.tif"
    arr = burn(g, 1, out, transform, width, height)
    dt = time.perf_counter() - t0
    print(f"{dt:5.1f}s  {out.stat().st_size/1e6:5.1f} MB  "
          f"nonzero={int((arr>0).sum()):,}")


def main():
    transform, width, height = nyc_grid(RES_FT)
    print(f"Grid: {width}x{height} px @ {RES_FT} ft/px")
    print(f"Output: {OUT_DIR}\n")
    bake_dep("dep_extreme_2080", transform, width, height)
    bake_dep("dep_moderate_2050", transform, width, height)
    bake_dep("dep_moderate_current", transform, width, height)
    bake_sandy(transform, width, height)
    total = sum(p.stat().st_size for p in OUT_DIR.glob("*.tif")) / 1e6
    print(f"\nTotal: {total:.1f} MB")


if __name__ == "__main__":
    main()
