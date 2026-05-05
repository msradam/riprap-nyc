"""MTA Subway Entrances and Exits (NY OpenData i9wp-a4ja).

~1,900 subway entrances city-wide. The MTA Climate Resilience Roadmap
(Oct 2025) names ~1,500 of these as priorities for sealing — this is
exactly the asset class our RAG corpus has the most to say about, and
exactly the audience (MTA capital planners, transit advocacy) the
register is built for.
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import httpx

from app.spatial import DATA, NYC_CRS

URL = "https://data.ny.gov/api/geospatial/i9wp-a4ja?method=export&format=GeoJSON"
LOCAL = DATA / "mta_entrances.geojson"


def _ensure_fixture() -> Path:
    if LOCAL.exists():
        return LOCAL
    print("downloading MTA Subway Entrances (one-time)...", flush=True)
    r = httpx.get(URL, timeout=60)
    r.raise_for_status()
    LOCAL.write_text(r.text)
    return LOCAL


def load() -> gpd.GeoDataFrame:
    _ensure_fixture()
    g = gpd.read_file(LOCAL)
    if g.crs is None:
        g.set_crs("EPSG:4326", inplace=True)
    g = g.to_crs(NYC_CRS)
    rename_map = {
        "stop_name": "name",
        "constrained_floor_to_floor_height": None,
        "borough": "borough",
        "entrance_type": "entrance_type",
        "ada": "ada",
        "north_south_street": "ns_street",
        "east_west_street": "ew_street",
        "corner": "corner",
    }
    for k, v in rename_map.items():
        if v and k in g.columns and k != v:
            g = g.rename(columns={k: v})

    # build a usable address-style label
    def label(row):
        nm = (row.get("name") or "").strip()
        ns = (row.get("ns_street") or "").strip()
        ew = (row.get("ew_street") or "").strip()
        cn = (row.get("corner") or "").strip()
        bits = [nm]
        cross = " & ".join(b for b in [ns, ew] if b)
        if cross: bits.append(cross)
        if cn: bits.append(f"({cn})")
        return ", ".join([b for b in bits if b])

    g["address"] = g.apply(label, axis=1)
    if "borough" in g.columns:
        boro_map = {"M": "Manhattan", "Bk": "Brooklyn", "B": "Brooklyn",
                    "Q": "Queens", "Bx": "Bronx", "SI": "Staten Island"}
        g["borough"] = g["borough"].astype(str).map(lambda v: boro_map.get(v, v.title()))

    keep = [c for c in ["name", "address", "borough", "entrance_type",
                        "ada", "ns_street", "ew_street", "corner", "geometry"]
            if c in g.columns]
    return g[keep].copy()
