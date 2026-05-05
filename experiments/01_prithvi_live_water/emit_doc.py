"""Build a `role: "document prithvi_live"` chat message from a
WaterResult so the reconciler can ground a claim against it.

The doc body is a compact key:value block. We deliberately keep the
numeric framing concrete:
  - per-chip % water at the address area (5.12 km square around the
    point)
  - % water within 500 m of the address (radius)
  - the S2 scene id + acquisition date so the briefing can attribute
    the freshness honestly

The brief calls for a *comparative* claim (vs an NTA-level baseline);
the baseline computation is parked to a follow-up so this experiment
can validate the model + plumbing first. The doc surfaces the raw %
plus a placeholder `nta_baseline_pct` field that the wrapper sets to
`null` when no baseline has been computed — the reconciler is told to
omit the comparative sentence in that case.
"""

from __future__ import annotations

from typing import Any

SYSTEM_PROMPT_FRAGMENT = """\
You will be given a Prithvi-EO live water-segmentation document tagged
[prithvi_live]. Cite at least one numeric value from it using
[prithvi_live]. If `nta_baseline_pct` is null, do NOT write a
comparative sentence — only state the observed %; saying "above
baseline" without a baseline is not allowed.
"""


def make_doc(result, nta_baseline_pct: float | None = None) -> dict[str, str]:
    """Construct the chat-message tuple {role, content} for the
    reconciler."""
    rows = [
        f"address_label: {result.address_label}",
        f"observation_date: {(result.item_datetime or 'unknown')[:10]}",
        f"sentinel2_scene_id: {result.item_id or 'unknown'}",
        f"cloud_cover_pct: {result.cloud_cover:.3f}"
        if result.cloud_cover is not None else "cloud_cover_pct: unknown",
        f"pct_water_within_500m: {result.pct_water_within_500m:.2f}",
        f"pct_water_5km_chip: {result.pct_water_full:.2f}",
    ]
    if nta_baseline_pct is not None:
        rows.append(f"nta_baseline_pct: {nta_baseline_pct:.2f}")
        delta = result.pct_water_within_500m - nta_baseline_pct
        rows.append(f"delta_vs_nta_baseline_pct: {delta:+.2f}")
    else:
        rows.append("nta_baseline_pct: null")
    body = "\n".join(rows)
    return {"role": "document prithvi_live", "content": body}


def render_for_trace(result) -> dict[str, Any]:
    """Trace-card payload — what <r-trace> would render in production."""
    return {
        "label": "prithvi_live_water",
        "ok": True,
        "fields": {
            "scene": (result.item_id or "")[:32] + "…",
            "date": (result.item_datetime or "")[:10],
            "%water (≤500m)": f"{result.pct_water_within_500m:.2f}",
            "%water (5km)": f"{result.pct_water_full:.2f}",
        },
        "thumbnail_path": result.overlay_png,
    }
