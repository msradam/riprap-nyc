"""mta_entrance_exposure — flood-exposure briefing per subway entrance.

The headline new specialist for the IBM senior technical staffer's
"subway entrances" reaction. Joins:

  - MTA Open Data subway-entrance geometry (data/mta_entrances.geojson,
    2120 entrances city-wide).
  - NYC OEM Sandy 2012 Inundation Zone (data/sandy_inundation.geojson)
    — empirical evidence (a flood actually happened here).
  - NYC DEP Stormwater Flood Maps for Extreme-2080, Moderate-2050,
    Moderate-current scenarios — modeled evidence.
  - USGS 3DEP DEM (data/nyc_dem_30m.tif) for entrance-level elevation.
  - HAND raster (data/hand.tif) for height above nearest drainage.
  - Entrance type → ADA-status heuristic (Elevator / Ramp = accessible).

Per queried address, returns the entrances within a configurable
radius (default 800 m) with structured per-entrance claims the
reconciler can cite. doc_id format: `mta_entrance_<station_id>`.

Honest scope (per Riprap discipline):
  - This is an EXPOSURE specialist, not a damage forecast. We say
    "this entrance sits inside the 2012 Sandy zone" — we don't say
    "this entrance will flood again in the next storm".
  - The Sandy / DEP layers are point-in-polygon over public-record
    geometry; ADA status from the MTA Open Data `entrance_type`
    column is a heuristic, not the authoritative MTA accessibility
    list.
  - Documented MTA Sandy-recovery records for specific stations are
    NOT included in this first cut — only the empirical-inundation
    membership. Adding station-level recovery citations requires
    parsing the MTA's "Hurricane Sandy: Three Years Later" report
    and is a follow-up.
"""

from __future__ import annotations

import json
import logging
import math
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# Ensure `app/` is importable when this experiment is invoked directly
# from its own subdir.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

log = logging.getLogger("riprap.mta_entrance")

DATA = Path(__file__).resolve().parents[2] / "data"
MTA_ENTRANCES = DATA / "mta_entrances.geojson"

ADA_ACCESSIBLE_TYPES = {"Elevator", "Ramp"}

DEFAULT_RADIUS_M = 800
DEFAULT_MAX_PER_QUERY = 8  # cap per station so doc payload stays small


@dataclass
class EntranceFinding:
    station_id: str
    station_name: str
    daytime_routes: str
    borough: str
    entrance_type: str
    entrance_lat: float
    entrance_lon: float
    distance_m: float
    ada_accessible: bool
    elevation_m: float | None
    hand_m: float | None  # height above nearest drainage
    inside_sandy_2012: bool
    dep_extreme_2080_class: int | None     # 0/1/2/3
    dep_extreme_2080_label: str | None
    dep_moderate_2050_class: int | None
    dep_moderate_2050_label: str | None


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1); dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


@lru_cache(maxsize=1)
def _load_entrances():
    import geopandas as gpd
    import pandas as pd
    gdf = gpd.read_file(MTA_ENTRANCES)
    # The lat/lon columns are strings in this GeoJSON; coerce so we
    # can do range comparisons in the bbox prefilter.
    gdf["entrance_latitude"] = pd.to_numeric(gdf["entrance_latitude"],
                                              errors="coerce")
    gdf["entrance_longitude"] = pd.to_numeric(gdf["entrance_longitude"],
                                                errors="coerce")
    gdf = gdf[gdf["entrance_latitude"].notna()
              & gdf["entrance_longitude"].notna()].copy()
    return gdf.reset_index(drop=True)


def _entrances_near(lat: float, lon: float, radius_m: float):
    gdf = _load_entrances()
    # Coarse bbox prefilter to avoid haversine on 2120 rows every call.
    deg = radius_m / 90_000  # generous degree padding at NYC latitude
    sub = gdf[
        (gdf["entrance_latitude"].between(lat - deg, lat + deg))
        & (gdf["entrance_longitude"].between(lon - deg, lon + deg))
    ].copy()
    if sub.empty:
        return sub
    sub["distance_m"] = sub.apply(
        lambda r: _haversine_m(lat, lon, r["entrance_latitude"],
                                 r["entrance_longitude"]),
        axis=1,
    )
    sub = sub[sub["distance_m"] <= radius_m].sort_values("distance_m")
    return sub


def _sample_raster(raster_path: Path, lat: float, lon: float) -> float | None:
    """Read one pixel from a raster at (lat, lon). Returns None if the
    point is outside the raster or the raster is missing.

    The cached NYC rasters are all EPSG:4326. rasterio.sample handles
    coordinate-to-pixel translation directly — simpler than building
    a windowed read."""
    if not raster_path.exists():
        return None
    try:
        import rasterio
        with rasterio.open(raster_path) as src:
            v = next(src.sample([(lon, lat)]))[0]
            if v is None:
                return None
            v = float(v)
            if math.isnan(v) or v == src.nodata:
                return None
            return v
    except Exception:
        log.exception("raster sample failed for %s", raster_path)
        return None


def _inside_sandy(lat: float, lon: float) -> bool:
    """Reuse Riprap's existing sandy specialist's join logic."""
    try:
        import geopandas as gpd
        from shapely.geometry import Point

        from app.flood_layers import sandy_inundation
        pt = gpd.GeoDataFrame(
            geometry=[Point(lon, lat)], crs="EPSG:4326"
        ).to_crs("EPSG:2263")
        return bool(sandy_inundation.join(pt).iloc[0])
    except Exception:
        log.exception("sandy join failed")
        return False


def _dep_class(lat: float, lon: float, scenario: str) -> tuple[int | None, str | None]:
    """Sample DEP stormwater scenario depth class at the point."""
    try:
        import geopandas as gpd
        from shapely.geometry import Point

        from app.flood_layers import dep_stormwater
        pt = gpd.GeoDataFrame(
            geometry=[Point(lon, lat)], crs="EPSG:4326"
        ).to_crs("EPSG:2263")
        j = dep_stormwater.join(pt, scenario).iloc[0]
        return int(j["depth_class"]), str(j["depth_label"])
    except Exception:
        log.exception("dep join failed for %s", scenario)
        return None, None


def summary_for_point(lat: float, lon: float,
                      radius_m: float = DEFAULT_RADIUS_M,
                      max_entrances: int = DEFAULT_MAX_PER_QUERY) -> dict:
    """Return all subway entrances within `radius_m` of (lat, lon),
    enriched with flood-exposure fields. Empty list when no entrances
    are nearby (silence over confabulation)."""
    near = _entrances_near(lat, lon, radius_m)
    if near.empty:
        return {"available": False,
                "n_entrances": 0,
                "radius_m": radius_m,
                "entrances": []}

    near = near.head(max_entrances)
    findings: list[EntranceFinding] = []
    for _, row in near.iterrows():
        elat, elon = float(row["entrance_latitude"]), float(row["entrance_longitude"])
        ada = str(row["entrance_type"]) in ADA_ACCESSIBLE_TYPES
        elev = _sample_raster(DATA / "nyc_dem_30m.tif", elat, elon)
        hand = _sample_raster(DATA / "hand.tif", elat, elon)
        in_sandy = _inside_sandy(elat, elon)
        dep_2080_class, dep_2080_label = _dep_class(elat, elon, "dep_extreme_2080")
        dep_2050_class, dep_2050_label = _dep_class(elat, elon, "dep_moderate_2050")
        findings.append(EntranceFinding(
            station_id=str(row["station_id"]),
            station_name=str(row["stop_name"]),
            daytime_routes=str(row["daytime_routes"]),
            borough=str(row["borough"]),
            entrance_type=str(row["entrance_type"]),
            entrance_lat=elat, entrance_lon=elon,
            distance_m=round(float(row["distance_m"]), 1),
            ada_accessible=ada,
            elevation_m=round(elev, 2) if elev is not None else None,
            hand_m=round(hand, 2) if hand is not None else None,
            inside_sandy_2012=in_sandy,
            dep_extreme_2080_class=dep_2080_class,
            dep_extreme_2080_label=dep_2080_label,
            dep_moderate_2050_class=dep_2050_class,
            dep_moderate_2050_label=dep_2050_label,
        ))

    # Citywide rollups across the returned entrances.
    n_in_sandy = sum(1 for f in findings if f.inside_sandy_2012)
    n_in_dep_2080 = sum(1 for f in findings
                          if (f.dep_extreme_2080_class or 0) > 0)
    n_ada = sum(1 for f in findings if f.ada_accessible)
    return {
        "available": True,
        "n_entrances": len(findings),
        "radius_m": radius_m,
        "n_inside_sandy_2012": n_in_sandy,
        "n_in_dep_extreme_2080": n_in_dep_2080,
        "n_ada_accessible": n_ada,
        "entrances": [vars(f) for f in findings],
        "citation": ("MTA Open Data subway entrances + NYC OEM Sandy 2012 "
                     "Inundation Zone (5xsi-dfpx) + NYC DEP Stormwater "
                     "Flood Maps + USGS 3DEP DEM"),
    }


def main() -> int:
    """CLI smoke test."""
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
    import sys
    sys.exit(main())
