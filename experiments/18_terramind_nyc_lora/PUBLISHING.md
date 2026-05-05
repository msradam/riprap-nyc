# Publishing

Recipe for pushing the adapter family to Hugging Face under
`msradam/TerraMind-NYC-Adapters`. The repo follows the LoRA + base-model
convention used across the PEFT ecosystem.

## Repo layout on Hugging Face

```
msradam/TerraMind-NYC-Adapters/
├── README.md                    Family card (architecture, ADRs, results)
├── lulc_nyc/
│   ├── adapter_config.json      peft config + base_model_id reference
│   ├── adapter_model.safetensors
│   ├── decoder_head.safetensors LoRA does not cover decoder; ship separately
│   ├── splits/test.txt          for reproducibility checks
│   ├── eval/metrics.json        from EVAL.md methodology
│   └── MODEL_CARD.md            per-adapter card (results, limitations)
├── tim_nyc/
│   └── ... (same structure)
└── buildings_nyc/
    └── ... (same structure)
```

The base model `ibm-esa-geospatial/TerraMind-1.0-base` is referenced by ID,
NOT redistributed (per ADR-004).

## What gets published

For each adapter:

1. `adapter_config.json` — peft `LoraConfig` serialization, base model
   reference, target modules, rank/alpha/dropout, our adapter version.
2. `adapter_model.safetensors` — LoRA Δ matrices for qkv and proj across
   24 blocks. ~5 MB float32 / ~2.5 MB float16.
3. `decoder_head.safetensors` — UPerNet (or FCN) weights and segmentation
   head. ~80 MB float32 / ~40 MB float16. Stored as a flat state-dict.
4. `splits/test.txt` — chip IDs of the held-out test set so external
   re-evaluations can match our methodology byte-for-byte.
5. `eval/metrics.json` — output of `shared/eval_adapter.py` against the
   locked test split. Includes mIoU, per-class IoU, F1, pixel-acc, and
   the comparison-baseline rows (zero-shot and full-FT).
6. `MODEL_CARD.md` — Hugging Face standard card structure. Results table
   per the EVAL.md format. Limitations section explicit about scope and
   honesty about test-IoU gaps.

## What does NOT get published

- TerraMind 1.0 base weights. Reference by ID only.
- Training data chips. The Major-TOM source is already on HF; users
  rebuild the dataset from `DATA.md`. We don't redistribute Sentinel-2
  imagery.
- Train/val splits. We commit them to the repo for reproducibility but
  test split is the only one needed for evaluation.

## Tagging and versioning

Each adapter ships with:

- `tags`: `["earth-observation", "geospatial", "sentinel-2", "lora",
  "peft", "nyc", "new-york", "{task}", "terramind", "amd", "rocm",
  "apache-2.0"]`
- `library_name`: `peft`
- `base_model`: `ibm-esa-geospatial/TerraMind-1.0-base`
- `pipeline_tag`: `image-segmentation`

Repo-level git tags use semver: `v0.1.0` for initial 3-adapter release,
minor bumps for new adapters or methodology changes (with EVAL.md change
log entry), patch bumps for typos / documentation only.

## Push command

```bash
python3 shared/publish_hf.py --all
```

This:

1. Validates that each adapter has all required files (adapter_config,
   adapter_model, decoder_head, splits/test.txt, eval/metrics.json,
   MODEL_CARD.md).
2. Checks that the metrics.json was generated against the committed
   test.txt — if a mismatch, refuses to publish.
3. Verifies the LoRA adapter loads cleanly against the referenced base
   (`peft.PeftModel.from_pretrained` smoke test).
4. Pushes to `msradam/TerraMind-NYC-Adapters` with a single git commit
   per adapter so version history is clean.
5. Updates the family-level README.md with the consolidated results
   table.

## Single-adapter push

```bash
python3 shared/publish_hf.py --adapter buildings_nyc
```

For when you've improved one adapter (more data, better hyperparams) and
want to bump just it without re-pushing the others.

## Deprecation pointer on the old repo

After the first successful publish, the existing
`msradam/TerraMind-base-Flood-NYC` repo (3 separate full-fine-tunes) gets
a deprecation notice in its README pointing to this repo:

> ⚠️ This repository contains the original full-fine-tune Phase 2/3/4
> ckpts (~640 MB–2.2 GB each). For the consolidated LoRA-adapter
> family — single base model + tiny per-task adapters, easier to extend
> with new NYC tasks — see
> [msradam/TerraMind-NYC-Adapters](https://huggingface.co/msradam/TerraMind-NYC-Adapters).
> The full-fine-tune ckpts remain available for reproducibility of the
> Phase 2/3/4 experiments.

Old ckpts stay reachable for paper-reproduction purposes; new work
points at the LoRA repo.

## License compliance

Apache-2.0 throughout. The Hugging Face repo's `LICENSE` file is the
Apache-2.0 text. Each MODEL_CARD.md re-states the license and itemizes
the data licenses (CC-BY for ESA Sentinel-2 and ESA WorldCover, public
domain for NYC DOITT building footprints) per the family-level
[`DATA.md`](DATA.md).
