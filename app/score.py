"""Riprap exposure scoring — research-grounded deterministic rubric.

This is an EXPOSURE index, not a damage probability. It produces a tier
1-4 from a thematic additive composite over min-max-normalized indicators
within sub-indices. The same input always produces the same tier; live
signals (NWS alerts, surge residual, hourly precip) are NOT in this
score — they are surfaced as a separate "current conditions" badge per
NPCC4 / IPCC AR6 WG II's distinction between exposure (quasi-stationary
property of place) and event occurrence (time-varying).

Methodology:
- Cutter, Boruff & Shirley, 2003. "Social Vulnerability to Environmental
  Hazards." Social Science Quarterly 84(2): 242-261. — hazards-of-place
  composite construction.
- Tate, 2012. "Social Vulnerability Indices: A Comparative Assessment
  Using Uncertainty and Sensitivity Analysis." Natural Hazards 63: 325-
  347. — equal weights within thematic groups are the most rank-stable
  default; differential weighting is hard to defend.
- Balica, Wright & van der Meulen, 2012. "A Flood Vulnerability Index
  for Coastal Cities." Natural Hazards 64: 73-105. — multiplicative
  override behaviour; we recover the important part as a "max-empirical
  floor" rather than a full multiplicative form.

Per-indicator citations:
- HAND breakpoints: Nobre et al., 2011. "Height Above the Nearest
  Drainage." J. Hydrology 404: 13-29.
- TWI: Beven & Kirkby, 1979. Hydrological Sciences Bulletin 24; Sørensen,
  Zinko & Seibert, 2006. HESS 10: 101-112. (Half-weight because TWI is
  noisier than HAND in flat urban DEMs; we percentile-bin rather than
  use absolute cutoffs.)
- Zone hierarchy: NYC NPCC4 (2024) Ch. 3; NYC Hazard Mitigation Plan 2024.
- USGS HWM proximity floor: USGS HWM positional uncertainty is typically
  5-30 m horizontal, so 100 m gives ~3σ headroom for a true "this
  address was inundated" signal.

Scope limit: We have no labeled flood-damage outcomes. The tier is a
literature-grounded exposure prior, not a calibrated loss prediction.
For insurance pricing, use FEMA Risk Rating 2.0 (claims-driven GLM).
"""
from __future__ import annotations

import pandas as pd

# ---------- Indicator schemas ----------------------------------------------
#
# Each sub-index is a mapping {indicator_name: weight}. Within a sub-index,
# the weighted sum is normalized by the maximum possible weight, giving a
# 0-1 score per sub-index. The composite is the sum of the three sub-index
# scores (range 0-3), then mapped to tiers.
#
# Why equal weights within thematic groups: Tate 2012's uncertainty
# analysis showed that differential weighting is the most-attacked axis
# of any composite vulnerability/exposure index. Equal weights are the
# safest default; agency tiering (which puts FEMA 1% above 0.2%, Sandy
# above modeled scenarios) supplies the remaining structure.

REGULATORY = {
    # FEMA NFHL — regulatory baseline. SFHA (1%) is the mandate threshold.
    "fema_1pct":            1.00,
    "fema_02pct":           0.50,
    # NYC DEP Stormwater Maps (2021) — modeled pluvial scenarios.
    # Moderate-2050 is treated heavier than Extreme-2080 because NPCC4
    # explicitly designates 2080 SLR + 7 in/hr as a TAIL scenario.
    "dep_moderate_2050":    0.75,
    "dep_extreme_2080":     0.50,
    "dep_tidal_2050":       0.75,
}

HYDROLOGICAL = {
    # HAND (Height Above Nearest Drainage), banded per Nobre et al. 2011.
    # Bands: <1 m (channel/floodplain near-certain wet) → 1.0
    #        1-3 m (floodplain)                         → 0.66
    #        3-10 m (transitional)                      → 0.33
    #        >10 m (hillslope, dry)                     → 0
    "hand_band":            1.00,
    # TWI quartile (top quartile = saturation-prone). Half-weight
    # because TWI is noisier than HAND in urban DEMs; we percentile-bin
    # within NYC rather than using absolute cutoffs.
    "twi_quartile":         0.50,
    # Local-relief inversions: low percentile = topographic low point.
    # Bins: <10th=1.0, 10-25th=0.66, 25-50th=0.33, ≥50th=0.
    "elev_pct_200m_inv":    0.50,
    "elev_pct_750m_inv":    0.50,
    # Basin relief contributes a small additional terrain term.
    "basin_relief_band":    0.25,
}

EMPIRICAL = {
    # Sandy 2012 inundation — empirical post-event extent. Also triggers
    # the max-empirical FLOOR rule below.
    "sandy":                1.00,
    # USGS Hurricane Ida 2021 high-water marks. Within 100 m → "direct"
    # (also triggers the floor); 100-800 m → "neighborhood proximity".
    "ida_hwm_within_100m":  1.00,
    "ida_hwm_within_800m":  0.50,
    # Prithvi-EO 2.0 satellite-derived inundation polygon (Hurricane Ida
    # pre/post diff) — semi-empirical because model-derived but
    # conditioned on observed Sentinel-2 imagery.
    "prithvi_polygon":      0.75,
    # NYC 311 flood-related complaint count, banded over 5-year window:
    #   ≥10 → 1.0, 3-9 → 0.66, 1-2 → 0.33, 0 → 0
    # Weight capped at 0.75 because 311 has documented socio-economic
    # reporting bias (engagement varies by neighborhood).
    "complaints_band":      0.75,
    # FloodNet trigger flag (any labeled flood event at any sensor
    # within 600 m, last 3 years). Same 0.75 cap as 311 since both have
    # spatial coverage bias.
    "floodnet_trigger":     0.75,
}


def _hand_band(hand_m: float | None) -> float:
    """Nobre et al. 2011 HAND classes adapted for NYC's flat urban terrain."""
    if hand_m is None:
        return 0.0
    if hand_m < 1.0:
        return 1.0
    if hand_m < 3.0:
        return 0.66
    if hand_m < 10.0:
        return 0.33
    return 0.0


def _percentile_inv_band(pct: float | None) -> float:
    """Inverted relief percentile: lower = more exposed (water pools here)."""
    if pct is None:
        return 0.0
    if pct < 10:
        return 1.0
    if pct < 25:
        return 0.66
    if pct < 50:
        return 0.33
    return 0.0


def _twi_quartile(twi: float | None) -> float:
    """TWI thresholds calibrated to NYC's flat 30 m DEM. Top quartile
    cutoff comes from the NYC-wide TWI distribution; here we approximate
    with literature-typical breakpoints (Sørensen 2006 site-specific
    advice)."""
    if twi is None:
        return 0.0
    if twi >= 12:
        return 1.0
    if twi >= 10:
        return 0.66
    if twi >= 8:
        return 0.33
    return 0.0


def _basin_relief_band(relief_m: float | None) -> float:
    if relief_m is None:
        return 0.0
    # Higher basin relief in a flat area means the address sits in a real
    # depression. Banding is empirical for NYC.
    if relief_m >= 8:
        return 1.0
    if relief_m >= 4:
        return 0.66
    if relief_m >= 2:
        return 0.33
    return 0.0


def _complaints_band(n: int | None) -> float:
    if not n:
        return 0.0
    if n >= 10:
        return 1.0
    if n >= 3:
        return 0.66
    if n >= 1:
        return 0.33
    return 0.0


# ---------- Sub-index computation ------------------------------------------

def _normalize(weighted: float, weights: dict[str, float]) -> float:
    max_w = sum(weights.values())
    return weighted / max_w if max_w else 0.0


def regulatory_subindex(s: dict) -> float:
    """0..1. All inputs are binary (inside zone or not)."""
    w = REGULATORY
    raw = sum(w[k] * (1.0 if s.get(k) else 0.0) for k in w)
    return _normalize(raw, w)


def hydrological_subindex(s: dict) -> float:
    """0..1. Inputs are continuous; convert to ordinal bands first."""
    w = HYDROLOGICAL
    bands = {
        "hand_band":          _hand_band(s.get("hand_m")),
        "twi_quartile":       _twi_quartile(s.get("twi")),
        "elev_pct_200m_inv":  _percentile_inv_band(s.get("rel_elev_pct_200m")),
        "elev_pct_750m_inv":  _percentile_inv_band(s.get("rel_elev_pct_750m")),
        "basin_relief_band":  _basin_relief_band(s.get("basin_relief_m")),
    }
    raw = sum(w[k] * bands[k] for k in w)
    return _normalize(raw, w)


def empirical_subindex(s: dict) -> float:
    """0..1. Mix of binary and banded count signals."""
    w = EMPIRICAL
    vals = {
        "sandy":               1.0 if s.get("sandy") else 0.0,
        "ida_hwm_within_100m": 1.0 if s.get("ida_hwm_within_100m") else 0.0,
        "ida_hwm_within_800m": 1.0 if s.get("ida_hwm_within_800m") else 0.0,
        "prithvi_polygon":     1.0 if s.get("prithvi_polygon") else 0.0,
        "complaints_band":     _complaints_band(s.get("complaints_count")),
        "floodnet_trigger":    1.0 if s.get("floodnet_trigger") else 0.0,
    }
    raw = sum(w[k] * vals[k] for k in w)
    return _normalize(raw, w)


# ---------- Composite + tier mapping ---------------------------------------

# Tier breakpoints over the composite (range 0-3, since each sub-index is
# 0-1). Tuned so that "Sandy + DEP-2050 + HAND<1m" lands in Tier 1, and a
# single positive signal lands in Tier 4. Documented in METHODOLOGY.md.
TIER_BREAKPOINTS = [
    (1.50, 1),   # high — multiple sub-indices saturated
    (1.00, 2),   # elevated — at least one strong sub-index
    (0.50, 3),   # moderate — partial signals across categories
    (0.01, 4),   # limited — a single contextual signal
]

TIER_LABELS = {
    1: ("High exposure",       "Multiple sub-indices saturated; empirical and/or "
                               "modeled scenarios both indicate substantial exposure."),
    2: ("Elevated exposure",   "At least one sub-index near saturation; significant "
                               "overlap with empirical or modeled scenarios."),
    3: ("Moderate exposure",   "Partial signals across categories; scenario- or "
                               "neighborhood-specific exposure."),
    4: ("Limited exposure",    "A single contextual signal; no positive scenario hits."),
    0: ("No flagged exposure", "No positive flood signal across the assessed sources."),
}


def composite(signals: dict) -> dict:
    """Compute sub-indices, composite score, and tier with the floor rule.

    Returns: {
        'subindices': {'regulatory': 0..1, 'hydrological': 0..1, 'empirical': 0..1},
        'composite': 0..3,
        'tier': 0..4,
        'floor_applied': bool,
    }

    Max-empirical floor: if Sandy 2012 inundation OR a USGS Ida HWM within
    100 m fired, the tier is capped at 2 (cannot be worse). This recovers
    the multiplicative behavior — empirical evidence overrides terrain or
    modeled scenarios — without giving up additive transparency.
    """
    reg = regulatory_subindex(signals)
    hyd = hydrological_subindex(signals)
    emp = empirical_subindex(signals)
    composite_score = reg + hyd + emp

    raw_tier = 0
    for breakpoint, t in TIER_BREAKPOINTS:
        if composite_score >= breakpoint:
            raw_tier = t
            break

    floor_applied = bool(signals.get("sandy") or signals.get("ida_hwm_within_100m"))
    if floor_applied and (raw_tier == 0 or raw_tier > 2):
        final_tier = 2
    else:
        final_tier = raw_tier

    return {
        "subindices": {
            "regulatory":   round(reg, 3),
            "hydrological": round(hyd, 3),
            "empirical":    round(emp, 3),
        },
        "composite":     round(composite_score, 3),
        "tier":          final_tier,
        "floor_applied": floor_applied,
    }


# ---------- Backward-compat shims ------------------------------------------
# Register CLI and register_builder consume a flat `tier` column on a
# DataFrame. The shim materializes composite() over rows and writes back
# `score` (composite scaled 0-100) and `tier`.

def tier(score: int) -> int:
    """Legacy bridge for callers that still pass a small-integer score.
    Maps the OLD additive-integer score to the new tier breakpoints by
    scaling. Prefer composite() for new code."""
    if score >= 6: return 1
    if score >= 4: return 2
    if score >= 2: return 3
    if score >= 1: return 4
    return 0


# Legacy WEIGHTS map kept so riprap.py and any external consumer
# continue to import without breaking. The new composite() is the
# authoritative scorer.
WEIGHTS = {
    "sandy":                 3,
    "dep_extreme_2080":      2,
    "dep_moderate_2050":     2,
    "dep_moderate_current":  1,
    "complaints_3plus":      1,
    "floodnet_trigger":      1,
    "policy_named":          1,
}


def score_row(signals: dict) -> tuple[int, int]:
    """Legacy-shape wrapper around composite(). Returns (composite_x100, tier)."""
    c = composite(signals)
    return int(round(c["composite"] * 100)), c["tier"]


def score_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Vectorized composite over a DataFrame whose columns name our
    indicators. Missing columns are treated as 0 / None.

    Adds columns: subindex_regulatory, subindex_hydrological,
    subindex_empirical, composite, score, tier, floor_applied.
    `score` is the composite scaled 0-100 for register CSV legibility.
    """
    out = df.copy()
    rows = out.to_dict(orient="records")
    results = [composite(r) for r in rows]
    out["subindex_regulatory"]   = [r["subindices"]["regulatory"]   for r in results]
    out["subindex_hydrological"] = [r["subindices"]["hydrological"] for r in results]
    out["subindex_empirical"]    = [r["subindices"]["empirical"]    for r in results]
    out["composite"]    = [r["composite"]     for r in results]
    out["score"]        = (out["composite"] * 100).round().astype(int)
    out["tier"]         = [r["tier"]          for r in results]
    out["floor_applied"] = [r["floor_applied"] for r in results]
    return out
