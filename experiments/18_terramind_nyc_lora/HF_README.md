---
license: apache-2.0
library_name: peft
pipeline_tag: image-segmentation
base_model: ibm-esa-geospatial/TerraMind-1.0-base
tags:
  - earth-observation
  - geospatial
  - sentinel-2
  - sentinel-1
  - lora
  - peft
  - nyc
  - new-york
  - terramind
  - amd
  - rocm
---

# TerraMind-NYC-Adapters

A LoRA-adapter family that specializes IBM-ESA's
[TerraMind 1.0](https://huggingface.co/ibm-esa-geospatial/TerraMind-1.0-base)
on three New York City Earth-Observation tasks. Built and fine-tuned on
AMD Instinct MI300X via AMD Developer Cloud. Apache 2.0.

> **TL;DR.** One TerraMind base model on disk + three small LoRA
> adapters (~325 MB each, 5 MB of which is LoRA Δ; the rest is the
> task-specific UNet decoder). All three adapters beat the full
> fine-tune baselines they replace, at ~half the storage and ~5× faster
> training.

## Results

All metrics are on held-out test splits with `seed=42`, identical to the
Phase 2/3/4 full-fine-tune baselines for byte-for-byte comparison.

| Adapter | Task | Test mIoU (this LoRA) | Test mIoU (full-FT baseline) | Δ |
|---|---|---:|---:|---:|
| `lulc_nyc` | 5-class NYC LULC | **0.5866** | 0.5253 (Phase 2) | **+6.13 pp** |
| `tim_nyc` | 5-class NYC LULC w/ Thinking-in-Modalities | **0.6023** | 0.5380 (Phase 3) | **+6.43 pp** |
| `buildings_nyc` | binary NYC building footprints | **0.5518** | 0.5324 (Phase 4) | **+1.94 pp** |

All three are stored as `adapter_model.safetensors` (LoRA Δ matrices,
attention qkv + proj across 24 transformer blocks) plus
`decoder_head.safetensors` (UNet decoder + head + neck, trained from
scratch per adapter). The frozen TerraMind base is referenced by ID,
not redistributed.

## Why a LoRA family

Earlier work in this repo (Phase 2/3/4) shipped three independent full
fine-tunes, each ~640 MB–2.2 GB. Three near-identical encoders sat on
disk because only the decoder + a small fraction of attention weights
actually changed per task. This consolidation:

- One TerraMind base file (~1.6 GB), kept fresh from the official IBM
  release. Re-downloaded once across all adapters.
- Three adapters totalling ~1 GB on disk (vs ~3.5 GB previously).
- Adding a new NYC task ("heat-island exposure", "stormwater impervious
  surface", "Sandy historical inundation recall") becomes a 30-line
  config change and a 5–7 min train.
- Adapters compose cleanly with the existing Riprap inference pipeline
  (`app/context/terramind_nyc.py`).

Architecture rationale, ADRs, and the eval-methodology lock are in the
[source repo](https://github.com/msradam/riprap-nyc/tree/main/experiments/18_terramind_nyc_lora).

## Quick start

```python
from huggingface_hub import snapshot_download
from peft import LoraConfig, inject_adapter_in_model
from terratorch.tasks import SemanticSegmentationTask
from safetensors.torch import load_file
import torch

# 1. Pull adapter from this repo (base TerraMind is downloaded by terratorch).
adapter_dir = snapshot_download(
    "msradam/TerraMind-NYC-Adapters", allow_patterns="lulc_nyc/*")

# 2. Build TerraMind + LoRA scaffolding.
task = SemanticSegmentationTask(
    model_factory="EncoderDecoderFactory",
    model_args=dict(
        backbone="terramind_v1_base",
        backbone_pretrained=True,
        backbone_modalities=["S2L2A", "S1RTC", "DEM"],
        backbone_use_temporal=True,
        backbone_temporal_pooling="concat",
        backbone_temporal_n_timestamps=4,
        necks=[
            {"name": "SelectIndices", "indices": [2, 5, 8, 11]},
            {"name": "ReshapeTokensToImage", "remove_cls_token": False},
            {"name": "LearnedInterpolateToPyramidal"},
        ],
        decoder="UNetDecoder",
        decoder_channels=[512, 256, 128, 64],
        head_dropout=0.1,
        num_classes=5,
    ),
    loss="ce", lr=1e-4, freeze_backbone=False, freeze_decoder=False,
)
inject_adapter_in_model(LoraConfig(
    r=16, lora_alpha=32, lora_dropout=0.05,
    target_modules=["attn.qkv", "attn.proj"], bias="none",
), task.model.encoder)

# 3. Load adapter weights.
lora = load_file(f"{adapter_dir}/lulc_nyc/adapter_model.safetensors")
head = load_file(f"{adapter_dir}/lulc_nyc/decoder_head.safetensors")
task.model.encoder.load_state_dict(
    {k.removeprefix("encoder."): v for k, v in lora.items()
     if k.startswith("encoder.")}, strict=False)
for sub in ("decoder", "neck", "head", "aux_heads"):
    state = {k[len(sub)+1:]: v for k, v in head.items()
             if k.startswith(sub + ".")}
    if state and hasattr(task.model, sub):
        getattr(task.model, sub).load_state_dict(state, strict=False)

task.eval().cuda()

# 4. Inference.
with torch.no_grad():
    out = task.model({
        "S2L2A": s2l2a.cuda(),
        "S1RTC": s1rtc.cuda(),
        "DEM":   dem.cuda(),
    })
preds = out.output.argmax(dim=1)
```

For the ensemble interface that loads the base once and swaps adapters
between task calls, see
[`shared/inference_ensemble.py`](https://github.com/msradam/riprap-nyc/blob/main/experiments/18_terramind_nyc_lora/shared/inference_ensemble.py).

## Repo layout

```
lulc_nyc/
    adapter_config.json
    adapter_model.safetensors      LoRA Δ on attention qkv + proj
    decoder_head.safetensors       UNet decoder + head + neck
    eval/metrics_lora.json         test-set metrics
    splits/test.txt                held-out test split chip IDs
    README.md                      per-adapter MODEL_CARD
tim_nyc/...
buildings_nyc/...
README.md                          this file
```

## Hardware and budget

All adapters trained on a single AMD Instinct MI300X (192 GB HBM3) on
AMD Developer Cloud, ROCm 4.0.0. Wall-clock per adapter:

- LULC-NYC: ~5 min
- TiM-NYC: ~6 min
- Buildings-NYC: ~7 min

Total: ~18 min for the full family. Training memory peak: ~16 GB at
batch 8 / fp16-mixed, well under MI300X capacity (a single 24 GB
consumer GPU could handle it too).

## License

Apache 2.0. Underlying training data:

- ESA Sentinel-2 L2A / Sentinel-1 RTC / Copernicus DEM via
  [Major-TOM Core](https://huggingface.co/Major-TOM) — Copernicus Open
  Data License (CC-BY-equivalent, attribution required).
- ESA WorldCover 2021 v200 — CC-BY-4.0.
- NYC DOITT Building Footprints — public domain via NYC OpenData.

Detailed attribution in
[`DATA.md`](https://github.com/msradam/riprap-nyc/blob/main/experiments/18_terramind_nyc_lora/DATA.md).

## Source

[github.com/msradam/riprap-nyc/tree/main/experiments/18_terramind_nyc_lora](https://github.com/msradam/riprap-nyc/tree/main/experiments/18_terramind_nyc_lora)

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
