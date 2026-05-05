"""nycha_development_exposure — flood-exposure briefing per NYCHA development.

Same pattern as the MTA-entrance specialist, but NYCHA developments are
*polygons* not points, so the metrics shift to overlap fractions:

  - % of footprint inside the 2012 Sandy Inundation Zone (empirical)
  - % of footprint inside DEP Extreme-2080 / Moderate-2050 scenarios
    (modeled, broken out by depth class)
  - Representative-point elevation, HAND, TWI (proxy)
  - Footprint area (km²)
  - Distance from query point to development boundary

Joins:
  - data/nycha.geojson  (NYC Open Data, 218 NYCHA developments)
  - data/sandy_inundation.geojson
  - DEP Stormwater Flood Map polygons (3 scenarios)
  - data/nyc_dem_30m.tif, data/hand.tif

Per queried (lat, lon), returns developments whose centroid is within
the radius (default 2000 m — NYCHA developments are sparser than
subway entrances, so the radius is wider).

Honest scope:
  - This is exposure, not damage forecast. We say "85% of this
    development's footprint is inside the 2012 Sandy zone" — not
    "this development will flood next storm".
  - All overlap fractions are computed in EPSG:2263 (NYC State Plane,
    feet) for accurate area arithmetic in the city.
"""

from __future__ import annotations

import json
import logging
import math
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

log = logging.getLogger("riprap.nycha")

DATA = _ROOT / "data"
NYCHA = DATA / "nycha.geojson"

DEFAULT_RADIUS_M = 2000
DEFAULT_MAX_PER_QUERY = 5


@dataclass
class DevelopmentFinding:
    development: str
    tds_num: str
    borough: str
    centroid_lat: float
    centroid_lon: float
    distance_m: float
    footprint_km2: float
    rep_elevation_m: float | None
    rep_hand_m: float | None
    pct_inside_sandy_2012: float
    pct_in_dep_extreme_2080: float       # any-depth (class>=1)
    pct_in_dep_extreme_2080_deep: float  # class==3 only ("Deep Contiguous")
    pct_in_dep_moderate_2050: float


@lru_cache(maxsize=1)
def _load_nycha():
    import geopandas as gpd
    gdf = gpd.read_file(NYCHA).to_crs("EPSG:2263")  # feet, accurate areas
    gdf["centroid_2263"] = gdf.geometry.centroid
    return gdf.reset_index(drop=True)


@lru_cache(maxsize=1)
def _load_sandy_2263():
    """Load the Sandy zone in EPSG:2263 once. Already used by
    app.flood_layers.sandy_inundation but we want the geometry directly
    for overlap-fraction math."""
    import geopandas as gpd
    g = gpd.read_file(DATA / "sandy_inundation.geojson").to_crs("EPSG:2263")
    # Some NYC OEM Sandy polygons have hole-orientation issues that
    # blow up unary_union. buffer(0) fixes self-intersections without
    # changing the footprint at sub-foot precision.
    g["geometry"] = g.geometry.buffer(0)
    return g.geometry.union_all()


@lru_cache(maxsize=4)
def _load_dep_2263(scenario: str):
    """DEP scenario polygons in EPSG:2263, with depth_class column."""
    import geopandas as gpd
    p = DATA / "dep" / f"{scenario}.geojson"
    if not p.exists():
        # Fallback to whatever the existing dep_stormwater module loaded.
        from app.flood_layers import dep_stormwater
        gdf = dep_stormwater.load(scenario)
        return gdf.to_crs("EPSG:2263") if gdf.crs is not None else gdf
    return gpd.read_file(p).to_crs("EPSG:2263")


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1); dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _sample_raster(raster_path: Path, lat: float, lon: float) -> float | None:
    if not raster_path.exists():
        return None
    try:
        import rasterio
        with rasterio.open(raster_path) as src:
            v = next(src.sample([(lon, lat)]))[0]
            v = float(v)
            if math.isnan(v) or v == src.nodata:
                return None
            return v
    except Exception:
        log.exception("raster sample failed for %s", raster_path)
        return None


def _developments_near(lat: float, lon: float, radius_m: float):
    """Return developments whose centroid is within `radius_m` of
    (lat, lon). Uses haversine on centroids re-projected back to
    EPSG:4326 — the bbox prefilter gets us close, then exact distance."""
    import geopandas as gpd
    gdf = _load_nycha()
    # Re-project centroids to 4326 for haversine
    cents_4326 = gpd.GeoSeries(gdf["centroid_2263"], crs="EPSG:2263").to_crs("EPSG:4326")
    deg = radius_m / 90_000
    cent_lat = cents_4326.y
    cent_lon = cents_4326.x
    mask = ((cent_lat >= lat - deg) & (cent_lat <= lat + deg)
            & (cent_lon >= lon - deg) & (cent_lon <= lon + deg))
    sub = gdf[mask].copy()
    if sub.empty:
        return sub, []
    sub["clat"] = cent_lat[mask].values
    sub["clon"] = cent_lon[mask].values
    sub["distance_m"] = sub.apply(
        lambda r: _haversine_m(lat, lon, r["clat"], r["clon"]),
        axis=1,
    )
    sub = sub[sub["distance_m"] <= radius_m].sort_values("distance_m")
    return sub, sub.index.tolist()


def _overlap_pct(geom_2263, mask_geom_2263) -> float:
    """% of geom_2263's area that intersects mask_geom_2263."""
    if mask_geom_2263 is None or mask_geom_2263.is_empty:
        return 0.0
    inter = geom_2263.intersection(mask_geom_2263)
    if inter.is_empty:
        return 0.0
    return round(100.0 * inter.area / max(geom_2263.area, 1e-9), 2)


def _dep_overlap(geom_2263, scenario: str) -> tuple[float, float]:
    """Return (pct_any_depth, pct_deep_contiguous) of a polygon's area
    inside the DEP scenario."""
    try:
        gdf = _load_dep_2263(scenario)
    except Exception:
        log.exception("DEP load failed for %s", scenario)
        return 0.0, 0.0
    if gdf is None or gdf.empty:
        return 0.0, 0.0
    # Bbox-prefilter the DEP polygons to those near our development.
    minx, miny, maxx, maxy = geom_2263.bounds
    cand = gdf.cx[minx:maxx, miny:maxy]
    if cand.empty:
        return 0.0, 0.0
    # DEP NYC stormwater FGDB uses `Flooding_Category` (int16):
    # 1=nuisance, 2=shallow, 3=deep contiguous (>4 ft).
    cat_col = "Flooding_Category" if "Flooding_Category" in cand.columns else None
    any_geom = cand.geometry.buffer(0).union_all()
    if cat_col:
        deep = cand[cand[cat_col] == 3]
        deep_geom = deep.geometry.buffer(0).union_all() if not deep.empty else None
    else:
        deep_geom = None
    pct_any = _overlap_pct(geom_2263, any_geom)
    pct_deep = _overlap_pct(geom_2263, deep_geom) if deep_geom is not None else 0.0
    return pct_any, pct_deep


def summary_for_point(lat: float, lon: float,
                       radius_m: float = DEFAULT_RADIUS_M,
                       max_developments: int = DEFAULT_MAX_PER_QUERY) -> dict:
    near, _ = _developments_near(lat, lon, radius_m)
    if near.empty:
        return {"available": False,
                "n_developments": 0,
                "radius_m": radius_m,
                "developments": []}

    near = near.head(max_developments)
    sandy_2263 = _load_sandy_2263()

    findings: list[DevelopmentFinding] = []
    for _, row in near.iterrows():
        geom = row.geometry
        # Representative interior point gives a more meaningful elevation
        # than the centroid for irregular development footprints.
        rep = geom.representative_point()
        # Re-project the rep point to 4326 for raster sampling
        import geopandas as gpd
        rep_4326 = gpd.GeoSeries([rep], crs="EPSG:2263").to_crs("EPSG:4326").iloc[0]
        rep_lat, rep_lon = rep_4326.y, rep_4326.x

        elev = _sample_raster(DATA / "nyc_dem_30m.tif", rep_lat, rep_lon)
        hand = _sample_raster(DATA / "hand.tif", rep_lat, rep_lon)
        pct_sandy = _overlap_pct(geom, sandy_2263)
        pct_2080_any, pct_2080_deep = _dep_overlap(geom, "dep_extreme_2080")
        pct_2050_any, _ = _dep_overlap(geom, "dep_moderate_2050")

        findings.append(DevelopmentFinding(
            development=str(row["developmen"]),
            tds_num=str(row["tds_num"]),
            borough=str(row["borough"]),
            centroid_lat=round(float(row["clat"]), 5),
            centroid_lon=round(float(row["clon"]), 5),
            distance_m=round(float(row["distance_m"]), 1),
            footprint_km2=round(geom.area / 10.7639 / 1_000_000, 4),  # sq-ft -> km²
            rep_elevation_m=round(elev, 2) if elev is not None else None,
            rep_hand_m=round(hand, 2) if hand is not None else None,
            pct_inside_sandy_2012=pct_sandy,
            pct_in_dep_extreme_2080=pct_2080_any,
            pct_in_dep_extreme_2080_deep=pct_2080_deep,
            pct_in_dep_moderate_2050=pct_2050_any,
        ))

    n_majority_sandy = sum(1 for f in findings if f.pct_inside_sandy_2012 >= 50)
    n_any_2080 = sum(1 for f in findings if f.pct_in_dep_extreme_2080 > 0)
    return {
        "available": True,
        "n_developments": len(findings),
        "radius_m": radius_m,
        "n_majority_inside_sandy_2012": n_majority_sandy,
        "n_with_dep_2080_overlap": n_any_2080,
        "developments": [vars(f) for f in findings],
        "citation": ("NYC Open Data NYCHA Developments (phvi-damg) + "
                     "NYC OEM Sandy 2012 Inundation Zone (5xsi-dfpx) + "
                     "NYC DEP Stormwater Flood Maps + USGS 3DEP DEM"),
    }


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--radius", type=float, default=DEFAULT_RADIUS_M)
    ap.add_argument("--max", type=int, default=DEFAULT_MAX_PER_QUERY)
    args = ap.parse_args()
    s = summary_for_point(args.lat, args.lon, args.radius, args.max)
    print(json.dumps(s, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
