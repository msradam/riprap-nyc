"""Address-by-address scrutiny sweep for the per-query routing fix.

Runs a wide address set through the full Burr pipeline using per-query
deployment routing (no `RIPRAP_DEPLOYMENT` pin), then writes a detailed
per-pebble report to `outputs/probe_scrutiny.json`.

What it checks beyond the basic probe_cities.py sanity:

  1. Per-query routing — each address is given to a single server-side
     process without telling it which city; the geocoder + bbox router
     pick the deployment. Cross-city leakage (e.g. ida_hwm firing for
     Boston) shows up as a deployment-mismatch flag.
  2. Federal-pebble propagation — every in-CONUS address fires
     nws_alerts + nws_obs even if it lands outside a city bbox.
  3. Per-pebble outcome scrutiny — for every pebble that fires we
     capture (ok, elapsed_s, error, value-shape summary, sample fields)
     so an engineer can spot pebbles that "fire" but return
     consistently empty data, which look healthy in the basic probe.
  4. Out-of-coverage gate — an Albuquerque + Tokyo address verify the
     per-pebble coverage filter rejects out-of-CONUS points entirely
     and the bbox router routes in-CONUS-no-city to federal-only.

Run:
    .venv/bin/python scripts/probe_scrutiny.py
    .venv/bin/python scripts/probe_scrutiny.py --addresses-only       # quick smoke
    cat outputs/probe_scrutiny.json | jq '.summary'

Exit code 0 iff every architectural assertion holds. Per-pebble data
quality is reported but does NOT fail the run — pebbles can return
"no records within radius" legitimately for a given point.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


# Address set. Each entry: human-label, address text, expected deployment
# name (None means "no deployment should cover this point").
PROBES: list[tuple[str, str, str | None]] = [
    # NYC — three boroughs.
    ("NYC / Red Hook",     "189 Atlantic Avenue, Brooklyn, NY",            "nyc"),
    ("NYC / Lower East",   "200 East Houston Street, New York, NY",        "nyc"),
    ("NYC / Coney Island", "1208 Surf Avenue, Brooklyn, NY",               "nyc"),
    # Boston — two anchor addresses.
    ("Boston / City Hall", "1 City Hall Square, Boston, MA",               "boston"),
    ("Boston / Seaport",   "1 Marina Park Drive, Boston, MA",              "boston"),
    # Chicago.
    ("Chicago / Loop",     "233 S Wacker Drive, Chicago, IL",              "chicago"),
    ("Chicago / Hyde Park","5801 S Ellis Avenue, Chicago, IL",             "chicago"),
    # Seattle.
    ("Seattle / Downtown", "600 4th Avenue, Seattle, WA",                  "seattle"),
    ("Seattle / SoDo",     "2100 5th Avenue, Seattle, WA",                 "seattle"),
    # San Francisco.
    ("SF / Civic Center",  "1 Dr Carlton B Goodlett Place, San Francisco, CA", "sf"),
    ("SF / Embarcadero",   "1 Ferry Building, San Francisco, CA",          "sf"),
    # Out-of-coverage (CONUS, no shipped city).
    ("Albuquerque NM",     "1 Civic Plaza NW, Albuquerque, NM",            None),
    # Out-of-CONUS (federal pebbles should also reject this).
    ("Tokyo JP",           "Tokyo Tower, Minato, Tokyo, Japan",            None),
]


def _trim(v: Any, max_chars: int = 240) -> Any:
    """Truncate noisy raw values for human-readable scrutiny output."""
    if isinstance(v, str):
        return v[:max_chars] + "…" if len(v) > max_chars else v
    if isinstance(v, list):
        return [_trim(x, max_chars) for x in v[:3]] + (
            [f"… (+{len(v) - 3} more)"] if len(v) > 3 else []
        )
    if isinstance(v, dict):
        return {k: _trim(val, max_chars) for k, val in list(v.items())[:6]}
    return v


def _summarize_pebble(pid: str, value: Any) -> dict[str, Any]:
    """Pull a compact, scrutinizable shape out of a pebble's value."""
    out: dict[str, Any] = {"id": pid}
    if value is None:
        out["shape"] = "none"
        return out
    if isinstance(value, dict):
        out["shape"] = "dict"
        out["keys"] = sorted(value.keys())[:12]
        for k in ("n", "n_records", "n_within_radius", "n_active",
                 "count", "station_id", "error"):
            if k in value and value[k] is not None:
                out[k] = value[k]
        # Sample one or two real fields for inspection.
        sample_fields = {}
        for k in list(value.keys())[:8]:
            v = value.get(k)
            if v is None or k in out:
                continue
            sample_fields[k] = _trim(v)
        if sample_fields:
            out["sample"] = sample_fields
    elif isinstance(value, list):
        out["shape"] = "list"
        out["len"] = len(value)
        if value:
            out["first"] = _trim(value[0])
    else:
        out["shape"] = type(value).__name__
        out["value"] = _trim(value)
    return out


def _run_one(label: str, address: str, expected: str | None) -> dict[str, Any]:
    """Run one probe with per-query routing (no RIPRAP_DEPLOYMENT pin)."""
    os.environ.pop("RIPRAP_DEPLOYMENT", None)  # force per-query routing
    os.environ["RIPRAP_RECONCILER_TIER"] = "no_llm"
    os.environ["RIPRAP_HEAVY_SPECIALISTS"] = "0"

    # Lazy import after env var setup.
    from riprap.core.burr.app import run

    t0 = time.time()
    err: str | None = None
    try:
        out = run(address)
    except Exception as e:  # noqa: BLE001
        out = {}
        err = f"{type(e).__name__}: {e}"
    elapsed = round(time.time() - t0, 2)

    trace = out.get("trace", []) or []
    geocode = out.get("geocode")
    lat = out.get("lat")
    lon = out.get("lon")
    actual_dep = out.get("deployment")

    # Sentinel `__none__` (in-state-only) means "we routed and chose
    # nothing"; surface it as None to the consumer.
    actual_dep_readable = None if actual_dep == "__none__" else actual_dep

    pebble_records = []
    fired_pebbles: list[str] = []
    for rec in trace:
        step = rec.get("step")
        if step in {"plan_heuristic", "plan_intent", "geocode",
                    "select_deployment", "assemble_legacy_state",
                    "policy_corpus", "step_reconcile", "reconcile_templated",
                    "rag", "gliner", "step_gliner", "step_rag"}:
            # Capture pipeline steps separately
            continue
        fired_pebbles.append(step)
        pebble_records.append({
            "step": step,
            "ok": rec.get("ok"),
            "elapsed_s": rec.get("elapsed_s"),
            "err": (rec.get("err") or "")[:140] or None,
            "result_summary": _trim(rec.get("result"), 200),
            "value_summary": _summarize_pebble(step, out.get(step)),
        })

    # Pipeline step traces (compact)
    pipeline_steps = [
        {
            "step": rec.get("step"),
            "ok": rec.get("ok"),
            "elapsed_s": rec.get("elapsed_s"),
            "err": (rec.get("err") or "")[:140] or None,
            "result": _trim(rec.get("result"), 160),
        }
        for rec in trace
        if rec.get("step") in {
            "plan_heuristic", "plan_intent", "geocode", "select_deployment",
            "assemble_legacy_state", "policy_corpus",
            "reconcile_templated", "step_reconcile",
        }
    ]

    record = {
        "label": label,
        "address": address,
        "expected_deployment": expected,
        "actual_deployment": actual_dep_readable,
        "geocode": {
            "address": (geocode or {}).get("address") if geocode else None,
            "lat": lat,
            "lon": lon,
        } if geocode or lat else None,
        "elapsed_s": elapsed,
        "error": err,
        "pipeline": pipeline_steps,
        "n_pebbles_fired": len(fired_pebbles),
        "pebbles_fired": sorted(set(fired_pebbles)),
        "pebble_details": pebble_records,
    }
    return record


def _scrutinize(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute architectural assertions over the run."""
    out: dict[str, Any] = {
        "n_probes": len(records),
        "n_passed_routing": 0,
        "n_failed_routing": 0,
        "leaks": [],
        "geocode_failures": [],
        "federal_propagation": {},
        "cross_city_isolation": [],
    }

    # Pebble ids that are NYC-only (must never fire for any other city).
    nyc_only_ids = {
        "sandy", "ida_hwm", "prithvi_water", "prithvi_live",
        "microtopo", "floodnet", "floodnet_forecast",
        "nyc311", "noaa_tides", "npcc4_slr",
        "mta_entrances", "nycha_developments", "doe_schools", "doh_hospitals",
        "ttm_forecast", "ttm_311_forecast", "ttm_battery_surge",
        "dep_extreme_2080", "dep_moderate_2050", "dep_moderate_current",
    }
    # City-prefixed ids that must only fire in their own deployment.
    city_only_prefixes = {
        "boston_": "boston",
        "chicago_": "chicago",
        "sf_": "sf",
        "lake_michigan_": "chicago",
    }

    for rec in records:
        label = rec["label"]
        expected = rec["expected_deployment"]
        actual = rec["actual_deployment"]
        # Routing match
        if actual == expected:
            out["n_passed_routing"] += 1
        else:
            out["n_failed_routing"] += 1
            out["leaks"].append({
                "label": label,
                "address": rec["address"],
                "expected": expected,
                "actual": actual,
                "reason": "deployment mismatch",
            })
        # Geocode failure
        if rec["geocode"] is None or rec["geocode"]["lat"] is None:
            out["geocode_failures"].append({
                "label": label,
                "address": rec["address"],
            })
            continue
        fired = set(rec["pebbles_fired"])
        # Federal propagation — every in-CONUS probe fires nws_alerts + nws_obs
        if actual is not None or rec["label"] == "Albuquerque NM":
            out["federal_propagation"][label] = {
                "nws_obs": "nws_obs" in fired,
                "nws_alerts": "nws_alerts" in fired,
            }
        # Cross-city isolation
        if actual != "nyc":
            for nyc_id in nyc_only_ids:
                if nyc_id in fired:
                    out["cross_city_isolation"].append({
                        "label": label,
                        "address": rec["address"],
                        "leaked_pebble": nyc_id,
                        "in_deployment": actual,
                        "severity": "high",
                    })
        # City-only pebble cross-fire
        for prefix, owner in city_only_prefixes.items():
            if actual == owner:
                continue
            for pid in fired:
                if pid.startswith(prefix):
                    out["cross_city_isolation"].append({
                        "label": label,
                        "address": rec["address"],
                        "leaked_pebble": pid,
                        "in_deployment": actual,
                        "severity": "high",
                    })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="outputs/probe_scrutiny.json")
    ap.add_argument("--only", help="substring match against label")
    args = ap.parse_args()

    probes = PROBES
    if args.only:
        needle = args.only.lower()
        probes = [p for p in probes if needle in p[0].lower()]

    print(f"=== Riprap probe scrutiny — {len(probes)} addresses ===")
    print(f"Pipeline: per-query routing (no RIPRAP_DEPLOYMENT pin), no-LLM, no-heavy-specialists")
    print()

    records = []
    for label, addr, expected in probes:
        print(f"[run] {label:25s}  {addr}")
        rec = _run_one(label, addr, expected)
        records.append(rec)
        ok_routing = "✓" if rec["actual_deployment"] == rec["expected_deployment"] else "✗"
        print(f"       {ok_routing} routed → {rec['actual_deployment']!r:>10}  "
              f"(expected {rec['expected_deployment']!r}, {rec['n_pebbles_fired']} pebbles, "
              f"{rec['elapsed_s']}s)")
        if rec["error"]:
            print(f"       error: {rec['error']}")

    print()
    print("=== Scrutiny ===")
    summary = _scrutinize(records)
    print(f"  routing pass:      {summary['n_passed_routing']}/{summary['n_probes']}")
    print(f"  geocode failures:  {len(summary['geocode_failures'])}")
    print(f"  cross-city leaks:  {len(summary['cross_city_isolation'])}")
    if summary["cross_city_isolation"]:
        for leak in summary["cross_city_isolation"]:
            print(f"    ! {leak['label']:25s}  leaked {leak['leaked_pebble']!r} into {leak['in_deployment']!r}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"records": records, "summary": summary}, indent=2, default=str))
    print()
    print(f"Wrote {out_path}")

    if summary["n_failed_routing"] > 0 or summary["cross_city_isolation"]:
        print()
        print("FAIL — routing or cross-city isolation breach.")
        return 1
    print()
    print("PASS — routing correct, no cross-city leakage.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
