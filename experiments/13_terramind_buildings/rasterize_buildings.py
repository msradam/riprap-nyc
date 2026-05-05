"""Rasterize NYC DOITT Building Footprints onto the same chip grids used by
Phase 2 (Major-TOM NYC parents → 256x256 sub-chips). Produces a binary
GeoTIFF per sub-chip (1 = inside building polygon, 0 = not), drop-in
replacement for the WorldCover MASK files in the ImpactMesh-format dataset.

Source data: NYC DOITT Building Footprints (`https://data.cityofnewyork.us/...`).
Public domain. Vector polygons of every building in NYC.

Output layout (overwrites the LULC labels with binary building labels):

    /root/terramind_nyc/nyc_buildings/data/MASK/<chip_id>_annotation_flood.tif
    /root/terramind_nyc/nyc_buildings/split/impactmesh_flood_{train,val,test}.txt

The S2L2A and S1RTC zarr.zip files are reused via symlink/copy from the
Phase 2 dataset to avoid re-packaging them.

Usage on droplet:
    python3 rasterize_buildings.py \\
        --major-tom-root /root/terramind_nyc/major_tom/data \\
        --footprints-url 'https://data.cityofnewyork.us/api/geospatial/nqwf-w8eh?accessType=DOWNLOAD&method=export&format=GeoJSON' \\
        --phase2-dataset /root/terramind_nyc/nyc_flood \\
        --out /root/terramind_nyc/nyc_buildings
"""
from __future__ import annotations

import argparse, json, os, shutil, sys, urllib.request
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.warp import transform_geom, transform_bounds
from rasterio.transform import Affine
import geopandas as gpd

CHIP_PX = 256


def fetch_footprints(url: str, dst: Path) -> Path:
    """Download NYC DOITT Building Footprints GeoJSON if not cached."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and dst.stat().st_size > 1_000_000:
        print(f"[bld] cached: {dst} ({dst.stat().st_size/1e6:.1f} MB)", flush=True)
        return dst
    print(f"[bld] downloading from {url[:80]}...", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "TerraMind-NYC/1.0"})
    with urllib.request.urlopen(req, timeout=600) as r, open(dst, "wb") as f:
        shutil.copyfileobj(r, f)
    print(f"[bld] downloaded {dst.stat().st_size/1e6:.1f} MB", flush=True)
    return dst


def find_parents(major_tom_root: Path):
    """Mirror find_parent_chips from slice_and_label_nyc; same 22 NYC parents."""
    s2_root = major_tom_root / "Core-S2L2A" / "S2L2A"
    s1_root = major_tom_root / "Core-S1RTC" / "S1RTC"
    parents = []
    for row_dir in sorted(s2_root.iterdir()):
        if not row_dir.is_dir(): continue
        for cell_dir in sorted(row_dir.iterdir()):
            if not cell_dir.is_dir(): continue
            s2_products = sorted(cell_dir.iterdir())
            if not s2_products: continue
            s2_dir = s2_products[0]
            s1_cell = s1_root / row_dir.name / cell_dir.name
            if not s1_cell.exists(): continue
            s1_products = sorted(s1_cell.iterdir())
            if not s1_products: continue
            parents.append({
                "chip_id": f"nyc_{cell_dir.name}",
                "s2_dir": s2_dir,
                "s1_dir": s1_products[0],
            })
    return parents


def rasterize_for_parent(parent, footprints_gdf, out_root: Path,
                          phase2_dataset: Path):
    """For one parent chip, slice into 16 sub-chips and write a binary
    building-mask tif per sub-chip. S2/S1 zarr.zip files are reused from
    the Phase 2 dataset via copy."""
    # Read S2 anchor band to get transform + CRS + shape
    with rasterio.open(parent["s2_dir"] / "B02.tif") as src:
        H, W = src.shape
        chip_transform = src.transform
        chip_crs = src.crs

    # Reproject footprints into chip CRS once per parent (cheap vs per-sub-chip)
    if footprints_gdf.crs != chip_crs:
        local = footprints_gdf.to_crs(chip_crs)
    else:
        local = footprints_gdf

    # Filter to footprints inside the parent's bbox first (massive speedup)
    parent_bbox = rasterio.transform.array_bounds(H, W, chip_transform)
    parent_box = (parent_bbox[0], parent_bbox[1], parent_bbox[2], parent_bbox[3])
    local = local.cx[parent_box[0]:parent_box[2], parent_box[1]:parent_box[3]]
    if len(local) == 0:
        print(f"[bld] {parent['chip_id']}: 0 footprints inside parent bbox", flush=True)
        return []

    # Rasterize all footprints onto the parent grid in one shot
    print(f"[bld] {parent['chip_id']}: rasterizing {len(local)} footprints "
          f"onto {H}x{W} parent grid", flush=True)
    parent_mask = rasterize(
        [(g, 1) for g in local.geometry],
        out_shape=(H, W),
        transform=chip_transform,
        fill=0,
        all_touched=False,
        dtype=np.uint8,
    )

    # Slice into 16 sub-chips; reuse Phase 2's S2/S1 zarr.zip + DEM files
    sub_ids = []
    rows = H // CHIP_PX
    cols = W // CHIP_PX
    for r in range(rows):
        for c in range(cols):
            sub_id = f"{parent['chip_id']}_r{r}c{c}"
            # Check the Phase 2 dataset has this sub-chip's S2/S1/DEM
            phase2_s2 = phase2_dataset / "data" / "S2L2A" / f"{sub_id}_S2L2A.zarr.zip"
            phase2_s1 = phase2_dataset / "data" / "S1RTC" / f"{sub_id}_S1RTC.zarr.zip"
            phase2_dem = phase2_dataset / "data" / "DEM" / f"{sub_id}_DEM.tif"
            if not (phase2_s2.exists() and phase2_s1.exists() and phase2_dem.exists()):
                continue  # Phase 2 dropped this sub-chip (e.g. low NLCD coverage)

            # Sub-chip transform + window of the building mask
            sub_tf = Affine(chip_transform.a, chip_transform.b,
                            chip_transform.c + c * CHIP_PX * chip_transform.a,
                            chip_transform.d, chip_transform.e,
                            chip_transform.f + r * CHIP_PX * chip_transform.e)
            sub_mask = parent_mask[r*CHIP_PX:(r+1)*CHIP_PX,
                                   c*CHIP_PX:(c+1)*CHIP_PX]

            mask_dir = out_root / "data" / "MASK"
            mask_dir.mkdir(parents=True, exist_ok=True)
            mask_path = mask_dir / f"{sub_id}_annotation_flood.tif"
            with rasterio.open(mask_path, "w", driver="GTiff",
                               height=CHIP_PX, width=CHIP_PX, count=1,
                               dtype="int8", transform=sub_tf, crs=chip_crs) as dst:
                dst.write(sub_mask.astype("int8"), 1)

            # Symlink S2/S1/DEM from Phase 2 dataset to avoid duplication
            for sub, src_path in [
                ("S2L2A", phase2_s2),
                ("S1RTC", phase2_s1),
                ("DEM",   phase2_dem),
            ]:
                target_dir = out_root / "data" / sub
                target_dir.mkdir(parents=True, exist_ok=True)
                target = target_dir / src_path.name
                if not target.exists():
                    try:
                        os.symlink(src_path, target)
                    except OSError:
                        shutil.copy2(src_path, target)

            sub_ids.append(sub_id)

    return sub_ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--major-tom-root", required=True)
    ap.add_argument("--footprints-url",
                    default="https://data.cityofnewyork.us/api/geospatial/"
                            "5zhs-2jue?accessType=DOWNLOAD&method=export"
                            "&format=GeoJSON")
    ap.add_argument("--phase2-dataset", required=True,
                    help="Phase 2 packaged dataset (provides S2/S1/DEM)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    out_root = Path(args.out)
    (out_root / "split").mkdir(parents=True, exist_ok=True)

    fp_path = fetch_footprints(args.footprints_url,
                                out_root / "footprints" / "nyc_footprints.geojson")
    print(f"[bld] reading footprints...", flush=True)
    fp_gdf = gpd.read_file(fp_path)
    print(f"[bld] {len(fp_gdf):,} footprints, CRS={fp_gdf.crs}", flush=True)

    parents = find_parents(Path(args.major_tom_root))
    print(f"[bld] {len(parents)} parent chips", flush=True)

    import random
    rng = random.Random(args.seed)
    rng.shuffle(parents)
    n = len(parents)
    splits = {
        "train": parents[:int(0.7 * n)],
        "val":   parents[int(0.7 * n):int(0.85 * n)],
        "test":  parents[int(0.85 * n):],
    }

    summary = {}
    for split, plist in splits.items():
        ids = []
        for p in plist:
            ids.extend(rasterize_for_parent(p, fp_gdf, out_root,
                                             Path(args.phase2_dataset)))
        path = out_root / "split" / f"impactmesh_flood_{split}.txt"
        path.write_text("\n".join(ids) + "\n")
        summary[split] = len(ids)
        print(f"[bld] split {split}: {len(ids)} sub-chips", flush=True)

    print(f"\n[bld] === Summary ===")
    print(f"[bld] total sub-chips: {sum(summary.values())}")
    for k, v in summary.items():
        print(f"[bld]   {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
