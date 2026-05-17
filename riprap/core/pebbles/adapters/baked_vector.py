"""Generic baked-vector adapter — radius / contains queries over GeoJSON.

Covers a large fraction of pebbles whose source is a static vector file
shipped with the deployment (Ida HWMs, Sandy inundation polygons, NYCHA
developments, etc.).

Manifest config shape (all fields optional unless noted):

  config:
    path: data/ida_2021_hwms_ny.geojson   # required, relative to deployment root
    query:
      type: radius_point                  # radius_point | contains_point | nearest
      radius_m: 1000                      # required for radius_point
    feature_cap: 50                       # cap features included in result
    feature_properties:                   # which feature props to copy through
      - site_description
      - elev_ft
      - height_above_gnd
    aggregations:                         # declarative summary stats
      max_elev_ft:        {op: max, field: elev_ft}
      max_height_above_gnd_ft: {op: max, field: height_above_gnd}

Result payload shape (PebbleResult.value):

  {
    "n_within_radius": int,
    "radius_m": int,                      # echoed from config (radius_point only)
    "nearest": {                           # always populated when features exist
      "distance_m": float,
      "properties": {...},
    } | None,
    "features": [                          # capped, sorted by distance
      {"lat": ..., "lon": ..., "distance_m": ..., "properties": {...}}
    ],
    "aggregations": {key: value | None},
  }
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from typing import Any

from riprap.core.pebbles._http import fetch_url_text
from riprap.core.pebbles.base import BasePebble, PebbleResult, SpatialQuery


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _is_url(path_str: str) -> bool:
    return path_str.startswith("http://") or path_str.startswith("https://")


@lru_cache(maxsize=32)
def _load_features_local(path_str: str) -> tuple[dict, ...]:
    """Load and cache features from a local file path."""
    with open(path_str) as f:
        data = json.load(f)
    return tuple(data.get("features", []))


class _BakedVectorFetchError(Exception):
    """Raised on URL fetch / parse failure. The adapter catches this and
    returns an offline PebbleResult so a single dataset outage doesn't
    propagate as a 500 to the briefing pipeline."""


def _load_features(path_str: str, *, cache_ttl_s: int = 3600) -> tuple[dict, ...]:
    """Load GeoJSON features from a local path or http(s) URL.

    URL loads go through the shared HTTP cache (default 1 h TTL —
    geospatial layers usually update on a day-or-longer cadence).
    HTTP errors raise `_BakedVectorFetchError`; the caller turns that
    into an offline PebbleResult.
    """
    if _is_url(path_str):
        try:
            text = fetch_url_text(path_str, cache_ttl_s=cache_ttl_s)
            data = json.loads(text)
        except Exception as e:  # noqa: BLE001 — network / parse / status all fold into offline
            raise _BakedVectorFetchError(f"{type(e).__name__}: {e}") from e
        return tuple(data.get("features", []))
    return _load_features_local(path_str)


def _agg(op: str, values: list[float]) -> float | None:
    if not values:
        return None
    if op == "max":
        return max(values)
    if op == "min":
        return min(values)
    if op == "mean":
        return sum(values) / len(values)
    if op == "sum":
        return sum(values)
    if op == "count":
        return float(len(values))
    raise ValueError(f"unknown aggregation op: {op}")


class BakedVectorPebble(BasePebble):
    """Radius/contains queries over a static GeoJSON file."""

    def _fetch_raw(self, query: SpatialQuery) -> PebbleResult:
        cfg = self.manifest.config
        path_field = cfg.get("path")
        if not path_field:
            return PebbleResult(
                pebble_id=self.id, value=None,
                error="baked_vector: manifest.config.path is required",
            )
        if _is_url(path_field):
            path_str = path_field
        else:
            abs_path = self._resolve_path(path_field)
            if not abs_path.exists():
                return self._handle_missing(f"file not found: {abs_path}")
            path_str = str(abs_path)

        query_cfg = cfg.get("query") or {"type": "radius_point", "radius_m": 1000}
        qtype = query_cfg.get("type", "radius_point")

        if qtype == "radius_point":
            if query.lat is None or query.lon is None:
                return PebbleResult(
                    pebble_id=self.id, value=None,
                    error="radius_point query requires lat/lon",
                )
            radius_m = int(query.radius_m or query_cfg.get("radius_m") or 1000)
            return self._radius_query(path_str, query.lat, query.lon, radius_m, cfg)

        return PebbleResult(
            pebble_id=self.id, value=None,
            error=f"baked_vector: unsupported query type {qtype!r}",
        )

    def _handle_missing(self, msg: str) -> PebbleResult:
        on_offline = self.manifest.fallback.on_offline
        if on_offline == "error":
            return PebbleResult(pebble_id=self.id, value=None, error=msg)
        return PebbleResult(pebble_id=self.id, value=None, offline=True, error=msg)

    def _radius_query(self, path_str: str, lat: float, lon: float,
                      radius_m: int, cfg: dict[str, Any]) -> PebbleResult:
        try:
            feats = _load_features(path_str,
                                   cache_ttl_s=int(cfg.get("cache_ttl_s", 3600)))
        except _BakedVectorFetchError as e:
            # Single dataset outage — return offline rather than 500.
            return self._handle_missing(str(e))
        prop_keys: list[str] | None = cfg.get("feature_properties")
        cap = int(cfg.get("feature_cap", 50))

        in_radius: list[tuple[float, dict]] = []
        nearest: tuple[float, dict] | None = None
        for f in feats:
            geom = f.get("geometry") or {}
            if geom.get("type") != "Point":
                continue  # polygons land in a separate query type later
            flon, flat = geom["coordinates"][0], geom["coordinates"][1]
            d = _haversine_m(lat, lon, flat, flon)
            if nearest is None or d < nearest[0]:
                nearest = (d, f)
            if d <= radius_m:
                in_radius.append((d, f))

        in_radius.sort(key=lambda x: x[0])

        def _props(f: dict) -> dict:
            props = f.get("properties") or {}
            if prop_keys is None:
                return dict(props)
            return {k: props.get(k) for k in prop_keys}

        features_out: list[dict] = []
        for d, f in in_radius[:cap]:
            flon, flat = f["geometry"]["coordinates"][:2]
            features_out.append({
                "lat": flat,
                "lon": flon,
                "distance_m": round(d, 1),
                "properties": _props(f),
            })

        agg_cfg = cfg.get("aggregations") or {}
        aggregations: dict[str, float | None] = {}
        for agg_name, spec in agg_cfg.items():
            op = spec["op"]
            field = spec["field"]
            values = [
                (f.get("properties") or {}).get(field)
                for _, f in in_radius
            ]
            values_f = [float(v) for v in values if isinstance(v, (int, float))]
            aggregations[agg_name] = _agg(op, values_f)

        nearest_out: dict | None = None
        if nearest is not None:
            d, f = nearest
            nearest_out = {
                "distance_m": round(d, 1),
                "properties": _props(f),
            }

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
