"""Phase 15: Multi-head TerraMind on NYC.

ONE TerraMind backbone with TWO decoder heads:
  Head A: 5-class WorldCover LULC
  Head B: binary building footprint segmentation

Trained simultaneously with joint loss = α·dice(LULC) + β·dice(Buildings)
on the intersection of Phase 2 (LULC) and Phase 4 (Buildings) datasets.

Result is a SINGLE published checkpoint that produces BOTH outputs in
one forward pass — what Riprap actually needs to call from the FSM.

Datasets reused:
  /root/terramind_nyc/nyc_flood          (Phase 2 LULC labels)
  /root/terramind_nyc/nyc_buildings_flood (Phase 4 building labels)

These share S2/S1/DEM zarr.zip files via symlink (the building rasterizer
symlinked from the LULC dataset). Sub-chip IDs match across both.

Usage on droplet:
    python3 multihead_train.py --epochs 30
"""
from __future__ import annotations

import argparse, json, os, sys, time
from pathlib import Path

import lightning.pytorch as pl
import numpy as np
import rasterio
import torch
import torch.nn as nn
import torch.nn.functional as F
import yaml as yamllib
import zarr
from torch.utils.data import DataLoader, Dataset

import terratorch.models.backbones.terramind.model.terramind_register  # noqa
from terratorch.registry import BACKBONE_REGISTRY


CHIP_PX = 256
N_TIMESTEPS = 4

# ImpactMesh-flood normalization stats (same as Phase 2)
S2_MEAN = np.array([1223.128, 1251.355, 1423.443, 1408.984, 1786.818, 2448.316,
                    2685.642, 2745.795, 2817.936, 3194.081, 1964.659, 1399.317],
                   dtype=np.float32)
S2_STD = np.array([2358.709, 2227.598, 2082.363, 2068.519, 2086.682, 2003.085,
                   2019.494, 2060.309, 2014.732, 2992.644, 1414.951, 1218.357],
                  dtype=np.float32)
S1_MEAN = np.array([-9.98, -15.968], dtype=np.float32)
S1_STD = np.array([4.24, 4.105], dtype=np.float32)


class NYCMultiHeadDataset(Dataset):
    """Yields (S2L2A, S1RTC, DEM, LULC_mask, Buildings_mask) per chip.

    Buildings_mask uses ignore_index -1 for chips not present in the
    buildings dataset (so the buildings head's loss masks them out
    automatically)."""

    def __init__(self, chip_ids, lulc_root: Path, buildings_root: Path):
        self.chip_ids = chip_ids
        self.lulc_root = lulc_root
        self.buildings_root = buildings_root

    def __len__(self):
        return len(self.chip_ids)

    def __getitem__(self, idx):
        cid = self.chip_ids[idx]
        # S2 + S1 from the LULC dataset (Buildings dataset symlinks them)
        s2_path = self.lulc_root / "data" / "S2L2A" / f"{cid}_S2L2A.zarr.zip"
        s1_path = self.lulc_root / "data" / "S1RTC" / f"{cid}_S1RTC.zarr.zip"
        dem_path = self.lulc_root / "data" / "DEM" / f"{cid}_DEM.tif"
        lulc_mask_path = (self.lulc_root / "data" / "MASK" /
                          f"{cid}_annotation_flood.tif")
        bld_mask_path = (self.buildings_root / "data" / "MASK" /
                         f"{cid}_annotation_flood.tif")

        s2 = zarr.open_consolidated(zarr.storage.ZipStore(str(s2_path), mode="r"),
                                     mode="r")["bands"][:]   # (T, 12, H, W)
        s1 = zarr.open_consolidated(zarr.storage.ZipStore(str(s1_path), mode="r"),
                                     mode="r")["bands"][:]   # (T, 2, H, W)
        with rasterio.open(dem_path) as src:
            dem = src.read(1).astype(np.float32)
        with rasterio.open(lulc_mask_path) as src:
            lulc_mask = src.read(1).astype(np.int64)
        if bld_mask_path.exists():
            with rasterio.open(bld_mask_path) as src:
                bld_mask = src.read(1).astype(np.int64)
        else:
            bld_mask = np.full((CHIP_PX, CHIP_PX), -1, dtype=np.int64)

        # Normalize (apply training stats)
        s2 = (s2.astype(np.float32) - S2_MEAN[None, :, None, None]) / \
             S2_STD[None, :, None, None]
        s1 = (s1.astype(np.float32) - S1_MEAN[None, :, None, None]) / \
             S1_STD[None, :, None, None]
        dem = (dem - 141.786) / 189.363

        # Permute to (C, T, H, W) for TerraMind temporal wrapper
        s2_ct = torch.from_numpy(s2).permute(1, 0, 2, 3).float()  # (12, T, H, W)
        s1_ct = torch.from_numpy(s1).permute(1, 0, 2, 3).float()
        dem_ct = torch.from_numpy(dem).unsqueeze(0).unsqueeze(0).repeat(
            1, N_TIMESTEPS, 1, 1).float()  # (1, T, H, W)
        return {
            "S2L2A": s2_ct,
            "S1RTC": s1_ct,
            "DEM": dem_ct,
            "lulc_mask": torch.from_numpy(lulc_mask).long(),
            "bld_mask": torch.from_numpy(bld_mask).long(),
        }


class UNetDecoderHead(nn.Module):
    """Minimal UNet-style decoder, mirrors terratorch's UNetDecoder shape.
    Takes pyramidal features at channel sizes [512, 256, 128, 64] and
    outputs a (B, num_classes, H, W) prediction."""

    def __init__(self, in_channels=[512, 256, 128, 64], num_classes=2):
        super().__init__()
        # Project pyramidal features to common channel; upsample stages
        self.up3 = nn.ConvTranspose2d(in_channels[0], in_channels[1], 2, stride=2)
        self.conv3 = nn.Conv2d(2 * in_channels[1], in_channels[1], 3, padding=1)
        self.up2 = nn.ConvTranspose2d(in_channels[1], in_channels[2], 2, stride=2)
        self.conv2 = nn.Conv2d(2 * in_channels[2], in_channels[2], 3, padding=1)
        self.up1 = nn.ConvTranspose2d(in_channels[2], in_channels[3], 2, stride=2)
        self.conv1 = nn.Conv2d(2 * in_channels[3], in_channels[3], 3, padding=1)
        self.up0 = nn.ConvTranspose2d(in_channels[3], 32, 2, stride=2)
        self.head = nn.Conv2d(32, num_classes, 1)

    def forward(self, feats):
        # feats: list of 4 tensors at decreasing resolution
        f0, f1, f2, f3 = feats   # f3 is deepest (lowest H/W, highest C)
        x = self.up3(f3)
        x = self.conv3(torch.cat([x, f2], dim=1))
        x = F.relu(x)
        x = self.up2(x)
        x = self.conv2(torch.cat([x, f1], dim=1))
        x = F.relu(x)
        x = self.up1(x)
        x = self.conv1(torch.cat([x, f0], dim=1))
        x = F.relu(x)
        x = self.up0(x)
        return self.head(x)


class MultiHeadTerraMind(pl.LightningModule):
    def __init__(self, lr=1e-5, n_lulc=5, n_bld=2,
                 lulc_weight=1.0, bld_weight=1.0):
        super().__init__()
        self.save_hyperparameters()
        self.backbone = BACKBONE_REGISTRY.build(
            "terramind_v1_base",
            modalities=["S2L2A", "S1RTC", "DEM"],
            pretrained=True,
        )
        # Probe the backbone to figure out output channels per stage
        self._head_lulc = None
        self._head_bld = None
        self.n_lulc = n_lulc
        self.n_bld = n_bld

    def _build_heads(self, sample_feats):
        ch = [f.shape[1] for f in sample_feats]
        # Heads are built at first forward (after we see the feat shapes)
        device = sample_feats[0].device
        self._head_lulc = UNetDecoderHead(in_channels=ch[::-1],
                                          num_classes=self.n_lulc).to(device)
        self._head_bld = UNetDecoderHead(in_channels=ch[::-1],
                                         num_classes=self.n_bld).to(device)
        # Register as proper modules so optimizer sees them
        self.head_lulc = self._head_lulc
        self.head_bld = self._head_bld

    def forward(self, batch):
        # Use single-timestep slice (t=0); our chips are stacked-same anyway
        x = {
            "S2L2A": batch["S2L2A"][:, :, 0],   # (B, C, H, W)
            "S1RTC": batch["S1RTC"][:, :, 0],
            "DEM":   batch["DEM"][:, :, 0],
        }
        feats = self.backbone(x)
        # Backbone returns a list of feature maps from each transformer block
        # Pick the same indices as the YAML's SelectIndices: [2, 5, 8, 11]
        if isinstance(feats, (list, tuple)) and len(feats) >= 12:
            feats = [feats[2], feats[5], feats[8], feats[11]]
        # Feats are (B, T*P, C); reshape to (B, C, H, W)
        # SelectIndices output has shape (B, P, embed_dim) per stage where
        # P = (H/16) * (W/16) * T_concat. Reshape to spatial.
        feats_spatial = []
        for f in feats:
            B = f.shape[0]
            if f.ndim == 3:
                # (B, P, C) — assume square spatial layout, ignore CLS token
                P, C = f.shape[1], f.shape[2]
                # Patch grid edge: chip_px / patch_size; default 16 for ViT
                hw = int((P) ** 0.5)
                f = f[:, : hw * hw, :].permute(0, 2, 1).reshape(B, C, hw, hw)
            feats_spatial.append(f)

        # Lazy build heads at first forward
        if self._head_lulc is None:
            self._build_heads(feats_spatial)

        # Upsample feats to a 4-stage pyramid at increasing resolution
        target_size = batch["S2L2A"].shape[-1]  # CHIP_PX
        # Reorder smallest-to-largest if needed; simplest: replicate same feats
        # Actually we have 4 ViT blocks; for U-Net-like decoding we want
        # progressively higher resolution. Simplest: upsample each by 2× more.
        sizes = [target_size // 16, target_size // 8, target_size // 4,
                 target_size // 2]
        py = [F.interpolate(feats_spatial[i], size=(sizes[i], sizes[i]),
                            mode="bilinear", align_corners=False)
              for i in range(4)]

        lulc_logits = self.head_lulc(py)
        bld_logits = self.head_bld(py)
        # Ensure target spatial size
        lulc_logits = F.interpolate(lulc_logits, size=(target_size, target_size),
                                    mode="bilinear", align_corners=False)
        bld_logits = F.interpolate(bld_logits, size=(target_size, target_size),
                                   mode="bilinear", align_corners=False)
        return lulc_logits, bld_logits

    def _losses(self, batch):
        lulc_logits, bld_logits = self(batch)
        loss_lulc = F.cross_entropy(lulc_logits, batch["lulc_mask"],
                                    ignore_index=-1)
        loss_bld = F.cross_entropy(bld_logits, batch["bld_mask"],
                                   ignore_index=-1)
        loss = self.hparams.lulc_weight * loss_lulc + \
               self.hparams.bld_weight * loss_bld
        return loss, loss_lulc, loss_bld, lulc_logits, bld_logits

    def training_step(self, batch, batch_idx):
        loss, lulc_l, bld_l, _, _ = self._losses(batch)
        self.log_dict({"train/loss": loss, "train/lulc_loss": lulc_l,
                       "train/bld_loss": bld_l}, on_step=False, on_epoch=True,
                      prog_bar=True, batch_size=batch["S2L2A"].shape[0])
        return loss

    def validation_step(self, batch, batch_idx):
        loss, lulc_l, bld_l, lulc_logits, bld_logits = self._losses(batch)
        bs = batch["S2L2A"].shape[0]
        # Per-task IoU
        lulc_pred = lulc_logits.argmax(1)
        bld_pred = bld_logits.argmax(1)
        lulc_iou = self._iou(lulc_pred, batch["lulc_mask"], self.n_lulc)
        bld_iou = self._iou(bld_pred, batch["bld_mask"], self.n_bld)
        self.log_dict({
            "val/loss": loss,
            "val/lulc_loss": lulc_l, "val/bld_loss": bld_l,
            "val/lulc_mIoU": lulc_iou, "val/bld_mIoU": bld_iou,
        }, on_step=False, on_epoch=True, prog_bar=True, batch_size=bs)
        return loss

    @staticmethod
    def _iou(pred, target, n_classes):
        ious = []
        for c in range(n_classes):
            valid = target != -1
            tp = ((pred == c) & (target == c) & valid).sum().float()
            fp = ((pred == c) & (target != c) & valid).sum().float()
            fn = ((pred != c) & (target == c) & valid).sum().float()
            denom = tp + fp + fn + 1e-9
            ious.append((tp / denom).item())
        return float(sum(ious) / len(ious))

    def configure_optimizers(self):
        opt = torch.optim.AdamW(self.parameters(), lr=self.hparams.lr)
        sch = torch.optim.lr_scheduler.ReduceLROnPlateau(
            opt, mode="min", factor=0.5, patience=2)
        return {"optimizer": opt, "lr_scheduler": {"scheduler": sch,
                                                    "monitor": "val/loss"}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lulc-root", default="/root/terramind_nyc/nyc_flood")
    ap.add_argument("--bld-root",  default="/root/terramind_nyc/nyc_buildings_flood")
    ap.add_argument("--out", default="/root/terramind_nyc/output_phase15_multihead")
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--lr", type=float, default=1e-5)
    ap.add_argument("--num-workers", type=int, default=2)
    args = ap.parse_args()

    # Discover sub-chip IDs from LULC dataset, partition by Phase 2's split
    lulc_root = Path(args.lulc_root)
    bld_root = Path(args.bld_root)
    splits = {}
    for sp in ["train", "val", "test"]:
        ids = (lulc_root / "split" / f"impactmesh_flood_{sp}.txt").read_text().split()
        splits[sp] = [s.strip() for s in ids if s.strip()]
        print(f"[mh] {sp}: {len(splits[sp])} chips", flush=True)

    train_ds = NYCMultiHeadDataset(splits["train"], lulc_root, bld_root)
    val_ds = NYCMultiHeadDataset(splits["val"], lulc_root, bld_root)

    # Smoke first item
    smoke = train_ds[0]
    print(f"[mh] sample shapes:", flush=True)
    for k, v in smoke.items():
        print(f"  {k}: {tuple(v.shape)} {v.dtype}", flush=True)

    train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True,
                              num_workers=args.num_workers, drop_last=False)
    val_loader = DataLoader(val_ds, batch_size=args.batch, shuffle=False,
                            num_workers=args.num_workers, drop_last=False)

    model = MultiHeadTerraMind(lr=args.lr)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)

    csv_logger = pl.loggers.CSVLogger(save_dir=str(out / "logs"),
                                       name="multihead")
    ckpt_cb = pl.callbacks.ModelCheckpoint(
        monitor="val/loss", mode="min", save_weights_only=True,
        dirpath=str(out / "ckpt"), filename="best_val_loss")
    es_cb = pl.callbacks.EarlyStopping(monitor="val/loss", patience=5)

    trainer = pl.Trainer(
        max_epochs=args.epochs,
        accelerator="auto",
        precision="16-mixed",
        logger=csv_logger,
        callbacks=[ckpt_cb, es_cb],
        log_every_n_steps=5,
        default_root_dir=str(out),
    )
    trainer.fit(model, train_loader, val_loader)
    print(f"[mh] best val_loss: {ckpt_cb.best_model_score}")


if __name__ == "__main__":
    sys.exit(main())
