"""Lodestone — the Projector.

Projects what's coming next: NWS active flood-relevant alerts (the
National Weather Service's authoritative short-horizon watches /
warnings), Granite TimeSeries TTM r2 zero-shot forecasts of the Battery
surge residual and per-address NYC 311 complaint rates and per-sensor
FloodNet event recurrence, and (via the Granite-TTM-r2-Battery-Surge
fine-tune on AMD MI300X) a 96-hour surge nowcast.

The Lodestone is the forward-looking Stone — every cited number here
is a forecast, framed as such in the briefing.
"""
from __future__ import annotations

from typing import Any

NAME = "Lodestone"
TAGLINE = "The Projector"
DESCRIPTION = "Projects what's coming: alerts, surge, and recurrence forecasts."

# Existing forecast specialists + the new fine-tuned Battery surge
# nowcast (added in commit 6).
SOURCES = [
    "nws_alerts",          # step_nws_alerts         — NWS public alerts
    "ttm_forecast",        # step_ttm_forecast       — TTM r2 Battery zero-shot
    "ttm_311_forecast",    # step_ttm_311_forecast   — TTM r2 311 weekly
    "floodnet_forecast",   # step_floodnet_forecast  — TTM r2 FloodNet recurrence
    "ttm_battery_surge",   # step_ttm_battery_surge (commit 6) — fine-tuned
]


def collect(state: dict[str, Any]) -> dict[str, Any]:
    """Return {state_key: value} for every Lodestone source that fired."""
    return {k: state[k] for k in SOURCES if state.get(k) is not None}
