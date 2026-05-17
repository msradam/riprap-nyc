"""Pebble → Burr @action factory.

`pebble_action(pebble_id)` returns a Burr action that reads lat/lon from
state, runs the pebble through the registry bridge, and writes the
pebble's value + a trace record. One factory function replaces ~30
hand-written `step_*` shims.

Trace records are kept compact (`{step, ok, err?, result?, elapsed_s,
started_at}`) so the SSE event stream stays the same shape the
SvelteKit UI already consumes.
"""
from __future__ import annotations

import time
from typing import Any

from burr.core import State, action

from riprap.core.pebbles.bridge import fetch_pebble


def trace_rec_for(step_name: str) -> dict[str, Any]:
    """Create an in-flight trace record. Mirrors app/fsm.py:_make_rec so the
    SSE consumers (web/main.py and the SvelteKit cardAdapter) don't need to
    change."""
    return {
        "step": step_name,
        "ok": None,
        "started_at": time.time(),
        "elapsed_s": 0.0,
        "err": None,
        "result": None,
    }


def pebble_action(pebble_id: str):
    """Return a Burr @action that fetches one pebble.

    Reads:  ["lat", "lon"]                            (parent state)
    Writes: [pebble_id, "trace"]                      (own state slice)

    State key the action writes equals the pebble id — by design the
    pebble id IS the state key consumers downstream use. This is also
    what the cardAdapter expects (`state["sandy"]`, `state["floodnet"]`,
    etc.).
    """
    @action(reads=["lat", "lon", "deployment"], writes=[pebble_id, "trace"])
    def _step(state: State) -> State:
        trace = list(state.get("trace", []))
        rec = trace_rec_for(pebble_id)
        try:
            lat, lon = state.get("lat"), state.get("lon")
            if lat is None or lon is None:
                rec["ok"] = False
                rec["err"] = "no coords"
                trace.append(rec)
                return state.update(**{pebble_id: None}, trace=trace)
            # Per-query deployment routing: fetch_pebble must look up
            # this pebble in the SELECTED deployment's registry, not in
            # whatever the env var defaulted to. Without this, a Boston
            # query would route to the Boston deployment for fan-out
            # (correct) but then call fetch_pebble against the NYC
            # registry — which doesn't contain boston_311 — and crash
            # with KeyError('boston_311').
            deployment = state.get("deployment")
            value, trace_summary, err = fetch_pebble(
                pebble_id, lat, lon, deployment=deployment,
            )
            if value is None:
                rec["ok"] = False
                rec["err"] = err or "no value"
            else:
                rec["ok"] = True
                rec["result"] = trace_summary
            trace.append(rec)
            return state.update(**{pebble_id: value}, trace=trace)
        except Exception as e:  # noqa: BLE001 — surfaced via trace, not raised
            rec["ok"] = False
            rec["err"] = str(e)
            trace.append(rec)
            return state.update(**{pebble_id: None}, trace=trace)
        finally:
            rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)

    # Give the action a stable, debuggable name. Burr uses this in the
    # tracker UI and in transition declarations.
    _step.__name__ = f"pebble_{pebble_id}"
    return _step
