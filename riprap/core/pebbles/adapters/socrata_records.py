"""socrata_records — point-radius queries over any Socrata SODA endpoint.

Socrata is the most common US municipal open-data platform — NYC, Chicago,
Seattle, LA, DC, SF, and several others use it. All speak the same SODA
API: same query syntax (`$where`, `$limit`, `$order`), same JSON output,
same `within_circle(location, lat, lon, m)` spatial filter.

This adapter is what makes a Riprap deployment portable across Socrata
cities. The manifest declares the resource URL, the spatial-field name
(`location` is the Socrata default, but some datasets use `point` or
`the_geom`), and a small projection of which fields to include in the
result + which fields to count.

Manifest config:

  adapter: socrata_records
  config:
    base_url: https://data.cityofchicago.org/resource/v6vf-nfxy.json
    radius_m: 500
    location_field: location           # Socrata field name for the point
    limit: 200                         # max records to pull per query
    sample_fields: [sr_type, created_date, status]
    count_by_field: sr_type            # optional: top-N value counts
    extra_where: "status = 'Open'"     # optional: AND-appended to the $where
    cache_ttl_s: 600

Value payload:

  {
    "n_records":   int,
    "radius_m":    int,
    "sample":      [ {field: value, ...}, ... ]   # up to N records
    "top_by_<field>": [ {value: ..., count: ...}, ... ]   # if count_by_field set
  }
"""
from __future__ import annotations

from collections import Counter
from typing import Any

import httpx

from riprap.core.pebbles._http import fetch_url_json
from riprap.core.pebbles.base import BasePebble, PebbleResult, SpatialQuery


class SocrataRecordsPebble(BasePebble):
    def _fetch_raw(self, query: SpatialQuery) -> PebbleResult:
        cfg = self.manifest.config or {}
        base_url = cfg.get("base_url")
        if not base_url:
            return PebbleResult(
                pebble_id=self.id, value=None,
                error="socrata_records: manifest.config.base_url is required",
            )
        if query.lat is None or query.lon is None:
            return PebbleResult(
                pebble_id=self.id, value=None,
                error="socrata_records: lat/lon required",
            )

        radius_m = int(cfg.get("radius_m", 500))
        loc_field = cfg.get("location_field", "location")
        limit = int(cfg.get("limit", 200))
        sample_fields = cfg.get("sample_fields") or []
        count_by = cfg.get("count_by_field")
        extra_where = cfg.get("extra_where")
        cache_ttl_s = int(cfg.get("cache_ttl_s", 600))

        where = f"within_circle({loc_field},{query.lat},{query.lon},{radius_m})"
        if extra_where:
            where += f" AND {extra_where}"

        params = {
            "$where": where,
            "$limit": str(limit),
        }
        # Some datasets have a `created_date` we can sort newest-first; the
        # manifest can override via `extra_order`.
        order = cfg.get("order")
        if order:
            params["$order"] = order

        try:
            url = base_url + "?" + "&".join(f"{k}={v}" for k, v in params.items())
            data = fetch_url_json(url, cache_ttl_s=cache_ttl_s, timeout_s=15.0)
        except httpx.HTTPError as e:
            return PebbleResult(
                pebble_id=self.id, value=None, offline=True,
                error=f"socrata_records: HTTP error: {e}",
            )
        except Exception as e:  # noqa: BLE001
            return PebbleResult(
                pebble_id=self.id, value=None, offline=True,
                error=f"socrata_records: {type(e).__name__}: {e}",
            )

        if not isinstance(data, list):
            return PebbleResult(
                pebble_id=self.id, value=None,
                error=f"socrata_records: expected list, got {type(data).__name__}",
            )

        records: list[dict] = data
        n = len(records)
        sample_cap = int(cfg.get("sample_cap", 5))
        sample: list[dict] = []
        for r in records[:sample_cap]:
            if sample_fields:
                sample.append({k: r.get(k) for k in sample_fields})
            else:
                sample.append(r)

        # Honest cap surfacing: the Socrata API truncates at $limit;
        # when n equals the configured cap, the briefing should say
        # "200+ records" not "200 records" since there may be more we
        # didn't fetch. Surface as a boolean so the UI can append the
        # "+" suffix and the narration can distinguish exact from
        # truncated counts.
        limit_was_hit = n >= limit
        value: dict[str, Any] = {
            "n_records": n,
            "n_truncated": limit_was_hit,
            "radius_m": radius_m,
            "sample": sample,
        }

        if count_by:
            counter = Counter(str(r.get(count_by) or "?") for r in records)
            top = [{"value": v, "count": c} for v, c in counter.most_common(5)]
            value[f"top_by_{count_by}"] = top

        return PebbleResult(pebble_id=self.id, value=value)
