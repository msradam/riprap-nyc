"""csv_points — radius queries over a CSV with declared lat/lon columns.

The BYOD path for tabular point data. Drop a CSV (local or URL), declare
which columns are lat/lon, get the same query + aggregation surface as
baked_vector.

Manifest config shape:

  adapter: csv_points
  config:
    path: incidents.csv             # local path or http(s) URL
    lat_col: latitude
    lon_col: longitude
    query:
      type: radius_point
      radius_m: 500
    feature_cap: 50
    feature_properties:             # which columns to include in result
      - severity
      - reported_at
    aggregations:
      max_severity: {op: max, field: severity}
    cache_ttl_s: 3600               # for URL paths only
    delimiter: ","                  # optional
    encoding: "utf-8"               # optional
"""
from __future__ import annotations

import csv
import io
import math
from functools import lru_cache
from typing import Any

from riprap.core.pebbles._http import fetch_url_text
from riprap.core.pebbles.base import BasePebble, PebbleResult, SpatialQuery


def _is_url(path_str: str) -> bool:
    return path_str.startswith("http://") or path_str.startswith("https://")


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _agg(op: str, values: list[float]) -> float | None:
    if not values:
        return None
    if op == "max":   return max(values)
    if op == "min":   return min(values)
    if op == "mean":  return sum(values) / len(values)
    if op == "sum":   return sum(values)
    if op == "count": return float(len(values))
    raise ValueError(f"csv_points: unknown aggregation op: {op}")


@lru_cache(maxsize=32)
def _read_csv_local(path_str: str, delimiter: str, encoding: str) -> tuple[dict, ...]:
    with open(path_str, encoding=encoding, newline="") as f:
        rows = tuple(csv.DictReader(f, delimiter=delimiter))
    return rows


def _read_csv(path_str: str, *, delimiter: str = ",", encoding: str = "utf-8",
              cache_ttl_s: int = 3600) -> tuple[dict, ...]:
    if _is_url(path_str):
        text = fetch_url_text(path_str, cache_ttl_s=cache_ttl_s)
        return tuple(csv.DictReader(io.StringIO(text), delimiter=delimiter))
    return _read_csv_local(path_str, delimiter, encoding)


def _coerce_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class CSVPointsPebble(BasePebble):
    def _fetch_raw(self, query: SpatialQuery) -> PebbleResult:
        cfg = self.manifest.config
        path_field = cfg.get("path")
        lat_col = cfg.get("lat_col", "lat")
        lon_col = cfg.get("lon_col", "lon")
        if not path_field:
            return PebbleResult(
                pebble_id=self.id, value=None,
                error="csv_points: manifest.config.path is required",
            )

        if _is_url(path_field):
            path_str = path_field
        else:
            abs_path = self._resolve_path(path_field)
            if not abs_path.exists():
                msg = f"csv not found: {abs_path}"
                return PebbleResult(pebble_id=self.id, value=None, offline=True, error=msg)
            path_str = str(abs_path)

        query_cfg = cfg.get("query") or {"type": "radius_point", "radius_m": 1000}
        qtype = query_cfg.get("type", "radius_point")

        if qtype != "radius_point":
            return PebbleResult(
                pebble_id=self.id, value=None,
                error=f"csv_points: unsupported query type {qtype!r}",
            )
        if query.lat is None or query.lon is None:
            return PebbleResult(
                pebble_id=self.id, value=None,
                error="radius_point query requires lat/lon",
            )
        radius_m = int(query.radius_m or query_cfg.get("radius_m") or 1000)

        rows = _read_csv(
            path_str,
            delimiter=cfg.get("delimiter", ","),
            encoding=cfg.get("encoding", "utf-8"),
            cache_ttl_s=int(cfg.get("cache_ttl_s", 3600)),
        )

        prop_keys: list[str] | None = cfg.get("feature_properties")
        cap = int(cfg.get("feature_cap", 50))

        in_radius: list[tuple[float, dict]] = []
        nearest: tuple[float, dict] | None = None
        for row in rows:
            flat = _coerce_float(row.get(lat_col))
            flon = _coerce_float(row.get(lon_col))
            if flat is None or flon is None:
                continue
            d = _haversine_m(query.lat, query.lon, flat, flon)
            if nearest is None or d < nearest[0]:
                nearest = (d, row)
            if d <= radius_m:
                in_radius.append((d, row))

        in_radius.sort(key=lambda x: x[0])

        def _props(row: dict) -> dict:
            if prop_keys is None:
                return {k: v for k, v in row.items() if k not in (lat_col, lon_col)}
            return {k: row.get(k) for k in prop_keys}

        features_out: list[dict] = []
        for d, row in in_radius[:cap]:
            features_out.append({
                "lat": _coerce_float(row.get(lat_col)),
                "lon": _coerce_float(row.get(lon_col)),
                "distance_m": round(d, 1),
                "properties": _props(row),
            })

        aggregations: dict[str, float | None] = {}
        for agg_name, spec in (cfg.get("aggregations") or {}).items():
            op = spec["op"]
            field = spec["field"]
            values = [_coerce_float(r.get(field)) for _, r in in_radius]
            aggregations[agg_name] = _agg(op, [v for v in values if v is not None])

        nearest_out: dict | None = None
        if nearest is not None:
            d, row = nearest
            nearest_out = {"distance_m": round(d, 1), "properties": _props(row)}

        return PebbleResult(
            pebble_id=self.id,
            value={
                "n_within_radius": len(in_radius),
                "radius_m": radius_m,
                "nearest": nearest_out,
                "features": features_out,
                "aggregations": aggregations,
            },
        )
