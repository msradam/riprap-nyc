"""Collect per-query benchmark data from the live lablab UI.

Runs each query through `/api/agent/stream`, accumulates the full
SSE trace, and emits a JSON record per query with everything the
benchmark page (docs/BENCHMARKS.md) needs:

  - briefing paragraph
  - per-Stone fired count (Cornerstone / Keystone / Touchstone /
    Lodestone / Capstone)
  - by-design / errored skip rows
  - Mellea attempts, rerolls, requirements passed/failed
  - emissions: total Wh, J, tokens, n_measured, by-kind / by-hardware
  - wall-clock start-to-final
  - geocode (lat/lon, BBL, BIN)

Output: JSON written to outputs/benchmarks.json (or `--out`).

Usage:
  PYTHONPATH=. uv run python scripts/probe_benchmarks.py
  PYTHONPATH=. uv run python scripts/probe_benchmarks.py \\
      --queries "80 Pioneer Street, Brooklyn" "2508 Beach Channel Drive"

Defaults to the canonical four addresses from `scripts/probe_addresses.py`.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.parse import quote

import httpx

DEFAULT_BASE = "https://lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space"
DEFAULT_QUERIES = [
    "80 Pioneer Street, Brooklyn",
    "2508 Beach Channel Drive, Queens",
    "Coney Island I Houses, Brooklyn",
    "Carleton Manor Houses, Queens",
]

STEP_TO_STONE: dict[str, str] = {
    "sandy_inundation": "Cornerstone", "dep_stormwater": "Cornerstone",
    "ida_hwm_2021": "Cornerstone", "prithvi_eo_v2": "Cornerstone",
    "microtopo_lidar": "Cornerstone", "sandy_nta": "Cornerstone",
    "dep_extreme_2080_nta": "Cornerstone", "dep_moderate_2050_nta": "Cornerstone",
    "dep_moderate_current_nta": "Cornerstone", "microtopo_nta": "Cornerstone",
    "mta_entrance_exposure": "Keystone",
    "nycha_development_exposure": "Keystone",
    "doe_school_exposure": "Keystone", "doh_hospital_exposure": "Keystone",
    "terramind_synthesis": "Keystone", "eo_chip_fetch": "Keystone",
    "terramind_buildings": "Keystone",
    "floodnet": "Touchstone", "nyc311": "Touchstone",
    "nws_obs": "Touchstone", "noaa_tides": "Touchstone",
    "prithvi_eo_live": "Touchstone", "terramind_lulc": "Touchstone",
    "nyc311_nta": "Touchstone",
    "nws_alerts": "Lodestone", "ttm_forecast": "Lodestone",
    "ttm_311_forecast": "Lodestone", "floodnet_forecast": "Lodestone",
    "ttm_battery_surge": "Lodestone",
    "reconcile_granite41": "Capstone",
    "mellea_reconcile_address": "Capstone",
    "reconcile_neighborhood": "Capstone",
    "reconcile_development": "Capstone",
    "reconcile_live_now": "Capstone",
}


def stream_events(base: str, q: str, timeout_s: float):
    url = f"{base.rstrip('/')}/api/agent/stream?q={quote(q)}"
    with httpx.Client(timeout=timeout_s) as client:
        with client.stream("GET", url) as r:
            r.raise_for_status()
            event = None
            for line in r.iter_lines():
                if not line:
                    event = None
                    continue
                if line.startswith("event:"):
                    event = line.removeprefix("event:").strip()
                elif line.startswith("data:") and event:
                    body = line.removeprefix("data:").strip()
                    try:
                        yield event, json.loads(body)
                    except Exception:
                        yield event, {"_raw": body}


def collect_one(base: str, q: str, timeout_s: float) -> dict:
    print(f"\n== {q!r} ==", flush=True)
    t0 = time.time()
    fired: dict[str, list[str]] = {s: [] for s in
                                    ("Cornerstone", "Keystone", "Touchstone",
                                     "Lodestone", "Capstone")}
    errored: list[dict] = []
    skipped: list[dict] = []
    final: dict | None = None
    plan: dict | None = None
    n_token_events = 0

    for event, payload in stream_events(base, q, timeout_s):
        if event == "plan":
            plan = payload
        elif event == "token":
            n_token_events += 1
        elif event == "step":
            step = payload.get("step", "")
            ok = bool(payload.get("ok"))
            stone = STEP_TO_STONE.get(step)
            if stone and ok:
                fired[stone].append(step)
            elif not ok:
                err = (payload.get("err") or
                       (payload.get("result") or {}).get("err") or
                       (payload.get("result") or {}).get("skipped") or "")
                row = {"step": step, "stone": stone, "reason": err,
                       "elapsed_s": payload.get("elapsed_s")}
                # Heuristic: by-design skips use neutral language;
                # genuine errors usually contain a Python exception type.
                blob = err.lower()
                is_design_skip = any(p in blob for p in [
                    "no entrances within radius",
                    "only 2 historical",
                    "no schools within radius",
                    "no nycha",
                    "no hospitals within radius",
                    "out of nyc scope",
                    "not in nyc pluto",
                ])
                if is_design_skip:
                    skipped.append(row)
                else:
                    errored.append(row)
        elif event == "final":
            final = payload

    elapsed_s = round(time.time() - t0, 2)
    print(f"   {elapsed_s}s · token events={n_token_events}", flush=True)

    em = (final or {}).get("emissions") or {}
    mel = (final or {}).get("mellea") or {}
    geo = (final or {}).get("geocode") or {}
    return {
        "query": q,
        "wallclock_s": elapsed_s,
        "n_token_events": n_token_events,
        "geocode": {
            "address": geo.get("address"),
            "lat": geo.get("lat"),
            "lon": geo.get("lon"),
            "bbl": geo.get("bbl"),
            "bin": geo.get("bin"),
            "borough": geo.get("borough"),
        },
        "plan": {
            "intent": (plan or {}).get("intent"),
            "specialists": (plan or {}).get("specialists"),
            "rationale": (plan or {}).get("rationale"),
        },
        "stones": {
            stone: {"n_fired": len(steps), "steps": steps}
            for stone, steps in fired.items()
        },
        "errored": errored,
        "skipped_by_design": skipped,
        "mellea": {
            "n_attempts": mel.get("n_attempts"),
            "rerolls": mel.get("rerolls"),
            "requirements_passed": mel.get("requirements_passed"),
            "requirements_failed": mel.get("requirements_failed"),
            "requirements_total": mel.get("requirements_total"),
            "model": mel.get("model"),
        },
        "emissions": {
            "n_calls": em.get("n_calls"),
            "n_measured": em.get("n_measured"),
            "total_wh": em.get("total_wh"),
            "total_mwh": em.get("total_mwh"),
            "total_joules": em.get("total_joules"),
            "total_duration_s": em.get("total_duration_s"),
            "tokens": em.get("tokens"),
            "by_kind": em.get("by_kind"),
            "by_hardware": em.get("by_hardware"),
        },
        "paragraph": (final or {}).get("paragraph"),
        "paragraph_chars": len((final or {}).get("paragraph") or ""),
        "tier": (final or {}).get("tier"),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default=DEFAULT_BASE)
    p.add_argument("--queries", nargs="*", default=DEFAULT_QUERIES)
    p.add_argument("--timeout", type=float, default=600.0)
    p.add_argument("--out", default="outputs/benchmarks.json")
    args = p.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print("== probe_benchmarks ==")
    print(f"  base : {args.base}")
    print(f"  queries: {len(args.queries)}")

    runs = []
    for q in args.queries:
        try:
            runs.append(collect_one(args.base, q, args.timeout))
        except Exception as e:
            print(f"   FAIL {type(e).__name__}: {e}", flush=True)
            runs.append({"query": q, "error": f"{type(e).__name__}: {e}"})

    out = {"base": args.base, "ts": time.time(), "runs": runs}
    out_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nwrote {out_path} ({len(runs)} runs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
