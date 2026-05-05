"""Decide whether Phase 4's synthetic-SAR fallback should fire.

The integrated specialist will gate on this function: when the primary
Phase 1 path can't find a usable cloud-free Sentinel-2 acquisition, the
fallback (real S1GRD → TerraMind → synthesized S2L2A → existing Phase
1 segmentation head) takes over.

Trigger ladder:
  1. Cloud-free S2 (cloud_cover < 30%) within ±3 days of today: use
     primary path. Return should_use_terramind=False.
  2. Cloud-tolerant S2 (cloud_cover < 50%) within ±14 days: use primary
     path with a flag indicating relaxed-cloud. Still primary; the
     reconciler should disclose vintage in the briefing.
  3. Otherwise: fallback to TerraMind synthesis. Return
     should_use_terramind=True.

This module only depends on PC's S2 collection — independent of the
S1 STAC reachability.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass


@dataclass
class TriggerDecision:
    should_use_terramind: bool
    primary_scene_id: str | None
    primary_cloud_pct: float | None
    primary_age_days: int | None
    rationale: str


def decide(lat: float, lon: float,
           strict_days: int = 3, strict_cloud: float = 30.0,
           tolerant_days: int = 14, tolerant_cloud: float = 50.0
           ) -> TriggerDecision:
    """Walk the trigger ladder and return the verdict."""
    import planetary_computer as pc
    from pystac_client import Client

    today = dt.datetime.utcnow().date()
    end = today + dt.timedelta(days=1)
    far_start = today - dt.timedelta(days=tolerant_days)
    delta = 0.02

    client = Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=pc.sign_inplace,
    )
    search = client.search(
        collections=["sentinel-2-l2a"],
        bbox=[lon - delta, lat - delta, lon + delta, lat + delta],
        datetime=f"{far_start}/{end}",
        query={"eo:cloud_cover": {"lt": tolerant_cloud}},
        max_items=20,
    )
    items = list(search.items())
    if not items:
        return TriggerDecision(
            should_use_terramind=True,
            primary_scene_id=None,
            primary_cloud_pct=None,
            primary_age_days=None,
            rationale=f"no S2 acquisition in last {tolerant_days}d "
                      f"under {tolerant_cloud}% cloud — TerraMind synthesis required",
        )
    items.sort(key=lambda it: (
        it.properties.get("eo:cloud_cover", 100),
        -(it.datetime.timestamp() if it.datetime else 0),
    ))
    best = items[0]
    cc = float(best.properties.get("eo:cloud_cover", 100))
    age_days = (today - best.datetime.date()).days if best.datetime else 999

    # Tier 1: strict ±3d cloud-free
    if cc < strict_cloud and age_days <= strict_days:
        return TriggerDecision(
            should_use_terramind=False,
            primary_scene_id=best.id,
            primary_cloud_pct=cc,
            primary_age_days=age_days,
            rationale=f"primary path: clear S2 {age_days}d ago "
                      f"({cc:.1f}% cloud)",
        )
    # Tier 2: cloud-tolerant within ±14d
    if cc < tolerant_cloud and age_days <= tolerant_days:
        return TriggerDecision(
            should_use_terramind=False,
            primary_scene_id=best.id,
            primary_cloud_pct=cc,
            primary_age_days=age_days,
            rationale=f"primary path with relaxed cloud: best S2 "
                      f"{age_days}d ago ({cc:.1f}% cloud)",
        )
    # Tier 3: fallback
    return TriggerDecision(
        should_use_terramind=True,
        primary_scene_id=best.id,
        primary_cloud_pct=cc,
        primary_age_days=age_days,
        rationale=f"fallback: best S2 in {tolerant_days}d window is "
                  f"{age_days}d old at {cc:.1f}% cloud — TerraMind synthesis",
    )


if __name__ == "__main__":
    import argparse
    import json
    from dataclasses import asdict
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    args = ap.parse_args()
    d = decide(args.lat, args.lon)
    print(json.dumps(asdict(d), indent=2))
