"""Shaper for the three DEP stormwater scenario pebbles.

`dep_stormwater.join_raster()` returns an integer depth class (0 outside,
1 nuisance, 2 deep+contiguous 1-4 ft, 3 deep >4 ft). Downstream consumers
expect a dict with the int class, a human-readable label, a citation
naming the scenario, and a `narrative` the manifest's narration.template
renders verbatim.

Class 0 (outside this scenario) returns None so the templated card
silently drops — matches the prior buildDep behaviour of only surfacing
scenarios that actually flood at the address.
"""
from __future__ import annotations

_DEPTH_CLASS_LABELS = {
    0: "outside",
    1: "Nuisance (>4 in to 1 ft)",
    2: "Deep & Contiguous (1-4 ft)",
    3: "Deep Contiguous (>4 ft)",
}


def shape(value, manifest) -> dict | None:
    cls = int(value) if value is not None else 0
    if cls <= 0:
        # No flooding in this scenario — drop the card silently rather
        # than render three "outside" cards per address. Matches the
        # legacy buildDep filter (rows.length === 0 → null).
        return None
    label = _DEPTH_CLASS_LABELS.get(cls, "outside")
    citation = (manifest.provenance.citation
                or f"NYC DEP Stormwater Flood Map — {manifest.title}")
    # Type-keyed narrative the manifest's narration.template renders.
    # The scenario name (e.g. "Extreme — 3.66 in/hr, 2080 SLR") is
    # extracted from manifest.title's parenthetical; if absent, fall
    # back to a class-only sentence.
    title = manifest.title or ""
    paren_start = title.find("(")
    paren_end = title.rfind(")")
    if paren_start >= 0 and paren_end > paren_start:
        scenario_label = title[paren_start + 1:paren_end]
        narrative = f"NYC DEP modeled flooding ({scenario_label}): {label}."
    else:
        narrative = f"NYC DEP modeled flooding at this address: {label}."
    return {
        "depth_class": cls,
        "depth_label": label,
        "citation": citation,
        "narrative": narrative,
    }
