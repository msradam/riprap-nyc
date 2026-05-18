"""NWS station observations — latest hourly METAR for the nearest NYC airport.

api.weather.gov/stations/{id}/observations/latest.

Five NYC-region ASOS stations cover the city; we pick the nearest.
Most useful field for flood context is hourly precipitation (the
`precipitationLastHour` quantity, mm). The latest observation is
typically <60 min old.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt

import httpx

DOC_ID = "nws_obs"
CITATION = "NWS station observations API (api.weather.gov/stations)"

USER_AGENT = "Riprap-NYC/0.1 (civic-flood-tool; +https://huggingface.co/spaces/msradam/riprap-nyc)"

# NYC + Hudson Corridor ASOS stations. Picker is haversine-nearest, so adding
# upstate stations enables Albany / Poughkeepsie / Newburgh queries without
# breaking NYC behaviour (NYC stations stay closer for NYC lat/lon).
STATIONS = [
    # NYC region
    ("KNYC", "Central Park, NY",         40.7794, -73.9692),
    ("KLGA", "LaGuardia Airport, NY",    40.7794, -73.8800),
    ("KJFK", "JFK Airport, NY",          40.6413, -73.7781),
    ("KEWR", "Newark Liberty, NJ",       40.6925, -74.1687),
    ("KFRG", "Republic Farmingdale, NY", 40.7288, -73.4134),
    # Hudson Corridor (south → north)
    ("KHPN", "White Plains, NY",         41.0670, -73.7076),
    ("KSWF", "Newburgh-Stewart, NY",     41.5042, -74.1048),
    ("KPOU", "Poughkeepsie, NY",         41.6262, -73.8842),
    ("KALB", "Albany Intl, NY",          42.7475, -73.8025),
    # Other shipped deployments — without these a Boston query
    # returns Albany NY at 230km. Same NYC-bias bug as the NOAA
    # tide-gauge list before the round-4 fix.
    ("KBOS", "Boston Logan, MA",         42.3606, -71.0097),
    ("KBED", "Hanscom Field, MA",        42.4699, -71.2890),
    ("KORD", "Chicago O'Hare, IL",       41.9786, -87.9048),
    ("KMDW", "Chicago Midway, IL",       41.7868, -87.7522),
    ("KSEA", "Seattle-Tacoma, WA",       47.4502, -122.3088),
    ("KBFI", "Boeing Field, WA",         47.5300, -122.3019),
    ("KSFO", "San Francisco Intl, CA",   37.6213, -122.3790),
    ("KOAK", "Oakland Intl, CA",         37.7213, -122.2208),
]


@dataclass
class Obs:
    station_id: str
    station_name: str
    distance_km: float
    obs_time: str | None
    temp_c: float | None
    precip_last_hour_mm: float | None
    precip_last_3h_mm: float | None
    precip_last_6h_mm: float | None
    error: str | None = None


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    p1, p2 = radians(lat1), radians(lat2)
    dp = radians(lat2 - lat1); dl = radians(lon2 - lon1)
    a = sin(dp/2)**2 + cos(p1)*cos(p2)*sin(dl/2)**2
    return 2 * R * asin(sqrt(a))


def _val_mm(props, key) -> float | None:
    """NWS returns {value: ..., unitCode: 'wmoUnit:mm'} per quantity. Convert
    to mm; if value is null, return None."""
    q = (props or {}).get(key) or {}
    v = q.get("value")
    if v is None:
        return None
    return round(float(v), 2)


def obs_at(lat: float, lon: float) -> Obs:
    sid, name, slat, slon = min(STATIONS, key=lambda s: _haversine_km(lat, lon, s[2], s[3]))
    dist_km = round(_haversine_km(lat, lon, slat, slon), 1)
    out = Obs(station_id=sid, station_name=name, distance_km=dist_km,
              obs_time=None, temp_c=None,
              precip_last_hour_mm=None, precip_last_3h_mm=None,
              precip_last_6h_mm=None)
    try:
        r = httpx.get(
            f"https://api.weather.gov/stations/{sid}/observations/latest",
            headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json"},
            timeout=8.0,
        )
        r.raise_for_status()
        p = r.json().get("properties", {}) or {}
        out.obs_time = p.get("timestamp")
        out.temp_c = _val_mm(p, "temperature")
        out.precip_last_hour_mm = _val_mm(p, "precipitationLastHour")
        out.precip_last_3h_mm = _val_mm(p, "precipitationLast3Hours")
        out.precip_last_6h_mm = _val_mm(p, "precipitationLast6Hours")
    except Exception as e:
        out.error = str(e)
    return out


def summary_for_point(lat: float, lon: float) -> dict:
    o = obs_at(lat, lon)
    # Templatable narrative the manifest's narration.template renders.
    # None when the fetch failed entirely; narration.short takes over.
    narrative: str | None = None
    if o.station_name and (o.temp_c is not None
                           or o.precip_last_hour_mm is not None
                           or o.precip_last_6h_mm is not None):
        bits = [f"Latest METAR at {o.station_name}"]
        if o.distance_km is not None:
            bits.append(f" ({o.distance_km:.1f} km away)")
        bits.append(":")
        if o.temp_c is not None:
            bits.append(f" {o.temp_c}°C")
        p1 = o.precip_last_hour_mm
        p6 = o.precip_last_6h_mm
        if p1 is not None and p1 > 0:
            bits.append(f", {p1} mm precip in the last hour")
        elif p6 is not None and p6 > 0:
            bits.append(f", {p6} mm precip in the last 6 hours")
        elif p1 == 0 or p6 == 0:
            bits.append(", no recent precipitation")
        if o.obs_time:
            bits.append(f" (obs {o.obs_time[:16]})")
        narrative = "".join(bits) + "."
    return {
        "station_id": o.station_id,
        "station_name": o.station_name,
        "distance_km": o.distance_km,
        "obs_time": o.obs_time,
        "temp_c": o.temp_c,
        "precip_last_hour_mm": o.precip_last_hour_mm,
        "precip_last_3h_mm": o.precip_last_3h_mm,
        "precip_last_6h_mm": o.precip_last_6h_mm,
        "narrative": narrative,
        "error": o.error,
    }
