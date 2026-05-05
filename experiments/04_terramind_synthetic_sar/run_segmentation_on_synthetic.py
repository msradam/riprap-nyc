"""Run Phase 1's Sen1Floods11 segmentation head on a TerraMind-
synthesized S2L2A scene.

The whole point of the synthesis-direction pivot from the brief: the
existing Phase 1 head (`Prithvi-EO-2.0-300M-TL-Sen1Floods11`,
6-band Sentinel-2 optical input) consumes the synthesized S2L2A
without any modification. This script wraps that call so the
fallback path emits the same `% water within 500m` and polygon
geometry the primary path does.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

CACHE = Path(__file__).parent / ".cache"
CACHE.mkdir(exist_ok=True)

PHASE1_REPO = "ibm-nasa-geospatial/Prithvi-EO-2.0-300M-TL-Sen1Floods11"
IMG_SIZE = 512
PHASE1_BAND_INDICES = [1, 2, 3, 8, 10, 11]  # B02, B03, B04, B8A, B11, B12 in
                                            # TerraMind's 12-band S2L2A order
                                            # [B01, B02, B03, B04, B05, B06,
                                            #  B07, B08, B8A, B09, B11, B12]


@dataclass
class SegResult:
    pct_water_full: float
    pct_water_within_500m: float
    mask_shape: tuple
    mask_npy_path: str
    elapsed_s: float


def _load_phase1_model():
    import importlib.util

    from huggingface_hub import hf_hub_download
    from terratorch.cli_tools import LightningInferenceModel
    cfg = hf_hub_download(PHASE1_REPO, "config.yaml")
    ckpt = hf_hub_download(PHASE1_REPO, "Prithvi-EO-V2-300M-TL-Sen1Floods11.pt")
    m = LightningInferenceModel.from_config(cfg, ckpt)
    m.model.eval()
    inf_py = hf_hub_download(PHASE1_REPO, "inference.py")
    spec = importlib.util.spec_from_file_location("_p1inf", inf_py)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return m, mod.run_model


def segment(synth_s2_npy_path: str) -> SegResult:
    """synth_s2_npy_path: path to a (12, H, W) float32 npy emitted by
    run_terramind_generate.py. We extract the 6-band Phase 1 subset and
    feed it to the Sen1Floods11 head exactly the way Phase 1 does."""
    import numpy as np
    import torch
    from PIL import Image

    arr12 = np.load(synth_s2_npy_path).astype("float32")
    if arr12.ndim != 3 or arr12.shape[0] != 12:
        raise RuntimeError(
            f"expected (12, H, W) S2L2A array, got shape {arr12.shape}"
        )
    arr6 = arr12[PHASE1_BAND_INDICES]  # (6, H, W)
    # Resize to IMG_SIZE×IMG_SIZE — the Sen1Floods11 head was trained on
    # 512×512 chips. TerraMind defaults to 224, so we upscale.
    if arr6.shape[1:] != (IMG_SIZE, IMG_SIZE):
        ten = torch.from_numpy(arr6).unsqueeze(0)
        ten = torch.nn.functional.interpolate(ten,
                                               size=(IMG_SIZE, IMG_SIZE),
                                               mode="bilinear",
                                               align_corners=False)
        arr6 = ten.squeeze(0).numpy()
    # The Phase 1 head expects S2 reflectance scaled by /10000. TerraMind's
    # output is already in roughly the same dynamic range as scaled S2 —
    # we apply Phase 1's "if mean > 1, divide by 10000" guard.
    if arr6.mean() > 1:
        arr6 = arr6 / 10000.0

    model, run_model = _load_phase1_model()
    x = arr6[None, :, None, :, :]  # (1, 6, 1, H, W)

    t0 = time.time()
    pred_t = run_model(x, None, None, model.model, model.datamodule, IMG_SIZE)
    elapsed = time.time() - t0

    pred = pred_t[0].cpu().numpy().astype("uint8")
    pct_full = float(100.0 * pred.mean())

    yy, xx = np.indices(pred.shape)
    cy, cx = pred.shape[0] // 2, pred.shape[1] // 2
    radius_px = 500 / 10  # 500 m / 10 m per pixel
    circle = (yy - cy) ** 2 + (xx - cx) ** 2 <= radius_px ** 2
    pct_500 = float(100.0 * pred[circle].mean()) if circle.sum() else 0.0

    mask_npy = CACHE / Path(synth_s2_npy_path).with_suffix(".mask.npy").name
    np.save(mask_npy, pred)

    # Save a quick RGB overlay for the trace UI.
    rgb = np.stack([arr6[2], arr6[1], arr6[0]], axis=-1)
    rgb = np.clip(rgb / max(rgb.max(), 1e-6), 0, 1)
    overlay = (rgb * 255).astype("uint8")
    mask_color = np.array([72, 198, 235], dtype="uint8")
    overlay[pred == 1] = ((overlay[pred == 1].astype(int) * 0.4 +
                           mask_color * 0.6).clip(0, 255).astype("uint8"))
    overlay_png = mask_npy.with_suffix(".overlay.png")
    Image.fromarray(overlay).resize((512, 512)).save(overlay_png)

    return SegResult(
        pct_water_full=pct_full,
        pct_water_within_500m=pct_500,
        mask_shape=tuple(pred.shape),
        mask_npy_path=str(mask_npy),
        elapsed_s=round(elapsed, 2),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--synth-npy", required=True)
    args = ap.parse_args()
    r = segment(args.synth_npy)
    print(json.dumps(asdict(r), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
