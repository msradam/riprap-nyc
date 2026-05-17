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

    def _fetch_raw(self, query: SpatialQuery) -> PebbleResult:  # pragma: no cover
        raise NotImplementedError
