"""Spatial helpers. NYC works in EPSG:2263 (NY state plane, feet)."""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd

NYC_CRS = "EPSG:2263"  # ft
WGS84 = "EPSG:4326"

DATA = Path(__file__).resolve().parent.parent / "data"


def to_nyc(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if g.crs is None:
        raise ValueError("layer has no CRS")
    return g.to_crs(NYC_CRS) if g.crs.to_string() != NYC_CRS else g


def load_layer(path: str | Path, layer: str | None = None) -> gpd.GeoDataFrame:
    g = gpd.read_file(path, layer=layer) if layer else gpd.read_file(path)
    return to_nyc(g)
