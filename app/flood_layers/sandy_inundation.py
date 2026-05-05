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


def join(assets: gpd.GeoDataFrame) -> "gpd.pd.Series":
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
