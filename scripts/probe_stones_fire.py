"""Probe the lablab UI: does every Stone fire on the canonical address,
and is the dep-availability regression that the SAT_MAY_9 run hit
(`RuntimeError: operator torchvision::nms does not exist` on the local
fallback path; `deps unavailable on this deployment: terratorch
(RuntimeError), peft` on TerraMind LULC + Buildings) gone?

This consumes /api/agent/stream as a curl-style SSE client (no
EventSource needed) and asserts:
  1. Every step event has a Stone mapping (per web/main.py:_STEP_TO_STONE)
  2. All five Stones (Cornerstone, Keystone, Touchstone, Lodestone,
     Capstone) emit at least one fired step
  3. No step result mentions:
       - "torchvision::nms"
       - "deps unavailable on this deployment: terratorch"
       - "peft (RuntimeError)"
  4. Final emissions block carries L4 hardware + non-zero tokens

Usage:
  PYTHONPATH=. uv run python scripts/probe_stones_fire.py
  PYTHONPATH=. uv run python scripts/probe_stones_fire.py \\
      --base http://127.0.0.1:8000 \\
      --query "Carleton Manor Houses, Queens"

Exit 0 on success, 1 on any failure. Prints a per-Stone summary.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from urllib.parse import quote

import httpx

DEFAULT_BASE = "https://lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space"
DEFAULT_QUERY = "80 Pioneer Street, Brooklyn"

EXPECTED_STONES = {"Cornerstone", "Keystone", "Touchstone",
                    "Lodestone", "Capstone"}

# Step name → Stone, mirrored from web/main.py:_STEP_TO_STONE so this
# script can be run without importing the app package.
STEP_TO_STONE: dict[str, str] = {
    "sandy_inundation":           "Cornerstone",
    "dep_stormwater":             "Cornerstone",
    "ida_hwm_2021":               "Cornerstone",
    "prithvi_eo_v2":              "Cornerstone",
    "microtopo_lidar":            "Cornerstone",
    "sandy_nta":                  "Cornerstone",
    "dep_extreme_2080_nta":       "Cornerstone",
    "dep_moderate_2050_nta":      "Cornerstone",
    "dep_moderate_current_nta":   "Cornerstone",
    "microtopo_nta":              "Cornerstone",
    "mta_entrance_exposure":      "Keystone",
    "nycha_development_exposure": "Keystone",
    "doe_school_exposure":        "Keystone",
    "doh_hospital_exposure":      "Keystone",
    "terramind_synthesis":        "Keystone",
    "eo_chip_fetch":              "Keystone",
    "terramind_buildings":        "Keystone",
    "floodnet":                   "Touchstone",
    "nyc311":                     "Touchstone",
    "nws_obs":                    "Touchstone",
    "noaa_tides":                 "Touchstone",
    "prithvi_eo_live":            "Touchstone",
    "terramind_lulc":             "Touchstone",
    "nyc311_nta":                 "Touchstone",
    "nws_alerts":                 "Lodestone",
    "ttm_forecast":               "Lodestone",
    "ttm_311_forecast":           "Lodestone",
    "floodnet_forecast":          "Lodestone",
    "ttm_battery_surge":          "Lodestone",
    "reconcile_granite41":        "Capstone",
    "mellea_reconcile_address":   "Capstone",
    "reconcile_neighborhood":     "Capstone",
    "reconcile_development":      "Capstone",
    "reconcile_live_now":         "Capstone",
}

DEP_REGRESSION_PATTERNS = [
    "torchvision::nms",
    "deps unavailable on this deployment: terratorch",
    "peft (RuntimeError)",
]


def stream_events(base: str, q: str, timeout_s: float = 360.0):
    """Yield (event, data_dict) for each SSE record."""
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


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default=DEFAULT_BASE)
    p.add_argument("--query", default=DEFAULT_QUERY)
    p.add_argument("--timeout", type=float, default=360.0)
    args = p.parse_args()

    print("== probe_stones_fire ==")
    print(f"  base : {args.base}")
    print(f"  query: {args.query}\n")

    t0 = time.time()
    fired: dict[str, list[dict]] = {s: [] for s in EXPECTED_STONES}
    errored: list[dict] = []
    dep_regressions: list[dict] = []
    final: dict | None = None

    for event, payload in stream_events(args.base, args.query, args.timeout):
        if event == "step":
            step = payload.get("step", "")
            ok = bool(payload.get("ok"))
            stone = STEP_TO_STONE.get(step)
            if stone:
                if ok:
                    fired[stone].append(payload)
                else:
                    errored.append(payload)
                # Check the result + err strings against regression patterns.
                blob = json.dumps(payload, default=str).lower()
                for pat in DEP_REGRESSION_PATTERNS:
                    if pat.lower() in blob:
                        dep_regressions.append({"pattern": pat,
                                                "step": step,
                                                "payload": payload})
                        break
        elif event == "final":
            final = payload

    elapsed = time.time() - t0

    # ---- assertions
    failures: list[str] = []

    missing_stones = [s for s in EXPECTED_STONES if not fired[s]]
    if missing_stones:
        failures.append(f"Stones with no fired step: {missing_stones}")

    if dep_regressions:
        for d in dep_regressions[:10]:
            failures.append(
                f"dep regression in step '{d['step']}': matched '{d['pattern']}'"
            )

    if final is None:
        failures.append("no `final` event received")
    else:
        em = final.get("emissions") or {}
        n_calls = em.get("n_calls", 0)
        if n_calls == 0:
            failures.append("emissions ledger is empty (n_calls=0)")
        hw_keys = list((em.get("by_hardware") or {}).keys())
        if hw_keys and "nvidia_l4" not in hw_keys:
            failures.append(f"expected nvidia_l4 in emissions; got {hw_keys}")

    # ---- print summary
    print("-- step events --")
    for s in ("Cornerstone", "Keystone", "Touchstone", "Lodestone", "Capstone"):
        steps = [p.get("step") for p in fired[s]]
        print(f"  {s:11s} fired={len(fired[s]):2d}  {steps}")
    if errored:
        print(f"\n-- {len(errored)} step events with ok=False --")
        for p in errored[:8]:
            err = (p.get("err") or
                   (p.get("result") or {}).get("err") or
                   (p.get("result") or {}).get("skipped") or "?")
            print(f"  {p.get('step'):28s} {err[:140]}")

    if final and (em := final.get("emissions")):
        print("\n-- emissions --")
        print(f"  n_calls       = {em.get('n_calls')}")
        print(f"  n_measured    = {em.get('n_measured')}")
        print(f"  total_wh      = {em.get('total_wh')}")
        print(f"  total_joules  = {em.get('total_joules')}")
        print(f"  tokens.total  = {(em.get('tokens') or {}).get('total')}")
        print(f"  by_hardware   = {list((em.get('by_hardware') or {}).keys())}")

    print(f"\nelapsed: {elapsed:.1f}s")

    if failures:
        print(f"\nFAIL ({len(failures)} issue{'s' if len(failures) != 1 else ''}):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nPASS — all 5 Stones fired, no torchvision/terratorch dep regression.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
