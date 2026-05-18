"""NYC 311 — flood-related complaints around a point.

Live dataset: erm2-nwe9. Filter by descriptor (the flood signal is in
descriptor, not complaint_type) within a buffer.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

URL = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
DOC_ID = "nyc311"
CITATION = "NYC 311 service requests (Socrata erm2-nwe9, 2010-present)"

FLOOD_DESCRIPTORS = [
    "Street Flooding (SJ)",
    "Sewer Backup (Use Comments) (SA)",
    "Catch Basin Clogged/Flooding (Use Comments) (SC)",
    "Highway Flooding (SH)",
    "Manhole Overflow (Use Comments) (SA1)",
    "Flooding on Street",
    "RAIN GARDEN FLOODING (SRGFLD)",
]

_DESC_CLAUSE = "(" + " OR ".join(f"descriptor='{d}'" for d in FLOOD_DESCRIPTORS) + ")"


@dataclass
class Complaint:
    unique_key: str
    descriptor: str
    created_date: str
    address: str | None
    status: str | None
    lat: float | None = None
    lon: float | None = None


def complaints_near(lat: float, lon: float, radius_m: float = 200,
                    since: datetime | None = None,
                    limit: int = 1000) -> list[Complaint]:
    where = f"{_DESC_CLAUSE} AND within_circle(location, {lat}, {lon}, {radius_m})"
    if since:
        # Socrata floating-timestamp: drop tz suffix
        ts = since.replace(tzinfo=None).isoformat(timespec="seconds")
        where += f" AND created_date >= '{ts}'"
    r = httpx.get(URL, params={
        "$select": "unique_key, descriptor, created_date, incident_address, "
                   "status, latitude, longitude",
        "$where": where,
        "$order": "created_date desc",
        "$limit": str(limit),
    }, timeout=30)
    r.raise_for_status()
    out = []
    for row in r.json():
        lat = row.get("latitude")
        lon = row.get("longitude")
        try:
            lat = float(lat) if lat is not None else None
            lon = float(lon) if lon is not None else None
        except Exception:
            lat, lon = None, None
        out.append(Complaint(
            unique_key=row.get("unique_key", ""),
            descriptor=row.get("descriptor", ""),
            created_date=row.get("created_date", ""),
            address=row.get("incident_address"),
            status=row.get("status"),
            lat=lat, lon=lon,
        ))
    return out


def summary_for_point(lat: float, lon: float, radius_m: float = 200,
                      years: int = 5) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=365 * years)
    cs = complaints_near(lat, lon, radius_m, since=since, limit=2000)
    return _summarize(cs, years=years, radius_m=radius_m)


def complaints_in_polygon(polygon, polygon_crs: str = "EPSG:4326",
                          since: datetime | None = None,
                          limit: int = 5000,
                          simplify_tolerance: float = 0.0005) -> list[Complaint]:
    """Pull flood-related complaints inside an arbitrary polygon via
    Socrata's `within_polygon(location, 'MULTIPOLYGON(...)')` predicate.

    NYC NTA polygons can have thousands of vertices and exceed Socrata's
    URL length limit (414). We simplify in EPSG:4326 with a default
    ~50 m tolerance, which collapses vertex count ~10-20× without
    materially changing the contained-points result.

    Polygon must be EPSG:4326 (lat/lon) for the Socrata query.
    """
    import geopandas as gpd
    g = gpd.GeoDataFrame(geometry=[polygon], crs=polygon_crs).to_crs("EPSG:4326")
    geom = g.iloc[0].geometry.simplify(simplify_tolerance, preserve_topology=True)
    wkt = geom.wkt
    where = f"{_DESC_CLAUSE} AND within_polygon(location, '{wkt}')"
    if since:
        ts = since.replace(tzinfo=None).isoformat(timespec="seconds")
        where += f" AND created_date >= '{ts}'"
    r = httpx.get(URL, params={
        "$select": "unique_key, descriptor, created_date, incident_address, status",
        "$where": where,
        "$order": "created_date desc",
        "$limit": str(limit),
    }, timeout=60)
    r.raise_for_status()
    return [
        Complaint(
            unique_key=row.get("unique_key", ""),
            descriptor=row.get("descriptor", ""),
            created_date=row.get("created_date", ""),
            address=row.get("incident_address"),
            status=row.get("status"),
        )
        for row in r.json()
    ]


def summary_for_polygon(polygon, polygon_crs: str = "EPSG:4326",
                        years: int = 5) -> dict:
    """Polygon-mode aggregation: counts of flood-related 311 complaints
    inside the polygon over the trailing window."""
    since = datetime.now(timezone.utc) - timedelta(days=365 * years)
    cs = complaints_in_polygon(polygon, polygon_crs=polygon_crs, since=since)
    return _summarize(cs, years=years, radius_m=None)


def _summarize(cs: list[Complaint], years: int, radius_m: float | None) -> dict:
    by_year: Counter = Counter(c.created_date[:4] for c in cs if c.created_date)
    by_descriptor: Counter = Counter(c.descriptor for c in cs)
    # Cap at 60 most-recent points for the map layer — keeps the SSE
    # payload small while still showing meaningful clustering.
    points = [
        {"lat": c.lat, "lon": c.lon,
         "descriptor": c.descriptor,
         "date": c.created_date[:10],
         "address": c.address}
        for c in cs[:60]
        if c.lat is not None and c.lon is not None
    ]
    n = len(cs)
    by_year_sorted = dict(sorted(by_year.items()))
    by_descriptor_top = dict(by_descriptor.most_common(6))
    top_descriptor = next(iter(by_descriptor_top), None) if by_descriptor_top else None
    radius_str = f"{radius_m:.0f} m" if radius_m else "the NTA"
    if n == 0:
        narrative = (
            f"No NYC 311 flood-related complaints filed within {radius_str} "
            f"of this location in the last {years} years."
        )
    else:
        narrative = (
            f"{n} NYC 311 flood-related complaint{'s' if n != 1 else ''} "
            f"filed within {radius_str} of this location in the last "
            f"{years} years."
        )
        if top_descriptor:
            narrative += f" Most common descriptor: {top_descriptor}."
    return {
        "n": n,
        "radius_m": radius_m,
        "years": years,
        "by_year": by_year_sorted,
        "by_descriptor": by_descriptor_top,
        "most_recent": [
            {"date": c.created_date[:10],
             "descriptor": c.descriptor,
             "address": c.address}
            for c in cs[:5]
        ],
        "points": points,
        # Normalized rendering fields the type-keyed histogram renderer
        # reads. `histogram` is the array the chart draws; `headline_value`
        # is the bold figure; `subhead_text` is the descriptor caption.
        "headline_value": f"{n} call{'s' if n != 1 else ''}",
        "subhead_text": (f"top descriptor: {top_descriptor}"
                         if top_descriptor else "all flood-related descriptors"),
        "narrative": narrative,
        "histogram": list(by_year_sorted.values()) or [],
    }
