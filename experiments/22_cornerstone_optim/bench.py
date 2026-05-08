"""Bench all four Cornerstone-join approaches on canonical addresses.

Run from repo root:
    uv run python experiments/22_cornerstone_optim/bench.py

The script benchmarks per-point query time AFTER warm-up (cold-start
load is reported separately). The HF Space pays warm-up once at boot;
the per-query latency is what compounds in the 20-query batch.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import Point, box
from shapely.strtree import STRtree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from app.flood_layers import dep_stormwater, sandy_inundation  # noqa: E402

NYC_CRS = "EPSG:2263"

ADDRESSES = [
    ("80 Pioneer St, Brooklyn",       40.6790, -74.0050),
    ("2508 Beach Channel Dr, Queens", 40.5867, -73.8062),
    ("Coney Island I Houses, BK",     40.5772, -73.9870),
    ("Carleton Manor, Queens",        40.6033, -73.7626),
]

DEP_SCENARIOS = ["dep_extreme_2080", "dep_moderate_2050", "dep_moderate_current"]


def to_2263(lat: float, lon: float):
    pt = gpd.GeoDataFrame(geometry=[Point(lon, lat)], crs="EPSG:4326").to_crs(NYC_CRS)
    return pt, pt.iloc[0].geometry


# ---------------------------------------------------------------------------
# 1. baseline — current production path
# ---------------------------------------------------------------------------

def baseline_dep(pt_gdf, scenario):
    j = dep_stormwater.join(pt_gdf, scenario).iloc[0]
    return int(j["depth_class"])


def baseline_sandy(pt_gdf):
    return bool(sandy_inundation.join(pt_gdf).iloc[0])


# ---------------------------------------------------------------------------
# 2. strtree — pre-warmed index, single-point intersects
# ---------------------------------------------------------------------------

class StrTreeDEP:
    def __init__(self):
        self.trees = {}
        self.cats = {}
        for s in DEP_SCENARIOS:
            g = dep_stormwater.load(s)
            geoms = list(g.geometry.values)
            cats = g["Flooding_Category"].astype(int).to_numpy()
            self.trees[s] = STRtree(geoms)
            self.cats[s] = (geoms, cats)

    def query(self, pt_geom, scenario):
        tree = self.trees[scenario]
        geoms, cats = self.cats[scenario]
        idx = tree.query(pt_geom, predicate="intersects")
        if len(idx) == 0:
            return 0
        return int(cats[idx].max())


class StrTreeSandy:
    def __init__(self):
        g = sandy_inundation.load()
        self.geoms = list(g.geometry.values)
        self.tree = STRtree(self.geoms)

    def query(self, pt_geom):
        idx = self.tree.query(pt_geom, predicate="intersects")
        return len(idx) > 0


# ---------------------------------------------------------------------------
# 3. bbox-prefilter — clip layer to small window, then sjoin
# ---------------------------------------------------------------------------

def bbox_prefilter_dep(pt_geom, scenario, pad_ft=200):
    g = dep_stormwater.load(scenario)
    minx, miny = pt_geom.x - pad_ft, pt_geom.y - pad_ft
    maxx, maxy = pt_geom.x + pad_ft, pt_geom.y + pad_ft
    sub = g.cx[minx:maxx, miny:maxy]
    if sub.empty:
        return 0
    hits = sub[sub.intersects(pt_geom)]
    if hits.empty:
        return 0
    return int(hits["Flooding_Category"].astype(int).max())


def bbox_prefilter_sandy(pt_geom, pad_ft=200):
    g = sandy_inundation.load()
    minx, miny = pt_geom.x - pad_ft, pt_geom.y - pad_ft
    maxx, maxy = pt_geom.x + pad_ft, pt_geom.y + pad_ft
    sub = g.cx[minx:maxx, miny:maxy]
    if sub.empty:
        return False
    return bool(sub.intersects(pt_geom).any())


# ---------------------------------------------------------------------------
# 4. raster — sample baked GeoTIFFs
# ---------------------------------------------------------------------------

def raster_paths():
    out = REPO / "experiments" / "22_cornerstone_optim" / "baked"
    return {
        "dep_extreme_2080":      out / "dep_extreme_2080.tif",
        "dep_moderate_2050":     out / "dep_moderate_2050.tif",
        "dep_moderate_current":  out / "dep_moderate_current.tif",
        "sandy":                 out / "sandy.tif",
    }


class RasterLookup:
    def __init__(self):
        import rasterio
        self.rasterio = rasterio
        paths = raster_paths()
        missing = [k for k, p in paths.items() if not p.exists()]
        if missing:
            raise FileNotFoundError(
                f"missing baked rasters: {missing}\n"
                f"run: uv run python experiments/22_cornerstone_optim/bake_rasters.py"
            )
        self.handles = {k: rasterio.open(str(p)) for k, p in paths.items()}

    def sample(self, pt_geom, key):
        ds = self.handles[key]
        v = next(ds.sample([(pt_geom.x, pt_geom.y)]))
        return int(v[0])


# ---------------------------------------------------------------------------
# bench harness
# ---------------------------------------------------------------------------

def time_call(fn, *args, **kwargs):
    t0 = time.perf_counter()
    out = fn(*args, **kwargs)
    return time.perf_counter() - t0, out


def main():
    print("=" * 78)
    print("Cornerstone optimization bench")
    print("=" * 78)

    addrs_2263 = []
    for label, lat, lon in ADDRESSES:
        pt_gdf, pt_geom = to_2263(lat, lon)
        addrs_2263.append((label, pt_gdf, pt_geom))

    # cold load + warm-up baseline lru_cache
    print("\n[cold-load times — paid once at boot]")
    t, _ = time_call(dep_stormwater.load, "dep_extreme_2080")
    print(f"  dep_extreme_2080.load     {t*1000:8.1f} ms")
    t, _ = time_call(dep_stormwater.load, "dep_moderate_2050")
    print(f"  dep_moderate_2050.load    {t*1000:8.1f} ms")
    t, _ = time_call(dep_stormwater.load, "dep_moderate_current")
    print(f"  dep_moderate_current.load {t*1000:8.1f} ms")
    t, _ = time_call(sandy_inundation.load)
    print(f"  sandy.load                {t*1000:8.1f} ms")

    # build approaches
    print("\n[approach init]")
    t, strtree_dep = time_call(StrTreeDEP)
    print(f"  STRtree DEP build         {t*1000:8.1f} ms")
    t, strtree_sandy = time_call(StrTreeSandy)
    print(f"  STRtree Sandy build       {t*1000:8.1f} ms")

    raster = None
    try:
        t, raster = time_call(RasterLookup)
        print(f"  raster open               {t*1000:8.1f} ms")
    except FileNotFoundError as e:
        print(f"  raster: NOT BAKED — {e}")

    results = {}  # approach -> list of per-address per-query times (ms)

    for label, pt_gdf, pt_geom in addrs_2263:
        print(f"\n--- {label} ---")
        row = {}

        # baseline: full sjoin per scenario
        total = 0
        truth_dep = {}
        for s in DEP_SCENARIOS:
            t, c = time_call(baseline_dep, pt_gdf, s)
            truth_dep[s] = c
            total += t
        t_sandy_base, truth_sandy = time_call(baseline_sandy, pt_gdf)
        total += t_sandy_base
        row["baseline"] = total * 1000
        print(f"  baseline (3 dep + sandy)  {total*1000:8.1f} ms   "
              f"dep={truth_dep}  sandy={truth_sandy}")

        # strtree
        total = 0
        out_dep = {}
        for s in DEP_SCENARIOS:
            t, c = time_call(strtree_dep.query, pt_geom, s)
            out_dep[s] = c
            total += t
        t, out_sandy = time_call(strtree_sandy.query, pt_geom)
        total += t
        row["strtree"] = total * 1000
        ok = out_dep == truth_dep and out_sandy == truth_sandy
        print(f"  strtree                   {total*1000:8.1f} ms   parity={ok}")

        # bbox prefilter
        total = 0
        out_dep = {}
        for s in DEP_SCENARIOS:
            t, c = time_call(bbox_prefilter_dep, pt_geom, s)
            out_dep[s] = c
            total += t
        t, out_sandy = time_call(bbox_prefilter_sandy, pt_geom)
        total += t
        row["bbox-prefilter"] = total * 1000
        ok = out_dep == truth_dep and out_sandy == truth_sandy
        print(f"  bbox-prefilter            {total*1000:8.1f} ms   parity={ok}")

        # raster
        if raster is not None:
            total = 0
            out_dep = {}
            for s in DEP_SCENARIOS:
                t, c = time_call(raster.sample, pt_geom, s)
                out_dep[s] = c
                total += t
            t, out_sandy_int = time_call(raster.sample, pt_geom, "sandy")
            total += t
            out_sandy = bool(out_sandy_int)
            row["raster"] = total * 1000
            ok = out_dep == truth_dep and out_sandy == truth_sandy
            print(f"  raster                    {total*1000:8.1f} ms   parity={ok}")

        results[label] = row

    print("\n" + "=" * 78)
    print("SUMMARY (per-query ms, lower is better)")
    print("=" * 78)
    headers = ["address", "baseline", "strtree", "bbox", "raster"]
    print(f"{headers[0]:<32} {headers[1]:>10} {headers[2]:>10} {headers[3]:>10} {headers[4]:>10}")
    for label, row in results.items():
        print(f"{label:<32} "
              f"{row.get('baseline', float('nan')):>10.1f} "
              f"{row.get('strtree', float('nan')):>10.1f} "
              f"{row.get('bbox-prefilter', float('nan')):>10.1f} "
              f"{row.get('raster', float('nan')) if 'raster' in row else float('nan'):>10.1f}")


if __name__ == "__main__":
    main()
