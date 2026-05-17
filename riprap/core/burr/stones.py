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


# Module-level registry handle. The pebble registry itself caches its
# manifests via a module-level singleton (`bridge._REGISTRY`), so the
# load here is cheap on the first call and free after.
def _pebbles_for(stone_id: str) -> list[str]:
    """Pebble ids for a stone, ordered by display.order (UI-friendly).

    Reads the same `RIPRAP_DEPLOYMENT` deployment dir as the rest of the
    runtime so a single env var swaps stones + pebbles atomically."""
    import os
    from pathlib import Path
    deployment = os.environ.get("RIPRAP_DEPLOYMENT", "deployments/nyc")
    p = Path(deployment)
    if not p.is_absolute():
        # Resolve relative to repo root (4 levels up from this file).
        p = Path(__file__).resolve().parent.parent.parent.parent / deployment
    reg = load_registry(p)
    pebbles = [pb for pb in reg.all() if pb.stone == stone_id]
    pebbles.sort(key=lambda pb: (
        pb.manifest.display.order if pb.manifest.display.order is not None else 999,
        pb.id,
    ))
    return [pb.id for pb in pebbles]


class _StoneMapActions(MapActions):
    """Common base — concrete Stone classes set `stone_id` + `state_keys`.

    `state_keys` is the list of pebble-state-keys this Stone writes,
    declared to Burr via the `writes` property so transitions can chain
    on a single Stone action.
    """
    stone_id: str = ""

    @property
    def reads(self) -> list[str]:
        return ["lat", "lon"]

    @property
    def writes(self) -> list[str]:
        # Pebble ids (state keys) + the shared trace list.
        return [*_pebbles_for(self.stone_id), "trace"]

    def actions(
        self,
        state: State,
        inputs: dict[str, Any],
        context: ApplicationContext,
    ) -> Generator[Any, None, None]:
        # The pebble_action factory sets __name__ = f"pebble_{pid}", which
        # Burr picks up as the action name (no with_name() needed since
        # @action returns a plain function, not an Action object).
        for pid in _pebbles_for(self.stone_id):
            yield pebble_action(pid)

    def state(self, state: State, inputs: dict[str, Any]) -> State:
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
                    # keys (lat/lon) unchanged; we don't want to write
                    # those back.
                    if k in ("lat", "lon"):
                        continue
                    updates[k] = s[k]
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
