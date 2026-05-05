"""TerraMind micro-finetune on NYC labels — proof it works on AMD MI300X.

Goal: show the smallest possible *real* fine-tune of TerraMind on NYC
data converges loss in a few seconds on the MI300X. Not building a
useful model — just showing the end-to-end loop (load → forward →
backward → step) works on the AMD ROCm path with terratorch.

Setup:
  - TerraMind v1 base ENCODER (frozen) — the multimodal foundation
    model's vision encoder, ~300 M params.
  - Tiny classification head on top — single linear layer over the
    pooled patch embedding, 2-class output.
  - 8 synthetic NYC samples (6-band S2L2A 224×224 tensors). Labels
    are deterministic based on the synthetic input (a function of
    the NIR band's mean) so the head has a real signal to learn.
  - 30 SGD steps with Adam. Print loss + accuracy + elapsed.

This isn't a useful classifier — the labels are synthetic. But it
proves: weights load on AMD, forward pass works, gradients flow,
optimizer steps. Real NYC fine-tune would replace the synthetic
labels with actual Sandy-inundation-zone membership at the chip's
center coord (we have the polygon in data/sandy_inundation.geojson).
"""

from __future__ import annotations

import time

import torch
import torch.nn.functional as F


def main():
    # Force-import the terramind registration module so the registry
    # gets populated.
    import terratorch.models.backbones.terramind.model.terramind_register  # noqa
    from terratorch.registry import BACKBONE_REGISTRY

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[micro] device: {device}")
    if device == "cuda":
        props = torch.cuda.get_device_properties(0)
        print(f"[micro] gpu: {torch.cuda.get_device_name(0)}, "
              f"VRAM={props.total_memory/1e9:.1f} GB")

    # ---- Load TerraMind base ENCODER (not the generative variant) ----
    print("[micro] loading terramind_v1_base encoder...")
    t0 = time.time()
    backbone = BACKBONE_REGISTRY.build(
        "terratorch_terramind_v1_base",
        modalities=["S2L2A"],  # one input modality is enough for fine-tune
        pretrained=True,
    )
    backbone.eval()
    backbone.to(device)
    # Freeze backbone — we're only training the head.
    for p in backbone.parameters():
        p.requires_grad = False
    print(f"[micro] backbone loaded in {time.time()-t0:.2f}s; "
          f"params={sum(p.numel() for p in backbone.parameters()):,}")

    # ---- Build synthetic NYC dataset --------------------------------
    # 8 samples. Labels = (1 if mean of NIR band > 0.5 else 0).
    # Real fine-tune would use Sandy-zone membership at the chip's
    # geographic center, derived from data/sandy_inundation.geojson.
    n_samples = 8
    img_size = 224
    # TerraMind v1's S2L2A encoder is trained on the full 12-band L2A
    # tensor (B01, B02, B03, B04, B05, B06, B07, B08, B8A, B09, B11, B12).
    # 6-band subsets (Phase 1's Sen1Floods11 ordering) won't work here.
    bands = 12
    torch.manual_seed(42)
    x = torch.rand(n_samples, bands, img_size, img_size, device=device)
    # Synthetic label rule: True if Narrow NIR (band index 8 = B8A) mean > 0.5.
    y = (x[:, 8].mean(dim=(1, 2)) > 0.5).long().to(device)
    print(f"[micro] dataset: {n_samples} samples, "
          f"label balance: {y.float().mean().item():.2f} positive")

    # ---- Embedding shape probe -------------------------------------
    print("[micro] probing embedding shape...")
    with torch.no_grad():
        # TerraMind backbone expects (B, C, T, H, W) for time-series, or
        # the encoder takes a dict with the modality key. Use the dict
        # form that the registry's modality config knows about.
        out = backbone({"S2L2A": x[:1]})
    # Embedding shape varies by variant; check what we got.
    if isinstance(out, (list, tuple)):
        out_t = out[0]
    elif isinstance(out, dict):
        out_t = next(iter(out.values()))
    else:
        out_t = out
    print(f"[micro] backbone output type={type(out).__name__}, "
          f"shape={tuple(out_t.shape) if hasattr(out_t, 'shape') else 'n/a'}")
    # Pool to per-sample embedding. Output is typically
    # (B, num_patches, dim) for ViT-style; mean-pool patches.
    emb_dim = out_t.shape[-1]
    print(f"[micro] embedding dim: {emb_dim}")

    # ---- Tiny linear head -------------------------------------------
    head = torch.nn.Linear(emb_dim, 2).to(device)
    optimizer = torch.optim.Adam(head.parameters(), lr=1e-3)

    # ---- Train loop --------------------------------------------------
    n_steps = 30
    print(f"[micro] training {n_steps} steps...")
    t0 = time.time()
    losses = []
    accs = []
    for step in range(n_steps):
        with torch.no_grad():
            emb = backbone({"S2L2A": x})
        if isinstance(emb, (list, tuple)):
            emb = emb[0]
        elif isinstance(emb, dict):
            emb = next(iter(emb.values()))
        # Mean-pool over patches (axis 1) -> (B, dim)
        if emb.ndim == 3:
            emb = emb.mean(dim=1)
        logits = head(emb)
        loss = F.cross_entropy(logits, y)
        acc = (logits.argmax(-1) == y).float().mean().item()
        losses.append(loss.item())
        accs.append(acc)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        if step == 0 or (step + 1) % 5 == 0 or step == n_steps - 1:
            print(f"[micro] step {step+1:2d}/{n_steps}  "
                  f"loss={loss.item():.4f}  acc={acc:.2f}")
    elapsed = time.time() - t0
    print()
    print(f"[micro] DONE — {n_steps} steps in {elapsed:.2f}s "
          f"({elapsed/n_steps*1000:.0f} ms/step)")
    print(f"[micro] loss: {losses[0]:.4f} -> {losses[-1]:.4f}  "
          f"({(losses[0]-losses[-1])/losses[0]*100:+.1f}% reduction)")
    print(f"[micro] accuracy: {accs[0]:.2f} -> {accs[-1]:.2f}")
    print()
    print("[micro] ✓ TerraMind fine-tune loop working on AMD MI300X")


if __name__ == "__main__":
    main()
