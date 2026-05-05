"""Riprap — CLI driver for the bulk-mode flood exposure register.

Joins an asset class (schools / NYCHA / MTA entrances) against the
static flood layers (Sandy + DEP Stormwater scenarios), runs the
scoring rubric over the result, and emits a ranked CSV plus a tier
distribution to stderr.
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import pandas as pd  # noqa: E402

from app.assets import schools  # noqa: E402
from app.flood_layers import dep_stormwater, sandy_inundation  # noqa: E402
from app.score import WEIGHTS, score_frame  # noqa: E402

OUT = Path(__file__).resolve().parent / "outputs"
OUT.mkdir(exist_ok=True)


def build_schools_register() -> pd.DataFrame:
    print("loading schools...", file=sys.stderr)
    s = schools.load()
    print(f"  {len(s)} schools loaded", file=sys.stderr)

    print("joining Sandy Inundation Zone...", file=sys.stderr)
    s["sandy"] = sandy_inundation.join(s).astype(int)
    print(f"  {int(s['sandy'].sum())} schools inside Sandy zone", file=sys.stderr)

    for scen in ["dep_extreme_2080", "dep_moderate_2050", "dep_moderate_current"]:
        print(f"joining {scen}...", file=sys.stderr)
        j = dep_stormwater.join(s, scen)
        s[scen] = (j["depth_class"] > 0).astype(int)
        s[f"{scen}_depth_class"] = j["depth_class"].values
        s[f"{scen}_depth_label"] = j["depth_label"].values
        print(f"  {int(s[scen].sum())} schools inside {scen}", file=sys.stderr)

    s = score_frame(s)

    # drop geometry for CSV; keep lat/lon for journalist usability
    s["lat"] = s.geometry.to_crs("EPSG:4326").y
    s["lon"] = s.geometry.to_crs("EPSG:4326").x
    cols = ["loc_code", "name", "address", "borough", "bbl", "bin",
            "geo_district", "lat", "lon",
            "sandy",
            "dep_extreme_2080", "dep_extreme_2080_depth_label",
            "dep_moderate_2050", "dep_moderate_2050_depth_label",
            "dep_moderate_current", "dep_moderate_current_depth_label",
            "score", "tier"]
    return pd.DataFrame(s[cols])


def main() -> int:
    ap = argparse.ArgumentParser(description="Riprap flood exposure register")
    ap.add_argument("--asset-class", default="schools")
    ap.add_argument("--out", default=None)
    ap.add_argument("--top", type=int, default=20, help="rows to print to stdout")
    args = ap.parse_args()

    if args.asset_class != "schools":
        print(f"asset class '{args.asset_class}' not yet implemented", file=sys.stderr)
        return 2

    df = build_schools_register()
    df = df.sort_values(["score", "name"], ascending=[False, True])

    out_path = Path(args.out) if args.out else OUT / "schools_register.csv"
    df.to_csv(out_path, index=False)
    print(f"\nwrote {len(df)} rows -> {out_path}", file=sys.stderr)

    print(f"\n=== top {args.top} ===")
    print(df.head(args.top).to_string(index=False))

    print("\n=== tier distribution ===")
    print(df["tier"].value_counts().sort_index().to_string())

    print("\n=== signal totals ===")
    for k in WEIGHTS:
        if k in df.columns:
            print(f"  {k:24s}: {int(df[k].sum()):4d} schools")

    return 0


if __name__ == "__main__":
    sys.exit(main())
