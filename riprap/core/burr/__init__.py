"""Burr layer — first-class state machine on top of the pebble registry.

The runtime is composed of:

  intake_action       (planner + geocode; sets query, intent, lat, lon)
       ↓
  cornerstone_action  (MapActions: parallel fan-out over Cornerstone pebbles)
  touchstone_action   (MapActions: ditto for Touchstone)
  lodestone_action    (MapActions: ditto for Lodestone)
  keystone_action     (MapActions: ditto for Keystone)
       ↓
  capstone_action     (sub-Application: rag + reconcile + Mellea iterate)

Each Stone's pebble actions are generated at call time from the
manifest registry — there is no per-pebble @action boilerplate.
Adding a pebble in YAML automatically extends the Stone's fan-out.
"""
from riprap.core.burr.pebble import pebble_action, trace_rec_for
from riprap.core.burr.stones import (
    CornerstoneAction,
    KeystoneAction,
    LodestoneAction,
    TouchstoneAction,
)

__all__ = [
    "pebble_action",
    "trace_rec_for",
    "CornerstoneAction",
    "TouchstoneAction",
    "LodestoneAction",
    "KeystoneAction",
]
