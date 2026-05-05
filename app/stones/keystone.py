"""Keystone — the Asset Register.

Counts what the city has built on top of those hazards: subway
entrances, NYCHA developments, DOE schools, NYS DOH hospitals, and
(via the TerraMind-NYC-Buildings adapter, fine-tuned on NYC building
footprints on AMD MI300X) the building stock visible in current EO.

These are the public-asset registers — the per-address briefing
quantifies how many of each asset class fall inside the hazard
footprints the Cornerstone established.
"""
from __future__ import annotations

from typing import Any

NAME = "Keystone"
TAGLINE = "The Asset Register"
DESCRIPTION = "Counts the public assets and built fabric exposed to the hazards."

# Existing register specialists + the new TerraMind-Buildings tool
# (added in commit 4 of the Stones migration). Stones layer is
# tolerant of state keys that don't exist yet — `collect` skips
# anything absent.
SOURCES = [
    "mta_entrances",        # step_mta_entrances   — MTA entrance exposure
    "nycha_developments",   # step_nycha           — NYCHA exposure
    "doe_schools",          # step_doe_schools     — DOE schools exposure
    "doh_hospitals",        # step_doh_hospitals   — NYS DOH hospitals
    "terramind_buildings",  # step_terramind_buildings (commit 4) — NYC LoRA
]


def collect(state: dict[str, Any]) -> dict[str, Any]:
    """Return {state_key: value} for every Keystone source that fired."""
    return {k: state[k] for k in SOURCES if state.get(k) is not None}
