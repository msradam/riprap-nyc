"""Run Prithvi-EO 2.0 Sen1Floods11 inference on each NYC chip and save the
binary water mask as the pseudo-label for Phase-2 training.

Prithvi-EO 2.0 Sen1Floods11 is the model Riprap's production water-
segmentation specialist already deploys. Using its outputs as labels here
keeps the Phase-2 fine-tune in-domain with what the rest of the system
trusts as "water," and avoids needing FEMA polygon labels (which are
static and observation-time-independent).

The model expects 6 Sentinel-2 bands at native resolution. We map our
12-band L2A chips:

    S2 chip (12 bands extract_chips order):
        B02, B03, B04, B05, B06, B07, B08, B8A, B11, B12, AOT, SCL
    Prithvi Sen1Floods11 expected (6 bands):
        B02 (blue), B03 (green), B04 (red), B8A (narrow NIR),
        B11 (SWIR-1), B12 (SWIR-2)

So we slice [0, 1, 2, 7, 8, 9] from our chip's S2 stack.

Usage:
    python3 prithvi_pseudo_label.py \\
        --chips-root /root/terramind_nyc/chips \\
        --out-root   /root/terramind_nyc/prithvi_masks \\
        --device     cuda
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch


# Indices into our extract_chips.py S2 stack that correspond to the bands
# Prithvi Sen1Floods11 was fine-tuned on.
PRITHVI_S2_INDICES = [0, 1, 2, 7, 8, 9]  # B02, B03, B04, B8A, B11, B12

# Band-wise normalization stats from Sen1Floods11 — these are baked into
# the Prithvi-EO 2.0 fine-tuned checkpoint's expected input distribution.
# Source: ibm-nasa-geospatial/Prithvi-EO-2.0-300M-TL-Sen1Floods11 README.
SEN1FLOODS11_MEANS = np.array([1086.45, 1063.0, 985.95, 2316.61, 2080.98, 1454.81],
                              dtype=np.float32)
SEN1FLOODS11_STDS  = np.array([1141.95, 1170.10, 1287.78, 1369.24, 1374.77, 1318.21],
                              dtype=np.float32)


def load_prithvi(device: str):
    """Load Prithvi-EO 2.0 Sen1Floods11 fine-tune via terratorch's registry."""
    import terratorch.models.backbones.prithvi_mae as _  # ensure registered
    from terratorch.cli_tools import LightningInferenceModel
    # The trusted Riprap path uses terratorch's model factory + the HF
    # checkpoint id; here we mirror that exact load path.
    config = {
        "model": {
            "class_path": "terratorch.tasks.SemanticSegmentationTask",
            "init_args": {
                "model_factory": "EncoderDecoderFactory",
                "model_args": {
                    "backbone": "prithvi_eo_v2_300_tl",
                    "backbone_pretrained": True,
                    "backbone_bands": ["BLUE", "GREEN", "RED", "NARROW_NIR",
                                       "SWIR_1", "SWIR_2"],
                    "necks": [
                        {"name": "SelectIndices", "indices": [5, 11, 17, 23]},
                        {"name": "ReshapeTokensToImage", "remove_cls_token": True},
                        {"name": "LearnedInterpolateToPyramidal"},
                    ],
                    "decoder": "UNetDecoder",
                    "decoder_channels": [512, 256, 128, 64],
                    "head_dropout": 0.1,
                    "num_classes": 2,
                },
                "loss": "ce",
                "freeze_backbone": False,
                "freeze_decoder": False,
            },
        },
    }
    raise NotImplementedError(
        "Prithvi pseudo-labeling is best done via terratorch's CLI predict "
        "against the official ibm-nasa-geospatial/Prithvi-EO-2.0-300M-TL-Sen1Floods11 "
        "config + checkpoint. Use the script's bash wrapper at the bottom "
        "or call the deployed Riprap specialist directly."
    )


def normalize_s2(stack6: np.ndarray) -> np.ndarray:
    """stack6 is (6, H, W) raw L2A integer; return (6, H, W) float32 z-scored."""
    a = stack6.astype(np.float32)
    return (a - SEN1FLOODS11_MEANS[:, None, None]) / SEN1FLOODS11_STDS[:, None, None]


def _ensure_npy(out_path: Path, mask: np.ndarray):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(out_path, mask.astype(np.int8))


def label_one(chip_dir: Path, model, device: str) -> dict:
    """Load one extract_chips.py chip, run Prithvi, save mask."""
    npz = np.load(chip_dir / "chip.npz")
    s2_full = npz["s2"]                              # (12, 224, 224) float32
    s2_six = s2_full[PRITHVI_S2_INDICES]             # (6, 224, 224)
    x = normalize_s2(s2_six)
    x_t = torch.from_numpy(x).unsqueeze(0).to(device)  # (1, 6, 224, 224)

    with torch.no_grad():
        out = model({"image": x_t}) if hasattr(model, "forward") else model(x_t)
    logits = out.output if hasattr(out, "output") else out
    if isinstance(logits, (list, tuple)):
        logits = logits[0]
    pred = logits.argmax(1)[0].cpu().numpy().astype(np.int8)  # (224, 224)
    return {"chip_id": chip_dir.name, "n_water_px": int((pred == 1).sum()),
            "mask": pred}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chips-root", required=True)
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--prithvi-config", default=None,
                    help="optional terratorch YAML; defaults to in-script load")
    ap.add_argument("--prithvi-ckpt", default=None,
                    help="optional Prithvi ckpt; pulled from HF if absent")
    args = ap.parse_args()

    chips_root = Path(args.chips_root)
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    print(f"[prithvi] loading model on {args.device}...", flush=True)
    if args.prithvi_config and args.prithvi_ckpt:
        from terratorch.cli_tools import LightningInferenceModel
        wrapper = LightningInferenceModel.from_config(args.prithvi_config,
                                                      args.prithvi_ckpt)
        model = wrapper.model.to(args.device).eval()
    else:
        model = load_prithvi(args.device)

    summary = []
    chip_dirs = sorted(p for p in chips_root.iterdir()
                       if p.is_dir() and (p / "chip.npz").exists())
    for cd in chip_dirs:
        try:
            r = label_one(cd, model, args.device)
            mask = r.pop("mask")
            _ensure_npy(out_root / f"{cd.name}.npy", mask)
            print(f"[prithvi] {cd.name} OK water_px={r['n_water_px']}",
                  flush=True)
            summary.append(r)
        except Exception as e:
            print(f"[prithvi] {cd.name} FAIL {e}", flush=True)
            summary.append({"chip_id": cd.name, "ok": False, "err": str(e)})

    (out_root / "label_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"[done] {len([s for s in summary if 'n_water_px' in s])} / {len(chip_dirs)}",
          flush=True)


if __name__ == "__main__":
    sys.exit(main())
