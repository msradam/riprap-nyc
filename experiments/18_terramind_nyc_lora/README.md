# TerraMind-NYC-Adapters

A single TerraMind 1.0 base model on disk plus a family of small LoRA adapters
specializing it on New York City Earth-Observation tasks. Built and fine-tuned
on AMD Instinct MI300X via AMD Developer Cloud. Apache 2.0.

> **Why this exists.** Previous Riprap iterations shipped three independent
> full-finetune checkpoints (~640 MB–2.2 GB each) for NYC LULC, TiM, and
> buildings segmentation. Three near-identical encoders sat on disk because
> only the decoder + a small fraction of attention weights actually changed
> per task. This project consolidates them into one shared base + three
> adapters totalling ~30–150 MB. Adding a new NYC task ("heat-island
> exposure", "stormwater impervious surface", "Sandy historical inundation
> recall") becomes a ~10 MB file rather than a 2 GB one.

## Quick links

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — LoRA design, ADRs, why this and not
  multi-head or zero-shot generation.
- [`DATA.md`](DATA.md) — provenance, licensing, chip pipeline.
- [`TRAINING.md`](TRAINING.md) — reproduction, hyperparameters, hardware.
- [`EVAL.md`](EVAL.md) — locked eval methodology and per-adapter test metrics.
- [`PUBLISHING.md`](PUBLISHING.md) — Hugging Face publication recipe.
- [`adapters/_template/`](adapters/_template/) — scaffold for new adapters.

## Repo layout

```
adapters/
  lulc_nyc/          5-class NYC land-use/cover (impervious, vegetation,
                     water, bare, built-up). Macro-collapsed from
                     ESA WorldCover 2021 v200.
  tim_nyc/           Same task, with TerraMind's Thinking-in-Modalities
                     (LULC token generation as auxiliary context).
  buildings_nyc/     Binary segmentation of building footprints from NYC
                     DOITT (1.08 M public-domain polygons).
  _template/         Copy this to start a new adapter.

shared/
  train_lora.py      Single config-driven entry point. Wraps a TerraMind
                     EncoderDecoderFactory model with a peft LoRA on
                     attention qkv + proj projections, trains end-to-end
                     (LoRA + decoder + head), saves an adapter-only ckpt.
  eval_adapter.py    Standardized eval against the locked methodology
                     in EVAL.md. Writes a JSON metrics card + dumps it
                     into the matching adapter's MODEL_CARD.md.
  inference_ensemble.py
                     Loads the base TerraMind once, hot-swaps adapters
                     between task calls. This is what Riprap's FSM nodes
                     consume.
  publish_hf.py      Pushes base reference + adapters + cards to
                     msradam/TerraMind-NYC-Adapters.

scripts/
  add_adapter.sh     Scaffolds a new adapter from _template/.
```

## Adding a new NYC adapter

The whole point of this design. To add a new task:

```bash
# 1. Scaffold
./scripts/add_adapter.sh my_new_task

# 2. Edit adapters/my_new_task/data_spec.yaml — point to your chip dir
#    and label dir, declare class names + collapse rules.

# 3. Edit adapters/my_new_task/config.yaml — set decoder type
#    (UPerNet for multiclass, FCN for binary), num_classes, loss
#    (Focal-Tversky for sparse-positive, CE for balanced multiclass).

# 4. Train
python3 shared/train_lora.py --config adapters/my_new_task/config.yaml

# 5. Evaluate against the locked test split
python3 shared/eval_adapter.py --adapter adapters/my_new_task

# 6. Fill in adapters/my_new_task/MODEL_CARD.md with results,
#    then publish:
python3 shared/publish_hf.py --adapter my_new_task
```

Each of those steps is reproducible from the configs alone — no per-task
Python edits required for standard segmentation tasks. See
[`adapters/_template/README.md`](adapters/_template/README.md) for what
each scaffolded file means.

## Inference

```python
from shared.inference_ensemble import TerraMindNYCEnsemble

ens = TerraMindNYCEnsemble(
    base_id="ibm-esa-geospatial/TerraMind-1.0-base",
    adapter_dir="adapters/",  # or pull from HF
)

# Single S2L2A chip in, dict of task outputs out
result = ens.infer(
    s2l2a=chip_tensor,           # [6, 224, 224]
    tasks=["lulc", "tim", "buildings"],
)
# {"lulc": [5, 224, 224], "tim": [5, 224, 224], "buildings": [2, 224, 224]}
```

## Reproducing from scratch

```bash
# 1. Build datasets (Phase 2/3/4 chip pipeline; see DATA.md)
bash scripts/build_all_datasets.sh

# 2. Train all three adapters sequentially on a single MI300X
python3 shared/train_lora.py --config adapters/lulc_nyc/config.yaml
python3 shared/train_lora.py --config adapters/tim_nyc/config.yaml
python3 shared/train_lora.py --config adapters/buildings_nyc/config.yaml

# 3. Evaluate
python3 shared/eval_adapter.py --adapter adapters/lulc_nyc
python3 shared/eval_adapter.py --adapter adapters/tim_nyc
python3 shared/eval_adapter.py --adapter adapters/buildings_nyc

# 4. Publish
python3 shared/publish_hf.py --all
```

Total wall-clock on 1× MI300X: ~3 hours.

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

## License

Apache 2.0. Underlying datasets and licenses are itemized in
[`DATA.md`](DATA.md).
