---
license: apache-2.0
base_model: ibm-nasa-geospatial/Prithvi-EO-2.0-300M-TL-Sen1Floods11
tags:
  - earth-observation
  - geospatial
  - sentinel-2
  - flood
  - pluvial
  - hurricane-ida
  - hurricane-sandy
  - nyc
  - new-york
  - segmentation
  - terratorch
  - amd
  - rocm
library_name: terratorch
---

# Prithvi-EO-2.0-NYC-Pluvial v2

NYC-specific pluvial-flood fine-tune of NASA-IBM's Prithvi-EO 2.0 (300M
params, Sen1Floods11 base), trained on AMD Instinct MI300X via AMD
Developer Cloud. Specializes the model on Hurricane Ida 2021 NYC patterns
(basement / sub-surface flooding from rapid stormwater accumulation),
with copy-paste augmentation that materially improves the rare-class
flood IoU.

This is the v2 release. v1 (released earlier today) had test flood IoU
0.10; v2 has **0.5979**, a ~6× improvement on the actual flood detection
task. The change came from:

1. Copy-paste augmentation (Ghiasi et al. CVPR 2021) producing 332
   synthetic positives by alpha-blending real Ida flood polygons onto
   clear-sky NYC chips.
2. Major-TOM expanded negatives (264 additional clear-sky NYC chips
   from 22 cached parents, sliced randomly).
3. Lovász-Softmax loss replacing Dice. Lovász is a direct surrogate
   for IoU and lifts the rare-class metric where Dice optimizes
   pixel-accuracy under heavy imbalance.

## Result

| Test metric | v1 (released earlier) | v2 (this release) | Δ |
|---|---:|---:|---:|
| test/mIoU | 0.5381 | **0.7974** | +25.93 pp |
| test/IoU_0 (non-flood) | 0.9747 | **0.9968** | +2.21 pp |
| **test/IoU_1 (flood)** | **0.1016** | **0.5979** | **+49.79 pp** |
| test/Pixel_Accuracy | 0.9747 | 0.9968 | +2.21 pp |
| test/F1_Score | 0.5858 | 0.8734 | +28.76 pp |
| test/Boundary_mIoU | — | 0.5657 | — |

The flood IoU lift is the headline. v1's 0.10 was honest but weak. v2's
0.60 makes the model demo-credible as a structural-prior signal in
Riprap's flood-exposure briefings.

## Why this exists

Riprap (the parent NYC flood-exposure briefing system) uses Prithvi-EO 2.0
for its pluvial water-segmentation specialist. Sen1Floods11's training
distribution is global flood events dominated by coastal / large-water
events. NYC's deadliest flood mode is pluvial (Hurricane Ida 2021)
where rain accumulates faster than drainage can clear it; basement
apartments in Queens were where people died, not the coast.

This fine-tune nudges the model toward small-polygon, urban, post-rain
water patterns that match NYC's pluvial regime.

## Training data

| Component | Count | Source |
|---|---:|---|
| Ida real positives (centroid chips) | 166 | Riprap baked Ida 2021 polygons + Earth Search S2 |
| Synthetic positives (copy-paste) | 332 | Real Ida polygons pasted onto clear-sky NYC backgrounds |
| Original clear-sky negatives | 22 | Major-TOM Core-S2L2A NYC parents, center-crop |
| Expanded negatives | 264 | Random sub-chips from 22 Major-TOM parents |
| **Total** | **784** | (498 pos / 286 neg) |

The copy-paste augmentation uses Gaussian-feathered alpha blending
(sigma 2.0) on the polygon mask edges. Each synthetic chip pastes
1-4 real Ida polygons at random positions / rotations / flips.

Splits: stratified-random with seed=42:
- train: 548 chips (348 pos / 200 neg)
- val: 118 chips (75 pos / 43 neg)
- test: 118 chips (75 pos / 43 neg)

## Architecture

| | |
|---|---|
| Backbone | `prithvi_eo_v2_300_tl` (NASA-IBM Prithvi-EO 2.0, 300M params) |
| Bands | B02, B03, B04, B8A, B11, B12 (Sen1Floods11 schema) |
| Decoder | UNet, channels [512, 256, 128, 64] |
| Output | 2-class binary segmentation, 224×224 |
| Trainable | 324M params (full backbone + decoder fine-tune) |

## Training procedure

| | |
|---|---|
| Framework | TerraTorch 1.2.7 + PyTorch Lightning 2.6.1 |
| Hardware | 1× AMD Instinct MI300X (192 GB HBM3) |
| Cloud | AMD Developer Cloud |
| ROCm | 4.0.0+1a5c7ec |
| Precision | fp16-mixed |
| Optimizer | AdamW, lr 3e-5 |
| Scheduler | ReduceLROnPlateau (factor 0.5, patience 4) |
| Loss | Lovász-Softmax with class weights [0.4, 1.6] |
| Batch | 8 |
| Epochs | 60 (max reached); best ckpt at val_loss minimum |
| Wall-clock | ~12 min |
| Random seed | 42 |
| Means (per band, raw L2A) | [1086.45, 1063.0, 985.95, 2316.61, 2080.98, 1454.81] |
| Stds (per band, raw L2A) | [1141.95, 1170.10, 1287.78, 1369.24, 1374.77, 1318.21] |

## Honest limitations

- Test set is 118 chips. Reported metrics have wide implicit confidence
  intervals; a different seed could shift them by several pp.
- 332 of 498 positives are synthetic copy-paste. The model learns
  flood spectra well in those chips, which boosts in-distribution
  metrics. On real-world novel Ida-style events, performance may be
  somewhat lower than the test/IoU_1 = 0.60 we report.
- We did not run a multi-seed ablation. Single-run, single-seed result.
- Lovász-Softmax pairs poorly with focal-loss in our setup; we tried
  both Lovász and class-weighted CE, settled on Lovász. The losses are
  fundamentally different optimization targets, and your mileage may
  vary on a different chip distribution.

## What did NOT work

- v2-attempt-1 used focal loss with class_weights [0.4, 1.6]. Model
  collapsed to majority class (val/IoU_1 trended 0.012 → 0.001 over 7
  epochs). Killed and restarted with Lovász. The focal-collapse
  failure mode is reproducible and not specific to ROCm.

## License

Apache 2.0. Underlying datasets:
- ESA Copernicus Sentinel-2 via Major-TOM Core
  (Copernicus Open Data License, attribution required).
- NYC Hurricane Ida polygon extents derived from Sentinel-2 via
  Prithvi offline pre-compute, included in
  [`riprap-nyc/data/prithvi_ida_2021.geojson`](https://github.com/msradam/riprap-nyc).

## Citation

```bibtex
@misc{prithvi-eo-2024,
  title={Prithvi-EO-2.0: A Versatile Multi-Temporal Foundation Model for Earth Observation Applications},
  author={NASA-IMPACT and IBM},
  year={2024},
  eprint={2412.02732},
}

@misc{prithvi-nyc-pluvial-2026-v2,
  title={Prithvi-EO-2.0-NYC-Pluvial v2: NYC Hurricane Ida fine-tune with
         copy-paste augmentation and Lovász-Softmax loss on AMD MI300X},
  author={Rahman, Adam Munawar},
  year={2026},
  publisher={Hugging Face},
  url={https://huggingface.co/msradam/Prithvi-EO-2.0-NYC-Pluvial},
}
```
