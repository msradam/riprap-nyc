"""Smoke test for the pebble bridge — the FSM-facing helper that the legacy
step_* functions now delegate to.

Asserts:
  - registry loads from RIPRAP_DEPLOYMENT (default deployments/nyc)
  - fetch_pebble returns (value, trace_summary, None) for a working pebble
  - trace_summary keys match the manifest's trace_summary block
"""
from __future__ import annotations

from riprap.core.pebbles.bridge import fetch_pebble

TEST_LAT = 40.7282
TEST_LON = -73.7949


def test_fetch_pebble_ida_hwm_returns_value_and_trace():
    value, trace_summary, err = fetch_pebble("ida_hwm", TEST_LAT, TEST_LON)
    assert err is None
    assert value is not None
    assert "n_within_radius" in value
    # Trace summary uses renamed keys per manifest.
    assert set(trace_summary.keys()) == {
        "n_within_800m", "max_height_above_gnd_ft", "nearest_m",
    }
    assert trace_summary["n_within_800m"] == value["n_within_radius"]
    assert trace_summary["nearest_m"] == value["nearest_dist_m"]
