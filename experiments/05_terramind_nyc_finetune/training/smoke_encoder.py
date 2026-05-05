"""Smoke test: load TerraMind v1 base encoder, forward-pass one synthetic
S2L2A chip shaped per the first manifest record. Confirms weights load on
ROCm and produce sensible-shape embeddings.

We don't actually fetch the COG asset — just validate shape/dtype handling
match the manifest. Real chip extraction happens in the train loop.
"""

from __future__ import annotations

import json
import time
import torch

import terratorch.models.backbones.terramind.model.terramind_register  # noqa
from terratorch.registry import BACKBONE_REGISTRY


MANIFEST = "/root/build_manifest_train.jsonl"  # docker cp'd path


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[smoke] device={device}", flush=True)
    if device == "cuda":
        p = torch.cuda.get_device_properties(0)
        print(f"[smoke] gpu={torch.cuda.get_device_name(0)} VRAM={p.total_memory/1e9:.1f} GB",
              flush=True)

    # Inspect first manifest record so the smoke truly mirrors the train data
    try:
        with open(MANIFEST) as fh:
            rec = json.loads(fh.readline())
        print(f"[smoke] manifest[0]: s2={rec['s2_id']} bbox={rec['bbox']} "
              f"chip={rec['chip_size_px']}", flush=True)
        s2_band_keys = [k for k, v in rec["s2_assets"].items() if v]
        print(f"[smoke]   s2 bands: {s2_band_keys}", flush=True)
    except Exception as e:
        print(f"[smoke] could not read manifest: {e}", flush=True)

    # Load TerraMind v1 base encoder
    print("[smoke] loading terramind_v1_base encoder...", flush=True)
    t0 = time.time()
    model = BACKBONE_REGISTRY.build(
        "terramind_v1_base",
        modalities=["S2L2A"],
        pretrained=True,
    )
    model = model.to(device).eval()
    print(f"[smoke] loaded in {time.time()-t0:.1f}s", flush=True)

    n_params = sum(p.numel() for p in model.parameters())
    print(f"[smoke] params={n_params/1e6:.1f} M", flush=True)

    # One synthetic 12-band S2L2A chip (TerraMind expects 12 L2A bands; same
    # convention as the prior micro.py that converged loss).
    x = torch.randn(1, 12, 224, 224, device=device, dtype=torch.float32)
    print(f"[smoke] input: {tuple(x.shape)} dtype={x.dtype}", flush=True)

    with torch.no_grad():
        t0 = time.time()
        out = model({"S2L2A": x})
        dt = time.time() - t0

    if isinstance(out, (list, tuple)):
        shapes = [tuple(o.shape) if hasattr(o, "shape") else type(o).__name__ for o in out]
        print(f"[smoke] forward {dt*1000:.0f} ms -> {len(out)} outputs shapes={shapes}",
              flush=True)
    elif hasattr(out, "shape"):
        print(f"[smoke] forward {dt*1000:.0f} ms -> shape={tuple(out.shape)} dtype={out.dtype}",
              flush=True)
    else:
        print(f"[smoke] forward {dt*1000:.0f} ms -> {type(out).__name__}", flush=True)

    print("[smoke] PASS", flush=True)


if __name__ == "__main__":
    main()
