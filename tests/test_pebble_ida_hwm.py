"""End-to-end test for the first pebble: ida_hwm.

Verifies the pebble loaded from YAML produces a value dict that is
byte-for-byte equal to `vars(app.flood_layers.ida_hwm.summary_for_point(...))`
on the same NYC test address. The legacy function is the regression oracle.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from riprap.core.pebbles import SpatialQuery, load_registry

ROOT = Path(__file__).resolve().parent.parent
DEPLOYMENT = ROOT / "deployments" / "nyc"

# Address in Queens with known Ida flooding nearby.
TEST_LAT = 40.7282
TEST_LON = -73.7949


@pytest.fixture(scope="module")
def registry():
    return load_registry(DEPLOYMENT)


def test_registry_loads_ida_hwm(registry):
    assert "ida_hwm" in registry
    pebble = registry.get("ida_hwm")
    assert pebble.stone == "cornerstone"
    assert pebble.manifest.type == "baked"


def test_pebble_shape_matches_legacy(registry):
    """Pebble.value must equal vars(HWMSummary) field-for-field."""
    from app.flood_layers.ida_hwm import summary_for_point  # noqa: PLC0415

    pebble = registry.get("ida_hwm")
    result = pebble.fetch(SpatialQuery(lat=TEST_LAT, lon=TEST_LON))
    assert result.error is None, result.error
    assert result.offline is False

    new = result.value
    old = vars(summary_for_point(TEST_LAT, TEST_LON, radius_m=800))

    # Every field present in legacy must appear in new with matching value.
    for k in old:
        assert k in new, f"missing key {k!r} in shaped output"
        if k == "points":
            assert len(new[k]) == len(old[k])
            for np_, op in zip(new[k], old[k], strict=True):
                assert np_ == op, f"point mismatch: {np_} vs {op}"
        else:
            assert new[k] == old[k], f"{k}: {new[k]!r} != {old[k]!r}"
