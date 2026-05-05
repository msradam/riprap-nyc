# Phase 15 — TerraMind NYC Multi-head: ONE Model, Multiple Tasks

## Goal

The defensible single artifact. ONE TerraMind checkpoint trained
simultaneously on multiple NYC tasks via a shared backbone with
multiple decoder heads. A multi-task model is harder to overclaim,
harder to forget, and more honest about model capacity than a chain
of separate fine-tunes.

This is the alternative to Phase 12 (TiM) and Phase 13 (buildings) —
INSTEAD OF training them as separate ckpts, we train one model that
does both at the same time.

## Why this is the right shape

- **One artifact** to publish, one card, one repro recipe. Simpler.
- **Shared encoder** learns features that help BOTH tasks; can be more
  parameter-efficient than separate models.
- **No catastrophic forgetting** — both tasks are in the loss, both
  have equal gradient share.
- **Honest claim**: "the same backbone produces these outputs" is
  defensible; "we trained five separate models" sounds less rigorous.
- **Real downstream use**: Riprap's `terramind_nyc` specialist gets
  multiple class-fraction signals from one forward pass.

## Architecture

```
                       ┌─────────────────────────────────┐
  S2L2A (12 bands) ──► │                                 │
  S1RTC (2 bands) ───► │   TerraMind v1 base encoder     │  shared
  DEM   (1 band)  ───► │   (167M trainable params)       │
                       │                                 │
                       └─┬───────────────┬───────────────┘
                         │               │
                         ▼               ▼
              ┌──────────────────┐  ┌──────────────────┐
              │ UNet decoder     │  │ UNet decoder     │
              │  LULC head (5)   │  │  Buildings head  │
              │                  │  │  (binary)        │
              └────────┬─────────┘  └────────┬─────────┘
                       │                     │
                       ▼                     ▼
                 (LULC prediction)    (Building footprint)

  loss = α * dice(LULC) + β * dice(Buildings)
```

Could extend to a third head (flood mask) once Phase 14's Prithvi
NYC dataset exists — same chip → flood mask via Prithvi labels —
but flood is a different signal and may want a separate model.
Stick to LULC + Buildings for the multi-head experiment.

## Training data

Same 22 parent chips × 16 sub-chips = 336 training tiles (Phase 2 dataset).
Each sub-chip now has TWO labels:
- `MASK_LULC/<chip_id>.tif` — 5-class WorldCover labels (Phase 2)
- `MASK_BUILDINGS/<chip_id>.tif` — binary NYC building footprint (Phase 13)

Both rasterized onto the same chip grid in the same prep pipeline.

## Plan

1. Scaffold (this file).
2. Extend `slice_and_label_nyc.py` to write BOTH MASK_LULC and
   MASK_BUILDINGS per sub-chip (currently only LULC).
3. Write `multihead_datamodule.py` — yields `(image_dict, {"lulc": tensor,
   "buildings": tensor})` per batch.
4. Write `terramind_multihead_model.py` — TerraMind backbone + two
   decoder heads, joint forward, joint loss.
5. Write `phase5_multihead.yaml` — training config.
6. Smoke-test on 1 sub-chip with both losses summing.
7. Run full fine-tune (~6 GPU-hr).
8. Eval BOTH heads independently against held-out test set.
   Compare: Phase 5 multi-head LULC IoU vs Phase 2 single-task LULC IoU.
   Compare: Phase 5 multi-head Buildings IoU vs Phase 13 single-task IoU.
9. Publish as `msradam/TerraMind-base-NYC-multitask`.

## Eval gate

Strong: BOTH heads within 1pp of their respective single-task baselines
        AND the model is published as a single deployment artifact.
Acceptable: One head trades up to 3pp loss for the other to gain ≥ that
        much, AND the multi-head story is told honestly.
Negative: Both heads drop ≥ 3pp from single-task → multi-task interference
        is real, publish negative result.

## Risk

Higher than separate models (more bugs in dataloader + multi-loss + dual
heads), but the artifact is much more compelling. If I were a single
judge, I'd recognize this as "real ML engineering" vs "ran the recipe N
times."

## What it adds to Riprap

`app/context/terramind_nyc.py` returns a single `fetch(lat, lon)` with
BOTH building density AND LULC class fractions in one call. Halves
inference cost and surfaces correlated features (a high-density
building tile usually has high "developed" class fraction; the
multi-head model sees this jointly).

## Reproduction (planned)

```bash
python3 experiments/15_terramind_multihead/build_multihead_dataset.py
docker exec terramind terratorch fit --config /root/config_multihead.yaml
docker exec terramind terratorch test --config /root/config_multihead.yaml
```
