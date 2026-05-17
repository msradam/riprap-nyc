"""UI ↔ backend scaffold diff — programmatic check on what the UI would render.

Hits the three endpoints the SvelteKit UI consumes per query:

  /api/deployment         — feeds the header chip ("Flood-exposure briefing · NYC")
  /api/pebbles            — feeds the findings-card scaffold + pebbleManifest store
  /api/agent?q=<address>  — feeds the actual briefing data + trace

…and reports the three-way disagreement that produces visible bugs like
"querying Boston shows the NYC chip and an NYC pebble scaffold while the
data shows Boston pebbles fired."

Why this exists: spotting these desyncs in a browser took 20+ minutes of
Playwright wrangling. This script does it in 5 seconds with no DOM, no
browser, no SSE. Designed to run against a live uvicorn on :7860.

Usage:
    .venv/bin/python scripts/ui_scaffold_diff.py
    .venv/bin/python scripts/ui_scaffold_diff.py --base-url http://127.0.0.1:7860
    .venv/bin/python scripts/ui_scaffold_diff.py --only boston

Exit code 0 iff every probe is internally consistent: chip city matches
the geocoded city, the pebble scaffold loaded by the UI matches the
pebbles that actually fired, and no NYC-only pebble id leaks into a
non-NYC scaffold.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import URLError

# Same 6 anchor probes as probe_scrutiny.py — keep the address set in
# lockstep so the two scripts cover the same matrix.
PROBES: list[tuple[str, str, str | None]] = [
    ("NYC / Atlantic Ave",      "189 Atlantic Avenue, Brooklyn, NY",                  "nyc"),
    ("Boston / City Hall",      "1 City Hall Square, Boston, MA",                     "boston"),
    ("Chicago / Loop",          "233 S Wacker Drive, Chicago, IL",                    "chicago"),
    ("Seattle / Downtown",      "600 4th Avenue, Seattle, WA",                        "seattle"),
    ("SF / Civic Center",       "1 Dr Carlton B Goodlett Place, San Francisco, CA",   "sf"),
    ("Albuquerque NM",          "1 Civic Plaza NW, Albuquerque, NM",                  None),
]

# Pebble ids the UI cardAdapter has *hardcoded* NYC-specific builder
# functions for (buildSandy, buildIdaHwm, buildPrithviWater, ...).
# These render as empty "□" cards when the API data doesn't include
# them — the exact failure mode the user reported when a Boston query
# rendered an NYC scaffold.
NYC_ONLY_CARD_BUILDERS = {
    "sandy", "ida_hwm", "prithvi_water", "prithvi_live",
    "microtopo", "floodnet", "nyc311", "noaa_tides",
    "mta_entrances", "nycha_developments", "doe_schools", "doh_hospitals",
    "ttm_forecast", "ttm_battery_surge", "npcc4_slr", "floodnet_forecast",
    "dep_extreme_2080", "dep_moderate_2050", "dep_moderate_current",
    "terramind_buildings", "terramind_lulc",
}

PIPELINE_STEPS = {
    "plan_heuristic", "plan_intent", "geocode", "select_deployment",
    "assemble_legacy_state", "policy_corpus", "reconcile_templated",
    "step_reconcile", "rag", "gliner", "step_gliner", "step_rag",
}


def _get(base_url: str, path: str, timeout: float = 90) -> Any:
    url = base_url.rstrip("/") + path
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=timeout) as resp:  # noqa: S310 — controlled URL
        return json.loads(resp.read())


def _probe_one(base_url: str, address: str, expected: str | None) -> dict[str, Any]:
    """One probe = three GETs + the diff report."""
    result: dict[str, Any] = {"address": address, "expected": expected, "errors": []}

    # 1. /api/deployment — what the header chip displays
    try:
        deployment_endpoint = _get(base_url, "/api/deployment")
        result["chip"] = {
            "name": deployment_endpoint.get("name"),
            "city": deployment_endpoint.get("city"),
            "hazard": deployment_endpoint.get("hazard"),
        }
    except (URLError, OSError, ValueError) as e:
        result["chip"] = None
        result["errors"].append(f"/api/deployment: {e}")

    # 2. /api/pebbles — what the findings-card scaffold lists
    try:
        pebbles_endpoint = _get(base_url, "/api/pebbles")
        result["scaffold"] = {
            "n_pebbles": len(pebbles_endpoint.get("pebbles", [])),
            "pebble_ids": sorted(p["id"] for p in pebbles_endpoint.get("pebbles", [])),
            "stones": [s["id"] for s in pebbles_endpoint.get("stones", [])],
        }
    except (URLError, OSError, ValueError) as e:
        result["scaffold"] = None
        result["errors"].append(f"/api/pebbles: {e}")

    # 3. /api/agent — the actual run
    try:
        out = _get(base_url, f"/api/agent?q={quote(address)}")
        trace = out.get("trace", []) or []
        fired = sorted({
            r.get("step") for r in trace
            if r.get("step") and r["step"] not in PIPELINE_STEPS and r.get("ok") is True
        })
        result["run"] = {
            "deployment": out.get("deployment"),
            "lat": out.get("lat"),
            "lon": out.get("lon"),
            "geocode_address": (out.get("geocode") or {}).get("address"),
            "fired_pebbles": fired,
            "compliance_passed": (out.get("compliance") or {}).get("passed"),
        }
    except (URLError, OSError, ValueError) as e:
        result["run"] = None
        result["errors"].append(f"/api/agent: {e}")

    # ─── Diff ──────────────────────────────────────────────────────
    diffs: list[dict[str, Any]] = []
    chip = result.get("chip") or {}
    scaffold = result.get("scaffold") or {}
    run = result.get("run") or {}
    actual = run.get("deployment")

    # A. Chip vs. run
    if chip and actual is not None and chip.get("name") != actual:
        diffs.append({
            "kind": "chip_mismatch",
            "severity": "high",
            "detail": (
                f"Header chip shows {chip.get('name')!r} but query routed to "
                f"{actual!r} — UI tells the user the wrong city."
            ),
        })

    # B. Scaffold vs. run — does the UI's pebble scaffold include the
    # pebbles that actually fired?
    if scaffold and run.get("fired_pebbles"):
        scaffold_ids = set(scaffold.get("pebble_ids") or [])
        missing = [pid for pid in run["fired_pebbles"] if pid not in scaffold_ids]
        if missing:
            diffs.append({
                "kind": "scaffold_missing_fired_pebble",
                "severity": "high",
                "detail": (
                    f"Pebbles that fired but UI scaffold doesn't list "
                    f"(will not render): {missing}"
                ),
            })

    # C. Scaffold contains NYC-only builders that didn't fire — they'll
    # render as empty "□" cards (the visible 'NYC scaffold for Boston query' bug)
    if scaffold and run and actual not in (None, "nyc"):
        scaffold_ids = set(scaffold.get("pebble_ids") or [])
        ghosts = sorted(scaffold_ids & NYC_ONLY_CARD_BUILDERS)
        if ghosts:
            diffs.append({
                "kind": "ghost_cards_in_scaffold",
                "severity": "high",
                "detail": (
                    f"UI scaffold for {actual!r} run includes NYC-only pebble "
                    f"ids that will render as empty '□ not invoked' cards: {ghosts[:6]}"
                    + ("…" if len(ghosts) > 6 else "")
                ),
            })

    # D. Expected vs. actual routing
    if expected is not None and actual != expected:
        diffs.append({
            "kind": "routing_mismatch",
            "severity": "critical",
            "detail": f"Expected deployment={expected!r}, got {actual!r}",
        })

    result["diffs"] = diffs
    return result


def _print_report(records: list[dict[str, Any]]) -> int:
    """Returns exit code (0 = clean, 1 = at least one high/critical diff)."""
    rc = 0
    print()
    print("=== UI ↔ backend scaffold diff ===")
    print()
    for r in records:
        addr = r["address"]
        expected = r["expected"]
        chip = (r.get("chip") or {}).get("name")
        scaffold_n = (r.get("scaffold") or {}).get("n_pebbles")
        run_dep = (r.get("run") or {}).get("deployment")
        fired = (r.get("run") or {}).get("fired_pebbles") or []

        diffs = r["diffs"]
        status = "✓" if not diffs else "✗"
        print(f"{status} {addr}")
        print(f"     expected={expected!r:>10}  chip={chip!r:>8}  "
              f"scaffold_n={scaffold_n!r:>4}  run={run_dep!r:>10}  fired={len(fired):>2}")
        if r["errors"]:
            for e in r["errors"]:
                print(f"     ERROR  {e}")
                rc = 1
        for d in diffs:
            sev = d["severity"].upper()
            print(f"     [{sev}] {d['kind']}")
            print(f"             {d['detail']}")
            if sev in ("HIGH", "CRITICAL"):
                rc = 1
        print()
    return rc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:7860")
    ap.add_argument("--only", help="substring match against probe label")
    ap.add_argument("--json", help="write the diff report to this file as JSON")
    args = ap.parse_args()

    probes = PROBES
    if args.only:
        needle = args.only.lower()
        probes = [p for p in probes if needle in p[0].lower()]

    print(f"Probing {len(probes)} addresses against {args.base_url}…")

    records = []
    for label, addr, expected in probes:
        print(f"  · {label}")
        rec = _probe_one(args.base_url, addr, expected)
        rec["label"] = label
        records.append(rec)

    rc = _print_report(records)

    if args.json:
        from pathlib import Path
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(records, indent=2))
        print(f"Wrote {out}")

    if rc == 0:
        print("PASS — chip, scaffold, and run agree across every probe.")
    else:
        print("FAIL — UI would render misaligned data; see [HIGH] / [CRITICAL] above.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
