# Port your city — a worked walkthrough

> NYC is the reference deployment for an open civic-tech framework.
> Adding your jurisdiction is a directory of YAML, not a fork.

This is the lived experience of porting Boston, Chicago, Seattle, and
San Francisco onto Riprap in two days, written up so anyone can do the
same for their city. Boston is the worked example because it's the
hardest case (different data platform: CKAN, not Socrata) — once Boston
is in your head, every Socrata city is easier.

If your city's open-data portal runs **Socrata** (data.cityofnewyork.us,
data.cityofchicago.org, data.sfgov.org, data.seattle.gov, opendata.dc.gov,
data.austintexas.gov, ...) or **CKAN** (data.boston.gov, opendataphilly.org,
open.toronto.ca, most EU portals): the existing adapters already
work. You write YAML.

## What a deployment is

```
deployments/<city>/
├── stones.yaml              # five entries, one per Stone (Cornerstone,
│                            # Keystone, Touchstone, Lodestone, Capstone),
│                            # with city-flavoured taglines and descriptions
└── manifests/
    ├── nws_obs.yaml         # federal pebble — works for any US address
    ├── nws_alerts.yaml      # federal pebble — works for any US address
    ├── water_level.yaml     # federal pebble — NOAA tides, nearest station auto-resolves
    └── <city>_311.yaml      # your city's 311 / equivalent service-request feed
```

Four pebbles is enough to clear the 13-predicate compliance audit on
every city we've shipped. Add more for your local hazard signals
(historical inundation, regulatory floodplain, asset registers, etc.) —
those depend on what your jurisdiction publishes.

## Step 0 — Pick the address you'll test against

Pick something with a known street address and lat/lon. City halls work
great; they're publicly geocodable on Nominatim, they tend to have
311 records nearby, and they're inside whatever flood/heat/air dataset
coverage your portal exposes.

| City    | Test address                                   |
|---------|------------------------------------------------|
| Chicago | 233 S Wacker Dr (Willis Tower)                |
| Seattle | 2100 5th Ave (Climate Pledge Arena area)      |
| SF      | 1 Dr Carlton B Goodlett Pl (City Hall)        |
| Boston  | 1 City Hall Square                            |

## Step 1 — Find your 311 dataset

Most US cities publish 311 service requests. Find yours on the open-data
portal. The two things you need:

- **Resource ID** (Socrata: `xxxx-xxxx`; CKAN: a UUID)
- **Spatial field name** — Socrata datasets vary: NYC + Chicago use
  `location`, SF uses `point`, Seattle's 311 dataset has *no usable
  Point geometry* (we skipped it). CKAN datasets typically ship
  `latitude`/`longitude` numeric columns.

Verify with a tiny curl before writing YAML:

```bash
# Socrata: list fields + check spatial field
curl -s 'https://data.cityofchicago.org/resource/v6vf-nfxy.json?$limit=1' \
  | python3 -m json.tool | head -30

# CKAN: list fields
curl -s 'https://data.boston.gov/api/3/action/datastore_search?\
resource_id=1a0b420d-99f1-4887-9851-990b2a5a6e17&limit=1' \
  | python3 -m json.tool | head -30
```

If the spatial field is missing, you have two options:

1. **Different dataset** — many cities publish multiple 311 exports;
   one might have a `Point`-typed geo column even if another doesn't.
2. **Skip the 311 pebble** — Seattle ships with federal pebbles only,
   and still passes 13/13 compliance.

## Step 2 — Scaffold the deployment directory

Easiest path: copy a sibling.

```bash
cp -r deployments/boston deployments/<your-city>
```

This gives you a stones.yaml + the four-pebble starter set
(federal × 3 + city 311). You'll edit `stones.yaml` for taglines and
the 311 manifest for resource id + spatial field; everything else can
stay.

## Step 3 — Edit `stones.yaml`

```yaml
stones:
  - id: cornerstone
    name: Cornerstone
    tagline: The Hazard Reader
    description: Reads what <your city> remembers about flooding —
                 specific local terrain / shoreline / catchment notes.
    order: 1
  - id: touchstone
    name: Touchstone
    tagline: The Live Observer
    description: Watches current flood signals — <city> 311 cases,
                 NWS forecast office, NOAA tide/lake observations.
    order: 2
  ...
```

This is the only "voice" you'll write. It's what readers see at the
top of each Stone section in the briefing. Keep it short and local.

## Step 4 — Edit the 311 manifest

### Socrata cities

```yaml
id: <city>_311
type: live
title: <City> 311 service requests near this address
stone: touchstone
adapter: socrata_records

spatial: {scope: point, crs: EPSG:4326}

config:
  base_url: https://data.<city>.gov/resource/<resource-id>.json
  radius_m: 300
  location_field: location           # OR `point`, OR `the_geom`, check first
  limit: 200
  sample_fields: [<a few descriptive fields>]
  count_by_field: <category field>   # e.g. `service_name`, `reason`
  order: <date_field> DESC
  cache_ttl_s: 1800

provenance:
  source_name: <City> Open Data — 311 (<resource-id>)
  source_url: https://data.<city>.gov/d/<resource-id>
  license: <portal's stated license>
  doc_id: <city>_311

narration:
  short: <City> 311 service requests filed within 300 m of this address.
  template: >-
    <City> 311 received {n_records} service requests within {radius_m} m
    of this address.
```

### CKAN cities

```yaml
id: <city>_311
type: live
title: <City> 311 service requests near this address
stone: touchstone
adapter: ckan_records

spatial: {scope: point, crs: EPSG:4326}

config:
  ckan_base: https://data.<city>.gov
  resource_id: <ckan-uuid>
  lat_field: latitude
  lon_field: longitude
  radius_m: 300
  limit: 500
  sample_fields: [<a few descriptive fields>]
  count_by_field: <category field>
  order: <date_field> DESC
  cache_ttl_s: 1800
```

The CKAN adapter does bbox SQL push-down on the lat/lon columns and
then haversine-refines in Python — works for any CKAN datastore with
numeric lat/lon columns.

## Step 5 — Adjust the NOAA station (optional)

`water_level.yaml` calls `app.context.noaa_tides.summary_for_point`,
which auto-resolves the nearest NOAA CO-OPS station for an address.
You usually don't need to touch this — the federal pebble figures it
out.

If you want the manifest comment to be accurate, look up your city's
nearest station at <https://tidesandcurrents.noaa.gov/>. Examples:

| City    | NOAA station             |
|---------|--------------------------|
| NYC     | 8518750 (Battery)        |
| Chicago | 9087044 (Calumet Harbor) |
| Seattle | 9447130 (Seattle)        |
| SF      | 9414290 (San Francisco)  |
| Boston  | 8443970 (Boston Harbor)  |

## Step 6 — Run the probe

```bash
RIPRAP_DEPLOYMENT=deployments/<your-city> RIPRAP_RECONCILER_TIER=no_llm \
.venv/bin/python -c "
import riprap.core.burr.app as a
r = a.run('<your test address>')
print(r['paragraph'])
print('compliance:', r['compliance'])
"
```

Expected: a Markdown paragraph with **Live Observer.**, **Projector.**,
etc. headers, citations like `[<city>_311]` and `[nws_obs]`, and
`compliance: {'passed': True, 'n_passed': 13, 'n_total': 13, ...}`.

Add your city to the sweep:

```python
# scripts/probe_cities.py
PROBES.append({
    "deployment": "deployments/<your-city>",
    "address": "<your test address>",
    "expect_city_pebble": "<city>_311",
    "expect_federal": ["nws_obs", "nws_alerts"],
})
```

Then:

```bash
.venv/bin/python scripts/probe_cities.py
# Look for: N/N deployments PASS
```

## Step 7 — Open a PR

The PR template asks for the address you tested against and the
compliance result. If you got 13/13 from the probe, you're done.

If you can also include:

- Screenshots of the briefing rendered in the UI
- A line in `docs/multi-city.md` adding your city to the cities table
- A `CHANGELOG.md` entry under `[Unreleased]`

That's the polished version. None of those are strictly required to
ship the deployment.

## Common gotchas

**Geocoder picks the wrong place.** Riprap's geocoder has a fast-path
for NYC addresses (NYC Geosearch) and a fallback (OSM Nominatim) for
everything else. The fallback is triggered by a regex in
`app/geocode.py:_NON_NYC_HINT_RE` matching state codes + major city
names. If your address gets fuzzy-matched to a Brooklyn street, add
your state code or city name to that regex.

**Compliance fails.** Read the `failed` list:

```bash
RIPRAP_DEPLOYMENT=deployments/<city> RIPRAP_RECONCILER_TIER=no_llm \
.venv/bin/python -c "
import riprap.core.burr.app as a
r = a.run('<addr>')
print(r['compliance']['failed'])
"
```

Each entry names the predicate. Common ones:

- `every_pebble_has_provenance` — make sure your manifest has a
  `provenance:` block with at least `source_name`.
- `every_pebble_has_narration` — `narration.short` is the minimum.
- `compliance_failed_pebbles_have_fallback` — set
  `fallback.on_offline: skip` (the default) so the briefing still
  emits when your upstream is down.

**Spatial field returns 0 records.** Curl the dataset directly with a
hand-picked `within_circle` (Socrata) or `BETWEEN` (CKAN) to confirm
your spatial field name. Easy mistake: many Socrata datasets have a
`location_address` text field next to the `location` geometry field;
you want the latter.

## See also

- [`docs/byod.md`](byod.md) — for users who want to add their own
  data on top of any existing deployment, without forking.
- [`docs/multi-city.md`](multi-city.md) — current city roster +
  the framework claim.
- [`docs/VERIFICATION.md`](VERIFICATION.md) — what's verified
  deterministically against the current branch.
- [`examples/byod/`](../examples/byod/) — real-data BYOD walkthrough
  using NYC FDNY firehouses (`hc8x-tcnd`).
