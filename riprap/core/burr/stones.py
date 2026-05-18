"""Stone fan-out actions via Burr `MapActions`.

Each Stone (Cornerstone / Touchstone / Lodestone / Keystone) is a single
parent action in the top-level Application that fans out to its pebbles
in parallel, then reduces results back into one state.

The set of pebbles a Stone fans out to is read at call time from the
manifest registry — no hand-coded lists. Drop a YAML manifest with
`stone: cornerstone` and the next briefing run picks it up.

Capstone is **not** a MapActions — it's a sequential rag+reconcile+mellea
loop with its own iterate() halt condition, modelled as a sub-Application
(see capstone.py).
"""
from __future__ import annotations

from collections.abc import Generator, Iterable
from typing import Any

from burr.core import State
from burr.core.application import ApplicationContext
from burr.core.parallelism import MapActions

from riprap.core.burr.pebble import pebble_action
from riprap.core.pebbles import load_registry


def _pebbles_for(
    stone_id: str,
    deployment: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> list[str]:
    """Pebble ids for a stone, ordered by display.order (UI-friendly).

    Two-stage filter:
      1. Load the deployment's registry (which auto-merges federal pebbles).
      2. Per-pebble: keep only pebbles whose `coverage` contains the
         query point. Pebbles without a `coverage` block inherit their
         deployment's bbox (back-compat).

    `deployment` is a deployment directory name (e.g. `'boston'`) or a
    path. When None, falls back to `RIPRAP_DEPLOYMENT` env var.
    Sentinel `"__none__"` (set by `select_deployment` when no deployment
    covers the geocoded point) returns [].
    """
    import os
    from pathlib import Path

    from riprap.core.pebbles.deployments import deployment_by_name  # noqa: PLC0415
    if deployment == "__none__":
        # Out-of-coverage of every spatially-routed deployment. We
        # should still fire FEDERAL pebbles (NWS alerts, NWS obs) for
        # any in-CONUS point — those are national in scope and the
        # user expects an "active alerts" surface even in Albuquerque.
        # The per-pebble `fires_at` filter below catches out-of-CONUS
        # points (e.g. Tokyo) regardless.
        deployment = "federal"
    if deployment is None:
        deployment = os.environ.get("RIPRAP_DEPLOYMENT", "deployments/nyc")
    # Resolve: short name like 'nyc' → repo deployments/nyc; otherwise
    # treat as a path (env var legacy form `deployments/nyc`).
    dep = deployment_by_name(deployment)
    if dep is not None:
        p = dep.root
        deployment_bbox = dep.bbox
    else:
        p = Path(deployment)
        if not p.is_absolute():
            p = Path(__file__).resolve().parent.parent.parent.parent / deployment
        deployment_bbox = None
    if not p.exists() or not (p / "manifests").is_dir():
        return []
    reg = load_registry(p)
    pebbles = [pb for pb in reg.all() if pb.stone == stone_id]

    # Per-pebble coverage filter. Skip when we have no coords — the
    # union-of-writes path needs a complete list (it's lat/lon-blind),
    # and the empty-fan-out case is already handled by the __none__
    # sentinel above.
    if lat is not None and lon is not None:
        pebbles = [pb for pb in pebbles if pb.fires_at(lat, lon, deployment_bbox)]

    pebbles.sort(key=lambda pb: (
        pb.manifest.display.order if pb.manifest.display.order is not None else 999,
        pb.id,
    ))
    return [pb.id for pb in pebbles]


def _all_pebbles_for_stone(stone_id: str) -> list[str]:
    """Union of pebble ids for this stone across every spatially-routed
    deployment (i.e. those that declare a `coverage.bbox` in stones.yaml).

    Hazard-only deployments (heat, air) don't bbox-route — they're
    selected via the `RIPRAP_DEPLOYMENT` env var and never collide with
    place-based routing — so they're excluded from the union to keep
    the declared writes set tight.

    `writes` is read once at graph-build time, before any query lands,
    so it can't depend on the per-query deployment. The reducer fills
    any union-declared key that the active deployment didn't write with
    None so Burr's write-validation passes.

    Federal pebbles get auto-merged into every city deployment by
    `load_registry`, so the per-deployment listings already include
    them — no separate federal pass needed."""
    from riprap.core.pebbles.deployments import discover_deployments  # noqa: PLC0415
    seen: set[str] = set()
    for dep in discover_deployments():
        if dep.bbox is None:
            continue
        # lat/lon omitted → no per-pebble filter; the union spans
        # everything that COULD fire for this stone, regardless of
        # geocoded point. Coverage filtering happens at run time.
        seen.update(_pebbles_for(stone_id, dep.name))
    # Stable order keeps debug output reproducible.
    return sorted(seen)


class _StoneMapActions(MapActions):
    """Common base — concrete Stone classes set `stone_id` + `state_keys`.

    `state_keys` is the list of pebble-state-keys this Stone writes,
    declared to Burr via the `writes` property so transitions can chain
    on a single Stone action.
    """
    stone_id: str = ""

    @property
    def reads(self) -> list[str]:
        return ["lat", "lon", "deployment"]

    @property
    def writes(self) -> list[str]:
        # Union across deployments — see `_all_pebbles_for_stone`. The
        # per-query deployment subset is chosen at run time inside
        # `actions()`; unused pebble keys stay unset in state.
        return [*_all_pebbles_for_stone(self.stone_id), "trace"]

    def actions(
        self,
        state: State,
        inputs: dict[str, Any],  # noqa: ARG002 — Burr API signature
        context: ApplicationContext,  # noqa: ARG002 — Burr API signature
    ) -> Generator[Any, None, None]:
        # The pebble_action factory sets __name__ = f"pebble_{pid}", which
        # Burr picks up as the action name (no with_name() needed since
        # @action returns a plain function, not an Action object).
        deployment = state.get("deployment")
        lat = state.get("lat")
        lon = state.get("lon")
        for pid in _pebbles_for(self.stone_id, deployment, lat=lat, lon=lon):
            yield pebble_action(pid)

    def state(self, state: State, inputs: dict[str, Any]) -> State:  # noqa: ARG002 — Burr API signature
        # Each fan-out task starts with the same parent state slice:
        # lat, lon, and an empty trace (each task adds its own rec; the
        # reduce merges them back).
        return state.update(trace=[])

    def reduce(
        self,
        state: State,
        states: Iterable[State],
    ) -> State:
        """Merge each pebble's value + trace record back into one state."""
        accumulated_trace = list(state.get("trace", []))
        updates: dict[str, Any] = {}
        for s in states:
            # Each sub-state wrote its own pebble_id and a single-entry trace.
            for k in s.keys():
                if k == "trace":
                    accumulated_trace.extend(s["trace"])
                else:
                    # Only copy the keys this sub-task wrote — its own
                    # pebble key. Sub-state inherits the parent's read
                    # keys (lat/lon, deployment) unchanged; we don't
                    # want to write those back.
                    if k in ("lat", "lon", "deployment"):
                        continue
                    updates[k] = s[k]
        # Burr validates every declared `write` is present after reduce.
        # `writes` is the union across spatially-routed deployments; if
        # this run's deployment doesn't include a pebble, fill it with
        # None so the validator is satisfied.
        for declared in self.writes:
            if declared == "trace":
                continue
            if declared not in updates and state.get(declared) is None:
                updates[declared] = None
        return state.update(trace=accumulated_trace, **updates)


class CornerstoneAction(_StoneMapActions):
    """What NYC's ground remembers about flooding — hazard + history."""
    stone_id = "cornerstone"


class TouchstoneAction(_StoneMapActions):
    """The current state of the city's flood signals + live EO."""
    stone_id = "touchstone"


class LodestoneAction(_StoneMapActions):
    """Alerts + surge + recurrence forecasts (what's coming)."""
    stone_id = "lodestone"


class KeystoneAction(_StoneMapActions):
    """Exposed public assets + built fabric (what's at risk)."""
    stone_id = "keystone"
