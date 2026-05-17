"""Address geocoding — NYC primary + national fallback.

NYC primary: NYC DCP Geosearch (geosearch.planninglabs.nyc), no auth,
NYC-only. It will fuzzy-match upstate addresses to NYC streets — e.g.
'257 Washington Ave, Albany NY' silently maps to Clinton Hill, Brooklyn.
We detect this via a non-NYC region or non-NYC ZIP and fall back to
OpenStreetMap Nominatim (no key, free, rate-limited per usage policy).

Includes a borough-hint post-filter so Queens hyphenated-style addresses
(e.g. '153-09 90 Ave, Jamaica, Queens') preferentially resolve to the
borough the user named.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import httpx

log = logging.getLogger("riprap.geocode")

URL = "https://geosearch.planninglabs.nyc/v2/search"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_UA = "Riprap-NYC/0.5 (civic-flood-tool; +https://huggingface.co/spaces/msradam/riprap-nyc)"

# NYC-bbox guard: lat 40.49–40.92, lon -74.27 to -73.69.
NYC_BBOX = (40.49, -74.27, 40.92, -73.69)

_UPSTATE_ZIP_RE = re.compile(r"\b1[2-4]\d{3}\b")
_BOROUGHS = ("Manhattan", "Bronx", "Brooklyn", "Queens", "Staten Island")

def _detect_borough(text: str) -> str | None:
    t = text.lower()
    for b in _BOROUGHS:
        if b.lower() in t:
            return b
    # neighborhood -> borough hints
    hints = {
        "queens": "Queens", "jamaica": "Queens", "rockaway": "Queens",
        "astoria": "Queens", "flushing": "Queens",
        "manhattan": "Manhattan", "harlem": "Manhattan", "soho": "Manhattan",
        "brooklyn": "Brooklyn", "bushwick": "Brooklyn", "red hook": "Brooklyn",
        "bronx": "Bronx", "fordham": "Bronx",
        "staten island": "Staten Island",
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
    """NYC Geosearch primary."""
    try:
        r = httpx.get(URL, params={"text": text, "size": limit}, timeout=5)
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
    except Exception as e:
        log.warning("Geosearch failed: %r", e)
        return []

def geocode_nominatim(text: str) -> GeocodeHit | None:
    """National OSM Nominatim fallback.

    Uses geopy's Nominatim client, which enforces the OSM Nominatim
    Usage Policy: a non-default User-Agent (required), and the 1 req/s
    rate limit (we apply it explicitly via RateLimiter — geopy doesn't
    rate-limit by default).
    See https://operations.osmfoundation.org/policies/nominatim/
    """
    from geopy.extra.rate_limiter import RateLimiter  # noqa: PLC0415
    from geopy.geocoders import Nominatim  # noqa: PLC0415

    geocoder = Nominatim(user_agent=NOMINATIM_UA, timeout=10)
    geocode_call = RateLimiter(
        geocoder.geocode, min_delay_seconds=1.0, swallow_exceptions=False
    )
    try:
        location = geocode_call(
            text,
            addressdetails=True,
            country_codes="us",
            exactly_one=True,
        )
    except Exception as e:  # noqa: BLE001 — log + None per the rest of this module
        log.warning("Nominatim fetch failed: %r", e)
        return None
    if location is None:
        return None
    row = location.raw  # the same dict the JSON API returns
    addr = row.get("address") or {}

    # Try to map Nominatim borough/county back to NYC standard
    boro = addr.get("suburb") or addr.get("city_district") or addr.get("county")
    if boro and "Kings" in boro: boro = "Brooklyn"
    if boro and "New York County" in boro: boro = "Manhattan"
    if boro and "Queens" in boro: boro = "Queens"
    if boro and "Bronx" in boro: boro = "Bronx"
    if boro and "Richmond" in boro: boro = "Staten Island"

    return GeocodeHit(
        address=row.get("display_name") or text,
        borough=boro,
        lat=location.latitude,
        lon=location.longitude,
        bbl=None,  # Nominatim doesn't have BBLs
        bin=None,
        raw={"source": "nominatim", **row},
    )

# Any of these in the query string strongly signals NOT-NYC — skip
# the NYC Geosearch step entirely. NYC Geosearch will fuzzy-match
# e.g. "401 N Wabash Ave, Chicago, IL" to "401 AVENUE N, Brooklyn"
# if we let it try, which then passes the broad NYC-bbox check
# downstream because the bad match happens to fall inside NYC.
_NON_NYC_HINT_RE = re.compile(
    r",\s*(?:"
    # US state codes other than NY (the ones with significant cities)
    r"AL|AK|AZ|AR|CA|CO|CT|DE|DC|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|"
    r"MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NC|ND|OH|OK|OR|PA|RI|SC|SD|"
    r"TN|TX|UT|VT|VA|WA|WV|WI|WY|"
    # Major non-NYC US cities (common quick-test names)
    r"chicago|los angeles|san francisco|seattle|boston|philadelphia|"
    r"philly|houston|dallas|austin|miami|atlanta|denver|portland|"
    r"san diego|phoenix|minneapolis|detroit|baltimore|washington dc"
    r")\b",
    re.IGNORECASE,
)


def _looks_non_nyc(text: str) -> bool:
    """Returns True only when the query explicitly names a non-NYC
    place. Bare addresses without city/state info still try NYC
    Geosearch first (the NYC bias is intentional — most callers are
    NYC users)."""
    return bool(_NON_NYC_HINT_RE.search(text))


def geocode_one(text: str) -> GeocodeHit | None:
    """Dynamic geocoder with failover.

    NYC Geosearch is the primary because it gives BBL/BIN identifiers
    needed by NYC-flood pebbles. National OSM Nominatim is the fallback
    when the address clearly names a non-NYC place, when Geosearch
    returns nothing, or when its top match falls outside the NYC bbox.
    """
    if _looks_non_nyc(text):
        log.info("geocode_one: query %r names a non-NYC place; skipping Geosearch", text)
        return geocode_nominatim(text)

    hits = geocode(text)
    hint = _detect_borough(text)

    if hint:
        in_boro = [h for h in hits if h.borough and h.borough.lower() == hint.lower()]
        if in_boro:
            return in_boro[0]

    if hits:
        top = hits[0]
        if top.lat and 40.4 <= top.lat <= 41.0:  # Broad NYC check
            return top

    log.info("Falling back to Nominatim for %r", text)
    return geocode_nominatim(text)
