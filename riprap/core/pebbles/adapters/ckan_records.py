"""ckan_records — point-radius queries over any CKAN datastore resource.

CKAN powers the second-largest slice of US municipal open data after
Socrata: Boston (data.boston.gov), Philadelphia (opendataphilly.org),
plus most Canadian and EU portals. Unlike Socrata, CKAN datasets rarely
expose a uniform geo-typed field — they typically store latitude and
longitude as separate numeric columns. So this adapter does spatial
filtering in two steps: a bounding-box predicate pushed down into SQL,
then a haversine refine in Python to enforce the actual circle.

Manifest config:

  adapter: ckan_records
  config:
    ckan_base: https://data.boston.gov
    resource_id: 9d7c2214-4709-478a-a2e8-fb2020a5bb94
    lat_field: latitude
    lon_field: longitude
    radius_m: 300
    limit: 500                          # SQL LIMIT (pulled, then refined)
    sample_fields: [case_title, reason, type, open_dt, neighborhood]
    count_by_field: reason              # optional: top-N value counts
    extra_where: "case_status = 'Open'" # optional: AND-appended to SQL WHERE
    order: open_dt DESC
    cache_ttl_s: 600

Value payload (same shape as socrata_records, so reconcilers can be
adapter-agnostic):

  {
    "n_records":   int,                                 # after haversine refine
    "radius_m":    int,
    "sample":      [ {field: value, ...}, ... ]
    "top_by_<field>": [ {value: ..., count: ...}, ... ] # if count_by_field set
  }
"""
from __future__ import annotations

from collections import Counter
from typing import Any
from urllib.parse import quote

import httpx

from riprap.core.pebbles._geo import bbox_from_radius, haversine_m
from riprap.core.pebbles._http import fetch_url_json
from riprap.core.pebbles.base import BasePebble, PebbleResult, SpatialQuery


def _build_sql(
    resource_id: str,
    bbox: tuple[float, float, float, float],
    lat_field: str,
    lon_field: str,
    extra_where: str | None,
    order: str | None,
    limit: int,
) -> str:
    lat_min, lat_max, lon_min, lon_max = bbox
    where = (
        f'"{lat_field}" BETWEEN {lat_min} AND {lat_max} '
        f'AND "{lon_field}" BETWEEN {lon_min} AND {lon_max}'
    )
    if extra_where:
        where += f" AND ({extra_where})"
    sql = f'SELECT * FROM "{resource_id}" WHERE {where}'
    if order:
        sql += f" ORDER BY {order}"
    sql += f" LIMIT {limit}"
    return sql


def _refine_haversine(
    records: list[dict],
    query: SpatialQuery,
    lat_field: str,
    lon_field: str,
    radius_m: int,
) -> list[dict]:
    """Filter SQL bbox hits down to ones actually inside the radius circle.
    Drops rows whose lat/lon don't parse as floats."""
    out: list[dict] = []
    for r in records:
        try:
            rlat = float(r.get(lat_field))
            rlon = float(r.get(lon_field))
        except (TypeError, ValueError):
            continue
        if haversine_m(query.lat, query.lon, rlat, rlon) <= radius_m:
            out.append(r)
    return out


def _shape_sample(
    records: list[dict], sample_fields: list[str], sample_cap: int,
) -> list[dict]:
    if not sample_fields:
        return records[:sample_cap]
    return [{k: r.get(k) for k in sample_fields} for r in records[:sample_cap]]


def _top_by(records: list[dict], field: str, top_n: int = 5) -> list[dict]:
    counter = Counter(str(r.get(field) or "?").strip() or "?" for r in records)
    return [{"value": v, "count": c} for v, c in counter.most_common(top_n)]


class CKANRecordsPebble(BasePebble):
    def _fetch_raw(self, query: SpatialQuery) -> PebbleResult:
        cfg = self.manifest.config or {}
        ckan_base = (cfg.get("ckan_base") or "").rstrip("/")
        resource_id = cfg.get("resource_id")
        if not ckan_base or not resource_id:
            return PebbleResult(
                pebble_id=self.id, value=None,
                error="ckan_records: manifest.config.ckan_base and resource_id required",
            )
        if query.lat is None or query.lon is None:
            return PebbleResult(
                pebble_id=self.id, value=None,
                error="ckan_records: lat/lon required",
            )

        lat_field = cfg.get("lat_field", "latitude")
        lon_field = cfg.get("lon_field", "longitude")
        radius_m = int(cfg.get("radius_m", 500))
        sql_limit = int(cfg.get("limit", 500))

        sql = _build_sql(
            resource_id=resource_id,
            bbox=bbox_from_radius(query.lat, query.lon, radius_m),
            lat_field=lat_field, lon_field=lon_field,
            extra_where=cfg.get("extra_where"),
            order=cfg.get("order"),
            limit=sql_limit,
        )
        url = f"{ckan_base}/api/3/action/datastore_search_sql?sql={quote(sql)}"

        try:
            data = fetch_url_json(
                url, cache_ttl_s=int(cfg.get("cache_ttl_s", 600)), timeout_s=20.0,
            )
        except httpx.HTTPError as e:
            return PebbleResult(
                pebble_id=self.id, value=None, offline=True,
                error=f"ckan_records: HTTP error: {e}",
            )
        except Exception as e:  # noqa: BLE001
            return PebbleResult(
                pebble_id=self.id, value=None, offline=True,
                error=f"ckan_records: {type(e).__name__}: {e}",
            )

        if not isinstance(data, dict) or not data.get("success"):
            return PebbleResult(
                pebble_id=self.id, value=None,
                error=f"ckan_records: CKAN error: {(data or {}).get('error')}",
            )

        raw_rows = (data.get("result") or {}).get("records") or []
        refined = _refine_haversine(
            raw_rows, query, lat_field, lon_field, radius_m,
        )

        # When the SQL LIMIT capped the upstream pull, we don't know
        # the true count — surface as `n_truncated` so the briefing
        # narration + the card sub-line can show "N+ records" instead
        # of falsely claiming exact count "N".
        value: dict[str, Any] = {
            "n_records": len(refined),
            "n_truncated": len(raw_rows) >= sql_limit,
            "radius_m": radius_m,
            "sample": _shape_sample(
                refined, cfg.get("sample_fields") or [],
                int(cfg.get("sample_cap", 5)),
            ),
        }
        count_by = cfg.get("count_by_field")
        if count_by:
            value[f"top_by_{count_by}"] = _top_by(refined, count_by)

        return PebbleResult(pebble_id=self.id, value=value)
