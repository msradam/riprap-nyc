# Architecture

This document is the design of record. If you are wondering "why did they
do it this way", the answer is here.

## High-level shape

```
Input chip
    │
    ▼
┌────────────────────────────────────────────┐
│  TerraMind 1.0 base encoder                │
│  (24 ViT blocks, frozen base weights)      │
│                                            │
│   per block:                               │
│     ┌────────────────────────────────┐     │
│     │ qkv linear   ◄── LoRA Δqkv     │     │
│     │ attention                      │     │
│     │ proj linear  ◄── LoRA Δproj    │     │
│     │ MLP                            │     │
│     └────────────────────────────────┘     │
└────────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────────┐
│  Task-specific decoder (trained from        │
│  scratch per adapter, ~5–25 M params)      │
│   - UPerNet head for multiclass            │
│   - FCN head for binary segmentation       │
└────────────────────────────────────────────┘
    │
    ▼
Per-pixel logits (num_classes × 224 × 224)
```

The **only** weights stored per adapter:

- LoRA Δqkv and Δproj for all 24 attention blocks (≈ 2 r × d² each — for
  r=16, d=768 that's ≈ 1.2 M params per adapter, ≈ 5 MB float32, ≈ 2.5 MB
  float16);
- the task-specific decoder + segmentation head (5–25 M params).

The base encoder is loaded once and shared across all adapter swaps. This is
the entire reason the design works: encoder-shared, decoder-per-task, with
LoRA filling the gap between "what TerraMind already knows about EO" and
"what NYC actually looks like".

## ADRs

### ADR-001: Why LoRA, not full fine-tune

**Decision.** Train each NYC task as a LoRA adapter on a frozen TerraMind
base, with the task-specific decoder also trainable.

**Alternatives considered.**

1. *Three full fine-tunes (status quo).* What we already have on Hugging
   Face under `msradam/TerraMind-base-Flood-NYC`. Three near-identical
   encoders sit on disk; ~640 MB–2.2 GB per task. No path to "one model
   on disk".

2. *Custom multi-head Lightning module.* Shared encoder, separate decoders,
   joint loss. Attempted in `experiments/15_terramind_multihead/`. TerraMind
   ViT outputs single-scale tokens, but UPerNet expects a 4-level FPN at
   strides {4, 8, 16, 32}. Reproducing the FPN neck stack
   (`Reshape → SelectIndices → LearnedInterpolateToPyramid`) per head and
   making them all coexist with one set of encoder activations is solvable
   but not in the hackathon window. It also produces a *single* large
   checkpoint, which is the opposite of what we want for "easy to add new
   tasks later".

3. *Zero-shot via `terramind_v1_base_generate`.* TerraMind can generate LULC
   directly from S2 without fine-tuning. Discards the NYC specialization
   we already saw move the needle (LULC mIoU 0.5253 fine-tuned vs base
   pretrained, on the same NYC test split). For a publishable artifact,
   throwing away that signal is unacceptable.

**Why LoRA wins.**

- One base file (~1.6 GB) plus ≤ 50 MB per adapter; new tasks are small,
  cheap to publish, cheap to version.
- Each adapter is independently re-trainable when more NYC data arrives —
  the user's stated goal of "easy to add more data on top".
- PEFT-GeoFM (IBM, 2024) reports LoRA on geo-foundation-model encoders
  matches full-fine-tune mIoU within ≤ 1 pp on segmentation tasks. We
  expect similar.
- Adapters compose cleanly with the existing TerraTorch
  `EncoderDecoderFactory` build path; we add `peft.get_peft_model` after
  construction and otherwise reuse the same training stack as the
  full-fine-tune Phase 2/3/4 work.

### ADR-002: LoRA target modules

**Decision.** Apply LoRA to `qkv` and `proj` linears in every transformer
block. Rank 16, alpha 32, dropout 0.05.

**Why.** TerraMind's `terramind_v1_base` exposes attention modules as
`encoder.{i}.attn.qkv` (in-projection) and `encoder.{i}.attn.proj`
(out-projection) for `i ∈ [0, 23]`. These are the canonical LoRA targets
across ViT-style geo-foundation models (PEFT-GeoFM, the LoRA-ViT line).
MLP `fc1`/`fc2` could also be targeted for slightly more capacity, but
empirically the marginal mIoU gain is small (≤ 0.5 pp on similar tasks)
and doubles the adapter size. Stick with attention-only.

Rank 16 is the standard middle-ground for ~768-d ViT-base; rank 8 saves
~half the params with measurable quality drop on Earth-observation tasks
per the PEFT-GeoFM ablations.

### ADR-003: Decoder is trained from scratch per adapter, not LoRA-d

**Decision.** Each adapter gets its own freshly initialized decoder
(UPerNet for multiclass, FCN for binary). The decoder is fully trainable;
LoRA is encoder-only.

**Why.** The decoder is small (5–25 M params), task-specific by definition
(class count, output topology), and learns NYC-specific features from
scratch in a few epochs. Trying to LoRA the decoder is mathematically
fine but architecturally pointless — there's no "base decoder weights"
to specialize away from. This also keeps the total adapter file small
even when including the decoder, because UPerNet at our config is
~21 M params (≈ 80 MB float32, ≈ 40 MB float16).

### ADR-004: One base reference, not bundled

**Decision.** The HuggingFace repo `msradam/TerraMind-NYC-Adapters` does
**not** redistribute the TerraMind 1.0 base weights. It ships only the
adapters and a `base_model_id: ibm-esa-geospatial/TerraMind-1.0-base` field
in each adapter's config.

**Why.** Avoids re-uploading IBM-ESA's 1.6 GB base every time we publish a
new adapter; users pull base once and stack adapters on top. Matches the
PEFT/LoRA Hugging Face publication convention used by
`transformers`+`peft`. Keeps the license clean — the base license stays
where IBM-ESA published it; our repo is purely Apache-2.0 NYC artefacts.

### ADR-005: Eval methodology locked before retraining

**Decision.** [`EVAL.md`](EVAL.md) defines test splits, metrics, and
reporting format BEFORE any adapter is trained against them. Splits are
deterministic from a fixed seed, and the test split files are committed
to the repo.

**Why.** Publishable artifact. Without this, any reported number is
suspect because we could have selected against the test set during
hyperparameter tuning. The locked split is also the same split used by
the Phase 2/3/4 full-fine-tunes, so head-to-head LoRA-vs-full-FT
comparisons are valid.

### ADR-006: TiM-NYC keeps the auxiliary modality generation pathway

**Decision.** The TiM adapter uses backbone variant
`terramind_v1_base_tim` rather than plain `terramind_v1_base`, even though
it's targeting the same 5-class NYC LULC task as `lulc_nyc`.

**Why.** The point of TiM is to test whether internal LULC-token
generation as auxiliary context helps — that's the Phase 3 result we
already saw (+1.27 pp mIoU). Replicating the comparison under the LoRA
regime is informative for the publishable artifact: does the TiM uplift
survive when the encoder is frozen and only LoRA + decoder train? If yes,
TiM is robust; if no, the prior +1.27 pp might have been encoder-side
specialization that vanishes with a frozen base.

### ADR-007: Inference ensemble swaps adapters, doesn't compose them

**Decision.** [`shared/inference_ensemble.py`](shared/inference_ensemble.py)
loads the base once and swaps a single active adapter between task calls.
Tasks are NOT run in parallel against the same forward pass.

**Why.** PEFT supports adapter merging and weighted composition in theory,
but for our use (Riprap FSM specialist nodes invoking distinct tasks
sequentially), the simpler swap-per-task pattern keeps inference
predictable and matches PEFT's stable API. If we later want to merge LoRAs
(e.g. "buildings + LULC at once for a hybrid output"), that's an additive
feature on top of this ensemble, not a replacement.

## Trade-offs accepted

- **Quality vs full fine-tune.** Expected ≤ 1 pp mIoU drop per adapter
  vs the existing Phase 2/3/4 full fine-tunes. We will measure this and
  report honestly in MODEL_CARD.md per adapter. If the drop is materially
  larger on any task we will investigate before publishing.
- **VRAM at training.** LoRA training on TerraMind base needs ≈ 16 GB at
  batch 8 / fp16; trivial on MI300X (192 GB), comfortable on a single
  consumer GPU for downstream re-training.
- **Inference latency.** Adapter swap is ~50 ms (load LoRA matrices into
  memory, no recompile). Negligible relative to the 100–300 ms forward
  pass.

## Future work this design enables

1. Heat-island exposure adapter from MODIS LST + NYC zones.
2. Stormwater impervious-surface adapter (NYC Open Data DEP layers).
3. Sandy historical-inundation recall adapter (492 polygons, 2012, as
   weak supervision against L8/HLS).
4. Joint multi-adapter inference for unified NYC-EO briefings.
