"""Transparent exposure scoring rubric. Published, not a black box.

Each signal contributes a small integer; sum -> tier 1..4.
"""
from __future__ import annotations

import pandas as pd

WEIGHTS = {
    "sandy": 3,                 # empirical Sandy 2012 inundation
    "dep_extreme_2080": 2,      # pluvial scenario, 3.66 in/hr + 2080 SLR
    "dep_moderate_2050": 2,     # pluvial scenario, 2.13 in/hr + 2050 SLR
    "dep_moderate_current": 1,  # pluvial scenario, 2.13 in/hr current
    "complaints_3plus": 1,      # >=3 flood-related 311s within 200m, last 5 years
    "floodnet_trigger": 1,      # FloodNet sensor within 400m with >=1 trigger event
    "policy_named": 1,          # named in HMP/NPCC4/agency plan paragraph (RAG hit)
}


def tier(score: int) -> int:
    if score >= 6:
        return 1
    if score >= 4:
        return 2
    if score >= 2:
        return 3
    if score >= 1:
        return 4
    return 0


def score_row(signals: dict) -> tuple[int, int]:
    s = 0
    for k, w in WEIGHTS.items():
        if signals.get(k):
            s += w
    return s, tier(s)


def score_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["score"] = 0
    for k, w in WEIGHTS.items():
        if k in out.columns:
            out["score"] += out[k].astype(bool).astype(int) * w
    out["tier"] = out["score"].map(tier)
    return out
