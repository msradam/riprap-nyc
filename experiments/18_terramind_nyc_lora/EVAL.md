# Evaluation methodology

**Locked 2026-05-05.** Splits, metrics, and reporting format are fixed before
any LoRA adapter is trained. Do not re-define after the fact; if the
methodology needs to change for a future adapter, document the change here
with a dated entry and re-run all prior adapters under the new methodology
before reporting comparable numbers.

## Test splits

Each adapter targets one of three datasets, all built in Phase 2/3/4:

| Adapter | Chip source | Total chips | Train | Val | Test |
|---|---|---|---|---|---|
| `lulc_nyc` | Major-TOM Core-S2L2A+S1RTC+DEM NYC × WorldCover 2021 v200 (5-class collapse) | 336 | 224 | 48 | 64 |
| `tim_nyc` | same as lulc_nyc | 336 | 224 | 48 | 64 |
| `buildings_nyc` | Major-TOM Core-S2L2A+S1RTC+DEM NYC × NYC DOITT building footprints | 208 | 144 | 32 | 32 |

All splits are stratified-random with `seed=42`. The test split file lists
are committed at:

- `adapters/lulc_nyc/splits/test.txt`
- `adapters/tim_nyc/splits/test.txt`  (identical to lulc by construction)
- `adapters/buildings_nyc/splits/test.txt`

Each line is one chip ID (filename without extension). Any reported test
metric must be computed against this exact ID list.

## Metrics

For all adapters:

- **mIoU** — macro-averaged Intersection over Union across classes.
- **Per-class IoU** — explicit, never aggregated away.
- **Pixel accuracy** — overall.
- **F1 (macro)** — macro-averaged F1 across classes.
- **Test loss** — same loss function used at training, on the test split.

For `buildings_nyc` (binary), additionally:

- **Boundary F1** at 1-pixel and 3-pixel tolerance — building polygon
  edges matter for downstream Riprap exposure overlays.

For `lulc_nyc` and `tim_nyc` (5-class), additionally:

- **Confusion matrix** (raw counts and row-normalized) over the test
  split. The 5×5 matrix is dumped to
  `adapters/{name}/eval/confusion_matrix.json`.

## Comparison to baselines

Every adapter MUST be reported alongside two baselines on the same test split:

1. **TerraMind 1.0 base zero-shot.** No fine-tune. For LULC: use
   `terramind_v1_base_generate` LULC output mapped to our 5-class scheme
   via the WorldCover collapse rules in `DATA.md`. For Buildings: there
   is no analogous zero-shot path; report "N/A" with explanation.
2. **Phase 2/3/4 full fine-tune (existing).** Pulled from
   `msradam/TerraMind-base-Flood-NYC`. Same test split. Same eval script.

The MODEL_CARD.md for each adapter MUST contain the three-row table
(zero-shot / full-FT / LoRA). This is the publishable comparison.

## Reporting format

Each adapter's `MODEL_CARD.md` contains a Results section with this exact
table structure:

```markdown
| Configuration | Test mIoU | Pixel Acc | F1 macro | Train wall-clock | Adapter size |
|---|---|---|---|---|---|
| TerraMind base zero-shot | x.xxxx | x.xxxx | x.xxxx | — | — |
| Phase N full fine-tune (baseline) | x.xxxx | x.xxxx | x.xxxx | x min | xxx MB |
| **TerraMind-NYC-LoRA-{task} (this work)** | **x.xxxx** | x.xxxx | x.xxxx | x min | xx MB |
```

Plus per-class IoU and confusion matrix as separate subsections.

## Eval script

`shared/eval_adapter.py` is the single source of truth for computing these
numbers. It:

1. Loads the locked test split file.
2. Loads the base + adapter (or full-FT, or zero-shot, depending on
   `--mode`).
3. Runs forward pass on every test chip with no augmentation, no
   tiled-inference adjustments — single 224×224 forward.
4. Aggregates per-pixel predictions into the metrics above.
5. Writes `adapters/{name}/eval/metrics.json` with all numbers.
6. Updates the MODEL_CARD.md Results table in place.

The script is deterministic (`seed=42`, `torch.use_deterministic_algorithms`
where supported on ROCm). Reruns produce bitwise-identical metrics.json on
the same hardware.

## What we explicitly do NOT do

- Test-time augmentation (TTA). Not standard practice on segmentation
  benchmarks for this class of paper, and inflates apparent mIoU without
  reflecting deployment behaviour.
- Tiled inference at test. Chips are 224×224; native model resolution
  matches.
- Multi-seed averaging. Single seed (42) for budget. We report the
  single-seed number honestly. Where the literature provides std-deviation
  estimates for similar setups, we cite them in the MODEL_CARD.md
  Limitations section.
- Cherry-picked val-best metric. Test metrics come from the
  end-of-training checkpoint after the locked epoch budget defined in each
  adapter's `config.yaml`. We do NOT report val-best-then-eval-on-test
  unless the val-loss is monotone non-increasing (in which case it's
  equivalent).

## Methodology change log

- 2026-05-05: Initial lock. Splits, metrics, baselines, reporting format
  fixed.
