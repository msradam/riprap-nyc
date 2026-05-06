"""Granite TimeSeries TTM r2 forecast on FloodNet sensor flood events.

This is the strongest single TTM win for the NYU CUSP audience.
FloodNet (CUSP/Brooklyn College, Charlie Mydlarz + Andrea Silverman)
operates the sensor network and publishes the historical events; they
do not publish per-sensor forecasts. Riprap producing a forecast on
FloodNet's own data is a genuine ecosystem-extension capability — and
unlike the surge / 311 forecasts, the audience explicitly cares about
this dataset.

Architecture:
- Nearest FloodNet sensor to the queried address (reuse
  `app.context.floodnet.sensors_near`).
- 512 days of binary daily-event history at that sensor (1 if any
  labeled flood event started on that day, else 0).
- TTM r2 (512 → 96) reused from `app.live.ttm_forecast._load_model` —
  *no new model class loaded into memory*. The existing 311 daily
  forecaster has already paid this load cost.
- 96-day-ahead daily forecast → aggregated into 4-week and 12-week
  expected counts so the briefing narration stays human-readable.

Silence over confabulation: returns `available: False` with a
reason field on every failure path. Sensors with fewer than 5
flood events in their entire history yield no forecast (the TTM
output on near-empty histories is dominated by quantization noise).

Doc-id format: `floodnet_forecast_<deployment_id>` so it's distinct
from the existing `[floodnet]` event-history doc.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import numpy as np

from app.context.floodnet import flood_events_for, sensors_near
from app.live.ttm_forecast import (
    _MODEL_LOAD_ERROR,
    DAILY_CONTEXT,
    DAILY_PREDICTION,
    _run_ttm,
)

log = logging.getLogger("riprap.floodnet_forecast")

DOC_ID_PREFIX = "floodnet_forecast"
CITATION = (
    "FloodNet NYC ultrasonic depth sensors (api.floodnet.nyc) + "
    "IBM Granite TimeSeries TTM r2 (Ekambaram et al. 2024, NeurIPS) "
    "via granite-tsfm — daily flood-event recurrence forecast"
)

# A sensor with <5 historical events in 512 days has too sparse a
# signal for TTM to produce a meaningful forecast. The model still
# runs, but the output is dominated by quantization noise around
# zero; emitting a doc from that state is exactly the kind of
# pseudo-quantitative claim the four-tier discipline guards against.
MIN_EVENTS_FOR_FORECAST = 5

# Search radius for nearest-sensor lookup. Wider than the existing
# `floodnet` specialist's 600 m (which scans for *all* sensors at
# the address) — we just need *one* relevant sensor for the forecast.
NEAREST_SENSOR_RADIUS_M = 1500


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    from math import asin, cos, radians, sin, sqrt
    R = 6371000.0
    p1, p2 = radians(lat1), radians(lat2)
    dp = radians(lat2 - lat1); dl = radians(lon2 - lon1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * R * asin(sqrt(a))


def _build_daily_event_series(
    deployment_id: str, days: int
) -> tuple[np.ndarray, list[str], int]:
    """Pull flood events for one sensor over `days` days, return a
    daily binary series (1 if ≥1 flood event started that day, 0
    otherwise) plus the event count."""
    since = datetime.now(timezone.utc) - timedelta(days=days + 2)
    events = flood_events_for([deployment_id], since=since)
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days - 1)
    by_day: dict[str, int] = {}
    for e in events:
        ds = (e.start_time or "")[:10]
        if not ds:
            continue
        by_day[ds] = 1
    series: list[int] = []
    labels: list[str] = []
    for i in range(days):
        d = start + timedelta(days=i)
        d_iso = d.isoformat()
        labels.append(d_iso)
        series.append(by_day.get(d_iso, 0))
    return np.array(series, dtype=np.float32), labels, len(events)


def summary_for_point(lat: float, lon: float) -> dict:
    """Forecast flood-event recurrence at the nearest FloodNet sensor.

    Returns a dict with `available: bool`. On success, includes the
    sensor identity, history summary, and forecast aggregates.
    """
    try:
        sensors = sensors_near(lat, lon, NEAREST_SENSOR_RADIUS_M)
    except Exception as e:
        log.warning("FloodNet sensor lookup failed: %r", e)
        return {"available": False, "reason": "FloodNet API unreachable"}

    if not sensors:
        return {"available": False,
                "reason": f"no FloodNet sensor within {NEAREST_SENSOR_RADIUS_M} m"}

    # Closest by haversine. Some deployments have null geometry; skip those.
    geo_sensors = [s for s in sensors if s.lat is not None and s.lon is not None]
    if not geo_sensors:
        return {"available": False, "reason": "nearest sensor has no geometry"}
    nearest = min(geo_sensors,
                  key=lambda s: _haversine_m(lat, lon, s.lat, s.lon))
    distance_m = _haversine_m(lat, lon, nearest.lat, nearest.lon)

    try:
        history, labels, total_events = _build_daily_event_series(
            nearest.deployment_id, days=DAILY_CONTEXT
        )
    except Exception as e:
        log.warning("FloodNet history fetch failed for %s: %r",
                    nearest.deployment_id, e)
        return {"available": False, "reason": "history fetch failed"}

    if total_events < MIN_EVENTS_FOR_FORECAST:
        return {
            "available": False,
            "reason": (f"sensor has only {total_events} historical events "
                       f"(<{MIN_EVENTS_FOR_FORECAST}); forecast omitted"),
            "sensor_id": nearest.deployment_id,
            "sensor_name": nearest.name,
        }

    forecast = _run_ttm(history, DAILY_CONTEXT, DAILY_PREDICTION)
    if forecast is None:
        return {"available": False,
                "reason": _MODEL_LOAD_ERROR or "TTM inference failed"}

    fc = np.clip(forecast, 0, None)
    fc28 = float(fc[:28].sum())
    fc_total = float(fc.sum())
    fc_peak_offset = int(fc.argmax()) + 1
    fc_peak_value = float(fc.max())

    hist_total = int(history.sum())
    hist_recent_28d = float(history[-28:].sum())

    # "Accelerating" if the next-28-days expected count materially
    # exceeds the prior-28-days observed count.
    accelerating = (hist_recent_28d > 0
                    and fc28 > 1.5 * hist_recent_28d)

    return {
        "available": True,
        "doc_id": f"{DOC_ID_PREFIX}_{nearest.deployment_id}",
        "sensor_id": nearest.deployment_id,
        "sensor_name": nearest.name,
        "sensor_street": nearest.street,
        "sensor_borough": nearest.borough,
        "sensor_lat": nearest.lat,
        "sensor_lon": nearest.lon,
        "distance_from_query_m": round(distance_m, 1),
        "history_window_days": DAILY_CONTEXT,
        "history_total_events": hist_total,
        "history_recent_28d_events": int(hist_recent_28d),
        "forecast_horizon_days": DAILY_PREDICTION,
        "forecast_28d_expected_events": round(fc28, 2),
        "forecast_total_horizon_events": round(fc_total, 2),
        "forecast_peak_day_offset": fc_peak_offset,
        "forecast_peak_day_value": round(fc_peak_value, 3),
        "accelerating": accelerating,
        "model": "granite-timeseries-ttm-r2",
        "citation": CITATION,
    }
