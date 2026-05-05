"""NYC DOE School Point Locations (Socrata a3nt-yts4)."""
from __future__ import annotations

import geopandas as gpd

from app.spatial import DATA, load_layer

BORO = {"1": "Manhattan", "2": "Bronx", "3": "Brooklyn", "4": "Queens", "5": "Staten Island"}


def load() -> gpd.GeoDataFrame:
    g = load_layer(DATA / "schools.geojson")
    g = g.rename(columns={
        "loc_code": "loc_code",
        "loc_name": "name",
        "address": "address",
        "bbl": "bbl",
        "bin": "bin",
        "boronum": "boro_num",
        "geodistric": "geo_district",
        "adimindist": "admin_district",
    })
    g["borough"] = g["boro_num"].astype(str).map(BORO)
    g["bbl"] = g["bbl"].astype(str).str.replace(r"\.0$", "", regex=True)
    keep = ["loc_code", "name", "address", "borough", "bbl", "bin",
            "geo_district", "admin_district", "geometry"]
    return g[keep].copy()
