"""Smoke tests for the three DEP stormwater scenario pebbles.

Verifies that:
  - all three pebbles load,
  - each returns a dict with depth_class / depth_label / citation,
  - depth_class agrees with legacy dep_stormwater.join_raster() on the same point.
"""
from __future__ import annotations

import pytest

from riprap.core.pebbles import SpatialQuery, load_registry

TEST_LAT = 40.7100
TEST_LON = -73.9800

SCENARIOS = ("dep_extreme_2080", "dep_moderate_2050", "dep_moderate_current")


@pytest.fixture(scope="module")
def registry():
    return load_registry("deployments/nyc")


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_dep_pebble_matches_legacy(registry, scenario):
    import geopandas as gpd  # noqa: PLC0415
    from shapely.geometry import Point  # noqa: PLC0415

    from app.flood_layers.dep_stormwater import join_raster  # noqa: PLC0415

    pt_2263 = (gpd.GeoDataFrame(geometry=[Point(TEST_LON, TEST_LAT)], crs="EPSG:4326")
               .to_crs("EPSG:2263").iloc[0].geometry)
    legacy_cls = int(join_raster(pt_2263, scenario))

    result = registry.get(scenario).fetch(SpatialQuery(lat=TEST_LAT, lon=TEST_LON))
    assert result.error is None, result.error
    # The dep_scenario shaper returns None for class=0 (no flooding in
    # this scenario) so the templated card drops silently. For class>0
    # the dict layout is unchanged.
    if legacy_cls <= 0:
        assert result.value is None
        return
    assert isinstance(result.value, dict)
    assert result.value["depth_class"] == legacy_cls
    assert "depth_label" in result.value
    assert "citation" in result.value
    assert "narrative" in result.value
    assert result.value["citation"].startswith("NYC DEP Stormwater Flood Map")
