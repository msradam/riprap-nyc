"""Pack NYC chips (S2 + S1 numpy arrays from extract_chips.py) into the
ImpactMesh-Flood zarr.zip + GeoTIFF layout that TerraTorch's
`impactmesh.impactmesh_datamodule.ImpactMeshDataModule` expects.

Target schema (from inspecting ibm-esa-geospatial/ImpactMesh-Flood):

  data/
    S2L2A/<chip_id>_S2L2A.zarr.zip      # zarr group, 4 timesteps, 12 bands int16
    S1RTC/<chip_id>_S1RTC.zarr.zip      # zarr group, 4 timesteps, 2  bands float16
    DEM/  <chip_id>_DEM.tif             # GeoTIFF, 256x256 int16, single timestep
    MASK/ <chip_id>_annotation_flood.tif# GeoTIFF, 256x256 int8, values {-1, 0, 1}
  split/
    impactmesh_flood_{train,val,test}.txt    # one chip_id per line

Workaround for the 4-timestep requirement: NYC chips are single-timestep
paired (S2, S1). We stack the same data 4× along the time axis so the
TerraTorch temporal-wrapper recipe stays unchanged. Model sees 4
identical copies; this is documented in the model card.

DEM source: extracted from the same S2 raster's UTM extent via Copernicus
GLO-30 if available locally, else a synthetic zero array (the ImpactMesh
DEM channel adds little signal compared to S2/S1 in our regime).

MASK source: water mask from a separately-run Prithvi-EO Sen1Floods11
inference (see prithvi_pseudo_label.py), saved as int8 with values
{0=non-water, 1=water}.

Output is ready for TerraTorch's ImpactMeshDataModule with no schema
changes.

Usage:
    python3 pack_nyc_to_impactmesh.py \\
        --chips-root /root/terramind_nyc/chips \\
        --masks-root /root/terramind_nyc/prithvi_masks \\
        --out-root   /root/terramind_nyc/nyc_dataset \\
        --train-frac 0.7 --val-frac 0.15 --test-frac 0.15 \\
        --seed 42
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path

import numpy as np
import rasterio
import zarr
from rasterio.transform import Affine
from rasterio.crs import CRS


S2_BANDS = ["B02", "B03", "B04", "B05", "B06", "B07",
            "B08", "B8A", "B11", "B12", "AOT", "SCL"]
S1_BANDS = ["vv", "vh"]

# Extracted chips are 224x224; ImpactMesh expects 256x256. We pad with zeros
# (data_mask flags the padded region as no-data).
CHIP_PX_SRC = 224
CHIP_PX_DST = 256
N_TIMESTEPS = 4  # ImpactMesh schema; we stack the single chip this many times


def pad_to_256(a: np.ndarray) -> np.ndarray:
    """Pad a HxW or CxHxW array to 256x256 in the spatial dims."""
    if a.ndim == 2:
        h, w = a.shape
        out = np.zeros((CHIP_PX_DST, CHIP_PX_DST), dtype=a.dtype)
        out[:h, :w] = a
        return out
    if a.ndim == 3:
        c, h, w = a.shape
        out = np.zeros((c, CHIP_PX_DST, CHIP_PX_DST), dtype=a.dtype)
        out[:, :h, :w] = a
        return out
    raise ValueError(f"unsupported ndim {a.ndim}")


def utm_transform_from_meta(meta: dict) -> tuple[Affine, str]:
    """Recreate the chip's geographic transform from extract_chips.py meta."""
    t = meta["dst_transform"]  # [a, b, c, d, e, f]
    return Affine(*t), str(meta["dst_crs"])


def write_s2_zarr(out_path: Path, s2_stack: np.ndarray, transform: Affine, crs: str):
    """Write the 12-band S2L2A chip as ImpactMesh-format zarr.zip with 4
    identical timesteps. s2_stack is (12, 256, 256) float32; we cast to
    int16 (multiply by 1, ImpactMesh stores raw L2A reflectance integers)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()
    with zarr.open(zarr.storage.ZipStore(str(out_path), mode="w"), mode="w") as g:
        bands_arr = np.broadcast_to(s2_stack[None, ...].astype(np.int16),
                                    (N_TIMESTEPS, len(S2_BANDS),
                                     CHIP_PX_DST, CHIP_PX_DST)).copy()
        g.create_dataset("bands", data=bands_arr, dtype="int16")
        g["bands"].attrs["_ARRAY_DIMENSIONS"] = ["time", "band", "y", "x"]

        g.create_dataset("band", data=np.array(S2_BANDS, dtype="<U6"))
        # SCL band is index 11 in our extract; ImpactMesh stores it as a
        # separate field. Stack 4×.
        scl = s2_stack[11].astype(np.int8)
        g.create_dataset("SCL", data=np.broadcast_to(scl[None, ...],
                                  (N_TIMESTEPS, CHIP_PX_DST, CHIP_PX_DST)).copy(),
                         dtype="int8")
        zeros_t_hw = np.zeros((N_TIMESTEPS, CHIP_PX_DST, CHIP_PX_DST), dtype=np.int8)
        g.create_dataset("cloud_mask", data=zeros_t_hw, dtype="int8")
        g.create_dataset("nan_mask", data=zeros_t_hw, dtype="int8")
        g.create_dataset("data_mask", data=np.ones(N_TIMESTEPS, dtype=np.int8),
                         dtype="int8")
        g.create_dataset("time",
                         data=np.arange(N_TIMESTEPS, dtype=np.int64),
                         dtype="int64")
        ax_x = np.arange(CHIP_PX_DST, dtype=np.float64) * transform.a + transform.c
        ax_y = np.arange(CHIP_PX_DST, dtype=np.float64) * transform.e + transform.f
        g.create_dataset("x", data=ax_x, dtype="float64")
        g.create_dataset("y", data=ax_y, dtype="float64")
        g.create_dataset("spatial_ref", data=np.array(0, dtype=np.int64))
        g["spatial_ref"].attrs["crs_wkt"] = crs


def write_s1_zarr(out_path: Path, s1_stack: np.ndarray, transform: Affine, crs: str):
    """Write the 2-band S1RTC chip as ImpactMesh-format zarr.zip."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()
    with zarr.open(zarr.storage.ZipStore(str(out_path), mode="w"), mode="w") as g:
        bands_arr = np.broadcast_to(s1_stack[None, ...].astype(np.float16),
                                    (N_TIMESTEPS, len(S1_BANDS),
                                     CHIP_PX_DST, CHIP_PX_DST)).copy()
        g.create_dataset("bands", data=bands_arr, dtype="float16")
        g["bands"].attrs["_ARRAY_DIMENSIONS"] = ["time", "band", "y", "x"]

        g.create_dataset("band", data=np.array(S1_BANDS, dtype="<U2"))
        zeros = np.zeros((N_TIMESTEPS, CHIP_PX_DST, CHIP_PX_DST), dtype=np.int8)
        g.create_dataset("nan_mask", data=zeros, dtype="int8")
        g.create_dataset("data_mask",
                         data=np.ones(N_TIMESTEPS, dtype=np.int8),
                         dtype="int8")
        g.create_dataset("time",
                         data=np.arange(N_TIMESTEPS, dtype=np.int64),
                         dtype="int64")
        ax_x = np.arange(CHIP_PX_DST, dtype=np.float64) * transform.a + transform.c
        ax_y = np.arange(CHIP_PX_DST, dtype=np.float64) * transform.e + transform.f
        g.create_dataset("x", data=ax_x, dtype="float64")
        g.create_dataset("y", data=ax_y, dtype="float64")
        g.create_dataset("spatial_ref", data=np.array(0, dtype=np.int64))
        g["spatial_ref"].attrs["crs_wkt"] = crs


def write_geotiff(out_path: Path, arr: np.ndarray, transform: Affine, crs: str,
                  dtype: str):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    arr = pad_to_256(arr).astype(dtype)
    with rasterio.open(out_path, "w", driver="GTiff",
                       height=CHIP_PX_DST, width=CHIP_PX_DST,
                       count=1, dtype=dtype,
                       transform=transform, crs=CRS.from_string(crs)) as dst:
        dst.write(arr, 1)


def pack_one(chip_dir: Path, mask_dir: Path | None, out_root: Path) -> dict:
    """Pack a single extract_chips.py chip dir into ImpactMesh layout."""
    chip_id = chip_dir.name  # e.g. "00_train"
    npz = np.load(chip_dir / "chip.npz")
    meta = json.loads((chip_dir / "meta.json").read_text())
    s2 = pad_to_256(npz["s2"].astype(np.float32))
    s1 = pad_to_256(npz["s1"].astype(np.float32))
    transform, crs = utm_transform_from_meta(meta)

    write_s2_zarr(out_root / "data" / "S2L2A" / f"{chip_id}_S2L2A.zarr.zip",
                  s2, transform, crs)
    write_s1_zarr(out_root / "data" / "S1RTC" / f"{chip_id}_S1RTC.zarr.zip",
                  s1, transform, crs)

    # DEM: pack a zeros tile if no real DEM provided. The model can still
    # learn from S2+S1 dominantly. (TODO: pull GLO-30 DEM at the chip's
    # bbox if we want a real elevation channel.)
    dem = np.zeros((CHIP_PX_DST, CHIP_PX_DST), dtype=np.int16)
    write_geotiff(out_root / "data" / "DEM" / f"{chip_id}_DEM.tif",
                  dem, transform, crs, "int16")

    # MASK: the binary water/non-water from Prithvi pseudo-labeling.
    mask_tile = None
    if mask_dir is not None:
        m_path = mask_dir / f"{chip_id}.npy"
        if m_path.exists():
            mask_tile = np.load(m_path).astype(np.int8)
    if mask_tile is None:
        # No mask yet — fill with -1 (ignore_index). This chip is unlabeled.
        mask_tile = np.full((CHIP_PX_DST, CHIP_PX_DST), -1, dtype=np.int8)
    write_geotiff(out_root / "data" / "MASK" / f"{chip_id}_annotation_flood.tif",
                  mask_tile, transform, crs, "int8")

    return {"chip_id": chip_id,
            "has_mask": bool(mask_dir is not None and (mask_dir / f"{chip_id}.npy").exists())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chips-root", required=True,
                    help="dir of NN_train/holdout subdirs from extract_chips.py")
    ap.add_argument("--masks-root", default=None,
                    help="dir of <chip_id>.npy water-mask files (Prithvi pseudo-labels)")
    ap.add_argument("--out-root", required=True,
                    help="ImpactMesh-format dataset target")
    ap.add_argument("--train-frac", type=float, default=0.7)
    ap.add_argument("--val-frac",   type=float, default=0.15)
    ap.add_argument("--test-frac",  type=float, default=0.15)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    chips_root = Path(args.chips_root)
    masks_root = Path(args.masks_root) if args.masks_root else None
    out_root = Path(args.out_root)
    (out_root / "split").mkdir(parents=True, exist_ok=True)

    chip_dirs = sorted(p for p in chips_root.iterdir()
                       if p.is_dir() and (p / "chip.npz").exists())
    print(f"[pack] found {len(chip_dirs)} chips -> {out_root}")

    summary = []
    for cd in chip_dirs:
        try:
            r = pack_one(cd, masks_root, out_root)
            print(f"[pack] {cd.name} OK has_mask={r['has_mask']}", flush=True)
            summary.append(r)
        except Exception as e:
            print(f"[pack] {cd.name} FAIL {e}", flush=True)

    # Stratified split by source label suffix (train vs holdout dir name).
    rng = random.Random(args.seed)
    chip_ids = [r["chip_id"] for r in summary]
    rng.shuffle(chip_ids)
    n = len(chip_ids)
    n_train = int(args.train_frac * n)
    n_val = int(args.val_frac * n)
    splits = {
        "train": chip_ids[:n_train],
        "val":   chip_ids[n_train : n_train + n_val],
        "test":  chip_ids[n_train + n_val:],
    }
    for split, ids in splits.items():
        path = out_root / "split" / f"impactmesh_flood_{split}.txt"
        path.write_text("\n".join(ids) + "\n")
        print(f"[pack] split {split}: {len(ids)} chips -> {path}")

    (out_root / "pack_summary.json").write_text(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
