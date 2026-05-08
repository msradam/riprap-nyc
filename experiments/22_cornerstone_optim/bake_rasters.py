"""Bake DEP scenarios + Sandy extent to compact GeoTIFFs.

For each DEP scenario we produce a uint8 raster keyed by max
Flooding_Category (0=outside, 1/2/3 = depth class). Sandy is a uint8
0/1 mask. CRS is EPSG:2263 (feet) so callers project once and sample
at native units.

Resolution defaults to 10 ft. At that resolution a single pixel is
~smaller than a building footprint, which is more than fine for
point-in-polygon queries. NYC bbox at 10 ft fits comfortably in a
~12k x 16k uint8 array — a few hundred MB uncompressed but DEFLATE
compresses these heavily because most pixels are 0.

Run:
    uv run python experiments/22_cornerstone_optim/bake_rasters.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from rasterio import features
from rasterio.transform import from_origin

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from app.flood_layers import dep_stormwater, sandy_inundation  # noqa: E402

NYC_CRS = "EPSG:2263"
RES_FT = 10.0  # raster cell size in feet
OUT_DIR = REPO / "experiments" / "22_cornerstone_optim" / "baked"


def nyc_grid(res_ft: float = RES_FT):
    """Return (transform, width, height) covering all of NYC + harbor.

    Bounds chosen wide enough to cover every Cornerstone source.
    """
    minx, miny = 910_000.0, 110_000.0   # SW of Staten Island
    maxx, maxy = 1_080_000.0, 280_000.0  # NE of Bronx
    width = int(np.ceil((maxx - minx) / res_ft))
    height = int(np.ceil((maxy - miny) / res_ft))
    transform = from_origin(minx, maxy, res_ft, res_ft)
    return transform, width, height


def burn(gdf, value_col_or_const, out_path: Path, transform, width, height):
    if isinstance(value_col_or_const, str):
        shapes = ((geom, int(val)) for geom, val
                  in zip(gdf.geometry, gdf[value_col_or_const]))
    else:
        v = int(value_col_or_const)
        shapes = ((geom, v) for geom in gdf.geometry)

    arr = features.rasterize(
        shapes=shapes,
        out_shape=(height, width),
        transform=transform,
        fill=0,
        dtype="uint8",
        merge_alg=rasterio.enums.MergeAlg.replace,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver":    "GTiff",
        "dtype":     "uint8",
        "count":     1,
        "width":     width,
        "height":    height,
        "transform": transform,
        "crs":       NYC_CRS,
        "compress":  "deflate",
        "predictor": 2,
        "tiled":     True,
        "blockxsize": 512,
        "blockysize": 512,
        "nodata":    0,
    }
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(arr, 1)
    return arr


def bake_dep(scenario: str, transform, width, height) -> dict:
    print(f"  baking {scenario}...", end=" ", flush=True)
    t0 = time.perf_counter()
    g = dep_stormwater.load(scenario).copy()
    g["Flooding_Category"] = g["Flooding_Category"].astype(int)
    # rasterize lowest first so highest category wins at overlaps
    g = g.sort_values("Flooding_Category", ascending=True)
    out = OUT_DIR / f"{scenario}.tif"
    arr = burn(g, "Flooding_Category", out, transform, width, height)
    dt = time.perf_counter() - t0
    size_mb = out.stat().st_size / 1e6
    nz = int((arr > 0).sum())
    print(f"{dt:5.1f}s  {size_mb:5.1f} MB on disk  nonzero={nz:,}")
    return {"path": str(out), "elapsed_s": dt, "size_mb": size_mb, "nonzero_px": nz}


def bake_sandy(transform, width, height) -> dict:
    print("  baking sandy...", end=" ", flush=True)
    t0 = time.perf_counter()
    g = sandy_inundation.load().copy()
    out = OUT_DIR / "sandy.tif"
    arr = burn(g, 1, out, transform, width, height)
    dt = time.perf_counter() - t0
    size_mb = out.stat().st_size / 1e6
    nz = int((arr > 0).sum())
    print(f"{dt:5.1f}s  {size_mb:5.1f} MB on disk  nonzero={nz:,}")
    return {"path": str(out), "elapsed_s": dt, "size_mb": size_mb, "nonzero_px": nz}


def main():
    transform, width, height = nyc_grid(RES_FT)
    print(f"Grid: {width} x {height} px @ {RES_FT} ft/px (~{width*height/1e6:.0f} M cells)")
    print(f"Output: {OUT_DIR}")
    print()

    bake_dep("dep_extreme_2080", transform, width, height)
    bake_dep("dep_moderate_2050", transform, width, height)
    bake_dep("dep_moderate_current", transform, width, height)
    bake_sandy(transform, width, height)

    total_mb = sum(p.stat().st_size for p in OUT_DIR.glob("*.tif")) / 1e6
    print(f"\nTotal baked: {total_mb:.1f} MB")


if __name__ == "__main__":
    main()
