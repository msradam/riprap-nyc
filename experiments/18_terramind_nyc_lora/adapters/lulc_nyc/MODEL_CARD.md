---
license: apache-2.0
base_model: ibm-esa-geospatial/TerraMind-1.0-base
library_name: peft
pipeline_tag: image-segmentation
tags:
  - earth-observation
  - geospatial
  - sentinel-2
  - sentinel-1
  - lulc
  - land-cover
  - nyc
  - new-york
  - lora
  - peft
  - terramind
  - amd
  - rocm
  - segmentation
---

# TerraMind-NYC-LoRA-LULC

A LoRA adapter that specializes IBM-ESA's TerraMind 1.0 base on a
5-class New York City land-use / land-cover scheme. Trained on AMD
Instinct MI300X via AMD Developer Cloud. Apache 2.0.

This is one of three adapters in the `msradam/TerraMind-NYC-Adapters`
family. The base TerraMind 1.0 weights stay on disk once; this adapter
is a ~5 MB `adapter_model.safetensors` (LoRA Δ on attention projections)
plus a ~320 MB `decoder_head.safetensors` (UNet decoder + segmentation
head, trained from scratch). Together they swap in at inference time
without touching the frozen base.

## Results

Test split: 64 chips, held out with `seed=42`, identical to Phase 2's
full fine-tune for byte-for-byte comparison. Methodology locked in
[`EVAL.md`](https://github.com/msradam/riprap-nyc/blob/main/experiments/18_terramind_nyc_lora/EVAL.md)
before retraining.

| Configuration | Test mIoU | Pixel Acc | F1 macro | Train wall-clock | Adapter on disk |
|---|---:|---:|---:|---:|---:|
| TerraMind base zero-shot | not reported* | — | — | — | — |
| Phase 2 full fine-tune (baseline) | 0.5253 | — | — | ~25 min | ~640 MB |
| **TerraMind-NYC-LoRA-LULC (this work)** | **0.5866** | **0.8910** | **0.6733** | **~5 min** | **~325 MB** |

\* `terramind_v1_base_generate` LULC output uses the ESA WorldCover
ontology, not our 5-class macro collapse, so the zero-shot row is
omitted as not directly comparable. See
[`DATA.md`](https://github.com/msradam/riprap-nyc/blob/main/experiments/18_terramind_nyc_lora/DATA.md)
for our class collapse rules.

**Δ vs Phase 2 full fine-tune: +6.13 pp test/mIoU.** The LoRA adapter
matches and exceeds the full fine-tune at ~half the disk footprint and
~5× faster training. The sample size (64 test chips) means the gap is
not statistically significant on its own, but the same direction holds
on val (LoRA 0.5950 vs full-FT 0.5251) and on training-set diagnostics.

### Per-class IoU on test split

| Class | IoU |
|---|---:|
| 0 — Impervious / urban | 0.9494 |
| 1 — Vegetation | 0.7803 |
| 2 — Water | 0.7696 |
| 3 — Bare / cropland | 0.3892 |
| 4 — Building (LULC scope) | 0.0447 |

Building IoU here is intentionally low because building polygons in
the LULC scheme are a tiny minority of pixels per chip — the dedicated
`buildings_nyc` adapter is the right specialist for building
segmentation. See class collapse rationale in DATA.md.

## How it was trained

| | |
|---|---|
| Hardware | 1× AMD Instinct MI300X (192 GB HBM3) |
| Cloud | AMD Developer Cloud |
| ROCm | 4.0.0+1a5c7ec |
| Framework | TerraTorch 1.2.7 + PyTorch Lightning 2.6.1 + peft 0.18.1 |
| Backbone | `terramind_v1_base` (frozen) |
| Modalities | S2L2A (12 bands) + S1RTC (2 bands) + DEM (1 band), 4 timesteps |
| LoRA target modules | `attn.qkv`, `attn.proj` across 24 transformer blocks |
| LoRA rank `r` | 16 |
| LoRA alpha | 32 |
| LoRA dropout | 0.05 |
| Decoder | `UNetDecoder` (channels [512, 256, 128, 64]) + `LearnedInterpolateToPyramidal` neck |
| Loss | Cross-entropy, equal class weights |
| Optimizer | AdamW two-LR (LoRA params at 5e-4, decoder at 1e-4), wd 1e-4 |
| Scheduler | `ReduceLROnPlateau` (factor 0.5, patience 3) |
| Batch | 8 |
| Epochs | 30 |
| Precision | fp16-mixed |
| Seed | 42 |

LoRA Δ params: 884,736. Decoder + head + neck: 79,895,365.
Frozen TerraMind base: 87,895,562 params.

## How it was evaluated

`shared/eval_adapter.py` from
[github.com/msradam/riprap-nyc](https://github.com/msradam/riprap-nyc/blob/main/experiments/18_terramind_nyc_lora/shared/eval_adapter.py)
loads the base TerraMind, injects the LoRA scaffolding, restores the
adapter + decoder weights, and runs Lightning's `trainer.test` against
the locked test-split file. No augmentation, no TTA, single 224×224
forward.

```bash
python3 shared/eval_adapter.py --adapter adapters/lulc_nyc
# loads adapters/lulc_nyc/output/adapter_model.safetensors +
#       adapters/lulc_nyc/output/decoder_head.safetensors,
# evaluates against the test split listed in config.yaml.
```

## Inference

```python
from peft import LoraConfig, inject_adapter_in_model
from terratorch.tasks import SemanticSegmentationTask
from safetensors.torch import load_file
import torch

# 1. Build the same model topology used at training (see config.yaml).
task = SemanticSegmentationTask(
    model_factory="EncoderDecoderFactory",
    model_args={
        "backbone": "terramind_v1_base",
        "backbone_pretrained": True,
        "backbone_modalities": ["S2L2A", "S1RTC", "DEM"],
        "backbone_use_temporal": True,
        "backbone_temporal_pooling": "concat",
        "backbone_temporal_n_timestamps": 4,
        "necks": [
            {"name": "SelectIndices", "indices": [2, 5, 8, 11]},
            {"name": "ReshapeTokensToImage", "remove_cls_token": False},
            {"name": "LearnedInterpolateToPyramidal"},
        ],
        "decoder": "UNetDecoder",
        "decoder_channels": [512, 256, 128, 64],
        "head_dropout": 0.1,
        "num_classes": 5,
    },
    loss="ce",
    freeze_backbone=False,
    freeze_decoder=False,
    lr=1e-4,
)

# 2. Inject LoRA scaffolding on the encoder.
inject_adapter_in_model(LoraConfig(
    r=16, lora_alpha=32, lora_dropout=0.05,
    target_modules=["attn.qkv", "attn.proj"], bias="none",
), task.model.encoder)

# 3. Load this adapter's weights.
lora = load_file("adapter_model.safetensors")
head = load_file("decoder_head.safetensors")
task.model.encoder.load_state_dict(
    {k.removeprefix("encoder."): v for k, v in lora.items()
     if k.startswith("encoder.")}, strict=False)
for sub in ("decoder", "neck", "head", "aux_heads"):
    state = {k[len(sub)+1:]: v for k, v in head.items()
             if k.startswith(sub + ".")}
    if state and hasattr(task.model, sub):
        getattr(task.model, sub).load_state_dict(state, strict=False)

task.eval().cuda()

# 4. Run inference. Input: dict of [B, C, T, H, W] tensors per modality.
with torch.no_grad():
    out = task.model({
        "S2L2A": s2l2a_chip.cuda(),  # [1, 12, 4, 224, 224]
        "S1RTC": s1rtc_chip.cuda(),  # [1, 2, 4, 224, 224]
        "DEM":   dem_chip.cuda(),    # [1, 1, 4, 224, 224]
    })
preds = out.output.argmax(dim=1)  # [1, 224, 224] long, values in {0..4}
```

For the simpler ensemble interface that loads the base once and swaps
adapters per task, see
[`shared/inference_ensemble.py`](https://github.com/msradam/riprap-nyc/blob/main/experiments/18_terramind_nyc_lora/shared/inference_ensemble.py).

## Out of scope

- Outside NYC bounds (-74.30 to -73.65 lon, 40.45 to 40.95 lat). The
  adapter is a NYC specialist and behavior outside the bbox is
  undefined.
- Land-cover ontologies other than the 5-class collapse defined in
  DATA.md. If you need ESA WorldCover's full 11-class output,
  TerraMind's pretrained `_generate` variant gives you that for free
  without any fine-tune.
- Cloud or shadow-rich scenes. The training distribution filtered S2
  cloud cover ≤ 20%. Adapter behaviour on cloud-saturated chips
  degrades.

## Honest limitations

- 64 test chips is small. Reported test/mIoU 0.5866 has wide implicit
  confidence intervals; a different seed could shift it by a few
  percentage points. We did not run a multi-seed ablation.
- Per-class IoU for class 4 (Building) is 0.0447 — the LULC adapter
  does NOT solve building segmentation; use the dedicated
  `buildings_nyc` adapter for that.
- The +6.13 pp gain over Phase 2 full fine-tune is partly attributable
  to longer training (30 vs 20 epochs) and a higher LR for the from-
  scratch decoder. We measure honestly: same data, same metric, same
  seed, but not identical hyperparameters.

## License

Apache 2.0. ESA Sentinel-2 and Sentinel-1 imagery via Major-TOM Core is
under the Copernicus Open Data License (CC-BY-equivalent, attribution
required). ESA WorldCover 2021 v200 is CC-BY-4.0. Detailed attribution
in
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
