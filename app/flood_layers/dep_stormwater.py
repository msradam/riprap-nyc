"""NYC DEP Stormwater Flood Maps — pluvial scenarios.

Four scenarios, all in EPSG:2263. Polygons are categorized by depth class:
    1 = Nuisance Flooding (>4" and ≤1 ft)
    2 = Deep and Contiguous Flooding (>1 ft and ≤4 ft)
    3 = Deep Contiguous Flooding (>4 ft)
"""
from __future__ import annotations

from functools import lru_cache

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


def coverage_for_polygon(polygon, scenario: str,
                         polygon_crs: str = "EPSG:4326") -> dict:
    """Polygon-level summary: what fraction of the input polygon falls into
    each depth class for a given DEP scenario? Used in neighborhood mode.

    Returns:
      {
        'scenario':        scenario id,
        'label':           human-readable scenario name,
        'fraction_any':    fraction of polygon inside any flooded class,
        'fraction_class':  {1: f, 2: f, 3: f} fraction in each class,
        'polygon_area_m2': total polygon area,
      }
    """
    z = load(scenario)
    poly_gdf = gpd.GeoDataFrame(geometry=[polygon], crs=polygon_crs).to_crs(NYC_CRS)
    poly_geom = poly_gdf.iloc[0].geometry
    poly_ft2 = float(poly_geom.area)
    sqft_to_m2 = 0.092903
    fraction_class = {1: 0.0, 2: 0.0, 3: 0.0}
    if poly_ft2:
        for cat in (1, 2, 3):
            sub = z[z["Flooding_Category"] == cat]
            if sub.empty:
                continue
            inter = sub.geometry.intersection(poly_geom)
            inter = inter[~inter.is_empty]
            ft2 = float(inter.area.sum()) if len(inter) else 0.0
            fraction_class[cat] = round(ft2 / poly_ft2, 4)
    fraction_any = round(sum(fraction_class.values()), 4)
    return {
        "scenario":        scenario,
        "label":           label(scenario),
        "fraction_any":    fraction_any,
        "fraction_class":  fraction_class,
        "polygon_area_m2": round(poly_ft2 * sqft_to_m2, 1),
    }
