"""Probe live Sentinel-2 + Sentinel-1 fetch via Element 84's Earth Search
STAC API (which fronts s3://sentinel-cogs/, AWS Open Data).

Anonymous access. No registration. The raw data is ESA Copernicus Sentinel
under the Copernicus License (CC-BY-style). Element 84 hosts the COGs as a
pay-it-forward Open Data Registry mirror; AWS pays the egress.

Sovereignty disclosure for civic tech: this is a *private-cloud-hosted
mirror* of public ESA data. The DATA is ESA-authoritative; the HOST is
private. Use this for zero-friction demos; for production civic-tech
deployments, prefer ESA Copernicus Data Space (CDSE) directly with a
registered account.

This probe answers:
  1. Does Earth Search return recent results for a NYC point with no auth?
  2. What's the actual freshness (acquisition_date - today)?
  3. What's the per-chip wall-clock for fetch + read?
  4. Are returned chip dimensions usable by our TerraMind-NYC model?

Usage:
    python3 probe_earth_search.py --lat 40.7484 --lon -73.9857
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import os
# Sentinel-1 GRD on Earth Search lives in an unauthenticated S3 bucket;
# rasterio/GDAL needs the no-sign hint for VSIS3 reads. (S2 L2A is hosted
# via HTTPS and doesn't need this; S1 GRD reads through s3://... HREFs.)
os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_USE_HEAD", "NO")

CACHE = Path(__file__).parent / ".cache"
CACHE.mkdir(exist_ok=True, parents=True)

EARTH_SEARCH = "https://earth-search.aws.element84.com/v1"
S2_COLL = "sentinel-2-l2a"
S1_COLL = "sentinel-1-grd"  # GRD = ground-range-detected

# Bands we need to feed our TerraMind-NYC fine-tune (12 bands, ImpactMesh order).
# Earth Search uses lowercase asset keys; matches Sentinel-2 L2A scene structure.
S2_BANDS = ["coastal", "blue", "green", "red", "rededge1", "rededge2",
            "rededge3", "nir", "nir08", "nir09", "swir16", "swir22"]
# Mapping back to Sentinel-2 band identifiers for honest provenance.
S2_BAND_TO_ID = dict(zip(S2_BANDS,
    ["B01", "B02", "B03", "B04", "B05", "B06",
     "B07", "B08", "B8A", "B09", "B11", "B12"]))

CHIP_PX = 256
CHIP_M = CHIP_PX * 10  # 2.56 km tile centered on the point
HALF_M = CHIP_M / 2


@dataclass
class FetchResult:
    ok: bool
    err: str | None = None
    s2_acquired_iso: str | None = None
    s2_age_days: int | None = None
    s2_cloud_pct: float | None = None
    s2_product_id: str | None = None
    s1_acquired_iso: str | None = None
    s1_age_days: int | None = None
    s1_product_id: str | None = None
    elapsed_s: float | None = None
    bytes_fetched: int | None = None
    source: str = "earth_search_aws_open_data"
    license: str = "ESA Copernicus License (free for any use, attribution required)"


def search_recent(client, collection, bbox, max_age_days, max_cloud_pct=None):
    """Find the most recent scene covering bbox, optionally cloud-filtered."""
    today = datetime.utcnow().date()
    earliest = (today - timedelta(days=max_age_days)).isoformat()
    query = {"eo:cloud_cover": {"lt": max_cloud_pct}} if max_cloud_pct else None
    items = list(client.search(
        collections=[collection],
        bbox=bbox,
        datetime=f"{earliest}/{today.isoformat()}",
        query=query,
        max_items=20,
        limit=20,
    ).items())
    if not items:
        return None
    items.sort(key=lambda i: i.properties["datetime"], reverse=True)
    return items[0]


def fetch_one_chip(href, lat, lon, bbox_window):
    """Read a CHIP_PX×CHIP_PX window centered on (lat, lon) from a remote COG."""
    import rasterio
    from rasterio.warp import transform as warp_transform
    from rasterio.windows import from_bounds
    with rasterio.open(href) as src:
        # Project lat/lon to the COG's CRS to get a centered window
        lon_min, lat_min, lon_max, lat_max = bbox_window
        xs, ys = warp_transform("EPSG:4326", src.crs,
                                [lon_min, lon_max], [lat_min, lat_max])
        window = from_bounds(xs[0], ys[0], xs[1], ys[1], src.transform)
        return src.read(1, window=window, boundless=True, fill_value=0,
                        out_shape=(CHIP_PX, CHIP_PX))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, default=40.7484,
                    help="lat (default: Empire State Building)")
    ap.add_argument("--lon", type=float, default=-73.9857)
    ap.add_argument("--max-age-days", type=int, default=30,
                    help="how stale the recent scene is allowed to be")
    ap.add_argument("--max-cloud", type=float, default=30.0)
    ap.add_argument("--save-thumbnail", action="store_true")
    args = ap.parse_args()

    from pystac_client import Client
    import numpy as np

    print(f"[probe] lat,lon = ({args.lat}, {args.lon})", flush=True)
    print(f"[probe] STAC endpoint: {EARTH_SEARCH}", flush=True)

    # Build a small lon/lat bbox for the search (don't need a precise window
    # for STAC item discovery — just intersection with our point)
    d = 0.01  # ~1 km
    bbox = (args.lon - d, args.lat - d, args.lon + d, args.lat + d)
    chip_bbox = (args.lon - HALF_M / 85_000.0, args.lat - HALF_M / 111_000.0,
                 args.lon + HALF_M / 85_000.0, args.lat + HALF_M / 111_000.0)

    t0 = time.time()
    try:
        client = Client.open(EARTH_SEARCH)
    except Exception as e:
        print(f"[probe] FATAL: cannot reach STAC: {e}", flush=True)
        return 2

    res = FetchResult(ok=False)
    today = datetime.utcnow().date()
    bytes_fetched = 0

    # ---- S2 -------------------------------------------------------------------
    print("\n[probe] === Sentinel-2 L2A search ===", flush=True)
    t = time.time()
    s2_item = search_recent(client, S2_COLL, bbox, args.max_age_days,
                            max_cloud_pct=args.max_cloud)
    print(f"[probe] S2 search: {time.time()-t:.2f}s", flush=True)
    if not s2_item:
        res.err = "no recent S2 within age + cloud filter"
        print(f"[probe] FAIL: {res.err}", flush=True)
        print(json.dumps(res.__dict__, indent=2))
        return 1
    s2_dt = datetime.fromisoformat(s2_item.properties["datetime"].replace("Z", "+00:00"))
    res.s2_acquired_iso = s2_item.properties["datetime"]
    res.s2_age_days = (today - s2_dt.date()).days
    res.s2_cloud_pct = s2_item.properties.get("eo:cloud_cover")
    res.s2_product_id = s2_item.id
    print(f"[probe] S2 product: {s2_item.id}", flush=True)
    print(f"[probe] S2 acquired: {res.s2_acquired_iso} ({res.s2_age_days} days ago)",
          flush=True)
    print(f"[probe] S2 cloud cover: {res.s2_cloud_pct:.1f}%", flush=True)
    print(f"[probe] available bands: {sorted(s2_item.assets.keys())[:15]}...",
          flush=True)

    # Try reading a single band (red) to verify we can fetch a chip-window
    t = time.time()
    try:
        red_href = s2_item.assets["red"].href
        chip = fetch_one_chip(red_href, args.lat, args.lon, chip_bbox)
        print(f"[probe] S2 red band chip read: {time.time()-t:.2f}s, "
              f"shape={chip.shape}, dtype={chip.dtype}, "
              f"nz_pct={(chip > 0).mean()*100:.1f}%, "
              f"min/max={chip.min()}/{chip.max()}", flush=True)
        bytes_fetched += chip.nbytes
    except Exception as e:
        print(f"[probe] S2 chip read FAIL: {e}", flush=True)

    # ---- S1 -------------------------------------------------------------------
    print("\n[probe] === Sentinel-1 GRD search ===", flush=True)
    t = time.time()
    s1_item = search_recent(client, S1_COLL, bbox, args.max_age_days)
    print(f"[probe] S1 search: {time.time()-t:.2f}s", flush=True)
    if s1_item:
        s1_dt = datetime.fromisoformat(s1_item.properties["datetime"].replace("Z", "+00:00"))
        res.s1_acquired_iso = s1_item.properties["datetime"]
        res.s1_age_days = (today - s1_dt.date()).days
        res.s1_product_id = s1_item.id
        print(f"[probe] S1 product: {s1_item.id}", flush=True)
        print(f"[probe] S1 acquired: {res.s1_acquired_iso} "
              f"({res.s1_age_days} days ago)", flush=True)
        print(f"[probe] available assets: {sorted(s1_item.assets.keys())[:10]}...",
              flush=True)
        t = time.time()
        try:
            vv_key = "vv" if "vv" in s1_item.assets else \
                     ("VV" if "VV" in s1_item.assets else None)
            if vv_key:
                vv_href = s1_item.assets[vv_key].href
                chip = fetch_one_chip(vv_href, args.lat, args.lon, chip_bbox)
                print(f"[probe] S1 vv chip read: {time.time()-t:.2f}s, "
                      f"shape={chip.shape}, nz_pct={(chip > 0).mean()*100:.1f}%",
                      flush=True)
                bytes_fetched += chip.nbytes
            else:
                print(f"[probe] no vv/VV asset in S1 item", flush=True)
        except Exception as e:
            print(f"[probe] S1 chip read FAIL: {e}", flush=True)
    else:
        print(f"[probe] no recent S1 within {args.max_age_days} days", flush=True)

    res.elapsed_s = round(time.time() - t0, 2)
    res.bytes_fetched = bytes_fetched
    res.ok = bool(res.s2_acquired_iso)

    print("\n[probe] === Result ===", flush=True)
    print(json.dumps(res.__dict__, indent=2, default=str))
    return 0 if res.ok else 1


if __name__ == "__main__":
    sys.exit(main())
