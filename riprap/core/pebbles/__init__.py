"""Pebbles — atomic, manifest-declared data sources.

A pebble is one source (live API, baked geospatial file, model endpoint)
described by one YAML manifest in a deployment's manifests/ directory.

The public surface is intentionally small:

    from riprap.core.pebbles import load_registry, SpatialQuery

    reg = load_registry("deployments/nyc")
    result = reg.get("ida_hwm_2021").fetch(SpatialQuery(lat=40.7, lon=-74.0))
"""
from __future__ import annotations

from riprap.core.pebbles.base import Pebble, PebbleResult, SpatialQuery
from riprap.core.pebbles.registry import Registry, load_registry

__all__ = ["Pebble", "PebbleResult", "SpatialQuery", "Registry", "load_registry"]
