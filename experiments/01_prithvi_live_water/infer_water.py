"""Run Prithvi-EO 2.0 (Sen1Floods11 fine-tune) on a 6-band S2 chip.

Wraps `terratorch.cli_tools.LightningInferenceModel` per the upstream
inference.py recipe. Returns:
  - the binary water mask (1 where water, 0 elsewhere)
  - the % water inside a 500 m radius circle centered on the chip
  - the % water across the whole 5.12 km chip
  - an RGB+mask overlay PNG for the trace UI

Phase 1 deliberate simplifications (documented in RESULTS.md):
  - we run the model on the **center 512x512** of our 1024x1024 chip
    (matches Sen1Floods11 training size; tiling can be added later)
  - bands are scaled by /10000 per upstream's recipe
  - no NTA baseline computation in this script — that's a separate
    offline job; this script just outputs the per-chip % water and
    leaves the comparative-claim construction to the doc emitter
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import rasterio
import torch
from huggingface_hub import hf_hub_download
from PIL import Image

CACHE = Path(__file__).parent / ".cache"
CACHE.mkdir(exist_ok=True)

REPO = "ibm-nasa-geospatial/Prithvi-EO-2.0-300M-TL-Sen1Floods11"
IMG_SIZE = 512                # Sen1Floods11 training size
CHIP_PX = 1024                # our fetch_s2_chip output
CENTER_RADIUS_M = 500
PIXEL_M = 10                  # S2 resolution


@dataclass
class WaterResult:
    address_label: str
    chip_path: str
    item_id: str | None
    item_datetime: str | None
    cloud_cover: float | None
    pct_water_full: float          # over the 5.12 km chip
    pct_water_within_500m: float   # within a 500 m circle of the point
    overlay_png: str
    mask_npy: str


def _load_model(device: str) -> tuple:
    config_path = hf_hub_download(REPO, "config.yaml")
    checkpoint = hf_hub_download(REPO, "Prithvi-EO-V2-300M-TL-Sen1Floods11.pt")
    from terratorch.cli_tools import LightningInferenceModel
    model = LightningInferenceModel.from_config(config_path, checkpoint)
    model.model.eval()
    if device == "cuda" and torch.cuda.is_available():
        model.model.cuda()
    return model, config_path


def _load_upstream_run_model():
    """Pull the upstream `run_model()` helper from the model repo's
    inference.py so we use IBM-NASA's exact preprocessing
    (datamodule.test_transform + augmentation) instead of guessing."""
    import importlib.util
    inference_py = hf_hub_download(REPO, "inference.py")
    spec = importlib.util.spec_from_file_location("_prithvi_inference",
                                                   inference_py)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.run_model


def _read_chip(chip_path: str) -> np.ndarray:
    with rasterio.open(chip_path) as src:
        img = src.read()  # (bands, H, W)
        meta = src.meta
    return img.astype(np.float32), meta


def _center_crop(img: np.ndarray, size: int) -> np.ndarray:
    _, h, w = img.shape
    sy = (h - size) // 2
    sx = (w - size) // 2
    return img[:, sy:sy + size, sx:sx + size]


def infer(chip_path: str, address_label: str,
          device: str = "cpu", out_dir: Path | None = None) -> WaterResult:
    out_dir = Path(out_dir or CACHE / "infer")
    out_dir.mkdir(exist_ok=True, parents=True)

    img, _meta = _read_chip(chip_path)
    img = _center_crop(img, IMG_SIZE)

    # Scale to 0-1. Our fetch_s2_chip stores float32 raw S2 reflectance
    # values in [0, ~10000+]; the upstream recipe is /10000.
    if img.mean() > 1:
        img = img / 10000.0

    model, _ = _load_model(device)
    run_model = _load_upstream_run_model()

    # Upstream run_model expects (B=1, C=6, T=1, H, W) numpy float
    x = img[None, :, None, :, :]  # (1, 6, 1, 512, 512)
    pred_t = run_model(x, None, None, model.model, model.datamodule, IMG_SIZE)
    # pred_t: (1, H, W) tensor of class indices. Class 1 = water.
    pred = pred_t[0].cpu().numpy().astype(np.uint8)

    # % water across the whole 512×512 (5.12 km) crop
    pct_full = float(100.0 * pred.mean())

    # % water within a 500 m radius (50 px) of center
    yy, xx = np.indices(pred.shape)
    cy, cx = pred.shape[0] // 2, pred.shape[1] // 2
    radius_px = CENTER_RADIUS_M / PIXEL_M
    circle = (yy - cy) ** 2 + (xx - cx) ** 2 <= radius_px ** 2
    if circle.sum() == 0:
        pct_500 = 0.0
    else:
        pct_500 = float(100.0 * pred[circle].mean())

    # Overlay PNG for the trace UI: dim RGB + cyan mask
    rgb = np.stack([img[2], img[1], img[0]], axis=-1)  # B04, B03, B02
    rgb = np.clip(rgb / max(rgb.max(), 1e-6), 0, 1)
    overlay = (rgb * 255).astype(np.uint8)
    mask_color = np.array([72, 198, 235], dtype=np.uint8)
    overlay[pred == 1] = ((overlay[pred == 1].astype(int) * 0.4 +
                           mask_color * 0.6).clip(0, 255).astype(np.uint8))
    safe_label = address_label.replace(" ", "_").lower()
    overlay_png = out_dir / f"overlay_{safe_label}.png"
    mask_npy = out_dir / f"mask_{safe_label}.npy"
    Image.fromarray(overlay).resize((512, 512)).save(overlay_png)
    np.save(mask_npy, pred)

    # The chip metadata was written by fetch_s2_chip; pull it from
    # alongside the .tif if present.
    meta_json = Path(chip_path).with_suffix(".json")
    item_id = None
    item_datetime = None
    cc = None
    if meta_json.exists():
        meta = json.loads(meta_json.read_text())
        item_id = meta.get("item_id")
        item_datetime = meta.get("item_datetime")
        cc = meta.get("cloud_cover")

    return WaterResult(
        address_label=address_label,
        chip_path=chip_path,
        item_id=item_id,
        item_datetime=item_datetime,
        cloud_cover=cc,
        pct_water_full=pct_full,
        pct_water_within_500m=pct_500,
        overlay_png=str(overlay_png),
        mask_npy=str(mask_npy),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chip", required=True, help="Path to 6-band S2 chip GeoTIFF")
    ap.add_argument("--label", required=True, help="Human-readable address label")
    ap.add_argument("--device", default="cpu")
    args = ap.parse_args()
    r = infer(args.chip, args.label, device=args.device)
    print(json.dumps(asdict(r), indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
