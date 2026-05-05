"""NOAA CO-OPS Tides & Currents — live coastal water level.

api.tidesandcurrents.noaa.gov, no auth, 6-min cadence.

We pick the nearest of three NYC-region stations to the queried address:
  - 8518750 The Battery, NY
  - 8516945 Kings Point, NY (Long Island Sound entrance)
  - 8531680 Sandy Hook, NJ (NY Harbor approach)

The verified-water-level API returns instantaneous water elevation
relative to MLLW (Mean Lower Low Water — the local tidal datum). To
distinguish "high tide" from "storm surge" we also fetch the published
predicted tide and report the residual.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt

import httpx

DOC_ID = "noaa_tides"
CITATION = "NOAA CO-OPS Tides & Currents (api.tidesandcurrents.noaa.gov)"
URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"

STATIONS = [
    # (id, name, lat, lon)
    # NYC harbor + Long Island Sound
    ("8518750", "The Battery, NY",         40.7006, -74.0142),
    ("8516945", "Kings Point, NY",         40.8103, -73.7649),
    ("8531680", "Sandy Hook, NJ",          40.4669, -74.0094),
    # Hudson tidal corridor (head-of-tide is Troy / Albany; Hudson is tidal
    # all the way up to the Federal Lock at Troy)
    ("8518995", "Albany, NY (Hudson)",     42.6469, -73.7464),
    ("8518962", "Turkey Point Hudson, NY", 41.7569, -73.9433),
    ("8519483", "West Point, NY",          41.3845, -73.9536),
]


@dataclass
class TideReading:
    station_id: str
    station_name: str
    distance_km: float
    observed_ft: float | None      # current water level above MLLW
    predicted_ft: float | None     # astronomical prediction at same instant
    residual_ft: float | None      # observed - predicted (≈ storm surge)
    obs_time: str | None
    error: str | None = None


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    p1, p2 = radians(lat1), radians(lat2)
    dp = radians(lat2 - lat1); dl = radians(lon2 - lon1)
    a = sin(dp/2)**2 + cos(p1)*cos(p2)*sin(dl/2)**2
    return 2 * R * asin(sqrt(a))


def _nearest_station(lat: float, lon: float):
    return min(STATIONS, key=lambda s: _haversine_km(lat, lon, s[2], s[3]))


def _fetch(station_id: str, product: str) -> dict:
    r = httpx.get(URL, params={
        "date": "latest", "station": station_id, "product": product,
        "datum": "MLLW", "units": "english", "time_zone": "lst_ldt",
        "format": "json",
    }, timeout=8.0)
    r.raise_for_status()
    return r.json()


def reading_at(lat: float, lon: float) -> TideReading:
    sid, name, slat, slon = _nearest_station(lat, lon)
    dist_km = round(_haversine_km(lat, lon, slat, slon), 1)
    out = TideReading(station_id=sid, station_name=name, distance_km=dist_km,
                      observed_ft=None, predicted_ft=None, residual_ft=None,
                      obs_time=None)
    try:
        obs = _fetch(sid, "water_level").get("data") or []
        pred = _fetch(sid, "predictions").get("predictions") or []
        if obs:
            out.observed_ft = round(float(obs[0]["v"]), 2)
            out.obs_time = obs[0].get("t")
        if pred:
            out.predicted_ft = round(float(pred[0]["v"]), 2)
        if out.observed_ft is not None and out.predicted_ft is not None:
            out.residual_ft = round(out.observed_ft - out.predicted_ft, 2)
    except Exception as e:
        out.error = str(e)
    return out


def summary_for_point(lat: float, lon: float) -> dict:
    r = reading_at(lat, lon)
    # Look up station coords for the map marker.
    sta = next((s for s in STATIONS if s[0] == r.station_id), None)
    return {
        "station_id": r.station_id,
        "station_name": r.station_name,
        "station_lat": sta[2] if sta else None,
        "station_lon": sta[3] if sta else None,
        "distance_km": r.distance_km,
        "observed_ft_mllw": r.observed_ft,
        "predicted_ft_mllw": r.predicted_ft,
        "residual_ft": r.residual_ft,
        "obs_time": r.obs_time,
        "error": r.error,
    }
