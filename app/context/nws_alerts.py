"""NWS API — active alerts at a point.

api.weather.gov/alerts/active?point={lat},{lon}, no auth, JSON.
A User-Agent header is required (NWS rate-limits anonymous traffic).

We surface only flood-relevant categories so the doc the reconciler
sees is short and on-topic.
"""
from __future__ import annotations

from typing import Any

import httpx

DOC_ID = "nws_alerts"
CITATION = "NWS public alert API (api.weather.gov/alerts)"

USER_AGENT = "Riprap-NYC/0.1 (civic-flood-tool; +https://huggingface.co/spaces/msradam/riprap-nyc)"

_FLOOD_EVENT_KEYWORDS = (
    "flood", "flash flood", "coastal flood", "high surf", "storm surge",
    "hurricane", "tropical storm", "tornado warning",  # high-impact context
    "rip current",
)


def _is_flood_relevant(event_name: str) -> bool:
    e = (event_name or "").lower()
    return any(k in e for k in _FLOOD_EVENT_KEYWORDS)


def alerts_at(lat: float, lon: float) -> list[dict[str, Any]]:
    r = httpx.get(
        "https://api.weather.gov/alerts/active",
        params={"point": f"{lat:.4f},{lon:.4f}"},
        headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json"},
        timeout=8.0,
    )
    r.raise_for_status()
    out = []
    for f in r.json().get("features", []):
        p = f.get("properties", {}) or {}
        event = p.get("event") or ""
        if not _is_flood_relevant(event):
            continue
        out.append({
            "id": p.get("id"),
            "event": event,
            "severity": p.get("severity"),
            "urgency": p.get("urgency"),
            "certainty": p.get("certainty"),
            "headline": p.get("headline"),
            "sent": p.get("sent"),
            "effective": p.get("effective"),
            "expires": p.get("expires"),
            "sender_name": p.get("senderName"),
            "areaDesc": p.get("areaDesc"),
        })
    return out


def summary_for_point(lat: float, lon: float) -> dict:
    try:
        active = alerts_at(lat, lon)
    except Exception as e:
        return {"n_active": 0, "alerts": [], "error": str(e)}
    return {
        "n_active": len(active),
        "alerts": active,
        "error": None,
    }
