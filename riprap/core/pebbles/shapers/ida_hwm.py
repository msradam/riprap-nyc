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

    n = value["n_within_radius"]
    radius = value["radius_m"]
    max_elev = _round(aggs.get("max_elev_ft"), 2)
    max_above = _round(aggs.get("max_height_above_gnd_ft"), 2)
    nearest_dist = _round((nearest or {}).get("distance_m"), 0)
    nearest_site = nearest_props.get("site_description")
    # Templatable narrative for the manifest's narration.template.
    # Two shapes: the affirmative case ("we found N marks…") and the
    # honest-negative case ("no marks within radius — the nearest is X").
    # The latter matches the NWS "no active alerts" all-clear card; users
    # see Riprap asked the question and the answer was reassuring.
    if n and n > 0:
        bits = [f"USGS surveyed {n} Hurricane Ida high-water mark(s) within"
                f" {radius} m of this address"]
        if max_elev is not None:
            bits.append(f"; the highest observed water elevation was {max_elev} ft")
        if max_above is not None:
            bits.append(f" (up to {max_above} ft above ground)")
        if nearest_site and nearest_dist is not None:
            bits.append(
                f". Nearest mark: {nearest_site} ({int(nearest_dist)} m away)"
            )
        narrative = "".join(bits) + "."
    else:
        narrative = (
            f"No Hurricane Ida (Sept 2021) high-water marks were surveyed "
            f"within {radius} m of this address."
        )
        if nearest_site and nearest_dist is not None:
            narrative += (
                f" Nearest USGS-surveyed mark: {nearest_site} "
                f"({int(nearest_dist)} m away)."
            )
    return {
        "n_within_radius": n,
        "radius_m": radius,
        "max_elev_ft": max_elev,
        "max_height_above_gnd_ft": max_above,
        "nearest_dist_m": nearest_dist,
        "nearest_site": nearest_site,
        "nearest_elev_ft": nearest_props.get("elev_ft"),
        "sample_sites": sample_sites,
        "points": points,
        "narrative": narrative,
    }


def _round(v, ndigits: int):
    if v is None:
        return None
    return round(v, ndigits)
