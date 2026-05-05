"""NYC address geocoding via the city's public Geosupport service (no key).

Uses NYC Department of City Planning's Geoclient-replacement via the open
Geosearch API (geosearch.planninglabs.nyc) — no auth required, NYC-only,
runs against the public service. Stays inside the "open civic data" lane.

Includes a borough-hint post-filter so Queens hyphenated-style addresses
(e.g. "153-09 90 Ave, Jamaica, Queens") preferentially resolve to the
borough the user named.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

URL = "https://geosearch.planninglabs.nyc/v2/search"

_BOROUGHS = ("Manhattan", "Bronx", "Brooklyn", "Queens", "Staten Island")


def _detect_borough(text: str) -> str | None:
    t = text.lower()
    for b in _BOROUGHS:
        if b.lower() in t:
            return b
    # neighborhood -> borough hints (incomplete but covers our demo set)
    hints = {
        "queens": "Queens",
        "jamaica": "Queens", "hollis": "Queens", "rockaway": "Queens",
        "elmhurst": "Queens", "maspeth": "Queens", "ozone park": "Queens",
        "astoria": "Queens", "flushing": "Queens", "edgemere": "Queens",
        "manhattan": "Manhattan", "harlem": "Manhattan", "soho": "Manhattan",
        "tribeca": "Manhattan", "midtown": "Manhattan", "les": "Manhattan",
        "chelsea": "Manhattan", "noho": "Manhattan",
        "brooklyn": "Brooklyn", "bushwick": "Brooklyn",
        "carroll gardens": "Brooklyn", "gowanus": "Brooklyn",
        "park slope": "Brooklyn", "williamsburg": "Brooklyn",
        "coney island": "Brooklyn", "red hook": "Brooklyn",
        "bronx": "Bronx", "fordham": "Bronx", "riverdale": "Bronx",
        "staten island": "Staten Island", "richmond": "Staten Island",
    }
    for needle, boro in hints.items():
        if needle in t:
            return boro
    return None


@dataclass
class GeocodeHit:
    address: str
    borough: str | None
    lat: float
    lon: float
    bbl: str | None
    bin: str | None
    raw: dict


def geocode(text: str, limit: int = 5) -> list[GeocodeHit]:
    """Return up to `limit` candidates from Geosearch, ranked by API order."""
    r = httpx.get(URL, params={"text": text, "size": limit}, timeout=15)
    r.raise_for_status()
    feats = r.json().get("features", [])
    out = []
    for f in feats:
        p = f.get("properties", {})
        coords = (f.get("geometry") or {}).get("coordinates") or [None, None]
        out.append(GeocodeHit(
            address=p.get("label") or p.get("name") or text,
            borough=p.get("borough"),
            lat=coords[1],
            lon=coords[0],
            bbl=p.get("addendum", {}).get("pad", {}).get("bbl"),
            bin=p.get("addendum", {}).get("pad", {}).get("bin"),
            raw=p,
        ))
    return out


def geocode_one(text: str) -> GeocodeHit | None:
    """Return the best NYC match for `text`. If the user mentions a
    borough or neighborhood we recognize, filter candidates to that
    borough before picking the top hit. Avoids `183-12 Liberty Avenue,
    Queens` resolving to a Brooklyn match the API surfaced first."""
    hint = _detect_borough(text)
    hits = geocode(text, limit=8)
    if hint:
        in_boro = [h for h in hits if h.borough and h.borough.lower() == hint.lower()]
        if in_boro:
            return in_boro[0]
    return hits[0] if hits else None
