"""Shaper for the three DEP stormwater scenario pebbles.

`dep_stormwater.join_raster()` returns an integer depth class (0 outside,
1 nuisance, 2 deep+contiguous 1-4 ft, 3 deep >4 ft). Downstream consumers
expect a dict with the int class, a human-readable label, and a citation
naming the scenario — preserves the legacy state["dep"][scenario] shape.
"""
from __future__ import annotations

_DEPTH_CLASS_LABELS = {
    0: "outside",
    1: "Nuisance (>4 in to 1 ft)",
    2: "Deep & Contiguous (1-4 ft)",
    3: "Deep Contiguous (>4 ft)",
}


def shape(value, manifest) -> dict:
    cls = int(value) if value is not None else 0
    citation = (manifest.provenance.citation
                or f"NYC DEP Stormwater Flood Map — {manifest.title}")
    return {
        "depth_class": cls,
        "depth_label": _DEPTH_CLASS_LABELS.get(cls, "outside"),
        "citation": citation,
    }
