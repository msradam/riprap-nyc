# Phase 9 — `doe_school_exposure` specialist (first output)

## Status

**First end-to-end output on Coney Island validates.** Point-based
register specialist on the 1,992 NYC DOE school locations, identical
join pattern to the MTA-entrance specialist.

## What it does

Per queried (lat, lon), returns up to N schools within `radius_m`
(default 1,500 m), enriched with:

| Field | Source | Tier |
|---|---|---|
| `loc_code`, `loc_name`, `address`, `bin`, `bbl`, `managed_by`, `borough` | `data/schools.geojson` (NYC DOE Locations Points) | reference |
| `distance_m` | haversine from query point | computed |
| `elevation_m` | `data/nyc_dem_30m.tif` (USGS 3DEP) | proxy |
| `hand_m` | `data/hand.tif` (derived) | proxy |
| `inside_sandy_2012` | point-in-polygon over `data/sandy_inundation.geojson` | **empirical** |
| `dep_extreme_2080_class` / `_label` | NYC DEP 3.66 in/hr / 2080 SLR scenario | modeled |
| `dep_moderate_2050_class` / `_label` | NYC DEP 2.13 in/hr / 2050 SLR scenario | modeled |

doc_id format: `doe_school_<loc_code>` (loc_code is the NYC DOE
school identifier, e.g. `M089`, `K212`).

## First output — Coney Island (40.5790, -73.9847)

5 of 5 schools within 1.5 km **inside the 2012 Sandy Inundation
Zone**; 2 of 5 in DEP Extreme-2080 "Deep Contiguous (>4 ft)" band.

| School | Address | Elev (m) | Sandy 2012 | DEP 2080 |
|---|---|---:|---|---|
| Liberation Diploma Plus (`K728`) | 2865 W 19th St | 1.25 | ✓ | Deep Contiguous (>4 ft) |
| P.S. 90 Edna Cohen (`K090`) | 2840 W 12th St | 0.55 | ✓ | outside |
| Mark Twain I.S. 239 (`K239`) | 2401 Neptune Ave | 0.10 | ✓ | outside |
| P.S. 288 Shirley Tanyhill (`K288`) | 2950 W 25th St | 0.75 | ✓ | Deep Contiguous (>4 ft) |
| P.S. 212 Lady Deborah Moody (`K212`) | 87 Bay 49th St | 2.82 | ✓ | outside |

These are real Sandy-affected schools — Mark Twain I.S. 239 and P.S.
288 in particular were both recovery sites in DOE's post-Sandy
Title-I emergency declarations.

## Honest scope

- **Exposure, not damage forecast.** "This school sits inside the
  2012 Sandy zone" is a structural claim, not a prediction the
  building will flood again at the same depth.
- **Point-at-school-centroid join.** Schools are big buildings;
  point-in-polygon at the centroid can miss a building whose
  footprint clips the flood polygon edge. Battery Park City schools
  (P.S. 89, Stuyvesant HS) returned `inside_sandy_2012=false`
  despite real basement flooding in 2012 — their centroid points
  lie just outside the OEM polygon. Building-footprint joins via
  PLUTO would catch these edge cases; that's a follow-up.
- **30 m DEM / HAND.** Useful for borough-level comparisons, not
  building-level discrimination.
- **No DOE Sandy recovery citations yet.** Title-I emergency
  declarations and HUD CDBG-DR school recovery flows aren't joined
  in this first cut — same follow-up shape as NYCHA Recovery Plan
  parsing.

## Reproduce

```bash
.venv/bin/python experiments/09_doe_schools/specialist.py \
    --lat 40.5790 --lon -73.9847 --radius 1500 --max 5
# Coney Island (5/5 in Sandy zone, 2/5 in DEP deep band)

.venv/bin/python experiments/09_doe_schools/specialist.py \
    --lat 40.7155 --lon -74.0145 --radius 1000 --max 5
# Battery Park City — known centroid-edge case (returns 0/5 even
# though Stuyvesant + P.S. 89 had basement flooding)
```

## Open work (before app/ integration)

1. **PLUTO building-footprint join** for the centroid-edge fix —
   replace point-in-polygon with footprint-overlap to catch BPC /
   Tribeca cases.
2. **Doc-message emitter** for `doe_school_<loc_code>`.
3. **DOE Sandy-recovery citations** layer.
4. **MapLibre rendering** of school points, color by Sandy/DEP.
5. **Far Rockaway + Howard Beach validation runs** — most
   Sandy-affected DOE clusters citywide.
6. **Hollis silence test** (`available=False, n_schools=0`).
7. **FSM wiring** under `step_doe_schools` parallel-fanout.

## Sharp edges encountered

- **Non-breaking spaces in school addresses.** NYC DOE export
  encodes ` ` between street number and direction in some
  addresses (`"2840 WEST  12 STREET"`). Cosmetic; safe to
  leave for now, or `.replace(" ", " ")` if it bites the
  reconciler's prose rendering.
- **Battery Park City false-negatives** above are a real limitation
  worth documenting — and a strong argument for the PLUTO join
  upgrade in the follow-up.

License: NYC DOE Locations is NYC OD (Open Data Terms of Use);
Sandy / DEP / 3DEP all already-used civic-tech-clean public data.
