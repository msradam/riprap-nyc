# BYOD — Bring Your Own Data

Riprap's deployments are directories of YAML. **BYOD** lets you layer
your own pebbles on top of any base deployment without forking the repo,
without editing any code, and without recompiling the registry — drop a
manifest into one of two known locations and the next briefing includes
your data alongside the city defaults.

## TL;DR

```bash
# Option 1 — drop into ./.riprap/ in your CWD
mkdir -p .riprap && cp examples/byod/fdny_firehouses.{yaml,csv} .riprap/
RIPRAP_DEPLOYMENT=deployments/nyc RIPRAP_RECONCILER_TIER=no_llm \
  .venv/bin/python -c "import riprap.core.burr.app as a; \
    print(a.run('189 Atlantic Ave, Brooklyn, NY')['fdny_firehouses'])"

# Option 2 — point an env var at a directory (or single YAML)
RIPRAP_DEPLOYMENT=deployments/nyc \
RIPRAP_EXTRA_MANIFESTS=examples/byod \
RIPRAP_RECONCILER_TIER=no_llm \
  .venv/bin/python -c "import riprap.core.burr.app as a; \
    print(a.run('189 Atlantic Ave, Brooklyn, NY')['fdny_firehouses'])"
```

Both verified working — see "Verified output" below.

## The two load paths

`riprap/core/pebbles/registry.py:load_registry` merges manifests in this
order (later writers win on id collisions):

1. **Base deployment** — `deployments/<name>/manifests/*.yaml`
2. **`.riprap/` auto-discovery** — `${CWD}/.riprap/**/*.yaml`
3. **`RIPRAP_EXTRA_MANIFESTS` env var** — colon-separated list of paths;
   each entry is a directory (loaded recursively, sorted) or a single
   `.yaml` file.

A BYOD pebble with the same `id` as a base pebble **overrides** it, and
the registry logs a warning so you know it happened.

## Path resolution

Base-deployment manifests resolve relative paths against the deployment
root (so `data/foo.tif` means `<deployment>/data/foo.tif`). BYOD
manifests resolve relative paths against **the manifest's own directory**,
so you can drop a manifest and a CSV side-by-side anywhere on disk:

```
~/projects/my-portfolio/
  .riprap/
    portfolio.yaml      # refers to:
    portfolio.csv       # ← this file
```

This is enforced by `BasePebble.manifest_dir`, which `load_registry`
sets to `yaml_path.parent` for BYOD pebbles and leaves `None` for base
ones (preserving the existing deployment layout).

## Worked example — FDNY firehouses as a BYOD portfolio

`examples/byod/` ships a real NYC Open Data CSV — 219 FDNY firehouses
across the five boroughs (real addresses, real lat/lon, pulled from
`hc8x-tcnd` on data.cityofnewyork.us) — treated as if it were a
user-supplied facility portfolio.

The manifest is a thin `csv_points` adapter config:

```yaml
id: fdny_firehouses
type: baked
title: FDNY firehouses near this address
stone: keystone
adapter: csv_points
config:
  path: fdny_firehouses.csv     # resolves to examples/byod/fdny_firehouses.csv
  lat_col: latitude
  lon_col: longitude
  query: {type: radius_point, radius_m: 1500}
  feature_properties: [facilityname, facilityaddress, borough, postcode, nta]
  aggregations:
    n_firehouses_in_radius: {op: count, field: latitude}
provenance:
  source_name: NYC Open Data — FDNY Firehouses (hc8x-tcnd)
  source_url: https://data.cityofnewyork.us/d/hc8x-tcnd
  ...
```

Swap the CSV for your own (any lat/lon-bearing portfolio), keep the
manifest mostly intact, and you've added a custom pebble. No code
changes.

## Verified output

**1. NYC deployment, 189 Atlantic Ave, Brooklyn — via `RIPRAP_EXTRA_MANIFESTS`**

```
fdny_firehouses populated: True
  n_within_radius: 4
  radius_m: 1500
  aggregations: {'n_firehouses_in_radius': 4.0}
  nearest: Engine 224 @ 274 Hicks Street (454.1 m, Brooklyn Heights-Cobble Hill)
Compliance: 13 / 13 ✓
```

**2. NYC deployment, 80 Pioneer Street, Red Hook — via `.riprap/`**

```
fdny_firehouses populated: True
  n_within_radius: 2
  nearest: Battalion 32 / Engine 202 / Ladder 101
Compliance: 13 / 13 ✓
```

**3. Boston deployment, 1 City Hall Square — same BYOD pebble, cross-deployment**

```
fdny_firehouses populated: True
  n_within_radius (FDNY in Boston area): 0    # correct — NYC-only CSV
  nearest distance: 282.4 km                  # correct — Manhattan from Boston
boston_311 n_records: 396                     # Boston-native pebble still flows
Compliance: 13 / 13 ✓
```

The same BYOD pebble layers cleanly on every base deployment. Spatial
mismatches degrade silently (zero records, no errors).

## What adapters are available for BYOD?

Every adapter the base deployments use, registered in
`riprap/core/pebbles/adapters/__init__.py`:

| Adapter | Use for |
|---|---|
| `csv_points` | Tabular point data with lat/lon columns (local file or URL) |
| `baked_vector` | GeoJSON / Shapefile / Parquet of points or polygons |
| `socrata_records` | Any Socrata SODA endpoint (NYC, Chicago, Seattle, SF, DC, ...) |
| `ckan_records` | Any CKAN datastore_search_sql endpoint (Boston, Philly, EU portals, ...) |
| `rest_json` | Generic REST JSON endpoint with a JMESPath shape extraction |
| `python_call` | Call a Python function in your env — escape hatch for anything custom |
| `local_corpus_with_ner` | Local PDF corpus + entity extraction (used by `policy_corpus`) |

## Override semantics

```bash
# Base deployment ships `nws_obs`. Drop a BYOD manifest with id: nws_obs
# (e.g. pointing at a different upstream) and your version wins:

cat > .riprap/my_nws_obs.yaml <<'EOF'
id: nws_obs
type: live
adapter: rest_json
config:
  url: https://my-private-weather-api.example.com/obs?lat={lat}&lon={lon}
  shape: {path: data}
...
EOF

# stderr will warn:
#   [registry] BYOD override: pebble 'nws_obs' from .riprap/my_nws_obs.yaml
#   shadows base deployment manifest
```

Use sparingly — overrides break the compliance audit if your replacement
returns a shape the predicates don't recognise.

## See also

- [`docs/multi-city.md`](multi-city.md) — generalising across cities
- [`examples/byod/`](../examples/byod/) — the worked FDNY example
- [`riprap/core/pebbles/registry.py`](../riprap/core/pebbles/registry.py) — the load merge logic
