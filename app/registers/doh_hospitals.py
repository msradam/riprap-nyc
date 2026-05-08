"""nys_doh_hospital_exposure — flood-exposure briefing per NYC hospital.

Point-based register specialist on 67 NYC hospitals from the NYS DOH
Health Facility Certification Information dataset (Article 28
hospitals only, filtered to the 5 NYC counties). Same join pattern
as MTA entrances and DOE schools.

Hospitals are essential infrastructure: a hospital inside the 2012
Sandy Inundation Zone tells planners and emergency-management
audiences something concrete about lifeline-asset exposure. NYU
Langone, Bellevue, and Coney Island Hospital all evacuated patients
during Sandy — those events are public-record and well-documented.

doc_id format: `nyc_hospital_<fac_id>` (NYS DOH facility ID).
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
    BUFFER_DOH_HOSPITAL_M,
    dep_class_buffered,
    inside_sandy_buffered,
)

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

log = logging.getLogger("riprap.hospital")

DATA = _ROOT / "data"
HOSPITALS = DATA / "hospitals.geojson"

DEFAULT_RADIUS_M = 3000  # hospitals are sparse; wider radius
DEFAULT_MAX_PER_QUERY = 5

COUNTY_TO_BOROUGH = {
    "New York": "MANHATTAN", "Kings": "BROOKLYN", "Bronx": "BRONX",
    "Queens": "QUEENS", "Richmond": "STATEN ISLAND",
}


@dataclass
class HospitalFinding:
    fac_id: str
    facility_name: str
    address: str
    borough: str
    operator_name: str
    ownership_type: str
    hospital_lat: float
    hospital_lon: float
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
def _load_hospitals():
    import geopandas as gpd
    gdf = gpd.read_file(HOSPITALS)
    gdf["lat"] = gdf.geometry.y
    gdf["lon"] = gdf.geometry.x
    return gdf.reset_index(drop=True)


def _hospitals_near(lat: float, lon: float, radius_m: float):
    gdf = _load_hospitals()
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
    return inside_sandy_buffered(lat, lon, BUFFER_DOH_HOSPITAL_M)


def _dep_class(lat: float, lon: float, scenario: str):
    return dep_class_buffered(lat, lon, BUFFER_DOH_HOSPITAL_M, scenario)


_DEPTH_LABEL = {
    0: "outside",
    1: "Nuisance (>4 in to 1 ft)",
    2: "Deep & Contiguous (1-4 ft)",
    3: "Deep Contiguous (>4 ft)",
}


def _exposure_at(lat: float, lon: float) -> tuple[bool, dict]:
    """Use baked Cornerstone rasters for fast per-point exposure lookup.
    Returns (inside_sandy, {scen: (depth_class, depth_label)}). Falls
    back to the legacy buffered GDB join if rasters absent."""
    try:
        import geopandas as gpd
        from shapely.geometry import Point

        from app.flood_layers import dep_stormwater, sandy_inundation
        pt = (gpd.GeoDataFrame(geometry=[Point(lon, lat)], crs="EPSG:4326")
              .to_crs("EPSG:2263").iloc[0].geometry)
        in_sandy = sandy_inundation.inside_raster(pt)
        deps = {}
        for scen in ("dep_extreme_2080", "dep_moderate_2050"):
            cls = dep_stormwater.join_raster(pt, scen)
            deps[scen] = (cls, _DEPTH_LABEL.get(cls, "outside"))
        return in_sandy, deps
    except Exception:
        log.exception("raster exposure lookup failed; falling back")
        in_sandy = _inside_sandy(lat, lon)
        d80c, d80l = _dep_class(lat, lon, "dep_extreme_2080")
        d50c, d50l = _dep_class(lat, lon, "dep_moderate_2050")
        return in_sandy, {
            "dep_extreme_2080": (d80c, d80l),
            "dep_moderate_2050": (d50c, d50l),
        }


def summary_for_point(lat: float, lon: float,
                       radius_m: float = DEFAULT_RADIUS_M,
                       max_hospitals: int = DEFAULT_MAX_PER_QUERY) -> dict:
    """N nearest hospitals to (lat, lon), with exposure flags computed
    via Cornerstone baked rasters. Hospitals have no pre-built register
    (small enough at ~150 entries to not need one), so we read the
    full GeoJSON and sample the rasters per-hit. Sub-ms per query."""
    near = _hospitals_near(lat, lon, radius_m)
    if near.empty:
        return {"available": False,
                "n_hospitals": 0,
                "radius_m": radius_m,
                "hospitals": []}

    near = near.head(max_hospitals)
    findings: list[HospitalFinding] = []
    for _, row in near.iterrows():
        hlat, hlon = float(row["lat"]), float(row["lon"])
        elev = _sample_raster(DATA / "nyc_dem_30m.tif", hlat, hlon)
        hand = _sample_raster(DATA / "hand.tif", hlat, hlon)
        in_sandy, deps = _exposure_at(hlat, hlon)
        d80c, d80l = deps["dep_extreme_2080"]
        d50c, d50l = deps["dep_moderate_2050"]
        findings.append(HospitalFinding(
            fac_id=str(row["fac_id"]),
            facility_name=str(row["facility_name"]),
            address=f"{row['address1']}, {row['city']}".strip(", "),
            borough=COUNTY_TO_BOROUGH.get(str(row["county"]), str(row["county"])),
            operator_name=str(row["operator_name"]),
            ownership_type=str(row["ownership_type"]),
            hospital_lat=round(hlat, 5),
            hospital_lon=round(hlon, 5),
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
        "n_hospitals": len(findings),
        "radius_m": radius_m,
        "footprint_buffer_m": BUFFER_DOH_HOSPITAL_M,
        "n_inside_sandy_2012": n_in_sandy,
        "n_in_dep_extreme_2080": n_dep_2080,
        "hospitals": [vars(f) for f in findings],
        "citation": ("NYS DOH Health Facility Certification (vn5v-hh5r) + "
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
