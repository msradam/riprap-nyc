"""python_call — adapter that fetches a pebble by calling a Python function.

The manifest declares a module + function and how to build positional / keyword
args from the SpatialQuery. Many probes are best expressed as a Python function
that takes lat/lon (or a derived geometry) and returns a dict — this adapter is
how that surface plugs into the pebble layer.

Manifest config shape:

  adapter: python_call
  config:
    module: app.flood_layers.sandy_inundation
    function: inside_raster
    args:                     # positional, in order
      - {source: pt_2263}
    kwargs:                   # optional
      radius_m: {source: radius_m}
    on_none: offline          # how to treat function returning None:
                              #   offline (default) | empty_dict | passthrough
    inject:                   # optional; merged into result dict post-call
      radius_m: 600

Supported `source:` values:
  lat, lon            — query.lat / query.lon
  radius_m            — query.radius_m
  pt_2263             — shapely.Point in EPSG:2263 from lat/lon
  pt_4326             — shapely.Point in EPSG:4326 from lat/lon
  query               — the full SpatialQuery object

Constants: `{const: 800}`.
"""
from __future__ import annotations

import importlib
from functools import lru_cache
from typing import Any

from riprap.core.json_safe import to_json_safe as _to_json_safe  # noqa: PLC0415
from riprap.core.pebbles.base import BasePebble, PebbleResult, SpatialQuery


@lru_cache(maxsize=64)
def _load_callable(module_path: str, func_name: str):
    mod = importlib.import_module(module_path)
    return getattr(mod, func_name)


def _build_pt_2263(lat: float, lon: float):
    """Convert WGS84 lat/lon to a shapely Point in EPSG:2263. Imported lazily
    so the heavy geopandas/pyproj import only fires when a pebble needs it."""
    import geopandas as gpd  # noqa: PLC0415
    from shapely.geometry import Point  # noqa: PLC0415
    return (gpd.GeoDataFrame(geometry=[Point(lon, lat)], crs="EPSG:4326")
            .to_crs("EPSG:2263").iloc[0].geometry)


def _build_pt_4326(lat: float, lon: float):
    from shapely.geometry import Point  # noqa: PLC0415
    return Point(lon, lat)


def _resolve(spec: Any, query: SpatialQuery) -> Any:
    if not isinstance(spec, dict):
        return spec  # raw value, e.g. plain string
    if "const" in spec:
        return spec["const"]
    src = spec.get("source")
    if src == "lat":
        return query.lat
    if src == "lon":
        return query.lon
    if src == "radius_m":
        return query.radius_m
    if src == "pt_2263":
        return _build_pt_2263(query.lat, query.lon)
    if src == "pt_4326":
        return _build_pt_4326(query.lat, query.lon)
    if src == "query":
        return query
    raise ValueError(f"python_call: unknown source {src!r}")


class PythonCallPebble(BasePebble):
    def _fetch_raw(self, query: SpatialQuery) -> PebbleResult:
        cfg = self.manifest.config
        module_path = cfg.get("module")
        func_name = cfg.get("function")
        if not module_path or not func_name:
            return PebbleResult(
                pebble_id=self.id, value=None,
                error="python_call: module and function are required",
            )

        try:
            func = _load_callable(module_path, func_name)
        except (ImportError, AttributeError) as e:
            return PebbleResult(
                pebble_id=self.id, value=None,
                error=f"python_call: cannot resolve {module_path}.{func_name}: {e}",
            )

        try:
            args = [_resolve(a, query) for a in cfg.get("args", [])]
            kwargs = {k: _resolve(v, query) for k, v in (cfg.get("kwargs") or {}).items()}
        except Exception as e:  # noqa: BLE001
            return PebbleResult(
                pebble_id=self.id, value=None,
                error=f"python_call: arg resolution failed: {e}",
            )

        try:
            value = func(*args, **kwargs)
        except Exception as e:  # noqa: BLE001
            return PebbleResult(
                pebble_id=self.id, value=None,
                error=f"python_call: {func_name} raised: {e}",
            )

        if value is None:
            mode = cfg.get("on_none", "offline")
            if mode == "offline":
                return PebbleResult(
                    pebble_id=self.id, value=None, offline=True,
                    error=self.manifest.fallback.message,
                )
            if mode == "empty_dict":
                return PebbleResult(pebble_id=self.id, value={})
            # passthrough: return None as the value (shaper may handle it)
            return PebbleResult(pebble_id=self.id, value=None)

        # Auto-unwrap dataclasses + coerce numpy scalars/arrays so the
        # value is JSON-safe out of the box (legacy probes often return
        # dataclasses containing numpy floats from their underlying
        # raster / array math).
        value = _to_json_safe(value)

        # Merge literal extras declared in `config.inject` (handy for
        # constants the wrapped function doesn't include in its return,
        # e.g. floodnet's radius_m).
        inject = cfg.get("inject")
        if inject and isinstance(value, dict):
            value = {**value, **inject}

        return PebbleResult(pebble_id=self.id, value=value)
