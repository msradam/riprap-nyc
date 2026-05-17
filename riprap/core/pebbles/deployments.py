"""Deployment discovery + per-query routing.

Every deployment under `deployments/` carries a `stones.yaml` with an
optional top-level `coverage:` block declaring its bbox + city/state:

  coverage:
    bbox: [min_lon, min_lat, max_lon, max_lat]  # WGS84
    city: New York City
    state: NY

When a query is geocoded, `pick_deployment(lat, lon)` picks the deployment
whose bbox contains the resolved point. That deployment's manifest set is
the one that fans out for the run — so a Boston query never fires NYC's
`ida_hwm` pebble, regardless of which deployment the server happened to
boot with as its default.

Falls back to `None` when no deployment covers the point; the caller is
responsible for short-circuiting the briefing to a "not covered yet"
response in that case.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Deployment:
    name: str                    # 'nyc', 'boston', ...
    root: Path                   # absolute path to deployments/<name>/
    bbox: tuple[float, float, float, float] | None  # (min_lon, min_lat, max_lon, max_lat)
    city: str | None
    state: str | None

    def contains(self, lat: float, lon: float) -> bool:
        if self.bbox is None:
            return False
        min_lon, min_lat, max_lon, max_lat = self.bbox
        return (min_lat <= lat <= max_lat) and (min_lon <= lon <= max_lon)


def _repo_root() -> Path:
    # riprap/core/pebbles/deployments.py → repo root is 4 levels up
    return Path(__file__).resolve().parent.parent.parent.parent


@lru_cache(maxsize=1)
def discover_deployments() -> tuple[Deployment, ...]:
    """Scan `deployments/` for stones.yaml and parse the coverage block.

    Cached: deployments are scanned once per process. Tests that need to
    refresh after writing new manifests can call `discover_deployments.cache_clear()`.
    """
    root = _repo_root() / "deployments"
    if not root.is_dir():
        return ()
    out: list[Deployment] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        stones_yaml = child / "stones.yaml"
        if not stones_yaml.is_file():
            continue
        try:
            data = yaml.safe_load(stones_yaml.read_text())
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict):
            continue
        cov = data.get("coverage") or {}
        bbox_raw = cov.get("bbox")
        bbox = None
        if (isinstance(bbox_raw, list) and len(bbox_raw) == 4
                and all(isinstance(v, (int, float)) for v in bbox_raw)):
            bbox = (float(bbox_raw[0]), float(bbox_raw[1]),
                    float(bbox_raw[2]), float(bbox_raw[3]))
        out.append(Deployment(
            name=child.name,
            root=child.resolve(),
            bbox=bbox,
            city=cov.get("city"),
            state=cov.get("state"),
        ))
    return tuple(out)


def pick_deployment(lat: float | None, lon: float | None) -> Deployment | None:
    """Return the deployment whose bbox contains the point, else None.

    With overlapping bboxes (won't happen for our five shipped cities,
    but is theoretically possible for a custom site), the first match in
    discovery order wins. Discovery order is alphabetical by directory
    name — deterministic across machines.
    """
    if lat is None or lon is None:
        return None
    for dep in discover_deployments():
        if dep.contains(lat, lon):
            return dep
    return None


def deployment_by_name(name: str) -> Deployment | None:
    """Lookup a deployment by its directory name (e.g. 'nyc')."""
    for dep in discover_deployments():
        if dep.name == name:
            return dep
    return None
