# TerraMind-NYC fine-tune — eval specification

**Locked before training kicks off** so the Tuesday-evening "is this
actually better" judgement isn't made under fatigue. If a result we
get later doesn't match the criteria below, the rule is to default
to *publish but don't ship in the demo* — never re-litigate the bar.

## Goal of the fine-tune (one line)

A TerraMind 1.0 base checkpoint specialized on NYC-region S2L2A ↔
S1GRD-RTC pairs, demonstrating that a regional fine-tune of
IBM/ESA's any-to-any geospatial foundation model is feasible in
~30 GPU-hours on a single MI300X and produces qualitatively
plausible synthetic SAR for cloudy NYC days, with quantified
limitations.

The fine-tune is a **publishable artifact** (`msradam/TerraMind-1.0-NYC`
under user handle, Apache-2.0). Whether it ships in the live hackathon
demo is decided by the criteria below — but the publication happens
either way.

## What's being trained

| | |
|---|---|
| Base | `ibm-esa-geospatial/TerraMind-1.0-base` (300 M params, Apache-2.0) |
| Variant | `terramind_v1_base_generate` (the diffusion-sampler head, not the bare encoder) |
| Trainable | Encoder + decoder. Tokenizers (S2L2A and S1GRD-RTC) frozen. |
| Loss | Whatever the upstream `terramind_v1_base_generate` training loop uses — token-level cross-entropy through the discrete codebooks. |
| Optimizer | AdamW, lr 5e-5, cosine decay, 5% warmup |
| Compute budget | 30 GPU-hours hard cap on the AMD MI300X, alarm at 25 |
| Checkpoint cadence | Every 2 GPU-hours; keep best-on-val + most-recent |

## Training data

- **Region:** NYC five-borough convex hull, buffered 5 km (so the
  Hudson Palisades, Newark Bay, and the western Long Island Sound
  shelf are included).
- **Time window:** 2021-05-01 → 2026-04-30 (60 months).
- **Modalities:** Sentinel-2 L2A (12-band, < 30% cloud cover) paired
  with the **temporally-nearest** Sentinel-1 GRD-RTC scene (within
  ±10 days). One pair per chip.
- **Source:** Microsoft Planetary Computer STAC, public + keyless.
- **Chip size:** 224×224, stride 224 (non-overlapping), filtered to
  ≥80% land coverage to drop pure-water tiles.
- **Manifest:** `train_manifest.parquet` — frozen before training,
  with `split: train|val|test`. Every row has `(s2_item_id,
  s1_item_id, lat, lon, chip_idx, datetime, split)`.
- **Held-out test set:** 5 cloudy NYC scenes from **April 2026
  only**, never seen during training. Coordinates pinned in
  `held_out_test.parquet`.

The held-out scenes are the only ones that count for shipping decisions.

## Quantitative metrics

Run on the 5-scene held-out test set after training completes.

### Primary: per-band L1 on S2L2A → S1GRD-RTC synthesis

Reverse-direction (since this is the cloudy-day fallback path Riprap
would actually use): given the *real* cloudy S2L2A as conditioning,
generate synthetic S1GRD-RTC and compare to the temporally-paired
*real* S1GRD-RTC.

| Metric | What it measures | Target |
|---|---|---|
| Mean per-band L1 (VV / VH, dB) | Reflectance fidelity | Fine-tune ≤ base × 0.95 |
| Spatial correlation (per-pixel Spearman) | Structural alignment | Fine-tune ≥ base × 1.05 |

### Secondary: LPIPS perceptual

For each test scene, compute LPIPS (AlexNet feature distance) between
generated and ground-truth S1GRD-RTC.

| Metric | Target |
|---|---|
| Mean LPIPS, lower=better | Fine-tune ≤ base × 0.95 |

### Tertiary: water segmentation downstream

For one waterfront held-out scene where Sandy zone is known:

1. Run base TerraMind synth → Phase-1 Prithvi water seg → % water in 500 m
2. Run fine-tuned TerraMind synth → same Prithvi seg → same %
3. Compare both to the ground-truth real-S2 Prithvi seg

| Metric | Target |
|---|---|
| Absolute error in % water vs. real-S2 baseline | Fine-tune ≤ base |

## Qualitative metric

For the 5 held-out scenes, generate side-by-side panels:

```
[real S2L2A]   [real S1 GRD-RTC]   [base synth S1]   [fine-tune synth S1]
```

Save as PNG in `eval/qual_panels/` with filename
`{scene_id}_{lat}_{lon}.png`. **Reviewer (you) judges:**

- Does the synthesis preserve recognizable NYC infrastructure (bridges,
  piers, harbour features) where ground-truth shows them?
- Does the synthesis avoid hallucinated water in built-up areas?
- Is the synthesis qualitatively *more* coherent than the base, or is
  it equivalent / worse?

This is intentionally subjective — the published model card discloses
that and includes the panels.

## Decision criteria — explicit, no re-litigation

After eval completes, the fine-tune lands in **exactly one** of three
buckets:

### A. Ships in the live hackathon demo + publishes as checkpoint

All three must be true:
- Quantitative: fine-tune passes **≥ 2 of 3** primary/secondary
  numerical targets above.
- Qualitative: at least 4 of 5 held-out panels are judged **clearly
  better** than base on the "preserve infrastructure / avoid
  hallucinated water" criteria.
- Latency: fine-tuned model's per-query inference time on the
  MI300X is **within 1.5×** of base TerraMind's. (No demo benefit
  from a regression that hangs the trace.)

### B. Publishes as checkpoint only, demo runs base TerraMind

If the fine-tune is **not clearly worse than base** but doesn't
clear the bar above. Publish the checkpoint with an honest model
card that includes the eval results and the "didn't decisively
beat base" framing. The demo runs base TerraMind.

This is the *honest publication* outcome and is treated as a fully
acceptable deliverable. Civic-tech publication discipline is more
durable than placing in any single hackathon.

### C. Reverted, no checkpoint published

Only if the fine-tune is **clearly worse than base** on either
quantitative or qualitative — i.e., synthesis collapses, modes
disappear, output goes blank or unreadable. We don't ship a
demonstrably-worse model under our handle.

## Reporting format for the model card

The model card on `huggingface.co/msradam/TerraMind-1.0-NYC` must
include, per IBM-ESA model-card norms:

1. **Header**: license (Apache-2.0), base model link, library_name
   (terratorch), tags, languages, datasets.
2. **Intended use**: NYC-region cloudy-day S2L2A → S1GRD-RTC
   synthesis as a synthetic-prior signal for downstream water
   segmentation. Not a replacement for measurement.
3. **Out-of-scope**: outside the bbox-trained region; outside the
   training time window (no temporal extrapolation claim); not for
   property-level damage prediction; not for insurance / underwriting.
4. **Training data**: STAC query, time window, modality pairs, chip
   size, total chips, train/val/test splits. Public + keyless via
   Microsoft Planetary Computer.
5. **Training procedure**: optimizer, lr, schedule, total
   GPU-hours, hardware (AMD MI300X).
6. **Evaluation**: all metrics from this spec, exact numbers, side-
   by-side qualitative panels embedded in the card.
7. **Bias / generalization**: explicit bbox limitation, training-window
   cut-off, urban-coastal bias.
8. **Reproduction**: link to the training script, manifest hash, eval
   script, this eval_spec.md.
9. **Carbon**: ROCm GPU-hour total + the AMD MI300X TDP-based estimate.
10. **Authors / affiliation**: `msradam` (the user's HF handle).

## Honesty discipline

The model card uses the same four-tier epistemic framing as Riprap
itself: synthetic-prior, not measurement. The card never claims
"reconstruction" or "imaging." Phrasing like "generated a plausible
S1 GRD-RTC scene from the optical context" is the locked phrasing
from Phase 4's RESULTS.md — keep it consistent across the model card,
the Riprap UI, and the published artifact.

## What this spec is not

- It does not specify whether to fine-tune end-to-end or LoRA.
  Default is full fine-tune of encoder + decoder; if that doesn't
  fit in 30 GPU-hours we drop to LoRA on the decoder only and update
  the model card accordingly.
- It does not specify the seed, batch size, or other
  hyperparameter-sweep targets. Those go in `eval/training_config.yaml`
  alongside the trained checkpoint.
- It does not specify the pre-train data manifest schema in detail —
  that lives in `data_pipeline/README.md` once the pipeline lands.
