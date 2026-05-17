"""Per-query deployment routing — the data-correctness gate.

The architectural promise: a Boston query never fires NYC's `ida_hwm`
pebble, regardless of which deployment the server happened to boot
with. These tests are the regression seal on that promise.
"""
from __future__ import annotations

from riprap.core.pebbles.deployments import (
    deployment_by_name,
    discover_deployments,
    pick_deployment,
)


def test_all_shipped_cities_have_a_coverage_bbox():
    """Every place-routed deployment declares a bbox + city. Heat/air
    deployments are hazard-routed and intentionally bbox-less."""
    deps = {d.name: d for d in discover_deployments()}
    for name in ("nyc", "boston", "chicago", "seattle", "sf"):
        d = deps.get(name)
        assert d is not None, f"deployments/{name} missing from discovery"
        assert d.bbox is not None, f"deployments/{name} has no coverage.bbox"
        assert d.city, f"deployments/{name} coverage.city is missing"


def test_city_centroids_route_to_their_deployment():
    """Each shipped city's city-hall point picks its own deployment.

    A miss here is the bug the user called out: 'Hurricane Ida ran for
    Boston' — i.e. the routing put a Boston point into the NYC fan-out.
    """
    cases = [
        ("NYC City Hall",        40.7128, -74.0060, "nyc"),
        ("Boston City Hall",     42.3601, -71.0589, "boston"),
        ("Chicago Loop",         41.8781, -87.6298, "chicago"),
        ("Seattle Pike Place",   47.6094, -122.3422, "seattle"),
        ("SF Civic Center",      37.7793, -122.4192, "sf"),
    ]
    for label, lat, lon, expected in cases:
        d = pick_deployment(lat, lon)
        assert d is not None, f"{label} ({lat}, {lon}) didn't route to any deployment"
        assert d.name == expected, (
            f"{label} routed to {d.name!r}, expected {expected!r} — "
            f"this is the cross-city data leak that lets NYC's ida_hwm "
            f"fire for {label}."
        )


def test_out_of_coverage_point_returns_none():
    """An address outside every shipped deployment's bbox returns None.
    Caller short-circuits to 'not covered yet' instead of fanning out
    every NYC pebble against a non-NYC point."""
    # Albuquerque, NM — outside every shipped bbox.
    assert pick_deployment(35.0844, -106.6504) is None


def test_no_coords_returns_none():
    """Geocoding failed (e.g. unparseable address) → no routing."""
    assert pick_deployment(None, None) is None
    assert pick_deployment(40.0, None) is None


def test_deployment_by_name_lookup():
    assert deployment_by_name("nyc") is not None
    assert deployment_by_name("boston") is not None
    assert deployment_by_name("does_not_exist") is None


def test_stones_pebbles_for_filters_by_deployment():
    """The Stone fan-out function returns only the active deployment's
    pebbles — the regression seal on the data-leak fix."""
    from riprap.core.burr.stones import _pebbles_for

    boston_cornerstone = set(_pebbles_for("cornerstone", "boston"))
    nyc_cornerstone = set(_pebbles_for("cornerstone", "nyc"))

    # NYC Cornerstone includes ida_hwm, sandy, dep_*, prithvi_water, etc.
    assert "ida_hwm" in nyc_cornerstone
    assert "sandy" in nyc_cornerstone
    # Boston Cornerstone must NOT include them — this is the bug fix.
    assert "ida_hwm" not in boston_cornerstone, (
        "Boston cornerstone fan-out contains ida_hwm — Hurricane Ida is "
        "a New York 2021 event and must not fire for Boston queries."
    )
    assert "sandy" not in boston_cornerstone


def test_pebbles_for_none_sentinel_returns_empty():
    """Out-of-coverage sentinel produces zero pebbles."""
    from riprap.core.burr.stones import _pebbles_for
    assert _pebbles_for("cornerstone", "__none__") == []
    assert _pebbles_for("touchstone", "__none__") == []
