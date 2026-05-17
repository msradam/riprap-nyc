"""Tests for the BYOD adapters: csv_points, rest_json, and the URL path
support on baked_vector.

External network is monkey-patched. These tests don't hit the internet.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml
from pydantic import TypeAdapter

from riprap.core.pebbles import SpatialQuery
from riprap.core.pebbles.adapters import (
    BakedVectorPebble,
    CSVPointsPebble,
    RestJSONPebble,
)
from riprap.core.pebbles.schema import PebbleManifest

_ADAPTER = TypeAdapter(PebbleManifest)


def _build(manifest_yaml: str, root: Path) -> object:
    raw = yaml.safe_load(manifest_yaml)
    m = _ADAPTER.validate_python(raw)
    if m.adapter == "baked_vector":
        return BakedVectorPebble(m, root)
    if m.adapter == "csv_points":
        return CSVPointsPebble(m, root)
    if m.adapter == "rest_json":
        return RestJSONPebble(m, root)
    raise AssertionError(m.adapter)


# ---------- csv_points ----------

CSV_FIXTURE = (
    "site_id,latitude,longitude,severity\n"
    "A,40.7282,-73.7950,3\n"     # ~10 m from query point
    "B,40.7300,-73.7950,1\n"     # ~210 m
    "C,40.7500,-73.7950,5\n"     # ~2.4 km
)


def test_csv_points_radius_query(tmp_path):
    csv_path = tmp_path / "incidents.csv"
    csv_path.write_text(CSV_FIXTURE)
    manifest = f"""
id: my_csv
type: baked
title: CSV test
stone: cornerstone
adapter: csv_points
config:
  path: {csv_path}
  lat_col: latitude
  lon_col: longitude
  query: {{type: radius_point, radius_m: 500}}
  feature_properties: [site_id, severity]
  aggregations:
    max_severity: {{op: max, field: severity}}
provenance:
  source_name: test
"""
    p = _build(manifest, tmp_path)
    r = p.fetch(SpatialQuery(lat=40.7282, lon=-73.7949))
    assert r.error is None, r.error
    assert r.value["n_within_radius"] == 2
    assert r.value["aggregations"]["max_severity"] == 3.0
    assert r.value["features"][0]["properties"]["site_id"] == "A"
    assert r.value["nearest"]["properties"]["site_id"] == "A"


# ---------- baked_vector URL path ----------

GEOJSON_FIXTURE = {
    "type": "FeatureCollection",
    "features": [
        {"type": "Feature",
         "geometry": {"type": "Point", "coordinates": [-73.7950, 40.7282]},
         "properties": {"name": "near"}},
        {"type": "Feature",
         "geometry": {"type": "Point", "coordinates": [-73.7950, 40.7500]},
         "properties": {"name": "far"}},
    ],
}


def test_baked_vector_url_path(tmp_path, monkeypatch):
    # Stub the shared HTTP cache so the adapter never hits the network.
    from riprap.core.pebbles import _http  # noqa: PLC0415

    def fake_fetch_url_text(url, **kw):
        assert url == "https://example.com/test.geojson"
        return json.dumps(GEOJSON_FIXTURE)

    monkeypatch.setattr(_http, "fetch_url_text", fake_fetch_url_text)
    # Patch the symbol the adapter imported, too.
    from riprap.core.pebbles.adapters import baked_vector as bv  # noqa: PLC0415
    monkeypatch.setattr(bv, "fetch_url_text", fake_fetch_url_text)

    manifest = """
id: my_remote_geojson
type: baked
title: Remote geojson test
stone: cornerstone
adapter: baked_vector
config:
  path: https://example.com/test.geojson
  query: {type: radius_point, radius_m: 500}
provenance:
  source_name: test
"""
    p = _build(manifest, tmp_path)
    r = p.fetch(SpatialQuery(lat=40.7282, lon=-73.7949))
    assert r.error is None, r.error
    assert r.value["n_within_radius"] == 1
    assert r.value["nearest"]["properties"]["name"] == "near"


# ---------- rest_json ----------

def test_rest_json_with_response_path(tmp_path, monkeypatch):
    from riprap.core.pebbles import _http  # noqa: PLC0415
    from riprap.core.pebbles.adapters import rest_json as rj  # noqa: PLC0415

    captured = {}

    def fake_fetch_url_json(url, **kw):
        captured["url"] = url
        captured["headers"] = kw.get("headers")
        return {"meta": {"v": 1}, "data": {"score": 0.83, "trend": "up"}}

    monkeypatch.setattr(_http, "fetch_url_json", fake_fetch_url_json)
    monkeypatch.setattr(rj, "fetch_url_json", fake_fetch_url_json)
    monkeypatch.setenv("MYKEY", "secret-token-123")

    manifest = """
id: my_rest
type: live
title: REST test
stone: touchstone
adapter: rest_json
config:
  url: https://api.example.com/score/{lat},{lon}
  headers:
    Authorization: "Bearer ${MYKEY}"
  response_path: data.score
provenance:
  source_name: test
"""
    p = _build(manifest, tmp_path)
    r = p.fetch(SpatialQuery(lat=40.7282, lon=-73.7949))
    assert r.error is None, r.error
    assert r.value == 0.83
    assert captured["url"] == "https://api.example.com/score/40.7282,-73.7949"
    # Header interpolation reached the fetch layer; the actual env-var
    # expansion happens inside fetch_url_json (not exercised by the stub
    # but verified for transit).
    assert captured["headers"]["Authorization"] == "Bearer ${MYKEY}"


def test_rest_json_path_with_list_index(tmp_path, monkeypatch):
    from riprap.core.pebbles import _http  # noqa: PLC0415
    from riprap.core.pebbles.adapters import rest_json as rj  # noqa: PLC0415

    def fake(url, **kw):
        return {"features": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}

    monkeypatch.setattr(_http, "fetch_url_json", fake)
    monkeypatch.setattr(rj, "fetch_url_json", fake)

    manifest = """
id: idx
type: live
title: indexed
stone: touchstone
adapter: rest_json
config:
  url: https://api.example.com/x
  response_path: features[1].id
provenance:
  source_name: test
"""
    p = _build(manifest, tmp_path)
    r = p.fetch(SpatialQuery(lat=40.0, lon=-73.0))
    assert r.error is None, r.error
    assert r.value == "b"


def test_rest_json_offline_when_http_fails(tmp_path, monkeypatch):
    import httpx  # noqa: PLC0415

    from riprap.core.pebbles import _http  # noqa: PLC0415
    from riprap.core.pebbles.adapters import rest_json as rj  # noqa: PLC0415

    def boom(url, **kw):
        raise httpx.ConnectError("simulated network failure")

    monkeypatch.setattr(_http, "fetch_url_json", boom)
    monkeypatch.setattr(rj, "fetch_url_json", boom)

    manifest = """
id: down
type: live
title: down
stone: touchstone
adapter: rest_json
config:
  url: https://api.example.com/x
provenance:
  source_name: test
fallback:
  on_offline: skip
  message: example offline
"""
    p = _build(manifest, tmp_path)
    r = p.fetch(SpatialQuery(lat=40.0, lon=-73.0))
    assert r.offline is True
    assert r.value is None
    assert r.error is not None and "HTTP error" in r.error
