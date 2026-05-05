"""Hurricane Ida (Sept 2021) empirical flood extent — USGS high-water marks.

This specialist plays the same role as Prithvi-EO 2.0 (Sen1Floods11)
in the parent triangulation-engine: it provides empirical post-event
flood evidence (versus the modeled scenarios from FEMA/DEP). Where
Prithvi derives extent from Sentinel-1 SAR, USGS HWMs are surveyed
ground-truth water marks. Both are valid empirical signals; HWMs
are the public record for Ida specifically.

Output per address: number of HWMs within radius, max water elevation
(ft), nearest site description.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent.parent / "data" / "ida_2021_hwms_ny.geojson"
DOC_ID = "ida_hwm"
CITATION = "USGS STN Hurricane Ida 2021 high-water marks (Event 312, NY)"


@dataclass
class HWMSummary:
    n_within_radius: int
    radius_m: int
    max_elev_ft: float | None
    max_height_above_gnd_ft: float | None
    nearest_dist_m: float | None
    nearest_site: str | None
    nearest_elev_ft: float | None
    sample_sites: list[str]
    points: list[dict] | None = None  # per-mark for the map layer


def _haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1); dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


@lru_cache(maxsize=1)
def _load() -> list[dict]:
    if not DATA.exists():
        return []
    with open(DATA) as f:
        return json.load(f).get("features", [])


def summary_for_point(lat: float, lon: float, radius_m: int = 1000) -> HWMSummary | None:
    feats = _load()
    if not feats:
        return None
    in_radius = []
    nearest = (None, float("inf"), None)
    for f in feats:
        flon, flat = f["geometry"]["coordinates"]
        d = _haversine_m(lat, lon, flat, flon)
        if d <= radius_m:
            in_radius.append((d, f))
        if d < nearest[1]:
            nearest = (f, d, None)
    nf, nd, _ = nearest
    elevs = [f["properties"].get("elev_ft") for _, f in in_radius
             if f["properties"].get("elev_ft") is not None]
    heights = [f["properties"].get("height_above_gnd") for _, f in in_radius
               if f["properties"].get("height_above_gnd") is not None]
    sites = [f["properties"].get("site_description") for _, f in in_radius]
    sites = [s for s in sites if s][:5]
    points = []
    for d, f in in_radius[:50]:  # cap so SSE payload stays small
        flon, flat = f["geometry"]["coordinates"]
        p = f["properties"]
        points.append({
            "lat": flat, "lon": flon,
            "site": p.get("site_description"),
            "elev_ft": p.get("elev_ft"),
            "height_above_gnd_ft": p.get("height_above_gnd"),
            "distance_m": round(d, 1),
        })
    return HWMSummary(
        n_within_radius=len(in_radius),
        radius_m=radius_m,
        max_elev_ft=round(max(elevs), 2) if elevs else None,
        max_height_above_gnd_ft=round(max(heights), 2) if heights else None,
        nearest_dist_m=round(nd, 0) if nf is not None else None,
        nearest_site=nf["properties"].get("site_description") if nf else None,
        nearest_elev_ft=nf["properties"].get("elev_ft") if nf else None,
        sample_sites=sites,
        points=points,
    )
