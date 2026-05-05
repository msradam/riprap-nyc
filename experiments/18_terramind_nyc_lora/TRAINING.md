# Training

How to actually run the LoRA fine-tunes on AMD Instinct MI300X. Reproducible
end-to-end from this document.

## Hardware and software stack

| | |
|---|---|
| GPU | 1× AMD Instinct MI300X (192 GB HBM3) |
| Cloud | AMD Developer Cloud (DigitalOcean droplet) |
| ROCm | 4.0.0+1a5c7ec |
| Container | `rocm:latest` (custom image with TerraTorch installed) |
| Python | 3.12 |
| TerraTorch | 1.2.7 |
| PyTorch Lightning | 2.6.1 |
| peft | 0.18.1 |
| Precision | fp16-mixed |

The droplet has three persistent containers (`terramind`, `ttm`, `rocm`)
spawned from the same `rocm:latest` image. Adapter training runs inside
`terramind`. TTM and other future work get clean siblings to avoid the
transformers/torchvision ABI clashes documented in Phase 14.

## Hyperparameters (defaults shared by all adapters)

These are inherited from each adapter's `config.yaml`; per-adapter
overrides are noted in that file's header comment.

| | |
|---|---|
| Backbone | `terramind_v1_base` (or `terramind_v1_base_tim` for TiM) |
| Backbone weights | Frozen (LoRA only updates Δ) |
| LoRA rank `r` | 16 |
| LoRA `alpha` | 32 |
| LoRA dropout | 0.05 |
| LoRA target modules | `["qkv", "proj"]` (24 attention blocks) |
| Decoder | UPerNet (multiclass) or FCN (binary), trained from scratch |
| Optimizer | AdamW |
| LR (LoRA params) | 5e-4 |
| LR (decoder + head) | 1e-4 |
| Scheduler | ReduceLROnPlateau, factor 0.5, patience 3 |
| Batch size | 8 |
| Epochs | 30 (LULC, TiM) / 40 (Buildings, more class imbalance) |
| Loss — LULC, TiM | Class-weighted cross-entropy (weights = inverse-frequency on train split) |
| Loss — Buildings | Focal-Tversky (α=0.7, β=0.3, γ=0.75) — sparse-positive handling per Sen1Floods11 best practice |
| Random seed | 42 |
| Effective adapter size (per task) | ~5 MB (LoRA Δ) + ~80 MB (UPerNet) ≈ 85 MB float32, ~42 MB float16 |

## Single-task training command

```bash
# Inside the terramind container
cd /workspace/experiments/18_terramind_nyc_lora
python3 shared/train_lora.py --config adapters/lulc_nyc/config.yaml
```

That command produces:

- `adapters/lulc_nyc/output/last.ckpt` — final epoch.
- `adapters/lulc_nyc/output/best_val_loss.ckpt` — best val checkpoint.
- `adapters/lulc_nyc/output/lora_only.safetensors` — adapter-only weights
  (LoRA matrices + decoder + head, base encoder weights NOT included).
- `adapters/lulc_nyc/output/train_log.csv` — per-epoch loss + metrics.

Wall-clock: 25–40 min per adapter on a single MI300X. All three under 2 hr
sequential.

## Eval after training

```bash
python3 shared/eval_adapter.py --adapter adapters/lulc_nyc
```

Writes `adapters/lulc_nyc/eval/metrics.json` and updates the MODEL_CARD.md
Results table (per the locked methodology in [EVAL.md](EVAL.md)).

## Reproduction from scratch

```bash
# 1. Build datasets — these scripts already exist from Phase 2/3/4 and
#    are shared, not re-run for Phase 18.
cd /root
bash /workspace/experiments/05_terramind_nyc_finetune/build_dataset.sh
bash /workspace/experiments/13_terramind_buildings/build_dataset.sh

# 2. Train all three adapters.
cd /workspace/experiments/18_terramind_nyc_lora
for a in lulc_nyc tim_nyc buildings_nyc; do
    python3 shared/train_lora.py --config adapters/$a/config.yaml
done

# 3. Eval all three.
for a in lulc_nyc tim_nyc buildings_nyc; do
    python3 shared/eval_adapter.py --adapter adapters/$a
done

# 4. Publish.
python3 shared/publish_hf.py --all
```

Total wall-clock end-to-end: ~3 hours (30–45 min per adapter × 3,
plus 5 min eval each, plus ~15 min HF push).

## Common issues

### LoRA wrap fails on `peft.get_peft_model`

`peft.get_peft_model` requires a `transformers.PreTrainedModel` or a model
with a `forward` method that accepts the standard input dict. TerraMind's
`encoder` is a plain `nn.Module`. We wrap it manually with `LoraModel`
which requires only `nn.Module` — see `shared/train_lora.py:_apply_lora`
for the exact pattern.

### Decoder gets frozen accidentally

The decoder is a sibling of the encoder under the
`EncoderDecoderFactory`-built model. After LoRA-wrapping the encoder, only
the encoder LoRA params are trainable by default. We explicitly
`.requires_grad_(True)` on `model.decoder` and `model.head` (or
`model.aux_head` if present) — see the same module.

### NaN at fp16-mixed (intermittent)

Phase 1 saw NaN at epoch 10 on full fine-tune. With LoRA the trainable
param count is ~30× smaller and the gradient magnitude is generally
better-conditioned, but if it recurs, drop to `bf16-mixed` (MI300X
supports it) by setting `precision: bf16-mixed` in the config. We have
NOT seen this with LoRA in the smoke-probe phase but document it
preemptively.

### Adapter swap at inference produces wrong outputs

The base encoder must be re-instantiated (or `.merge_and_unload()` reset)
between adapter swaps. `shared/inference_ensemble.py` handles this via
`set_adapter()` on the wrapped encoder; do not bypass it.

## Smoke-probe before each full run

`shared/train_lora.py --config <yaml> --smoke` runs 1 train batch, 1 val
batch, dumps the LoRA-wrapped param count, prints decoder grad-flow
sanity checks, and exits. Always run this first when modifying a config.
~30 seconds on MI300X.
