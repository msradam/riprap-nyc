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


def test_pebbles_for_none_sentinel_returns_federal_only():
    """Out-of-coverage sentinel produces only federal pebbles —
    city-specific ones (sandy, dep_*, nyc311) are dropped, but the
    federal pebbles (nws_obs, nws_alerts) that resolve any CONUS
    lat/lon still fire so the briefing has something to report."""
    from riprap.core.burr.stones import _pebbles_for
    assert _pebbles_for("cornerstone", "__none__") == []
    # touchstone has nws_obs from the federal manifest.
    assert _pebbles_for("touchstone", "__none__") == ["nws_obs"]
    # lodestone has nws_alerts from the federal manifest.
    assert "nws_alerts" in _pebbles_for("lodestone", "__none__")


def test_federal_pebbles_auto_merge_into_every_city():
    """nws_alerts + nws_obs live in deployments/federal/ and auto-merge
    into every spatially-routed deployment. No city should re-declare
    them (deduped); every city should still fan out federal pebbles
    when fed CONUS coords."""
    from riprap.core.burr.stones import _pebbles_for

    for city, lat, lon in [
        ("nyc",     40.7128, -74.0060),
        ("boston",  42.3601, -71.0589),
        ("chicago", 41.8781, -87.6298),
        ("seattle", 47.6094, -122.3422),
        ("sf",      37.7793, -122.4192),
    ]:
        touchstone = _pebbles_for("touchstone", city, lat=lat, lon=lon)
        lodestone = _pebbles_for("lodestone", city, lat=lat, lon=lon)
        assert "nws_obs" in touchstone, (
            f"{city}: federal nws_obs failed to auto-merge into touchstone"
        )
        assert "nws_alerts" in lodestone, (
            f"{city}: federal nws_alerts failed to auto-merge into lodestone"
        )


def test_federal_pebbles_not_duplicated_in_city_dirs():
    """Each federal pebble exists in exactly one manifest file — the
    federal one. Drift here defeats the dedup."""
    from pathlib import Path
    repo = Path(__file__).resolve().parent.parent
    for fid in ("nws_alerts", "nws_obs"):
        matches = list(repo.glob(f"deployments/*/manifests/{fid}.yaml"))
        assert len(matches) == 1, (
            f"federal pebble {fid!r} found in {len(matches)} manifests: "
            f"{[str(m.relative_to(repo)) for m in matches]} — expected exactly one (federal)."
        )
        assert "federal" in str(matches[0]), (
            f"federal pebble {fid!r} is in {matches[0]}, not deployments/federal/"
        )


def test_per_pebble_coverage_filter_out_of_conus():
    """A point outside CONUS (e.g. Tokyo) fires zero pebbles even when
    we point at a known deployment — the per-pebble coverage filter
    catches global queries that bypassed the deployment router."""
    from riprap.core.burr.stones import _pebbles_for
    # Tokyo — outside CONUS, outside every city bbox.
    assert _pebbles_for("touchstone", "nyc", lat=35.6762, lon=139.6503) == []
    assert _pebbles_for("lodestone", "nyc", lat=35.6762, lon=139.6503) == []


def test_per_pebble_coverage_filter_conus_but_not_city():
    """A point inside CONUS but outside every city bbox still gets
    federal pebbles (NWS Alerts works for Albuquerque too)."""
    from riprap.core.burr.stones import _pebbles_for
    abq = _pebbles_for("touchstone", "nyc", lat=35.0844, lon=-106.6504)
    assert "nws_obs" in abq, (
        "Albuquerque is in CONUS — NWS METAR observations should fire."
    )
    # NYC-specific pebbles (floodnet, nyc311, prithvi_live) should NOT
    # fire for Albuquerque because they inherit the NYC bbox.
    assert "floodnet" not in abq
    assert "nyc311" not in abq
