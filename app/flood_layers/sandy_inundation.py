"""NYC Sandy Inundation Zone (empirical 2012 extent, NYC OD 5xsi-dfpx)."""
from __future__ import annotations

from functools import lru_cache

import geopandas as gpd

from app.spatial import DATA, load_layer

DOC_ID = "sandy_inundation"
CITATION = "NYC Sandy Inundation Zone (NYC OpenData 5xsi-dfpx, empirical 2012 extent)"


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
