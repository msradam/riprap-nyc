"""FloodNet NYC — live ultrasonic flood sensor network.

Hasura GraphQL endpoint, no auth, ~350 sensors. Used for:
  - sensors_near(lat, lon, radius_m) → list of deployments
  - flood_events_for(deployment_ids, since) → labeled flood events per sensor
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

URL = "https://api.floodnet.nyc/v1/graphql"
DOC_ID = "floodnet"
CITATION = "FloodNet NYC ultrasonic depth sensors (api.floodnet.nyc)"


@dataclass
class Sensor:
    deployment_id: str
    name: str
    street: str
    borough: str
    status: str
    deployed_at: str | None
    lat: float | None = None
    lon: float | None = None


@dataclass
class FloodEvent:
    deployment_id: str
    start_time: str
    end_time: str | None
    max_depth_mm: int | None
    label: str | None


def _gql(query: str, variables: dict[str, Any]) -> dict:
    r = httpx.post(URL, json={"query": query, "variables": variables},
                   timeout=20, verify=False)
    r.raise_for_status()
    j = r.json()
    if "errors" in j:
        raise RuntimeError(f"FloodNet GraphQL error: {j['errors']}")
    return j["data"]


_NEAR_Q = """
query Near($lat: Float!, $lon: Float!, $r: Float!) {
  deployments_within_radius(args:{lat:$lat, lon:$lon, radius_meters:$r},
                            order_by:{date_deployed: asc}) {
    deployment_id
    name
    sensor_address_street
    sensor_address_borough
    sensor_status
    date_deployed
    location
  }
}"""


def _parse_location(loc) -> tuple[float | None, float | None]:
    """Hasura PostGIS geometry returned as a GeoJSON object."""
    if not loc or not isinstance(loc, dict):
        return None, None
    coords = loc.get("coordinates")
    if not coords or len(coords) < 2:
        return None, None
    return coords[1], coords[0]  # (lat, lon) from (lon, lat)


def sensors_near(lat: float, lon: float, radius_m: float = 1000) -> list[Sensor]:
    d = _gql(_NEAR_Q, {"lat": lat, "lon": lon, "r": radius_m})
    out = []
    for row in d["deployments_within_radius"]:
        slat, slon = _parse_location(row.get("location"))
        out.append(Sensor(
            deployment_id=row["deployment_id"],
            name=row["name"] or "",
            street=row.get("sensor_address_street") or "",
            borough=row.get("sensor_address_borough") or "",
            status=row.get("sensor_status") or "",
            deployed_at=row.get("date_deployed"),
            lat=slat,
            lon=slon,
        ))
    return out


_EVENTS_Q = """
query Events($ids: [String!], $since: timestamp!) {
  sensor_events(where:{
      deployment_id:{_in:$ids},
      start_time:{_gte:$since},
      label:{_eq:"flood"}
  }, order_by:{start_time: desc}, limit: 200) {
    deployment_id
    start_time
    end_time
    max_depth_proc_mm
    label
  }
}"""


def flood_events_for(deployment_ids: list[str],
                     since: datetime | None = None) -> list[FloodEvent]:
    if not deployment_ids:
        return []
    if since is None:
        since = datetime.now(timezone.utc) - timedelta(days=365 * 3)
    d = _gql(_EVENTS_Q, {
        "ids": deployment_ids,
        "since": since.isoformat(timespec="seconds").replace("+00:00", ""),
    })
    return [
        FloodEvent(
            deployment_id=row["deployment_id"],
            start_time=row["start_time"],
            end_time=row.get("end_time"),
            max_depth_mm=row.get("max_depth_proc_mm"),
            label=row.get("label"),
        )
        for row in d["sensor_events"]
    ]


def summary_for_point(lat: float, lon: float, radius_m: float = 600) -> dict:
    """One-shot summary used by the FSM node and the cited paragraph."""
    sensors = sensors_near(lat, lon, radius_m)
    ids = [s.deployment_id for s in sensors]
    events = flood_events_for(ids)
    by_dep: dict[str, list[FloodEvent]] = {}
    for e in events:
        by_dep.setdefault(e.deployment_id, []).append(e)
    peak = max((e for e in events if e.max_depth_mm is not None),
               key=lambda e: e.max_depth_mm or 0, default=None)
    n_sensors = len(sensors)
    n_events = len(events)
    # Templatable narrative for the manifest's narration.template.
    # Honest negative ("0 sensors within range") still useful — same
    # contract as the NWS / ida_hwm all-clear cards.
    if n_sensors == 0:
        narrative = (
            f"No FloodNet sensors deployed within {int(radius_m)} m of "
            f"this address."
        )
    else:
        narrative = (
            f"{n_sensors} FloodNet community sensor(s) within "
            f"{int(radius_m)} m have logged {n_events} above-curb flood "
            f"event(s) in the last 3 years."
        )
        if peak is not None and peak.max_depth_mm is not None:
            narrative += (
                f" Peak depth recorded by these sensors: "
                f"{peak.max_depth_mm} mm."
            )
    return {
        "n_sensors": n_sensors,
        "sensors": [vars(s) for s in sensors],
        "n_flood_events_3y": n_events,
        "n_sensors_with_events": len(by_dep),
        "peak_event": vars(peak) if peak else None,
        "narrative": narrative,
    }
