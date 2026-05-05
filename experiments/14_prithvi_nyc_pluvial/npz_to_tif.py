"""Post-process the Prithvi build_dataset.py output: convert each NPZ to a
6-band GeoTIFF so terratorch's standard GenericNonGeoSegmentationDataModule
can load them. NPZ → multi-band GeoTIFF using the matching MASK file's
geo-reference (since both share the same chip grid).
"""
import argparse, sys
from pathlib import Path
import numpy as np
import rasterio


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="prithvi_nyc dataset root")
    args = ap.parse_args()

    root = Path(args.root)
    npz_dir = root / "data" / "S2L2A"
    mask_dir = root / "data" / "MASK"
    out_dir = root / "data" / "S2L2A_tif"
    out_dir.mkdir(parents=True, exist_ok=True)

    n_ok = 0
    n_skip = 0
    for npz_path in sorted(npz_dir.glob("*.npz")):
        chip_id = npz_path.stem
        mask_path = mask_dir / f"{chip_id}_annotation_flood.tif"
        if not mask_path.exists():
            n_skip += 1
            continue
        with rasterio.open(mask_path) as src:
            transform, crs = src.transform, src.crs
            H, W = src.shape
        bands = np.load(npz_path)["bands"].astype(np.float32)
        if bands.shape != (6, H, W):
            print(f"shape mismatch {chip_id}: {bands.shape} vs ({6}, {H}, {W})")
            n_skip += 1
            continue
        out_path = out_dir / f"{chip_id}.tif"
        with rasterio.open(out_path, "w", driver="GTiff",
                           height=H, width=W, count=6, dtype="float32",
                           transform=transform, crs=crs) as dst:
            dst.write(bands)
        n_ok += 1

    print(f"converted {n_ok}, skipped {n_skip} -> {out_dir}")


if __name__ == "__main__":
    sys.exit(main())
