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

import math
from collections import Counter
from typing import Any
from urllib.parse import quote

import httpx

from riprap.core.pebbles._http import fetch_url_json
from riprap.core.pebbles.base import BasePebble, PebbleResult, SpatialQuery


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


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
        limit = int(cfg.get("limit", 500))
        sample_fields = cfg.get("sample_fields") or []
        count_by = cfg.get("count_by_field")
        extra_where = cfg.get("extra_where")
        order = cfg.get("order")
        cache_ttl_s = int(cfg.get("cache_ttl_s", 600))

        dlat = radius_m / 111_320.0
        dlon = radius_m / (111_320.0 * max(math.cos(math.radians(query.lat)), 1e-6))
        lat_min = query.lat - dlat
        lat_max = query.lat + dlat
        lon_min = query.lon - dlon
        lon_max = query.lon + dlon

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

        url = f"{ckan_base}/api/3/action/datastore_search_sql?sql={quote(sql)}"

        try:
            data = fetch_url_json(url, cache_ttl_s=cache_ttl_s, timeout_s=20.0)
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

        records = (data.get("result") or {}).get("records") or []

        refined: list[dict] = []
        for r in records:
            try:
                rlat = float(r.get(lat_field))
                rlon = float(r.get(lon_field))
            except (TypeError, ValueError):
                continue
            if _haversine_m(query.lat, query.lon, rlat, rlon) <= radius_m:
                refined.append(r)

        n = len(refined)
        sample_cap = int(cfg.get("sample_cap", 5))
        sample: list[dict] = []
        for r in refined[:sample_cap]:
            if sample_fields:
                sample.append({k: r.get(k) for k in sample_fields})
            else:
                sample.append(r)

        value: dict[str, Any] = {
            "n_records": n,
            "radius_m": radius_m,
            "sample": sample,
        }

        if count_by:
            counter = Counter(
                str(r.get(count_by) or "?").strip() or "?" for r in refined
            )
            top = [{"value": v, "count": c} for v, c in counter.most_common(5)]
            value[f"top_by_{count_by}"] = top

        return PebbleResult(pebble_id=self.id, value=value)
