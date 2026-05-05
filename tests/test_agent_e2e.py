"""End-to-end tests for the agentic /api/agent endpoint.

Run against a live local server:
    .venv/bin/uvicorn web.main:app --port 8000 &
    .venv/bin/python tests/test_agent_e2e.py

Each test sends a query, asserts on the planner's intent + structure,
times the round-trip, and shows what the user would see. Output is a
pass/fail summary so we can iterate without clicking through the UI.
"""
from __future__ import annotations

import sys
import time

import httpx

BASE = "http://127.0.0.1:8000"
HARD_FAIL = []   # serious issues (route returns 500, no paragraph, etc.)
SOFT_WARN = []   # quality issues (citation tags missing, etc.)


def case(name, q, expected_intent, asserts):
    """One test case. `asserts` is a list of (label, callable(d) → bool)."""
    print(f"\n=== {name}")
    print(f"  query: {q!r}")
    t0 = time.time()
    try:
        r = httpx.get(f"{BASE}/api/agent", params={"q": q}, timeout=240.0)
        r.raise_for_status()
        d = r.json()
    except Exception as e:
        print(f"  ❌ HTTP/JSON error: {e!r}")
        HARD_FAIL.append((name, str(e)))
        return None
    dt = time.time() - t0

    intent = d.get("intent")
    plan = d.get("plan", {})
    print(f"  → intent={intent}  total_s={d.get('total_s', '?')}  wall_s={dt:.2f}")
    print(f"  → plan.specialists ({len(plan.get('specialists', []))}): "
          f"{plan.get('specialists', [])}")
    print(f"  → plan.rationale: {plan.get('rationale', '')[:120]}")

    if intent != expected_intent:
        print(f"  ❌ expected intent={expected_intent}, got {intent}")
        HARD_FAIL.append((name, f"intent {intent} != {expected_intent}"))

    for label, fn in asserts:
        try:
            res = fn(d)
        except Exception as e:
            res = False
            print(f"  ❌ assert raised — {label}: {e!r}")
        if res:
            print(f"  ✓ {label}")
        else:
            print(f"  ❌ {label}")
            HARD_FAIL.append((name, label))

    para = d.get("paragraph", "") or ""
    has_section = "**Status.**" in para or "**Live signals.**" in para
    if not has_section:
        print("  ⚠ no recognizable section header in paragraph")
        SOFT_WARN.append((name, "no section header"))
    has_cite = "[" in para and "]" in para
    if not has_cite:
        SOFT_WARN.append((name, "paragraph has no [doc_id] citations"))
        print("  ⚠ paragraph has no [doc_id] citations")
    return d


def has_signal(key):
    def _check(d):
        v = d.get(key)
        return v is not None and v != [] and v != {}
    return _check


def has_target_field(field, expected_substring):
    def _check(d):
        t = d.get("target") or {}
        return expected_substring.lower() in (t.get(field, "") or "").lower()
    return _check


def fraction_inside(lo, hi):
    def _check(d):
        s = d.get("sandy_nta") or {}
        f = s.get("fraction", -1)
        return lo <= f <= hi
    return _check


def main():
    # Sanity check the server is up
    try:
        httpx.get(f"{BASE}/", timeout=5.0)
    except Exception as e:
        print(f"server not reachable at {BASE}: {e!r}")
        sys.exit(1)

    print("=" * 60)
    print("PLANNER + EXECUTOR END-TO-END TESTS")
    print("=" * 60)

    # ---- single_address ----------------------------------------------------
    case("single_address: full NYC address",
         "116-50 Sutphin Blvd, Queens",
         expected_intent="single_address",
         asserts=[
             ("geocode populated",  lambda d: (d.get("geocode") or {}).get("address")),
             ("dep populated",      has_signal("dep")),
             ("nyc311 populated",   has_signal("nyc311")),
             ("paragraph nonempty", lambda d: len(d.get("paragraph", "")) > 50),
         ])

    case("single_address: coastal Brooklyn (Sandy hit)",
         "2940 Brighton 3rd St, Brooklyn",
         expected_intent="single_address",
         asserts=[
             ("sandy is True",      lambda d: d.get("sandy") is True),
             ("dep populated",      has_signal("dep")),
             ("microtopo populated", has_signal("microtopo")),
         ])

    # ---- neighborhood ------------------------------------------------------
    case("neighborhood: Brighton Beach (high coastal exposure)",
         "Brighton Beach",
         expected_intent="neighborhood",
         asserts=[
             ("target NTA name = Brighton Beach",
                has_target_field("nta_name", "Brighton Beach")),
             ("target borough = Brooklyn",
                has_target_field("borough", "Brooklyn")),
             ("sandy_nta fraction > 0.5", fraction_inside(0.5, 1.0)),
             ("dep_nta has 3 scenarios",
                lambda d: len(d.get("dep_nta") or {}) == 3),
             ("nyc311_nta n > 50",
                lambda d: (d.get("nyc311_nta") or {}).get("n", 0) > 50),
             ("microtopo_nta has hand_median_m",
                lambda d: (d.get("microtopo_nta") or {}).get("hand_median_m") is not None),
         ])

    case("neighborhood: Carroll Gardens (inland Brooklyn, Ida-deaths archetype)",
         "Carroll Gardens",
         expected_intent="neighborhood",
         asserts=[
             ("target borough = Brooklyn",
                has_target_field("borough", "Brooklyn")),
             ("sandy_nta fraction < 0.5 (inland)",
                lambda d: (d.get("sandy_nta") or {"fraction": 1}).get("fraction", 1) < 0.5),
             ("nyc311_nta n > 0",
                lambda d: (d.get("nyc311_nta") or {}).get("n", 0) > 0),
         ])

    case("neighborhood: borough-wide (Brooklyn → many NTAs, picks one)",
         "Brooklyn",
         expected_intent="neighborhood",
         asserts=[
             ("target borough = Brooklyn",
                has_target_field("borough", "Brooklyn")),
             ("n_matches > 50",
                lambda d: d.get("n_matches", 0) > 50),
         ])

    # ---- development_check -------------------------------------------------
    case("development_check: 'what are they building in Gowanus and is it risky?'",
         "what are they building in Gowanus and is it risky",
         expected_intent="development_check",
         asserts=[
             ("dob_summary present", lambda d: d.get("dob_summary") is not None),
             ("n_total > 0",
                lambda d: (d.get("dob_summary") or {}).get("n_total", 0) > 0),
             ("n_in_sandy >= 1 (Gowanus is coastal)",
                lambda d: (d.get("dob_summary") or {}).get("n_in_sandy", 0) >= 1),
             ("flagged_top has at least one project",
                lambda d: len((d.get("dob_summary") or {}).get("flagged_top") or []) >= 1),
             ("paragraph mentions specific BBL or address",
                lambda d: "BBL " in d.get("paragraph", "") or "St" in d.get("paragraph", "")),
         ])

    case("development_check: 'show me new construction in Red Hook'",
         "show me new construction in Red Hook",
         expected_intent="development_check",
         asserts=[
             ("dob_summary present", lambda d: d.get("dob_summary") is not None),
             ("paragraph nonempty",
                lambda d: len(d.get("paragraph", "")) > 50),
         ])

    # ---- live_now ----------------------------------------------------------
    case("live_now: explicit 'right now'",
         "is there flooding right now in NYC",
         expected_intent="live_now",
         asserts=[
             ("noaa_tides has observed_ft_mllw",
                lambda d: (d.get("noaa_tides") or {}).get("observed_ft_mllw") is not None),
             ("nws_alerts present",
                lambda d: d.get("nws_alerts") is not None),
             ("paragraph mentions Status",
                lambda d: "Status" in d.get("paragraph", "")),
         ])

    case("live_now: borough-scoped",
         "what's happening in Brooklyn right now",
         expected_intent="live_now",
         asserts=[
             ("place looks like a borough or NYC",
                lambda d: d.get("place") in ("Brooklyn", "NYC")),
         ])

    # ---- edge cases --------------------------------------------------------
    case("edge: typo'd address",
         "2940 Brighten 3rd St, Brkln",
         expected_intent="single_address",
         asserts=[
             ("paragraph nonempty (best-effort)",
                lambda d: len(d.get("paragraph", "")) > 0),
         ])

    case("edge: nonsense neighborhood — should fail gracefully",
         "Nonsense Heights",
         expected_intent="neighborhood",
         asserts=[
             ("error or paragraph fallback",
                lambda d: "error" in d or "Could not" in d.get("paragraph", "")),
         ])

    case("edge: very ambiguous query",
         "what about flood",
         expected_intent="live_now",  # planner usually maps this to live
         asserts=[
             ("paragraph nonempty",
                lambda d: len(d.get("paragraph", "")) > 0),
         ])

    # ---- summary -----------------------------------------------------------
    print("\n" + "=" * 60)
    print(f"HARD FAILS:  {len(HARD_FAIL)}")
    for name, why in HARD_FAIL:
        print(f"  - {name}: {why}")
    print(f"SOFT WARNS:  {len(SOFT_WARN)}")
    for name, why in SOFT_WARN:
        print(f"  - {name}: {why}")
    print("=" * 60)
    sys.exit(1 if HARD_FAIL else 0)


if __name__ == "__main__":
    main()
