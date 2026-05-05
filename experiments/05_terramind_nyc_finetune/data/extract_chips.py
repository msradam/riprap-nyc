"""Extract aligned (S2L2A, S1GRD-RTC) chip pairs from STAC URLs in the
manifest, reprojecting both onto a common UTM grid at 10 m / pixel and
cropping a 224x224 window centered on the scene-overlap centroid.

Outputs per chip:
  chips/<idx>_<src>/
    s2_rgb.png        # RGB visualization (B04/B03/B02, 5-95 percentile stretch)
    s1_vv.png         # VV backscatter (dB-stretched grayscale)
    s1_vh.png         # VH backscatter (dB-stretched grayscale)
    panel.png         # side-by-side [S2 RGB | S1 VV | S1 VH] for visual QA
    chip.npz          # raw arrays: s2 (12, 224, 224), s1 (2, 224, 224)
    meta.json         # bbox, CRS, source manifest record

Run on the droplet (data is cached in /root/terramind_nyc/chips/) since
chip downloads are large and bandwidth is better there.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import traceback
from io import BytesIO

import numpy as np

# rasterio + odc-stac for reprojection. Both are pip-installable.
import planetary_computer as pc
from pystac_client import Client
import rasterio
from rasterio.warp import reproject, Resampling, transform as warp_transform
from rasterio.windows import Window
from PIL import Image


CHIP_PX = 224
CHIP_RES_M = 10  # S2 native; S1 RTC is 10 m too.

# NYC five-borough convex-hull bbox in lon/lat.
# Anchor is computed PER SCENE in raster-UTM space (not in lon/lat) — see
# data_driven_chip_window().
NYC_BBOX = (-74.30, 40.45, -73.65, 40.95)


# Manhattan / Brooklyn Bridge area — guaranteed to land on dense NYC built
# environment when the scene contains it.
NYC_REFERENCE_LONLAT = (-73.99, 40.72)


def scene_contains_reference(scene_bbox, ref=NYC_REFERENCE_LONLAT):
    sw, ss, se, sn = scene_bbox
    return sw <= ref[0] <= se and ss <= ref[1] <= sn


def chip_anchor_lonlat(scene_bbox):
    """Use Manhattan reference if scene contains it; else fall back to bbox
    intersection centroid (caller should have already filtered, this is a
    safety net)."""
    if scene_contains_reference(scene_bbox):
        return NYC_REFERENCE_LONLAT
    sw, ss, se, sn = scene_bbox
    iw = max(sw, NYC_BBOX[0]); ie = min(se, NYC_BBOX[2])
    is_ = max(ss, NYC_BBOX[1]); in_ = min(sn, NYC_BBOX[3])
    return ((iw + ie) / 2, (is_ + in_) / 2)

S2_BANDS = ["B02", "B03", "B04", "B05", "B06", "B07",
            "B08", "B8A", "B11", "B12", "AOT", "SCL"]
S1_BANDS = ["vv", "vh"]

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/"
_STAC_CLIENT = None


def _stac():
    global _STAC_CLIENT
    if _STAC_CLIENT is None:
        _STAC_CLIENT = Client.open(STAC_URL)
    return _STAC_CLIENT


def fresh_signed_assets(item_id, collection, retries=4):
    """Re-sign assets for a STAC item by ID. PC API frequently times out
    (>50% rate observed); retry with backoff."""
    import time
    last = None
    for attempt in range(retries):
        try:
            item = _stac().get_collection(collection).get_item(item_id)
            if item is None:
                raise RuntimeError(f"STAC item not found: {collection}/{item_id}")
            return {k: pc.sign(a.href) for k, a in item.assets.items()}
        except Exception as e:
            last = e
            wait = 2 + 3 * attempt
            print(f"  fresh_signed_assets retry {attempt+1}/{retries} after {wait}s: {e}",
                  flush=True)
            time.sleep(wait)
    raise last


def stretch(arr, lo=2, hi=98):
    a = arr.astype(np.float32)
    finite = np.isfinite(a)
    if not finite.any():
        return np.zeros_like(a, dtype=np.uint8)
    plo, phi = np.percentile(a[finite], [lo, hi])
    if phi <= plo:
        return np.zeros_like(a, dtype=np.uint8)
    out = np.clip((a - plo) / (phi - plo), 0, 1)
    return (out * 255).astype(np.uint8)


def s1_db_stretch(arr):
    a = arr.astype(np.float32)
    a = np.where(a > 0, a, 1e-6)
    db = 10.0 * np.log10(a)
    return stretch(db)


# Inland NYC reference points (lon, lat). Anchor placement requires that
# at least one of these falls within the chosen S2 raster's data extent —
# otherwise the chip would land in coastal-overlap-strip slop centered on
# open Atlantic. Each centroid is on solid built environment.
NYC_REFERENCE_POINTS = [
    ("manhattan",     (-73.971, 40.778)),  # Central Park
    ("brooklyn",      (-73.949, 40.650)),  # Prospect Park / Crown Heights
    ("queens",        (-73.842, 40.728)),  # Forest Hills / Rego Park
    ("bronx",         (-73.864, 40.844)),  # central Bronx
    ("staten-island", (-74.151, 40.580)),  # central Staten Island
]


def candidate_chip_windows(href, anchor_choices=NYC_REFERENCE_POINTS):
    """Return ALL valid (anchor_name, window, transform, crs) candidates for
    NYC reference points that fit inside the raster's bounds. Caller picks
    the first one whose chip read isn't zero-filled (since raster.bounds
    reflects the full tile extent but actual image data can be sparse
    within it, e.g. swath edges, no-data fill).
    """
    candidates = []
    with rasterio.open(href) as src:
        b = src.bounds
        for name, (lon, lat) in anchor_choices:
            ax, ay = warp_transform("EPSG:4326", src.crs, [lon], [lat])
            x, y = ax[0], ay[0]
            margin_m = CHIP_PX / 2 * 10
            if not (b.left + margin_m <= x <= b.right - margin_m and
                    b.bottom + margin_m <= y <= b.top - margin_m):
                continue
            col, row = (~src.transform) * (x, y)
            col_off = int(round(col)) - CHIP_PX // 2
            row_off = int(round(row)) - CHIP_PX // 2
            col_off = max(0, min(src.width - CHIP_PX, col_off))
            row_off = max(0, min(src.height - CHIP_PX, row_off))
            win = Window(col_off, row_off, CHIP_PX, CHIP_PX)
            win_transform = src.window_transform(win)
            candidates.append((name, win, win_transform, src.crs))
    return candidates


def read_s2_band(href, window):
    with rasterio.open(href) as src:
        data = src.read(1, window=window, boundless=True, fill_value=0,
                        out_shape=(CHIP_PX, CHIP_PX),
                        resampling=Resampling.bilinear)
    return data.astype(np.float32)


def read_s1_band_into_grid(href, dst_crs, dst_transform):
    """Read full S1 RTC raster and reproject into the S2 chip grid."""
    with rasterio.open(href) as src:
        src_band = src.read(1)
        dst = np.zeros((CHIP_PX, CHIP_PX), dtype=np.float32)
        reproject(
            source=src_band,
            destination=dst,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=dst_transform,
            dst_crs=dst_crs,
            resampling=Resampling.bilinear,
        )
    return dst


def build_panel(s2_rgb_u8, vv_u8, vh_u8):
    h, w = CHIP_PX, CHIP_PX
    panel = np.zeros((h, w * 3, 3), dtype=np.uint8)
    panel[:, :w, :] = s2_rgb_u8
    panel[:, w:2 * w, :] = vv_u8[..., None]
    panel[:, 2 * w:, :] = vh_u8[..., None]
    return panel


def extract_one(rec, idx, source_label, out_root):
    """Extract one chip pair from a manifest record. Returns dict with status."""
    out_dir = os.path.join(out_root, f"{idx:02d}_{source_label}")
    os.makedirs(out_dir, exist_ok=True)

    s2_assets = fresh_signed_assets(rec["s2_id"], "sentinel-2-l2a")
    s1_assets = fresh_signed_assets(rec["s1_id"], "sentinel-1-rtc")

    # Anchor on a 10 m S2 band (B04 is always there for L2A).
    anchor = s2_assets.get("B04")
    if anchor is None:
        raise RuntimeError("manifest record has no B04 asset")

    # Try every NYC reference point that fits inside the raster bounds.
    # The first one whose B04 read isn't zero-filled is the chip location.
    # raster.bounds is the FULL tile extent — actual data inside can be sparse
    # (no-data fill at swath edges). A cheap probe of B04 catches that.
    candidates = candidate_chip_windows(anchor)
    if not candidates:
        raise RuntimeError("no NYC reference point fits inside raster bounds")

    chosen = None
    for name, win, win_transform, crs in candidates:
        with rasterio.open(anchor) as src:
            probe = src.read(1, window=win, boundless=True, fill_value=0)
        if (probe > 0).mean() >= 0.8:
            chosen = (name, win, win_transform, crs)
            break
    if chosen is None:
        raise RuntimeError(
            f"no candidate anchor produced ≥80% nonzero B04 (tried {[c[0] for c in candidates]})"
        )
    anchor_name, win, win_transform, dst_crs = chosen

    # S2 stack (12 bands). Some bands are 20m native (B05/B06/B07/B8A/B11/B12)
    # — rasterio's read with out_shape=CHIP_PX resamples them to the 10m chip grid.
    s2_stack = np.zeros((len(S2_BANDS), CHIP_PX, CHIP_PX), dtype=np.float32)
    for i, b in enumerate(S2_BANDS):
        href = s2_assets.get(b)
        if href is None:
            raise RuntimeError(f"missing S2 band {b}")
        with rasterio.open(href) as src:
            left, bottom, right, top = rasterio.windows.bounds(win, win_transform)
            band_win = rasterio.windows.from_bounds(
                left, bottom, right, top, transform=src.transform
            )
            data = src.read(
                1, window=band_win, boundless=True, fill_value=0,
                out_shape=(CHIP_PX, CHIP_PX),
                resampling=Resampling.bilinear,
            )
        s2_stack[i] = data.astype(np.float32)

    # S1 stack (vv, vh) reprojected onto the S2 chip grid.
    s1_stack = np.zeros((len(S1_BANDS), CHIP_PX, CHIP_PX), dtype=np.float32)
    for i, b in enumerate(S1_BANDS):
        href = s1_assets.get(b)
        if href is None:
            raise RuntimeError(f"missing S1 band {b}")
        s1_stack[i] = read_s1_band_into_grid(href, dst_crs, win_transform)

    # Quality gate: reject chips with too much zero-fill in either modality.
    s2_nz = float((s2_stack > 0).mean())
    s1_nz = float((s1_stack > 0).mean())
    if s2_nz < 0.5 or s1_nz < 0.5:
        raise RuntimeError(
            f"chip too sparse: S2 nz {s2_nz*100:.1f}%, S1 nz {s1_nz*100:.1f}%"
        )

    # Visualizations.
    rgb = np.stack([s2_stack[2], s2_stack[1], s2_stack[0]], axis=-1)  # B04 B03 B02
    rgb_u8 = np.stack([stretch(rgb[..., k]) for k in range(3)], axis=-1)
    vv_u8 = s1_db_stretch(s1_stack[0])
    vh_u8 = s1_db_stretch(s1_stack[1])
    Image.fromarray(rgb_u8).save(os.path.join(out_dir, "s2_rgb.png"))
    Image.fromarray(vv_u8).save(os.path.join(out_dir, "s1_vv.png"))
    Image.fromarray(vh_u8).save(os.path.join(out_dir, "s1_vh.png"))
    Image.fromarray(build_panel(rgb_u8, vv_u8, vh_u8)).save(
        os.path.join(out_dir, "panel.png"))

    np.savez_compressed(os.path.join(out_dir, "chip.npz"),
                        s2=s2_stack.astype(np.float32),
                        s1=s1_stack.astype(np.float32))
    with open(os.path.join(out_dir, "meta.json"), "w") as f:
        json.dump({
            "s2_id": rec["s2_id"],
            "s1_id": rec["s1_id"],
            "s2_datetime": rec["s2_datetime"],
            "s1_datetime": rec["s1_datetime"],
            "delta_days": rec["delta_days"],
            "cloud_cover": rec.get("cloud_cover"),
            "bbox": rec["bbox"],
            "dst_crs": str(dst_crs),
            "dst_transform": list(win_transform)[:6],
            "anchor": anchor_name,
            "source": source_label,
        }, f, indent=2)
    return {"ok": True, "dir": out_dir,
            "s2_dtype": str(s2_stack.dtype), "s1_dtype": str(s1_stack.dtype),
            "s2_nz_pct": round(s2_nz * 100, 1),
            "s1_nz_pct": round(s1_nz * 100, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-manifest", required=True)
    ap.add_argument("--holdout-manifest", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-train", type=int, default=5)
    ap.add_argument("--n-holdout", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    os.makedirs(args.out, exist_ok=True)

    # Loose pre-screen: scene bbox must overlap NYC bbox at all. This is a
    # cheap text-only filter; the data-driven anchor in extract_one rejects
    # the false positives (scenes whose lon/lat bbox spans NYC but whose
    # actual UTM raster doesn't).
    def overlaps_nyc(bbox):
        sw, ss, se, sn = bbox
        return not (se < NYC_BBOX[0] or sw > NYC_BBOX[2] or
                    sn < NYC_BBOX[1] or ss > NYC_BBOX[3])

    train_all = [json.loads(l) for l in open(args.train_manifest)]
    holdout_all = [json.loads(l) for l in open(args.holdout_manifest)]
    train = [r for r in train_all if overlaps_nyc(r["bbox"])]
    holdout = [r for r in holdout_all if overlaps_nyc(r["bbox"])]
    print(f"[extract] train manifest: {len(train_all)} -> {len(train)} overlap NYC bbox")
    print(f"[extract] holdout manifest: {len(holdout_all)} -> {len(holdout)} overlap NYC bbox")

    # Over-pick to absorb data-driven rejections (loose bbox overlap is
    # a noisy filter).
    rng.shuffle(train)
    rng.shuffle(holdout)
    train_pick = train[: args.n_train * 3]
    holdout_pick = holdout[: args.n_holdout * 3]

    summary = []
    idx = 0

    def extract_until(records, source, target):
        nonlocal idx
        ok_count = 0
        for rec in records:
            if ok_count >= target:
                break
            try:
                r = extract_one(rec, idx, source, args.out)
                print(f"[chip {idx:02d} {source}] OK s2_nz={r['s2_nz_pct']}% "
                      f"s1_nz={r['s1_nz_pct']}% -> {r['dir']}", flush=True)
                ok_count += 1
            except Exception as e:
                # Clean up the empty dir from a failed extraction.
                fail_dir = os.path.join(args.out, f"{idx:02d}_{source}")
                if os.path.isdir(fail_dir) and not os.listdir(fail_dir):
                    os.rmdir(fail_dir)
                r = {"ok": False, "err": str(e)}
                print(f"[chip {idx:02d} {source}] FAIL {e}", flush=True)
            summary.append({"idx": idx, "source": source,
                            "s2_id": rec["s2_id"], **r})
            idx += 1
        return ok_count

    n_train_ok = extract_until(train_pick, "train", args.n_train)
    n_holdout_ok = extract_until(holdout_pick, "holdout", args.n_holdout)

    with open(os.path.join(args.out, "extract_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n[done] train: {n_train_ok}/{args.n_train} OK, "
          f"holdout: {n_holdout_ok}/{args.n_holdout} OK -> {args.out}")
    return 0 if (n_train_ok >= args.n_train and n_holdout_ok >= args.n_holdout) else 1


if __name__ == "__main__":
    sys.exit(main())
