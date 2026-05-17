"""Shaper for ida_hwm — produces the legacy `vars(HWMSummary)` dict shape.

Downstream FSM/reconcile/score consumers expect the flat layout from
app.flood_layers.ida_hwm.HWMSummary. This shaper unwraps the canonical
baked_vector adapter output into that shape so the bridge can drop in
without touching downstream code.
"""
from __future__ import annotations


def shape(value: dict | None, manifest=None) -> dict | None:
    if value is None:
        return None
    aggs = value.get("aggregations") or {}
    nearest = value.get("nearest")
    nearest_props = (nearest or {}).get("properties") or {}
    features = value.get("features") or []

    sample_sites = []
    for feat in features:
        site = (feat.get("properties") or {}).get("site_description")
        if site:
            sample_sites.append(site)
        if len(sample_sites) >= 5:
            break

    points = []
    for feat in features:
        props = feat.get("properties") or {}
        points.append({
            "lat": feat["lat"],
            "lon": feat["lon"],
            "site": props.get("site_description"),
            "elev_ft": props.get("elev_ft"),
            "height_above_gnd_ft": props.get("height_above_gnd"),
            "distance_m": feat["distance_m"],
        })

    return {
        "n_within_radius": value["n_within_radius"],
        "radius_m": value["radius_m"],
        "max_elev_ft": _round(aggs.get("max_elev_ft"), 2),
        "max_height_above_gnd_ft": _round(aggs.get("max_height_above_gnd_ft"), 2),
        "nearest_dist_m": _round((nearest or {}).get("distance_m"), 0),
        "nearest_site": nearest_props.get("site_description"),
        "nearest_elev_ft": nearest_props.get("elev_ft"),
        "sample_sites": sample_sites,
        "points": points,
    }


def _round(v, ndigits: int):
    if v is None:
        return None
    return round(v, ndigits)
