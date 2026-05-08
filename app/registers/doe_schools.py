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

from app.registers._footprint import (
    BUFFER_DOE_SCHOOL_M,
    dep_class_buffered,
    inside_sandy_buffered,
)

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
    return inside_sandy_buffered(lat, lon, BUFFER_DOE_SCHOOL_M)


def _dep_class(lat: float, lon: float, scenario: str):
    return dep_class_buffered(lat, lon, BUFFER_DOE_SCHOOL_M, scenario)


def summary_for_point(lat: float, lon: float,
                       radius_m: float = DEFAULT_RADIUS_M,
                       max_schools: int = DEFAULT_MAX_PER_QUERY) -> dict:
    """N nearest tier-1-3 DOE schools to (lat, lon), with pre-computed
    exposure flags read from data/registers/schools.json. The bake
    script runs the buffered point-in-polygon math citywide once;
    per-query work is haversine + dict lookup."""
    from app.registers._loader import nearest_n
    hits = nearest_n("schools", lat, lon, radius_m, max_schools)
    if not hits:
        return {"available": False,
                "n_schools": 0,
                "radius_m": radius_m,
                "schools": []}

    findings: list[SchoolFinding] = []
    for distance_m, row in hits:
        snap = row.get("snap") or {}
        dep = snap.get("dep") or {}
        microtopo = snap.get("microtopo") or {}

        def _depth(scen: str) -> tuple[int | None, str | None]:
            d = dep.get(scen) or {}
            cls = d.get("depth_class")
            lbl = d.get("depth_label")
            return (int(cls) if cls is not None else None,
                    str(lbl) if lbl else None)

        d80c, d80l = _depth("dep_extreme_2080")
        d50c, d50l = _depth("dep_moderate_2050")
        elev = microtopo.get("point_elev_m")
        hand = microtopo.get("aoi_hand_m") or microtopo.get("hand_m")

        findings.append(SchoolFinding(
            loc_code=str(row.get("loc_code", "")),
            loc_name=str(row.get("name", "")),
            address=str(row.get("address", "")).strip(),
            borough=str(row.get("borough", "")),
            bin=str(row.get("bin", "")),
            bbl=str(row.get("bbl", "")),
            managed_by="DOE-managed",
            school_lat=round(float(row["lat"]), 5),
            school_lon=round(float(row["lon"]), 5),
            distance_m=round(distance_m, 1),
            elevation_m=round(float(elev), 2) if elev is not None else None,
            hand_m=round(float(hand), 2) if hand is not None else None,
            inside_sandy_2012=bool(snap.get("sandy")),
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
        "footprint_buffer_m": BUFFER_DOE_SCHOOL_M,
        "n_inside_sandy_2012": n_in_sandy,
        "n_in_dep_extreme_2080": n_dep_2080,
        "schools": [vars(f) for f in findings],
        "citation": ("Pre-computed from NYC DOE Locations Points joined "
                     "to Sandy 2012 Inundation Zone (5xsi-dfpx) + "
                     "NYC DEP Stormwater Flood Maps + USGS 3DEP DEM. "
                     "See data/registers/schools.json."),
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
