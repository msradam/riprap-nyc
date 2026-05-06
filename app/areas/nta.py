"""NYC Neighborhood Tabulation Area (NTA 2020) resolver.

NTAs are NYC Department of City Planning's official neighborhood unit:
~262 polygons covering all 5 boroughs, including some park / airport
slivers. They are the canonical "neighborhood" unit for NYC civic data.

This module provides:
  - load() → GeoDataFrame with all NTAs (cached)
  - resolve(name) → list of matching NTAs by fuzzy name match, or by borough
  - by_code(code) → exact lookup
  - polygon_for(code) → shapely Polygon in EPSG:4326
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import geopandas as gpd
from shapely.geometry import Polygon

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "nyc_ntas_2020.geojson"

# Common alias map: user-typed strings → canonical NTA names. We don't need to
# be exhaustive here; the fuzzy matcher catches most cases. This handles the
# few hard ones where the official NTA name differs from local usage.
ALIASES = {
    "the rockaways":    "Rockaway Beach-Arverne-Edgemere",
    "rockaway":         "Rockaway Beach-Arverne-Edgemere",
    "brighton":         "Brighton Beach",
    "lower east side":  "Lower East Side",
    "les":              "Lower East Side",
    "soho":             "SoHo-Little Italy-Hudson Square",
    "tribeca":          "Tribeca-Civic Center",
    "fidi":             "Financial District-Battery Park City",
    "downtown brooklyn":"Downtown Brooklyn-DUMBO-Boerum Hill",
    "dumbo":            "Downtown Brooklyn-DUMBO-Boerum Hill",
    "park slope":       "Park Slope",
    "carroll gardens":  "Carroll Gardens-Cobble Hill-Gowanus-Red Hook",
    "red hook":         "Carroll Gardens-Cobble Hill-Gowanus-Red Hook",
    "gowanus":          "Carroll Gardens-Cobble Hill-Gowanus-Red Hook",
    "hollis":           "Queens Village-Hollis-Bellerose",
    "long island city": "Hunters Point-Sunnyside-West Maspeth",
    "lic":              "Hunters Point-Sunnyside-West Maspeth",
    "astoria":          "Astoria (Central)",
    "flushing":         "Flushing-Willets Point",
    "harlem":           "Central Harlem (North)",
    "east harlem":      "East Harlem (North)",
    "washington heights":"Washington Heights (North)",
    "midtown":          "Midtown South-Flatiron-Union Square",
    "upper east side":  "Upper East Side-Carnegie Hill",
    "ues":              "Upper East Side-Carnegie Hill",
    "upper west side":  "Upper West Side-Lincoln Square",
    "uws":              "Upper West Side-Lincoln Square",
    "coney island":     "Coney Island-Sea Gate",
}

BOROUGH_NORMALIZE = {
    "manhattan": "Manhattan", "mn": "Manhattan",
    "brooklyn":  "Brooklyn",  "bk": "Brooklyn",  "kings": "Brooklyn",
    "queens":    "Queens",    "qn": "Queens",
    "bronx":     "Bronx",     "the bronx": "Bronx", "bx": "Bronx",
    "staten island": "Staten Island", "si": "Staten Island", "richmond": "Staten Island",
}


def _normalize(s: str) -> str:
    return re.sub(r"[^a-z]+", "", (s or "").lower())


@lru_cache(maxsize=1)
def load() -> gpd.GeoDataFrame:
    """Load the NTA 2020 GeoJSON; coerce CRS to EPSG:4326. Cached."""
    g = gpd.read_file(DATA_PATH)
    if g.crs is None or g.crs.to_string() != "EPSG:4326":
        g = g.to_crs("EPSG:4326")
    return g


def by_code(code: str) -> dict | None:
    g = load()
    hit = g[g["nta2020"] == code]
    if hit.empty:
        return None
    return _row_to_dict(hit.iloc[0])


def _row_to_dict(row) -> dict:
    return {
        "nta_code":  row["nta2020"],
        "nta_name":  row["ntaname"],
        "borough":   row["boroname"],
        "cdta":      row.get("cdtaname"),
        "geometry":  row["geometry"],
    }


def borough_match(query: str) -> str | None:
    """If query matches a borough name (or common abbreviation), return the
    canonical name. Otherwise return None."""
    q = query.strip().lower()
    return BOROUGH_NORMALIZE.get(q)


def resolve(query: str) -> list[dict[str, Any]]:
    """Resolve a free-text query to NTA(s).

    Strategy (in priority order):
      1. Borough match → all NTAs in borough.
      2. Alias map → exact NTA name match.
      3. Case-insensitive EXACT name match (so 'Kew Gardens' wins over
         'Kew Gardens Hills' when both exist).
      4. Substring match on normalized NTA name. When multiple match,
         prefer the one whose normalized name length is closest to the
         query — avoids 'Kew Gardens' resolving to 'Kew Gardens Hills'.
      5. CDTA-name substring fallback.
    """
    g = load()
    q = (query or "").strip()
    if not q:
        return []
    boro = borough_match(q)
    if boro:
        hits = g[g["boroname"] == boro]
        return [_row_to_dict(r) for _, r in hits.iterrows()]

    alias = ALIASES.get(q.lower())
    if alias:
        hits = g[g["ntaname"] == alias]
        if not hits.empty:
            return [_row_to_dict(r) for _, r in hits.iterrows()]

    # Exact (case-insensitive) — preferred over substring
    name_lower = g["ntaname"].fillna("").str.lower()
    exact = g[name_lower == q.lower()]
    if not exact.empty:
        return [_row_to_dict(r) for _, r in exact.iterrows()]

    qn = _normalize(q)
    if not qn:
        return []
    name_norm = g["ntaname"].fillna("").map(_normalize)
    contains = g[name_norm.str.contains(qn, na=False)].copy()
    if not contains.empty:
        contains["_diff"] = contains["ntaname"].fillna("").map(
            lambda s: abs(len(_normalize(s)) - len(qn))
        )
        contains = contains.sort_values("_diff")
        return [_row_to_dict(r) for _, r in contains.iterrows()]

    cdta_norm = g["cdtaname"].fillna("").map(_normalize)
    contains = g[cdta_norm.str.contains(qn, na=False)]
    if not contains.empty:
        return [_row_to_dict(r) for _, r in contains.iterrows()]

    return []


def polygon_for(code: str) -> Polygon | None:
    hit = by_code(code)
    return hit["geometry"] if hit else None


def resolve_from_text(text: str) -> list[dict[str, Any]]:  # TODO(cleanup): cc-grade-D (25)
    """Scan free-text (e.g. a full natural-language query) for any known NTA
    name, alias, or borough. Returns the first match. This is the fallback
    when the planner failed to extract a clean target.

    Strategy: walk ALIASES first (cheap), then iterate NTA names and look
    for the longest match contained in the text. We prefer the longest
    match so 'Carroll Gardens' wins over 'Gardens'.
    """
    t = (text or "").lower()
    if not t:
        return []
    # Boroughs first (whole-word-ish — avoid false hits inside "queensland" etc.)
    for boro_key, canon in BOROUGH_NORMALIZE.items():
        if f" {boro_key} " in f" {t} " or t.startswith(boro_key + " ") or t.endswith(" " + boro_key):
            hits = resolve(canon)
            if hits:
                return hits
    # Alias keys, longest first
    for key in sorted(ALIASES.keys(), key=len, reverse=True):
        if key in t:
            hits = resolve(key)
            if hits:
                return hits
    # NTA names. Order: longest first so multi-word names match before
    # shorter substrings, AND preferring the WORD-BOUNDARY match so
    # "Kew Gardens" in the query doesn't collide with "Kew Gardens Hills"
    # (the latter is longer; without word-boundary checking it'd match
    # nothing, but with substring-in-text it'd match if the query ever
    # contained the longer phrase). Caller picks the closest-length match.
    g = load()
    names = sorted(set(g["ntaname"].dropna().str.lower().tolist()), key=len, reverse=True)
    matches = []
    for name in names:
        if not name or len(name) < 4:
            continue
        # Word-boundary-ish check: name must appear bounded by start/end or
        # whitespace/punct (so "kew gardens hills" matches but "kew gardens"
        # alone doesn't trigger "kew gardens hills" because of the trailing
        # space requirement).
        padded_t = f" {t} "
        if f" {name} " in padded_t or f" {name}." in padded_t or f" {name}," in padded_t or f" {name}?" in padded_t:
            matches.append(name)
    if matches:
        # Prefer the longest word-boundary match — most specific.
        best = sorted(matches, key=len, reverse=True)[0]
        hits = resolve(best)
        if hits:
            return hits
    # Fallback: any substring (no boundary). Less precise, but catches
    # casual queries like "show me red hook" where "red hook" is a
    # neighborhood-name fragment within a longer NTA name.
    for name in names:
        if not name or len(name) < 4:
            continue
        if name in t:
            hits = resolve(name)
            if hits:
                return hits
    return []
