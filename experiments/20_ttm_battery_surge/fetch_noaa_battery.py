"""Fetch NOAA Battery (NY) tide gauge water-level history.

NOAA station 8518750 — The Battery, lower Manhattan. The canonical NYC
storm-surge gauge; data available since 1920. We pull 6-minute interval
verified water level (predicted_tide_anomaly subtraction is the surge
residual). Station metadata:
  https://tidesandcurrents.noaa.gov/stationhome.html?id=8518750

Output: parquet with columns (timestamp, water_level_m, predicted_m,
surge_residual_m). Surge residual is the target for TTM nowcasting.

Usage:
    python3 fetch_noaa_battery.py --start 2015-01-01 --end 2024-12-31 \
        --out /root/ttm_battery/battery_2015_2024.parquet
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd
import requests

API = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
STATION = "8518750"
PRODUCTS = {"water_level": "water_level", "predictions": "predicted"}


def fetch_chunk(start: str, end: str, product: str) -> pd.DataFrame:
    params = {
        "station": STATION,
        "begin_date": start.replace("-", ""),
        "end_date": end.replace("-", ""),
        "product": product,
        "datum": "MLLW",
        "units": "metric",
        "time_zone": "gmt",
        "format": "json",
        "application": "riprap-nyc-phase20",
        "interval": "6" if product == "water_level" else "h",
    }
    for attempt in range(3):
        try:
            r = requests.get(API, params=params, timeout=60)
            r.raise_for_status()
            data = r.json()
            if "data" in data:
                df = pd.DataFrame(data["data"])
                df["timestamp"] = pd.to_datetime(df["t"])
                df["value"] = pd.to_numeric(df["v"], errors="coerce")
                return df[["timestamp", "value"]]
            if "predictions" in data:
                df = pd.DataFrame(data["predictions"])
                df["timestamp"] = pd.to_datetime(df["t"])
                df["value"] = pd.to_numeric(df["v"], errors="coerce")
                return df[["timestamp", "value"]]
            return pd.DataFrame()
        except Exception as e:
            print(f"  ! attempt {attempt+1}: {e}", flush=True)
            time.sleep(2 ** attempt)
    return pd.DataFrame()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2015-01-01")
    ap.add_argument("--end",   default="2024-12-31")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    start = pd.to_datetime(args.start)
    end = pd.to_datetime(args.end)

    # NOAA caps requests at 31 days for verified water levels.
    chunks_wl, chunks_pr = [], []
    cur = start
    while cur < end:
        nxt = min(cur + pd.Timedelta(days=30), end)
        s = cur.strftime("%Y-%m-%d")
        e = nxt.strftime("%Y-%m-%d")
        print(f"[noaa] fetching {s} .. {e}", flush=True)
        wl = fetch_chunk(s, e, "water_level")
        pr = fetch_chunk(s, e, "predictions")
        if not wl.empty: chunks_wl.append(wl)
        if not pr.empty: chunks_pr.append(pr)
        cur = nxt + pd.Timedelta(days=1)

    wl = pd.concat(chunks_wl, ignore_index=True).rename(
        columns={"value": "water_level_m"})
    pr = pd.concat(chunks_pr, ignore_index=True).rename(
        columns={"value": "predicted_m"})

    # Align predictions (hourly) with water-level (6-min) by floor-1h.
    wl["hour"] = wl["timestamp"].dt.floor("h")
    pr["hour"] = pr["timestamp"].dt.floor("h")
    pr_h = pr.groupby("hour")["predicted_m"].mean().reset_index()

    df = wl.merge(pr_h, on="hour", how="left")
    df["surge_residual_m"] = df["water_level_m"] - df["predicted_m"]
    df = df[["timestamp", "water_level_m", "predicted_m",
             "surge_residual_m"]]
    df = df.dropna()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.out)
    print(f"\n[noaa] wrote {len(df):,} rows -> {args.out}")
    print(f"  range: {df['timestamp'].min()} .. {df['timestamp'].max()}")
    print(f"  surge_residual range: "
          f"{df['surge_residual_m'].min():.3f} .. "
          f"{df['surge_residual_m'].max():.3f} m")
    print(f"  surge_residual std: {df['surge_residual_m'].std():.3f} m")


if __name__ == "__main__":
    sys.exit(main())
