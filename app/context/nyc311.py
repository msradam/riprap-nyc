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


def complaints_near(lat: float, lon: float, radius_m: float = 200,
                    since: datetime | None = None,
                    limit: int = 1000) -> list[Complaint]:
    where = f"{_DESC_CLAUSE} AND within_circle(location, {lat}, {lon}, {radius_m})"
    if since:
        # Socrata floating-timestamp: drop tz suffix
        ts = since.replace(tzinfo=None).isoformat(timespec="seconds")
        where += f" AND created_date >= '{ts}'"
    r = httpx.get(URL, params={
        "$select": "unique_key, descriptor, created_date, incident_address, status",
        "$where": where,
        "$order": "created_date desc",
        "$limit": str(limit),
    }, timeout=30)
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


def summary_for_point(lat: float, lon: float, radius_m: float = 200,
                      years: int = 5) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=365 * years)
    cs = complaints_near(lat, lon, radius_m, since=since, limit=2000)
    by_year: Counter = Counter(c.created_date[:4] for c in cs if c.created_date)
    by_descriptor: Counter = Counter(c.descriptor for c in cs)
    return {
        "n": len(cs),
        "radius_m": radius_m,
        "years": years,
        "by_year": dict(sorted(by_year.items())),
        "by_descriptor": dict(by_descriptor.most_common(6)),
        "most_recent": [
            {"date": c.created_date[:10],
             "descriptor": c.descriptor,
             "address": c.address}
            for c in cs[:5]
        ],
    }
