"""Smoke tests for the remaining Cornerstone pebbles (microtopo, prithvi_water).

The legacy functions return dataclasses; the legacy_call adapter auto-unwraps
them via __dataclass_fields__. Verifies the pebble value matches vars(legacy).
"""
from __future__ import annotations

import pytest

from riprap.core.pebbles import SpatialQuery, load_registry

TEST_LAT = 40.7100
TEST_LON = -73.9800


@pytest.fixture(scope="module")
def registry():
    return load_registry("deployments/nyc")


def test_microtopo_pebble_matches_legacy(registry):
    from app.context.microtopo import microtopo_at  # noqa: PLC0415

    legacy = microtopo_at(TEST_LAT, TEST_LON)
    if legacy is None:
        pytest.skip("DEM unavailable in this environment")
    result = registry.get("microtopo").fetch(SpatialQuery(lat=TEST_LAT, lon=TEST_LON))
    assert result.error is None, result.error
    assert isinstance(result.value, dict)
    assert result.value == vars(legacy)


def test_prithvi_water_pebble_matches_legacy(registry):
    from app.flood_layers.prithvi_water import summary_for_point  # noqa: PLC0415

    legacy = summary_for_point(TEST_LAT, TEST_LON)
    if legacy is None:
        pytest.skip("Prithvi water mask unavailable in this environment")
    result = registry.get("prithvi_water").fetch(SpatialQuery(lat=TEST_LAT, lon=TEST_LON))
    assert result.error is None, result.error
    assert isinstance(result.value, dict)
    assert result.value == vars(legacy)
