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
NOMINATIM_UA = "Riprap-NYC/0.1 (civic-flood-tool; +https://huggingface.co/spaces/msradam/riprap-nyc)"

# NYC-bbox guard: lat 40.49–40.92, lon -74.27 to -73.69. Anything outside
# this is probably not NYC; treat NYC Geosearch hits outside it as bogus.
NYC_BBOX = (40.49, -74.27, 40.92, -73.69)

# NYC ZIP prefixes are 100–104 (Manhattan), 110 (Queens), 112 (Brooklyn),
# 113 (Queens), 114 (Queens), 116 (Queens), 100 (Bronx 104), 103 (SI 1),
# basically all 1x with 3rd char 0–6. Upstate NY is 12x, 13x, 14x. We use
# this only as a HINT to escalate to Nominatim, not as a hard filter.
_UPSTATE_ZIP_RE = re.compile(r"\b1[2-4]\d{3}\b")
_NON_NYC_HINTS = re.compile(
    r"\b(albany|troy|schenectady|saratoga|kingston|poughkeepsie|newburgh|"
    r"yonkers|white plains|hudson|rhinebeck|peekskill|beacon|tarrytown|"
    r"new paltz|catskill|tivoli|hyde park|coxsackie|cohoes|amsterdam|"
    r"glens falls|lake george|nyack|garrison|cold spring|highland|saugerties)\b",
    re.IGNORECASE,
)

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


def _looks_upstate(text: str) -> bool:
    """Heuristic: should this query bypass NYC Geosearch?"""
    if _UPSTATE_ZIP_RE.search(text):
        return True
    if _NON_NYC_HINTS.search(text):
        return True
    return False


def _in_nyc_bbox(lat: float, lon: float) -> bool:
    s, w, n, e = NYC_BBOX
    return s <= lat <= n and w <= lon <= e


def geocode_nominatim(text: str) -> GeocodeHit | None:
    """National OSM Nominatim fallback. Used when NYC Geosearch can't
    plausibly answer the query."""
    try:
        r = httpx.get(NOMINATIM_URL, params={
            "q": text, "format": "jsonv2", "addressdetails": "1",
            "limit": 1, "countrycodes": "us",
        }, headers={"User-Agent": NOMINATIM_UA}, timeout=10)
        r.raise_for_status()
        rows = r.json()
    except Exception as e:
        log.warning("Nominatim fetch failed: %r", e)
        return None
    if not rows:
        return None
    row = rows[0]
    addr = row.get("address") or {}
    label = row.get("display_name") or text
    return GeocodeHit(
        address=label,
        borough=addr.get("city") or addr.get("town") or addr.get("village") or addr.get("county"),
        lat=float(row["lat"]),
        lon=float(row["lon"]),
        bbl=None,
        bin=None,
        raw={"source": "nominatim", **row},
    )


def geocode_one(text: str) -> GeocodeHit | None:
    """Best match for `text`, using NYC Geosearch primary with a national
    OSM Nominatim fallback for upstate / non-NYC queries.

    Strategy:
      1. If query mentions a known non-NYC city or has an upstate ZIP,
         go straight to Nominatim — Geosearch will silently fuzzy-snap
         '257 Washington Ave, Albany' to Clinton Hill Brooklyn otherwise.
      2. Otherwise try Geosearch with the borough-hint post-filter.
      3. If Geosearch returns nothing OR returns a hit outside the NYC
         bbox (which means even Geosearch knows it isn't NYC), escalate
         to Nominatim.
    """
    if _looks_upstate(text):
        log.info("upstate hint detected in %r — using Nominatim", text)
        hit = geocode_nominatim(text)
        if hit:
            return hit

    hint = _detect_borough(text)
    try:
        hits = geocode(text, limit=8)
    except Exception as e:
        # Geosearch is unreachable or returned a server error — fall back to
        # Nominatim rather than surfacing a 503 to every downstream specialist.
        log.warning("Geosearch unavailable (%r) — falling back to Nominatim", e)
        return geocode_nominatim(text)
    if hint:
        in_boro = [h for h in hits if h.borough and h.borough.lower() == hint.lower()]
        if in_boro:
            return in_boro[0]

    if hits:
        top = hits[0]
        if top.lat is not None and _in_nyc_bbox(top.lat, top.lon):
            return top
        # Geosearch returned a hit, but it's outside the NYC bbox — that
        # means even the NYC API thinks the answer isn't NYC. Try
        # Nominatim before giving up.
        log.info("Geosearch top hit outside NYC bbox (%s, %s) — falling back",
                 top.lat, top.lon)

    return geocode_nominatim(text)
