"""Buffered point-overlap helpers for the register specialists.

The four register specialists (MTA entrances, NYCHA developments,
DOE schools, NYS DOH hospitals) all need to test whether an asset
intersects a flood polygon. NYCHA developments are already polygons
(real building-group footprints), so polygon-vs-polygon `intersects`
is correct. The other three are stored as point centroids:

- MTA entrances are physical entrances; the point is the centerline
- DOE schools are address centroids (administrative point), but the
  actual building extends ~50 m around it
- NYS DOH hospitals are address centroids; campuses are 80–250 m wide

Pure point-in-polygon on the centroid produces false negatives at
the boundary: NYU Langone, Stuyvesant HS, P.S. 89 all sit on
buildings whose footprints overlap the 2012 Sandy zone but whose
recorded centroid points just miss it.

The honest fix is a join against the actual NYC Building Footprints
+ PLUTO BBL → footprint dataset (~400 MB). That's a separate
ingestion task. This module is the surgical-and-shippable
intermediate fix: buffer the centroid by an asset-class-appropriate
radius, then ask `intersects` against the same Sandy / DEP polygons
the existing helpers use. The `footprint_buffer_m` is recorded in
the specialist output so the trace UI shows what radius was used —
auditability over hidden assumptions.
"""
from __future__ import annotations

import logging

log = logging.getLogger("riprap.register.footprint")

# Per-asset-class footprint buffer (metres). Conservative enough to
# catch known canonical false-negatives (NYU Langone, Stuyvesant HS,
# P.S. 89) without sweeping in obviously-distant buildings.
BUFFER_MTA_ENTRANCE_M = 8
BUFFER_DOE_SCHOOL_M = 50
BUFFER_DOH_HOSPITAL_M = 100


def inside_sandy_buffered(lat: float, lon: float, buffer_m: float) -> bool:
    """True if the buffer of (lat, lon) by buffer_m metres intersects
    the 2012 Sandy Inundation Zone."""
    try:
        import geopandas as gpd
        from shapely.geometry import Point

        from app.flood_layers import sandy_inundation
        # Project before buffering so the buffer is metric. EPSG:2263
        # is NYC State Plane (feet) — convert metres to feet for buffer.
        ft = buffer_m * 3.280839895
        pt = gpd.GeoDataFrame(
            geometry=[Point(lon, lat)], crs="EPSG:4326"
        ).to_crs("EPSG:2263")
        pt["geometry"] = pt.geometry.buffer(ft)
        return bool(sandy_inundation.join(pt).iloc[0])
    except Exception:
        log.exception("buffered sandy join failed")
        return False


def dep_class_buffered(lat: float, lon: float, buffer_m: float,
                        scenario: str) -> tuple[int | None, str | None]:
    """Max DEP depth class within `buffer_m` of (lat, lon).

    Returns (depth_class, depth_label). Higher class wins on overlap,
    matching `dep_stormwater.join`'s semantics. None on failure.
    """
    try:
        import geopandas as gpd
        from shapely.geometry import Point

        from app.flood_layers import dep_stormwater
        ft = buffer_m * 3.280839895
        pt = gpd.GeoDataFrame(
            geometry=[Point(lon, lat)], crs="EPSG:4326"
        ).to_crs("EPSG:2263")
        pt["geometry"] = pt.geometry.buffer(ft)
        j = dep_stormwater.join(pt, scenario).iloc[0]
        return int(j["depth_class"]), str(j["depth_label"])
    except Exception:
        log.exception("buffered dep join failed for %s", scenario)
        return None, None
