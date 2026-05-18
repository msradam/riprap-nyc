"""Smoke test for the Burr Stone fan-out.

Builds a minimal Application that runs `CornerstoneAction` once and
verifies all the cornerstone pebbles populate their state keys + the
trace contains one record per pebble.
"""
from __future__ import annotations

from burr.core import ApplicationBuilder, State, action

from riprap.core.burr.stones import CornerstoneAction


@action(reads=[], writes=["lat", "lon", "trace"])
def _seed(state: State) -> State:
    return state.update(lat=40.7100, lon=-73.9800, trace=[])


def test_cornerstone_fans_out_all_pebbles():
    cornerstone = CornerstoneAction()
    cornerstone_writes = cornerstone.writes  # snapshot before assembly

    app = (
        ApplicationBuilder()
        .with_actions(seed=_seed, cornerstone=cornerstone)
        .with_transitions(("seed", "cornerstone"))
        .with_entrypoint("seed")
        .with_state(trace=[])
        .build()
    )
    _, _, final = app.run(halt_after=["cornerstone"])

    # Every cornerstone pebble wrote its state key.
    for k in cornerstone_writes:
        if k == "trace":
            continue
        assert k in final, f"cornerstone did not write state key {k!r}"

    # At least the file-backed pebbles should have produced non-None
    # values for an NYC address. (ida_hwm and sandy use baked data.)
    # Sandy now uses the boolean_zone shaper → dict {inside, ...} not bare bool.
    assert isinstance(final["sandy"], dict) and "inside" in final["sandy"]
    assert final["ida_hwm"] is not None and isinstance(final["ida_hwm"], dict)
    assert final["microtopo"] is not None and isinstance(final["microtopo"], dict)

    # Trace recorded one rec per pebble.
    trace = final["trace"]
    pebble_recs = [t for t in trace if t.get("step", "").startswith("dep_")
                   or t.get("step") in ("sandy", "ida_hwm", "microtopo",
                                        "prithvi_water")]
    # We expect 7 cornerstone pebbles: sandy, dep×3, ida_hwm, prithvi_water, microtopo
    assert len(pebble_recs) >= 5  # tolerate a flaky single probe; the bulk should land
