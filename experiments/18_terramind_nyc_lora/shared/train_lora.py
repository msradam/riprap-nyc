"""Train a single LoRA adapter on top of a frozen TerraMind 1.0 base.

One config-driven entry point. The same script trains LULC, TiM, or
Buildings adapters depending on which YAML you point it at. Adding a new
NYC task does not require new Python code, just a new config under
adapters/<task_name>/config.yaml.

Architecture rationale and ADRs are in ../ARCHITECTURE.md. Eval
methodology is locked in ../EVAL.md before any retraining.

Implementation: we build the standard terratorch `SemanticSegmentationTask`
+ `EncoderDecoderFactory` model (same plumbing as the Phase 2/3/4 full
fine-tunes for byte-for-byte comparison validity), then inject a peft
LoRA into the encoder's attention projections post-construction. The
decoder, neck, head, and aux_heads remain fully trainable; the encoder
base is frozen so only LoRA Δ updates.

Usage:
    python3 shared/train_lora.py --config adapters/lulc_nyc/config.yaml
    python3 shared/train_lora.py --config adapters/lulc_nyc/config.yaml --smoke
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import lightning.pytorch as pl
import torch
import torch.nn as nn
import torch.nn.functional as F
import yaml
from lightning.pytorch.callbacks import ModelCheckpoint, EarlyStopping
from lightning.pytorch.loggers import CSVLogger
from peft import LoraConfig, inject_adapter_in_model
from safetensors.torch import save_file

from terratorch.tasks import SemanticSegmentationTask


# ---------------------------------------------------------------------------
# Loss functions
# ---------------------------------------------------------------------------

class FocalTverskyLoss(nn.Module):
    """Focal-Tversky for sparse-positive binary segmentation.

    α weights false-negatives, β weights false-positives, γ focuses on
    hard examples. Default (0.7 / 0.3 / 0.75) is the Sen1Floods11-tuned
    setting from Abraham & Khan (2018) and the masked-Focal-Tversky
    paper for handling class imbalance.
    """

    def __init__(self, alpha: float = 0.7, beta: float = 0.3,
                 gamma: float = 0.75, smooth: float = 1.0):
        super().__init__()
        self.alpha, self.beta, self.gamma, self.smooth = alpha, beta, gamma, smooth

    def forward(self, logits, target):
        prob_pos = F.softmax(logits, dim=1)[:, 1]
        target_pos = (target == 1).float()
        target_neg = (target == 0).float()
        tp = (prob_pos * target_pos).sum(dim=(1, 2))
        fn = ((1 - prob_pos) * target_pos).sum(dim=(1, 2))
        fp = (prob_pos * target_neg).sum(dim=(1, 2))
        tversky = (tp + self.smooth) / (
            tp + self.alpha * fn + self.beta * fp + self.smooth)
        return ((1 - tversky) ** self.gamma).mean()


# ---------------------------------------------------------------------------
# LoRA injection on TerraMind encoder
# ---------------------------------------------------------------------------

def inject_lora_into_encoder(encoder: nn.Module, lora_cfg: dict) -> int:
    """Freeze the encoder, inject LoRA on attention qkv + proj.

    peft.inject_adapter_in_model works on plain nn.Module (TerraMind's
    encoder is not a transformers.PreTrainedModel, so the higher-level
    get_peft_model wouldn't accept it). After injection, only the LoRA Δ
    matrices are trainable; the original encoder weights stay frozen.

    Returns the number of LoRA parameters added.
    """
    for p in encoder.parameters():
        p.requires_grad = False

    config = LoraConfig(
        r=lora_cfg.get("r", 16),
        lora_alpha=lora_cfg.get("alpha", 32),
        lora_dropout=lora_cfg.get("dropout", 0.05),
        target_modules=lora_cfg.get("target_modules", ["qkv", "proj"]),
        bias="none",
    )
    inject_adapter_in_model(config, encoder)

    # peft sets requires_grad=True on lora_A, lora_B; everything else stays frozen.
    n_lora = sum(p.numel() for n, p in encoder.named_parameters()
                 if "lora_" in n and p.requires_grad)
    return n_lora


# ---------------------------------------------------------------------------
# LoRA-aware task subclass
# ---------------------------------------------------------------------------

class TerraMindLoRATask(SemanticSegmentationTask):
    """SemanticSegmentationTask with LoRA injected into the encoder
    after construction.

    Overrides:
      - __init__: post-construction LoRA injection
      - configure_optimizers: two-LR-group optimizer (LoRA params at
        lora_lr, decoder/neck/head at decoder_lr)
      - loss override: optional Focal-Tversky for sparse-positive tasks
    """

    def __init__(self, lora_cfg: dict, lora_lr: float, decoder_lr: float,
                 weight_decay: float, focal_tversky: dict | None = None,
                 **task_kwargs):
        super().__init__(**task_kwargs)
        self._lora_cfg = lora_cfg
        self._lora_lr = lora_lr
        self._decoder_lr = decoder_lr
        self._weight_decay = weight_decay
        self._lora_param_count = inject_lora_into_encoder(
            self.model.encoder, lora_cfg)
        if focal_tversky is not None:
            # Replace the parent's CE-based criterion. SemanticSegmentationTask
            # stores the loss under self.criterion in current terratorch.
            self.criterion = FocalTverskyLoss(**focal_tversky)

    def configure_optimizers(self):
        lora_params, dec_params = [], []
        for n, p in self.named_parameters():
            if not p.requires_grad:
                continue
            (lora_params if "lora_" in n else dec_params).append(p)

        opt = torch.optim.AdamW([
            {"params": lora_params, "lr": self._lora_lr},
            {"params": dec_params,  "lr": self._decoder_lr},
        ], weight_decay=self._weight_decay)
        sched = torch.optim.lr_scheduler.ReduceLROnPlateau(
            opt, mode="min", factor=0.5, patience=3)
        return {"optimizer": opt,
                "lr_scheduler": {"scheduler": sched, "monitor": "val/loss"}}


# ---------------------------------------------------------------------------
# Factory: build TerraMindLoRATask from a YAML config
# ---------------------------------------------------------------------------

def build_task(cfg: dict) -> TerraMindLoRATask:
    backbone_cfg = cfg["backbone"]
    decoder_cfg = cfg["decoder"]

    model_args = {
        "backbone": backbone_cfg["name"],
        "backbone_pretrained": True,
        "backbone_modalities": backbone_cfg.get("modalities", ["S2L2A"]),
        "necks": decoder_cfg.get("necks", [
            {"name": "SelectIndices",
             "indices": decoder_cfg.get("select_indices", [2, 5, 8, 11])},
            {"name": "ReshapeTokensToImage", "remove_cls_token": False},
            {"name": "LearnedInterpolateToPyramidal"},
        ]),
        "decoder": decoder_cfg["name"],
        "decoder_channels": decoder_cfg.get("channels", [512, 256, 128, 64]),
        "head_dropout": decoder_cfg.get("head_dropout", 0.1),
        "num_classes": cfg["num_classes"],
    }
    # Pass through optional backbone flags (temporal, TiM modalities, etc).
    for key in ("use_temporal", "temporal_pooling", "temporal_n_timestamps",
                "backbone_tim_modalities"):
        if key in backbone_cfg:
            backbone_kwarg = (key if key.startswith("backbone_")
                              else f"backbone_{key}")
            model_args[backbone_kwarg] = backbone_cfg[key]

    requested_loss = cfg.get("loss", "ce")
    focal_tversky_cfg = (cfg.get("loss_args")
                         if requested_loss == "focal_tversky" else None)
    # If we're going to override the criterion in the subclass, pass a
    # placeholder loss to the terratorch parent ctor so its init_loss()
    # validation succeeds. The placeholder is replaced before any train
    # step runs.
    parent_loss = "dice" if focal_tversky_cfg else requested_loss

    task_kwargs = {
        "model_factory": "EncoderDecoderFactory",
        "model_args": model_args,
        "loss": parent_loss,
        "ignore_index": cfg.get("ignore_index", -1),
        "class_weights": cfg.get("class_weights"),
        "freeze_backbone": False,   # we control freezing via LoRA injection
        "freeze_decoder": False,
        "lr": cfg.get("decoder_lr", 1e-4),  # parent ctor uses this; we override
    }
    return TerraMindLoRATask(
        lora_cfg=cfg["lora"],
        lora_lr=cfg.get("lora_lr", 5e-4),
        decoder_lr=cfg.get("decoder_lr", 1e-4),
        weight_decay=cfg.get("weight_decay", 1e-4),
        focal_tversky=focal_tversky_cfg,
        **task_kwargs,
    )


# ---------------------------------------------------------------------------
# Adapter-only checkpoint export
# ---------------------------------------------------------------------------

def export_adapter_only(task: TerraMindLoRATask, cfg: dict, out_dir: Path):
    """Save only LoRA Δ + decoder + neck + head to safetensors. The
    frozen TerraMind base is referenced by ID per ADR-004 and never
    redistributed in the published artifact.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    model = task.model

    # Save full state_dict slices (parameters + buffers — BatchNorm
    # running stats matter for inference). LoRA: filter encoder
    # state_dict by the lora_ substring.
    enc_sd = model.encoder.state_dict()
    lora_state = {f"encoder.{n}": v.detach().cpu()
                  for n, v in enc_sd.items() if "lora_" in n}
    head_state = {}
    for sub in ("decoder", "neck", "head", "aux_heads"):
        m = getattr(model, sub, None)
        if m is None:
            continue
        for n, v in m.state_dict().items():
            head_state[f"{sub}.{n}"] = v.detach().cpu()

    save_file(lora_state, out_dir / "adapter_model.safetensors")
    save_file(head_state, out_dir / "decoder_head.safetensors")

    adapter_cfg = {
        "base_model_name_or_path": cfg["backbone"].get(
            "hf_id", "ibm-esa-geospatial/TerraMind-1.0-base"),
        "peft_type": "LORA",
        "r": cfg["lora"].get("r", 16),
        "lora_alpha": cfg["lora"].get("alpha", 32),
        "lora_dropout": cfg["lora"].get("dropout", 0.05),
        "target_modules": cfg["lora"].get("target_modules", ["qkv", "proj"]),
        "bias": "none",
        "task_type": "FEATURE_EXTRACTION",
        "task_name_nyc": cfg.get("task_name", "unknown"),
        "decoder_name": cfg["decoder"]["name"],
        "num_classes": cfg["num_classes"],
        "lora_param_count":   sum(p.numel() for p in lora_state.values()),
        "decoder_param_count": sum(p.numel() for p in head_state.values()),
    }
    (out_dir / "adapter_config.json").write_text(
        json.dumps(adapter_cfg, indent=2))
    return adapter_cfg


# ---------------------------------------------------------------------------
# Datamodule construction
# ---------------------------------------------------------------------------

def _import_class(path: str):
    """Import a class from a 'pkg.mod.ClassName' string."""
    module_path, _, cls_name = path.rpartition(".")
    import importlib
    return getattr(importlib.import_module(module_path), cls_name)


def _resolve_transforms(transform_specs: list) -> list:
    """Convert a list of {class_path, init_args} dicts into objects."""
    resolved = []
    for t in transform_specs:
        cls = _import_class(t["class_path"])
        resolved.append(cls(**t.get("init_args", {})))
    return resolved


def build_datamodule(data_cfg: dict):
    """Build a Lightning DataModule from a Phase 2/3-style config block.

    data_cfg: {module: 'pkg.Class', init_args: {...}}.  Any list value
    under init_args whose elements are class_path dicts is recursively
    resolved into actual transform objects.
    """
    DM = _import_class(data_cfg["module"])
    init_args = dict(data_cfg.get("init_args", {}))
    for k, v in list(init_args.items()):
        if (isinstance(v, list) and v
                and isinstance(v[0], dict) and "class_path" in v[0]):
            init_args[k] = _resolve_transforms(v)
    return DM(**init_args)


# ---------------------------------------------------------------------------
# Smoke probe
# ---------------------------------------------------------------------------

def smoke_probe(task: TerraMindLoRATask):
    print("\n=== Smoke probe ===", flush=True)
    n_total = sum(p.numel() for p in task.parameters())
    n_train = sum(p.numel() for p in task.parameters() if p.requires_grad)
    n_lora = sum(p.numel() for n, p in task.named_parameters()
                 if p.requires_grad and "lora_" in n)
    n_dec = n_train - n_lora
    print(f"  total params:     {n_total:>12,}")
    print(f"  trainable:        {n_train:>12,}  ({100*n_train/n_total:.2f}%)")
    print(f"    LoRA Δ:         {n_lora:>12,}")
    print(f"    decoder/neck/head: {n_dec:>10,}")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    task = task.to(device)

    # Synthetic batch matching task.model.encoder's modality channel counts.
    # TerraMind 1.0 base modality input dims:
    #   S2L2A = 12 bands (B01..B12 incl B8A)
    #   S1RTC = 2 bands (VV, VH)
    #   DEM   = 1 band
    modalities = task.hparams["model_args"]["backbone_modalities"]
    n_chan = {"S2L2A": 12, "S1RTC": 2, "DEM": 1}
    # Temporal mode expects [B, C, T, H, W]; static mode expects [B, C, H, W].
    n_t = task.hparams["model_args"].get("backbone_temporal_n_timestamps")
    if task.hparams["model_args"].get("backbone_use_temporal") and n_t:
        x = {m: torch.randn(2, n_chan.get(m, 1), n_t, 224, 224, device=device)
             for m in modalities}
    else:
        x = {m: torch.randn(2, n_chan.get(m, 1), 224, 224, device=device)
             for m in modalities}
    y = torch.randint(0, task.hparams["model_args"]["num_classes"],
                      (2, 224, 224), device=device)

    out = task.model(x)
    logits = out.output if hasattr(out, "output") else out
    print(f"  forward output:   {tuple(logits.shape)}")

    if hasattr(task, "criterion") and task.criterion is not None:
        loss = task.criterion(logits, y)
    else:
        loss = F.cross_entropy(logits, y)
    loss.backward()
    print(f"  loss (synthetic): {loss.item():.4f}")

    grad_ok = sum(1 for p in task.parameters()
                  if p.requires_grad and p.grad is not None
                  and p.grad.abs().sum() > 0)
    grad_total = sum(1 for p in task.parameters() if p.requires_grad)
    print(f"  params w/ nonzero grad: {grad_ok}/{grad_total}")
    if grad_ok < grad_total * 0.5:
        print("  WARN: <50% of trainable tensors have nonzero grad — "
              "decoder may not be wired into the loss.", file=sys.stderr)
    print("=== Smoke probe OK ===\n", flush=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--devices", type=int, default=1)
    args = ap.parse_args()

    cfg = yaml.safe_load(args.config.read_text())
    pl.seed_everything(cfg.get("seed", 42), workers=True)

    task = build_task(cfg)

    if args.smoke:
        smoke_probe(task)
        return

    # Build the datamodule from the config (ImpactMesh by default).
    # We load albumentations / terratorch transforms via class_path so
    # the YAML stays declarative and matches Phase 2/3/4 verbatim.
    dm = build_datamodule(cfg["data"])

    out_dir = Path(cfg.get("output_dir", args.config.parent / "output"))
    out_dir.mkdir(parents=True, exist_ok=True)

    callbacks = [
        ModelCheckpoint(dirpath=out_dir / "ckpt",
                        filename="best_val_loss",
                        monitor="val/loss", mode="min", save_top_k=1,
                        save_last=True),
        EarlyStopping(monitor="val/loss", mode="min",
                      patience=cfg.get("early_stop_patience", 8)),
    ]
    logger = CSVLogger(save_dir=str(out_dir), name="logs")

    trainer = pl.Trainer(
        max_epochs=cfg.get("max_epochs", 30),
        accelerator="gpu" if torch.cuda.is_available() else "cpu",
        devices=args.devices,
        precision=cfg.get("precision", "16-mixed"),
        logger=logger,
        callbacks=callbacks,
        log_every_n_steps=10,
    )
    trainer.fit(task, datamodule=dm)

    info = export_adapter_only(task, cfg, out_dir)
    print(f"\n=== Adapter exported to {out_dir} ===")
    print(f"  LoRA Δ params:        {info['lora_param_count']:>12,}")
    print(f"  Decoder/neck/head:    {info['decoder_param_count']:>12,}")


if __name__ == "__main__":
    sys.exit(main())
