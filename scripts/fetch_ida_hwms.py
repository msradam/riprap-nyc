"""One-shot fetch of NYC Hurricane Ida 2021 high-water marks from USGS STN.

Output: data/ida_2021_hwms_ny.geojson — point GeoJSON with elev_ft + site
metadata. Used by the Riprap agent's `step_ida_hwm` action as the
empirical post-event flood signal (the same role Prithvi-EO plays for
SAR-derived extents in the parent project).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parent.parent / "data" / "ida_2021_hwms_ny.geojson"
URL = "https://stn.wim.usgs.gov/STNServices/HWMs/FilteredHWMs.json"


def main() -> int:
    print("fetching USGS STN Ida 2021 NY HWMs...", file=sys.stderr)
    r = httpx.get(URL, params={"Event": 312, "States": "NY"}, timeout=60)
    r.raise_for_status()
    data = r.json()

    features = []
    for d in data:
        lat = d.get("latitude"); lon = d.get("longitude")
        if lat is None or lon is None:
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "hwm_id": d.get("hwm_id"),
                "site_no": d.get("site_no"),
                "elev_ft": d.get("elev_ft"),
                "height_above_gnd": d.get("height_above_gnd"),
                "hwm_type": d.get("hwmTypeName"),
                "hwm_quality": d.get("hwmQualityName"),
                "county": d.get("countyName"),
                "site_description": d.get("siteDescription"),
                "waterbody": d.get("waterbody"),
            },
        })
    OUT.parent.mkdir(exist_ok=True, parents=True)
    OUT.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    print(f"wrote {len(features)} HWMs -> {OUT} ({OUT.stat().st_size // 1024} KB)",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
