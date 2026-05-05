"""Unit tests for the Stones taxonomy layer.

Pure-import tests; no server / FSM required. Each data-Stone exposes
`NAME`, `TAGLINE`, `DESCRIPTION`, `SOURCES`, `collect()`. The SOURCES
keys must be a subset of the FSM's actual state keys so the migration
stays honest as new specialists land.

Some SOURCES entries are forward-looking (state keys added by later
commits in the migration). Those are explicitly listed in
`FUTURE_STATE_KEYS` and skipped from the validity check.
"""
from __future__ import annotations

import inspect
import re

from app import fsm
from app.stones import (
    ALL_STONES,
    DATA_STONES,
    capstone,
    cornerstone,
    keystone,
    lodestone,
    touchstone,
)

# State keys added by later migration commits (C4 / C5 / C6). The Stones
# taxonomy is allowed to declare them up-front so the SOURCES list stays
# stable as the specialists land.
FUTURE_STATE_KEYS = {
    "terramind_buildings",  # commit 4
    "terramind_lulc",       # commit 4
    "ttm_battery_surge",    # commit 6
}


def _fsm_state_keys() -> set[str]:
    """Scrape every state key written by an @action in app/fsm.py.

    We don't import every action to introspect — Burr's @action wraps
    the function so the `writes` declaration isn't readable on the
    decorated object without instantiating an Application. The cheapest
    reliable read is regex over the module source.
    """
    src = inspect.getsource(fsm)
    keys: set[str] = set()
    # @action(reads=[...], writes=["k1", "k2", ...])
    for m in re.finditer(r"writes\s*=\s*\[([^\]]+)\]", src):
        for tok in re.findall(r'"([^"]+)"', m.group(1)):
            keys.add(tok)
    return keys


def test_data_stones_have_required_attrs():
    for st in DATA_STONES:
        assert isinstance(st.NAME, str) and st.NAME
        assert isinstance(st.TAGLINE, str) and st.TAGLINE
        assert isinstance(st.DESCRIPTION, str) and st.DESCRIPTION
        assert isinstance(st.SOURCES, list) and st.SOURCES
        assert callable(st.collect)


def test_capstone_has_required_attrs():
    assert capstone.NAME == "Capstone"
    assert capstone.TAGLINE
    assert capstone.DESCRIPTION
    # Capstone re-exports the reconciler.
    assert callable(capstone.build_documents)
    assert callable(capstone.run)
    assert isinstance(capstone.EXTRA_SYSTEM_PROMPT, str)


def test_data_stone_sources_are_valid_state_keys():
    fsm_keys = _fsm_state_keys()
    # Sanity: a couple of well-known keys really do appear.
    for required in ("sandy", "dep", "floodnet", "nyc311", "ida_hwm"):
        assert required in fsm_keys, f"FSM scrape missed {required!r}"
    for st in DATA_STONES:
        for key in st.SOURCES:
            if key in FUTURE_STATE_KEYS:
                continue
            assert key in fsm_keys, (
                f"{st.NAME}.SOURCES references {key!r}, which no @action in "
                f"app/fsm.py writes. Either fix the Stone or add the future "
                f"key to FUTURE_STATE_KEYS in this test."
            )


def test_data_stone_sources_are_disjoint():
    """A given state key belongs to exactly one Stone — no double-counting."""
    seen: dict[str, str] = {}
    for st in DATA_STONES:
        for key in st.SOURCES:
            assert key not in seen, (
                f"state key {key!r} listed in both {seen[key]} and {st.NAME}"
            )
            seen[key] = st.NAME


def test_collect_drops_silent_specialists():
    state = {
        "sandy": True,
        "dep": None,
        "ida_hwm": None,
        "prithvi_water": {"some": "data"},
        "microtopo": None,
        # unrelated key, should be ignored entirely
        "paragraph": "irrelevant",
    }
    out = cornerstone.collect(state)
    assert out == {"sandy": True, "prithvi_water": {"some": "data"}}


def test_all_stones_iteration_order():
    """The four data-Stones must appear in canonical order; Capstone last."""
    assert [s.NAME for s in DATA_STONES] == [
        "Cornerstone", "Keystone", "Touchstone", "Lodestone",
    ]
    assert ALL_STONES[-1].NAME == "Capstone"


def test_collect_signatures_are_uniform():
    """Every Stone's collect() takes a single dict argument."""
    for st in (cornerstone, keystone, touchstone, lodestone, capstone):
        sig = inspect.signature(st.collect)
        params = list(sig.parameters.values())
        assert len(params) == 1, f"{st.NAME}.collect arity"
