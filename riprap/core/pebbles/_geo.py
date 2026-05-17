"""Shared geo helpers used by csv_points + ckan_records.

Both adapters do bbox push-down (for fast filtering) followed by a
haversine refine (for true circle membership). Centralised here so the
math is in one place and any future bug fix lands once.
"""
from __future__ import annotations

import math

# Mean Earth radius (m). Conventional value for haversine — matches what
# PostGIS, sf, geopy, and the `haversine` library use.
_EARTH_RADIUS_M = 6_371_000.0

# Meters per degree of latitude (constant) and the equatorial conversion
# constant for longitude (scaled by cos(lat) at the query latitude).
_M_PER_DEG_LAT = 111_320.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters between two WGS84 points."""
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))


def bbox_from_radius(
    lat: float, lon: float, radius_m: int,
) -> tuple[float, float, float, float]:
    """Bounding box (lat_min, lat_max, lon_min, lon_max) that fully
    contains a `radius_m` circle around (lat, lon).

    Use for SQL push-down: the bbox is cheap to filter on (lat/lon
    BETWEEN), then refine each row with `haversine_m` to enforce the
    true circle. The eps clamp on cos(lat) avoids divide-by-zero at the
    poles; not material for any real address query but cheap insurance.
    """
    dlat = radius_m / _M_PER_DEG_LAT
    dlon = radius_m / (_M_PER_DEG_LAT * max(math.cos(math.radians(lat)), 1e-6))
    return (lat - dlat, lat + dlat, lon - dlon, lon + dlon)
