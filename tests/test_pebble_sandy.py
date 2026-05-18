"""Smoke test for the sandy pebble (legacy_call adapter wrapping
sandy_inundation.inside_raster).

Verifies that:
  - the pebble returns the boolean_zone-shaper dict for a point inside NYC,
  - `inside` matches what legacy inside_raster() returns on the same point.
"""
from __future__ import annotations

from riprap.core.pebbles import SpatialQuery, load_registry

# Coordinates inside Lower East Side near East River — within Sandy zone.
TEST_LAT = 40.7100
TEST_LON = -73.9800


def test_sandy_pebble_matches_legacy_inside_raster():
    import geopandas as gpd  # noqa: PLC0415
    from shapely.geometry import Point  # noqa: PLC0415

    from app.flood_layers.sandy_inundation import inside_raster  # noqa: PLC0415

    pt_2263 = (gpd.GeoDataFrame(geometry=[Point(TEST_LON, TEST_LAT)], crs="EPSG:4326")
               .to_crs("EPSG:2263").iloc[0].geometry)
    legacy = inside_raster(pt_2263)

    reg = load_registry("deployments/nyc")
    result = reg.get("sandy").fetch(SpatialQuery(lat=TEST_LAT, lon=TEST_LON))
    assert result.error is None, result.error
    # boolean_zone shaper wraps the raw bool in a phrasing-bearing dict
    # the manifest's narration.template renders verbatim.
    assert isinstance(result.value, dict)
    assert result.value["inside"] == bool(legacy)
    assert result.value["inside_or_outside"] in ("inside", "outside")
