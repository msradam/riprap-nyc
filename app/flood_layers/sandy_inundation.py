"""NYC Sandy Inundation Zone (empirical 2012 extent, NYC OD 5xsi-dfpx).

Two query paths exist:
    inside_raster(point) — fast path. Samples data/baked/sandy.tif.
        ~1 ms; used by step_sandy in the FSM.
    join(assets)         — legacy GeoJSON sjoin path. Retained as a
        fallback when the baked raster is absent (local dev) and
        for coverage_for_polygon (neighborhood mode).
"""
from __future__ import annotations

import logging
import threading
from functools import lru_cache

import geopandas as gpd

from app.spatial import DATA, NYC_CRS, load_layer

DOC_ID = "sandy_inundation"
CITATION = "NYC Sandy Inundation Zone (NYC OpenData 5xsi-dfpx, empirical 2012 extent)"

log = logging.getLogger(__name__)
BAKED = DATA / "baked"
_TLOCAL = threading.local()
_FALLBACK_WARNED = False


@lru_cache(maxsize=1)
def load() -> gpd.GeoDataFrame:
    g = load_layer(DATA / "sandy_inundation.geojson")
    return g[["geometry"]]


def join(assets: gpd.GeoDataFrame) -> gpd.pd.Series:
    """Return a boolean Series indexed like assets: True if inside Sandy zone."""
    z = load()
    # spatial join avoids fragile unary union over messy public polygons
    hits = gpd.sjoin(
        assets[["geometry"]].assign(_aid=range(len(assets))),
        z[["geometry"]],
        how="left",
        predicate="intersects",
    )
    flagged = hits.dropna(subset=["index_right"])["_aid"].unique()
    s = assets.geometry.copy().astype(bool)
    s[:] = False
    s.iloc[list(flagged)] = True
    return s.reset_index(drop=True)


def _raster_handle():
    """Per-thread rasterio handle. See dep_stormwater._raster_handles."""
    h = getattr(_TLOCAL, "handle", None)
    if h is not None:
        return h
    p = BAKED / "sandy.tif"
    if not p.exists():
        return None
    import rasterio
    h = rasterio.open(str(p))
    _TLOCAL.handle = h
    return h


def inside_raster(pt_geom_2263) -> bool:
    """Fast path. True if the shapely Point (in EPSG:2263) falls inside the
    2012 Sandy inundation extent. Falls back to the GeoJSON sjoin path if
    data/baked/sandy.tif is missing."""
    global _FALLBACK_WARNED
    h = _raster_handle()
    if h is None:
        if not _FALLBACK_WARNED:
            log.warning(
                "data/baked/sandy.tif not found — falling back to GeoJSON sjoin. "
                "Run: uv run python scripts/bake_cornerstone_rasters.py"
            )
            _FALLBACK_WARNED = True
        a = gpd.GeoDataFrame(geometry=[pt_geom_2263], crs=NYC_CRS)
        return bool(join(a).iloc[0])
    v = next(h.sample([(pt_geom_2263.x, pt_geom_2263.y)]))
    return bool(int(v[0]))


def coverage_for_polygon(polygon, polygon_crs: str = "EPSG:4326") -> dict:
    """Polygon-level summary: what fraction of the input polygon overlaps
    the 2012 Sandy inundation extent? Used in neighborhood-mode queries.

    Returns:
      {
        'overlap_area_m2':   absolute overlap in m2,
        'polygon_area_m2':   total polygon area in m2,
        'fraction':          overlap / polygon_area, range [0, 1],
        'inside':            True if any overlap exists,
      }
    """
    z = load().to_crs("EPSG:2263")  # NY State Plane Long Island, units = ft
    poly_gdf = gpd.GeoDataFrame(geometry=[polygon], crs=polygon_crs).to_crs("EPSG:2263")
    poly_geom = poly_gdf.iloc[0].geometry
    inter = z.intersection(poly_geom)
    inter = inter[~inter.is_empty]
    overlap_ft2 = float(inter.area.sum()) if len(inter) else 0.0
    poly_ft2 = float(poly_geom.area)
    sqft_to_m2 = 0.092903
    return {
        "overlap_area_m2":   round(overlap_ft2 * sqft_to_m2, 1),
        "polygon_area_m2":   round(poly_ft2 * sqft_to_m2, 1),
        "fraction":          round(overlap_ft2 / poly_ft2, 4) if poly_ft2 else 0.0,
        "inside":            overlap_ft2 > 0,
    }
