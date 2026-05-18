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
    # (id, name, lat, lon) — NOAA CO-OPS Tides & Currents station IDs.
    # The set must cover every spatially-routed deployment so the
    # `_find_nearest_station` lookup doesn't fall through to an
    # arbitrarily-distant station (which was the bug behind a Boston
    # query landing on Albany NY at 222 km).
    #
    # NYC harbor + Long Island Sound
    ("8518750", "The Battery, NY",         40.7006, -74.0142),
    ("8516945", "Kings Point, NY",         40.8103, -73.7649),
    ("8531680", "Sandy Hook, NJ",          40.4669, -74.0094),
    # Hudson tidal corridor (head-of-tide is Troy / Albany; Hudson is tidal
    # all the way up to the Federal Lock at Troy)
    ("8518995", "Albany, NY (Hudson)",     42.6469, -73.7464),
    ("8518962", "Turkey Point Hudson, NY", 41.7569, -73.9433),
    ("8519483", "West Point, NY",          41.3845, -73.9536),
    # Boston Harbor — covers the Boston deployment
    ("8443970", "Boston, MA",              42.3548, -71.0534),
    # San Francisco Bay — covers the SF deployment
    ("9414290", "San Francisco, CA",       37.8063, -122.4659),
    ("9414750", "Alameda, CA",             37.7717, -122.3000),
    # Puget Sound — covers the Seattle deployment
    ("9447130", "Seattle, WA",             47.6026, -122.3392),
    # Lake Michigan / Calumet Harbor — covers the Chicago deployment.
    # (Great Lakes use CO-OPS too; product set differs but the
    # nearest-station + reading shape is the same.)
    ("9087044", "Calumet Harbor, IL",      41.7300, -87.5383),
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


# Great Lakes stations (NOAA CO-OPS lake gauges) don't support the
# MLLW tidal datum — Great Lakes elevations reference IGLD (the
# International Great Lakes Datum). Hitting the API with datum=MLLW
# against Calumet Harbor (9087044) etc. returns HTTP 400, so the
# Chicago Lake Michigan card silently came up null. Map each station
# to its native datum.
_GREAT_LAKES_STATIONS = {"9087044"}  # Calumet Harbor, IL — extend as we ship more lake gauges


def _datum_for(station_id: str) -> str:
    return "IGLD" if station_id in _GREAT_LAKES_STATIONS else "MLLW"


def _fetch(station_id: str, product: str) -> dict:
    r = httpx.get(URL, params={
        "date": "latest", "station": station_id, "product": product,
        "datum": _datum_for(station_id),
        "units": "english", "time_zone": "lst_ldt",
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
    is_great_lakes = sid in _GREAT_LAKES_STATIONS
    try:
        obs = _fetch(sid, "water_level").get("data") or []
        if obs:
            out.observed_ft = round(float(obs[0]["v"]), 2)
            out.obs_time = obs[0].get("t")
        # Great Lakes stations don't publish tide predictions
        # (there are no astronomical tides on a lake — just wind,
        # ice, and seasonal water-level fluctuation). Skip the
        # predictions fetch to avoid a 400 on every Chicago run.
        if not is_great_lakes:
            pred = _fetch(sid, "predictions").get("predictions") or []
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
    datum = _datum_for(r.station_id)
    # Build a templatable narrative the manifest's narration.template
    # consumes — keeps location-specific phrasing here in the pebble's
    # adapter (not in the UI codebase). Returns None when the fetch
    # failed entirely; the manifest's `narration.short` then takes over.
    narrative: str | None = None
    if r.observed_ft is not None:
        bits = [f"Latest reading at {r.station_name}: "
                f"{r.observed_ft} ft above {datum}"]
        if r.predicted_ft is not None and r.residual_ft is not None:
            sign = "+" if r.residual_ft >= 0 else ""
            bits.append(f" ({sign}{r.residual_ft} ft vs predicted tide)")
        if r.obs_time:
            bits.append(f", observed {r.obs_time}")
        narrative = "".join(bits) + "."
    return {
        "station_id": r.station_id,
        "station_name": r.station_name,
        "station_lat": sta[2] if sta else None,
        "station_lon": sta[3] if sta else None,
        "distance_km": r.distance_km,
        "datum": datum,          # MLLW (tidal) | IGLD (Great Lakes)
        "observed_ft": r.observed_ft,
        # Back-compat alias: the legacy field name baked the tidal
        # datum into the key. Keep it for callers (frontend + LLM
        # citations) that haven't switched to the datum-agnostic
        # `observed_ft` + `datum` pair yet.
        "observed_ft_mllw": r.observed_ft,
        "predicted_ft_mllw": r.predicted_ft,
        "residual_ft": r.residual_ft,
        "obs_time": r.obs_time,
        "narrative": narrative,
        "error": r.error,
    }
