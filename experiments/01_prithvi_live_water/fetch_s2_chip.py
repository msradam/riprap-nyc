"""Fetch a Sentinel-2 L2A chip for a (lat, lon) from Microsoft
Planetary Computer.

Returns a 6-band float array (Blue, Green, Red, NarrowNIR(B8A), SWIR1,
SWIR2) at 10m, clipped to a 1024x1024 window centered on the point.
That's the band order Prithvi-EO 2.0 (Sen1Floods11 fine-tune) expects.

We pick the most-recent low-cloud scene (cloud_cover < 30%) intersecting
the point. Cached by (lat, lon, year-month-window) so dev iterations
don't re-hit STAC.

NB: we do NOT download the whole tile. rioxarray is asked to read only
the AOI window, so each call is a few-MB read, not the full 100MB tile.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

CACHE = Path(__file__).parent / ".cache"
CACHE.mkdir(exist_ok=True)


# 10 m resolution -> 1024 px = 10.24 km wide. Trim to the brief's 1024
# requirement; centered on the point.
CHIP_PX = 1024
CHIP_M = CHIP_PX * 10  # 10.24 km
HALF_M = CHIP_M / 2

# Prithvi-EO 2.0 Sen1Floods11 expects 6 bands in this exact order
# (per the IBM-NASA model card).
BANDS = ["B02", "B03", "B04", "B8A", "B11", "B12"]


@dataclass
class ChipResult:
    item_id: str
    item_datetime: str
    cloud_cover: float
    out_path: Path  # GeoTIFF, 6 bands, EPSG:32618
    rgb_thumbnail: Path  # PNG, RGB stretch for trace display
    bbox_4326: tuple[float, float, float, float]


def _cache_key(lat: float, lon: float, search_start: str, search_end: str) -> str:
    return f"chip_{lat:.4f}_{lon:.4f}_{search_start}_{search_end}"


def fetch(lat: float, lon: float, search_start: str = "2024-08-01",
          search_end: str = "2024-10-31",
          force: bool = False) -> ChipResult:
    """Find a low-cloud S2 L2A scene near (lat, lon) in [start, end] and
    cut a 1024x1024 6-band chip centered on the point. Returns paths to
    a GeoTIFF and a small RGB PNG for trace display."""
    import numpy as np
    import planetary_computer as pc
    import rioxarray  # noqa: F401  (registers .rio accessor)
    import xarray as xr
    from PIL import Image
    from pyproj import Transformer
    from pystac_client import Client

    key = _cache_key(lat, lon, search_start, search_end)
    meta_path = CACHE / f"{key}.json"
    out_tif = CACHE / f"{key}.tif"
    out_png = CACHE / f"{key}.png"
    if not force and meta_path.exists() and out_tif.exists() and out_png.exists():
        meta = json.loads(meta_path.read_text())
        return ChipResult(
            item_id=meta["item_id"],
            item_datetime=meta["item_datetime"],
            cloud_cover=meta["cloud_cover"],
            out_path=out_tif,
            rgb_thumbnail=out_png,
            bbox_4326=tuple(meta["bbox_4326"]),
        )

    client = Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=pc.sign_inplace,
    )
    # Small bbox around the point; STAC will return tiles whose footprint
    # intersects it, so we don't need a wide search.
    delta = 0.02
    search = client.search(
        collections=["sentinel-2-l2a"],
        bbox=[lon - delta, lat - delta, lon + delta, lat + delta],
        datetime=f"{search_start}/{search_end}",
        query={"eo:cloud_cover": {"lt": 30}},
        max_items=20,
    )
    items = sorted(search.items(),
                   key=lambda it: it.properties.get("eo:cloud_cover", 100))
    if not items:
        raise RuntimeError(
            f"No S2 L2A items <30% cloud near ({lat},{lon}) "
            f"in {search_start}..{search_end}"
        )
    item = items[0]
    cc = float(item.properties.get("eo:cloud_cover", -1))

    # Reproject point to the item's UTM zone and build a chip window
    # in projected meters around it. STAC clients vary on whether
    # they expose proj:epsg (legacy) or proj:code (current STAC ext).
    if "proj:epsg" in item.properties:
        epsg = int(item.properties["proj:epsg"])
    else:
        code = item.properties.get("proj:code", "")
        if code.startswith("EPSG:"):
            epsg = int(code.split(":", 1)[1])
        else:
            raise RuntimeError(
                f"item {item.id} missing proj:epsg / proj:code: "
                f"{list(item.properties.keys())}"
            )
    fwd = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    cx, cy = fwd.transform(lon, lat)
    xmin, xmax = cx - HALF_M, cx + HALF_M
    ymin, ymax = cy - HALF_M, cy + HALF_M

    # Read the 10 m reference band (B02) first, then reproject every
    # other band onto its exact pixel grid. This avoids subpixel
    # misalignment between 10 m and 20 m bands when they're naively
    # clip-boxed and concatenated (xr.concat outer-joins on coords,
    # which leaves NaNs at the edges).
    ref_da = rioxarray.open_rasterio(
        item.assets[BANDS[0]].href, masked=False).squeeze(drop=True)
    ref_da = ref_da.rio.clip_box(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax)
    ref_da = ref_da.isel(y=slice(0, CHIP_PX), x=slice(0, CHIP_PX))

    arrs = [ref_da.astype("float32")]
    for b in BANDS[1:]:
        href = item.assets[b].href
        da = rioxarray.open_rasterio(href, masked=False).squeeze(drop=True)
        da = da.rio.clip_box(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax)
        if da.shape != ref_da.shape:
            da = da.rio.reproject_match(ref_da)
        arrs.append(da.astype("float32"))
    stacked = xr.concat(arrs, dim="band", join="override")
    stacked = stacked.assign_coords(band=BANDS)

    # Save as a 6-band GeoTIFF.
    stacked.rio.to_raster(out_tif, dtype="float32", compress="lzw")

    # RGB thumbnail (B04, B03, B02) with a simple percentile stretch.
    rgb = np.stack([
        stacked.sel(band="B04").values,
        stacked.sel(band="B03").values,
        stacked.sel(band="B02").values,
    ], axis=-1)
    lo, hi = np.percentile(rgb, [2, 98])
    if hi <= lo:
        hi = lo + 1
    rgb = np.nan_to_num(rgb, nan=lo)
    rgb = np.clip((rgb - lo) / (hi - lo), 0, 1) * 255
    Image.fromarray(rgb.astype("uint8")).resize((256, 256)).save(out_png)

    bbox_4326 = [lon - delta, lat - delta, lon + delta, lat + delta]
    meta = {
        "item_id": item.id,
        "item_datetime": str(item.datetime),
        "cloud_cover": cc,
        "epsg": epsg,
        "bbox_4326": bbox_4326,
        "bands": BANDS,
    }
    meta_path.write_text(json.dumps(meta, indent=2, default=str))
    return ChipResult(
        item_id=item.id,
        item_datetime=str(item.datetime),
        cloud_cover=cc,
        out_path=out_tif,
        rgb_thumbnail=out_png,
        bbox_4326=tuple(bbox_4326),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--start", default="2024-08-01")
    ap.add_argument("--end", default="2024-10-31")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    r = fetch(args.lat, args.lon, args.start, args.end, force=args.force)
    print(json.dumps({
        "item_id": r.item_id,
        "datetime": r.item_datetime,
        "cloud_cover": r.cloud_cover,
        "tif": str(r.out_path),
        "png": str(r.rgb_thumbnail),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
