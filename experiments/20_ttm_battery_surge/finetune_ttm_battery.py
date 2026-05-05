"""Fine-tune Granite Time-Series TTM r2 on NYC Battery surge residual.

TTM r2 is a 1.5 M-param transformer for time-series forecasting from
IBM Granite TimeSeries. We fine-tune it to predict the next 24 hours
of surge residual at NOAA Battery (NY) given the prior 96 hours.

Reproducibility goals (publishable artifact):
  - Lock train/val/test splits temporally (chronological), not random.
  - Report sMAPE, MAE, MAPE on the held-out test horizon.
  - Compare against the trivial persistence baseline (next 24h = last 24h)
    to demonstrate the model adds signal beyond mean reversion.

Usage:
    python3 finetune_ttm_battery.py \
        --data /root/ttm_battery/battery_2015_2024.parquet \
        --out  /root/ttm_battery/output_phase20
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

# tsfm / granite-tsfm installation provides this on the clean container.
from tsfm_public import TinyTimeMixerForPrediction
from transformers import TrainingArguments, Trainer, AutoConfig


# TTM r2 ships pretrained variants for specific (context, horizon)
# combinations. The 512/96 variant is the workhorse: 512 hours of
# history -> 96 hours forecast (~21 days in, 4 days out). For Battery
# surge that's plenty of context to learn storm/quiescence patterns.
CONTEXT_LEN = 1024
PREDICTION_LEN = 96


class SurgeResidualDataset(Dataset):
    def __init__(self, series: np.ndarray, indices: np.ndarray):
        self.series = series
        self.indices = indices

    def __len__(self):
        return len(self.indices)

    def __getitem__(self, idx):
        i = self.indices[idx]
        x = self.series[i:i + CONTEXT_LEN]
        y = self.series[i + CONTEXT_LEN:i + CONTEXT_LEN + PREDICTION_LEN]
        return {
            "past_values":   torch.tensor(x, dtype=torch.float32).unsqueeze(-1),
            "future_values": torch.tensor(y, dtype=torch.float32).unsqueeze(-1),
        }


def chronological_split(df: pd.DataFrame,
                        train_frac: float = 0.7,
                        val_frac: float = 0.15) -> tuple:
    """Splits the time series chronologically. Train -> Val -> Test."""
    df = df.sort_values("timestamp").reset_index(drop=True)
    df = df.set_index("timestamp")

    # Resample to 1h to match prediction horizon granularity. Take mean.
    series = df["surge_residual_m"].resample("1h").mean().interpolate().values

    n = len(series)
    n_train = int(train_frac * n)
    n_val = int(val_frac * n)
    train_end = n_train
    val_end = n_train + n_val

    # Sliding windows; only valid where both context+prediction fit.
    def windows_in(start, end):
        valid = []
        for i in range(start, end - CONTEXT_LEN - PREDICTION_LEN + 1):
            valid.append(i)
        return np.array(valid, dtype=np.int64)

    return series, {
        "train": windows_in(0, train_end),
        "val":   windows_in(train_end, val_end),
        "test":  windows_in(val_end, n),
    }


def persistence_baseline(series: np.ndarray, indices: np.ndarray) -> dict:
    """Naive baseline: ŷ_{t+1..t+24} = y_t (last value held)."""
    preds, trues = [], []
    for i in indices:
        last = series[i + CONTEXT_LEN - 1]
        y_hat = np.full(PREDICTION_LEN, last)
        y = series[i + CONTEXT_LEN:i + CONTEXT_LEN + PREDICTION_LEN]
        preds.append(y_hat); trues.append(y)
    preds = np.array(preds); trues = np.array(trues)
    return {
        "MAE_m":  float(np.mean(np.abs(preds - trues))),
        "RMSE_m": float(np.sqrt(np.mean((preds - trues) ** 2))),
    }


def evaluate_model(model, dataset: SurgeResidualDataset,
                   device: str) -> dict:
    model.eval()
    loader = DataLoader(dataset, batch_size=64, shuffle=False)
    preds, trues = [], []
    with torch.no_grad():
        for batch in loader:
            past = batch["past_values"].to(device)
            future = batch["future_values"].to(device)
            out = model(past_values=past)
            yhat = out.prediction_outputs.cpu().numpy()
            preds.append(yhat); trues.append(future.cpu().numpy())
    preds = np.concatenate(preds, axis=0).squeeze(-1)
    trues = np.concatenate(trues, axis=0).squeeze(-1)
    return {
        "MAE_m":  float(np.mean(np.abs(preds - trues))),
        "RMSE_m": float(np.sqrt(np.mean((preds - trues) ** 2))),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out",  type=Path, required=True)
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(args.seed); np.random.seed(args.seed)

    print(f"[ttm] loading {args.data}", flush=True)
    df = pd.read_parquet(args.data)
    print(f"[ttm] {len(df):,} rows, "
          f"surge std {df['surge_residual_m'].std():.3f} m", flush=True)

    series, splits = chronological_split(df)
    print(f"[ttm] series len {len(series):,} hours; "
          f"train={len(splits['train'])} val={len(splits['val'])} "
          f"test={len(splits['test'])}", flush=True)

    train_ds = SurgeResidualDataset(series, splits["train"])
    val_ds   = SurgeResidualDataset(series, splits["val"])
    test_ds  = SurgeResidualDataset(series, splits["test"])

    # Persistence baseline.
    base = persistence_baseline(series, splits["test"])
    print(f"[baseline] persistence: MAE={base['MAE_m']:.4f} m, "
          f"RMSE={base['RMSE_m']:.4f} m", flush=True)

    # TTM r2 512/96 variant.
    print("[ttm] loading TTM-r2 (512/96)", flush=True)
    model = TinyTimeMixerForPrediction.from_pretrained(
        "ibm-granite/granite-timeseries-ttm-r2",
        revision="1024-96-r2",
        context_length=CONTEXT_LEN,
        prediction_length=PREDICTION_LEN,
        num_input_channels=1,
    )

    # Pre-fine-tune zero-shot eval.
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    zs = evaluate_model(model, test_ds, device)
    print(f"[zero-shot] TTM r2: MAE={zs['MAE_m']:.4f} m, "
          f"RMSE={zs['RMSE_m']:.4f} m", flush=True)

    # Fine-tune.
    train_args = TrainingArguments(
        output_dir=str(args.out / "trainer"),
        num_train_epochs=args.epochs,
        learning_rate=args.lr,
        per_device_train_batch_size=args.batch,
        per_device_eval_batch_size=args.batch,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        report_to="none",
        seed=args.seed,
        fp16=True,
        logging_steps=50,
    )
    trainer = Trainer(model=model, args=train_args,
                      train_dataset=train_ds, eval_dataset=val_ds)
    trainer.train()

    # Post-fine-tune eval.
    ft = evaluate_model(model, test_ds, device)
    print(f"[fine-tuned] TTM r2: MAE={ft['MAE_m']:.4f} m, "
          f"RMSE={ft['RMSE_m']:.4f} m", flush=True)

    # Persist results + the model.
    metrics = {
        "context_length": CONTEXT_LEN,
        "prediction_length": PREDICTION_LEN,
        "n_train_windows": int(len(splits["train"])),
        "n_val_windows": int(len(splits["val"])),
        "n_test_windows": int(len(splits["test"])),
        "baseline_persistence": base,
        "zero_shot_ttm_r2": zs,
        "fine_tuned_ttm_r2": ft,
        "improvement_vs_persistence": {
            "MAE_pct": 100 * (base["MAE_m"] - ft["MAE_m"]) / base["MAE_m"],
            "RMSE_pct": 100 * (base["RMSE_m"] - ft["RMSE_m"]) / base["RMSE_m"],
        },
        "improvement_vs_zeroshot": {
            "MAE_pct": 100 * (zs["MAE_m"] - ft["MAE_m"]) / zs["MAE_m"],
            "RMSE_pct": 100 * (zs["RMSE_m"] - ft["RMSE_m"]) / zs["RMSE_m"],
        },
    }
    (args.out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    model.save_pretrained(str(args.out / "ttm_battery_ft"))
    print(f"\n[done] metrics + model -> {args.out}", flush=True)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    sys.exit(main())
