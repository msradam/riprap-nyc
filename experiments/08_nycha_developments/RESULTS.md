# Phase 8 — `nycha_development_exposure` specialist (first output)

## Status

**First end-to-end output on Red Hook (Brooklyn) validates.** Same
join pattern as the MTA-entrance specialist, but for *polygon* assets:
the metric of interest is "% of the development's footprint that
intersects the flood layer" rather than point-in-polygon.

## What it does

Per queried (lat, lon), returns up to N NYCHA developments whose
centroid is within `radius_m` (default 2 km — developments are
sparser than subway entrances), enriched with:

| Field | Source | Tier |
|---|---|---|
| `development`, `tds_num`, `borough` | `data/nycha.geojson` (NYC Open Data, 218 developments) | reference |
| `centroid_lat/lon`, `distance_m`, `footprint_km2` | computed | computed |
| `rep_elevation_m`, `rep_hand_m` | USGS 3DEP DEM + derived HAND, sampled at the polygon's representative interior point | proxy |
| `pct_inside_sandy_2012` | area-fraction overlap with `data/sandy_inundation.geojson` | **empirical** |
| `pct_in_dep_extreme_2080` (any depth) | area-fraction overlap with NYC DEP 3.66 in/hr / 2080 SLR scenario | modeled |
| `pct_in_dep_extreme_2080_deep` | area-fraction overlap with DEP `Flooding_Category=3` ("Deep Contiguous, >4 ft") only | modeled |
| `pct_in_dep_moderate_2050` (any depth) | area-fraction overlap with NYC DEP 2.13 in/hr / 2050 SLR scenario | modeled |

Plus rollup counts: `n_majority_inside_sandy_2012`,
`n_with_dep_2080_overlap`.

All overlap math runs in **EPSG:2263** (NYC State Plane, feet) so
area arithmetic is correct citywide.

## First output — Red Hook (40.6745, -74.0090)

```json
{
  "n_developments": 2,
  "n_majority_inside_sandy_2012": 2,
  "n_with_dep_2080_overlap": 2,
  "developments": [
    {
      "development": "RED HOOK WEST",
      "footprint_km2": 0.0761,
      "rep_elevation_m": 3.16,
      "rep_hand_m": 4.39,
      "pct_inside_sandy_2012": 84.49,
      "pct_in_dep_extreme_2080": 8.33,
      "pct_in_dep_moderate_2050": 1.91
    },
    {
      "development": "RED HOOK EAST",
      "footprint_km2": 0.0808,
      "rep_elevation_m": 3.37,
      "rep_hand_m": 4.6,
      "pct_inside_sandy_2012": 59.83,
      "pct_in_dep_extreme_2080": 16.1,
      "pct_in_dep_moderate_2050": 4.73
    }
  ]
}
```

The Red Hook campuses are exactly the asset-level claim the work
plan calls for: **84% of Red Hook West's footprint sits inside the
2012 Sandy Inundation Zone** (empirical evidence — water actually
came in here), at a representative interior elevation of 3.16 m, and
the same campus has 8% overlap with DEP's modeled Extreme-2080
extreme-rainfall scenario. Red Hook East is similar — 60% Sandy
overlap at elev 3.37 m.

These are NYCHA's most-mentioned Sandy-affected campuses, and the
specialist surfaces the empirical + modeled exposure cleanly with
a single doc-message-shaped JSON object per development.

## Honest scope

- **Exposure, not damage forecast.** "84% of the development's
  footprint sits inside the 2012 Sandy zone" is a structural claim
  about the shape of the flood that day — not a prediction that
  the next storm will flood the same area to the same depth.
- **Polygon overlap is the right unit, not building count.** A
  development is many buildings on a campus; the % overlap conveys
  "how much of the campus footprint is exposed" without overstating
  per-unit impact. Building-level inundation requires a separate
  join against MapPLUTO + DOB footprints.
- **30 m DEM resolution.** `rep_elevation_m` is sampled at the
  polygon's `representative_point()`. Useful for borough-level
  comparisons; not building-by-building precision.
- **No NYCHA-internal Sandy-recovery records yet.** The 2014 NYCHA
  Sandy Recovery Plan and HUD CDBG-DR allocations name specific
  developments; folding those citations in is a follow-up before
  app/ integration.

## Reproduce

```bash
.venv/bin/python experiments/08_nycha_developments/specialist.py \
    --lat 40.6745 --lon -74.0090 --radius 1500 --max 4
# Red Hook West + Red Hook East (Brooklyn)

.venv/bin/python experiments/08_nycha_developments/specialist.py \
    --lat 40.5760 --lon -73.9836 --radius 1500 --max 4
# Coney Island Houses (Brooklyn)
```

## Open work (before app/ integration)

1. **MapLibre rendering.** Filled polygons color-graded by
   `pct_inside_sandy_2012`, dashed outline if no DEP overlap.
2. **Doc-message emitter.** `nycha_dev_<tds_num>` doc_id format,
   one per development; reuse the dev_check phrasing patterns.
3. **NYCHA Sandy Recovery Plan (2014) citations.** Per-development
   recovery dollars (or program tiers) folded in as a second
   evidence layer.
4. **Coney Island / Hammel / Carleton Manor validation runs.**
   Three sites that should produce the most demo-friendly outputs.
5. **Hollis silence test.** Hollis (no NYCHA in 2-km radius) should
   return `available=False, n_developments=0` cleanly.
6. **FSM wiring.** Add `step_nycha` to `app/fsm.py` parallel-fanout
   block, gated on whether the planner classified the query as
   `single_address` / `neighborhood` / `development_check`.
7. **pytest integration test.** Lock the Red Hook result shape;
   skip if `data/nycha.geojson` is missing.

## Sharp edges encountered

- **Sandy GeoJSON had a hole-orientation issue** that blew up
  `unary_union` with `TopologyException`. `buffer(0)` fixes it
  without changing the footprint at sub-foot precision.
- **DEP column is `Flooding_Category` (int16), not `depth_class`.**
  Documented; `Flooding_Category == 3` is "Deep Contiguous (>4 ft)".

License: NYC OD NYCHA developments + NYC OEM Sandy + NYC DEP
stormwater + USGS 3DEP DEM — all public-record, civic-tech-clean,
already in use elsewhere in Riprap.
