"""Cornerstone — the Hazard Reader.

Reads what NYC's ground remembers about flooding: empirical 2012 Sandy
extent, modelled DEP scenarios, 2021 Ida USGS high-water marks, baked
Prithvi-EO Ida-attributable polygons, and LiDAR-derived microtopography
(elevation / HAND / TWI).

These are static records — they don't change between queries. They
ground the briefing in what already happened or has already been
modelled, and serve as the empirical anchor for everything the live
sensors and forecasts report.
"""
from __future__ import annotations

from typing import Any

NAME = "Cornerstone"
TAGLINE = "The Hazard Reader"
DESCRIPTION = "Reads what NYC's ground remembers about flooding."

# FSM state keys this Stone aggregates. The order here mirrors the order
# documents are emitted into the reconciler prompt today.
SOURCES = [
    "sandy",          # step_sandy           — 2012 Sandy inundation extent
    "dep",            # step_dep             — NYC DEP stormwater scenarios
    "ida_hwm",        # step_ida_hwm         — USGS Ida 2021 high-water marks
    "prithvi_water",  # step_prithvi         — baked Prithvi-EO Ida polygons
    "microtopo",      # step_microtopo       — USGS 3DEP DEM + HAND/TWI
]


def collect(state: dict[str, Any]) -> dict[str, Any]:
    """Return {state_key: value} for every Cornerstone source that fired.

    Drops keys whose value is None (the silence-over-confabulation
    contract — specialists that didn't fire emit nothing).
    """
    return {k: state[k] for k in SOURCES if state.get(k) is not None}
