"""Per-query energy footprint estimate.

Conservative, defensible numbers — no overclaim. We measure local
inference time and apply a published-range package-power figure for
Apple-Silicon LLM inference; we compare to the most recent published
estimate of frontier-cloud per-query energy (Epoch AI, 2025).

This is not a benchmark — it's a transparent rule-of-thumb that the
user can audit. The system prompt and the UI both surface the
underlying numbers and the citation.
"""
from __future__ import annotations

# Local: Granite 4.1:3b on Apple M-series (M3/M4 Pro range)
# Sustained package power during ~5 s of LLM inference, q4_K_M quant.
# Source: ml.energy + community measurements; conservative midpoint.
LOCAL_PACKAGE_POWER_W = 20.0

# Frontier cloud per-query inference energy.
# Source: Epoch AI, "How much energy does ChatGPT use?" (2025).
# https://epoch.ai/gradient-updates/how-much-energy-does-chatgpt-use
# This is a typical-query estimate for GPT-4o-class inference; long-context
# queries scale roughly linearly with token count.
CLOUD_PER_QUERY_WH = 0.30

# Citation strings used in the UI.
LOCAL_SOURCE = ("ml.energy / community measurements; ~20 W package power "
                "during Granite 4.1:3b q4_K_M inference on Apple M-series.")
CLOUD_SOURCE = ('Epoch AI (2025), "How much energy does ChatGPT use?", '
                "estimating ~0.3 Wh per typical GPT-4o query.")


def estimate(reconcile_seconds: float, total_seconds: float | None = None) -> dict:
    """Return a per-query energy estimate.

    Args:
      reconcile_seconds: wallclock of the Granite reconcile step (the
        only step that meaningfully draws CPU/GPU power).
      total_seconds: optional full-FSM wallclock for context.
    """
    local_wh = LOCAL_PACKAGE_POWER_W * reconcile_seconds / 3600.0
    return {
        "local_wh": round(local_wh, 4),
        "local_mwh": round(local_wh * 1000, 1),
        "cloud_wh": CLOUD_PER_QUERY_WH,
        "cloud_mwh": round(CLOUD_PER_QUERY_WH * 1000, 1),
        "ratio_cloud_over_local": round(CLOUD_PER_QUERY_WH / local_wh, 1) if local_wh > 0 else None,
        "method": {
            "local": f"{LOCAL_PACKAGE_POWER_W} W × {reconcile_seconds:.2f} s ÷ 3600",
            "local_source": LOCAL_SOURCE,
            "cloud": f"{CLOUD_PER_QUERY_WH} Wh per query (published estimate)",
            "cloud_source": CLOUD_SOURCE,
        },
        "reconcile_seconds": round(reconcile_seconds, 2),
        "total_seconds": round(total_seconds, 2) if total_seconds is not None else None,
    }
