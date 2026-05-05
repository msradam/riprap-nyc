"""NYC DEP Stormwater Flood Maps — pluvial scenarios.

Four scenarios, all in EPSG:2263. Polygons are categorized by depth class:
    1 = Nuisance Flooding (>4" and ≤1 ft)
    2 = Deep and Contiguous Flooding (>1 ft and ≤4 ft)
    3 = Deep Contiguous Flooding (>4 ft)
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import geopandas as gpd

from app.spatial import DATA, NYC_CRS

ROOT = DATA / "dep"

SCENARIOS = {
    "dep_extreme_2080": {
        "gdb": "dep_extreme_2080.gdb",
        "label": "DEP Extreme Stormwater (3.66 in/hr, 2080 SLR)",
    },
    "dep_moderate_2050": {
        "gdb": "dep_moderate_2050.gdb",
        "label": "DEP Moderate Stormwater (2.13 in/hr, 2050 SLR)",
    },
    "dep_moderate_current": {
        "gdb": "dep_moderate_current.gdb",
        "label": "DEP Moderate Stormwater (2.13 in/hr, current SLR)",
    },
}

DEPTH_CLASS = {
    1: "Nuisance (>4 in to 1 ft)",
    2: "Deep & Contiguous (1-4 ft)",
    3: "Deep Contiguous (>4 ft)",
}


@lru_cache(maxsize=4)
def load(scenario: str) -> gpd.GeoDataFrame:
    s = SCENARIOS[scenario]
    path = ROOT / s["gdb"]
    g = gpd.read_file(str(path))
    if g.crs.to_string() != NYC_CRS:
        g = g.to_crs(NYC_CRS)
    return g


def join(assets: gpd.GeoDataFrame, scenario: str) -> gpd.GeoDataFrame:
    """Per-asset depth class, or 0 if outside scenario.

    Returns a frame indexed like assets with columns: depth_class, depth_label.
    Higher class wins on overlap.
    """
    z = load(scenario)
    a = assets[["geometry"]].copy()
    a["_aid"] = range(len(a))
    j = gpd.sjoin(a, z[["Flooding_Category", "geometry"]],
                  how="left", predicate="intersects")
    # for each asset, take max category hit (3 dominates 1)
    cat = (j.groupby("_aid")["Flooding_Category"].max()
              .reindex(range(len(a)))
              .fillna(0).astype(int))
    out = a[["_aid"]].copy()
    out["depth_class"] = cat.values
    out["depth_label"] = out["depth_class"].map(lambda c: DEPTH_CLASS.get(c, "outside"))
    return out[["depth_class", "depth_label"]].reset_index(drop=True)


def label(scenario: str) -> str:
    return SCENARIOS[scenario]["label"]
