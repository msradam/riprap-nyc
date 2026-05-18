"""Granite TTM r2 — Battery 96 h surge nowcast (NYC fine-tune).

Wraps the Apache-2.0 [`msradam/Granite-TTM-r2-Battery-Surge`](https://huggingface.co/msradam/Granite-TTM-r2-Battery-Surge)
fine-tune. Fetches the past 1024 hours (~43 days) of hourly verified
water level + harmonic tide predictions at NOAA station 8518750 (The
Battery), computes surge residual (observed − predicted), and forecasts
the next 96 hours.

Distinct from `app.live.ttm_forecast` — that's the *zero-shot* TTM r2
on 6-min cadence (~9.6 h horizon) at the closest of three NYC gauges.
This module is the *fine-tuned* model on hourly cadence (~4-day horizon)
at a single gauge (Battery only — see MODEL_CARD honest-limitations).

Both nowcasts coexist in the FSM. The zero-shot is shorter-horizon and
covers every coastal NYC query; the fine-tuned is longer-horizon and
specialised to the Battery's storm-surge regime, which is the dominant
driver of NYC inundation. The reconciler frames each as a separate
forecast in the briefing.

Gated by RIPRAP_TTM_BATTERY_SURGE_ENABLE — deployments without the
heavy ML deps (granite-tsfm / transformers) silently no-op via the
same skipped-result shape every other heavy specialist emits.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Any

log = logging.getLogger("riprap.ttm_battery_surge")

ENABLE = os.environ.get(
    "RIPRAP_TTM_BATTERY_SURGE_ENABLE", "1"
).lower() in ("1", "true", "yes")
DEVICE = os.environ.get("RIPRAP_TTM_BATTERY_SURGE_DEVICE", "cpu")
REPO = "msradam/Granite-TTM-r2-Battery-Surge"

DOC_ID = "ttm_battery"
CITATION = (
    "msradam/Granite-TTM-r2-Battery-Surge (Apache-2.0, fine-tune of "
    "ibm-granite/granite-timeseries-ttm-r2). Trained on AMD Instinct "
    "MI300X via AMD Developer Cloud. Test MAE 0.1091 m on held-out "
    "2023-2024 windows (vs 0.1467 zero-shot, 0.1861 persistence)."
)

# NOAA Battery (NY) — the canonical NYC storm-surge gauge.
STATION_ID = "8518750"
STATION_NAME = "The Battery, NY"
NOAA_API = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"

# TTM r2 1024-96-r2 backbone: 1024 hours of context, 96 hours of horizon.
CONTEXT_LENGTH = 1024
PREDICTION_LENGTH = 96

# Doc emission gate: only cite the forecast if the predicted peak surge
# is meaningful (positive ≥0.3 m or negative ≤-0.3 m). On a calm day the
# model still runs but the reconciler sees no doc.
MIN_INTERESTING_RESIDUAL_M = float(
    os.environ.get("RIPRAP_TTM_BATTERY_MIN_INTERESTING_M", "0.3"))

_MODEL = None
_INIT_LOCK = threading.Lock()


def _has_required_deps() -> tuple[bool, str | None]:
    missing: list[str] = []
    for name in ("tsfm_public", "huggingface_hub", "torch", "requests",
                 "pandas"):
        try:
            __import__(name)
        except ImportError:
            missing.append(name)
    if missing:
        return False, ", ".join(missing)
    return True, None


_DEPS_OK, _DEPS_MISSING = _has_required_deps()


def _ensure_model():
    """Load the fine-tuned TTM r2 once and cache. Failure is sticky —
    a downloaded-then-broken model leaves _MODEL=None so subsequent
    fetches re-attempt rather than silently serving a half-built one."""
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    with _INIT_LOCK:
        if _MODEL is not None:
            return _MODEL
        from huggingface_hub import snapshot_download

        # Force-import dispatched class names so the transformers lazy
        # registry can resolve `PreTrainedModel` / `TinyTimeMixerForPrediction`
        # under FSM worker threads. Same pattern as ttm_forecast._load_model.
        from transformers import PreTrainedModel  # noqa: F401
        from tsfm_public import TinyTimeMixerForPrediction
        log.info("ttm_battery_surge: downloading %s", REPO)
        local_dir = snapshot_download(REPO)
        log.info("ttm_battery_surge: loading model from %s", local_dir)
        model = TinyTimeMixerForPrediction.from_pretrained(local_dir).eval()
        if DEVICE == "cuda":
            try:
                import torch
                if torch.cuda.is_available():
                    model = model.cuda()
            except Exception:
                log.exception("ttm_battery_surge: cuda move failed; "
                              "staying on CPU")
        _MODEL = model
        return _MODEL


def _fetch_chunk(start: datetime, end: datetime, product: str):
    """Pull one ≤30-day chunk from the NOAA CO-OPS datagetter.

    Two products: `water_level` (verified, 6-min — we ask for hourly
    via interval=h) and `predictions` (hourly harmonic tide). Both come
    back in metres if `units=metric`.
    """
    import pandas as pd
    import requests
    params = {
        "station": STATION_ID,
        "begin_date": start.strftime("%Y%m%d"),
        "end_date": end.strftime("%Y%m%d"),
        "product": product,
        "datum": "MLLW",
        "units": "metric",
        "time_zone": "gmt",
        "format": "json",
        "application": "riprap-nyc",
        "interval": "h",
    }
    resp = requests.get(NOAA_API, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    key = "data" if "data" in data else "predictions"
    if key not in data:
        return pd.DataFrame()
    df = pd.DataFrame(data[key])
    if df.empty:
        return df
    df["timestamp"] = pd.to_datetime(df["t"])
    df["value"] = pd.to_numeric(df["v"], errors="coerce")
    return df[["timestamp", "value"]].dropna()


def _fetch_battery_history(hours: int) -> Any:
    """Pull the last `hours` hours of (water_level, predicted) at the
    Battery and return a DataFrame with columns
    `timestamp / water_level_m / predicted_m / surge_residual_m`."""
    import pandas as pd

    end_d = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    n_days = max(1, hours // 24 + 3)  # padding in case of NOAA gaps

    chunks_wl, chunks_pr = [], []
    cur = end_d - timedelta(days=n_days)
    while cur < end_d:
        nxt = min(cur + timedelta(days=30), end_d)
        try:
            chunks_wl.append(_fetch_chunk(cur, nxt, "water_level"))
            chunks_pr.append(_fetch_chunk(cur, nxt, "predictions"))
        except Exception as e:
            log.warning("ttm_battery_surge: NOAA chunk %s..%s failed: %s",
                        cur.date(), nxt.date(), e)
        cur = nxt

    wl = pd.concat(chunks_wl, ignore_index=True) if chunks_wl else pd.DataFrame()
    pr = pd.concat(chunks_pr, ignore_index=True) if chunks_pr else pd.DataFrame()
    if wl.empty or pr.empty:
        return pd.DataFrame()
    wl = wl.rename(columns={"value": "water_level_m"})
    pr = pr.rename(columns={"value": "predicted_m"})
    df = wl.merge(pr, on="timestamp", how="inner").sort_values("timestamp")
    df["surge_residual_m"] = df["water_level_m"] - df["predicted_m"]
    df = df.dropna(subset=["surge_residual_m"])
    if len(df) > hours:
        df = df.iloc[-hours:].reset_index(drop=True)
    return df


def _summarize(history_df, forecast_arr) -> dict[str, Any]:
    """Build the public dict the FSM specialist hands to the reconciler.

    Includes both raw arrays (for downstream charts in the trace UI)
    and human-readable scalars (peak / peak time / interesting flag)
    that the reconciler can paraphrase without overshooting evidence.
    """
    import numpy as np
    history_arr = history_df["surge_residual_m"].to_numpy()
    history_recent = float(history_arr[-1]) if len(history_arr) else None
    history_peak_abs = float(np.max(np.abs(history_arr))) if len(history_arr) else None

    fc = np.asarray(forecast_arr, dtype="float64").reshape(-1)
    if fc.size == 0:
        return {"available": False, "reason": "empty forecast"}
    peak_idx = int(np.argmax(np.abs(fc)))
    peak = float(fc[peak_idx])
    peak_h_ahead = peak_idx + 1  # hourly cadence; index 0 = +1 h

    last_ts = (history_df["timestamp"].iloc[-1]
               if len(history_df) else datetime.utcnow())
    peak_time = last_ts + timedelta(hours=peak_h_ahead)

    interesting = bool(abs(peak) >= MIN_INTERESTING_RESIDUAL_M)

    return {
        "available": True,
        "interesting": interesting,
        "model": REPO,
        "station_id": STATION_ID,
        "station_name": STATION_NAME,
        "context_hours": int(len(history_arr)),
        "horizon_hours": int(fc.size),
        "history_recent_m": (round(history_recent, 3)
                              if history_recent is not None else None),
        "history_peak_abs_m": (round(history_peak_abs, 3)
                                if history_peak_abs is not None else None),
        "forecast_peak_m": round(peak, 3),
        "forecast_peak_hours_ahead": peak_h_ahead,
        "forecast_peak_time_utc": peak_time.isoformat(timespec="minutes"),
        "forecast_array_m": [round(float(v), 4) for v in fc.tolist()],
        # Type-keyed bespoke renderer reads these for the
        # fine-tune footer. Constants because the model card is
        # fixed for this pebble — the same shape can appear in any
        # future fine-tuned forecast pebble.
        "hf_model_card": f"huggingface.co/{REPO}",
        "rmse_m": 0.157,
        "skill_vs_persistence": "-35% vs persistence",
        "hardware_badge": "MI300X",
        "spatial_note": f"regional · {STATION_NAME}, not point-of-query",
    }


def fetch(timeout_s: float = 60.0) -> dict[str, Any]:
    """Run the specialist. Always returns a dict with at minimum
    `{available: bool, reason | ...}`. Caller should treat
    `available=False` as silence-over-confabulation."""
    if not ENABLE:
        return {"available": False,
                "reason": "RIPRAP_TTM_BATTERY_SURGE_ENABLE=0"}

    t0 = time.time()
    try:
        df = _fetch_battery_history(CONTEXT_LENGTH)
        if len(df) < CONTEXT_LENGTH:
            return {"available": False,
                    "reason": f"insufficient NOAA history: "
                              f"got {len(df)} hours, need {CONTEXT_LENGTH}"}
        if time.time() - t0 > timeout_s:
            return {"available": False,
                    "reason": "NOAA fetch exceeded budget"}

        residuals = df["surge_residual_m"].to_numpy().astype("float32")

        # v0.4.5 — try the MI300X service first. The remote handles its
        # own model loading; if it's reachable we never need local
        # tsfm_public, which lets the HF Space drop the granite-tsfm
        # bake from the image. When the remote is configured but returns
        # non-ok we surface the remote error rather than try a local
        # load — the local code path can ModuleNotFoundError on transient
        # transformers-registry races and that's a worse user signal.
        forecast = None
        compute = "local"
        remote_attempted = False
        try:
            from app import inference as _inf
            if _inf.remote_enabled():
                remote_attempted = True
                remote = _inf.ttm_forecast(
                    "fine_tune_battery", residuals.tolist(),
                    context_length=CONTEXT_LENGTH,
                    prediction_length=PREDICTION_LENGTH,
                    cadence="h",
                    timeout=timeout_s,
                )
                if remote.get("ok"):
                    import numpy as np
                    forecast = np.asarray(remote["forecast"], dtype="float32")
                    compute = f"remote · {remote.get('device', 'gpu')}"
                else:
                    return {"available": False,
                            "reason": f"remote ttm-forecast non-ok: "
                                      f"{remote.get('error') or 'unknown'}",
                            "elapsed_s": round(time.time() - t0, 2)}
        except _inf.RemoteUnreachable as e:
            log.info("ttm_battery_surge: remote unreachable (%s); local", e)
        except Exception as e:
            log.exception("ttm_battery_surge: remote call failed")
            if remote_attempted:
                return {"available": False,
                        "reason": f"remote ttm-forecast error: "
                                  f"{type(e).__name__}: {e}",
                        "elapsed_s": round(time.time() - t0, 2)}

        if forecast is None:
            if not _DEPS_OK:
                return {"available": False,
                        "reason": f"deps unavailable on this deployment: "
                                  f"{_DEPS_MISSING}"}
            import torch
            model = _ensure_model()
            past = torch.from_numpy(residuals).unsqueeze(0).unsqueeze(-1)
            if DEVICE == "cuda":
                try:
                    if torch.cuda.is_available():
                        past = past.cuda()
                except Exception:
                    log.exception("ttm_battery_surge: cuda move failed")
            with torch.no_grad():
                out = model(past_values=past)
            forecast = out.prediction_outputs.squeeze(-1).squeeze(0).cpu().numpy()

        result = _summarize(df, forecast)
        result["compute"] = compute
        result["elapsed_s"] = round(time.time() - t0, 2)
        return result
    except Exception as e:
        log.exception("ttm_battery_surge fetch failed")
        return {"available": False,
                "reason": f"{type(e).__name__}: {e}",
                "elapsed_s": round(time.time() - t0, 2)}


def warm():
    """Optional pre-load — amortizes the first-query model build cost."""
    if not ENABLE or not _DEPS_OK:
        return
    try:
        _ensure_model()
    except Exception:
        log.exception("ttm_battery_surge: warm() failed")
