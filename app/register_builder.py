"""Generic per-asset register builder.

Runs the same FSM specialists over every asset in a class. Tier 1+2
get full Granite paragraphs; Tier 3 gets signals only (paragraph
generated on click in the UI).
"""
from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import geopandas as gpd

from app.flood_layers import dep_stormwater, sandy_inundation
from app.rag import retrieve as rag_retrieve
from app.rag import warm as rag_warm
from app.reconcile import reconcile as run_reconcile
from app.score import score_frame

ROOT = Path(__file__).resolve().parent.parent
REGISTERS_DIR = ROOT / "data" / "registers"


def _build_one(row_meta: dict, geom_2263, lat: float, lon: float,
               with_paragraph: bool) -> dict:
    from riprap.core.pebbles.bridge import fetch_pebble  # noqa: PLC0415
    gpd.GeoDataFrame(geometry=[geom_2263], crs="EPSG:2263")
    sandy_val, _, _ = fetch_pebble("sandy", lat, lon)
    sandy = bool(sandy_val) if sandy_val is not None else False
    dep = {}
    for scen in ("dep_extreme_2080", "dep_moderate_2050", "dep_moderate_current"):
        value, _, _ = fetch_pebble(scen, lat, lon)
        if value is not None:
            dep[scen] = value
    fn, _, _ = fetch_pebble("floodnet", lat, lon)
    n311, _, _ = fetch_pebble("nyc311", lat, lon)
    mt, _, _ = fetch_pebble("microtopo", lat, lon)
    ida, _, _ = fetch_pebble("ida_hwm", lat, lon)

    snap = {
        "geocode": {**row_meta, "lat": lat, "lon": lon},
        "sandy": sandy, "dep": dep, "floodnet": fn, "nyc311": n311,
        "microtopo": mt, "ida_hwm": ida,
    }
    if with_paragraph:
        rag_query = (f"flood risk for {row_meta.get('name','')} in "
                     f"{row_meta.get('borough','')}, NYC; resilience plan, "
                     f"vulnerability, mitigation")
        snap["rag"] = rag_retrieve(rag_query, k=2, min_score=0.55)
        para, audit = run_reconcile(snap, return_audit=True)
        snap["paragraph"] = para
        snap["audit"] = audit
    return snap


def build_register(asset_class: str, loader: Callable, *,
                   tier_with_paragraph: tuple[int, ...] = (1, 2),
                   meta_keys: tuple[str, ...] = ("name", "address", "borough"),
                   regenerate: bool = False) -> Path:
    """Build a register JSON for an asset class.

    Args:
      asset_class: short id (also the output filename)
      loader: zero-arg callable returning a GeoDataFrame in EPSG:2263 with
              point geometry and at least the columns in meta_keys
      tier_with_paragraph: which tiers get full Granite reconciliation
      meta_keys: which row columns to surface as the geocode-style metadata
    """
    out = REGISTERS_DIR / f"{asset_class}.json"
    if out.exists() and not regenerate:
        print(f"already exists: {out}; pass regenerate=True to rebuild",
              file=sys.stderr)
        return out
    REGISTERS_DIR.mkdir(exist_ok=True, parents=True)

    print(f"loading asset class {asset_class!r}...", file=sys.stderr)
    g = loader()
    if g.crs is None or g.crs.to_string() != "EPSG:2263":
        g = g.to_crs("EPSG:2263")

    # tier each asset off the same rubric (sandy + 3 DEP scenarios)
    g["sandy"] = sandy_inundation.join(g).astype(int)
    for scen in ["dep_extreme_2080", "dep_moderate_2050", "dep_moderate_current"]:
        j = dep_stormwater.join(g, scen)
        g[scen] = (j["depth_class"] > 0).astype(int)
    g = score_frame(g)
    g["lat"] = g.geometry.to_crs("EPSG:4326").y
    g["lon"] = g.geometry.to_crs("EPSG:4326").x

    targets = g[g["tier"].isin([1, 2, 3])].copy()
    print(f"  {len(targets)} of {len(g)} assets at Tier 1-3", file=sys.stderr)
    print("warming RAG index...", file=sys.stderr)
    rag_warm()

    # Resume support: a partial JSON sits next to the final output. We
    # write it after every row, so any blip can be retried without losing
    # work.
    partial = REGISTERS_DIR / f"{asset_class}.partial.json"
    rows: list[dict] = []
    done_keys: set = set()
    if partial.exists():
        try:
            data = json.loads(partial.read_text())
            rows = data.get("rows", [])
            # use lat/lon as the unique key (works for any asset class)
            done_keys = {(round(r["lat"], 5), round(r["lon"], 5)) for r in rows}
            print(f"  resuming with {len(rows)} rows already processed",
                  file=sys.stderr)
        except Exception as e:
            print(f"  failed to read partial, starting fresh: {e}",
                  file=sys.stderr)

    t0 = time.time()
    for i, (_, row) in enumerate(
            targets.sort_values(["score", "name"], ascending=[False, True]).iterrows()):
        key = (round(float(row["lat"]), 5), round(float(row["lon"]), 5))
        if key in done_keys:
            continue
        tier = int(row["tier"])
        with_paragraph = tier in tier_with_paragraph
        meta = {k: row.get(k) for k in meta_keys}
        try:
            snap = _build_one(meta, row["geometry"],
                              float(row["lat"]), float(row["lon"]),
                              with_paragraph=with_paragraph)
        except Exception as e:
            print(f"  [{i+1}/{len(targets)}] FAILED tier-{tier}  "
                  f"{str(meta.get('name',''))[:50]} -- {type(e).__name__}: {e}",
                  file=sys.stderr)
            time.sleep(2)  # back off on transient errors
            continue

        rec: dict[str, Any] = {
            **{k: row.get(k) for k in g.columns if k != "geometry"},
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "score": int(row["score"]),
            "tier": tier,
            "snap": snap,
        }
        rows.append(rec)
        done_keys.add(key)
        # incremental persist
        partial.write_text(json.dumps({
            "asset_class": asset_class,
            "rows": rows,
        }, default=str))
        elapsed = time.time() - t0
        print(f"  [{i+1}/{len(targets)}] tier-{tier}  "
              f"{str(meta.get('name',''))[:50]:<50}  "
              f"({elapsed:.0f}s elapsed)", file=sys.stderr)

    out.write_text(json.dumps({
        "asset_class": asset_class,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rows": rows,
    }, default=str))
    if partial.exists():
        partial.unlink()
    print(f"\nwrote {len(rows)} rows -> {out} ({out.stat().st_size // 1024} KB)",
          file=sys.stderr)
    return out
