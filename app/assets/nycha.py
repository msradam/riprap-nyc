"""NYCHA Developments (NYC OpenData phvi-damg).

326 public-housing developments across NYC. Used as an asset class for
the bulk-mode register; the parent rationale for surfacing this layer
is that NYCHA was hit hard by Sandy and remains a published Tier-1
flood-resilience priority in the city's Hazard Mitigation Plan.
"""
from __future__ import annotations

import geopandas as gpd

from app.spatial import DATA, load_layer


def load() -> gpd.GeoDataFrame:
    g = load_layer(DATA / "nycha.geojson")
    # NYCHA developments come back as polygons; the FSM expects point
    # geometry for spatial joins. Use centroid.
    g = g.copy()
    g["geometry"] = g.geometry.centroid

    # NYCHA Developments has only `developmen` (truncated label), tds_num, borough.
    g = g.rename(columns={"developmen": "name"})
    g["address"] = g["name"]  # the field doubles as both
    g["borough"] = g["borough"].str.title()  # "BRONX" -> "Bronx" to match Riprap convention

    keep = [c for c in ["name", "address", "borough", "tds_num", "geometry"] if c in g.columns]
    return g[keep].copy()
