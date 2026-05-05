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
  - nyc
  - new-york
  - segmentation
  - terratorch
  - amd
  - rocm
library_name: terratorch
---

# Prithvi-EO-2.0-NYC-Pluvial

NYC-specific pluvial-flood fine-tune of NASA-IBM's Prithvi-EO 2.0 (300M params,
Sen1Floods11 base), trained on AMD Instinct MI300X via AMD Developer Cloud.
Specializes the model on Hurricane Ida 2021 NYC patterns (basement / sub-surface
flooding from rapid stormwater accumulation).

This is the **second model family** in our AMD-fine-tune package, alongside the
TerraMind variants in
[`msradam/TerraMind-base-Flood-NYC`](https://huggingface.co/msradam/TerraMind-base-Flood-NYC).

## Result

| Test metric | Value |
|---|---|
| test/mIoU | 0.5381 |
| test/Pixel_Accuracy | 0.9747 |
| test/IoU_0 (non-flood) | 0.9747 |
| **test/IoU_1 (flood)** | **0.1016** |
| test/F1_Score | 0.5858 |
| test/loss (dice) | 0.5665 |

**Honest framing:** flood IoU 0.10 is weak in absolute terms but reflects the
hard reality of NYC pluvial flooding — small flood polygons (median ~50 pixels)
inside 224×224 chips means each chip is ~99% non-flood. The non-flood IoU
0.97 says the model has good baseline scene understanding; the flood IoU
0.10 says it has *some* signal on the rare positive class but the dataset
size (188 chips, 166 flooded + 22 clear) is too small for strong minority-class
performance.

## Why this exists

Riprap (the parent NYC flood-exposure briefing system) uses Prithvi-EO 2.0
zero-shot via `app/flood_layers/prithvi_water.py` for its water-segmentation
specialist. Sen1Floods11's training distribution is global flood events
dominated by *coastal/large-water* events (Hurricane Harvey, Bolivia rivers).
NYC's deadliest mode is *pluvial* (Hurricane Ida 2021) where rain accumulates
faster than drainage can clear it — basement apartments in Queens were where
people died, not the coast.

This fine-tune nudges the model toward small-polygon, urban, post-rain water
patterns that better match NYC's pluvial regime.

## Training data

**Positives:** 166 NYC chips at the centroid of each polygon in Riprap's
baked `data/prithvi_ida_2021.geojson` (output of a prior offline Prithvi
inference on Hurricane Ida 2021 pre/post Sentinel-2 pair). For each
positive chip, S2 imagery within ±14 days of 2021-09-02 (Ida post-storm)
was pulled live from Element 84's Earth Search STAC mirror.

**Negatives:** 22 clear-sky NYC chips from Major-TOM Core-S2L2A (one per
unique grid cell). Center-cropped 224×224.

**Labels:** the matching Ida polygon rasterized onto the chip's grid for
positives; all-zero mask for negatives.

**Splits:** stratified 70/15/15 by class:
- train: 131 chips (116 pos / 15 neg)
- val: 28 chips (24 pos / 4 neg)
- test: 29 chips (26 pos / 3 neg)

## Architecture

- Backbone: `prithvi_eo_v2_300_tl` (NASA-IBM Prithvi-EO 2.0, 300M params)
- 6-band Sentinel-2 input: B02, B03, B04, B8A, B11, B12 (Sen1Floods11 schema)
- Decoder: UNetDecoder, channels [512, 256, 128, 64]
- Output: 2-class binary segmentation (water/non-water), 224×224 chips
- Trainable: 324M params (full backbone + decoder fine-tune)

## Training procedure

| | |
|---|---|
| Framework | TerraTorch 1.2.7 + PyTorch Lightning 2.6.1 |
| Hardware | 1× AMD Instinct MI300X (192 GB HBM3) |
| Cloud | AMD Developer Cloud |
| ROCm | 4.0.0+1a5c7ec |
| Precision | fp16-mixed |
| Optimizer | AdamW, lr 1e-5, ReduceLROnPlateau (factor 0.5, patience 2) |
| Loss | Dice, class weights [0.342, 1.316] |
| Batch | 8 |
| Epochs | 30 (max_epochs reached) |
| Best val epoch | ~28 |
| Wall-clock | ~6 min |
| Random seed | 42 |
| Means (per band, raw L2A) | [1086.45, 1063.0, 985.95, 2316.61, 2080.98, 1454.81] |
| Stds (per band, raw L2A) | [1141.95, 1170.10, 1287.78, 1369.24, 1374.77, 1318.21] |

## Riprap integration

`app/flood_layers/prithvi_water.py` currently runs zero-shot Sen1Floods11.
Swap the backbone checkpoint id from `Prithvi-EO-2.0-300M-TL-Sen1Floods11`
to `msradam/Prithvi-EO-2.0-NYC-Pluvial` for NYC-specialized inference. The
specialist's output schema doesn't change.

## Out of scope

- Outside NYC bounds (-74.30 to -73.65 lon, 40.45 to 40.95 lat).
- Non-pluvial flooding (coastal surge / tidal). Use the Sen1Floods11 base
  for those — it's stronger on big-water events.
- Real-time alerting. The model is a structural prior, not a measurement.

## Honest limitations

- 188 chips is small for a binary segmentation task with severe class imbalance.
- 166 of 188 positives all come from the SAME Hurricane Ida acquisition
  (2021-09-02). Geographic diversity > temporal diversity in our training
  distribution.
- Single training run; no robustness numbers.
- Flood IoU 0.10 is the honest result — production users should treat this
  as a *prior/auxiliary* signal, not a primary detector.

## Reproduction

```bash
# 1. Pull NYC Hurricane Ida polygons from Riprap (or generate via Prithvi
#    offline pre-compute on Hurricane Ida pre/post S2 pair).
# 2. Build the dataset:
python3 build_dataset.py \
    --ida-polys /path/to/prithvi_ida_2021.geojson \
    --major-tom-root /data/major_tom_nyc/data \
    --out /data/prithvi_nyc

# 3. Convert NPZ chips to multi-band GeoTIFF (terratorch's standard format):
python3 npz_to_tif.py --root /data/prithvi_nyc

# 4. Symlink to a flood-named path (impactmesh datamodule path-greps for it):
ln -s /data/prithvi_nyc /data/prithvi_nyc_flood

# 5. Fine-tune:
terratorch fit --config prithvi_nyc_phase14.yaml

# 6. Eval:
terratorch test --config prithvi_nyc_phase14.yaml \
    --ckpt_path output_phase14_prithvi/ckpt/best_val_loss.ckpt
```

Wall-clock: ~6 min on a single MI300X.

## License

Apache 2.0. Underlying datasets:
- ESA Copernicus Sentinel-2 (Copernicus License — free for any use,
  attribution required).
- NYC Hurricane Ida polygon extents derived from Sentinel-2 via Prithvi
  offline pre-compute, included in
  [`riprap-nyc/data/prithvi_ida_2021.geojson`](https://github.com/msradam/riprap-nyc).

## Citation

```bibtex
@misc{prithvi-eo-2024,
  title={Prithvi-EO-2.0: A Versatile Multi-Temporal Foundation Model for Earth Observation Applications},
  author={NASA-IMPACT and IBM},
  year={2024},
  eprint={2412.02732},
}

@misc{prithvi-nyc-pluvial-2026,
  title={Prithvi-EO-2.0-NYC-Pluvial: NYC Hurricane Ida fine-tune on AMD MI300X},
  author={Rahman, Adam Munawar},
  year={2026},
  publisher={Hugging Face},
  url={https://huggingface.co/msradam/Prithvi-EO-2.0-NYC-Pluvial},
}
```
