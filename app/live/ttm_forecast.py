"""Granite TimeSeries TTM r2 — short-horizon nowcast for the live tide
residual (storm surge / wind setup) at the NYC harbor entrance.

Why TTM here, vs the existing live NOAA fetcher:
- The existing `noaa_tides` specialist returns a single 6-min snapshot:
  observed, predicted, residual = observed - predicted. That's "right now."
- TTM forecasts the next ~9.6 hours of the *residual* — the meteorologic
  component (surge + wind setup). NOAA already publishes the astronomical
  tide; TTM tells us if the surge component is about to peak.
- This is the genuinely useful add: a nowcast of the part NOAA *doesn't*
  predict.

Architecture: ibm-granite/granite-timeseries-ttm-r2, ~1.5M params,
zero-shot multivariate (we use it univariate here on the residual
series). 512-step context @ 6-min cadence = ~51 h of history;
96-step horizon = ~9.6 h ahead.

Citation: Ekambaram, V., et al. (2024). "Tiny Time Mixers (TTMs):
Fast Pre-trained Models for Enhanced Zero/Few-Shot Forecasting of
Multivariate Time Series." NeurIPS 2024.

Gated emission: a doc is only added when the forecast peak residual
exceeds an absolute threshold (default 0.3 ft / 9 cm). On a calm day
the model still runs, but the reconciler sees no doc — silence over
confabulation.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

import httpx
import numpy as np

log = logging.getLogger("riprap.ttm_forecast")

DOC_ID = "ttm_forecast"
CITATION = ("IBM Granite TimeSeries TTM r2 (Ekambaram et al. 2024, NeurIPS); "
            "ibm-granite/granite-timeseries-ttm-r2 via granite-tsfm")

# Three NOAA stations covering NYC harbor + Long Island Sound + Bight.
# step_ttm_forecast picks the closest to the queried address (matches the
# existing nearest-gauge behaviour in step_noaa_tides). This means an
# inland-Queens query forecasts at Kings Point (Long Island Sound), a
# Coney Island query forecasts at Sandy Hook (Bight), and a Manhattan
# query forecasts at the Battery — each gauge characterises a different
# storm-surge regime.
STATIONS = [
    ("8518750", "The Battery, NY",  40.7006, -74.0142),
    ("8516945", "Kings Point, NY",  40.8103, -73.7649),
    ("8531680", "Sandy Hook, NJ",   40.4669, -74.0094),
]
NOAA_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"

CONTEXT_LENGTH = 512   # ~51 h at 6-min cadence (surge forecast)
PREDICTION_LENGTH = 96  # ~9.6 h horizon (surge forecast)
MIN_INTERESTING_RESIDUAL_FT = 0.3  # ~9 cm — gate for doc emission

# 311 daily-counts forecast — TTM r2's smallest pretrained config is
# 512 context which is awkward for weekly counts on a single address.
# Daily aggregation (512 days ≈ 17 months of complaint history) lets
# the model run natively at its standard resolution; we forecast the
# next 96 days (~3 months).
DAILY_CONTEXT = 512
DAILY_PREDICTION = 96
NYC_311_URL = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
NYC_311_FLOOD_DESCRIPTORS = (
    "Sewer Backup (Use Comments) (SA)",
    "Catch Basin Clogged/Flooding (Use Comments) (SC)",
    "Street Flooding (SJ)",
    "Manhole Overflow (Use Comments) (SA1)",
    "Flooding on Street",
)


# ---- Lazy-loaded model singleton -----------------------------------------

_MODELS: dict[tuple[int, int], object] = {}
_MODEL_LOAD_ERROR: str | None = None


def _load_model(context_length: int = CONTEXT_LENGTH,
                prediction_length: int = PREDICTION_LENGTH):
    """TTM r2 is configured per (context, prediction) length pair. Cache
    by that pair so the surge forecaster (512→96) and the weekly 311
    forecaster (52→4) each get their own model handle on first use."""
    global _MODEL_LOAD_ERROR
    key = (context_length, prediction_length)
    if key in _MODELS:
        return _MODELS[key]
    if _MODEL_LOAD_ERROR is not None:
        return None
    try:
        import torch  # noqa: F401

        # Force-import the registered class names BEFORE get_model so that
        # transformers' lazy registry can resolve them by string. Without
        # this, AutoModel-style dispatch raises
        #   ModuleNotFoundError("Could not import module 'PreTrainedModel'")
        # under the FSM worker thread (the lazy import path races with
        # other model loads). See web/main.py startup for the same
        # pre-import on the main thread.
        from transformers import PreTrainedModel  # noqa: F401
        from tsfm_public import TinyTimeMixerForPrediction  # noqa: F401
        from tsfm_public.toolkit.get_model import get_model
        m = get_model(
            "ibm-granite/granite-timeseries-ttm-r2",
            context_length=context_length,
            prediction_length=prediction_length,
        )
        m.eval()
        _MODELS[key] = m
        log.info("TTM r2 loaded (context=%d horizon=%d)",
                 context_length, prediction_length)
        return m
    except Exception as e:
        _MODEL_LOAD_ERROR = repr(e)
        log.exception("TTM model load failed; future calls will be skipped")
        return None


# Closest-of-three station selection (mirrors app/context/noaa_tides.py).
def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    from math import asin, cos, radians, sin, sqrt
    R = 6371.0
    p1, p2 = radians(lat1), radians(lat2)
    dp = radians(lat2 - lat1); dl = radians(lon2 - lon1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * R * asin(sqrt(a))


def _nearest_station(lat: float, lon: float):
    return min(STATIONS, key=lambda s: _haversine_km(lat, lon, s[2], s[3]))


# ---- NOAA history fetch --------------------------------------------------

def _fetch_noaa_series(begin_iso: str, end_iso: str, product: str,
                       station_id: str) -> dict:
    """One-shot NOAA datagetter for a date range. Returns the JSON body."""
    r = httpx.get(NOAA_URL, params={
        "begin_date": begin_iso, "end_date": end_iso,
        "station": station_id, "product": product,
        "datum": "MLLW", "units": "english", "time_zone": "lst_ldt",
        "format": "json",
    }, timeout=15.0)
    r.raise_for_status()
    return r.json()


def _residual_series(station_id: str,
                     n_obs_needed: int = CONTEXT_LENGTH) -> tuple[np.ndarray, list[str]] | None:
    """Build the recent residual series (observed - predicted) at 6-min
    cadence, length CONTEXT_LENGTH. Returns (values_ft, timestamps_iso).
    Returns None if NOAA refused, returned mismatched shapes, or the
    series is too short."""
    # Fetch slightly more than we need to absorb the occasional missing
    # 6-min sample; we'll trim to exact length below.
    end = datetime.utcnow()
    # NOAA recommends LST/LDT for time_zone matching across products
    begin = end - timedelta(minutes=6 * (n_obs_needed + 50))
    fmt = "%Y%m%d %H:%M"
    begin_s = begin.strftime(fmt)
    end_s = end.strftime(fmt)
    try:
        obs_j = _fetch_noaa_series(begin_s, end_s, "water_level", station_id)
        pred_j = _fetch_noaa_series(begin_s, end_s, "predictions", station_id)
    except Exception as e:
        log.warning("NOAA fetch failed: %r", e)
        return None
    obs_data = obs_j.get("data") or []
    pred_data = pred_j.get("predictions") or []
    if not obs_data or not pred_data:
        return None
    # Both products are 6-min cadence and share timestamps; align by t.
    obs_by_t = {row["t"]: float(row["v"]) for row in obs_data if row.get("v")}
    pred_by_t = {row["t"]: float(row["v"]) for row in pred_data if row.get("v")}
    common_ts = sorted(set(obs_by_t) & set(pred_by_t))
    if len(common_ts) < n_obs_needed:
        log.warning("only %d aligned NOAA samples (need %d)",
                    len(common_ts), n_obs_needed)
        return None
    common_ts = common_ts[-n_obs_needed:]
    residual = np.array([obs_by_t[t] - pred_by_t[t] for t in common_ts],
                        dtype=np.float32)
    return residual, common_ts


# ---- Forecast --------------------------------------------------------------

def _run_ttm(history: np.ndarray,
             context_length: int = CONTEXT_LENGTH,
             prediction_length: int = PREDICTION_LENGTH,
             cadence: str = "h") -> np.ndarray | None:
    """Channel-wise standardize, run model, de-standardize. Returns a
    `prediction_length`-step de-standardized forecast in input units.

    v0.4.5 — tries the MI300X riprap-models service first; falls back
    to the local in-process model on RemoteUnreachable. The
    standardize / de-standardize math is owned by THIS function so the
    remote service stays a thin "given a series, give me a forecast"
    contract.
    """
    global _MODEL_LOAD_ERROR
    mu = float(history.mean())
    sigma = float(history.std() + 1e-6)
    normed = (history - mu) / sigma

    # Try remote first. When remote is configured we bias HARD toward it:
    # if the remote returns non-ok we surface that error rather than
    # silently falling through to a local model load (which on cpu-basic
    # surfaces would 502 with a cryptic transformers-internal
    # ModuleNotFoundError). Local fallback is only used when the remote
    # is unreachable (transport-level), which is what a degraded droplet
    # actually looks like.
    remote_attempted = False
    try:
        from app import inference as _inf
        if _inf.remote_enabled():
            remote_attempted = True
            remote = _inf.ttm_forecast(
                "zero_shot_battery", normed.tolist(),
                context_length=context_length,
                prediction_length=prediction_length,
                cadence=cadence,
            )
            if remote.get("ok"):
                pred = np.asarray(remote["forecast"], dtype=np.float32)
                return pred * sigma + mu
            _MODEL_LOAD_ERROR = (
                f"remote ttm-forecast returned non-ok: {remote.get('error') or remote}"
            )
            log.warning("TTM zero-shot: remote returned non-ok: %s", remote)
            return None
    except _inf.RemoteUnreachable as e:
        log.info("TTM zero-shot: remote unreachable (%s); local fallback", e)
    except Exception as e:
        log.exception("TTM zero-shot remote call failed: %r", e)
        if remote_attempted:
            _MODEL_LOAD_ERROR = f"remote ttm-forecast errored: {type(e).__name__}: {e}"
            return None

    # Local fallback (only reached when remote isn't configured or is
    # unreachable at the transport level).
    try:
        model = _load_model(context_length, prediction_length)
    except Exception as e:
        _MODEL_LOAD_ERROR = f"{type(e).__name__}: {e}"
        log.exception("TTM model load raised: %r", e)
        return None
    if model is None:
        return None
    try:
        import torch
    except ImportError:
        _MODEL_LOAD_ERROR = "torch not available on this deployment"
        return None
    x = torch.from_numpy(normed.astype(np.float32))[None, :, None]
    try:
        with torch.no_grad():
            out = model(past_values=x)
    except Exception as e:
        _MODEL_LOAD_ERROR = f"{type(e).__name__}: {e}"
        log.exception("TTM inference failed: %r", e)
        return None
    pred = out.prediction_outputs[0, :, 0].cpu().numpy()
    return pred * sigma + mu


def summary_for_point(lat: float, lon: float) -> dict:
    """Surge forecast at the NOAA gauge nearest the queried address.

    Three gauges cover NYC: Battery (harbor entrance), Kings Point
    (LI Sound), Sandy Hook (Bight). Surge regimes differ — Sandy 2012
    peaked at +14 ft at the Battery vs. lower at Kings Point because
    the gauges respond to different forcing geometries. Picking the
    closest gauge to the queried address makes the forecast
    address-relevant rather than always city-wide.
    """
    sid, sname, slat, slon = _nearest_station(lat, lon)
    distance_km = round(_haversine_km(lat, lon, slat, slon), 1)

    series = _residual_series(sid)
    if series is None:
        return {"available": False,
                "reason": "NOAA history fetch returned insufficient data",
                "station_id": sid, "station_name": sname,
                "distance_km": distance_km}
    history, timestamps = series
    forecast = _run_ttm(history, CONTEXT_LENGTH, PREDICTION_LENGTH)
    if forecast is None:
        return {"available": False,
                "reason": _MODEL_LOAD_ERROR or "TTM inference failed",
                "station_id": sid, "station_name": sname,
                "distance_km": distance_km}

    history_peak = float(np.max(np.abs(history)))
    fc_peak_idx = int(np.argmax(np.abs(forecast)))
    fc_peak_ft = float(forecast[fc_peak_idx])
    fc_peak_minutes_ahead = (fc_peak_idx + 1) * 6
    fc_peak_time = datetime.utcnow() + timedelta(minutes=fc_peak_minutes_ahead)

    interesting = (abs(fc_peak_ft) >= MIN_INTERESTING_RESIDUAL_FT or
                   history_peak >= MIN_INTERESTING_RESIDUAL_FT)

    return {
        "available": True,
        "interesting": interesting,
        "station_id": sid,
        "station_name": sname,
        "distance_km": distance_km,
        "context_length": int(len(history)),
        "horizon_steps": int(len(forecast)),
        "history_peak_abs_ft": round(history_peak, 2),
        "history_recent_ft": round(float(history[-1]), 2),
        "forecast_peak_ft": round(fc_peak_ft, 2),
        "forecast_peak_minutes_ahead": fc_peak_minutes_ahead,
        "forecast_peak_time_utc": fc_peak_time.isoformat(timespec="minutes") + "Z",
        "threshold_ft": MIN_INTERESTING_RESIDUAL_FT,
        # Type-keyed renderer reads this for the spatial-note row.
        # No fine-tune footer on the zero-shot variant — the
        # display.variant: timeseries (vs timeseries-ft) is the
        # signal that suppresses the model-card chrome.
        "spatial_note": f"regional · {sname}, not point-of-query",
    }


# ---- Per-address daily 311 flood-complaint forecast ----------------------

def _fetch_311_flood_daily(lat: float, lon: float,
                            radius_m: int = 200,
                            days: int = DAILY_CONTEXT,
                            ) -> tuple[np.ndarray, list[str]] | None:
    """Pull `days` of daily flood-complaint counts within `radius_m` of
    (lat, lon) from NYC OpenData. Returns (counts_array_length_days,
    date_labels) or None on failure. Missing days are zero-filled."""
    from collections import defaultdict
    from datetime import datetime as _dt
    from datetime import timedelta as _td
    end = _dt.utcnow().date()
    start = end - _td(days=days + 1)
    descs = " OR ".join(f"descriptor='{d}'" for d in NYC_311_FLOOD_DESCRIPTORS)
    where = (
        f"created_date between '{start.isoformat()}T00:00:00' and "
        f"'{end.isoformat()}T23:59:59' AND "
        f"latitude IS NOT NULL AND longitude IS NOT NULL AND "
        f"({descs}) AND "
        f"within_circle(location, {lat}, {lon}, {radius_m})"
    )
    try:
        r = httpx.get(NYC_311_URL,
                      params={"$select": "created_date",
                              "$where": where,
                              "$limit": "50000"},
                      timeout=20.0)
        r.raise_for_status()
        rows = r.json()
    except Exception as e:
        log.warning("311 flood fetch for TTM failed: %r", e)
        return None

    counts: dict[str, int] = defaultdict(int)
    for row in rows or []:
        ds = (row.get("created_date") or "")[:10]
        if not ds:
            continue
        counts[ds] += 1

    series: list[int] = []
    labels: list[str] = []
    for i in range(days):
        d = end - _td(days=days - 1 - i)
        d_iso = d.isoformat()
        labels.append(d_iso)
        series.append(counts.get(d_iso, 0))
    return np.array(series, dtype=np.float32), labels


def weekly_311_forecast_for_point(lat: float, lon: float,
                                  radius_m: int = 200) -> dict:
    """TTM r2 zero-shot forecast on per-address daily 311
    flood-complaint counts. Despite the name — kept for FSM-call-site
    stability — this now operates on daily resolution (TTM r2's
    smallest native config is 512 context, awkward for weekly).
    History: 512 days (~17 months); forecast: 96 days (~3 months).
    Returns daily and weekly summaries so the reconciler narration
    stays human-readable.

    Designed not to raise. Returns `available: False` with a reason
    field on any failure path."""
    series = _fetch_311_flood_daily(lat, lon, radius_m=radius_m)
    if series is None:
        return {"available": False, "reason": "311 history fetch failed"}
    history, labels = series
    forecast = _run_ttm(history, DAILY_CONTEXT, DAILY_PREDICTION)
    if forecast is None:
        return {"available": False,
                "reason": _MODEL_LOAD_ERROR or "TTM inference failed"}

    fc_clipped = np.clip(forecast, 0, None)
    hist_total = int(history.sum())
    hist_mean_per_day = float(history.mean())
    hist_recent_mean_30d = float(history[-30:].mean())
    fc_total = float(fc_clipped.sum())
    fc_mean_per_day = float(fc_clipped.mean())
    fc_peak_day = float(fc_clipped.max())
    fc_peak_day_offset = int(fc_clipped.argmax()) + 1

    # Aggregate to weekly equivalents for the briefing narration —
    # readers think in weeks, not days.
    history_weekly_mean = hist_mean_per_day * 7
    forecast_weekly_mean = fc_mean_per_day * 7

    accelerating = (hist_recent_mean_30d > 0 and
                    fc_mean_per_day > 1.5 * hist_recent_mean_30d)

    return {
        "available": True,
        "radius_m": radius_m,
        "days_context": DAILY_CONTEXT,
        "days_horizon": DAILY_PREDICTION,
        "history_total_complaints": hist_total,
        "history_mean_per_day": round(hist_mean_per_day, 3),
        "history_recent_30d_mean": round(hist_recent_mean_30d, 3),
        "history_weekly_equivalent": round(history_weekly_mean, 2),
        "forecast_total_next_horizon": round(fc_total, 1),
        "forecast_mean_per_day": round(fc_mean_per_day, 3),
        "forecast_weekly_equivalent": round(forecast_weekly_mean, 2),
        "forecast_peak_day": round(fc_peak_day, 2),
        "forecast_peak_day_offset": fc_peak_day_offset,
        "accelerating": accelerating,
        "context_window_start": labels[0] if labels else None,
        "context_window_end": labels[-1] if labels else None,
    }
