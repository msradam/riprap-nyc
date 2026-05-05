"""Five Stones — conceptual grouping over the FSM specialists.

Riprap's FSM runs ~20 atomic specialist actions; the Stones layer is a
thin re-grouping that gives the trace UI, the briefing prompt, and the
project's public framing five legible roles instead of 20 atomic
function calls.

Each Stone module exposes the same shape:

    NAME         — display name (e.g. "Cornerstone")
    TAGLINE      — single phrase used as a section header
    DESCRIPTION  — one-sentence description for the README / trace UI
    SOURCES      — list of FSM state keys this Stone aggregates from
    collect(state)  — pull this Stone's documents out of the state dict

Order is meaningful:
  1. Cornerstone — the hazard reader (static record)
  2. Keystone    — the asset register (exposure)
  3. Touchstone  — the live observer (current sensors + EO)
  4. Lodestone   — the projector (forecast)
  5. Capstone    — the synthesiser (Granite 4.1 + Mellea)

The first four are *data-Stones*; the Capstone IS the reconciler.
"""
from __future__ import annotations

from app.stones import capstone, cornerstone, keystone, lodestone, touchstone

# Iteration order for the briefing prompt and trace UI.
DATA_STONES = [cornerstone, keystone, touchstone, lodestone]
ALL_STONES = DATA_STONES + [capstone]

__all__ = [
    "ALL_STONES",
    "DATA_STONES",
    "capstone",
    "cornerstone",
    "keystone",
    "lodestone",
    "touchstone",
]
