"""Stones — curatorial bundles of pebbles.

A stone is declared in `deployments/<name>/stones.yaml`. Each pebble manifest
references one of these by id (`stone: cornerstone`). The frontend renders
each stone as a row of evidence cards (one card per pebble), in `order`.

Public surface:

    from riprap.core.stones import load_stones

    stones = load_stones("deployments/nyc")
    for s in stones.all():
        print(s.id, s.name, s.tagline)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class StoneManifest(BaseModel):
    """One entry in stones.yaml."""
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    name: str
    tagline: str
    description: str
    order: int = 100  # bigger = lower in the UI


class DeploymentDescriptor(BaseModel):
    """Optional top-level block in stones.yaml carrying the human-readable
    deployment descriptors the UI shell renders in the chip + page title:

        deployment:
          city: Boston                 # for the chip pill / browser title
          hazard: Flood-exposure briefing   # for the chip text on app pages

    Both are optional; load_stones() fills sensible defaults when the
    block is missing or partial. The default city is derived from the
    deployment directory name (`deployments/<name>/`); the default
    hazard is `Flood-exposure briefing`.
    """
    model_config = ConfigDict(extra="forbid")

    city: str | None = None
    hazard: str | None = None


class CoverageDescriptor(BaseModel):
    """Optional top-level block declaring this deployment's spatial
    coverage. Used by `riprap.core.pebbles.deployments.pick_deployment`
    to route each query to the deployment whose bbox contains the
    geocoded point — so a Boston query never fires NYC's `ida_hwm`."""
    model_config = ConfigDict(extra="forbid")
    bbox: list[float] | None = None  # [min_lon, min_lat, max_lon, max_lat]
    city: str | None = None
    state: str | None = None


class _StonesFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    deployment: DeploymentDescriptor = Field(default_factory=DeploymentDescriptor)
    coverage: CoverageDescriptor = Field(default_factory=CoverageDescriptor)
    stones: list[StoneManifest]


@dataclass
class StoneRegistry:
    stones: list[StoneManifest]
    city: str
    hazard: str

    def get(self, stone_id: str) -> StoneManifest:
        return next(s for s in self.stones if s.id == stone_id)

    def all(self) -> list[StoneManifest]:
        return sorted(self.stones, key=lambda s: s.order)

    def __contains__(self, stone_id: str) -> bool:
        return any(s.id == stone_id for s in self.stones)


# Casing overrides for the deployment-dir → display-name fallback.
# Most cities are correctly title-cased (`chicago` → `Chicago`); a few
# need explicit casing the simple `.title()` can't produce.
_CITY_FALLBACK = {
    "nyc": "NYC",
    "sf": "San Francisco",
    "la": "Los Angeles",
    "dc": "Washington, DC",
    "heat": "NYC",  # heat + air are NYC-scoped hazards
    "air": "NYC",
    "pi": "NYC",
}

_HAZARD_FALLBACK = {
    "heat": "Heat-exposure briefing",
    "air": "Air-quality briefing",
}


def load_stones(deployment_root: str | Path) -> StoneRegistry:
    root = Path(deployment_root).resolve()
    path = root / "stones.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"no stones.yaml at {path}")
    with path.open() as f:
        raw = yaml.safe_load(f)
    parsed = _StonesFile.model_validate(raw)

    dep_name = root.name.lower()
    city = parsed.deployment.city or _CITY_FALLBACK.get(dep_name, root.name.title())
    hazard = parsed.deployment.hazard or _HAZARD_FALLBACK.get(dep_name, "Flood-exposure briefing")

    return StoneRegistry(stones=list(parsed.stones), city=city, hazard=hazard)
