# Phase 10 — `nys_doh_hospital_exposure` specialist (first output)

## Status

**First end-to-end output on Coney Island Hospital (now South
Brooklyn Health) validates.** Point-based register specialist on 67
NYC hospitals from NYS Department of Health — the authoritative
Article-28 hospital roster, filtered to the five NYC counties.

This is the third register specialist in the lifeline-asset trio:
**transit (MTA entrances) + housing (NYCHA) + healthcare (DOH
hospitals)**, all sharing the same join chain (Sandy 2012 + DEP
scenarios + USGS 3DEP elevation + HAND).

## What it does

Per queried (lat, lon), returns up to N hospitals within `radius_m`
(default 3,000 m — hospitals are sparser than schools or transit
points), enriched with:

| Field | Source | Tier |
|---|---|---|
| `fac_id`, `facility_name`, `address`, `operator_name`, `ownership_type`, `borough` | NYS DOH `vn5v-hh5r` (Health Facility Certification, filtered to NYC counties + `fac_desc_short=HOSP`) | reference |
| `distance_m` | haversine | computed |
| `elevation_m`, `hand_m` | USGS 3DEP DEM + derived HAND | proxy |
| `inside_sandy_2012` | point-in-polygon over Sandy zone | **empirical** |
| `dep_extreme_2080_class` / `_label` | DEP 3.66 in/hr / 2080 SLR | modeled |
| `dep_moderate_2050_class` / `_label` | DEP 2.13 in/hr / 2050 SLR | modeled |

doc_id format: `nyc_hospital_<fac_id>` (NYS DOH facility ID).

## First output — Coney Island (40.5818, -73.9682)

```json
{
  "fac_id": "1294",
  "facility_name": "South Brooklyn Health",
  "address": "2601 Ocean Parkway, Brooklyn",
  "operator_name": "New York City Health and Hospitals Corporation",
  "ownership_type": "Municipality",
  "elevation_m": 2.66,
  "hand_m": 0.0,
  "inside_sandy_2012": true,
  "dep_extreme_2080_class": 2,
  "dep_extreme_2080_label": "Deep & Contiguous (1-4 ft)"
}
```

**South Brooklyn Health** (NYC's renamed Coney Island Hospital
campus) — a public NYC Health + Hospitals Corporation hospital
that was famously evacuated during Sandy when its basement
generators flooded. The specialist correctly surfaces:

- ✓ **Empirical**: inside the 2012 Sandy Inundation Zone
- ✓ **Modeled**: in DEP Extreme-2080 "Deep & Contiguous (1-4 ft)" band
- ✓ **Public-asset framing**: operator = NYC Health + Hospitals
  Corporation, ownership = Municipality

This is the canonical asset-level claim the work plan calls for —
a lifeline asset with both empirical-flood evidence and modeled
future-storm exposure, with the public-asset framing captured for
the journalist / planner / community-board audience.

## Honest scope

- **Exposure, not damage forecast.** "This hospital sits inside the
  2012 Sandy zone" is structural; not "this hospital will flood
  again the same depth next storm".
- **Centroid-edge limitation.** Same as DOE schools — NYU Langone
  Tisch (550 First Ave) returned `inside_sandy_2012=false` even
  though it evacuated 200+ patients in 2012, because the centroid
  point lies just outside the OEM polygon. Building-footprint joins
  via PLUTO would catch these. Already documented as the same
  follow-up shape.
- **Article-28 hospitals only.** Not nursing homes, not
  diagnostic-and-treatment centers, not urgent care. The DOH
  dataset includes all of those under different `fac_desc_short`
  codes; we filtered to `HOSP` for Phase 10 because it's the
  unambiguous lifeline category. Other facility types are a
  natural follow-up (and the same code path drops in).
- **NYS-only data.** This dataset doesn't include federal
  facilities (VA Manhattan / VA Brooklyn). Adding the VA via the
  US VA Facilities API is a separate small step.

## Reproduce

```bash
.venv/bin/python experiments/10_doh_hospitals/specialist.py \
    --lat 40.5818 --lon -73.9682 --radius 1500 --max 3
# Coney Island — South Brooklyn Health, inside Sandy + DEP-2080

.venv/bin/python experiments/10_doh_hospitals/specialist.py \
    --lat 40.7421 --lon -73.9740 --radius 2000 --max 4
# NYU Langone — known centroid-edge case (4/4 false-negative on Sandy
# zone despite real 2012 evacuation; PLUTO fix queued)
```

## Open work (before app/ integration)

1. **PLUTO building-footprint join** — same upgrade slated for
   schools; covers NYU Langone / Bellevue centroid edge cases.
2. **Doc-message emitter** for `nyc_hospital_<fac_id>`.
3. **Hospital Sandy-recovery citations** layer — many hospitals
   have public OIG / city HPM reports detailing 2012 closures
   and capital-rehab investments.
4. **Federal facilities (VA Manhattan / VA Brooklyn)** via VA
   API.
5. **Wider facility coverage** (DTC + NH + ASC) under a flag.
6. **MapLibre rendering** of hospital points.
7. **Hollis silence test**: `available=False, n_hospitals=0`.
8. **FSM wiring** under `step_doh_hospitals`.

## Data setup

```bash
# Refresh the cached NYC-only hospitals layer from NYS DOH
curl -sf "https://health.data.ny.gov/resource/vn5v-hh5r.json?\
\$where=county%20in('Bronx','Kings','New%20York','Queens','Richmond')&\
fac_desc_short=HOSP&\$limit=200" \
  | .venv/bin/python -c "
import sys, json, geopandas as gpd
from shapely.geometry import Point
d = json.load(sys.stdin)
records = [{**r, 'lat': float(r['latitude']), 'lon': float(r['longitude']),
            'geometry': Point(float(r['longitude']), float(r['latitude']))}
           for r in d if r.get('latitude') and r.get('longitude')]
gpd.GeoDataFrame(records, crs='EPSG:4326').to_file(
    'data/hospitals.geojson', driver='GeoJSON')
"
```

License: NYS Health Data is published under NYS Open Data terms
(public-record); civic-tech-clean. NYC OEM Sandy + NYC DEP +
USGS 3DEP are already in use.
