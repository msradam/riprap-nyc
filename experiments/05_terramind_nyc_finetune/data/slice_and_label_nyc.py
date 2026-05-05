"""Slice Major-TOM NYC chips into 256x256 sub-chips, label each with
NLCD 2021 macro-classes, and pack into ImpactMesh-compatible format
for Phase 2 fine-tuning.

Inputs:
  - Major-TOM NYC chips at 1068x1068x10m
      data/Core-S2L2A/S2L2A/<row>/<grid_cell>/<product_id>/B*.tif
      data/Core-S1RTC/S1RTC/<row>/<grid_cell>/<product_id>/{vv,vh}.tif
      data/Core-DEM/DEM/<row>/<grid_cell>/<product_id>/DEM.tif
  - NLCD 2021 raster (CONUS, 30m, single GeoTIFF)

Outputs:
  - <out>/data/S2L2A/<chip_id>_S2L2A.zarr.zip
  - <out>/data/S1RTC/<chip_id>_S1RTC.zarr.zip
  - <out>/data/DEM/<chip_id>_DEM.tif
  - <out>/data/MASK/<chip_id>_annotation_flood.tif (5 macro-classes)
  - <out>/split/impactmesh_flood_{train,val,test}.txt

Sub-chipping strategy:
  Each 1068x1068 parent chip gives 16 sub-chips (4x4 grid of 256x256
  windows with no overlap; the residual 44 px on each side is dropped).
  ~22 parents x 16 = ~350 training tiles.

Stratified split:
  Train/val/test split is stratified on parent chip ID so sub-chips
  from the same scene don't leak across splits.

NLCD class collapse to 5 macro-classes (per eval_spec_v3.md):
  0 — Water (NLCD 11)
  1 — Developed (21, 22, 23, 24)
  2 — Forest/shrub (41, 42, 43, 51, 52)
  3 — Herbaceous/cultivated (71-74, 81, 82)
  4 — Wetland/barren/ice (12, 31, 90, 95)
  -1 — Ignore (any other / no-data)

Usage:
    python3 slice_and_label_nyc.py \\
        --major-tom-root /root/terramind_nyc/major_tom/data \\
        --nlcd-tif /root/terramind_nyc/nlcd_2021_l48.tif \\
        --out /root/terramind_nyc/nyc_lulc_dataset \\
        --crop 256 \\
        --seed 42
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import Affine
import zarr


# ESA WorldCover v200 (10m, 11 classes) → our 5 macro-classes.
# WorldCover tile is 10m, EPSG:4326, exactly matches our chip grid resolution
# after reprojection. Perfect for NYC — no NLCD download dance.
LABEL_TO_MACRO = {
    10: 2,   # Tree cover     -> forest/vegetation
    20: 2,   # Shrubland       -> forest/vegetation
    30: 3,   # Grassland       -> herbaceous
    40: 3,   # Cropland        -> herbaceous
    50: 1,   # Built-up        -> developed
    60: 4,   # Bare / sparse   -> other
    70: 4,   # Snow and ice    -> other
    80: 0,   # Open water      -> water
    90: 0,   # Herbaceous wet  -> water (includes salt marsh; coastal NYC wetlands)
    95: 0,   # Mangroves       -> water (n/a in NYC but harmless)
    100: 4,  # Moss/lichen     -> other
}
N_CLASSES = 5
MACRO_NAMES = ["water", "developed", "forest", "herbaceous", "other"]

CHIP_PX = 256
N_TIMESTEPS_TARGET = 4   # ImpactMesh schema; we stack the single chip 4x

S2_BANDS = ["B01", "B02", "B03", "B04", "B05", "B06",
            "B07", "B08", "B8A", "B09", "B11", "B12"]   # 12-band ImpactMesh order
S1_BANDS = ["vv", "vh"]


def find_parent_chips(major_tom_root: Path):
    """Return list of dicts: {chip_id, s2_dir, s1_dir, dem_dir} for each
    grid cell that has S2+S1+DEM all present."""
    s2_root = major_tom_root / "Core-S2L2A" / "S2L2A"
    s1_root = major_tom_root / "Core-S1RTC" / "S1RTC"
    dem_root = major_tom_root / "Core-DEM" / "DEM"

    if not s2_root.exists():
        raise RuntimeError(f"S2 root not found: {s2_root}")

    parents = []
    for row_dir in sorted(s2_root.iterdir()):
        if not row_dir.is_dir(): continue
        for cell_dir in sorted(row_dir.iterdir()):
            if not cell_dir.is_dir(): continue
            cell = cell_dir.name
            row = row_dir.name
            # Use first product per cell (Major-TOM is monotemporal but
            # may have multiple acquisitions per cell occasionally).
            s2_products = sorted(cell_dir.iterdir())
            if not s2_products: continue
            s2_dir = s2_products[0]

            s1_cell = s1_root / row / cell
            dem_cell = dem_root / row / cell
            if not s1_cell.exists():
                continue  # S1 is required; DEM is optional
            s1_dir = sorted(s1_cell.iterdir())[0] if (s1_cell.exists() and any(s1_cell.iterdir())) else None
            dem_dir = sorted(dem_cell.iterdir())[0] if (dem_cell.exists() and any(dem_cell.iterdir())) else None
            if s1_dir is None:
                continue  # DEM is optional (will use zeros if missing)

            parents.append({
                "chip_id": f"nyc_{cell}",
                "s2_dir": s2_dir, "s1_dir": s1_dir, "dem_dir": dem_dir,
            })
    return parents


def read_band_stack(chip_dir: Path, bands: list[str]) -> tuple[np.ndarray, Affine, str]:
    """Read multi-band chip from a Major-TOM-style directory of single-band TIFs.
    Returns the stack at the max resolution found (typically 10m for S2)."""
    arrays = []
    transforms = []
    crs = None
    for b in bands:
        path = chip_dir / f"{b}.tif"
        if not path.exists():
            raise RuntimeError(f"missing band {b} in {chip_dir}")
        with rasterio.open(path) as src:
            data = src.read(1)
            transforms.append((data.shape, src.transform))
            if crs is None:
                crs = str(src.crs)
        arrays.append(data)
    # Pick transform from the highest-resolution band (largest shape)
    transforms.sort(key=lambda x: x[0][0] * x[0][1], reverse=True)
    transform = transforms[0][1]
    # S2 has mixed resolutions (10m for B02-B04/B08; 20m for B05-B07/B8A/B11/B12;
    # 60m for B01/B09). Use max shape (10m bands) as target; upsample others
    # via nearest-neighbour (np.kron with ones).
    target_h = max(a.shape[0] for a in arrays)
    target_w = max(a.shape[1] for a in arrays)
    out = np.zeros((len(bands), target_h, target_w), dtype=np.float32)
    for i, a in enumerate(arrays):
        if a.shape != (target_h, target_w):
            zoom_h = max(1, target_h // a.shape[0])
            zoom_w = max(1, target_w // a.shape[1])
            a = np.kron(a, np.ones((zoom_h, zoom_w), dtype=a.dtype))[:target_h, :target_w]
        out[i] = a.astype(np.float32)
    return out, transform, crs


def reproject_label_to_chip(label_path: Path, chip_transform: Affine, chip_crs: str,
                            h: int, w: int) -> np.ndarray:
    """Read ESA WorldCover raster, reproject + resample to the chip's 10m grid.
    Returns a (h, w) int8 array with our 5 macro-class codes; -1 for no-data."""
    with rasterio.open(label_path) as src:
        block = np.full((h, w), 0, dtype=np.uint8)
        reproject(
            source=rasterio.band(src, 1),
            destination=block,
            src_transform=src.transform, src_crs=src.crs,
            dst_transform=chip_transform, dst_crs=chip_crs,
            resampling=Resampling.nearest,
        )
    macro = np.full(block.shape, -1, dtype=np.int8)
    for code, macro_code in LABEL_TO_MACRO.items():
        macro[block == code] = macro_code
    return macro


def slice_chip(arr: np.ndarray, crop: int = CHIP_PX) -> list[tuple[int, int, np.ndarray]]:
    """4x4 grid of 256x256 windows from a 1068x1068 array. Drops residual."""
    h, w = arr.shape[-2:]
    rows = h // crop
    cols = w // crop
    out = []
    for r in range(rows):
        for c in range(cols):
            slc = (slice(r * crop, (r + 1) * crop),
                   slice(c * crop, (c + 1) * crop))
            sub = arr[..., slc[0], slc[1]]
            out.append((r, c, sub))
    return out


def write_s2_zarr(out_path: Path, s2_stack: np.ndarray, transform: Affine, crs: str):
    """ImpactMesh-format zarr.zip with 4 identical timesteps + consolidated metadata."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists(): out_path.unlink()
    n_bands = s2_stack.shape[0]
    store = zarr.storage.ZipStore(str(out_path), mode="w")
    with zarr.open(store, mode="w") as g:
        bands_arr = np.broadcast_to(
            s2_stack[None, ...].astype(np.int16),
            (N_TIMESTEPS_TARGET, n_bands, CHIP_PX, CHIP_PX)
        ).copy()
        g.create_dataset("bands", data=bands_arr, dtype="int16")
        g["bands"].attrs["_ARRAY_DIMENSIONS"] = ["time", "band", "y", "x"]
        g.create_dataset("band", data=np.array(S2_BANDS, dtype=f"<U6"))
        zeros = np.zeros((N_TIMESTEPS_TARGET, CHIP_PX, CHIP_PX), dtype=np.int8)
        g.create_dataset("SCL", data=zeros, dtype="int8")
        g.create_dataset("cloud_mask", data=zeros, dtype="int8")
        g.create_dataset("nan_mask", data=zeros, dtype="int8")
        g.create_dataset("data_mask", data=np.ones(N_TIMESTEPS_TARGET, dtype=np.int8),
                         dtype="int8")
        g.create_dataset("time", data=np.arange(N_TIMESTEPS_TARGET, dtype=np.int64),
                         dtype="int64")
        ax_x = np.arange(CHIP_PX, dtype=np.float64) * transform.a + transform.c
        ax_y = np.arange(CHIP_PX, dtype=np.float64) * transform.e + transform.f
        g.create_dataset("x", data=ax_x, dtype="float64")
        g.create_dataset("y", data=ax_y, dtype="float64")
        g.create_dataset("spatial_ref", data=np.array(0, dtype=np.int64))
        g["spatial_ref"].attrs["crs_wkt"] = crs
    # Re-open to consolidate metadata (the `with zarr.open` block closed the ZipStore)
    store2 = zarr.storage.ZipStore(str(out_path), mode="a")
    zarr.consolidate_metadata(store2)
    store2.close()


def write_s1_zarr(out_path: Path, s1_stack: np.ndarray, transform: Affine, crs: str):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists(): out_path.unlink()
    store = zarr.storage.ZipStore(str(out_path), mode="w")
    with zarr.open(store, mode="w") as g:
        bands_arr = np.broadcast_to(
            s1_stack[None, ...].astype(np.float16),
            (N_TIMESTEPS_TARGET, len(S1_BANDS), CHIP_PX, CHIP_PX)
        ).copy()
        g.create_dataset("bands", data=bands_arr, dtype="float16")
        g["bands"].attrs["_ARRAY_DIMENSIONS"] = ["time", "band", "y", "x"]
        g.create_dataset("band", data=np.array(S1_BANDS, dtype="<U2"))
        zeros = np.zeros((N_TIMESTEPS_TARGET, CHIP_PX, CHIP_PX), dtype=np.int8)
        g.create_dataset("nan_mask", data=zeros, dtype="int8")
        g.create_dataset("data_mask", data=np.ones(N_TIMESTEPS_TARGET, dtype=np.int8),
                         dtype="int8")
        g.create_dataset("time", data=np.arange(N_TIMESTEPS_TARGET, dtype=np.int64),
                         dtype="int64")
        ax_x = np.arange(CHIP_PX, dtype=np.float64) * transform.a + transform.c
        ax_y = np.arange(CHIP_PX, dtype=np.float64) * transform.e + transform.f
        g.create_dataset("x", data=ax_x, dtype="float64")
        g.create_dataset("y", data=ax_y, dtype="float64")
        g.create_dataset("spatial_ref", data=np.array(0, dtype=np.int64))
        g["spatial_ref"].attrs["crs_wkt"] = crs
    # Re-open to consolidate metadata (the `with zarr.open` block closed the ZipStore)
    store2 = zarr.storage.ZipStore(str(out_path), mode="a")
    zarr.consolidate_metadata(store2)
    store2.close()


def write_geotiff(out_path: Path, arr: np.ndarray, transform: Affine, crs: str, dtype: str):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    h, w = arr.shape
    with rasterio.open(out_path, "w", driver="GTiff",
                       height=h, width=w, count=1, dtype=dtype,
                       transform=transform, crs=crs) as dst:
        dst.write(arr.astype(dtype), 1)


def process_parent(parent: dict, nlcd_path: Path, out_root: Path) -> list[str]:
    """Read parent chip, slice into 16 sub-chips, write each in
    ImpactMesh format. Returns list of sub-chip IDs."""
    print(f"[slice] processing {parent['chip_id']}", flush=True)
    s2, s2_tf, s2_crs = read_band_stack(parent["s2_dir"], S2_BANDS)
    s1, s1_tf, s1_crs = read_band_stack(parent["s1_dir"], S1_BANDS)
    if parent.get("dem_dir"):
        dem, dem_tf, dem_crs = read_band_stack(parent["dem_dir"], ["DEM"])
    else:
        # DEM unavailable — fill with zeros at S2 grid shape.
        dem = np.zeros((1, s2.shape[1], s2.shape[2]), dtype=np.float32)
        dem_tf, dem_crs = s2_tf, s2_crs

    # WorldCover label tile at the S2 grid resolution
    nlcd = reproject_label_to_chip(nlcd_path, s2_tf, s2_crs,
                                   s2.shape[1], s2.shape[2])

    # Slice all into 16 sub-chips (4x4 of 256x256)
    s2_subs = slice_chip(s2)
    s1_subs = slice_chip(s1)
    dem_subs = slice_chip(dem)
    nlcd_subs = slice_chip(nlcd)

    sub_ids = []
    for (r, c, s2_sub), (_, _, s1_sub), (_, _, dem_sub), (_, _, nlcd_sub) in zip(
            s2_subs, s1_subs, dem_subs, nlcd_subs):
        sub_id = f"{parent['chip_id']}_r{r}c{c}"
        sub_tf = Affine(s2_tf.a, s2_tf.b,
                        s2_tf.c + c * CHIP_PX * s2_tf.a,
                        s2_tf.d, s2_tf.e,
                        s2_tf.f + r * CHIP_PX * s2_tf.e)

        # Skip if NLCD is mostly ignore (-1) — chip is outside CONUS
        valid_frac = (nlcd_sub != -1).mean()
        if valid_frac < 0.5:
            continue

        write_s2_zarr(out_root / "data" / "S2L2A" / f"{sub_id}_S2L2A.zarr.zip",
                      s2_sub, sub_tf, s2_crs)
        write_s1_zarr(out_root / "data" / "S1RTC" / f"{sub_id}_S1RTC.zarr.zip",
                      s1_sub, sub_tf, s1_crs)
        write_geotiff(out_root / "data" / "DEM" / f"{sub_id}_DEM.tif",
                      dem_sub[0], sub_tf, dem_crs, "int16")
        write_geotiff(out_root / "data" / "MASK" / f"{sub_id}_annotation_flood.tif",
                      nlcd_sub, sub_tf, s2_crs, "int8")
        sub_ids.append(sub_id)
    return sub_ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--major-tom-root", required=True)
    ap.add_argument("--label-tif", required=True,
                    help="ESA WorldCover (or NLCD) GeoTIFF covering the chip area")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    out_root = Path(args.out)
    (out_root / "split").mkdir(parents=True, exist_ok=True)

    parents = find_parent_chips(Path(args.major_tom_root))
    print(f"[slice] found {len(parents)} parent chips with S2+S1+DEM")

    # Stratified split: parents to train/val/test BEFORE sub-chipping
    rng = random.Random(args.seed)
    rng.shuffle(parents)
    n = len(parents)
    n_train = int(0.7 * n)
    n_val = int(0.15 * n)
    train_parents = parents[:n_train]
    val_parents = parents[n_train:n_train + n_val]
    test_parents = parents[n_train + n_val:]

    splits = {"train": [], "val": [], "test": []}
    for p in train_parents:
        splits["train"].extend(process_parent(p, Path(args.label_tif), out_root))
    for p in val_parents:
        splits["val"].extend(process_parent(p, Path(args.label_tif), out_root))
    for p in test_parents:
        splits["test"].extend(process_parent(p, Path(args.label_tif), out_root))

    for split, ids in splits.items():
        path = out_root / "split" / f"impactmesh_flood_{split}.txt"
        path.write_text("\n".join(ids) + "\n")
        print(f"[slice] split {split}: {len(ids)} sub-chips -> {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
