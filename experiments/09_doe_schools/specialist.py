"""doe_school_exposure — flood-exposure briefing per NYC public school.

Point-based register specialist (1992 NYC DOE school points). Same
join pattern as the MTA-entrance specialist. Per queried (lat, lon),
returns up to N schools within `radius_m`, enriched with:

  - inside_sandy_2012        (point-in-polygon, empirical)
  - dep_extreme_2080_class   (point-in-polygon, modeled)
  - dep_moderate_2050_class  (point-in-polygon, modeled)
  - elevation_m              (USGS 3DEP DEM, proxy)
  - hand_m                   (derived HAND raster, proxy)

doc_id format: `doe_school_<loc_code>`. Schools are physical
buildings that serve as evacuation hubs in city OEM plans, so
"this school sits inside the 2012 Sandy zone" is a structural
claim that's directly relevant to flood planning.
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

log = logging.getLogger("riprap.doe_school")

DATA = _ROOT / "data"
SCHOOLS = DATA / "schools.geojson"

DEFAULT_RADIUS_M = 1500
DEFAULT_MAX_PER_QUERY = 6

BORO_NAME = {"1": "MANHATTAN", "2": "BRONX", "3": "BROOKLYN",
             "4": "QUEENS", "5": "STATEN ISLAND"}

MANAGED_BY_LABEL = {"1": "DOE-managed", "2": "Charter or other"}


@dataclass
class SchoolFinding:
    loc_code: str
    loc_name: str
    address: str
    borough: str
    bin: str
    bbl: str
    managed_by: str
    school_lat: float
    school_lon: float
    distance_m: float
    elevation_m: float | None
    hand_m: float | None
    inside_sandy_2012: bool
    dep_extreme_2080_class: int | None
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
def _load_schools():
    import geopandas as gpd
    gdf = gpd.read_file(SCHOOLS)
    gdf["lat"] = gdf.geometry.y
    gdf["lon"] = gdf.geometry.x
    return gdf.reset_index(drop=True)


def _schools_near(lat: float, lon: float, radius_m: float):
    gdf = _load_schools()
    deg = radius_m / 90_000
    sub = gdf[(gdf["lat"].between(lat - deg, lat + deg))
              & (gdf["lon"].between(lon - deg, lon + deg))].copy()
    if sub.empty:
        return sub
    sub["distance_m"] = sub.apply(
        lambda r: _haversine_m(lat, lon, r["lat"], r["lon"]), axis=1)
    return sub[sub["distance_m"] <= radius_m].sort_values("distance_m")


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


def _inside_sandy(lat: float, lon: float) -> bool:
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


def _dep_class(lat: float, lon: float, scenario: str):
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
                       max_schools: int = DEFAULT_MAX_PER_QUERY) -> dict:
    near = _schools_near(lat, lon, radius_m)
    if near.empty:
        return {"available": False,
                "n_schools": 0,
                "radius_m": radius_m,
                "schools": []}

    near = near.head(max_schools)
    findings: list[SchoolFinding] = []
    for _, row in near.iterrows():
        slat, slon = float(row["lat"]), float(row["lon"])
        elev = _sample_raster(DATA / "nyc_dem_30m.tif", slat, slon)
        hand = _sample_raster(DATA / "hand.tif", slat, slon)
        in_sandy = _inside_sandy(slat, slon)
        d80c, d80l = _dep_class(slat, slon, "dep_extreme_2080")
        d50c, d50l = _dep_class(slat, slon, "dep_moderate_2050")
        boronum = str(row.get("boronum", ""))
        findings.append(SchoolFinding(
            loc_code=str(row["loc_code"]),
            loc_name=str(row["loc_name"]),
            address=str(row["address"]).strip(),
            borough=BORO_NAME.get(boronum, boronum),
            bin=str(row["bin"]),
            bbl=str(row["bbl"]),
            managed_by=MANAGED_BY_LABEL.get(str(row["managed_by"]),
                                              str(row["managed_by"])),
            school_lat=round(slat, 5),
            school_lon=round(slon, 5),
            distance_m=round(float(row["distance_m"]), 1),
            elevation_m=round(elev, 2) if elev is not None else None,
            hand_m=round(hand, 2) if hand is not None else None,
            inside_sandy_2012=in_sandy,
            dep_extreme_2080_class=d80c,
            dep_extreme_2080_label=d80l,
            dep_moderate_2050_class=d50c,
            dep_moderate_2050_label=d50l,
        ))

    n_in_sandy = sum(1 for f in findings if f.inside_sandy_2012)
    n_dep_2080 = sum(1 for f in findings
                       if (f.dep_extreme_2080_class or 0) > 0)
    return {
        "available": True,
        "n_schools": len(findings),
        "radius_m": radius_m,
        "n_inside_sandy_2012": n_in_sandy,
        "n_in_dep_extreme_2080": n_dep_2080,
        "schools": [vars(f) for f in findings],
        "citation": ("NYC DOE Locations Points + NYC OEM Sandy 2012 "
                     "Inundation Zone (5xsi-dfpx) + NYC DEP Stormwater "
                     "Flood Maps + USGS 3DEP DEM"),
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
