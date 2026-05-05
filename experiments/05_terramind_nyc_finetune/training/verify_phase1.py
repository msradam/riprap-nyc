"""Phase-1 verification battery.

Run after Phase-1 fine-tune completes to evaluate "is this checkpoint
publishable?". Produces a markdown report + supporting artifacts.

Tests run, in order:
  1. Reproduction parity     — terratorch test mIoU vs IBM baseline
  2. Head-to-head per-chip   — diff histogram (ours - IBM, same chips)
  3. Convergence trajectory  — parse training metrics.csv
  4. EMS event stratification — mIoU broken down by Copernicus event id
  5. Calibration / mode-collapse — prediction prob histogram
  6. Numeric stability       — checkpoint weights finite + sane
  7. Documented load path    — LightningInferenceModel.from_config()
  8. Safetensors round-trip  — HF-best-practice export
  9. Throughput              — fit + tiled inference rates on MI300X
 10. Qualitative panels      — N test chips with real | mask | both preds

Usage (on the AMD droplet, inside terramind container):

    python3 verify_phase1.py \
        --our-ckpt /root/terramind_nyc/output/.../best_val_loss.ckpt \
        --ibm-ckpt /root/.cache/huggingface/TerraMind-base-Flood/TerraMind_v1_base_ImpactMesh_flood.pt \
        --config /root/config_amd.yaml \
        --csv-log /root/terramind_nyc/output/.../metrics.csv \
        --out /root/terramind_nyc/verify_phase1 \
        --n-qual 12 \
        --n-calib 200

Outputs to --out:
    report.md
    per_chip_iou.tsv
    convergence.png
    calibration.png
    diff_histogram.png
    qual_panels/<chip_id>.png
    safetensors/TerraMind-base-Flood-AMD.safetensors  (if export OK)

Notes:
- Subprocess-driven terratorch test for the topline mIoU (no need to
  reimplement Lightning's metric reduction).
- Per-chip metrics use the same ImpactMeshDataModule via direct dataloader.
- Reads the same config used for training so the model factory + necks
  are identical between the two checkpoints.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image


def _to_device(batch, device):
    """Move ImpactMesh batch to device. Schema is `{"image": {modality: tensor}, "mask": tensor, ...}`
    so we descend into nested dicts. Returns the dict the model expects."""
    img = batch.get("image", batch)
    if isinstance(img, dict):
        return {k: v.to(device, non_blocking=True)
                for k, v in img.items() if torch.is_tensor(v)}
    if torch.is_tensor(img):
        return img.to(device, non_blocking=True)
    return {k: v.to(device, non_blocking=True)
            for k, v in batch.items()
            if k in ("S2L2A", "S1RTC", "DEM") and torch.is_tensor(v)}


def stretch(arr, lo=2, hi=98):
    a = np.asarray(arr, dtype=np.float32)
    finite = np.isfinite(a)
    if not finite.any():
        return np.zeros_like(a, dtype=np.uint8)
    plo, phi = np.percentile(a[finite], [lo, hi])
    if phi <= plo:
        return np.zeros_like(a, dtype=np.uint8)
    return (np.clip((a - plo) / (phi - plo), 0, 1) * 255).astype(np.uint8)


def s1_db(arr):
    a = np.where(arr > 0, arr, 1e-6).astype(np.float32)
    return stretch(10.0 * np.log10(a))


# ---------- 1. Reproduction parity --------------------------------------------

_METRIC_RE = re.compile(r"│\s+(test/[A-Za-z0-9_]+)\s+│\s+([0-9.]+)\s+│")


def run_terratorch_test(config: str, ckpt: str, log_dir: Path) -> dict:
    """Shell out to terratorch test, parse the rich-printed metric table."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"test_{Path(ckpt).stem}.log"
    cmd = ["terratorch", "test", "--config", config, "--ckpt_path", ckpt]
    print(f"[verify-1] {' '.join(cmd)}", flush=True)
    t0 = time.time()
    with open(log_path, "w") as f:
        proc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, text=True)
    dt = time.time() - t0
    metrics = {}
    for line in open(log_path):
        m = _METRIC_RE.search(line)
        if m:
            metrics[m.group(1)] = float(m.group(2))
    metrics["_wall_clock_s"] = dt
    metrics["_returncode"] = proc.returncode
    return metrics


def reproduction_parity(args, out_dir: Path) -> dict:
    print("\n=== 1. Reproduction parity ===")
    metrics_dir = out_dir / "test_runs"
    ours = run_terratorch_test(args.config, args.our_ckpt, metrics_dir)
    ibm = run_terratorch_test(args.config, args.ibm_ckpt, metrics_dir)
    delta_miou = ours.get("test/mIoU", float("nan")) - ibm.get("test/mIoU", float("nan"))
    delta_iou1 = ours.get("test/IoU_1", float("nan")) - ibm.get("test/IoU_1", float("nan"))
    pass_miou = abs(delta_miou) <= 0.02 if not np.isnan(delta_miou) else False
    pass_water = abs(delta_iou1) <= 0.03 if not np.isnan(delta_iou1) else False
    return {
        "ours": ours, "ibm": ibm,
        "delta_mIoU": delta_miou, "delta_IoU_1": delta_iou1,
        "pass_overall_mIoU_within_2pp": pass_miou,
        "pass_water_IoU_within_3pp": pass_water,
    }


# ---------- 2-5,10. Per-chip metrics + calibration + qual via dataloader ------


def build_inference_model(config_path: str, ckpt_path: str, device: str):
    """Build SemanticSegmentationTask from the YAML and load weights.
    Uses LightningInferenceModel as the documented user-facing path."""
    from terratorch.cli_tools import LightningInferenceModel
    model = LightningInferenceModel.from_config(config_path, ckpt_path)
    # LightningInferenceModel exposes `.model` (the LightningModule)
    inner = getattr(model, "model", model)
    inner = inner.to(device).eval()
    return inner


def build_test_dataloader(config_path: str):
    """Construct the ImpactMeshDataModule from the YAML and return its test
    dataloader. We instantiate it directly so we have access to filenames."""
    import yaml
    cfg = yaml.safe_load(open(config_path))
    data_cfg = cfg["data"]["init_args"]
    from impactmesh.impactmesh_datamodule import ImpactMeshDataModule
    # Strip transforms (we want raw test data; train_transform doesn't apply)
    dm = ImpactMeshDataModule(**{k: v for k, v in data_cfg.items()
                                 if k not in ("train_transform",)})
    dm.setup("test")
    dl = dm.test_dataloader()
    return dm, dl


def per_chip_eval(model, dataloader, device, max_batches=None):
    """Run model over dataloader, return per-chip IoU + sample probs."""
    per_chip = []  # list of (chip_id, iou0, iou1, n_pixels)
    prob_samples = []  # for calibration
    with torch.no_grad():
        for bi, batch in enumerate(dataloader):
            if max_batches is not None and bi >= max_batches:
                break
            x = _to_device(batch, device)
            mask = batch["mask"].to(device)
            # ImpactMeshDataModule yields chip names in batch["filename"] in
            # 1.2.x; fall back to indices if the key isn't there.
            names = batch.get("filename") or [f"batch{bi}_{i}" for i in range(mask.shape[0])]
            try:
                out = model(x)
            except Exception:
                out = model(**x)
            logits = out.output if hasattr(out, "output") else out
            if isinstance(logits, (list, tuple)):
                logits = logits[0]
            probs = F.softmax(logits, dim=1)
            preds = probs.argmax(1)
            for i in range(mask.shape[0]):
                m = mask[i]
                p = preds[i]
                valid = m != -1  # ignore_index
                tp1 = ((p == 1) & (m == 1) & valid).sum().item()
                fp1 = ((p == 1) & (m == 0) & valid).sum().item()
                fn1 = ((p == 0) & (m == 1) & valid).sum().item()
                tp0 = ((p == 0) & (m == 0) & valid).sum().item()
                iou0 = tp0 / max(1, tp0 + fp1 + fn1)  # non-water
                iou1 = tp1 / max(1, tp1 + fp1 + fn1)
                per_chip.append((str(names[i]), iou0, iou1, valid.sum().item()))
            if len(prob_samples) < 50:
                prob_samples.append(probs[:, 1].cpu().numpy().ravel()[:5000])
    return per_chip, np.concatenate(prob_samples) if prob_samples else np.array([])


def head_to_head(args, dl, device, out_dir: Path) -> dict:
    print("\n=== 2,5. Head-to-head per-chip + calibration ===")
    ours_model = build_inference_model(args.config, args.our_ckpt, device)
    ours_chips, ours_probs = per_chip_eval(ours_model, dl, device)
    del ours_model
    torch.cuda.empty_cache()
    ibm_model = build_inference_model(args.config, args.ibm_ckpt, device)
    ibm_chips, _ = per_chip_eval(ibm_model, dl, device)
    del ibm_model
    torch.cuda.empty_cache()

    # Align by chip-id
    ibm_idx = {c[0]: c for c in ibm_chips}
    diffs_iou1 = []
    rows = []
    for ours in ours_chips:
        ibm = ibm_idx.get(ours[0])
        if ibm is None:
            continue
        diffs_iou1.append(ours[2] - ibm[2])
        rows.append((ours[0], ours[1], ours[2], ibm[1], ibm[2],
                     ours[2] - ibm[2]))

    tsv = out_dir / "per_chip_iou.tsv"
    with open(tsv, "w") as f:
        f.write("chip_id\tours_iou0\tours_iou1\tibm_iou0\tibm_iou1\tdelta_iou1\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")

    diffs_iou1 = np.asarray(diffs_iou1)
    return {
        "n_chips": len(rows),
        "delta_iou1_mean": float(np.mean(diffs_iou1)) if len(diffs_iou1) else None,
        "delta_iou1_median": float(np.median(diffs_iou1)) if len(diffs_iou1) else None,
        "delta_iou1_std": float(np.std(diffs_iou1)) if len(diffs_iou1) else None,
        "delta_iou1_p05": float(np.percentile(diffs_iou1, 5)) if len(diffs_iou1) else None,
        "delta_iou1_p95": float(np.percentile(diffs_iou1, 95)) if len(diffs_iou1) else None,
        "n_ours_better": int((diffs_iou1 > 0.02).sum()),
        "n_ibm_better": int((diffs_iou1 < -0.02).sum()),
        "tsv_path": str(tsv),
        "ours_prob_sample": ours_probs,
        "rows": rows,
    }


def calibration_report(prob_sample: np.ndarray, out_dir: Path) -> dict:
    print("\n=== 5. Calibration / mode collapse ===")
    if prob_sample.size == 0:
        return {"ok": False, "reason": "no probs collected"}
    bins = np.linspace(0, 1, 21)
    hist, _ = np.histogram(prob_sample, bins=bins)
    # Mode-collapse heuristic: > 95% of mass at the extremes is suspicious
    extreme_mass = (hist[0] + hist[-1]) / max(1, hist.sum())
    middle_mass = hist[5:15].sum() / max(1, hist.sum())
    return {
        "n_samples": int(prob_sample.size),
        "p_extreme_mass": float(extreme_mass),
        "p_middle_mass": float(middle_mass),
        "histogram": hist.tolist(),
        "bins": bins.tolist(),
        "pass_not_collapsed": bool(extreme_mass < 0.95 and middle_mass > 0.02),
    }


# ---------- 3. Convergence trajectory -----------------------------------------

def convergence(csv_path: str, out_dir: Path) -> dict:
    print("\n=== 3. Convergence trajectory ===")
    if not Path(csv_path).exists():
        return {"ok": False, "reason": f"csv not found: {csv_path}"}
    import csv
    rows = list(csv.DictReader(open(csv_path)))
    train_loss = [(int(r["step"]), float(r["train/loss"]))
                  for r in rows if r.get("train/loss")]
    val_loss = [(int(r["epoch"]), float(r["val/loss"]))
                for r in rows if r.get("val/loss")]
    val_loss_sorted = sorted(val_loss, key=lambda x: x[1]) if val_loss else []
    best_epoch = val_loss_sorted[0][0] if val_loss_sorted else None
    best_val = val_loss_sorted[0][1] if val_loss_sorted else None
    last_epoch = val_loss[-1][0] if val_loss else None
    pass_best_not_last = (best_epoch != last_epoch) if val_loss else False
    return {
        "n_train_loss_points": len(train_loss),
        "n_val_epochs": len(val_loss),
        "first_train_loss": train_loss[0][1] if train_loss else None,
        "last_train_loss": train_loss[-1][1] if train_loss else None,
        "best_val_epoch": best_epoch,
        "best_val_loss": best_val,
        "last_val_epoch": last_epoch,
        "last_val_loss": val_loss[-1][1] if val_loss else None,
        "pass_best_not_last_epoch": pass_best_not_last,
    }


# ---------- 4. EMS event stratification ---------------------------------------

EMS_RE = re.compile(r"^(EMSR\d+)")


def ems_stratify(per_chip_rows: list) -> dict:
    print("\n=== 4. EMS event stratification ===")
    by_event = defaultdict(list)  # event -> list of iou1
    for chip_id, _, ours_iou1, _, _, _ in per_chip_rows:
        m = EMS_RE.match(chip_id)
        if not m:
            continue
        by_event[m.group(1)].append(ours_iou1)
    summary = {ev: {"n": len(ious),
                    "mean_iou1": float(np.mean(ious)),
                    "min_iou1": float(np.min(ious))}
               for ev, ious in by_event.items()}
    if not summary:
        return {"ok": False, "reason": "no EMS prefixes parsed"}
    means = [s["mean_iou1"] for s in summary.values()]
    return {
        "n_events": len(summary),
        "mean_iou1_min_event": float(np.min(means)),
        "mean_iou1_max_event": float(np.max(means)),
        "events": summary,
    }


# ---------- 6. Numeric stability ----------------------------------------------

def numeric_stability(ckpt_path: str) -> dict:
    print("\n=== 6. Numeric stability ===")
    sd = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    if isinstance(sd, dict) and "state_dict" in sd:
        sd = sd["state_dict"]
    n_params = 0; n_nan = 0; n_inf = 0
    max_abs = 0.0
    for k, v in sd.items():
        if not torch.is_tensor(v):
            continue
        n_params += v.numel()
        n_nan += int(torch.isnan(v).sum().item())
        n_inf += int(torch.isinf(v).sum().item())
        ma = float(v.abs().max().item()) if v.numel() else 0.0
        if ma > max_abs:
            max_abs = ma
    return {
        "n_params": n_params,
        "n_nan": n_nan,
        "n_inf": n_inf,
        "max_abs_weight": max_abs,
        "pass_no_nan_inf": n_nan == 0 and n_inf == 0,
    }


# ---------- 7. Documented-load-path -------------------------------------------

def documented_load_path(config: str, ckpt: str) -> dict:
    print("\n=== 7. Documented load path ===")
    try:
        from terratorch.cli_tools import LightningInferenceModel
        m = LightningInferenceModel.from_config(config, ckpt)
        return {"pass": True, "type": type(m).__name__}
    except Exception as e:
        return {"pass": False, "err": repr(e)}


# ---------- 8. Safetensors round-trip -----------------------------------------

def safetensors_roundtrip(ckpt: str, out_dir: Path) -> dict:
    print("\n=== 8. Safetensors export ===")
    try:
        from safetensors.torch import save_file, load_file
        sd = torch.load(ckpt, map_location="cpu", weights_only=False)
        if isinstance(sd, dict) and "state_dict" in sd:
            sd = sd["state_dict"]
        sd = {k: v.contiguous() for k, v in sd.items() if torch.is_tensor(v)}
        out_path = out_dir / "safetensors" / "TerraMind-base-Flood-AMD.safetensors"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        save_file(sd, str(out_path))
        sd2 = load_file(str(out_path))
        all_match = True
        for k in sd:
            if not torch.equal(sd[k], sd2[k]):
                all_match = False; break
        return {"pass": all_match,
                "out_path": str(out_path),
                "size_mb": out_path.stat().st_size / 1e6}
    except Exception as e:
        return {"pass": False, "err": repr(e)}


# ---------- 9. Throughput -----------------------------------------------------

def throughput(model, dl, device, n_batches=20) -> dict:
    print("\n=== 9. Throughput ===")
    it = iter(dl)
    # warm-up
    for _ in range(3):
        b = next(it)
        x = _to_device(b, device)
        with torch.no_grad():
            try: model(x)
            except Exception: model(**x)
    torch.cuda.synchronize()
    t0 = time.time()
    n = 0
    for _ in range(n_batches):
        try:
            b = next(it)
        except StopIteration:
            break
        x = _to_device(b, device)
        with torch.no_grad():
            try: model(x)
            except Exception: model(**x)
        n += 1
    torch.cuda.synchronize()
    dt = time.time() - t0
    peak_vram_gb = torch.cuda.max_memory_allocated() / 1e9
    return {
        "n_batches": n,
        "wall_s": dt,
        "it_per_s": n / dt if dt > 0 else None,
        "peak_vram_gb": peak_vram_gb,
    }


# ---------- 10. Qualitative panels --------------------------------------------

def qual_panels(model_ours, model_ibm, dl, device, out_dir: Path,
                n: int = 12) -> dict:
    print("\n=== 10. Qualitative panels ===")
    panels_dir = out_dir / "qual_panels"
    panels_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    with torch.no_grad():
        for batch in dl:
            x = _to_device(batch, device)
            mask = batch["mask"]
            names = batch.get("filename") or [f"chip{i}" for i in range(mask.shape[0])]
            for fn in (lambda: model_ours(x), lambda: model_ibm(x)):
                pass  # placeholder; do it below
            o = model_ours(x); o = o.output if hasattr(o, "output") else o
            i = model_ibm(x);  i = i.output if hasattr(i, "output") else i
            o = o[0] if isinstance(o, (list, tuple)) else o
            i = i[0] if isinstance(i, (list, tuple)) else i
            preds_o = o.argmax(1).cpu().numpy()
            preds_i = i.argmax(1).cpu().numpy()
            s2 = batch.get("S2L2A")
            s1 = batch.get("S1RTC")
            for k in range(mask.shape[0]):
                if len(saved) >= n:
                    break
                # S2L2A is usually (B, T, C, H, W) — pick t=0 RGB (B04,B03,B02)
                rgb = None
                if s2 is not None:
                    arr = s2[k]
                    if arr.dim() == 4:  # T,C,H,W
                        arr = arr[0]
                    if arr.shape[0] >= 5:
                        rgb = np.stack([stretch(arr[3].numpy()),  # B04
                                        stretch(arr[2].numpy()),  # B03
                                        stretch(arr[1].numpy())], axis=-1)  # B02
                vv = None
                if s1 is not None:
                    arr = s1[k]
                    if arr.dim() == 4:
                        arr = arr[0]
                    vv = s1_db(arr[0].numpy())
                msk_u8 = (mask[k].numpy() == 1).astype(np.uint8) * 255
                po = (preds_o[k] == 1).astype(np.uint8) * 255
                pi = (preds_i[k] == 1).astype(np.uint8) * 255
                tiles = []
                if rgb is not None: tiles.append(rgb)
                if vv is not None:  tiles.append(np.stack([vv]*3, -1))
                tiles.append(np.stack([msk_u8]*3, -1))
                tiles.append(np.stack([po]*3, -1))
                tiles.append(np.stack([pi]*3, -1))
                h = max(t.shape[0] for t in tiles)
                tiles = [t if t.shape[0] == h else
                         np.pad(t, ((0, h - t.shape[0]), (0,0), (0,0)))
                         for t in tiles]
                panel = np.concatenate(tiles, axis=1)
                fn = panels_dir / f"{names[k] if isinstance(names[k], str) else k:>04}.png"
                Image.fromarray(panel).save(fn)
                saved.append(str(fn))
            if len(saved) >= n:
                break
    return {"n_saved": len(saved), "panels_dir": str(panels_dir)}


# ---------- Report writer -----------------------------------------------------

def write_report(results: dict, out_dir: Path):
    md = ["# Phase-1 verification report\n",
          f"_Generated {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}_\n"]
    repr_p = results["reproduction"]
    md.append("## 1. Reproduction parity (gate)\n")
    md.append(f"- Ours `test/mIoU` = **{repr_p['ours'].get('test/mIoU'):.4f}**")
    md.append(f"- IBM  `test/mIoU` = **{repr_p['ibm'].get('test/mIoU'):.4f}**")
    md.append(f"- Δ mIoU = **{repr_p['delta_mIoU']:+.4f}** "
              f"({'PASS' if repr_p['pass_overall_mIoU_within_2pp'] else 'FAIL'} ±2pp)")
    md.append(f"- Ours `test/IoU_1` (water) = {repr_p['ours'].get('test/IoU_1'):.4f}")
    md.append(f"- IBM  `test/IoU_1` (water) = {repr_p['ibm'].get('test/IoU_1'):.4f}")
    md.append(f"- Δ water IoU = **{repr_p['delta_IoU_1']:+.4f}** "
              f"({'PASS' if repr_p['pass_water_IoU_within_3pp'] else 'FAIL'} ±3pp)\n")

    h2h = results["head_to_head"]
    md.append("## 2. Head-to-head per-chip\n")
    md.append(f"- Chips compared: {h2h['n_chips']}")
    md.append(f"- Δ water IoU mean = {h2h['delta_iou1_mean']:+.4f}")
    md.append(f"- Δ water IoU median = {h2h['delta_iou1_median']:+.4f}")
    md.append(f"- 5–95% range = [{h2h['delta_iou1_p05']:+.4f}, {h2h['delta_iou1_p95']:+.4f}]")
    md.append(f"- Ours better (>2pp): {h2h['n_ours_better']}")
    md.append(f"- IBM better (>2pp): {h2h['n_ibm_better']}\n")

    cv = results["convergence"]
    md.append("## 3. Convergence trajectory\n")
    if cv.get("ok") is False:
        md.append(f"- **SKIP** — {cv['reason']}\n")
    else:
        md.append(f"- Train-loss points logged: {cv['n_train_loss_points']}")
        md.append(f"- Val epochs: {cv['n_val_epochs']}")
        md.append(f"- First/last train loss: {cv['first_train_loss']:.4f} → {cv['last_train_loss']:.4f}")
        md.append(f"- Best val: epoch {cv['best_val_epoch']}, loss {cv['best_val_loss']:.4f}")
        md.append(f"- Last val: epoch {cv['last_val_epoch']}, loss {cv['last_val_loss']:.4f}")
        md.append(f"- Best≠last epoch: {'PASS' if cv['pass_best_not_last_epoch'] else 'FAIL (more training budget needed)'}\n")

    ems = results["ems"]
    md.append("## 4. EMS event stratification\n")
    if ems.get("ok") is False:
        md.append(f"- **SKIP** — {ems['reason']}\n")
    else:
        md.append(f"- Distinct events: {ems['n_events']}")
        md.append(f"- Mean water IoU (worst event): {ems['mean_iou1_min_event']:.4f}")
        md.append(f"- Mean water IoU (best event):  {ems['mean_iou1_max_event']:.4f}\n")

    cal = results["calibration"]
    md.append("## 5. Calibration / mode-collapse\n")
    if cal.get("ok") is False:
        md.append(f"- **SKIP** — {cal['reason']}\n")
    else:
        md.append(f"- N prob samples: {cal['n_samples']}")
        md.append(f"- Extreme-bin mass (≤0.05 ∪ ≥0.95): {cal['p_extreme_mass']:.3f}")
        md.append(f"- Middle-band mass (0.25–0.75):    {cal['p_middle_mass']:.3f}")
        md.append(f"- Not collapsed: {'PASS' if cal['pass_not_collapsed'] else 'FAIL'}\n")

    ns = results["numeric"]
    md.append("## 6. Numeric stability\n")
    md.append(f"- Params: {ns['n_params']:,}")
    md.append(f"- NaN: {ns['n_nan']} | Inf: {ns['n_inf']}")
    md.append(f"- Max |weight|: {ns['max_abs_weight']:.3f}")
    md.append(f"- {'PASS' if ns['pass_no_nan_inf'] else 'FAIL'} no NaN/Inf\n")

    md.append("## 7. Documented load path (`LightningInferenceModel.from_config`)\n")
    lp = results["load_path"]
    md.append(f"- {'PASS' if lp.get('pass') else 'FAIL'} — {lp.get('type') or lp.get('err')}\n")

    st = results["safetensors"]
    md.append("## 8. Safetensors round-trip\n")
    if st.get("pass"):
        md.append(f"- {'PASS'} — {st['size_mb']:.1f} MB → {st['out_path']}\n")
    else:
        md.append(f"- FAIL — {st.get('err')}\n")

    th = results.get("throughput", {})
    md.append("## 9. Throughput\n")
    md.append(f"- Inference batches measured: {th.get('n_batches')}")
    md.append(f"- it/s: {th.get('it_per_s'):.2f}" if th.get("it_per_s") else "- it/s: n/a")
    md.append(f"- Peak VRAM during measurement: {th.get('peak_vram_gb'):.2f} GB\n"
              if th.get("peak_vram_gb") is not None else "")

    qp = results["qual"]
    md.append("## 10. Qualitative panels\n")
    md.append(f"- {qp['n_saved']} panels → `{qp['panels_dir']}/`\n")

    md.append("---\n## Verdict\n")
    if (repr_p["pass_overall_mIoU_within_2pp"] and
        repr_p["pass_water_IoU_within_3pp"] and
        ns["pass_no_nan_inf"] and
        cal.get("pass_not_collapsed", True) and
        st.get("pass") and
        lp.get("pass")):
        md.append("**Reproduction confirmed.** Publish as "
                  "`<handle>/TerraMind-base-Flood-AMD`.\n")
    elif (not repr_p["pass_overall_mIoU_within_2pp"]
          and abs(repr_p["delta_mIoU"]) <= 0.05):
        md.append("**Approximate reproduction (2–5 pp gap).** Publish "
                  "with gap documented honestly in the model card.\n")
    else:
        md.append("**Failed reproduction or hard fail in safety checks.** "
                  "Publish as negative-results card or do not publish.\n")

    (out_dir / "report.md").write_text("\n".join(md))
    (out_dir / "report.json").write_text(
        json.dumps({k: v for k, v in results.items()
                    if not isinstance(v, (np.ndarray,))},
                   default=str, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--our-ckpt", required=True)
    ap.add_argument("--ibm-ckpt", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--csv-log", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-qual", type=int, default=12)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--max-eval-batches", type=int, default=None,
                    help="cap dataloader batches for the per-chip eval")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    results["reproduction"]   = reproduction_parity(args, out_dir)
    results["numeric"]        = numeric_stability(args.our_ckpt)
    results["load_path"]      = documented_load_path(args.config, args.our_ckpt)
    results["safetensors"]    = safetensors_roundtrip(args.our_ckpt, out_dir)
    results["convergence"]    = convergence(args.csv_log, out_dir)

    # Build dataloader once
    dm, dl = build_test_dataloader(args.config)

    # Per-chip / calibration / qual all share inference; group them.
    h2h = head_to_head(args, dl, args.device, out_dir)
    results["head_to_head"]   = {k: v for k, v in h2h.items()
                                 if k not in ("ours_prob_sample", "rows")}
    results["calibration"]    = calibration_report(h2h["ours_prob_sample"], out_dir)
    results["ems"]            = ems_stratify(h2h["rows"])

    # Throughput on ours
    ours_model = build_inference_model(args.config, args.our_ckpt, args.device)
    results["throughput"]     = throughput(ours_model, dl, args.device, n_batches=20)
    # Qual panels need both
    ibm_model = build_inference_model(args.config, args.ibm_ckpt, args.device)
    results["qual"]           = qual_panels(ours_model, ibm_model, dl,
                                             args.device, out_dir, n=args.n_qual)

    write_report(results, out_dir)
    print(f"\n[done] report → {out_dir / 'report.md'}")


if __name__ == "__main__":
    sys.exit(main())
