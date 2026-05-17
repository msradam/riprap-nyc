"""Intake — the first step of every briefing run.

Two responsibilities, modelled as two Burr actions chained sequentially:

  plan      → call the Granite planner. Writes `plan`, `intent`, and a
              first-target candidate string into state.
  geocode   → resolve the first target string to lat/lon. Writes
              `geocode`, `lat`, `lon`.

Branching:
  - If `plan.intent == "not_implemented"`, downstream Stones are skipped
    (the top-level Application's transitions wire that branch).
  - If `geocode` fails (no NYC match), Stones still get to run with
    lat=lon=None; each pebble action degrades to its `no coords` trace
    record. The reconciler can still produce a "we couldn't locate this
    address" briefing.

Intake is a couple of small actions, not a sub-Application — the two
steps don't have internal state cycling, so the extra wrapping wouldn't
buy us anything.
"""
from __future__ import annotations

import time
from typing import Any

from burr.core import State, action

from riprap.core.burr.pebble import trace_rec_for


@action(reads=["query"], writes=["plan", "intent", "first_target", "trace"])
def plan_heuristic(state: State) -> State:
    """LLM-free planner — pattern-matches the query string against a
    small set of heuristics. Used when `RIPRAP_RECONCILER_TIER=templated`
    so the no-AI mode is genuinely AI-free end-to-end.

    Decision tree:
      - query mentions "Hollis"/"Coney Island"/"neighborhood" → neighborhood
      - query starts with a street number → single_address
      - default → single_address (most queries on Riprap)

    The full LLM planner produces richer targets[] + rationale; here
    we synthesize a minimal one that the rest of the pipeline can
    consume without any quality loss in templated mode.
    """
    import re

    trace = list(state.get("trace", []))
    rec = trace_rec_for("plan_heuristic")
    query = (state.get("query") or "").strip()
    intent = "single_address"
    if re.search(
        r"\b(neighborhood|nta|district|coney island|hollis|red hook|"
        r"brownsville|the bronx|harlem|"
        r"lower east side|east village|williamsburg|astoria)\b",
        query, re.IGNORECASE,
    ):
        intent = "neighborhood"
    plan_dict = {
        "intent": intent,
        "targets": [{"type": "address", "text": query}],
        "specialists": [],  # let the Burr graph fan out everything
        "rationale": f"Heuristic match: {intent}.",
    }
    rec["ok"] = True
    rec["result"] = {"intent": intent, "tier": "heuristic"}
    rec["elapsed_s"] = round(time.time() - rec["started_at"], 4)
    trace.append(rec)
    return state.update(plan=plan_dict, intent=intent,
                        first_target=query, trace=trace)


@action(reads=["query"], writes=["plan", "intent", "first_target", "trace"])
def plan_intent(state: State) -> State:
    """Run the planner. Writes `plan` (dataclass-as-dict), the resolved
    `intent` string, and the first target text (for geocoding)."""
    from app.planner import plan as run_planner  # noqa: PLC0415

    trace = list(state.get("trace", []))
    rec = trace_rec_for("plan_intent")
    try:
        p = run_planner(state["query"])
        plan_dict = {
            "intent": p.intent,
            "targets": p.targets,
            "specialists": p.specialists,
            "rationale": p.rationale,
        }
        first = ""
        if p.targets:
            t0 = p.targets[0]
            # Each target is a dict; the "text" field holds the geocodable
            # address string. Falls back to the rationale if no targets.
            first = t0.get("text") or t0.get("address") or ""
        rec["ok"] = True
        rec["result"] = {"intent": p.intent, "n_targets": len(p.targets),
                         "n_specialists": len(p.specialists)}
        trace.append(rec)
        return state.update(plan=plan_dict, intent=p.intent,
                            first_target=first, trace=trace)
    except Exception as e:  # noqa: BLE001
        rec["ok"] = False
        rec["err"] = str(e)
        trace.append(rec)
        return state.update(plan=None, intent="not_implemented",
                            first_target="", trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["first_target", "query"], writes=["geocode", "lat", "lon", "trace"])
def geocode_target(state: State) -> State:
    """Resolve the first target (or the raw query if empty) to lat/lon
    via `app.geocode.geocode_one` — NYC Geosearch first, OSM Nominatim
    fallback for any US address. This is what makes non-NYC deployments
    (Chicago, Boston, etc.) work without code changes."""
    from app.geocode import geocode_one  # noqa: PLC0415

    trace = list(state.get("trace", []))
    rec = trace_rec_for("geocode")
    target = (state.get("first_target") or state.get("query") or "").strip()
    if not target:
        rec["ok"] = False
        rec["err"] = "no target text"
        trace.append(rec)
        return state.update(geocode=None, lat=None, lon=None, trace=trace)
    try:
        h = geocode_one(target)
        if h is None:
            rec["ok"] = False
            rec["err"] = "no geocode match (NYC Geosearch + Nominatim both empty)"
            trace.append(rec)
            return state.update(geocode=None, lat=None, lon=None, trace=trace)
        gdict: dict[str, Any] = {
            "address": h.address,
            "borough": h.borough,
            "lat": h.lat,
            "lon": h.lon,
            "bbl": h.bbl,
            "bin": h.bin,
        }
        rec["ok"] = True
        rec["result"] = {"address": h.address, "borough": h.borough}
        trace.append(rec)
        return state.update(geocode=gdict, lat=h.lat, lon=h.lon, trace=trace)
    except Exception as e:  # noqa: BLE001
        rec["ok"] = False
        rec["err"] = str(e)
        trace.append(rec)
        return state.update(geocode=None, lat=None, lon=None, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)
