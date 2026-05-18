"""boolean_zone shaper — wrap a bare bool result as a templatable dict.

Some baked spatial-membership pebbles (sandy 2012 zone, FEMA SFHA,
storm-surge polygon) emit a single True / False indicating whether
the queried point is inside the polygon. The templated reconciler
needs a dict to format `narration.template`; without one the only
fallback is `narration.short`, which can only describe one of the
two outcomes — "inside" or "outside", never both.

The shaper takes the bare bool and emits:

    { "inside": True, "inside_phrasing": "is inside",
      "outside_phrasing": "is not inside" }    when True
    { "inside": False, "inside_phrasing": "is not inside",
      "outside_phrasing": "is inside" }        when False

Manifests reference this via `shaper: boolean_zone`. The
`narration.template` then formats with `{inside_phrasing}` or
`{inside}` to phrase the outcome correctly for the actual value.

This is the architectural move toward a location-agnostic
cardAdapter: phrasing lives in the deployment's pebble manifest
(declarative, per-deployment), not in the UI codebase. Renderer
dispatches purely on `display.kind`.
"""
from __future__ import annotations

from typing import Any

from riprap.core.pebbles.schema import PebbleManifest


def shape(value: Any, _manifest: PebbleManifest) -> dict[str, Any]:
    """Coerce a bool (or already-dict) sandy-style result to the
    templatable shape. Returns None unchanged so the pebble action
    can surface offline / error states normally."""
    if value is None:
        return None
    # Phrasings designed for "This address {inside_phrasing} <zone>."
    #   inside=True  → "sits within"   ("This address sits within Sandy.")
    #   inside=False → "sits outside"  ("This address sits outside Sandy.")
    # `inside_or_outside` is the noun form ("inside" / "outside"), useful
    # for headlines and chip labels.
    if isinstance(value, dict):
        inside = bool(value.get("inside", False))
        out = dict(value)
        out.setdefault("inside_phrasing", "sits within" if inside else "sits outside")
        out.setdefault("inside_or_outside", "inside" if inside else "outside")
        return out
    inside = bool(value)
    return {
        "inside": inside,
        "inside_phrasing": "sits within" if inside else "sits outside",
        "inside_or_outside": "inside" if inside else "outside",
    }
