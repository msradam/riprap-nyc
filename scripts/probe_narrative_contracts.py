"""Verify the type-keyed dispatch refactor's adapter contract:
every migrated pebble's value must include a `narrative` (or the
normalized rendering fields the bespoke renderer reads).

Hits /api/agent/stream once per city, reads the final step.result
payloads, and checks the contract for each migrated pebble.
"""
from __future__ import annotations

import json
import sys
import time
from typing import Any
from urllib.parse import quote

import httpx


# Per-pebble contract: which field(s) the migrated adapter must emit.
# For type-keyed bespoke renderers (forecast/raster/histogram/register)
# the contract is a tuple of required fields; for templated-path
# pebbles the contract is just {narrative}.
CONTRACTS = {
    # Templated path — needs `narrative`
    "sandy": ["inside_phrasing", "inside_or_outside"],
    "ida_hwm": ["narrative"],
    "floodnet": ["narrative"],
    "nyc311": ["narrative", "histogram"],
    "microtopo": ["narrative"],
    "noaa_tides": ["narrative"],
    "nws_obs": ["narrative"],
    "nws_alerts": ["narrative"],
    "dep_extreme_2080": ["narrative", "depth_class"],
    "dep_moderate_2050": ["narrative", "depth_class"],
    "dep_moderate_current": ["narrative", "depth_class"],
    # Raster bespoke renderer — needs normalized rendering fields
    "prithvi_water": ["headline_value", "subhead_text", "narrative", "raster_kind"],
    "prithvi_live": ["ok"],  # ok=False is the offline path; if ok=True it has more
    # Boston / Chicago / Seattle / SF water_level
    "water_level": ["narrative"],
    "lake_michigan_water_level": ["narrative"],
}


def stream(query: str, base: str = "http://127.0.0.1:7860",
           timeout_s: float = 120) -> dict[str, Any]:
    """Read the SSE final event — that's what carries the full pebble
    value dicts. Step events only carry the slim trace_summary."""
    url = f"{base}/api/agent/stream?q={quote(query)}"
    deployment = None
    final: dict = {}
    with httpx.stream("GET", url, timeout=timeout_s,
                      headers={"Accept": "text/event-stream"}) as r:
        r.raise_for_status()
        cur_event = "message"
        cur_data: list[str] = []
        for line in r.iter_lines():
            if not line:
                if cur_data:
                    try:
                        payload = json.loads("\n".join(cur_data))
                    except json.JSONDecodeError:
                        payload = {"raw": "\n".join(cur_data)}
                    if cur_event == "deployment":
                        deployment = payload.get("name")
                    elif cur_event == "final":
                        final = payload
                    cur_event = "message"
                    cur_data = []
                continue
            if line.startswith("event:"):
                cur_event = line[6:].strip()
            elif line.startswith("data:"):
                cur_data.append(line[5:].lstrip())
    return {"deployment": deployment, "final": final}


def check_pebble(pid: str, value: dict, contract: list[str]) -> list[str]:
    issues = []
    if not isinstance(value, dict):
        return [f"{pid}: value not a dict ({type(value).__name__})"]
    for field in contract:
        if field not in value:
            issues.append(f"{pid}: missing required field {field!r}")
    return issues


def main() -> int:
    cities = [
        ("nyc", "442 East Houston Street, Manhattan"),
        ("boston", "100 Atlantic Avenue, Boston, MA"),
        ("chicago", "233 South Wacker Drive, Chicago, IL"),
        ("seattle", "400 Broad Street, Seattle, WA"),
        ("sf", "1 Ferry Building, San Francisco, CA"),
    ]
    all_pass = True
    for city, query in cities:
        print(f"\n— {city} — {query}")
        result = stream(query)
        print(f"  deployment: {result['deployment']}")
        final = result["final"]
        for pid in CONTRACTS:
            value = final.get(pid)
            if value is None:
                continue  # pebble didn't fire for this deployment
            issues = check_pebble(pid, value, CONTRACTS[pid])
            if issues:
                all_pass = False
                for iss in issues:
                    print(f"  FAIL  {iss}")
            else:
                preview = (
                    value.get("narrative", "")
                    or value.get("headline_value", "")
                    or "(no preview field)"
                )
                preview_str = preview[:80] if isinstance(preview, str) else str(preview)[:80]
                print(f"  PASS  {pid:35s}  narrative='{preview_str}'")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
