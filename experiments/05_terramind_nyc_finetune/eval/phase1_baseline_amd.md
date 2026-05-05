# Phase 1 baseline — IBM `TerraMind-base-Flood` checkpoint on AMD MI300X

**Run on:** 2026-05-03 22:14 UTC
**Hardware:** AMD Instinct MI300X via AMD Developer Cloud (ROCm)
**Stack:** terratorch 1.2.7, PyTorch (ROCm), Python 3.12, fp16-mixed
**Data:** ImpactMesh-Flood official test split (14,556 chips, 256×256, 4 timesteps)
**Checkpoint:** `ibm-esa-geospatial/TerraMind-base-Flood`
  (`TerraMind_v1_base_ImpactMesh_flood.pt`, 643 MB)
**Config:** `training/terramind_v1_base_impactmesh_flood_amd.yaml`
  (verbatim from IBM, only logger + paths adapted)

## Result table

| Metric | Value |
|---|---|
| **test/mIoU** | **0.6663** |
| test/mIoU_Micro | 0.9064 |
| test/Boundary_mIoU | 0.1212 |
| test/IoU_0 (non-water) | 0.9494 |
| test/IoU_1 (water) | 0.3832 |
| test/Class_Accuracy_0 | 0.9774 |
| test/Class_Accuracy_1 | 0.5236 |
| test/Pixel_Accuracy | 0.9509 |
| test/Accuracy | 0.7505 |
| test/F1_Score | 0.7641 |
| test/loss (dice) | 0.2721 |

## Throughput

- Wall-clock: **2 min 2 s** (incl. model load).
- Tiled inference: 910 batches × 16 chips at 7.30 it/s.
- GPU utilization: ~50% (CPU-bound on zarr decompress).

## Interpretation

This is the **AMD-side reproduction target**. When we fine-tune
`terramind_v1_base` (raw foundation backbone) on the ImpactMesh-Flood
training split on the same MI300X with the same YAML, the resulting
`TerraMind-base-Flood-AMD` checkpoint should match these numbers within
±2pp on `test/mIoU`. That demonstrates "we can fine-tune TerraMind on
AMD with parity to IBM's NVIDIA-trained published checkpoint."

The water-class IoU (0.383) is the difficult metric — water is a
minority class. The class-weighted dice loss (0.342, 1.316) is
calibrated for this. We expect our fine-tune to land in the
0.36–0.40 range for IoU_1.

## What this also proves

- TerraTorch + ROCm path is fully functional. End-to-end Lightning
  flow (config load → backbone load → tiled inference → metric
  reporting) works on MI300X without modification.
- ImpactMesh-Flood data pipeline (zarr.zip multi-temporal, 4 timesteps,
  S2L2A + S1RTC + DEM) loads correctly via `ImpactMeshDataModule`.
- fp16-mixed AMP works on ROCm for this model size.

## Training-loop smoke (50 batches, gradients verified)

Before kicking off the full run, a 50-train-batch / 5-val-batch smoke
through the same recipe confirmed:

- Forward + backward + AdamW step on the **167 M trainable parameters**
  (TerraMind `v1_base` encoder + UNet decoder with channels
  [512, 256, 128, 64], temporal wrapper at 4 timesteps, 3 modalities).
- **4.69 it/s on the fine-tune loop** at batch 16 (vs 7.30 it/s on the
  test-time tiled inference — the ~36% gap is the backward + optimizer
  step, well within expectations).
- 50 batches in 36 s, no OOM, no NaN gradients, no AMP scaler issues
  on ROCm fp16-mixed.
- Process exited cleanly (`max_epochs=1` reached).

**Throughput projection for full run:**
57,067 train chips / batch 16 = 3,567 steps/epoch at 4.69 it/s
≈ 12.7 min/epoch. 50 epochs = ~10.6 GPU-hours. With EarlyStopping
patience 10, realistic runtime is 4–7 GPU-hours.

## Phase-1 full fine-tune (in flight)

Launched 2026-05-03 22:20:26 UTC, PID 2125 inside `terramind` container.
Initial trajectory at step ~430 (epoch 0, ~12% through first epoch):

| Step | train/loss |
|---|---|
| 414 | 0.468 |
| 424 | 0.234 |
| 434 | 0.403 |

Loss is descending into the 0.2–0.5 band on noisy short windows —
expected for early steps on a class-imbalanced dice loss with
class-weights (0.342, 1.316).

GPU utilization: **92 % on MI300X**, VRAM ~15 % allocated (~30 GB of
192 GB available). Stable.

CSV metrics → `/root/terramind_nyc/output/terramind_base_impactmesh_flood/logs/amd_repro_lr1e-4/version_0/metrics.csv`
Best-checkpoint → `/root/terramind_nyc/output/terramind_base_impactmesh_flood/ckpt/best_val_loss.ckpt` (written on first val improvement).

## Reproduction command

```bash
# Inside the terramind container on the MI300X droplet:
docker exec terramind bash -c "
  terratorch test \
    --config /root/config_amd.yaml \
    --ckpt_path /root/.cache/huggingface/TerraMind-base-Flood/TerraMind_v1_base_ImpactMesh_flood.pt
"
```
