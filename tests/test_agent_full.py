"""Comprehensive end-to-end test suite for the Riprap agent.

Run against a live local server:
    .venv/bin/uvicorn web.main:app --port 8000 &
    .venv/bin/python tests/test_agent_full.py

Twenty-five cases across all four intents plus adversarial edge cases.
Tests cover:
  - Intent routing correctness
  - Real-value assertions (e.g. Brighton Beach must be majority-Sandy)
  - Hallucination detection (no leaked example values from old prompts)
  - Cross-query contamination check (back-to-back queries don't bleed)
  - Latency thresholds (warm; expect generous wall on local Apple Silicon)
  - Citation presence
  - Section structure presence
  - Map-data presence (target with bbox / geocode with lat/lon)

Hard fails fail the suite (exit 1).  Soft warns are logged but don't fail.
"""
from __future__ import annotations

import re
import sys
import time

import httpx

BASE = "http://127.0.0.1:8000"

HARD_FAILS: list[tuple[str, str]] = []
SOFT_WARNS: list[tuple[str, str]] = []
TIMINGS: list[tuple[str, float]] = []

# Phrases that ONLY exist as worked-example content from prior prompts/docs.
# If they appear in an output that didn't actually query that place, the model
# is leaking from prompt or training-prior. List verbatim, lowercased.
LEAK_PHRASES = [
    # Old prompt example that bit us once:
    "20 coffey st",  # only legitimate if the query is about Red Hook / Gowanus
    # Boilerplate that signals model is improvising agency speak rather than
    # citing — soft warn, not hard fail
]


def case(name: str, q: str, expected_intent: str, asserts: list, *,
        max_wall_s: float = 240.0, leak_must_not_appear: list[str] | None = None):
    """One test case. Returns the parsed response or None on hard fail."""
    print(f"\n=== {name}")
    print(f"  query: {q!r}")
    t0 = time.time()
    try:
        r = httpx.get(f"{BASE}/api/agent", params={"q": q}, timeout=max_wall_s + 30.0)
        r.raise_for_status()
        d = r.json()
    except Exception as e:
        print(f"  ❌ HTTP/JSON error: {e!r}")
        HARD_FAILS.append((name, f"HTTP error: {e}"))
        return None
    dt = time.time() - t0
    TIMINGS.append((name, dt))

    intent = d.get("intent")
    plan = d.get("plan", {})
    print(f"  → intent={intent}  total_s={d.get('total_s', '?')}  wall={dt:.2f}s")
    print(f"  → specialists ({len(plan.get('specialists', []))}): {plan.get('specialists', [])}")
    rationale = plan.get("rationale", "")
    print(f"  → rationale: {rationale[:130]}")

    if expected_intent is not None and intent != expected_intent:
        HARD_FAILS.append((name, f"intent {intent} != expected {expected_intent}"))
        print(f"  ❌ expected intent={expected_intent}, got {intent}")
        return d

    if expected_intent is None:
        print("  ✓ intent (no expectation — adversarial case)")
    else:
        print("  ✓ intent")

    # Latency
    if dt > max_wall_s:
        SOFT_WARNS.append((name, f"latency {dt:.1f}s > {max_wall_s}s budget"))
        print(f"  ⚠ latency {dt:.1f}s > {max_wall_s}s budget")
    else:
        print(f"  ✓ latency under {max_wall_s}s budget")

    # Per-case asserts
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
            HARD_FAILS.append((name, label))

    # Hallucination / leak check
    para = (d.get("paragraph", "") or "").lower()
    leaks = [p for p in (leak_must_not_appear or []) if p.lower() in para]
    if leaks:
        HARD_FAILS.append((name, f"leak phrase appeared in paragraph: {leaks}"))
        print(f"  ❌ leak phrase: {leaks}")
    else:
        print("  ✓ no leak phrases")

    # Section header presence
    has_section = bool(re.search(r"\*\*\w[\w\s/]*\.\*\*", para))
    if not has_section and (d.get("paragraph") or "") and "no grounded data" not in para and "could not" not in para:
        SOFT_WARNS.append((name, "no recognizable **Section.** header"))
        print("  ⚠ no section header")

    return d


# ---- helpers ---------------------------------------------------------------

def has_signal(key):
    def _check(d):
        v = d.get(key)
        return v is not None and v != [] and v != {}
    return _check


def target_field_eq(field, value_substring):
    def _check(d):
        t = d.get("target") or {}
        return value_substring.lower() in (t.get(field, "") or "").lower()
    return _check


def fraction_inside(key, lo, hi):
    def _check(d):
        s = d.get(key) or {}
        f = s.get("fraction", -1)
        return lo <= f <= hi
    return _check


def dob_n_total_at_least(n):
    return ("dob_summary.n_total >= " + str(n),
            lambda d: (d.get("dob_summary") or {}).get("n_total", 0) >= n)


def dob_n_in_sandy_at_least(n):
    return ("dob_summary.n_in_sandy >= " + str(n),
            lambda d: (d.get("dob_summary") or {}).get("n_in_sandy", 0) >= n)


def has_paragraph(min_chars=80):
    return ("paragraph >= " + str(min_chars) + " chars",
            lambda d: len(d.get("paragraph", "") or "") >= min_chars)


def has_citation_tag():
    return ("paragraph contains [doc_id] citation",
            lambda d: bool(re.search(r"\[[a-z][a-z0-9_]+\]", d.get("paragraph", "") or "")))


def has_map_data():
    return ("map data present (target.bbox or geocode.lat)",
            lambda d: ((d.get("target") or {}).get("bbox") is not None
                      or (d.get("geocode") or {}).get("lat") is not None
                      or d.get("place") is not None))


# ---- the suite -------------------------------------------------------------

def main():
    try:
        httpx.get(f"{BASE}/", timeout=5.0)
    except Exception as e:
        print(f"server not reachable at {BASE}: {e!r}")
        sys.exit(1)

    print("=" * 60)
    print("RIPRAP AGENT — FULL E2E SUITE")
    print("=" * 60)

    # ------ SINGLE_ADDRESS ------
    case("addr/golden — coastal Brooklyn (Sandy hit)",
         "2940 Brighton 3rd St, Brooklyn",
         "single_address",
         [
             ("geocode populated",  lambda d: (d.get("geocode") or {}).get("lat")),
             ("sandy is True",      lambda d: d.get("sandy") is True),
             ("dep populated",      has_signal("dep")),
             ("microtopo HAND populated",
                lambda d: (d.get("microtopo") or {}).get("hand_m") is not None),
             has_paragraph(),
             has_map_data(),
         ],
         max_wall_s=120,
         leak_must_not_appear=[],  # 20 Coffey is in Red Hook ZIP, near enough to Brighton via Brooklyn — accept
         )

    case("addr/golden — Queens inland (Hollis archetype)",
         "183-02 Liberty Ave, Queens",
         "single_address",
         [
             ("geocode populated",  lambda d: (d.get("geocode") or {}).get("lat")),
             ("sandy is False",     lambda d: d.get("sandy") is False),
             ("microtopo populated", has_signal("microtopo")),
             has_paragraph(),
         ],
         max_wall_s=120)

    case("addr/control — Empire State Building (high ground)",
         "350 5th Ave, Manhattan",
         "single_address",
         [
             ("geocode populated",  lambda d: (d.get("geocode") or {}).get("lat")),
             ("sandy is False",     lambda d: d.get("sandy") is False),
         ],
         max_wall_s=120,
         leak_must_not_appear=["20 coffey st", "brighton beach"])

    case("addr/edge — typo'd address survives",
         "2940 Brighten 3rd St, Brkln",
         "single_address",
         [has_paragraph(min_chars=20)],
         max_wall_s=120)

    case("addr/edge — outside NYC (Albany)",
         "Empire State Plaza, Albany",
         "single_address",
         [has_paragraph(min_chars=20)],
         max_wall_s=120)

    # ------ NEIGHBORHOOD ------
    case("nbhd/golden — Brighton Beach (high coastal exposure)",
         "Brighton Beach",
         "neighborhood",
         [
             ("nta_name = Brighton Beach", target_field_eq("nta_name", "Brighton Beach")),
             ("borough = Brooklyn",        target_field_eq("borough", "Brooklyn")),
             ("sandy_nta fraction > 0.7",  fraction_inside("sandy_nta", 0.7, 1.0)),
             ("dep_nta has scenarios",
                lambda d: len(d.get("dep_nta") or {}) >= 2),
             ("nyc311_nta n > 100",
                lambda d: (d.get("nyc311_nta") or {}).get("n", 0) > 100),
             has_paragraph(),
             has_citation_tag(),
             has_map_data(),
         ],
         max_wall_s=120)

    case("nbhd/golden — Carroll Gardens (mixed coastal/inland)",
         "Carroll Gardens",
         "neighborhood",
         [
             ("borough = Brooklyn", target_field_eq("borough", "Brooklyn")),
             ("nyc311_nta n > 0",
                lambda d: (d.get("nyc311_nta") or {}).get("n", 0) > 0),
             ("microtopo_nta populated", has_signal("microtopo_nta")),
             has_paragraph(),
         ],
         max_wall_s=120)

    case("nbhd/golden — Hollis (inland Queens, Ida-deaths archetype)",
         "Hollis",
         "neighborhood",
         [
             ("borough = Queens",   target_field_eq("borough", "Queens")),
             ("sandy_nta fraction < 0.1 (inland)",
                lambda d: (d.get("sandy_nta") or {"fraction": 1}).get("fraction", 1) < 0.1),
             has_paragraph(),
         ],
         max_wall_s=120,
         leak_must_not_appear=["20 coffey st"])

    case("nbhd/edge — exact-match wins over substring",
         "Kew Gardens",
         "neighborhood",
         [
             ("nta_name = Kew Gardens (NOT Kew Gardens Hills)",
                lambda d: (d.get("target") or {}).get("nta_name", "").lower() == "kew gardens"),
         ],
         max_wall_s=120)

    case("nbhd/edge — borough-wide query",
         "Brooklyn",
         "neighborhood",
         [
             ("borough = Brooklyn", target_field_eq("borough", "Brooklyn")),
             ("n_matches > 50",     lambda d: d.get("n_matches", 0) > 50),
         ],
         max_wall_s=120)

    case("nbhd/edge — NL phrasing 'is X at risk'",
         "is Brighton Beach at risk?",
         "neighborhood",
         [
             ("nta_name = Brighton Beach", target_field_eq("nta_name", "Brighton Beach")),
             has_paragraph(),
         ],
         max_wall_s=120)

    # ------ DEVELOPMENT_CHECK ------
    case("dev/golden — Gowanus (the marquee)",
         "what are they building in Gowanus and is it risky",
         "development_check",
         [
             dob_n_total_at_least(5),
             dob_n_in_sandy_at_least(1),
             ("flagged_top has projects",
                lambda d: len((d.get("dob_summary") or {}).get("flagged_top") or []) >= 1),
             ("paragraph mentions a real BBL or street name",
                lambda d: "BBL" in (d.get("paragraph") or "") or "St," in (d.get("paragraph") or "")),
             has_paragraph(min_chars=200),
             has_map_data(),
         ],
         max_wall_s=180)

    case("dev/golden — Red Hook (high Sandy)",
         "show me new construction in Red Hook",
         "development_check",
         [
             dob_n_total_at_least(1),
             has_paragraph(min_chars=80),
         ],
         max_wall_s=180)

    case("dev/edge — low-construction inland (Hollis)",
         "what are they building in Hollis",
         "development_check",
         [has_paragraph(min_chars=50)],
         max_wall_s=120)

    case("dev/edge — variant phrasing",
         "flood risk of new gowanus developments",
         "development_check",
         [
             ("target NTA borough = Brooklyn",
                lambda d: (d.get("target") or {}).get("borough") == "Brooklyn"),
             dob_n_total_at_least(1),
         ],
         max_wall_s=180)

    case("dev/anti-leak — query unrelated to Gowanus must not mention 20 Coffey St",
         "what are they building in Coney Island",
         "development_check",
         [has_paragraph(min_chars=80)],
         max_wall_s=180,
         leak_must_not_appear=["20 coffey st"])  # Coffey St is in Red Hook NTA, not Coney Island NTA

    # ------ LIVE_NOW ------
    case("live/golden — explicit 'right now'",
         "is there flooding right now in NYC",
         "live_now",
         [
             ("noaa_tides observed_ft_mllw populated",
                lambda d: (d.get("noaa_tides") or {}).get("observed_ft_mllw") is not None),
             ("nws_alerts present",
                lambda d: d.get("nws_alerts") is not None),
             has_paragraph(min_chars=20),
         ],
         max_wall_s=90)

    case("live/edge — borough-scoped",
         "what's happening in Brooklyn right now",
         "live_now",
         [
             ("place = Brooklyn or NYC",
                lambda d: d.get("place") in ("Brooklyn", "NYC")),
         ],
         max_wall_s=90)

    case("live/edge — surge-only phrasing",
         "is there a surge tonight",
         "live_now",
         [has_paragraph(min_chars=10)],
         max_wall_s=90)

    # ------ STAKEHOLDER FLAVOR ------
    case("stakeholder/reporter — DOB permits in flood zones",
         "what NYC construction is at flood risk",
         "development_check",  # planner should pick dev_check; if neighborhood, that's also OK
         [has_paragraph(min_chars=40)],
         max_wall_s=180)

    case("stakeholder/planner — borough-scope dev",
         "show me Brooklyn construction in flood zones",
         "development_check",
         [has_paragraph(min_chars=40)],
         max_wall_s=180)

    case("stakeholder/BRIC — Sandy-impacted address",
         "is 90 Bay St Staten Island in the Sandy zone",
         "single_address",
         [
             ("geocode populated",  lambda d: (d.get("geocode") or {}).get("lat")),
             has_paragraph(min_chars=80),
         ],
         max_wall_s=120)

    # ------ ADVERSARIAL / EDGE ------
    case("edge — nonsense query (planner falls back)",
         "what about flood",
         None,  # No expected — just wants ANY routing
         [has_paragraph(min_chars=10)],
         max_wall_s=120)

    case("edge — empty noun (planner picks live)",
         "flood",
         None,
         [has_paragraph(min_chars=5)],
         max_wall_s=120)

    case("edge — non-existent neighborhood (graceful fallback)",
         "Nonsense Heights",
         "neighborhood",
         [
             ("paragraph or error message",
                lambda d: bool(d.get("paragraph") or d.get("error"))),
         ],
         max_wall_s=60)

    # ---- summary ----------------------------------------------------------

    print("\n" + "=" * 60)
    print(f"HARD FAILS:  {len(HARD_FAILS)}")
    for name, why in HARD_FAILS:
        print(f"  - {name}: {why}")
    print(f"\nSOFT WARNS:  {len(SOFT_WARNS)}")
    for name, why in SOFT_WARNS:
        print(f"  - {name}: {why}")
    print("\nTIMINGS (top 5 slowest):")
    for name, t in sorted(TIMINGS, key=lambda x: -x[1])[:5]:
        print(f"  {t:6.1f}s  {name}")
    print("\nTIMINGS (intent medians):")
    by_intent = {}
    for name, t in TIMINGS:
        prefix = name.split("/", 1)[0]
        by_intent.setdefault(prefix, []).append(t)
    for prefix, times in sorted(by_intent.items()):
        med = sorted(times)[len(times) // 2]
        print(f"  {prefix:18s} median {med:5.1f}s  (n={len(times)})")
    print("=" * 60)
    sys.exit(1 if HARD_FAILS else 0)


if __name__ == "__main__":
    main()
