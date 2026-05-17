"""Verify the SSE stone_start / stone_done envelope around step events.

The web layer wraps the FSM step stream and emits stone_start / stone_done
events at Stone-group boundaries. We don't need a running server to test
the boundary logic — we extract the iterating segment of api_agent_stream
into a pure generator and feed it a synthetic event sequence.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_step_to_stone_mapping_covers_known_steps():
    # The mapping is built at import from the NYC deployment's pebble
    # manifests + legacy step aliases. Force the NYC deployment so the
    # set is deterministic regardless of how the harness invokes us.
    os.environ["RIPRAP_DEPLOYMENT"] = "deployments/nyc"
    from web.main import _STEP_TO_STONE
    missing = [
        step for step in (
            "sandy_inundation", "dep_stormwater", "ida_hwm_2021",
            "prithvi_eo_v2", "microtopo_lidar",
            "mta_entrance_exposure", "nycha_development_exposure",
            "doe_school_exposure", "doh_hospital_exposure",
            "terramind_synthesis", "eo_chip_fetch", "terramind_buildings",
            "floodnet", "nyc311", "nws_obs", "noaa_tides",
            "prithvi_eo_live", "terramind_lulc",
            "nws_alerts", "ttm_forecast", "ttm_311_forecast",
            "floodnet_forecast", "ttm_battery_surge",
            "reconcile_granite41", "mellea_reconcile_address",
        )
        if step not in _STEP_TO_STONE
    ]
    assert not missing, f"_STEP_TO_STONE missing step mappings: {missing}"


def _replay(events: list[dict]) -> list[tuple[str, dict]]:
    """Local re-implementation of the SSE envelope state machine in
    web/main.py:event_stream. We only emulate the parts that touch
    stone_start / stone_done / step / token / final."""
    # Match web/main.py exactly.
    STEP_TO_STONE = {
        "sandy_inundation": "Cornerstone", "dep_stormwater": "Cornerstone",
        "ida_hwm_2021": "Cornerstone", "prithvi_eo_v2": "Cornerstone",
        "microtopo_lidar": "Cornerstone",
        "mta_entrance_exposure": "Keystone",
        "nycha_development_exposure": "Keystone",
        "doe_school_exposure": "Keystone",
        "doh_hospital_exposure": "Keystone",
        "terramind_synthesis": "Keystone",
        "eo_chip_fetch": "Keystone",
        "terramind_buildings": "Keystone",
        "floodnet": "Touchstone", "nyc311": "Touchstone",
        "nws_obs": "Touchstone", "noaa_tides": "Touchstone",
        "prithvi_eo_live": "Touchstone", "terramind_lulc": "Touchstone",
        "nws_alerts": "Lodestone", "ttm_forecast": "Lodestone",
        "ttm_311_forecast": "Lodestone", "floodnet_forecast": "Lodestone",
        "ttm_battery_surge": "Lodestone",
        "reconcile_granite41": "Capstone",
        "mellea_reconcile_address": "Capstone",
    }
    out: list[tuple[str, dict]] = []
    current = None

    def open_(s):
        out.append(("stone_start", {"name": s}))

    def close_(s):
        out.append(("stone_done", {"name": s}))

    for ev in events:
        kind = ev["kind"]
        if kind == "token" and current != "Capstone":
            if current is not None:
                close_(current)
            current = "Capstone"
            open_(current)
        if kind == "step":
            stone = STEP_TO_STONE.get(ev["step"])
            if stone is not None and stone != current:
                if current is not None:
                    close_(current)
                current = stone
                open_(current)
        if kind == "final" and current is not None:
            close_(current)
            current = None
        out.append((kind, ev))
    if current is not None:
        close_(current)
    return out


def _names(seq, kind):
    return [d["name"] for k, d in seq if k == kind]


def test_envelope_around_full_pipeline():
    events = [
        {"kind": "step", "step": "geocode"},        # not in any Stone
        {"kind": "step", "step": "sandy_inundation"},
        {"kind": "step", "step": "dep_stormwater"},
        {"kind": "step", "step": "mta_entrance_exposure"},
        {"kind": "step", "step": "floodnet"},
        {"kind": "step", "step": "nyc311"},
        {"kind": "step", "step": "ttm_forecast"},
        {"kind": "step", "step": "ttm_battery_surge"},
        {"kind": "step", "step": "rag_granite_embedding"},  # ancillary
        {"kind": "token", "delta": "**Status**"},
        {"kind": "final", "paragraph": "..."},
    ]
    out = _replay(events)
    starts = _names(out, "stone_start")
    dones = _names(out, "stone_done")
    assert starts == ["Cornerstone", "Keystone", "Touchstone",
                       "Lodestone", "Capstone"]
    assert dones == ["Cornerstone", "Keystone", "Touchstone",
                      "Lodestone", "Capstone"]


def test_envelope_skips_ancillary_steps_cleanly():
    """geocode / rag / gliner aren't part of any Stone — they shouldn't
    open or close a Stone boundary."""
    events = [
        {"kind": "step", "step": "geocode"},
        {"kind": "step", "step": "rag_granite_embedding"},
        {"kind": "step", "step": "gliner_extract"},
    ]
    out = _replay(events)
    assert _names(out, "stone_start") == []
    assert _names(out, "stone_done") == []


def test_envelope_handles_token_before_capstone_step():
    """Reconcile streams tokens BEFORE the FSM emits a step event for
    reconcile (the step fires on completion). The envelope must
    open Capstone on the first token, not wait for the step."""
    events = [
        {"kind": "step", "step": "sandy_inundation"},
        {"kind": "token", "delta": "x"},
        {"kind": "token", "delta": "y"},
        {"kind": "step", "step": "reconcile_granite41"},
        {"kind": "final", "paragraph": "..."},
    ]
    out = _replay(events)
    starts = _names(out, "stone_start")
    dones = _names(out, "stone_done")
    assert starts == ["Cornerstone", "Capstone"]
    assert dones == ["Cornerstone", "Capstone"]
    # The reconcile_granite41 step shouldn't open a SECOND Capstone —
    # it's already current.
    assert starts.count("Capstone") == 1


def test_envelope_closes_on_premature_end():
    """Pipeline terminates without final (e.g. error) — any open Stone
    must be closed so the client doesn't render an unbounded row."""
    events = [
        {"kind": "step", "step": "sandy_inundation"},
        # No further events; replay() closes the open Stone.
    ]
    out = _replay(events)
    assert _names(out, "stone_start") == ["Cornerstone"]
    assert _names(out, "stone_done") == ["Cornerstone"]
