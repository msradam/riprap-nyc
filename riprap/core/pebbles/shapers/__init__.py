"""Shapers — optional post-processors that transform an adapter's canonical
result dict into a pebble-specific shape.

Use sparingly: prefer to have the adapter return the right shape via
declarative config. Shapers exist for cases where downstream code (legacy
or otherwise) expects a non-generic shape that's expensive to express in
YAML.

A shaper is a callable `(value: dict) -> dict` (also accepts None and
returns None). Registered here by short name; manifests reference it via
the optional `shaper:` field.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from riprap.core.pebbles.schema import PebbleManifest
from riprap.core.pebbles.shapers.boolean_zone import shape as _boolean_zone
from riprap.core.pebbles.shapers.dep_scenario import shape as _dep_scenario
from riprap.core.pebbles.shapers.ida_hwm import shape as _ida_hwm

Shaper = Callable[[Any, PebbleManifest], Any]

SHAPERS: dict[str, Shaper] = {
    "ida_hwm": _ida_hwm,
    "dep_scenario": _dep_scenario,
    "boolean_zone": _boolean_zone,
}

__all__ = ["SHAPERS", "Shaper"]
