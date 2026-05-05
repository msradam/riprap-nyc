"""Fine-tune Granite TimeSeries TTM r2 on NYC Battery surge residual.

Pulls 5 years of NOAA CO-OPS 6-min data for the Battery (8518750), computes
the surge residual = observed - predicted_astronomical_tide, fine-tunes TTM r2
to forecast that residual at 96-step (~9.6h) horizon.

Why TTM r2:
  - Riprap already runs zero-shot TTM r2 for the live surge residual specialist
  - 1.5M params: fine-tunes in minutes on MI300X
  - Same call signature as zero-shot, drop-in upgrade

Reproducibility: NOAA CO-OPS API is free, no auth. tsfm cookbook recipe is
upstream at github.com/ibm-granite-community/granite-timeseries-cookbook.

Usage:
    python3 finetune_ttm.py --epochs 10 --out /root/terramind_nyc/ttm_nyc
"""
from __future__ import annotations
import argparse, json, os, sys, time, urllib.request, urllib.parse
from pathlib import Path
from datetime import date, timedelta

import numpy as np
import pandas as pd

NOAA_BASE = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
GAUGE = "8518750"  # The Battery, NYC

CONTEXT_LEN = 512   # TTM r2 supported context lengths: 512 / 1024 / 1536
FORECAST_LEN = 96   # 9.6h at 6-min cadence

def fetch_window(start: date, end: date, product: str) -> pd.DataFrame:
    """NOAA CO-OPS limits requests to ~30 days of 6-min data; chunk it."""
    out = []
    cur = start
    while cur < end:
        chunk_end = min(cur + timedelta(days=30), end)
        params = {
            "begin_date": cur.strftime("%Y%m%d"),
            "end_date":   chunk_end.strftime("%Y%m%d"),
            "station":    GAUGE,
            "product":    product,
            "datum":      "MLLW",
            "units":      "metric",
            "time_zone":  "GMT",
            "format":     "json",
            "interval":   "6",
        }
        url = NOAA_BASE + "?" + urllib.parse.urlencode(params)
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=30) as r:
                    data = json.loads(r.read())
                break
            except Exception as e:
                print(f"  retry {attempt+1}: {e}", flush=True)
                time.sleep(2 + 3 * attempt)
        rows = data.get("data") or data.get("predictions") or []
        for row in rows:
            ts = row.get("t")
            v = row.get("v")
            if ts and v not in (None, "", "nan"):
                try: out.append((pd.Timestamp(ts), float(v)))
                except (ValueError, TypeError): pass
        cur = chunk_end
        time.sleep(0.5)  # be polite to NOAA
    df = pd.DataFrame(out, columns=["ts", product])
    return df.set_index("ts").sort_index()


def build_dataset(years: int, cache_dir: Path) -> pd.DataFrame:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache = cache_dir / f"battery_{years}yr.parquet"
    if cache.exists():
        print(f"[ttm] using cached {cache}", flush=True)
        return pd.read_parquet(cache)

    end = date.today()
    start = end - timedelta(days=years * 365)
    print(f"[ttm] pulling NOAA Battery {start} → {end}", flush=True)
    obs = fetch_window(start, end, "water_level")
    pred = fetch_window(start, end, "predictions")
    df = obs.join(pred, how="inner")
    df["residual"] = df["water_level"] - df["predictions"]
    print(f"[ttm] {len(df)} rows; residual mean={df.residual.mean():.3f} "
          f"std={df.residual.std():.3f}", flush=True)
    df.to_parquet(cache)
    return df


def make_splits(df: pd.DataFrame, train_frac=0.7, val_frac=0.15):
    n = len(df)
    n_tr = int(train_frac * n)
    n_va = int(val_frac * n)
    return df.iloc[:n_tr], df.iloc[n_tr:n_tr+n_va], df.iloc[n_tr+n_va:]


def windows_from_series(values: np.ndarray, ctx: int, hor: int, stride: int):
    """Sliding windows: each sample is (ctx,) input, (hor,) target."""
    X, Y = [], []
    n = len(values)
    for i in range(0, n - ctx - hor + 1, stride):
        X.append(values[i:i+ctx])
        Y.append(values[i+ctx:i+ctx+hor])
    return np.asarray(X, dtype=np.float32), np.asarray(Y, dtype=np.float32)


def train(args):
    import torch
    from torch.utils.data import DataLoader, TensorDataset
    from tsfm_public.models.tinytimemixer import TinyTimeMixerForPrediction
    from tsfm_public.toolkit.dataset import ForecastDFDataset
    from tsfm_public.toolkit.lr_finder import optimal_lr_finder

    df = build_dataset(args.years, Path(args.out) / "data")
    df = df.dropna(subset=["residual"])
    train_df, val_df, test_df = make_splits(df)
    print(f"[ttm] train={len(train_df)} val={len(val_df)} test={len(test_df)}",
          flush=True)

    # z-score by channel using train stats
    mu = float(train_df["residual"].mean())
    sd = float(train_df["residual"].std() or 1.0)

    def to_loader(part_df, batch_size, shuffle):
        vals = ((part_df["residual"].values - mu) / sd).astype(np.float32)
        X, Y = windows_from_series(vals, CONTEXT_LEN, FORECAST_LEN, stride=24)
        if len(X) == 0:
            return None
        Xt = torch.from_numpy(X).unsqueeze(-1)   # (n, ctx, 1)
        Yt = torch.from_numpy(Y).unsqueeze(-1)   # (n, hor, 1)
        return DataLoader(TensorDataset(Xt, Yt), batch_size=batch_size,
                          shuffle=shuffle, num_workers=0, drop_last=False)

    train_loader = to_loader(train_df, args.batch, shuffle=True)
    val_loader   = to_loader(val_df,   args.batch, shuffle=False)
    test_loader  = to_loader(test_df,  args.batch, shuffle=False)
    print(f"[ttm] train batches={len(train_loader)} val={len(val_loader)} "
          f"test={len(test_loader)}", flush=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[ttm] loading TTM r2 on {device}", flush=True)
    model = TinyTimeMixerForPrediction.from_pretrained(
        "ibm-granite/granite-timeseries-ttm-r2",
        revision="main",
        context_length=CONTEXT_LEN,
        prediction_length=FORECAST_LEN,
    ).to(device)

    # Quick zero-shot baseline on test before fine-tuning
    print(f"[ttm] zero-shot baseline on test...", flush=True)
    model.eval()
    zs_mse, zs_mae, zs_n = 0.0, 0.0, 0
    with torch.no_grad():
        for xb, yb in test_loader:
            xb = xb.to(device); yb = yb.to(device)
            out = model(past_values=xb).prediction_outputs
            zs_mse += ((out - yb) ** 2).sum().item()
            zs_mae += (out - yb).abs().sum().item()
            zs_n += yb.numel()
    zs_rmse_n = (zs_mse / zs_n) ** 0.5
    zs_mae_n = zs_mae / zs_n
    # Convert back to meters
    zs_rmse_m = zs_rmse_n * sd
    zs_mae_m = zs_mae_n * sd
    print(f"[ttm] zero-shot test RMSE = {zs_rmse_m:.4f} m, MAE = {zs_mae_m:.4f} m",
          flush=True)

    # Fine-tune
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=args.epochs * len(train_loader))
    history = {"train_loss": [], "val_loss": []}
    best_val = float("inf")
    best_path = Path(args.out) / "ckpt" / "best.pt"
    best_path.parent.mkdir(parents=True, exist_ok=True)

    for ep in range(args.epochs):
        model.train()
        tr_loss, n = 0.0, 0
        for xb, yb in train_loader:
            xb = xb.to(device); yb = yb.to(device)
            out = model(past_values=xb, future_values=yb)
            loss = out.loss
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            tr_loss += loss.item() * xb.size(0); n += xb.size(0)
        tr_loss /= n

        model.eval()
        vl, vn = 0.0, 0
        with torch.no_grad():
            for xb, yb in val_loader:
                xb = xb.to(device); yb = yb.to(device)
                out = model(past_values=xb, future_values=yb)
                vl += out.loss.item() * xb.size(0); vn += xb.size(0)
        vl /= vn
        history["train_loss"].append(tr_loss)
        history["val_loss"].append(vl)
        improved = vl < best_val
        if improved:
            best_val = vl
            torch.save({"state_dict": model.state_dict(),
                        "mu": mu, "sd": sd,
                        "context_len": CONTEXT_LEN,
                        "forecast_len": FORECAST_LEN}, best_path)
        print(f"[ttm] epoch {ep:>2} train_loss={tr_loss:.4f} val_loss={vl:.4f}"
              f"{'  *' if improved else ''}", flush=True)

    # Eval fine-tuned on test
    print(f"[ttm] loading best ckpt val_loss={best_val:.4f}", flush=True)
    sd_state = torch.load(best_path, map_location=device, weights_only=False)
    model.load_state_dict(sd_state["state_dict"])
    model.eval()
    ft_mse, ft_mae, ft_n = 0.0, 0.0, 0
    with torch.no_grad():
        for xb, yb in test_loader:
            xb = xb.to(device); yb = yb.to(device)
            out = model(past_values=xb).prediction_outputs
            ft_mse += ((out - yb) ** 2).sum().item()
            ft_mae += (out - yb).abs().sum().item()
            ft_n += yb.numel()
    ft_rmse_m = (ft_mse / ft_n) ** 0.5 * sd
    ft_mae_m = ft_mae / ft_n * sd
    delta_rmse = ft_rmse_m - zs_rmse_m
    pct = 100 * (zs_rmse_m - ft_rmse_m) / zs_rmse_m
    print("\n[ttm] === Final eval (NYC Battery surge residual, m) ===")
    print(f"  Zero-shot TTM r2     RMSE={zs_rmse_m:.4f}  MAE={zs_mae_m:.4f}")
    print(f"  Fine-tuned TTM-NYC   RMSE={ft_rmse_m:.4f}  MAE={ft_mae_m:.4f}")
    print(f"  Δ RMSE               {delta_rmse:+.4f} m  ({pct:+.1f}%)")

    summary = {
        "gauge": GAUGE, "n_train": len(train_df), "n_val": len(val_df),
        "n_test": len(test_df), "context_len": CONTEXT_LEN,
        "forecast_len": FORECAST_LEN, "epochs": args.epochs, "lr": args.lr,
        "z_mu": mu, "z_sd": sd,
        "zero_shot_rmse_m": zs_rmse_m, "zero_shot_mae_m": zs_mae_m,
        "fine_tuned_rmse_m": ft_rmse_m, "fine_tuned_mae_m": ft_mae_m,
        "rmse_improvement_m": -delta_rmse, "rmse_improvement_pct": pct,
        "history": history,
    }
    Path(args.out, "results.json").write_text(json.dumps(summary, indent=2))
    print(f"[ttm] saved {args.out}/results.json", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=5)
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--out", default="/root/terramind_nyc/ttm_nyc")
    args = ap.parse_args()
    train(args)


if __name__ == "__main__":
    sys.exit(main())
