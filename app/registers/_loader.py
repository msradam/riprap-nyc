"""Shared loader for pre-built register JSONs in data/registers/.

Each register specialist (`nycha`, `doe_schools`, `doh_hospitals`,
`mta_entrances`) has a pre-computed JSON catalog of every Tier 1-3
exposed asset. The catalog is built once by scripts/build_*_register.py
running the full polygon-overlap math; per-query specialists used to
recompute that math against multi-million-polygon GDB layers, which
on the HF Space CPU made `step_nycha` hang for minutes.

This module provides O(1) cached load + haversine-on-prebuilt-rows
nearest-N retrieval. Per-query latency drops from minutes to ~ms
without losing the exposure semantics — the per-asset flags
(snap.sandy, snap.dep[scen].depth_class, snap.microtopo) were already
computed during the bake.

Asset classes outside this catalog (truly unexposed assets, tier 0)
are intentionally not surfaced: a Carleton Manor query that returns
"no NYCHA developments at risk within 1 mi" is a more useful
result than "we found 5 inland NYCHA developments with 0% Sandy
overlap."
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

REGISTERS_DIR = Path(__file__).resolve().parents[2] / "data" / "registers"


@lru_cache(maxsize=8)
def load_register(asset_class: str) -> list[dict]:
    """Return the rows list from data/registers/<asset_class>.json. The
    caller treats each row as opaque except for the lat/lon fields."""
    p = REGISTERS_DIR / f"{asset_class}.json"
    if not p.exists():
        return []
    with open(p) as f:
        d = json.load(f)
    return list(d.get("rows", []))


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1); dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def nearest_n(asset_class: str, lat: float, lon: float,
              radius_m: float, n: int) -> list[tuple[float, dict]]:
    """Return up to N rows within radius_m of (lat, lon), sorted by
    distance ascending. Each entry is (distance_m, row)."""
    rows = load_register(asset_class)
    if not rows:
        return []
    candidates: list[tuple[float, dict]] = []
    for r in rows:
        rlat = r.get("lat")
        rlon = r.get("lon")
        if rlat is None or rlon is None:
            continue
        d = haversine_m(lat, lon, float(rlat), float(rlon))
        if d <= radius_m:
            candidates.append((d, r))
    candidates.sort(key=lambda t: t[0])
    return candidates[:n]
