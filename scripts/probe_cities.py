"""Multi-city deployment probe — verifies the framework claim end-to-end.

Loops over each Riprap deployment, geocodes a known anchor address, runs
the full Burr FSM, and asserts:

  - compliance.passed is True
  - compliance.n_passed == 13 (the full predicate set)
  - federal pebbles (nws_obs, nws_alerts) populated
  - city-specific pebble (where present) populated with n_records ≥ 0

Designed to be run cheaply, repeatedly, against the real upstream APIs.
No LLM is invoked (RIPRAP_RECONCILER_TIER=no_llm), so failure modes are
deterministic: HTTP, schema, or geocoding.

Exit code 0 iff every deployment passes all assertions. Designed for
both local verification and CI.

Usage:
    .venv/bin/python scripts/probe_cities.py
    .venv/bin/python scripts/probe_cities.py --only boston
    .venv/bin/python scripts/probe_cities.py --json outputs/probe_cities.json
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


# Each entry: deployment directory under deployments/, anchor address,
# and the pebble keys we expect populated (non-None value).
PROBES: list[dict[str, Any]] = [
    {
        "deployment": "deployments/nyc",
        "address": "189 Atlantic Avenue, Brooklyn, NY",
        "expect_city_pebble": "nyc311",
        "expect_federal": ["nws_obs", "nws_alerts"],
    },
    {
        "deployment": "deployments/chicago",
        "address": "233 S Wacker Dr, Chicago, IL",
        "expect_city_pebble": "chicago_311",
        "expect_federal": ["nws_obs", "nws_alerts"],
    },
    {
        "deployment": "deployments/seattle",
        "address": "2100 5th Ave, Seattle, WA",
        "expect_city_pebble": None,  # 311 dataset has no geometry; skipped
        "expect_federal": ["nws_obs", "nws_alerts"],
    },
    {
        "deployment": "deployments/sf",
        "address": "1 Dr Carlton B Goodlett Pl, San Francisco, CA",
        "expect_city_pebble": "sf_311",
        "expect_federal": ["nws_obs", "nws_alerts"],
    },
    {
        "deployment": "deployments/boston",
        "address": "1 City Hall Square, Boston, MA",
        "expect_city_pebble": "boston_311",
        "expect_federal": ["nws_obs", "nws_alerts"],
    },
]


def _run_one(probe: dict[str, Any]) -> dict[str, Any]:
    os.environ["RIPRAP_DEPLOYMENT"] = probe["deployment"]
    os.environ["RIPRAP_RECONCILER_TIER"] = "no_llm"

    for modname in [
        m for m in list(sys.modules)
        if m.startswith("riprap.") or m.startswith("app.") or m == "riprap"
    ]:
        sys.modules.pop(modname, None)

    import riprap.core.burr.app as burr_app

    t0 = time.time()
    try:
        result = burr_app.run(probe["address"])
    except Exception as e:  # noqa: BLE001
        return {
            "deployment": probe["deployment"],
            "address": probe["address"],
            "ok": False,
            "elapsed_s": round(time.time() - t0, 2),
            "error": f"run() raised: {type(e).__name__}: {e}",
        }
    elapsed = round(time.time() - t0, 2)

    compliance = result.get("compliance") or {}
    n_passed = compliance.get("n_passed")
    n_total = compliance.get("n_total")
    passed = compliance.get("passed") is True

    failures: list[str] = []
    if not passed:
        failures.append(
            f"compliance.passed=False ({n_passed}/{n_total}), failed={compliance.get('failed')}"
        )
    if n_passed is not None and n_passed != 13:
        failures.append(f"n_passed={n_passed}, expected 13")

    for fed_key in probe.get("expect_federal", []):
        v = result.get(fed_key)
        if v is None:
            failures.append(f"federal pebble '{fed_key}' missing entirely")

    city_key = probe.get("expect_city_pebble")
    city_n = None
    if city_key:
        city_val = result.get(city_key)
        if city_val is None:
            failures.append(f"city pebble '{city_key}' missing")
        elif isinstance(city_val, dict):
            # Different pebbles use different count field names — try the
            # common spellings before failing.
            for field in ("n_records", "n", "n_within_radius", "count"):
                if field in city_val:
                    city_n = city_val[field]
                    break
            if city_n is None:
                failures.append(
                    f"city pebble '{city_key}' has no count field "
                    f"(tried n_records / n / n_within_radius / count); "
                    f"keys present: {sorted(city_val.keys())[:8]}"
                )

    paragraph = result.get("paragraph") or ""
    if "[" not in paragraph or "Live Observer" not in paragraph:
        failures.append("paragraph missing expected citations / sections")

    return {
        "deployment": probe["deployment"],
        "address": probe["address"],
        "ok": not failures,
        "elapsed_s": elapsed,
        "n_passed": n_passed,
        "n_total": n_total,
        "city_pebble": city_key,
        "city_n_records": city_n,
        "failures": failures,
        "paragraph_head": paragraph[:200],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--only", help="run only this deployment dir (e.g. deployments/boston)")
    p.add_argument("--json", dest="json_out", help="write full results JSON to this path")
    args = p.parse_args()

    probes = PROBES
    if args.only:
        probes = [x for x in PROBES if x["deployment"] == args.only or x["deployment"].endswith(args.only)]
        if not probes:
            print(f"no probe matched --only {args.only}")
            return 2

    results = []
    print(f"running {len(probes)} city probes (no-LLM tier)\n")
    for probe in probes:
        r = _run_one(probe)
        results.append(r)
        status = "PASS" if r["ok"] else "FAIL"
        city = r.get("city_pebble") or "(no city pebble)"
        cn = r.get("city_n_records")
        cn_str = f"n={cn}" if cn is not None else "—"
        print(
            f"  [{status}] {r['deployment']:<24} {r['address']:<55} "
            f"compliance={r.get('n_passed')}/{r.get('n_total')}  {city}={cn_str}  ({r['elapsed_s']}s)"
        )
        for f in r.get("failures", []):
            print(f"        ↳ {f}")

    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(json.dumps(results, indent=2, default=str))
        print(f"\nwrote {args.json_out}")

    n_pass = sum(1 for r in results if r["ok"])
    print(f"\n{n_pass}/{len(results)} deployments PASS")
    return 0 if n_pass == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
