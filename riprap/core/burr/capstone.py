"""Capstone — final synthesis step.

Three actions in sequence:

  assemble_legacy_state → reshape the manifest-driven pebble state keys
                          (`dep_extreme_2080`, `dep_moderate_2050`,
                          `dep_moderate_current`) into the legacy compound
                          `dep` dict the reconciler reads. Most pebble
                          keys are already in the legacy shape after the
                          shaper layer, so this is mostly the DEP fan-in.
  rag                   → identity reuse of app.fsm.step_rag. Retrieves
                          policy-corpus passages based on the geocoded
                          address + flood signals.
  reconcile             → identity reuse of app.fsm.step_reconcile.
                          Granite 4.1 + Mellea grounded rejection-sampling
                          loop (the loop is INTERNAL to mellea_validator;
                          the Burr layer just sees one streaming action).

The Mellea reroll budget is configured by mellea_validator's
`DEFAULT_LOOP_BUDGET`. Surfacing each reroll as a distinct Burr step
would require lifting the loop out of mellea_validator — left as a
future improvement; for now, the rejection-sampling attempts appear
together as `n_attempts` in the trace.
"""
from __future__ import annotations

import time
from typing import Any

from burr.core import State, action

from riprap.core.burr.pebble import trace_rec_for


@action(
    reads=["dep_extreme_2080", "dep_moderate_2050", "dep_moderate_current"],
    writes=["dep", "trace"],
)
def assemble_legacy_state(state: State) -> State:
    """Compose the three DEP scenario pebble values into the legacy `dep`
    compound dict that step_rag + step_reconcile read.

    All other pebbles (sandy, ida_hwm, floodnet, etc.) already write the
    legacy state keys directly via their shapers — no other compounding
    needed in v1.
    """
    trace = list(state.get("trace", []))
    rec = trace_rec_for("assemble_legacy_state")
    dep: dict[str, Any] = {}
    for scen in ("dep_extreme_2080", "dep_moderate_2050", "dep_moderate_current"):
        v = state.get(scen)
        if v is not None:
            dep[scen] = v
    rec["ok"] = True
    rec["result"] = {"scenarios": sorted(dep.keys())}
    rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)
    trace.append(rec)
    return state.update(dep=dep, trace=trace)


# The reconcile pipeline's Mellea-grounded Granite call lives in
# app/fsm.step_reconcile; we reuse it as-is. The retrieval + NER stage
# is now consolidated into one text-mining pebble (`policy_corpus`)
# wired here as `step_policy_corpus`, replacing the old step_rag +
# step_gliner pair. See `local_corpus_with_ner` adapter for the
# pebble's internals.
from burr.core import action  # noqa: E402

from app.fsm import step_reconcile  # noqa: E402,F401


@action(
    reads=["lat", "lon", "geocode", "sandy", "dep", "intent"],
    writes=["policy_corpus", "rag", "gliner", "trace"],
)
def step_policy_corpus(state: State) -> State:
    """Run the policy_corpus pebble: retrieve + NER in one pebble call.

    Builds the search query from state (geocode + flood signals), then
    delegates to the pebble registry. For backward compatibility with
    `app.reconcile.build_documents`, the rag-hit list and entity dict
    are mirrored into `state["rag"]` and `state["gliner"]` — the same
    keys step_rag and step_gliner used to write. Future cleanup:
    migrate build_documents to read state["policy_corpus"] directly
    and drop the mirrors.
    """
    import time

    from riprap.core.pebbles.bridge import fetch_pebble

    trace = list(state.get("trace", []))
    rec = trace_rec_for("policy_corpus")
    try:
        geo = state.get("geocode") or {}
        sandy = state.get("sandy")
        dep = state.get("dep") or {}

        # Build a context-rich query so retrieval pulls policy paragraphs
        # relevant to *this* address, not generic flood text.
        bits: list[str] = []
        if geo.get("address"):
            bits.append(f"address {geo['address']}")
        if geo.get("borough"):
            bits.append(f"in {geo['borough']}")
        if sandy:
            bits.append("inside Hurricane Sandy 2012 inundation zone")
        for v in (dep or {}).values():
            if isinstance(v, dict) and (v.get("depth_class") or 0) > 0:
                bits.append(f"in {v.get('depth_label', '?')} pluvial scenario")
        bits.append("flood resilience plan, vulnerability, hardening, mitigation")
        query_str = "; ".join(bits)

        value, trace_summary, err = fetch_pebble(
            "policy_corpus",
            state.get("lat") or 0.0,
            state.get("lon") or 0.0,
            extras={"query": query_str},
        )
        if value is None:
            rec["ok"] = False
            rec["err"] = err or "policy_corpus unavailable"
            trace.append(rec)
            return state.update(policy_corpus=None, rag=[], gliner={}, trace=trace)

        rec["ok"] = True
        rec["result"] = trace_summary
        trace.append(rec)

        # Backward-compat mirrors so app.reconcile.build_documents
        # (which still reads state["rag"] and state["gliner"]) sees
        # the same shapes the deleted step_rag + step_gliner wrote.
        return state.update(
            policy_corpus=value,
            rag=value.get("rag_hits", []),
            gliner=value.get("entities", {}),
            trace=trace,
        )
    except Exception as e:  # noqa: BLE001
        rec["ok"] = False
        rec["err"] = str(e)
        trace.append(rec)
        return state.update(policy_corpus=None, rag=[], gliner={}, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 4)


__all__ = ["assemble_legacy_state", "step_policy_corpus", "step_reconcile"]
