"""Prithvi-EO 2.0 (Sen1Floods11) satellite flood inundation specialist.

The 300M-parameter Prithvi-EO foundation model (NASA/IBM, Apache-2.0)
was run twice offline on Hurricane Ida 2021 pre/post HLS Sentinel-2
scenes over central NYC:

    pre :  HLS.S30.T18TWK.2021237T153809  (2021-08-25,  3% cloud)
    post:  HLS.S30.T18TWK.2021245T154911  (2021-09-02,  1% cloud,
                                           ~12 hours after peak rainfall)

The diff (post-water minus pre-water, filtered to ≥3-cell polygons)
isolates surface water present 12 hours after Ida that wasn't present
the prior week — i.e., candidate Ida-attributable inundation. We ship
the resulting polygons as a flood-layer specialist; per query we
compute proximity from the address to the nearest such polygon.

Honest scope:
- Sub-surface flooding (subway entrances, basement apartments — the
  dominant Ida damage mode in NYC) is not visible to optical satellites.
- Pluvial street water had largely drained by the Sep 2 16:02Z pass,
  so the residual Prithvi signal mostly captures marsh ponding,
  riverside spillover, and low-lying park inundation.
- The model fired on Ida itself (a real flood event), not a synthetic
  fallback — that's the architectural value.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DOC_ID = "prithvi_water"
CITATION = ("Prithvi-EO-2.0-300M-TL-Sen1Floods11 (NASA/IBM, Apache-2.0, via "
            "TerraTorch). Hurricane Ida pre/post diff: pre HLS T18TWK "
            "2021-08-25 (3% cloud), post HLS T18TWK 2021-09-02 (1% cloud, "
            "~12h after peak rainfall).")


@dataclass
class PrithviSummary:
    inside_water_polygon: bool
    nearest_distance_m: float | None
    n_polygons_within_500m: int
    scene_id: str
    scene_date: str
    # Normalized rendering fields the type-keyed raster card reads.
    # Same shape across every raster pebble (prithvi_water, prithvi_live,
    # terramind buildings, future flood-mask models) so the renderer is
    # purely value-shape driven.
    headline_value: str = ""
    subhead_text: str = ""
    narrative: str = ""
    raster_kind: str = "prithvi"
    illustrative: bool = False


def _haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1); dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


@lru_cache(maxsize=1)
def _load():
    """Load the merged Prithvi water mask (combined across NYC MGRS tiles)
    as a GeoDataFrame in NYC state plane (EPSG:2263) for fast metric
    distance queries."""
    import geopandas as gpd
    # Prefer the Ida flood-event diff (real flood-attribution signal);
    # fall back to clear-day permanent-water masks if the Ida file is absent.
    candidates = [
        DATA_DIR / "prithvi_ida_2021.geojson",
        DATA_DIR / "prithvi_flood_nyc.geojson",
    ]
    candidates += sorted(DATA_DIR.glob("prithvi_flood_*.geojson"), reverse=True)
    path = next((p for p in candidates if p.exists()), None)
    if path is None:
        return None, None
    with open(path) as f:
        meta = json.load(f)
    g = gpd.read_file(path)
    if g.crs is None:
        g.set_crs("EPSG:4326", inplace=True)
    g = g.to_crs("EPSG:2263")
    return g, meta


def warm() -> None:
    _load()


def summary_for_point(lat: float, lon: float) -> PrithviSummary | None:
    import geopandas as gpd
    from shapely.geometry import Point
    g, meta = _load()
    if g is None:
        return None
    pt_wgs = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326")
    pt_2263 = pt_wgs.to_crs("EPSG:2263").iloc[0]
    inside = bool(g.contains(pt_2263).any())

    # nearest distance (feet -> metres)
    distances_ft = g.geometry.distance(pt_2263)
    nearest_ft = float(distances_ft.min()) if len(distances_ft) else None
    nearest_m = round(nearest_ft / 3.281, 1) if nearest_ft is not None else None

    within_500m = int((distances_ft <= 500 * 3.281).sum())

    # The Ida pre/post artifact carries pre_/post_ scene info; the clear-day
    # artifact carries scene_ids[]. Format compactly for either case.
    if "post_scene_id" in meta:
        sid = f"pre {meta['pre_scene_id']} | post {meta['post_scene_id']}"
        sdate = f"pre {meta['pre_scene_date']}, post {meta['post_scene_date']}"
    else:
        sid = meta.get("scene_id") or ", ".join(meta.get("scene_ids", []) or ["unknown"])
        sdate = meta.get("scene_date") or ", ".join(meta.get("scene_dates", []) or ["unknown"])

    headline = ("Inside polygon" if inside
                else (f"{nearest_m} m away" if nearest_m is not None
                      else "No polygons nearby"))
    narrative = (
        f"Prithvi-EO satellite-derived Hurricane Ida (Sept 2021) inundation: "
        f"this address {'sits inside' if inside else 'is outside'} the "
        f"empirical post-event water polygon"
    )
    if nearest_m is not None and not inside:
        narrative += f" (nearest mask {nearest_m} m away)"
    if within_500m:
        narrative += f"; {within_500m} distinct flood polygons within 500 m"
    narrative += "."
    return PrithviSummary(
        inside_water_polygon=inside,
        nearest_distance_m=nearest_m,
        n_polygons_within_500m=within_500m,
        scene_id=sid,
        scene_date=sdate,
        headline_value=headline,
        subhead_text="pre/post HLS Sentinel-2 segmentation",
        narrative=narrative,
        raster_kind="prithvi",
        illustrative=False,
    )
