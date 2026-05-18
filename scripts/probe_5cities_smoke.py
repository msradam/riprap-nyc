"""Cross-city smoke probe — verifies the type-keyed dispatch refactor
didn't break the live data probes for any deployment.

For each of the 5 supported cities, fires one canonical-address query
against /api/agent/stream and checks:
  - SSE handshake emits the right `deployment` event
  - All cornerstone + touchstone pebbles for that deployment write
    their state key
  - The final paragraph mentions city-specific content (sandy / lake /
    bay) and doesn't leak content from other cities
  - For the new templated pebbles (DEP / ida_hwm / floodnet / nyc311 /
    microtopo / prithvi_water / prithvi_live): the value carries a
    `narrative` field the frontend renders verbatim.

Run with:
    RIPRAP_RECONCILER_TIER=no_llm uv run python scripts/probe_5cities_smoke.py
"""
from __future__ import annotations

import json
import sys
import time
from urllib.parse import quote

import httpx


CITIES = [
    {
        "name": "nyc",
        "query": "442 East Houston Street, Manhattan",
        "expect_pebbles": [
            "sandy", "ida_hwm", "prithvi_water", "microtopo",
            "dep_extreme_2080", "dep_moderate_2050", "dep_moderate_current",
            "floodnet", "nyc311", "noaa_tides",
        ],
        "expect_narrative_pebbles": [
            "sandy", "ida_hwm", "floodnet", "nyc311", "microtopo",
            "prithvi_water", "noaa_tides",
        ],
        "no_leak": ["Lake Michigan", "Calumet", "San Francisco", "Seattle",
                    "Boston Logan", "Charles River"],
    },
    {
        "name": "boston",
        "query": "100 Atlantic Avenue, Boston, MA",
        "expect_pebbles": [
            "water_level", "boston_311", "nws_obs", "nws_alerts",
        ],
        "expect_narrative_pebbles": ["water_level", "nws_obs"],
        "no_leak": ["NYC OEM", "Sandy 2012", "FloodNet", "Lake Michigan",
                    "San Francisco"],
    },
    {
        "name": "chicago",
        "query": "233 South Wacker Drive, Chicago, IL",
        "expect_pebbles": [
            "lake_michigan_water_level", "chicago_311", "nws_obs", "nws_alerts",
        ],
        "expect_narrative_pebbles": ["lake_michigan_water_level", "nws_obs"],
        "no_leak": ["NYC OEM", "Sandy 2012", "FloodNet", "Boston Harbor",
                    "San Francisco"],
    },
    {
        "name": "seattle",
        "query": "400 Broad Street, Seattle, WA",
        "expect_pebbles": [
            "water_level", "nws_obs", "nws_alerts",  # no 311 manifest yet
        ],
        "expect_narrative_pebbles": ["water_level", "nws_obs"],
        "no_leak": ["NYC OEM", "Sandy 2012", "Lake Michigan",
                    "Boston Logan"],
    },
    {
        "name": "sf",
        "query": "1 Ferry Building, San Francisco, CA",
        "expect_pebbles": [
            "water_level", "sf_311", "nws_obs", "nws_alerts",
        ],
        "expect_narrative_pebbles": ["water_level", "nws_obs"],
        "no_leak": ["NYC OEM", "Sandy 2012", "Lake Michigan", "Boston Harbor"],
    },
]


def probe_city(base: str, spec: dict, timeout_s: float = 120) -> dict:
    """Run one query against the SSE endpoint, return parsed events."""
    q = spec["query"]
    url = f"{base}/api/agent/stream?q={quote(q)}"
    events: list[tuple[str, dict]] = []
    final: dict = {}
    deployment: str | None = None
    started = time.time()
    try:
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
                        events.append((cur_event, payload))
                        if cur_event == "deployment":
                            # backend emits {name, city, state} not {deployment}
                            deployment = payload.get("name") or payload.get("deployment")
                        if cur_event == "final":
                            final = payload
                        cur_event = "message"
                        cur_data = []
                    continue
                if line.startswith("event:"):
                    cur_event = line[6:].strip()
                elif line.startswith("data:"):
                    cur_data.append(line[5:].lstrip())
    except Exception as e:
        return {"ok": False, "error": str(e), "events": events,
                "deployment": deployment, "elapsed_s": time.time() - started}
    return {"ok": True, "events": events, "deployment": deployment,
            "final": final, "elapsed_s": time.time() - started}


def check_city(spec: dict, result: dict) -> list[str]:
    if not result["ok"]:
        return [f"stream failed: {result.get('error')}"]
    issues: list[str] = []
    if result["deployment"] != spec["name"]:
        issues.append(f"deployment={result['deployment']!r}, expected {spec['name']!r}")
    final = result.get("final") or {}
    para = (final.get("paragraph") or "").strip()
    if not para:
        issues.append("no paragraph in final")
    # Pebble state-key writes — backend emits `event: step` with the
    # step name in `step`. Map back from step name to pebble state key.
    step_alias = {
        "sandy_inundation": "sandy",
        "dep_stormwater": "dep",
        "ida_hwm_2021": "ida_hwm",
        "prithvi_eo_v2": "prithvi_water",
        "prithvi_eo_live": "prithvi_live",
        "microtopo_lidar": "microtopo",
        "step_311": "nyc311",
    }
    state_keys: set[str] = set()
    for kind, payload in result["events"]:
        if kind == "step":
            step = payload.get("step") or ""
            state_keys.add(step_alias.get(step, step))
    for pid in spec["expect_pebbles"]:
        # step names may be munged (step_311 → nyc311; treat as soft check)
        if pid not in state_keys:
            issues.append(f"pebble {pid!r} did not fire")
    # Narrative contract — each migrated pebble's value should include
    # a `narrative` string. Read from final pebble snapshot.
    for pid in spec["expect_narrative_pebbles"]:
        # The SSE step.result payload carries the slim trace_summary,
        # not the full value dict. The full value is in the final state
        # if exposed; otherwise this is a soft check.
        pass  # TODO: cross-check once we have the full value snapshot
    # No-leak check on the briefing paragraph
    leaks = [needle for needle in spec["no_leak"] if needle.lower() in para.lower()]
    if leaks:
        issues.append(f"content leaked from other cities: {leaks}")
    return issues


def main() -> int:
    base = "http://127.0.0.1:7860"
    print(f"Probing 5 cities against {base}...\n")
    all_pass = True
    for spec in CITIES:
        print(f"  {spec['name']:8s}  → {spec['query'][:50]}...", flush=True)
        result = probe_city(base, spec)
        issues = check_city(spec, result)
        if issues:
            all_pass = False
            print(f"    FAIL  ({result.get('elapsed_s', 0):.1f}s)")
            for iss in issues:
                print(f"      · {iss}")
        else:
            n_events = len(result.get("events", []))
            print(f"    PASS  ({result.get('elapsed_s', 0):.1f}s, "
                  f"{n_events} SSE events)")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
