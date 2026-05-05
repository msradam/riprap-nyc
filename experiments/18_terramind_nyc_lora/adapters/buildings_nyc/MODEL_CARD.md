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
  - building-segmentation
  - building-footprints
  - nyc
  - new-york
  - lora
  - peft
  - terramind
  - amd
  - rocm
  - segmentation
---

# TerraMind-NYC-LoRA-Buildings

A LoRA adapter that specializes IBM-ESA's TerraMind 1.0 base on NYC
building-footprint segmentation, trained against rasterized NYC DOITT
public-domain footprint polygons. Trained on AMD Instinct MI300X via
AMD Developer Cloud. Apache 2.0.

## Results

Test split: 32 chips, held out with `seed=42`, identical to Phase 4's
full fine-tune.

| Configuration | Test mIoU | IoU non-bld | IoU bld | Pixel Acc | F1 macro | Adapter on disk |
|---|---:|---:|---:|---:|---:|---:|
| Phase 4 full fine-tune (baseline) | 0.5324 | — | — | — | — | ~640 MB |
| **TerraMind-NYC-LoRA-Buildings (this work)** | **0.5518** | **0.8107** | **0.2928** | **0.8245** | **0.6742** | **~325 MB** |

**Δ vs Phase 4 full fine-tune: +1.94 pp test/mIoU.**

Building IoU 0.2928 is honestly low in absolute terms — building
segmentation from 10 m Sentinel-2 (with S1RTC + DEM) is a hard task
because most NYC buildings have rooftop spectral signatures very
similar to surrounding impervious surface (asphalt, concrete plazas).
The model learns to find the larger / more thermally distinct
buildings reliably (Class_Accuracy_1 = 0.84, recall) but
over-segments (precision is the constraint). For Riprap's downstream
exposure-overlay use case, recall-biased outputs are the right shape.

## Training history

The first attempt used Focal-Tversky loss on the same architecture and
data; results below for transparency. Retained as `output_v1_focaltversky/`
in the source repo for reproducibility.

| Run | Loss | Test mIoU | Test IoU bld | Train wall-clock |
|---|---|---:|---:|---:|
| v1 archived | Focal-Tversky (α=0.7, β=0.3, γ=0.75) | 0.3462 | 0.1606 | ~7 min |
| **v2 published** | **CE, class weights [0.6, 1.6]** | **0.5518** | **0.2928** | ~7 min |

Why v1 didn't work: with LoRA's frozen-encoder regime, Focal-Tversky's
aggressive false-negative weighting plus a from-scratch decoder
produced an unstable training signal — val/mIoU oscillated between
0.21 and 0.43 across epochs and didn't converge. CE with simple
inverse-frequency class weights was both more stable and more
accurate. The literature suggests Focal-Tversky is the right loss for
sparse-positive *full* fine-tunes (Sen1Floods11 results), but under
LoRA with limited capacity, simpler is better.

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
| Decoder | `UNetDecoder` (channels [512, 256, 128, 64]) |
| Loss | Cross-entropy with class weights [0.6, 1.6] |
| Optimizer | AdamW two-LR (LoRA params at 5e-4, decoder at 1e-4), wd 1e-4 |
| Scheduler | `ReduceLROnPlateau` (factor 0.5, patience 3) |
| Batch | 8 |
| Epochs | 40 |
| Precision | fp16-mixed |
| Seed | 42 |

LoRA Δ params: 884,736. Decoder + head + neck: 79,902,091.

## Inference

```python
# Same loader pattern as the lulc_nyc adapter (see that card's
# snippet) but with num_classes=2 in the model_args. After loading,
# model output's argmax is in {0=non-building, 1=building}.

with torch.no_grad():
    out = task.model({
        "S2L2A": s2l2a_chip.cuda(),  # [1, 12, 4, 224, 224]
        "S1RTC": s1rtc_chip.cuda(),
        "DEM":   dem_chip.cuda(),
    })
building_mask = out.output.argmax(dim=1) == 1
```

For the simpler ensemble interface that swaps adapters at inference,
see
[`shared/inference_ensemble.py`](https://github.com/msradam/riprap-nyc/blob/main/experiments/18_terramind_nyc_lora/shared/inference_ensemble.py).

## Out of scope

- Outside NYC bounds (-74.30 to -73.65 lon, 40.45 to 40.95 lat).
- Building footprint polygons at < 30 m² scale. Sentinel-2 at 10 m and
  the 16-pixel patch embedding mean the model only sees buildings
  larger than approximately one full S2 pixel.
- Building height or 3D extraction. This is a 2D segmentation
  adapter; vertical structure isn't recovered.

## Honest limitations

- 32-chip test split is small; reported test/mIoU 0.5518 has wide
  implicit confidence intervals.
- Building IoU 0.2928 is the honest absolute number. The +1.94 pp
  uplift over Phase 4 full fine-tune is positive but small relative to
  the LULC and TiM adapters in the same family (which gained ~+6 pp
  each); building segmentation from 10 m S2 is fundamentally
  harder than LULC because the spectral separation between buildings
  and surrounding impervious surface is weaker than between, say,
  vegetation and water.
- Recall-biased: model often over-segments around true buildings into
  adjacent impervious surfaces. Useful for Riprap's exposure-overlay
  use case (better to flag a building near floodwater than miss it),
  but consumers should treat outputs as "high-recall building
  candidates" rather than authoritative footprints. For authoritative
  data, use NYC DOITT directly — that's the training-label source.

## License

Apache 2.0. Sentinel-2 / Sentinel-1 imagery via Major-TOM Core under
the Copernicus Open Data License. NYC DOITT building footprints are
public domain via NYC OpenData (`nycopendata/5zhs-2jue`). Detailed
attribution in
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
