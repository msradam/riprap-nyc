# Phase 12 — TerraMind TiM (Thinking-in-Modalities) on NYC LULC

## Goal

Replicate IBM-ESA's headline TerraMind innovation — TiM (Thinking-in-Modalities) —
on our NYC LULC task. The hypothesis from the TerraMind paper (Jakubik et al.,
arXiv:2504.11171) is that generating intermediate modality tokens (e.g.,
synthetic LULC) BEFORE predicting downstream improves accuracy by 2–5 pp.

This is the *paper-grade differentiator* for the hackathon submission. To my
knowledge nobody has publicly reproduced TiM on NYC.

## Status

Scaffold + recipe research. Awaits GPU window.

## Recipe (from TerraMind GitHub examples)

The reference is `terramind_v1_small_sen1floods11.ipynb` in IBM's terramind
repo, which shows TiM with `tim_modalities: [LULC]` for binary water seg.

Adaptation for our 5-class NYC LULC:

```yaml
# delta from training/terramind_v1_base_nyc_phase2.yaml
model:
  init_args:
    model_args:
      backbone: terramind_v1_base_tim     # vs terramind_v1_base
      tim_modalities: [LULC]              # generate synthetic LULC tokens first
      backbone_modalities: [S2L2A, S1RTC, DEM]   # actual inputs
      backbone_use_temporal: true
      backbone_temporal_n_timestamps: 4
      # rest unchanged from Phase 2
```

The TiM model generates synthetic LULC tokens from the input modalities,
then uses those tokens AS ADDITIONAL CONTEXT for the downstream LULC head.
Self-referential — the model "thinks in LULC" before predicting LULC.

For our 5-class NYC LULC where the GROUND TRUTH IS ALSO LULC, this is a
slightly pathological case. The cleaner TiM ablation would use a different
intermediate modality (NDVI from S2 → LULC, or LULC from S1 alone). Worth
testing both.

## Plan

1. Scaffold (this file) — done.
2. Write `tim_smoke.py` — tiny smoke run to confirm TiM model loads and
   trains on our NYC dataset without architectural changes.
3. Write `phase3_tim.yaml` — the TiM-enabled training config.
4. Run the fine-tune (~6 GPU-hr).
5. Eval against Phase-2 (no-TiM) on the same 64-chip held-out test split.
   Same metrics: per-class IoU, overall mIoU, Pixel_Accuracy, F1.
6. Publish as `msradam/TerraMind-base-NYC-TiM-LULC` if it beats Phase 2 by
   at least 1pp on test mIoU.

## Eval gate

Strong: > +2pp mIoU vs Phase 2 → publish, headline result
Acceptable: 0 to +2pp → publish, "TiM stable on NYC" framing
Negative: < 0 mIoU vs Phase 2 → publish negative result, document framing

## Risk

Medium. TiM recipe needs adaptation from sen1floods11's setup; 1-2 hours
of debug time likely. Backup plan if TiM model variant doesn't load:
implement TiM-as-input-augmentation manually (run base TerraMind in
generate mode for synthetic LULC, concatenate to input for fine-tune).

## Reproduction (planned)

```bash
docker exec terramind bash -c "
  terratorch fit --config /root/config_phase3_tim.yaml
  terratorch test --config /root/config_phase3_tim.yaml --ckpt_path .../best_val_loss.ckpt
"
```
