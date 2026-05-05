"""NYC DOB construction-permit specialist — "what are they building".

Pulls active NYC DOB Permit Issuance records (Socrata `ipu4-2q9a`)
inside a polygon, filtered to recent New Building (NB), major
Alteration (A1), and Demolition (DM) jobs. Each project is then
cross-referenced against the static flood layers (Sandy 2012, DEP
Stormwater scenarios) so the reconciler can write things like:

  "12 active major construction projects in Gowanus. Of these,
   8 sit inside the DEP Extreme-2080 stormwater scenario."

The dataset uses separate gis_latitude / gis_longitude columns rather
than a Socrata Point, so we bbox-filter via SoQL then do exact
point-in-polygon containment client-side with shapely.
"""
from __future__ import annotations

import logging
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Any

import geopandas as gpd
import httpx
from shapely.geometry import Point

log = logging.getLogger("riprap.dob_permits")

URL = "https://data.cityofnewyork.us/resource/ipu4-2q9a.json"
DOC_ID = "dob_permits"
CITATION = ("NYC DOB Permit Issuance (NYC OpenData ipu4-2q9a) — "
            "issued/in-progress construction permits")

JOB_TYPE_LABELS = {
    "NB": "new building",
    "A1": "major alteration (use/occupancy)",
    "A2": "minor alteration",
    "A3": "minor work / interior",
    "DM": "demolition",
    "SG": "sign",
    "PL": "plumbing",
    "EQ": "equipment",
}

# Default filter: focus on "what are they building" — new construction,
# major alterations, demolitions. Skip minor mechanical permits.
DEFAULT_JOB_TYPES = ("NB", "A1", "DM")


@dataclass
class Permit:
    job_id: str
    job_type: str
    job_type_label: str
    permit_status: str
    issuance_date: str
    expiration_date: str | None
    address: str
    borough: str
    bbl: str | None
    lat: float
    lon: float
    owner_business: str | None
    permittee_business: str | None
    nta_name: str | None


def permits_in_bbox(min_lat: float, min_lon: float,
                    max_lat: float, max_lon: float,
                    job_types: tuple[str, ...] = DEFAULT_JOB_TYPES,
                    since: date | None = None,
                    limit: int = 5000) -> list[Permit]:
    """Pull DOB permits intersecting a bounding box, recently issued, with
    matching job types. We expand from polygon to bbox and rely on the
    caller to do exact point-in-polygon filtering."""
    if since is None:
        since = date.today() - timedelta(days=540)  # ~18 months
    # gis_latitude/gis_longitude are stored as text in this dataset; cast
    # to number for the bbox compare. issuance_date is a floating timestamp
    # surfaced as 'MM/DD/YYYY' string — cast explicitly to floating_timestamp
    # so the comparator parses ISO dates correctly. BETWEEN is picky on text
    # columns, so use explicit >= / <= operators.
    where = (
        f"job_type IN ({','.join(repr(t) for t in job_types)})"
        f" AND issuance_date::floating_timestamp >= '{since.isoformat()}'"
        f" AND gis_latitude::number >= {min_lat}"
        f" AND gis_latitude::number <= {max_lat}"
        f" AND gis_longitude::number >= {min_lon}"
        f" AND gis_longitude::number <= {max_lon}"
    )
    r = httpx.get(URL, params={
        "$select": ",".join([
            "job__", "job_type", "permit_status", "issuance_date",
            "expiration_date", "house__", "street_name", "borough",
            "block", "lot",
            "gis_latitude", "gis_longitude", "owner_s_business_name",
            "permittee_s_business_name", "gis_nta_name",
        ]),
        "$where": where,
        "$order": "issuance_date desc",
        "$limit": str(limit),
    }, timeout=60)
    r.raise_for_status()
    out: list[Permit] = []
    for row in r.json():
        try:
            lat = float(row["gis_latitude"])
            lon = float(row["gis_longitude"])
        except (KeyError, ValueError, TypeError):
            continue
        addr = " ".join(filter(None, [
            row.get("house__"),
            (row.get("street_name") or "").title(),
        ])).strip()
        # DOB has no `bbl` column; compose from borough + block + lot.
        # Borough codes: MAN=1, BX=2, BK=3, QN=4, SI=5.
        boro_code = {"MANHATTAN": "1", "BRONX": "2", "BROOKLYN": "3",
                     "QUEENS": "4", "STATEN ISLAND": "5"}.get(
                     (row.get("borough") or "").upper())
        block = (row.get("block") or "").lstrip("0")
        lot = (row.get("lot") or "").lstrip("0")
        bbl = (f"{boro_code}-{block.zfill(5)}-{lot.zfill(4)}"
               if boro_code and block and lot else None)
        out.append(Permit(
            job_id=row.get("job__", ""),
            job_type=row.get("job_type", ""),
            job_type_label=JOB_TYPE_LABELS.get(row.get("job_type", ""), row.get("job_type", "")),
            permit_status=row.get("permit_status", ""),
            issuance_date=(row.get("issuance_date") or "")[:10],
            expiration_date=(row.get("expiration_date") or "")[:10] or None,
            address=addr,
            borough=(row.get("borough") or "").title(),
            bbl=bbl,
            lat=lat,
            lon=lon,
            owner_business=row.get("owner_s_business_name"),
            permittee_business=row.get("permittee_s_business_name"),
            nta_name=row.get("gis_nta_name"),
        ))
    return out


def permits_in_polygon(polygon, polygon_crs: str = "EPSG:4326",
                       job_types: tuple[str, ...] = DEFAULT_JOB_TYPES,
                       since: date | None = None) -> list[Permit]:
    """Permits inside a polygon. Uses bbox prefilter + shapely contains."""
    g = gpd.GeoDataFrame(geometry=[polygon], crs=polygon_crs).to_crs("EPSG:4326")
    geom = g.iloc[0].geometry
    minx, miny, maxx, maxy = geom.bounds
    raw = permits_in_bbox(miny, minx, maxy, maxx, job_types=job_types, since=since)
    out: list[Permit] = []
    for p in raw:
        pt = Point(p.lon, p.lat)
        if geom.contains(pt) or geom.intersects(pt):
            out.append(p)
    # Dedupe by job_id (one job can have multiple permits as work proceeds)
    seen: dict[str, Permit] = {}
    for p in out:
        # Keep the most-recently-issued permit per job
        cur = seen.get(p.job_id)
        if cur is None or (p.issuance_date or "") > (cur.issuance_date or ""):
            seen[p.job_id] = p
    return list(seen.values())


def cross_reference_flood(permits: list[Permit]) -> list[dict[str, Any]]:
    """Tag each permit with which flood layers cover its point.
    Adds: in_sandy (bool), dep_class (highest depth class hit across DEP scenarios),
    dep_scenarios (list of scenario ids that fired)."""
    if not permits:
        return []
    from app.flood_layers import dep_stormwater, sandy_inundation
    pts = gpd.GeoDataFrame(
        geometry=[Point(p.lon, p.lat) for p in permits],
        crs="EPSG:4326",
    ).to_crs("EPSG:2263")
    pts["_pid"] = list(range(len(pts)))

    sandy_flags = sandy_inundation.join(pts).reset_index(drop=True).tolist()

    dep_hits = {scen: dep_stormwater.join(pts, scen)["depth_class"].astype(int).tolist()
                for scen in ("dep_extreme_2080", "dep_moderate_2050", "dep_moderate_current")}

    out = []
    for i, p in enumerate(permits):
        scen_hits = {s: dep_hits[s][i] for s in dep_hits}
        max_class = max(scen_hits.values(), default=0)
        active_scens = [s for s, c in scen_hits.items() if c > 0]
        out.append({
            **asdict(p),
            "in_sandy":      bool(sandy_flags[i]),
            "dep_max_class": max_class,
            "dep_scenarios": active_scens,
            "any_flood_layer_hit": bool(sandy_flags[i] or max_class > 0),
        })
    return out


def summary_for_polygon(polygon, polygon_crs: str = "EPSG:4326",
                        since_days: int = 540,
                        top_n: int = 8) -> dict:
    """Full polygon-mode summary: list active permits, cross-reference each
    with flood layers, return aggregate counts + a top-N projects-of-concern
    list (those that hit at least one flood layer, ranked by max DEP class
    + Sandy hit)."""
    since = date.today() - timedelta(days=since_days)
    permits = permits_in_polygon(polygon, polygon_crs=polygon_crs, since=since)
    enriched = cross_reference_flood(permits)

    by_type: Counter = Counter(e["job_type_label"] for e in enriched)
    by_status: Counter = Counter(e["permit_status"] for e in enriched)
    n_total = len(enriched)
    n_sandy = sum(1 for e in enriched if e["in_sandy"])
    n_dep_any = sum(1 for e in enriched if e["dep_max_class"] > 0)
    n_dep_severe = sum(1 for e in enriched if e["dep_max_class"] >= 2)
    n_any_flood = sum(1 for e in enriched if e["any_flood_layer_hit"])

    # Rank: severity = (in_sandy * 3) + dep_max_class
    def severity(e):
        return (3 if e["in_sandy"] else 0) + e["dep_max_class"]
    flagged = sorted(
        [e for e in enriched if e["any_flood_layer_hit"]],
        key=severity, reverse=True,
    )[:top_n]

    # Light projection of every permit for map pinning (no need to ship the
    # full permit record for the not-flagged ones — the map only needs lat,
    # lon, address, job_type_label, and the flood-flag fields).
    all_pins = [
        {
            "lat":           e["lat"],
            "lon":           e["lon"],
            "address":       e["address"],
            "job_type":      e["job_type"],
            "in_sandy":      e["in_sandy"],
            "dep_max_class": e["dep_max_class"],
            "any_flood":     e["any_flood_layer_hit"],
        }
        for e in enriched
    ]
    return {
        "since":           since.isoformat(),
        "n_total":         n_total,
        "n_in_sandy":      n_sandy,
        "n_in_dep_any":    n_dep_any,
        "n_in_dep_severe": n_dep_severe,
        "n_any_flood":     n_any_flood,
        "by_job_type":     dict(by_type.most_common()),
        "by_permit_status":dict(by_status.most_common()),
        "flagged_top":     flagged,
        "all_pins":        all_pins,
        "all_count":       n_total,
    }


def now_iso() -> str:
    return datetime.utcnow().date().isoformat()
