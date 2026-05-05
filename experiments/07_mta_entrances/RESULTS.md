# Phase 7 — `mta_entrance_exposure` specialist (first output)

## Status

**First end-to-end output on Sheepshead Bay validates.** The headline
new specialist for the IBM senior technical staffer's "subway
entrances" reaction works structurally; ready for FSM integration
once expanded across the city.

## What it does

Per queried (lat, lon), returns up to N MTA subway entrances within
a configurable radius (default 800 m), enriched with flood-exposure
fields per entrance:

| Field | Source | Tier |
|---|---|---|
| `station_id`, `station_name`, `daytime_routes`, `entrance_type`, `entrance_lat/lon` | `data/mta_entrances.geojson` (MTA Open Data, 2120 entrances) | reference |
| `distance_m` | haversine from query point | computed |
| `ada_accessible` (heuristic) | `entrance_type ∈ {"Elevator", "Ramp"}` | proxy |
| `elevation_m` | `data/nyc_dem_30m.tif` (USGS 3DEP) | proxy |
| `hand_m` (height above nearest drainage) | `data/hand.tif` (derived) | proxy |
| `inside_sandy_2012` | point-in-polygon over `data/sandy_inundation.geojson` | **empirical** |
| `dep_extreme_2080_class` / `_label` | NYC DEP Stormwater Flood Map (3.66 in/hr, 2080 SLR) | modeled |
| `dep_moderate_2050_class` / `_label` | NYC DEP Stormwater Flood Map (2.13 in/hr, 2050 SLR) | modeled |

Plus rollup counts: `n_inside_sandy_2012`, `n_in_dep_extreme_2080`,
`n_ada_accessible`.

## First output — Sheepshead Bay (40.5868, -73.9543)

```json
{
  "n_entrances": 2,
  "n_inside_sandy_2012": 1,
  "n_in_dep_extreme_2080": 1,
  "entrances": [
    {
      "station_id": "54", "station_name": "Sheepshead Bay",
      "daytime_routes": "B Q", "entrance_type": "Station House",
      "distance_m": 56.2,
      "elevation_m": 7.07, "hand_m": 5.38,
      "inside_sandy_2012": false,
      "dep_extreme_2080_class": 0, "dep_extreme_2080_label": "outside"
    },
    {
      "station_id": "54", "station_name": "Sheepshead Bay",
      "daytime_routes": "B Q", "entrance_type": "Station House",
      "distance_m": 118.7,
      "elevation_m": 5.41, "hand_m": 5.41,
      "inside_sandy_2012": true,
      "dep_extreme_2080_class": 3,
      "dep_extreme_2080_label": "Deep Contiguous (>4 ft)"
    }
  ]
}
```

The two Sheepshead Bay station-house entrances split: the one ~56 m
NE of the query point (elev 7 m) is outside both empirical and
modeled flood layers; the one ~119 m S of the query point (elev
5.4 m) is **inside the 2012 Sandy zone** and **falls in DEP's deepest
"Deep Contiguous (>4 ft)" 2080 flood band**. This is the kind of
asset-level claim the work plan calls for: an entrance that
empirically flooded in 2012 and is modeled to flood deeply under
the 2080 extreme-rain scenario.

## Honest scope (locked before integration)

- This is an **exposure** specialist. We say "this entrance sits
  inside the 2012 Sandy zone" — not "this entrance will flood
  again next storm".
- Sandy / DEP claims are point-in-polygon over public-record
  geometry. ADA status from the MTA Open Data `entrance_type`
  column is a heuristic (Elevator / Ramp), **not** the
  authoritative MTA accessibility list.
- **Documented MTA Sandy-recovery records** for specific stations
  are NOT yet in this first cut. Adding station-level recovery
  citations from the MTA's "Hurricane Sandy: Three Years Later"
  report is a follow-up before integration.
- USGS 3DEP DEM here is the cached **30 m** raster. The work plan
  references 1 m DEM; if station-level elevation discrimination
  matters more than 30 m gives us, we upgrade to the higher-res
  raster in a separate step.

## Reproduce

```bash
.venv/bin/python experiments/07_mta_entrances/specialist.py \
    --lat 40.5868 --lon -73.9543 --radius 800 --max 6
```

## Open work (before app/ integration)

1. Add MTA Sandy-recovery station list (parse "Hurricane Sandy:
   Three Years Later" report or use a digestible CSV).
2. Validate on diverse NYC contexts: South Ferry / Whitehall (the
   pitch-cold-open framing), Coney Island / Stillwell Ave, Hunts
   Point Avenue, Hollis (no subway → silence-over-confabulation
   should hold), Red Hook (no subway directly).
3. Build a doc-message emitter that turns the structured output
   into a `mta_entrance_<station_id>` doc the reconciler can cite.
4. Wire into the parallel-fanout block in `app/fsm.py`.
5. Trace UI / map: render entrance points on the existing
   MapLibre canvas with color-coding by sandy/dep status.
6. pytest integration test asserting the Sheepshead Bay output
   shape across a refresh.

License: existing — MTA Open Data is NYC OpenData (NYC Open Data
Terms of Use), public + free. NYC OEM Sandy zone, NYC DEP
stormwater maps, and USGS 3DEP DEM are all public-record
infrastructure already used elsewhere in Riprap.
