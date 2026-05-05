"""One-shot fetch of an NYC-wide DEM for the microtopo specialist.

Run this once before launching the agent or web UI:

    python scripts/fetch_nyc_dem.py

Output: data/nyc_dem_30m.tif (~few MB at 30 m, citywide).
We use 30 m resolution for the precomputed tile because at higher
resolution the file gets large and microtopo metrics (200/750 m
windows) don't need 10 m granularity.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import py3dep  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"
OUT = DATA / "nyc_dem_30m.tif"

# NYC bbox (lon_min, lat_min, lon_max, lat_max) plus a bit of padding
NYC_BBOX = (-74.30, 40.45, -73.65, 40.95)


def main() -> int:
    if OUT.exists():
        print(f"already exists: {OUT}", file=sys.stderr)
        return 0
    DATA.mkdir(exist_ok=True, parents=True)
    print(f"fetching NYC DEM @ 30 m for bbox {NYC_BBOX}", file=sys.stderr)
    dem = py3dep.get_dem(NYC_BBOX, resolution=30)
    print(f"  shape: {dem.shape}", file=sys.stderr)
    # Reproject to WGS84 if needed
    try:
        if dem.rio.crs and dem.rio.crs.to_epsg() != 4326:
            dem = dem.rio.reproject("EPSG:4326")
            print("  reprojected to EPSG:4326", file=sys.stderr)
    except Exception:
        pass
    dem.rio.to_raster(str(OUT), compress="DEFLATE", dtype="float32")
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
