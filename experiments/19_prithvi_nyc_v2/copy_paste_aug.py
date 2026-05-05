"""Copy-paste augmentation for Prithvi NYC pluvial dataset.

Takes the existing Phase 14 v1 dataset (166 Ida positive chips at
polygon centroids + 22 clear-sky negatives from Major-TOM) and
generates ~600 synthetic positive chips by pasting real Ida flood
polygons onto clear-sky NYC backgrounds at random positions.

Per Ghiasi et al. (CVPR 2021) "Simple Copy-Paste". Validated to be the
highest-ROI augmentation for sparse-positive segmentation across many
benchmarks. We use feathered alpha blending on the polygon mask edge
to avoid sharp spectral seams.

Usage:
    python3 copy_paste_aug.py \
        --src /root/terramind_nyc/prithvi_nyc/data \
        --out /root/terramind_nyc/prithvi_nyc_v2/data \
        --multiplier 5 \
        --paste-min 1 --paste-max 4
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import Affine
from scipy.ndimage import binary_dilation, gaussian_filter


def feather_mask(mask: np.ndarray, sigma: float = 2.0) -> np.ndarray:
    """Soft 0..1 alpha matte from a binary mask, feathered at edges."""
    return gaussian_filter(mask.astype(np.float32), sigma=sigma)


def find_polygon_bbox(mask: np.ndarray, pad: int = 4) -> tuple | None:
    """Tight bounding box around the positive pixels, with padding."""
    ys, xs = np.where(mask > 0)
    if len(ys) == 0:
        return None
    H, W = mask.shape
    y0, y1 = max(0, ys.min() - pad), min(H, ys.max() + pad + 1)
    x0, x1 = max(0, xs.min() - pad), min(W, xs.max() + pad + 1)
    return y0, y1, x0, x1


def paste(bg_chip: np.ndarray, bg_mask: np.ndarray,
          fg_chip: np.ndarray, fg_mask: np.ndarray,
          rng: random.Random) -> tuple[np.ndarray, np.ndarray]:
    """Paste a polygon crop from fg onto bg at a random position.

    bg_chip:   [C, H, W] background imagery
    bg_mask:   [H, W] background mask (will be OR-merged)
    fg_chip:   [C, H, W] source imagery containing flood polygon
    fg_mask:   [H, W] source mask

    Returns (out_chip, out_mask) of same shape as bg_*.
    """
    bbox = find_polygon_bbox(fg_mask, pad=4)
    if bbox is None:
        return bg_chip.copy(), bg_mask.copy()
    y0, y1, x0, x1 = bbox
    crop_chip = fg_chip[:, y0:y1, x0:x1]
    crop_mask = fg_mask[y0:y1, x0:x1]

    # Random rotation by k × 90° + flips for spatial diversity
    k = rng.randint(0, 3)
    crop_chip = np.rot90(crop_chip, k=k, axes=(1, 2)).copy()
    crop_mask = np.rot90(crop_mask, k=k).copy()
    if rng.random() < 0.5:
        crop_chip = np.flip(crop_chip, axis=2).copy()
        crop_mask = np.flip(crop_mask, axis=1).copy()
    if rng.random() < 0.5:
        crop_chip = np.flip(crop_chip, axis=1).copy()
        crop_mask = np.flip(crop_mask, axis=0).copy()

    ch, H, W = bg_chip.shape
    fh, fw = crop_mask.shape
    if fh >= H or fw >= W:
        # Polygon larger than chip — center-crop the polygon to fit
        sh = max(0, (fh - H + 1) // 2)
        sw = max(0, (fw - W + 1) // 2)
        crop_chip = crop_chip[:, sh:sh + min(fh, H), sw:sw + min(fw, W)]
        crop_mask = crop_mask[sh:sh + min(fh, H), sw:sw + min(fw, W)]
        fh, fw = crop_mask.shape

    # Random paste position
    py = rng.randint(0, H - fh)
    px = rng.randint(0, W - fw)

    out_chip = bg_chip.copy().astype(np.float32)
    out_mask = bg_mask.copy().astype(np.uint8)

    alpha = feather_mask(crop_mask, sigma=2.0)[None, :, :]  # [1, fh, fw]
    region = out_chip[:, py:py + fh, px:px + fw]
    region = region * (1 - alpha) + crop_chip.astype(np.float32) * alpha
    out_chip[:, py:py + fh, px:px + fw] = region

    out_mask[py:py + fh, px:px + fw] = np.maximum(
        out_mask[py:py + fh, px:px + fw], crop_mask.astype(np.uint8))
    return out_chip, out_mask


def read_chip(path: Path) -> tuple[np.ndarray, Affine, str]:
    with rasterio.open(path) as src:
        return src.read().astype(np.float32), src.transform, src.crs


def read_mask(path: Path) -> tuple[np.ndarray, Affine, str]:
    with rasterio.open(path) as src:
        return src.read(1).astype(np.uint8), src.transform, src.crs


def write_chip(path: Path, bands: np.ndarray, transform, crs):
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", driver="GTiff",
                       height=bands.shape[1], width=bands.shape[2],
                       count=bands.shape[0], dtype="float32",
                       transform=transform, crs=crs) as dst:
        dst.write(bands.astype(np.float32))


def write_mask(path: Path, mask: np.ndarray, transform, crs):
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", driver="GTiff",
                       height=mask.shape[0], width=mask.shape[1],
                       count=1, dtype="uint8",
                       transform=transform, crs=crs) as dst:
        dst.write(mask.astype(np.uint8), 1)


def expand_negatives_from_majortom(parent_root: Path,
                                   n_per_parent: int,
                                   chip_px: int,
                                   bands: list[str],
                                   out_chip_dir: Path,
                                   out_mask_dir: Path,
                                   rng: random.Random) -> list[str]:
    """Slice each Major-TOM parent into n_per_parent random chip windows.

    Each parent is ~1000x1000 px; we extract `n_per_parent` random
    non-overlapping 224x224 windows per parent. Yields more clear-sky
    NYC backgrounds without needing fresh STAC fetches.
    """
    from rasterio.windows import Window
    new_neg_ids = []
    n_neg = 0
    cells = []
    for cell_dir in sorted(parent_root.iterdir()):
        if not cell_dir.is_dir():
            continue
        for sub_dir in sorted(cell_dir.iterdir()):
            if not sub_dir.is_dir():
                continue
            products = sorted(sub_dir.iterdir())
            if products:
                cells.append(products[0])
    print(f"[neg-expand] {len(cells)} parents available", flush=True)
    for parent_dir in cells:
        for _ in range(n_per_parent):
            try:
                stack = []
                transform, crs = None, None
                # Determine random offset based on first band
                with rasterio.open(parent_dir / f"{bands[0]}.tif") as src:
                    H, W = src.shape
                    if H < chip_px or W < chip_px:
                        break
                    oy = rng.randint(0, H - chip_px)
                    ox = rng.randint(0, W - chip_px)
                for band in bands:
                    with rasterio.open(parent_dir / f"{band}.tif") as src:
                        win = Window(ox, oy, chip_px, chip_px)
                        data = src.read(1, window=win, boundless=True,
                                        fill_value=0,
                                        out_shape=(chip_px, chip_px))
                        if transform is None:
                            transform = src.window_transform(win)
                            crs = src.crs
                    stack.append(data.astype(np.float32))
                chip = np.stack(stack)
                cid = f"nyc_negx_{n_neg:04d}"
                write_chip(out_chip_dir / f"{cid}.tif", chip, transform, crs)
                mask = np.zeros((chip_px, chip_px), dtype=np.uint8)
                write_mask(out_mask_dir / f"{cid}_annotation_flood.tif",
                           mask, transform, crs)
                new_neg_ids.append(cid)
                n_neg += 1
            except Exception as e:
                print(f"  ! neg expand {parent_dir.name}: {e}", flush=True)
    print(f"[neg-expand] {n_neg} new negatives", flush=True)
    return new_neg_ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, required=True,
                    help="Phase 14 dataset root with S2L2A_tif/ and MASK/")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--multiplier", type=int, default=2,
                    help="how many synthetic positives per original positive")
    ap.add_argument("--paste-min", type=int, default=1)
    ap.add_argument("--paste-max", type=int, default=4)
    ap.add_argument("--major-tom-root", type=Path, default=None,
                    help="Major-TOM Core-S2L2A root for additional negatives")
    ap.add_argument("--neg-per-parent", type=int, default=12,
                    help="random sub-chips per Major-TOM parent (for negs)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rng = random.Random(args.seed)

    chip_dir = args.src / "S2L2A_tif"
    mask_dir = args.src / "MASK"

    # Discover positives and negatives.
    pos_chips, pos_masks = [], []
    neg_chips = []
    for chip_path in sorted(chip_dir.glob("*.tif")):
        cid = chip_path.stem
        mp = mask_dir / f"{cid}_annotation_flood.tif"
        if not mp.exists():
            continue
        if cid.startswith("ida_pos_"):
            pos_chips.append(chip_path)
            pos_masks.append(mp)
        elif cid.startswith("nyc_neg_"):
            neg_chips.append(chip_path)
    print(f"[phase19] {len(pos_chips)} positives, {len(neg_chips)} negatives",
          flush=True)

    out_chip_dir = args.out / "S2L2A_tif"
    out_mask_dir = args.out / "MASK"
    out_chip_dir.mkdir(parents=True, exist_ok=True)
    out_mask_dir.mkdir(parents=True, exist_ok=True)

    new_ids = []

    # 1. Carry over original positives + negatives.
    for src_chip, src_mask in zip(pos_chips, pos_masks):
        cid = src_chip.stem
        c, t, crs = read_chip(src_chip)
        m, _, _ = read_mask(src_mask)
        write_chip(out_chip_dir / f"{cid}.tif", c, t, crs)
        write_mask(out_mask_dir / f"{cid}_annotation_flood.tif", m, t, crs)
        new_ids.append(cid)

    for src_chip in neg_chips:
        cid = src_chip.stem
        c, t, crs = read_chip(src_chip)
        m, _, _ = read_mask(mask_dir / f"{cid}_annotation_flood.tif")
        write_chip(out_chip_dir / f"{cid}.tif", c, t, crs)
        write_mask(out_mask_dir / f"{cid}_annotation_flood.tif", m, t, crs)
        new_ids.append(cid)

    # 1b. Optionally expand negatives by slicing Major-TOM parents.
    if args.major_tom_root and args.major_tom_root.exists():
        prithvi_bands = ["B02", "B03", "B04", "B8A", "B11", "B12"]
        new_negs = expand_negatives_from_majortom(
            args.major_tom_root, args.neg_per_parent, 224,
            prithvi_bands, out_chip_dir, out_mask_dir, rng)
        new_ids.extend(new_negs)

    # 2. Synthesize copy-paste positives.
    n_synth = 0
    target = args.multiplier * len(pos_chips)
    pos_pool = list(zip(pos_chips, pos_masks))

    while n_synth < target:
        bg_path = rng.choice(neg_chips)
        bg_c, bg_t, bg_crs = read_chip(bg_path)
        bg_m, _, _ = read_mask(
            mask_dir / f"{bg_path.stem}_annotation_flood.tif")
        n_paste = rng.randint(args.paste_min, args.paste_max)
        for _ in range(n_paste):
            fg_chip_p, fg_mask_p = rng.choice(pos_pool)
            fg_c, _, _ = read_chip(fg_chip_p)
            fg_m, _, _ = read_mask(fg_mask_p)
            bg_c, bg_m = paste(bg_c, bg_m, fg_c, fg_m, rng)

        cid = f"synth_pos_{n_synth:04d}"
        write_chip(out_chip_dir / f"{cid}.tif", bg_c, bg_t, bg_crs)
        write_mask(out_mask_dir / f"{cid}_annotation_flood.tif",
                   bg_m, bg_t, bg_crs)
        new_ids.append(cid)
        n_synth += 1
        if n_synth % 100 == 0:
            print(f"  synthesized {n_synth}/{target}", flush=True)

    # 3. Stratified split (positive chips include synth_pos and ida_pos).
    out_split = args.out / "split"
    out_split.mkdir(parents=True, exist_ok=True)

    pos_ids = [c for c in new_ids
               if c.startswith("ida_pos_") or c.startswith("synth_pos_")]
    neg_ids = [c for c in new_ids
               if c.startswith("nyc_neg_") or c.startswith("nyc_negx_")]
    rng.shuffle(pos_ids); rng.shuffle(neg_ids)

    def split(lst, tr=0.7, va=0.15):
        n = len(lst)
        return lst[:int(tr*n)], lst[int(tr*n):int((tr+va)*n)], lst[int((tr+va)*n):]

    pt, pv, pe = split(pos_ids); nt, nv, ne = split(neg_ids)
    splits = {"train": pt + nt, "val": pv + nv, "test": pe + ne}
    for name, ids in splits.items():
        rng.shuffle(ids)
        (out_split / f"impactmesh_flood_{name}.txt").write_text(
            "\n".join(ids) + "\n")
        n_pos = sum(1 for x in ids if not x.startswith("nyc_neg_"))
        print(f"[phase19] split {name}: {len(ids)} chips ({n_pos} pos)",
              flush=True)
    print(f"[phase19] total: {len(new_ids)} chips "
          f"({len(pos_ids)} pos, {len(neg_ids)} neg)")


if __name__ == "__main__":
    sys.exit(main())
