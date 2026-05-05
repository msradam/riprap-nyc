# TerraMind-NYC fine-tune — eval spec v3 (Phase 2 revised)

Supersedes the Phase-2 portion of `eval_spec_v2.md`. Phase 1 stays the
same (ImpactMesh-Flood reproduction on AMD MI300X).

This v3 was written after our bespoke STAC pipeline failed seven times
and we pivoted to an off-the-shelf NYC dataset.

## Phase 2 (revised): NYC LULC fine-tune via Major-TOM + NLCD 2021

### What changed from v2

- **Data source:** Major-TOM Core (Sentinel-2 L2A + Sentinel-1 RTC + DEM)
  on Hugging Face. Pre-staged, ML-ready, no STAC API. Verified 22 NYC
  chips already downloaded.
- **Labels:** NLCD 2021 (USGS National Land Cover Database). 30 m
  rasterized US-wide LULC, 16 classes. Pixel-aligned ground truth.
- **Task:** semantic segmentation, 16 classes (NLCD legend).
- **Pseudo-label dependency removed** — NLCD is real ground truth, not a
  Prithvi inference.

### Why this is better than v2's water-segmentation plan

- **Real labels.** NLCD is USGS-published, peer-reviewed, pixel-aligned.
  Pseudo-labels from Prithvi were a workaround; NLCD is the genuine
  thing.
- **Different downstream from Phase 1.** Phase 1 = binary water/non-water
  flood. Phase 2 = 16-class LULC. Demonstrates TerraMind's
  multi-task versatility, not just "we ran the same recipe twice."
- **Civic-tech relevant for Riprap.** LULC outputs feed directly into
  flood-risk modeling (impervious-surface fraction is a primary driver
  of urban flooding). Phase 2's checkpoint is more useful to Riprap's
  production stack than Phase 1's was.
- **No bespoke data engineering.** Major-TOM + NLCD download in
  minutes; format conversion is straightforward.

## Data summary

| | |
|---|---|
| **Sentinel-2 L2A** | 22 NYC chips × 1068×1068 px @ 10 m, 12 bands, from `Major-TOM/Core-S2L2A` |
| **Sentinel-1 RTC** | grid-cell-matched chips from `Major-TOM/Core-S1RTC` (~22 expected) |
| **DEM** | grid-cell-matched chips from `Major-TOM/Core-DEM` (~22 expected) |
| **Labels** | NLCD 2021, 16 classes, resampled to 10 m on each chip's grid |
| **Sub-chipping** | each 1068×1068 chip → 16 × 256×256 sub-chips → ~350 training tiles |
| **Region** | NYC five-borough convex hull buffered (-74.30, 40.45, -73.65, 40.95) |
| **Time range** | 2020-01-01 to 2025-12-31, ≤ 30 % cloud |
| **License** | Major-TOM Core CC-BY-SA-4.0; NLCD public domain |

## NLCD class collapse (initial)

The 16-class NLCD legend is too granular for our chip count. For Phase 2
we collapse to **5 macro-classes** to keep per-class IoU computable on
~350 chips:

| Macro | NLCD codes | Description |
|---|---|---|
| 0 — Water | 11 | Open water |
| 1 — Developed | 21, 22, 23, 24 | Open / Low / Medium / High intensity dev |
| 2 — Forest / shrub | 41, 42, 43, 51, 52 | Deciduous / Evergreen / Mixed / Dwarf / Shrub |
| 3 — Herbaceous / cultivated | 71, 72, 73, 74, 81, 82 | Grassland / Sedge / Lichens / Moss / Pasture / Crops |
| 4 — Wetland / barren / ice | 12, 31, 90, 95 | Snow / Barren / Woody wet / Herbaceous wet |

This collapse is documented in the model card. If results are strong
we can extend back to full 16-class in a follow-up.

## Training procedure

| | |
|---|---|
| **Init** | Phase-1 best ckpt (`<handle>/TerraMind-base-Flood-AMD-reproduction`) — continuation, not from scratch |
| **Backbone** | full fine-tune |
| **Decoder** | UNetDecoder, channels [512, 256, 128, 64] |
| **Modalities** | S2L2A + S1RTC + DEM (matches Phase 1) |
| **Task** | semantic segmentation, 5 macro-classes |
| **Loss** | dice (or cross-entropy with class weights) |
| **Optimizer** | AdamW, lr 1e-5, ReduceLROnPlateau (factor 0.5, patience 2) |
| **Precision** | bf16-mixed (avoiding the fp16-NaN hit from Phase 1) |
| **Batch** | 8 (smaller, since chips are 256×256) |
| **Epochs** | up to 30 with EarlyStopping (val/loss, patience 5) |
| **Train/val/test** | 70 / 15 / 15 split on the ~350 sub-chips, stratified by parent grid cell to prevent leakage |

## Eval metrics

### Primary

| Metric | What | Pass condition |
|---|---|---|
| Test mean IoU (5 macro-classes) | Headline | report value, no specific gate |
| Per-class IoU (water, developed, forest, herbaceous, wetland) | Stratification | published in model card |
| Pixel accuracy | Sanity | > 0.7 on test set |

### Secondary

- LULC distribution histogram on training set (catches class-imbalance pathologies)
- Side-by-side panels on 5 hand-picked NYC scenes:
  `[real S2 RGB] [real S1 VV] [NLCD truth] [Phase-2 prediction]`

### Generalization sanity

- Run Phase-2 checkpoint on the 14,556 ImpactMesh-Flood test chips to
  check whether Phase 2 catastrophically forgot Phase 1's flood-seg
  ability. Pass: ImpactMesh test mIoU stays within 5 pp of Phase 1's
  (any drop > 5pp = catastrophic forgetting, document in card).

## Decision tree

### A. Full ship

All true:
- Phase 2 test mIoU on NYC sub-chips > 0.50 (5 macro-classes is
  reasonable; chance is 0.20)
- Per-class water IoU > 0.6 (water is easy to learn from S1)
- No catastrophic forgetting on ImpactMesh-Flood (within 5 pp)

→ Publish as `<handle>/TerraMind-base-Flood-NYC-LULC` with full card,
include in submission as the differentiated artifact.

### B. Publish-only

Phase 2 lands working but doesn't clear all gates → publish with honest
"specialized for NYC LULC; trade-offs documented" framing.

### C. Reverted

Phase 2 fails to learn (test mIoU < 0.30, near chance) → publish with
negative-results framing OR don't publish, depending on what failed.

## Reproduction recipe

```bash
# 1. Pull NYC chips from Major-TOM (no STAC):
python3 major_tom_nyc.py --out /data/major_tom_nyc \
                         --collections L2A S1RTC DEM \
                         --max-cloud 30

# 2. Pull NLCD 2021 raster for NYC bbox (USGS, free):
gdal_translate -projwin -74.30 40.95 -73.65 40.45 \
  /vsicurl/.../nlcd_2021_land_cover_l48_20230630.tif \
  nlcd_nyc_2021.tif

# 3. Slice + label + pack:
python3 slice_and_label_nyc.py --major-tom /data/major_tom_nyc \
                               --nlcd nlcd_nyc_2021.tif \
                               --out /data/nyc_lulc_dataset

# 4. Phase 2 fine-tune:
terratorch fit --config terramind_v1_base_nyc_phase2.yaml \
  --ckpt_path .../phase1_best_val_loss.ckpt
```

Estimated wall-clock: 30 min data prep + 1-2 GPU-hours fine-tune.

## Honesty discipline

- **No NYC ground truth from FEMA / NYC OpenData.** NLCD is what we use.
  If a future submission wants FEMA flood-zone polygons, that's a
  different task and a different model.
- **22 unique S2 chip locations.** Sub-chipping multiplies count but not
  diversity. Disclose in card: "fine-tuned on 22 spatially distinct NYC
  Sentinel-2 acquisitions."
- **NLCD 2021 vs S2 acquisition dates.** S2 chips span 2020-2025; NLCD
  is from 2021. LULC changes slowly so this is acceptable for our
  purposes. Disclose.
