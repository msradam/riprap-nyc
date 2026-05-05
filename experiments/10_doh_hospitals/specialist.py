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
                       max_hospitals: int = DEFAULT_MAX_PER_QUERY) -> dict:
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
        in_sandy = _inside_sandy(hlat, hlon)
        d80c, d80l = _dep_class(hlat, hlon, "dep_extreme_2080")
        d50c, d50l = _dep_class(hlat, hlon, "dep_moderate_2050")
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
