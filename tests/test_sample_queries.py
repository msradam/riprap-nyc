"""Verify the 5 demo sample-query buttons all return rich, useful output.

These five are the buttons we put on the agent landing page; if any
fail or produce empty output, the demo is dead. This is the
gating test before shipping.
"""
from __future__ import annotations

import sys
import time

import httpx

BASE = "http://127.0.0.1:8000"

SAMPLES = [
    {
        "label": "live",
        "q": "is there flooding right now in NYC",
        "intent": "live_now",
        "min_chars": 30,
        "min_specialists_fired": 2,  # at least nws_alerts + noaa_tides
    },
    {
        "label": "address",
        "q": "2940 Brighton 3rd St, Brooklyn",
        "intent": "single_address",
        "min_chars": 100,
        "must_have_geocode": True,
        "must_be_in_sandy": True,
    },
    {
        "label": "neighborhood (coastal)",
        "q": "is Brighton Beach at risk?",
        "intent": "neighborhood",
        "min_chars": 150,
        "must_have_target": "Brighton Beach",
        "min_sandy_fraction": 0.7,
    },
    {
        "label": "neighborhood (inland)",
        "q": "Hollis",
        "intent": "neighborhood",
        "min_chars": 80,
        "must_have_target_borough": "Queens",
    },
    {
        "label": "development_check (marquee)",
        "q": "what are they building in Gowanus and is it risky",
        "intent": "development_check",
        "min_chars": 200,
        "min_n_total": 5,
        "min_n_in_sandy": 1,
        "min_flagged_top": 1,
    },
    {
        "label": "upstate (Albany convention venue)",
        "q": "257 Washington Avenue, Albany NY 12205",
        "intent": "single_address",
        "min_chars": 80,
        "must_resolve_outside_nyc": True,
        # NOAA + NWS pickers should now select Hudson Corridor stations
        "must_pick_albany_stations": True,
        # Reconciler must NOT hallucinate NYC-specific layers for an upstate addr
        # Phrases the reconciler shouldn't claim about an upstate address.
        # Note we accept "Sandy" or "DEP" appearing in scope-guard negation
        # ("does not apply"), only fail on definitive Albany-is-in-NYC claims.
        "must_not_contain_phrases": ["gowanus", "carroll gardens",
                                     "red hook", "brighton beach"],
    },
]

FAILS = []


def run(s):
    label = s["label"]; q = s["q"]
    print(f"\n=== {label}: {q!r}")
    t0 = time.time()
    try:
        r = httpx.get(f"{BASE}/api/agent", params={"q": q}, timeout=240.0)
        r.raise_for_status()
        d = r.json()
    except Exception as e:
        FAILS.append((label, f"HTTP error: {e}"))
        print(f"  ❌ {e}")
        return
    dt = time.time() - t0
    intent = d.get("intent")
    para = d.get("paragraph", "") or ""
    print(f"  intent={intent}  wall={dt:.1f}s  para={len(para)} chars")

    def fail(why):
        FAILS.append((label, why))
        print(f"  ❌ {why}")

    if intent != s["intent"]:
        fail(f"intent {intent} != {s['intent']}")
        return

    if len(para) < s.get("min_chars", 0):
        fail(f"paragraph {len(para)} < min {s['min_chars']}")

    if s.get("must_have_geocode") and not (d.get("geocode") or {}).get("lat"):
        fail("geocode missing lat")
    if s.get("must_be_in_sandy") and d.get("sandy") is not True:
        fail("expected sandy=True")
    if s.get("must_have_target"):
        nta = (d.get("target") or {}).get("nta_name", "")
        if s["must_have_target"].lower() not in nta.lower():
            fail(f"target NTA {nta!r} doesn't contain {s['must_have_target']!r}")
    if s.get("must_have_target_borough"):
        boro = (d.get("target") or {}).get("borough", "")
        if boro != s["must_have_target_borough"]:
            fail(f"target borough {boro!r} != {s['must_have_target_borough']!r}")
    if "min_sandy_fraction" in s:
        f = (d.get("sandy_nta") or {}).get("fraction", 0)
        if f < s["min_sandy_fraction"]:
            fail(f"sandy_nta.fraction {f} < {s['min_sandy_fraction']}")
    if "min_n_total" in s:
        n = (d.get("dob_summary") or {}).get("n_total", 0)
        if n < s["min_n_total"]:
            fail(f"dob.n_total {n} < {s['min_n_total']}")
    if "min_n_in_sandy" in s:
        n = (d.get("dob_summary") or {}).get("n_in_sandy", 0)
        if n < s["min_n_in_sandy"]:
            fail(f"dob.n_in_sandy {n} < {s['min_n_in_sandy']}")
    if "min_flagged_top" in s:
        n = len((d.get("dob_summary") or {}).get("flagged_top") or [])
        if n < s["min_flagged_top"]:
            fail(f"flagged_top size {n} < {s['min_flagged_top']}")
    if "min_specialists_fired" in s:
        n = sum(1 for k in ("noaa_tides","nws_alerts","nws_obs","ttm_forecast")
                if d.get(k) is not None)
        if n < s["min_specialists_fired"]:
            fail(f"only {n} live specialists fired, need {s['min_specialists_fired']}")
    if s.get("must_resolve_outside_nyc"):
        geo = d.get("geocode") or {}
        lat, lon = geo.get("lat"), geo.get("lon")
        in_nyc = lat is not None and 40.49 <= lat <= 40.92 and -74.27 <= lon <= -73.69
        if in_nyc:
            fail(f"resolved coords ({lat},{lon}) ARE inside NYC bbox; expected upstate")
    if s.get("must_pick_albany_stations"):
        tides_id = (d.get("noaa_tides") or {}).get("station_id")
        obs_id = (d.get("nws_obs") or {}).get("station_id")
        if tides_id != "8518995":
            fail(f"NOAA station {tides_id!r} != 8518995 (Albany Hudson)")
        if obs_id != "KALB":
            fail(f"NWS ASOS {obs_id!r} != KALB (Albany Intl)")
    if s.get("must_not_contain_phrases"):
        bad = [p for p in s["must_not_contain_phrases"]
               if p.lower() in para.lower()]
        if bad:
            fail(f"paragraph leaked NYC content for upstate addr: {bad}")

    if not any(label in para for label in ["**Status.**", "**Live signals.**", "**Flagged projects.**"]):
        # Soft check — paragraph should have at least one section header
        print("  ⚠ no recognized section header (soft)")
    else:
        print("  ✓ has section header")
    print(f"  ✓ {label}")


def main():
    try:
        httpx.get(f"{BASE}/", timeout=5.0)
    except Exception as e:
        print(f"server not up: {e}")
        sys.exit(1)
    print("=" * 60)
    print(f"SAMPLE-QUERY GATE — {len(SAMPLES)} buttons")
    print("=" * 60)
    for s in SAMPLES:
        run(s)
    print("\n" + "=" * 60)
    if FAILS:
        print(f"FAILED ({len(FAILS)}):")
        for label, why in FAILS:
            print(f"  - {label}: {why}")
        sys.exit(1)
    else:
        print("ALL 5 SAMPLE QUERIES PASS — safe to ship buttons")
    print("=" * 60)


if __name__ == "__main__":
    main()
