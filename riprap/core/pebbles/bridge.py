"""Bridge between the pebble registry and the legacy FSM.

Provides one helper, `fetch_pebble(pebble_id, lat, lon)`, that returns the
tuple `(value, trace_summary, err_msg)` matching the legacy FSM step
contract: a dict (or None) to write into state, a small renamed dict for
the SSE trace, and an error message if the fetch failed.

The registry is lazily loaded once on first access. The deployment dir
is `$RIPRAP_DEPLOYMENT` (default `deployments/nyc` relative to repo root).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from riprap.core.pebbles import SpatialQuery, load_registry
from riprap.core.pebbles.registry import Registry

_REGISTRY: Registry | None = None
# Per-deployment registry cache. Keyed by short name (`'nyc'`,
# `'boston'`, ...). Per-query routing needs to load whatever the
# router picked; a single global cache would re-introduce the
# cross-city leak fixed in 22de646.
_REGISTRIES: dict[str, Registry] = {}


def _repo_root() -> Path:
    # bridge.py -> pebbles -> core -> riprap -> repo root
    return Path(__file__).resolve().parent.parent.parent.parent


def get_registry(deployment: str | None = None) -> Registry:
    """Return the pebble registry for `deployment` (a short name like
    `'boston'`). When None, falls back to the `RIPRAP_DEPLOYMENT` env
    var and caches the result globally — back-compat for callers that
    pre-date per-query routing.

    Per-query callers pass `deployment` from `state.get("deployment")`;
    each deployment's registry is loaded once and cached.
    """
    # Out-of-coverage sentinel → federal: when no city covers a point,
    # we still want NWS / NOAA-level (federal) pebbles to fire, so map
    # the sentinel to the federal deployment's registry.
    if deployment == "__none__":
        deployment = "federal"
    if deployment:
        cached = _REGISTRIES.get(deployment)
        if cached is not None:
            return cached
        # Resolve `nyc` → deployments/nyc; also accept absolute paths.
        from riprap.core.pebbles.deployments import deployment_by_name
        dep = deployment_by_name(deployment)
        if dep is not None:
            reg = load_registry(dep.root)
        else:
            path = Path(deployment)
            if not path.is_absolute():
                path = _repo_root() / path
            reg = load_registry(path)
        _REGISTRIES[deployment] = reg
        return reg

    global _REGISTRY
    if _REGISTRY is None:
        dep_str = os.environ.get("RIPRAP_DEPLOYMENT", "deployments/nyc")
        path = Path(dep_str)
        if not path.is_absolute():
            path = _repo_root() / path
        _REGISTRY = load_registry(path)
    return _REGISTRY


def fetch_pebble(pebble_id: str, lat: float, lon: float,
                 extras: dict | None = None,
                 deployment: str | None = None) -> tuple[Any, dict, str | None]:
    """Run one pebble. Return (value_dict_for_state, trace_summary, err_msg).

    `value_dict_for_state` is None if the pebble was offline or errored.
    `trace_summary` is built from the manifest's `trace_summary:` block
    (empty dict if not declared). `err_msg` is set when an error or
    offline-fallback occurred.

    `extras` are passed into SpatialQuery.extras for adapters that need
    more context than lat/lon — text-mining pebbles need a search query
    string, dependent pebbles need an upstream pebble's value, etc.

    `deployment` is the short name from per-query routing (e.g.
    `'boston'`). When set, the pebble is looked up in that deployment's
    registry — so a Boston run finds `boston_311` even when the server's
    env var defaults to `nyc`.
    """
    reg = get_registry(deployment)
    pebble = reg.get(pebble_id)
    result = pebble.fetch(SpatialQuery(lat=lat, lon=lon, extras=extras or {}))

    if result.error is not None or result.value is None:
        return None, {}, result.error or "no value"

    value = result.value
    trace_map = pebble.manifest.trace_summary or {}
    trace_summary: dict = {}
    for tk, vk in trace_map.items():
        if vk == "__value__":
            trace_summary[tk] = value
        elif isinstance(value, dict):
            trace_summary[tk] = value.get(vk)
        else:
            trace_summary[tk] = None  # value isn't a dict; skip this lookup
    return value, trace_summary, None
