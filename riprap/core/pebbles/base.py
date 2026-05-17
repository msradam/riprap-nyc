"""Pebble runtime types — the Protocol every adapter implements.

A Pebble is constructed once at registry-load time with its parsed manifest
and a `deployment_root` Path. `fetch(query)` is the hot path; it must be
cheap to call repeatedly (adapters cache their own data where appropriate).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from riprap.core.pebbles.schema import PebbleManifest


@dataclass(frozen=True)
class SpatialQuery:
    """The input to every pebble. `lat`/`lon` are always WGS84.

    `radius_m` is a hint; adapters may interpret or ignore it. Polygon
    queries pass `geometry_wkt` (well-known text) and leave point fields
    None.
    """
    lat: float | None = None
    lon: float | None = None
    radius_m: int | None = None
    geometry_wkt: str | None = None  # for polygon-scope queries
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class PebbleResult:
    """A pebble's fetched output.

    `value` carries the adapter-shaped payload (a dict; never a custom
    class — the downstream reconciler must be able to JSON-serialize it).
    `offline` is True when the source was unreachable AND `fallback.on_offline`
    was `skip` or `stub` — the briefing layer will omit or stub the entry.
    """
    pebble_id: str
    value: Any  # adapter-shaped; usually dict, but scalar pebbles return bool/float/list/etc.
    offline: bool = False
    error: str | None = None
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@runtime_checkable
class Pebble(Protocol):
    """The protocol every adapter satisfies.

    Adapters typically subclass a small `BasePebble` (in each adapter
    module) that stores `manifest` and `deployment_root` for them.
    """
    manifest: PebbleManifest
    deployment_root: Path

    @property
    def id(self) -> str: ...
    @property
    def stone(self) -> str: ...

    def fetch(self, query: SpatialQuery) -> PebbleResult: ...


class BasePebble:
    """Mixin every adapter inherits — stores manifest + root, exposes id/stone.

    Concrete adapters override `_fetch_raw(query)`. `fetch(query)` is the
    public entry that wraps `_fetch_raw` with shaper application so the
    shaper logic lives in one place.
    """

    def __init__(self, manifest: PebbleManifest, deployment_root: Path,
                 shaper=None, manifest_dir: Path | None = None) -> None:
        self.manifest = manifest
        self.deployment_root = deployment_root
        # For base deployment pebbles, manifest_dir is None and relative
        # paths resolve against deployment_root (preserving prior layout
        # like `data/foo.tif`). For BYOD pebbles loaded from .riprap/ or
        # RIPRAP_EXTRA_MANIFESTS, manifest_dir is the directory holding
        # the manifest, and relative paths resolve there — so a user can
        # ship a manifest + CSV side-by-side without knowing anything
        # about the host deployment layout.
        self.manifest_dir = manifest_dir
        self._shaper = shaper  # Callable[[dict|None], dict|None] | None

    @property
    def id(self) -> str:
        return self.manifest.id

    @property
    def stone(self) -> str:
        return self.manifest.stone

    def _resolve_path(self, rel_or_abs: str) -> Path:
        """Resolve a manifest path against manifest_dir (BYOD) or
        deployment_root (base) if relative."""
        p = Path(rel_or_abs)
        if p.is_absolute():
            return p
        base = self.manifest_dir if self.manifest_dir is not None else self.deployment_root
        return (base / p).resolve()

    def fetch(self, query: SpatialQuery) -> PebbleResult:
        result = self._fetch_raw(query)
        if self._shaper is not None and result.value is not None:
            result.value = self._shaper(result.value, self.manifest)
        return result

    @property
    def fallback(self):
        return self.manifest.fallback

    def fires_at(self, lat: float | None, lon: float | None,
                 deployment_bbox: tuple[float, float, float, float] | None = None) -> bool:
        """Does this pebble's coverage contain the geocoded point?

        Resolution order:
          1. Manifest-declared `coverage`:
               region: us_conus → CONUS bbox
               region: global   → always True
               bbox: [...]      → bbox containment
          2. Otherwise inherit the deployment's bbox (back-compat path —
             every existing manifest works unchanged).
          3. If neither is set, fall back to True (assume nationwide).

        None for lat/lon means geocode failed → False (don't fire).
        """
        if lat is None or lon is None:
            return False
        cov = self.manifest.coverage
        if cov is not None:
            if cov.region == "global":
                return True
            if cov.region == "us_conus":
                # CONUS lower-48 bbox (excludes AK + HI by design).
                min_lon, min_lat, max_lon, max_lat = -125.0, 24.5, -66.9, 49.4
                return (min_lat <= lat <= max_lat) and (min_lon <= lon <= max_lon)
            if cov.bbox is not None and len(cov.bbox) == 4:
                min_lon, min_lat, max_lon, max_lat = cov.bbox
                return (min_lat <= lat <= max_lat) and (min_lon <= lon <= max_lon)
        if deployment_bbox is not None:
            min_lon, min_lat, max_lon, max_lat = deployment_bbox
            return (min_lat <= lat <= max_lat) and (min_lon <= lon <= max_lon)
        return True

    def _fetch_raw(self, query: SpatialQuery) -> PebbleResult:  # pragma: no cover
        raise NotImplementedError
