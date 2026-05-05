"""Pull NYC-only chips from ESA Φ-lab's Major-TOM Core datasets via HF.

Bypasses the bespoke STAC pipeline that was failing tonight. Major-TOM
already has every NYC-covering Sentinel-2 + Sentinel-1 chip pre-staged
on Hugging Face, indexed by grid cell, with a documented filter API.

Outputs a directory tree compatible with our Phase-2 packager / TerraTorch
(or, if we accept the Major-TOM-native MajorTOM dataset class, just
points to the filtered manifest and a downloaded chip cache).

Usage:
    python3 major_tom_nyc.py --out /root/terramind_nyc/major_tom_nyc \\
                             --collections L2A S1RTC DEM \\
                             --max-cloud 30
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Major-TOM helpers — clone of github.com/ESA-PhiLab/Major-TOM placed on
# the container's PYTHONPATH (or pip-installed if a wheel exists).
from MajorTOM.metadata_helpers import (
    metadata_from_url, filter_metadata, filter_download
)
from shapely.geometry import box


# NYC five-borough convex hull, buffered slightly to capture marine
# fringes that are still within the city boundary.
NYC_BBOX = (-74.30, 40.45, -73.65, 40.95)
NYC_REGION = box(*NYC_BBOX)

# Major-TOM Core dataset slugs. Each has its own metadata.parquet.
COLLECTIONS = {
    "L2A":   "Major-TOM/Core-S2L2A",
    "L1C":   "Major-TOM/Core-S2L1C",
    "S1RTC": "Major-TOM/Core-S1RTC",
    "DEM":   "Major-TOM/Core-DEM",
}


def fetch_filtered(coll_slug: str, out_root: Path,
                   max_cloud: float, daterange: tuple[str, str]):
    """Download one Major-TOM Core dataset's NYC-only chips."""
    print(f"[major-tom] === {coll_slug} ===", flush=True)
    meta_url = f"https://huggingface.co/datasets/{coll_slug}/resolve/main/metadata.parquet?download=true"
    meta_local = out_root / "metadata" / f"{coll_slug.split('/')[-1]}.parquet"
    meta_local.parent.mkdir(parents=True, exist_ok=True)

    gdf = metadata_from_url(meta_url, str(meta_local))
    print(f"[major-tom] {coll_slug}: total chips = {len(gdf):,}", flush=True)

    # filter_metadata defaults to cloud_cover=(0,100) and nodata=(0,1.0)
    # which fail on S1/DEM that lack those columns. Set to None per-collection.
    filter_kwargs = {"region": NYC_REGION,
                     "cloud_cover": None, "nodata": None, "daterange": None}
    if "S2" in coll_slug:
        filter_kwargs["cloud_cover"] = (0.0, max_cloud)
        filter_kwargs["daterange"] = daterange
        filter_kwargs["nodata"] = (0.0, 0.0)
    elif "S1" in coll_slug:
        filter_kwargs["daterange"] = daterange

    nyc_df = filter_metadata(gdf, **filter_kwargs)
    print(f"[major-tom] {coll_slug}: after NYC filter = {len(nyc_df):,}",
          flush=True)
    if len(nyc_df) == 0:
        print(f"[major-tom] {coll_slug}: 0 NYC chips, skipping download",
              flush=True)
        return None

    download_dir = out_root / "data" / coll_slug.split("/")[-1]
    download_dir.mkdir(parents=True, exist_ok=True)

    # S1RTC parquets have columns vv, vh (not Bxx + cloud_mask).
    # DEM has just elevation. The default in filter_download is hardcoded
    # for S2's column convention; we override for non-S2 collections.
    if "S1" in coll_slug:
        tif_columns = ["vv", "vh"]
    elif "DEM" in coll_slug:
        tif_columns = ["DEM"]
    else:
        tif_columns = None

    filter_download(nyc_df,
                    local_dir=str(download_dir),
                    source_name=coll_slug.split("-")[-1],  # e.g. "L2A"
                    by_row=True,
                    tif_columns=tif_columns)
    nyc_df.to_parquet(out_root / "metadata" /
                      f"{coll_slug.split('/')[-1]}_nyc.parquet")
    return nyc_df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True,
                    help="output root directory")
    ap.add_argument("--collections", nargs="+",
                    default=["L2A", "S1RTC", "DEM"],
                    choices=list(COLLECTIONS.keys()),
                    help="which Major-TOM Core collections to pull")
    ap.add_argument("--max-cloud", type=float, default=30.0,
                    help="max cloud cover percent for S2 chips")
    ap.add_argument("--date-from", default="2020-01-01")
    ap.add_argument("--date-to",   default="2025-12-31")
    args = ap.parse_args()

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    summary = {}
    for c in args.collections:
        df = fetch_filtered(COLLECTIONS[c], out_root,
                            max_cloud=args.max_cloud,
                            daterange=(args.date_from, args.date_to))
        summary[c] = 0 if df is None else len(df)

    print("\n[major-tom] summary:")
    for c, n in summary.items():
        print(f"  {c}: {n} NYC chips")
    return 0


if __name__ == "__main__":
    sys.exit(main())
