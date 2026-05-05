"""Fetch a Sentinel-1 GRD chip from Microsoft Planetary Computer.

Phase 4 fallback: when Sentinel-2 is too cloudy for Phase 1's primary
path, we pull a recent S1 GRD scene (radar — sees through clouds —
that's the whole point of using SAR in this fallback) and feed it to
TerraMind to synthesize a plausible cloud-free S2L2A. The Phase 1
6-band-S2 segmentation head then runs against the synthesis.

Note on the brief's chain direction
-----------------------------------
The original Phase 4 brief specified S2L2A → S1GRD synthesis with the
"existing Sen1Floods11 head from Phase 1" running on synthesized SAR.
That doesn't work: Phase 1's head is `Prithvi-EO-2.0-300M-TL-
Sen1Floods11`, which takes 6-band Sentinel-2 *optical* input, not S1
SAR. There is no Apache-2.0 Sen1Floods11 fine-tune for S1 input.
Inverting the chain (real S1 → synthesized S2 → existing S2 head)
keeps the same model, license, schema, and map layer while actually
buying cloud-day robustness — S1 is the cloud-penetrating modality
in the first place. See RESULTS.md for the full pivot rationale.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

CACHE = Path(__file__).parent / ".cache"
CACHE.mkdir(exist_ok=True)

CHIP_PX = 1024
CHIP_M = CHIP_PX * 10  # 10.24 km square at 10 m
HALF_M = CHIP_M / 2

# TerraMind v1 expects S1GRD inputs as VV+VH dual-pol (per its
# tokenizer config). The PC `sentinel-1-grd` collection exposes both.
BANDS = ["vv", "vh"]


@dataclass
class S1ChipResult:
    item_id: str
    item_datetime: str
    out_path: Path  # 2-band GeoTIFF, EPSG:32618 (or whatever the scene's UTM is)
    bbox_4326: tuple[float, float, float, float]


def _cache_key(lat: float, lon: float, start: str, end: str) -> str:
    return f"s1_{lat:.4f}_{lon:.4f}_{start}_{end}"


def fetch(lat: float, lon: float, search_start: str = "2024-09-01",
          search_end: str = "2024-09-30",
          force: bool = False) -> S1ChipResult:
    import planetary_computer as pc
    import rioxarray  # noqa: F401  (registers .rio accessor)
    import xarray as xr
    from pyproj import Transformer
    from pystac_client import Client

    key = _cache_key(lat, lon, search_start, search_end)
    meta_path = CACHE / f"{key}.json"
    out_tif = CACHE / f"{key}.tif"
    if not force and meta_path.exists() and out_tif.exists():
        meta = json.loads(meta_path.read_text())
        return S1ChipResult(
            item_id=meta["item_id"],
            item_datetime=meta["item_datetime"],
            out_path=out_tif,
            bbox_4326=tuple(meta["bbox_4326"]),
        )

    client = Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=pc.sign_inplace,
    )
    delta = 0.02
    search = client.search(
        collections=["sentinel-1-grd"],
        bbox=[lon - delta, lat - delta, lon + delta, lat + delta],
        datetime=f"{search_start}/{search_end}",
        max_items=20,
        # SAR isn't filtered by clouds; pick whatever's most recent.
    )
    items = sorted(
        search.items(),
        key=lambda it: -(it.datetime.timestamp() if it.datetime else 0),
    )
    if not items:
        raise RuntimeError(
            f"No S1 GRD items near ({lat},{lon}) "
            f"in {search_start}..{search_end}"
        )
    item = items[0]

    # Reproject the point to the item's projected CRS for chip windowing.
    if "proj:epsg" in item.properties:
        epsg = int(item.properties["proj:epsg"])
    else:
        code = item.properties.get("proj:code", "")
        if code.startswith("EPSG:"):
            epsg = int(code.split(":", 1)[1])
        else:
            # S1 GRD items on PC sometimes lack proj:epsg; fall back to
            # WGS84/UTM zone for NYC longitude.
            epsg = 32618 if lon > -78 else 32617
    fwd = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    cx, cy = fwd.transform(lon, lat)
    xmin, xmax = cx - HALF_M, cx + HALF_M
    ymin, ymax = cy - HALF_M, cy + HALF_M

    arrs = []
    for b in BANDS:
        href = item.assets[b].href
        da = rioxarray.open_rasterio(href, masked=False).squeeze(drop=True)
        # S1 GRD on PC is delivered in EPSG:4326 (geographic). Reproject
        # to our UTM zone first, then clip.
        if str(da.rio.crs).upper() != f"EPSG:{epsg}":
            da = da.rio.reproject(f"EPSG:{epsg}", resolution=10)
        da = da.rio.clip_box(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax)
        if da.shape[0] >= CHIP_PX and da.shape[1] >= CHIP_PX:
            da = da.isel(y=slice(0, CHIP_PX), x=slice(0, CHIP_PX))
        arrs.append(da.astype("float32"))
    # Align both polarizations to the first one's grid.
    if arrs[1].shape != arrs[0].shape:
        arrs[1] = arrs[1].rio.reproject_match(arrs[0])
    stacked = xr.concat(arrs, dim="band", join="override").assign_coords(band=BANDS)
    stacked.rio.to_raster(out_tif, dtype="float32", compress="lzw")

    bbox_4326 = [lon - delta, lat - delta, lon + delta, lat + delta]
    meta = {
        "item_id": item.id,
        "item_datetime": str(item.datetime),
        "epsg": epsg,
        "bbox_4326": bbox_4326,
        "bands": BANDS,
    }
    meta_path.write_text(json.dumps(meta, indent=2, default=str))
    return S1ChipResult(
        item_id=item.id,
        item_datetime=str(item.datetime),
        out_path=out_tif,
        bbox_4326=tuple(bbox_4326),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--start", default="2024-09-01")
    ap.add_argument("--end", default="2024-09-30")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    r = fetch(args.lat, args.lon, args.start, args.end, force=args.force)
    print(json.dumps({
        "item_id": r.item_id,
        "datetime": r.item_datetime,
        "tif": str(r.out_path),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
