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


class _StonesFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stones: list[StoneManifest]


@dataclass
class StoneRegistry:
    stones: list[StoneManifest]

    def get(self, stone_id: str) -> StoneManifest:
        return next(s for s in self.stones if s.id == stone_id)

    def all(self) -> list[StoneManifest]:
        return sorted(self.stones, key=lambda s: s.order)

    def __contains__(self, stone_id: str) -> bool:
        return any(s.id == stone_id for s in self.stones)


def load_stones(deployment_root: str | Path) -> StoneRegistry:
    root = Path(deployment_root).resolve()
    path = root / "stones.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"no stones.yaml at {path}")
    with open(path) as f:
        raw = yaml.safe_load(f)
    parsed = _StonesFile.model_validate(raw)
    return StoneRegistry(stones=list(parsed.stones))
