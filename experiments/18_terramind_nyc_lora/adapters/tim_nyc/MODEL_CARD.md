---
license: apache-2.0
base_model: ibm-esa-geospatial/TerraMind-1.0-base-TiM
library_name: peft
pipeline_tag: image-segmentation
tags:
  - earth-observation
  - geospatial
  - sentinel-2
  - sentinel-1
  - lulc
  - thinking-in-modalities
  - tim
  - nyc
  - new-york
  - lora
  - peft
  - terramind
  - amd
  - rocm
  - segmentation
---

# TerraMind-NYC-LoRA-TiM

A LoRA adapter on TerraMind 1.0's TiM (Thinking-in-Modalities) variant,
specializing it on the same 5-class NYC LULC task as the
`lulc_nyc` adapter. The point: measure whether the TiM uplift
documented in TerraMind's paper survives under LoRA's frozen-encoder
regime.

Trained on AMD Instinct MI300X via AMD Developer Cloud. Apache 2.0.

## Why TiM

TerraMind's TiM mode generates internal LULC tokens during the forward
pass and uses them as auxiliary context for the downstream task — the
"think before you answer" pattern from the paper. Phase 3 of this
project's earlier work (full fine-tune) showed +1.27 pp test/mIoU vs
plain `terramind_v1_base` on the identical NYC chip distribution. The
question we wanted answered with the LoRA artefact: does that uplift
require encoder-side specialization, or does it survive when the base
is frozen and only LoRA Δ + decoder train?

**Answer: it survives.** TiM-NYC LoRA beats LULC-NYC LoRA by **+1.57
pp** test/mIoU, slightly larger than the +1.27 pp full-FT gap.

## Results

Same test split, same eval methodology as the `lulc_nyc` adapter (64
chips, locked seed=42).

| Configuration | Test mIoU | Pixel Acc | F1 macro | Train wall-clock | Adapter on disk |
|---|---:|---:|---:|---:|---:|
| Phase 3 TiM full fine-tune | 0.5380 | — | — | ~30 min | ~2.2 GB |
| **TerraMind-NYC-LoRA-TiM (this work)** | **0.6023** | **0.8971** | **0.6967** | **~6 min** | **~330 MB** |
| (For comparison) `lulc_nyc` LoRA (no TiM) | 0.5866 | 0.8910 | 0.6733 | ~5 min | ~325 MB |

**Δ vs Phase 3 full fine-tune: +6.43 pp test/mIoU.**
**Δ vs `lulc_nyc` LoRA (TiM uplift): +1.57 pp test/mIoU.**

### Per-class IoU on test split

| Class | IoU | vs `lulc_nyc` LoRA |
|---|---:|---:|
| 0 — Impervious / urban | 0.9639 | +0.0145 |
| 1 — Vegetation | 0.7826 | +0.0023 |
| 2 — Water | 0.7674 | -0.0022 |
| 3 — Bare / cropland | 0.3904 | +0.0012 |
| 4 — Building (LULC scope) | 0.1073 | +0.0626 |

The TiM adapter's uplift over the plain LULC LoRA is concentrated in
class 0 (impervious/urban) and class 4 (building-as-LULC-class) — the
two classes where contextual reasoning about adjacent land use most
helps. Vegetation and water are easier per-pixel decisions and don't
benefit as much from auxiliary modality reasoning.

## How it differs from `lulc_nyc`

Single config delta: `backbone.name: terramind_v1_base_tim` instead of
`terramind_v1_base`, plus `backbone_tim_modalities: [LULC]`.
Everything else (data, splits, decoder, loss, optimizer, schedule) is
identical. The training cost is ~20% higher because of the auxiliary
LULC token generation pass; the disk cost is comparable
(LoRA Δ is bigger because there are more attention blocks in the TiM
encoder, but the decoder/head/neck portion is the same size).

LoRA Δ params: 3,538,944 (vs 884,736 for `lulc_nyc`).
Decoder + head + neck: 79,895,365.

## How it was trained

Identical to `lulc_nyc` except backbone variant. See
[`adapters/tim_nyc/config.yaml`](https://github.com/msradam/riprap-nyc/blob/main/experiments/18_terramind_nyc_lora/adapters/tim_nyc/config.yaml).
Wall-clock: ~6 min on MI300X.

## How it was evaluated

```bash
python3 shared/eval_adapter.py --adapter adapters/tim_nyc
```

Methodology in
[`EVAL.md`](https://github.com/msradam/riprap-nyc/blob/main/experiments/18_terramind_nyc_lora/EVAL.md).

## Inference

Identical to `lulc_nyc` (see that card's snippet) — substitute backbone
name `"terramind_v1_base_tim"` and add
`backbone_tim_modalities=["LULC"]`. Same `EncoderDecoderFactory`
construction otherwise.

## Out of scope, limitations, license

Same as `lulc_nyc`:
- NYC-only.
- 5-class macro collapse only.
- 64-chip test split, single seed.
- Apache 2.0; ESA + WorldCover attribution per
  [`DATA.md`](https://github.com/msradam/riprap-nyc/blob/main/experiments/18_terramind_nyc_lora/DATA.md).

## Citation

```bibtex
@misc{terramind-nyc-adapters-2026,
  title={TerraMind-NYC-Adapters: A LoRA family specializing TerraMind 1.0
         on New York City Earth-Observation tasks},
  author={Rahman, Adam Munawar},
  year={2026},
  publisher={Hugging Face},
  url={https://huggingface.co/msradam/TerraMind-NYC-Adapters},
}
```
