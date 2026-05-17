"""Registry — discover, validate, and instantiate pebbles from a deployment.

Layout expected:

  deployments/<name>/
    manifests/*.yaml      # one pebble per file
    data/                 # adapter-relative file references resolve here
    corpus/               # rag pdfs (unused by registry directly)

The registry also merges **BYOD** (Bring Your Own Data) pebbles from two
optional sources, in this precedence order — later writers win:

  1. base deployment       deployments/<name>/manifests/*.yaml
  2. .riprap/ auto-discover ${CWD}/.riprap/**/*.yaml
  3. env var               RIPRAP_EXTRA_MANIFESTS=path1:path2:...
                           (each entry is a directory or a single .yaml file)

For BYOD pebbles, relative paths in the manifest (e.g. `path: my.csv`)
resolve against the *manifest file's directory*, not deployment_root —
so a user can ship a manifest + data side-by-side in any folder.

Usage:

  reg = load_registry("deployments/nyc")
  pebble = reg.get("ida_hwm_2021")
  pebble.fetch(SpatialQuery(lat=40.7, lon=-74.0))
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml
from pydantic import TypeAdapter

from riprap.core.pebbles.adapters import ADAPTERS
from riprap.core.pebbles.base import Pebble
from riprap.core.pebbles.schema import PebbleManifest
from riprap.core.pebbles.shapers import SHAPERS

_MANIFEST_ADAPTER = TypeAdapter(PebbleManifest)


class Registry:
    def __init__(self, deployment_root: Path, pebbles: dict[str, Pebble]) -> None:
        self.deployment_root = deployment_root
        self._pebbles = pebbles

    def get(self, pebble_id: str) -> Pebble:
        return self._pebbles[pebble_id]

    def all(self) -> list[Pebble]:
        return list(self._pebbles.values())

    def by_stone(self, stone: str) -> list[Pebble]:
        return [p for p in self._pebbles.values() if p.stone == stone]

    def ids(self) -> list[str]:
        return list(self._pebbles.keys())

    def __contains__(self, pebble_id: str) -> bool:
        return pebble_id in self._pebbles

    def __len__(self) -> int:
        return len(self._pebbles)


def _instantiate(
    yaml_path: Path,
    deployment_root: Path,
    *,
    manifest_dir: Path | None,
) -> tuple[str, Pebble]:
    """Load and instantiate one pebble from a manifest yaml. `manifest_dir`
    None for base-deployment pebbles (relative paths resolve to deployment_root)
    or set to the manifest's parent for BYOD pebbles."""
    with yaml_path.open() as f:
        raw = yaml.safe_load(f)
    manifest = _MANIFEST_ADAPTER.validate_python(raw)
    adapter_cls = ADAPTERS.get(manifest.adapter)
    if adapter_cls is None:
        raise ValueError(
            f"{yaml_path}: unknown adapter {manifest.adapter!r} "
            f"(known: {sorted(ADAPTERS)})"
        )
    shaper = None
    if manifest.shaper is not None:
        shaper = SHAPERS.get(manifest.shaper)
        if shaper is None:
            raise ValueError(
                f"{yaml_path}: unknown shaper {manifest.shaper!r} "
                f"(known: {sorted(SHAPERS)})"
            )
    pebble = adapter_cls(
        manifest, deployment_root, shaper=shaper, manifest_dir=manifest_dir,
    )
    return manifest.id, pebble


def _byod_yaml_sources() -> list[Path]:
    """Collect BYOD manifest paths from .riprap/ + RIPRAP_EXTRA_MANIFESTS, in load order."""
    out: list[Path] = []

    riprap_dir = Path.cwd() / ".riprap"
    if riprap_dir.is_dir():
        out.extend(sorted(riprap_dir.rglob("*.yaml")))

    extras = os.environ.get("RIPRAP_EXTRA_MANIFESTS", "").strip()
    if extras:
        for entry in extras.split(":"):
            entry = entry.strip()
            if not entry:
                continue
            p = Path(entry).resolve()
            if p.is_file() and p.suffix == ".yaml":
                out.append(p)
            elif p.is_dir():
                out.extend(sorted(p.glob("*.yaml")))
            else:
                print(f"[registry] RIPRAP_EXTRA_MANIFESTS entry not found: {p}", file=sys.stderr)

    return out


def _federal_manifests_dir() -> Path | None:
    """Path to deployments/federal/manifests/ if it exists.

    The federal directory holds pebbles whose data covers the whole US
    (NWS, NOAA, EPA) — one canonical manifest each, auto-merged into
    every spatially-routed deployment so we never duplicate them per
    city. Returns None when the directory is absent (e.g. tests pointing
    at a temp deployment root).
    """
    # registry.py → repo root is 4 levels up.
    repo = Path(__file__).resolve().parent.parent.parent.parent
    fed = repo / "deployments" / "federal" / "manifests"
    return fed if fed.is_dir() else None


def load_registry(deployment_root: str | Path) -> Registry:
    root = Path(deployment_root).resolve()
    manifests_dir = root / "manifests"
    if not manifests_dir.is_dir():
        raise FileNotFoundError(f"no manifests dir at {manifests_dir}")

    pebbles: dict[str, Pebble] = {}

    for yaml_path in sorted(manifests_dir.glob("*.yaml")):
        pid, pebble = _instantiate(yaml_path, root, manifest_dir=None)
        if pid in pebbles:
            raise ValueError(f"duplicate pebble id {pid!r} in {yaml_path.name}")
        pebbles[pid] = pebble

    # Auto-merge federal pebbles into every non-federal deployment.
    # A federal pebble carrying the same id as a base-deployment pebble
    # is treated as an override candidate, but in practice the deployment
    # owns the id (base-deployment pebbles win) so federal duplicates
    # are skipped silently. The federal directory itself doesn't trigger
    # a recursive merge.
    fed_dir = _federal_manifests_dir()
    if fed_dir is not None and fed_dir.resolve() != manifests_dir.resolve():
        for yaml_path in sorted(fed_dir.glob("*.yaml")):
            pid, pebble = _instantiate(yaml_path, root, manifest_dir=None)
            if pid in pebbles:
                continue  # deployment-owned pebble of the same id wins
            pebbles[pid] = pebble

    for yaml_path in _byod_yaml_sources():
        pid, pebble = _instantiate(yaml_path, root, manifest_dir=yaml_path.parent)
        if pid in pebbles:
            print(
                f"[registry] BYOD override: pebble {pid!r} from {yaml_path} "
                f"shadows base deployment manifest",
                file=sys.stderr,
            )
        pebbles[pid] = pebble

    return Registry(root, pebbles)
