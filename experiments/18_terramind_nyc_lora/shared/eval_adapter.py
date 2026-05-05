"""Evaluate a LoRA adapter against the locked test split.

Single source of truth for publishable test metrics per ../EVAL.md.
Uses Lightning's trainer.test() against the SemanticSegmentationTask
so all the metric plumbing matches what was used during training —
this is required because the task's forward() does pre/post-processing
that a hand-rolled loop diverges from. See dev notes in TRAINING.md.

Writes:
    eval/metrics_{mode}.json — full metrics dict
    eval/test_results.txt    — pretty-printed Lightning summary

Usage:
    python3 shared/eval_adapter.py --adapter adapters/lulc_nyc
    python3 shared/eval_adapter.py --adapter adapters/lulc_nyc --mode full_ft \
        --ckpt-override adapters/lulc_nyc/output/ckpt/last.ckpt

Modes:
    lora      load adapter_model.safetensors + decoder_head.safetensors
    full_ft   load a complete Lightning .ckpt (Phase 2/3/4 baseline)
    zero_shot no fine-tune; freshly built task with pretrained base only
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import lightning.pytorch as pl
import torch
import yaml
from safetensors.torch import load_file

sys.path.insert(0, str(Path(__file__).parent))
from train_lora import build_task, build_datamodule  # noqa: E402


def load_adapter_into_task(task, adapter_dir: Path):
    """Restore LoRA Δ + decoder/neck/head weights into a fresh task.

    Uses state_dict() format (parameters + buffers including BatchNorm
    running stats — those matter for inference accuracy and were the
    cause of an earlier eval failure when omitted).
    """
    lora = load_file(adapter_dir / "adapter_model.safetensors")
    head = load_file(adapter_dir / "decoder_head.safetensors")

    model = task.model

    # Encoder LoRA Δ.
    enc_state = {k.removeprefix("encoder."): v
                 for k, v in lora.items() if k.startswith("encoder.")}
    missing, unexpected = model.encoder.load_state_dict(
        enc_state, strict=False)
    # missing[] is huge (the entire frozen base); we don't print it. We
    # do warn on unexpected, since those mean the saved file has keys
    # the model doesn't recognize.
    if unexpected:
        print(f"WARN: {len(unexpected)} unexpected encoder keys; "
              f"first: {unexpected[:3]}", file=sys.stderr)

    # Decoder / neck / head / aux_heads.
    head_grouped: dict[str, dict] = {}
    for k, v in head.items():
        sub, _, rest = k.partition(".")
        head_grouped.setdefault(sub, {})[rest] = v
    for sub, state in head_grouped.items():
        m = getattr(model, sub, None)
        if m is None:
            continue
        m.load_state_dict(state, strict=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", required=True, type=Path)
    ap.add_argument("--mode", choices=["lora", "full_ft", "zero_shot"],
                    default="lora")
    ap.add_argument("--ckpt-override", type=Path, default=None)
    args = ap.parse_args()

    cfg = yaml.safe_load((args.adapter / "config.yaml").read_text())
    pl.seed_everything(cfg.get("seed", 42), workers=True)

    task = build_task(cfg)
    if args.mode == "lora":
        adapter_dir = args.adapter / "output"
        load_adapter_into_task(task, adapter_dir)
    elif args.mode == "full_ft":
        if not args.ckpt_override:
            raise SystemExit("--mode full_ft requires --ckpt-override")
        ckpt = torch.load(args.ckpt_override, map_location="cpu",
                          weights_only=False)
        task.load_state_dict(ckpt["state_dict"], strict=True)
    # zero_shot: no weight loading; just evaluate the freshly built task.

    dm = build_datamodule(cfg["data"])
    trainer = pl.Trainer(
        accelerator="gpu" if torch.cuda.is_available() else "cpu",
        devices=1,
        precision=cfg.get("precision", "16-mixed"),
        logger=False,
        enable_progress_bar=False,
    )
    results = trainer.test(task, datamodule=dm)
    metrics = results[0] if results else {}
    metrics["mode"] = args.mode
    metrics["task_name"] = cfg.get("task_name", args.adapter.name)
    metrics["num_classes"] = cfg["num_classes"]

    out_dir = args.adapter / "eval"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"metrics_{args.mode}.json").write_text(
        json.dumps(metrics, indent=2))

    # Print summary
    print(f"\n=== {cfg.get('task_name')} :: {args.mode} ===")
    keys = ["test/mIoU", "test/loss", "test/Pixel_Accuracy",
            "test/F1_Score", "test/Boundary_mIoU"]
    for k in keys:
        if k in metrics:
            print(f"  {k:24s} {metrics[k]:.4f}")
    print(f"  per-class IoU:           "
          f"{[f'{metrics.get(f'test/IoU_{i}', float('nan')):.4f}' for i in range(cfg['num_classes'])]}")


if __name__ == "__main__":
    sys.exit(main())
