"""Concurrency probe: simulate N users hitting the Cornerstone in parallel.

Compares three patterns under thread contention:
  1. baseline (gpd.sjoin) — current production
  2. raster-shared    — single rasterio.DatasetReader shared across threads
                         (UNSAFE; included as a control to show why it's wrong)
  3. raster-tlocal    — threading.local() DatasetReader per worker thread
                         (RECOMMENDED pattern)

Run: uv run python experiments/22_cornerstone_optim/bench_concurrent.py
"""
from __future__ import annotations

import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import geopandas as gpd
import rasterio
from shapely.geometry import Point

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from app.flood_layers import dep_stormwater, sandy_inundation  # noqa: E402

NYC_CRS = "EPSG:2263"
N_CONCURRENT = 8
N_QUERIES_PER_THREAD = 5

ADDRESSES = [
    (40.6790, -74.0050),
    (40.5867, -73.8062),
    (40.5772, -73.9870),
    (40.6033, -73.7626),
]

BAKED = REPO / "experiments" / "22_cornerstone_optim" / "baked"
RASTER_PATHS = {
    "dep_extreme_2080":     BAKED / "dep_extreme_2080.tif",
    "dep_moderate_2050":    BAKED / "dep_moderate_2050.tif",
    "dep_moderate_current": BAKED / "dep_moderate_current.tif",
    "sandy":                BAKED / "sandy.tif",
}


def to_2263_point(lat, lon):
    return gpd.GeoDataFrame(geometry=[Point(lon, lat)], crs="EPSG:4326").to_crs(NYC_CRS)


# --- pattern A: baseline sjoin ----------------------------------------------

def worker_baseline(thread_id):
    times = []
    for i in range(N_QUERIES_PER_THREAD):
        lat, lon = ADDRESSES[(thread_id + i) % len(ADDRESSES)]
        pt = to_2263_point(lat, lon)
        t0 = time.perf_counter()
        for s in ["dep_extreme_2080", "dep_moderate_2050", "dep_moderate_current"]:
            dep_stormwater.join(pt, s)
        sandy_inundation.join(pt)
        times.append(time.perf_counter() - t0)
    return times


# --- pattern B: shared DatasetReader (UNSAFE control) -----------------------

class SharedRaster:
    def __init__(self):
        self.handles = {k: rasterio.open(str(p)) for k, p in RASTER_PATHS.items()}

    def sample(self, pt_geom, key):
        ds = self.handles[key]
        return int(next(ds.sample([(pt_geom.x, pt_geom.y)]))[0])


def worker_shared(args):
    shared, thread_id = args
    times = []
    errors = 0
    for i in range(N_QUERIES_PER_THREAD):
        lat, lon = ADDRESSES[(thread_id + i) % len(ADDRESSES)]
        pt = to_2263_point(lat, lon).iloc[0].geometry
        t0 = time.perf_counter()
        try:
            for k in RASTER_PATHS:
                shared.sample(pt, k)
        except Exception:
            errors += 1
        times.append(time.perf_counter() - t0)
    return times, errors


# --- pattern C: thread-local DatasetReader (RECOMMENDED) --------------------

_TL = threading.local()


def _tl_handles():
    h = getattr(_TL, "handles", None)
    if h is None:
        h = {k: rasterio.open(str(p)) for k, p in RASTER_PATHS.items()}
        _TL.handles = h
    return h


def worker_tlocal(thread_id):
    times = []
    for i in range(N_QUERIES_PER_THREAD):
        lat, lon = ADDRESSES[(thread_id + i) % len(ADDRESSES)]
        pt = to_2263_point(lat, lon).iloc[0].geometry
        h = _tl_handles()
        t0 = time.perf_counter()
        for k in RASTER_PATHS:
            ds = h[k]
            int(next(ds.sample([(pt.x, pt.y)]))[0])
        times.append(time.perf_counter() - t0)
    return times


# --- harness ----------------------------------------------------------------

def run_pattern(name, worker, *extra):
    print(f"\n[{name}] N={N_CONCURRENT} threads × {N_QUERIES_PER_THREAD} queries")
    t_wall = time.perf_counter()
    all_times = []
    errors = 0
    with ThreadPoolExecutor(max_workers=N_CONCURRENT) as ex:
        futs = [ex.submit(worker, *(extra + (i,))) for i in range(N_CONCURRENT)]
        for f in as_completed(futs):
            r = f.result()
            if isinstance(r, tuple):
                ts, err = r
                errors += err
                all_times.extend(ts)
            else:
                all_times.extend(r)
    wall = time.perf_counter() - t_wall
    n = len(all_times)
    avg_ms = sum(all_times) / n * 1000
    p95_ms = sorted(all_times)[int(0.95 * n) - 1] * 1000
    print(f"  wall {wall:5.2f}s   per-query avg {avg_ms:6.1f} ms   "
          f"p95 {p95_ms:6.1f} ms   errors={errors}")
    return wall, avg_ms, p95_ms, errors


def main():
    # warm caches first so we measure steady-state, not cold-load
    print("warming baseline caches (first DEP load is ~30s)...")
    pt = to_2263_point(*ADDRESSES[0][:2])
    for s in RASTER_PATHS:
        if s != "sandy":
            dep_stormwater.join(pt, s)
    sandy_inundation.join(pt)
    print("warm.")

    base = run_pattern("baseline (gpd.sjoin)", worker_baseline)

    if not BAKED.exists() or not all(p.exists() for p in RASTER_PATHS.values()):
        print("\nbaked rasters missing — run bake_rasters.py first")
        return

    shared = SharedRaster()
    rb = run_pattern("raster-shared (UNSAFE)", worker_shared, shared)

    rt = run_pattern("raster-tlocal (recommended)", worker_tlocal)

    print("\n" + "=" * 72)
    print(f"{'pattern':<32} {'wall(s)':>10} {'avg(ms)':>10} {'p95(ms)':>10} {'err':>5}")
    print("=" * 72)
    for name, r in [("baseline", base), ("raster-shared", rb), ("raster-tlocal", rt)]:
        print(f"{name:<32} {r[0]:>10.2f} {r[1]:>10.1f} {r[2]:>10.1f} {r[3]:>5}")


if __name__ == "__main__":
    main()
