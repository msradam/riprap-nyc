"""Touchstone — the Live Observer.

Watches what's happening right now: FloodNet ultrasonic depth sensors,
NYC 311 flood-complaint history, NWS hourly METAR observations, NOAA
tide-gauge water levels, and per-query EO segmentation
(Prithvi-EO 2.0 NYC Pluvial fine-tune for water/flood; TerraMind-NYC
LULC adapter for current land cover).

The Touchstone is the "current state of the world" Stone. Its outputs
change minute to minute and are explicitly framed in the briefing as
right-now context, not historical record.
"""
from __future__ import annotations

from typing import Any

NAME = "Touchstone"
TAGLINE = "The Live Observer"
DESCRIPTION = "Watches the current state of the city's flood signals and EO."

# Live sensors + per-query EO. `prithvi_live` becomes the NYC Pluvial
# v2 fine-tune in commit 5; `terramind_lulc` is added in commit 4.
SOURCES = [
    "floodnet",         # step_floodnet         — FloodNet sensor network
    "nyc311",           # step_311              — NYC 311 flood complaints
    "nws_obs",          # step_nws_obs          — NWS hourly METAR obs
    "noaa_tides",       # step_noaa_tides       — NOAA tide gauge water level
    "prithvi_live",     # step_prithvi_live     — Prithvi-EO 2.0 (v2 in commit 5)
    "terramind_lulc",   # step_terramind_lulc (commit 4) — NYC LULC adapter
]


def collect(state: dict[str, Any]) -> dict[str, Any]:
    """Return {state_key: value} for every Touchstone source that fired."""
    return {k: state[k] for k in SOURCES if state.get(k) is not None}
