"""Build the NYC pluvial-flood training set for Prithvi-EO 2.0 fine-tuning.

Reuses Riprap's already-baked Hurricane Ida 2021 polygons (166 polys, the
output of a prior Prithvi offline pre-compute) as the POSITIVE class. Pulls
matching Sentinel-2 6-band chips from the live Earth Search STAC for
acquisition windows around the polygon dates.

Negative samples come from the Major-TOM cached NYC chips (which are
clear-sky, non-event acquisitions) — these provide "no flood" examples to
balance the binary classifier.

Output: ImpactMesh-style flat directory with S2 chips + binary masks,
loadable by terratorch's standard datamodule.

Usage on droplet:
    python3 build_dataset.py \\
        --ida-polys /root/data/prithvi_ida_2021.geojson \\
        --major-tom-root /root/terramind_nyc/major_tom/data \\
        --out /root/terramind_nyc/prithvi_nyc \\
        --pos-per-poly 1 --neg-from-cache 100
"""
from __future__ import annotations

import argparse, json, os, sys, time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import Affine, from_bounds
from rasterio.features import rasterize
from rasterio.warp import transform as warp_transform, transform_geom
import geopandas as gpd

CHIP_PX = 224
PRITHVI_BANDS = ["B02", "B03", "B04", "B8A", "B11", "B12"]  # Sen1Floods11 order
EARTH_SEARCH = "https://earth-search.aws.element84.com/v1"

# Earth Search asset key mapping for the Prithvi 6-band slice
EARTH_SEARCH_ASSET = {
    "B02": "blue",
    "B03": "green",
    "B04": "red",
    "B8A": "nir08",
    "B11": "swir16",
    "B12": "swir22",
}

os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")


def fetch_s2_chip_at(client, lat, lon, target_date, max_age_days=14,
                     max_cloud=30):
    """Find a low-cloud S2 acquisition near target_date within max_age_days,
    return a 6-band chip centered on (lat, lon)."""
    start = (target_date - timedelta(days=max_age_days)).isoformat()
    end = (target_date + timedelta(days=max_age_days)).isoformat()
    d = 0.01
    bbox = (lon - d, lat - d, lon + d, lat + d)
    items = list(client.search(
        collections=["sentinel-2-l2a"],
        bbox=bbox,
        datetime=f"{start}/{end}",
        query={"eo:cloud_cover": {"lt": max_cloud}},
        max_items=20,
    ).items())
    if not items:
        return None
    items.sort(
        key=lambda i: abs((date.fromisoformat(i.properties["datetime"][:10])
                          - target_date).days))
    item = items[0]
    actual_date = date.fromisoformat(item.properties["datetime"][:10])

    # Compute window in each band's CRS
    HALF_M = CHIP_PX / 2 * 10  # ~1.12 km half-side at 10m
    chip_lon_min = lon - HALF_M / 85_000.0
    chip_lon_max = lon + HALF_M / 85_000.0
    chip_lat_min = lat - HALF_M / 111_000.0
    chip_lat_max = lat + HALF_M / 111_000.0

    out = np.zeros((len(PRITHVI_BANDS), CHIP_PX, CHIP_PX), dtype=np.float32)
    transform = None
    crs = None
    for i, band in enumerate(PRITHVI_BANDS):
        asset_key = EARTH_SEARCH_ASSET[band]
        href = item.assets[asset_key].href
        with rasterio.open(href) as src:
            xs, ys = warp_transform(
                "EPSG:4326", src.crs,
                [chip_lon_min, chip_lon_max], [chip_lat_min, chip_lat_max])
            from rasterio.windows import from_bounds as wfb
            window = wfb(xs[0], ys[0], xs[1], ys[1], src.transform)
            data = src.read(1, window=window, boundless=True, fill_value=0,
                            out_shape=(CHIP_PX, CHIP_PX))
            if i == 0:
                transform = src.window_transform(window)
                crs = src.crs
        out[i] = data.astype(np.float32)
    return out, transform, crs, actual_date, item.id, item.properties.get("eo:cloud_cover")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ida-polys", required=True,
                    help="Riprap's prithvi_ida_2021.geojson")
    ap.add_argument("--major-tom-root", required=True,
                    help="cache of clear-sky NYC chips for negative samples")
    ap.add_argument("--out", required=True)
    ap.add_argument("--pos-per-poly", type=int, default=1,
                    help="positive S2 chip extractions per Ida polygon")
    ap.add_argument("--neg-from-cache", type=int, default=100,
                    help="number of negative chips to draw from Major-TOM")
    ap.add_argument("--ida-event-date", default="2021-09-02",
                    help="canonical Ida post-event date")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    out_root = Path(args.out)
    (out_root / "data" / "S2L2A").mkdir(parents=True, exist_ok=True)
    (out_root / "data" / "MASK").mkdir(parents=True, exist_ok=True)
    (out_root / "split").mkdir(parents=True, exist_ok=True)

    polys = gpd.read_file(args.ida_polys)
    if polys.crs is None or polys.crs.to_epsg() != 4326:
        polys = polys.to_crs("EPSG:4326")
    print(f"[ph14] {len(polys)} Ida polygons", flush=True)

    target_date = date.fromisoformat(args.ida_event_date)

    from pystac_client import Client
    client = Client.open(EARTH_SEARCH)

    summary = {"positive": [], "negative": [], "failed": []}

    # --- Positive samples: Ida polygons + S2 chip near event date -----------
    print(f"[ph14] fetching positive S2 chips near {target_date}...", flush=True)
    for idx, row in polys.iterrows():
        if len(summary["positive"]) >= args.pos_per_poly * len(polys):
            break
        c = row.geometry.centroid
        lat, lon = float(c.y), float(c.x)
        try:
            r = fetch_s2_chip_at(client, lat, lon, target_date)
            if r is None:
                summary["failed"].append({"idx": int(idx), "reason": "no_s2"})
                continue
            chip, tf, crs, actual_date, prod_id, cc = r
            chip_id = f"ida_pos_{idx:04d}"
            np.savez_compressed(out_root / "data" / "S2L2A" / f"{chip_id}.npz",
                                bands=chip)
            # Rasterize THIS polygon onto the chip grid (we capture the
            # within-tile flood extent, not the full 6.7km tile)
            poly_in_crs = transform_geom("EPSG:4326", str(crs),
                                          row.geometry.__geo_interface__)
            mask = rasterize([(poly_in_crs, 1)], out_shape=(CHIP_PX, CHIP_PX),
                             transform=tf, fill=0, dtype=np.uint8)
            with rasterio.open(out_root / "data" / "MASK" /
                               f"{chip_id}_annotation_flood.tif", "w",
                               driver="GTiff", height=CHIP_PX, width=CHIP_PX,
                               count=1, dtype="int8", transform=tf, crs=crs) as dst:
                dst.write(mask.astype("int8"), 1)
            summary["positive"].append({
                "chip_id": chip_id,
                "lat": lat, "lon": lon,
                "s2_acquired": str(actual_date),
                "s2_product": prod_id,
                "s2_cloud_pct": cc,
                "n_flood_pixels": int(mask.sum()),
            })
            print(f"  + {chip_id}: {actual_date} cc={cc:.1f}% "
                  f"flood_px={int(mask.sum())}", flush=True)
        except Exception as e:
            print(f"  ! {idx}: {type(e).__name__}: {e}", flush=True)
            summary["failed"].append({"idx": int(idx), "reason": str(e)})

    # --- Negative samples: cached Major-TOM clear-sky NYC chips ------------
    print(f"\n[ph14] sampling {args.neg_from_cache} negatives from Major-TOM cache",
          flush=True)
    s2_root = Path(args.major_tom_root) / "Core-S2L2A" / "L2A"
    cells = []
    for row_dir in sorted(s2_root.iterdir()):
        if not row_dir.is_dir(): continue
        for cell_dir in sorted(row_dir.iterdir()):
            if not cell_dir.is_dir(): continue
            products = sorted(cell_dir.iterdir())
            if products: cells.append(products[0])
    print(f"  {len(cells)} parent cells available", flush=True)

    import random
    rng = random.Random(args.seed)
    rng.shuffle(cells)
    n_neg = 0
    for parent_dir in cells[:args.neg_from_cache]:
        if n_neg >= args.neg_from_cache:
            break
        try:
            stack = []
            transform = None
            crs = None
            for band in PRITHVI_BANDS:
                with rasterio.open(parent_dir / f"{band}.tif") as src:
                    H, W = src.shape
                    # Center crop CHIP_PX from the 1068x1068 parent
                    cx, cy = W // 2, H // 2
                    win_off_x = cx - CHIP_PX // 2
                    win_off_y = cy - CHIP_PX // 2
                    from rasterio.windows import Window
                    win = Window(win_off_x, win_off_y, CHIP_PX, CHIP_PX)
                    data = src.read(1, window=win, boundless=True, fill_value=0,
                                    out_shape=(CHIP_PX, CHIP_PX))
                    if transform is None:
                        transform = src.window_transform(win)
                        crs = src.crs
                stack.append(data.astype(np.float32))
            chip = np.stack(stack)
            chip_id = f"nyc_neg_{n_neg:04d}"
            np.savez_compressed(out_root / "data" / "S2L2A" / f"{chip_id}.npz",
                                bands=chip)
            mask = np.zeros((CHIP_PX, CHIP_PX), dtype=np.int8)
            with rasterio.open(out_root / "data" / "MASK" /
                               f"{chip_id}_annotation_flood.tif", "w",
                               driver="GTiff", height=CHIP_PX, width=CHIP_PX,
                               count=1, dtype="int8", transform=transform,
                               crs=crs) as dst:
                dst.write(mask, 1)
            summary["negative"].append({"chip_id": chip_id,
                                         "parent": parent_dir.name})
            n_neg += 1
        except Exception as e:
            print(f"  ! {parent_dir.name}: {e}", flush=True)
            continue

    # --- Stratified split: 70/15/15, both classes proportional --------------
    rng.shuffle(summary["positive"])
    rng.shuffle(summary["negative"])

    def split_list(lst, train_frac=0.7, val_frac=0.15):
        n = len(lst)
        n_tr = int(train_frac * n)
        n_va = int(val_frac * n)
        return lst[:n_tr], lst[n_tr:n_tr+n_va], lst[n_tr+n_va:]

    pos_tr, pos_va, pos_te = split_list(summary["positive"])
    neg_tr, neg_va, neg_te = split_list(summary["negative"])
    splits = {
        "train": [r["chip_id"] for r in pos_tr + neg_tr],
        "val":   [r["chip_id"] for r in pos_va + neg_va],
        "test":  [r["chip_id"] for r in pos_te + neg_te],
    }
    for sp, ids in splits.items():
        rng.shuffle(ids)
        (out_root / "split" / f"impactmesh_flood_{sp}.txt").write_text(
            "\n".join(ids) + "\n")

    Path(out_root, "build_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\n[ph14] === Summary ===")
    print(f"  positives: {len(summary['positive'])} (Ida polygons with matched S2)")
    print(f"  negatives: {len(summary['negative'])} (clear-sky NYC chips)")
    print(f"  train/val/test: {len(splits['train'])}/{len(splits['val'])}/{len(splits['test'])}")


if __name__ == "__main__":
    sys.exit(main())
